#!/usr/bin/env python3
"""素材存在性 / URL 可达性校验闭环（A3）。

机制改编自 OpenCanvas 的 image_validation（MIT）；本实现为 Python stdlib 原创重写，
据用户线下授权。退出码：0 全可达 / 1 存在不可达（阻断入页）/ 2 仅警告
（缓存过期、慢端点或 offline 跳过的 URL）。

用法：
  validate_assets.py <sources-manifest.json 或 slides.json/spec.json> [--offline]
  可选：--cache <path>（默认 <project-root>/sources/.asset-validation.json，
  环境变量 LEO_PPT_ASSET_CACHE 覆盖；--no-cache 禁用）

闭环合同（见 image-deck-workflow.md 第 1a 步）：素材校验失败 → 该素材标
`unknown`（禁止入页）→ 用户提供真实素材 / 改为 AI 生成并标示意 → 重跑校验 →
缓存 diff 展示替换前后。编造链接直接出图 = 红灯。缓存永不作为"通过"的替代：
交付前重跑必须全绿。

检查项：
- 本地：路径存在、可读、是图片（PIL 读头，与 contracts.py 同法）、sha256 与
  manifest 记录一致。
- URL：仅 https://（http:// 直接 FAIL）；HEAD（405 时降级 GET + Range 0-1024）；
  超时 10s；2xx/3xx 为可达；记录最终 URL 与 Content-Type 前缀。不下载整文件、
  不执行任何内容。--offline 模式完全不联网（URL 条目记 skipped_offline）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL_TIMEOUT_SECONDS = 10
SLOW_WARN_SECONDS = 5
CACHE_TTL_DAYS = 7


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_targets(data) -> list[dict]:
    """从 sources manifest 或 slides.json/spec 收集待校验素材条目。"""
    items: list[dict] = []
    if isinstance(data, dict) and data.get("manifest_kind") == "visual-sources":
        for page in data.get("pages", []):
            for visual in page.get("visuals", []):
                ref = visual.get("source_ref")
                if isinstance(ref, str) and ref.strip():
                    items.append(
                        {
                            "ref": ref.strip(),
                            "sha256": visual.get("source_sha256"),
                            "page": page.get("page_id"),
                        }
                    )
        return items
    slides = data if isinstance(data, list) else data.get("slides", [])
    if isinstance(slides, list):
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            images = slide.get("required_images") or slide.get("input_images") or []
            if not isinstance(images, list):
                continue
            for entry in images:
                if isinstance(entry, dict):
                    ref = entry.get("path") or entry.get("attachment")
                    if isinstance(ref, str) and ref.strip():
                        items.append({"ref": ref.strip(), "sha256": None, "page": None})
                elif isinstance(entry, str) and entry.strip().startswith("https://"):
                    items.append({"ref": entry.strip(), "sha256": None, "page": None})
    return items


def derive_cache_path(target: Path, override: str | None) -> Path | None:
    if override:
        return Path(override)
    env = os.environ.get("LEO_PPT_ASSET_CACHE")
    if env:
        return Path(env)
    # run 布局：<run>/input/sources-manifest.json → <run>
    root = target.resolve().parent
    if root.name == "input":
        root = root.parent
    # content 布局：<project>/content/sources-manifest.json → <project>
    elif root.name == "content":
        root = root.parent
    return root / "sources" / ".asset-validation.json"


def check_local(ref: str, expected_sha: str | None, roots: list[Path]) -> dict:
    candidate = Path(ref)
    resolved = None
    if candidate.is_absolute():
        resolved = candidate if candidate.exists() else None
    else:
        for root in roots:
            merged = root / candidate
            if merged.is_file():
                resolved = merged
                break
    if resolved is None:
        return {"ref": ref, "kind": "local", "status": "missing", "detail": "文件不存在"}
    if not os.access(resolved, os.R_OK):
        return {"ref": ref, "kind": "local", "status": "unreadable", "detail": "不可读"}
    result: dict = {"ref": ref, "kind": "local", "status": "ok", "detail": str(resolved)}
    try:
        from PIL import Image  # noqa: PLC0415（按需导入，URL-only 场景不强制）

        with Image.open(resolved) as image:
            result["image_format"] = image.format
    except Exception as exc:  # PIL 缺失或非图片
        return {
            "ref": ref,
            "kind": "local",
            "status": "not_image",
            "detail": f"无法按图片读取（{exc}）",
        }
    if expected_sha:
        actual = sha256_file(resolved)
        result["sha256"] = actual
        if actual != expected_sha:
            result["status"] = "sha_mismatch"
            result["detail"] = f"sha256 不匹配（期望 {expected_sha[:12]}…）"
    return result


def check_url(ref: str) -> dict:
    started = time.monotonic()
    request = urllib.request.Request(ref, method="HEAD")
    request.add_header("User-Agent", "leo-ppt-generator/validate-assets")
    try:
        with urllib.request.urlopen(request, timeout=URL_TIMEOUT_SECONDS) as response:
            status_code = response.status
            final_url = response.geturl()
            content_type = (response.headers.get("Content-Type") or "").split(";")[0]
    except urllib.error.HTTPError as exc:
        if exc.code == 405:  # HEAD 不被支持 → 降级 GET + Range 0-1024
            ranged = urllib.request.Request(ref)
            ranged.add_header("Range", "bytes=0-1024")
            try:
                with urllib.request.urlopen(ranged, timeout=URL_TIMEOUT_SECONDS) as response:
                    status_code = response.status
                    final_url = response.geturl()
                    content_type = (response.headers.get("Content-Type") or "").split(";")[0]
            except urllib.error.HTTPError as inner:
                return _url_fail(ref, f"HTTP {inner.code}")
            except (urllib.error.URLError, OSError, TimeoutError) as inner:
                return _url_fail(ref, f"网络错误：{inner}")
        else:
            return _url_fail(ref, f"HTTP {exc.code}")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return _url_fail(ref, f"网络错误：{exc}")
    elapsed = time.monotonic() - started
    if not 200 <= status_code < 400:
        return _url_fail(ref, f"HTTP {status_code}")
    result = {
        "ref": ref,
        "kind": "url",
        "status": "ok",
        "detail": f"HTTP {status_code}",
        "final_url": final_url,
        "content_type": content_type,
        "elapsed_ms": int(elapsed * 1000),
    }
    if elapsed > SLOW_WARN_SECONDS:
        result["status"] = "reachable_slow"
        result["detail"] += f"（>{SLOW_WARN_SECONDS}s，慢端点）"
    return result


def _url_fail(ref: str, detail: str) -> dict:
    return {"ref": ref, "kind": "url", "status": "unreachable", "detail": detail}


def exit_code(results: list[dict]) -> int:
    if any(item["status"] in ("missing", "unreadable", "not_image", "sha_mismatch", "bad_scheme", "unreachable") for item in results):
        return 1
    if any(item["status"] in ("cache_expired", "reachable_slow", "skipped_offline") for item in results):
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="sources manifest 或 slides.json/spec 路径")
    parser.add_argument("--offline", action="store_true", help="只做本地检查，完全不联网")
    parser.add_argument("--cache", help="缓存文件路径（默认 <root>/sources/.asset-validation.json）")
    parser.add_argument("--no-cache", action="store_true", help="禁用缓存读写")
    args = parser.parse_args(argv)

    target = Path(args.target)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"FAIL 无法读取 {target}：{exc}")
        return 1
    entries = collect_targets(data)
    if not entries:
        print("OK 未发现待校验素材（无 source_ref / required_images）")
        return 0

    roots = [target.resolve().parent, target.resolve().parent.parent, Path.cwd()]
    cache_path = None if args.no_cache else derive_cache_path(target, args.cache)
    previous: dict = {}
    if cache_path is not None and cache_path.is_file():
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                previous = loaded
        except (OSError, ValueError):
            previous = {}

    results: list[dict] = []
    for entry in entries:
        ref = entry["ref"]
        if ref.startswith("https://"):
            if args.offline:
                results.append(
                    {"ref": ref, "kind": "url", "status": "skipped_offline", "detail": "offline 模式不联网"}
                )
            else:
                results.append(check_url(ref))
        elif ref.startswith("http://"):
            results.append(
                {"ref": ref, "kind": "url", "status": "bad_scheme", "detail": "仅允许 https://"}
            )
        else:
            results.append(check_local(ref, entry.get("sha256"), roots))

    # 缓存 diff：本次结果与上次缓存不同的条目即"替换/变化"，输出前后状态。
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=CACHE_TTL_DAYS)
    cache_updates: dict = dict(previous)
    for item in results:
        old = previous.get(item["ref"])
        if old and old.get("status") != item["status"]:
            item["cache_diff"] = {"before": old.get("status"), "after": item["status"]}
        record = {
            "status": item["status"],
            "checked_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        for key in ("final_url", "content_type", "sha256", "detail"):
            if item.get(key) is not None:
                record[key] = item[key]
        cache_updates[item["ref"]] = record
        # 缓存过期只在"本次未实测、依赖旧缓存"的场景降级为 WARN（offline 跳过）；
        # 本次已实测的条目以实测结果为准，缓存永不作为"通过"的替代。
        if item["status"] == "skipped_offline" and isinstance(old, dict) and old.get("status") == "ok":
            stamp = old.get("checked_at", "")
            if stamp.endswith("Z"):
                try:
                    if datetime.fromisoformat(stamp[:-1]).replace(tzinfo=timezone.utc) < cutoff:
                        item["status"] = "cache_expired"
                        item["detail"] = (
                            f"offline 依赖的缓存已过期（> {CACHE_TTL_DAYS} 天），交付前须联网重验"
                        )
                except ValueError:
                    pass

    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(cache_updates, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"WARN 缓存写入失败（{exc}）；校验结果不受影响")

    for item in results:
        marker = {"ok": "OK", "cache_expired": "WARN", "reachable_slow": "WARN", "skipped_offline": "WARN"}.get(
            item["status"], "FAIL"
        )
        diff = ""
        if item.get("cache_diff"):
            diff = (
                f" | 替换/变化：{item['cache_diff']['before']} -> {item['cache_diff']['after']}"
            )
        print(f"{marker} [{item['kind']}] {item['ref']}: {item['status']} {item['detail']}{diff}")

    code = exit_code(results)
    print(
        json.dumps(
            {
                "target": str(target),
                "offline": args.offline,
                "items": len(results),
                "exit_code": code,
                "cache": str(cache_path) if cache_path else None,
            },
            ensure_ascii=False,
        )
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
