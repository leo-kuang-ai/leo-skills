#!/usr/bin/env python3
"""provider_health.py —— 渠道健康三级体检（加固方案 2026-09-07-002 WS1）。

用法：
  python3 scripts/provider_health.py [--level 1|2|3] [--providers p1,p2]
                                     [--probe] [--json]

级别：
  L1 静态    凭据在场性 + 渠道目录注册 + 模型矩阵登记（零成本）
  L2 参数面  各渠道默认模型经 vendored dry-run：模型名校验/参数门控/
             尺寸档约束查表（零成本，无需凭据）
  L3 探活    一张最小图真实生成（每渠道一张图费用；--probe 或 --level 3），
             回写 $LEO_PPT_HOME/observability/channel-health.jsonl

退出码：0 全部受检渠道达到请求级别；1 存在失败/阻断；2 用法错误。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "runtime" / "src"))

from leo_ppt_generator.config.channel_catalog import (  # noqa: E402
    channel_by_name,
    channel_names,
)
from leo_ppt_generator.credentials import credential_manager  # noqa: E402

VENDOR_IMAGE_GEN = (
    SKILL_ROOT / "runtime" / "src" / "leo_ppt_generator" / "_vendor"
    / "codex_ppt" / "image_gen.py"
)
PROBE_PROMPT = (
    "Minimal clean 16:9 presentation cover, off-white background, one short "
    "Chinese title text \"渠道探活\", no other text, no watermark."
)
# 未登记约束时仅使用默认请求尺寸，不代表远端支持已验证。
FALLBACK_PROBE_SIZE = "2560x1440"


def _python() -> str:
    return sys.executable


def _home() -> Path:
    raw = os.environ.get("LEO_PPT_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / "Library" / "Application Support" / "leo-ppt-generator"


def _credential_state(channel_id: str) -> dict:
    channel = channel_by_name(channel_id)
    if channel is None:
        return {"registered": False}
    env_name = channel.credential_environment
    state = {
        "registered": True,
        "credential_environment": env_name,
        "in_process_env": bool(os.environ.get(env_name)),
    }
    # 与 backend_execution 同源：keychain 引用 keychain:leo-ppt-generator/<id>。
    try:
        manager = credential_manager()
        secret = manager.resolve("keychain", f"leo-ppt-generator/{channel_id}")
        state["keychain_resolved"] = bool(secret)
    except Exception as exc:  # noqa: BLE001 —— 健康体检必须吞掉凭据层异常并如实记录
        state["keychain_resolved"] = False
        state["keychain_error"] = str(exc)[:120]
    return state


def _level1(channel_id: str) -> dict:
    channel = channel_by_name(channel_id)
    if channel is None:
        return {"provider": channel_id, "registered": False, "status": "unregistered"}
    compat = channel.param_compat
    credential = _credential_state(channel_id)
    return {
        "provider": channel_id,
        "registered": True,
        "default_model": channel.default_model,
        "param_compat": {
            "rejects": list(compat.rejects),
            "size": dict(compat.size),
        },
        "credential": credential,
        "status": "ok" if (credential.get("in_process_env") or
                           credential.get("keychain_resolved")) else "credentials_missing",
    }


def _probe_size(channel_id: str) -> str | None:
    channel = channel_by_name(channel_id)
    if channel is None:
        return None
    if not channel.param_compat.size:
        return FALLBACK_PROBE_SIZE
    constraints = dict(channel.param_compat.size)
    # 精确 16:9 尺寸为 (16k, 9k)；两边均为 m 的倍数等价于 k 为 m 的倍数。
    step = constraints.get("multiples_of", 1)
    min_k = max(1, (constraints.get("min_edge", 1) + 8) // 9)
    min_k = (min_k + step - 1) // step * step
    max_k = max(160, min_k)
    if "max_edge" in constraints:
        max_k = min(max_k, constraints["max_edge"] // 16)
    if "max_pixels" in constraints:
        max_k = min(max_k, math.isqrt(constraints["max_pixels"] // 144))
    k = max_k // step * step
    return f"{16 * k}x{9 * k}" if k >= min_k else None


def _level2(channel_id: str) -> dict:
    """参数面：vendored dry-run（模型/参数门控/尺寸档查表），无需凭据。"""

    channel = channel_by_name(channel_id)
    if channel is None:
        return {"provider": channel_id, "status": "unregistered"}
    compat = channel.param_compat
    env = dict(os.environ)
    env.pop("LEO_PPT_PARAM_COMPAT", None)
    env["CODEX_PPT_IMAGE_MODEL"] = channel.default_model
    if compat.rejects or compat.size:
        env["LEO_PPT_PARAM_COMPAT"] = compat.as_env_json()
    size = _probe_size(channel_id)
    if size is None:
        return {"provider": channel_id, "status": "aspect_ratio_unsupported",
                "size": None, "constraints": dict(compat.size)}
    result = subprocess.run(
        [_python(), str(VENDOR_IMAGE_GEN), "generate", "--dry-run",
         "--model", channel.default_model, "--size", size,
         "--prompt", "probe", "--out", "/tmp/leo-health-probe.png"],
        capture_output=True, text=True, timeout=60, env=env,
    )
    if result.returncode != 0:
        return {
            "provider": channel_id, "status": "param_face_rejected",
            "size": size,
            "error": (result.stderr or result.stdout).strip().splitlines()[-1][:200]
            if (result.stderr or result.stdout).strip() else "unknown",
        }
    try:
        request = json.loads(result.stdout)
    except ValueError:
        return {"provider": channel_id, "status": "param_face_opaque", "size": size}
    violations: list[str] = []
    if "quality" in request and "quality" in compat.rejects:
        violations.append("quality-sent-despite-rejects")
    if "output_format" in request and "output_format" in compat.rejects:
        violations.append("output_format-sent-despite-rejects")
    status = "ok" if not violations else "compat_violation"
    return {
        "provider": channel_id, "status": status, "size": size,
        "sent_params": sorted(k for k in request if k not in ("outputs", "endpoint")),
        "violations": violations,
    }


def _level3(channel_id: str) -> dict:
    """探活：经 backend contract 走一张最小图（真实费用）。"""

    started = time.time()
    size = _probe_size(channel_id)
    if size is None:
        return {"provider": channel_id, "status": "aspect_ratio_unsupported", "size": None}
    with tempfile.TemporaryDirectory(prefix="leo-health-l3-") as tmp:
        contract = Path(tmp) / "backend.json"
        # 经 CLI 创建合同并生成（CLI 路径承载凭据解析与超时语义）。
        cli = os.environ.get("LEO_PPT_CLI")
        if not cli:
            boot = subprocess.run(
                ["bash", str(SKILL_ROOT / "scripts" / "leo-bootstrap.sh"), "print-cli"],
                capture_output=True, text=True, timeout=120,
            )
            cli = boot.stdout.strip().splitlines()[-1] if boot.returncode == 0 else ""
        if not cli:
            return {"provider": channel_id, "status": "cli_unavailable"}
        create = subprocess.run(
            [cli, "backend", "create", "--provider", channel_id, "--mode", "generate",
             "--output", str(contract), "--overwrite"],
            capture_output=True, text=True, timeout=120,
        )
        if '"status": "ready"' not in create.stdout:
            return {
                "provider": channel_id, "status": "contract_create_failed",
                "error": (create.stdout or create.stderr).strip()[-200:],
            }
        prompt = Path(tmp) / "probe.txt"
        prompt.write_text(PROBE_PROMPT, encoding="utf-8")
        out = Path(tmp) / "probe.png"
        gen = subprocess.run(
            [cli, "upstream", "--backend-contract", str(contract), "--timeout", "300",
             "codex-ppt", "--", "image", "generate", "--size", size,
             "--prompt-file", str(prompt), "--out", str(out)],
            capture_output=True, text=True, timeout=360,
        )
        elapsed = round(time.time() - started, 1)
        record = {
            "provider": channel_id,
            "status": "live_ok" if gen.returncode == 0 and out.is_file() and out.stat().st_size else "live_failed",
            "reason": _reason_code(gen.stdout),
            "probe_size": size,
            "elapsed_s": elapsed,
            "png_bytes": out.stat().st_size if out.is_file() else 0,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if out.is_file():
            health_dir = _home() / "observability"
            health_dir.mkdir(parents=True, exist_ok=True)
            with (health_dir / "channel-health.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record


def _reason_code(stdout: str) -> str | None:
    try:
        return json.loads(_last_json(stdout)).get("reason_code")
    except Exception:  # noqa: BLE001
        return None


def _last_json(text: str) -> str:
    idx = text.rfind('{"artifact_refs"')
    if idx == -1:
        idx = text.find("{")
    return text[idx:] if idx != -1 else "{}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--providers", default="")
    parser.add_argument("--probe", action="store_true", help="等价于 --level 3")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    level = 3 if args.probe else args.level

    wanted = [p.strip() for p in args.providers.split(",") if p.strip()] or list(channel_names())
    reports: list[dict] = []
    for provider in wanted:
        report = _level1(provider)
        if level >= 2 and report.get("registered"):
            report["level2"] = _level2(provider)
        if level >= 3 and report.get("registered"):
            if report.get("status") != "ok" or report.get("level2", {}).get("status") != "ok":
                report["level3"] = {"provider": provider, "status": "prerequisite_failed"}
            else:
                report["level3"] = _level3(provider)
        reports.append(report)

    failed = any(
        r.get("status") not in ("ok",)
        or (level >= 2 and r.get("level2", {}).get("status") not in ("ok", None))
        or (level >= 3 and r.get("level3", {}).get("status") not in ("live_ok", None))
        for r in reports
    )
    payload = {"level": level, "providers": reports, "summary": "fail" if failed else "ok"}
    print(json.dumps(payload, ensure_ascii=False, indent=1 if args.json else None))
    return 1 if failed else 0


import tempfile  # noqa: E402  （_level3 使用；置底避免顶部导入噪音）


if __name__ == "__main__":
    raise SystemExit(main())
