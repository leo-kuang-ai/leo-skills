#!/usr/bin/env python3
r"""Delivery preflight aggregator (R-59): one machine-readable truth file.

Before any delivery claim, the verification split currently spans several
independent exit codes (delivery-receipt.json fingerprints + per-script
runs). This aggregator runs the pre-delivery gates in order and lands a
single report at <run>/reports/delivery-preflight.json (claude-blog
preflight-report.json shape: gates[] with per-gate status + a WARN list +
not-run list). The delivery disclosure then cites this one file.

Gates (invoked as subprocesses of the sibling scripts, same interpreter):
  deck_geometry    check_deck_geometry.py <pptx>            exit 1 → failed
  sources_manifest check_sources_manifest.py <run> --strict  exit 1 → failed,
                                                              exit 2 → warn
  sensitive_text   check_sensitive_text.py <master> --json   candidates are
                                                              leads: hits > 0
                                                              → warn, 0 → pass
  delivery_receipt reports/delivery-receipt.json presence + freshness.
                   The runtime CLI exposes no standalone verify subcommand
                   (verification lives inside run-state delivery_readiness),
                   so we import verify_delivery_receipt from the runtime
                   source tree when importable; otherwise degrade honestly
                   to presence + parse check reported as "present_unverified"
                   (warn, never silently passed).

Missing inputs are reported as not_run and listed — never fabricated as
passed. Gate failure keeps exit 1 so CI/bench can assert "report exists and
all gates passed".

Determinism: fixed gate order, fixed probe order, no clock, sorted JSON keys.

Usage:
  build_delivery_preflight.py <run-dir> [--master FILE] [--pptx FILE] [--out FILE]

Exit codes: 0 = report written, no failed gate (warn/not_run allowed);
1 = report written, at least one gate failed; 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_USAGE = 2

SCRIPTS_DIR = Path(__file__).resolve().parent
RECEIPT_RELATIVE = Path("reports") / "delivery-receipt.json"
MASTER_PROBE_RES = ("content/deck-master.md", "deck-master.md", "master.md")
GATE_ORDER = ("deck_geometry", "sources_manifest", "sensitive_text",
              "delivery_receipt")


def _run_gate(command: list[str]) -> dict:
    proc = subprocess.run(command, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "stdout_tail": proc.stdout.strip().splitlines()[-3:],
        "stderr_tail": proc.stderr.strip().splitlines()[-3:],
    }


def probe_pptx(run_dir: Path, explicit: str | None) -> Path | None:
    """Deterministic delivery-pptx probe: explicit arg, then sorted last hit."""
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.is_file() else None
    for pattern in ("*.pptx", "image-deck/*.pptx", "output/*.pptx"):
        hits = sorted(run_dir.glob(pattern))
        if hits:
            return hits[-1]
    return None


def probe_master(run_dir: Path, explicit: str | None) -> Path | None:
    """Master probe: explicit arg, then versioned content copies (max v)."""
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.is_file() else None
    versioned = sorted((run_dir / "content").glob("deck-master-v*.md"))
    if versioned:
        return versioned[-1]
    for rel in MASTER_PROBE_RES:
        candidate = run_dir / rel
        if candidate.is_file():
            return candidate
    return None


def gate_geometry(pptx: Path | None) -> tuple[dict, list[str]]:
    if pptx is None:
        return ({"gate": "deck_geometry", "status": "not_run",
                 "detail": "run 目录未找到交付 PPTX（可用 --pptx 指定）"},
                ["deck_geometry: 未运行（无 PPTX 输入）"])
    command = [sys.executable, str(SCRIPTS_DIR / "check_deck_geometry.py"), str(pptx)]
    result = _run_gate(command)
    status = {0: "passed", 1: "failed"}.get(result["exit_code"], "not_run")
    warnings: list[str] = []
    if status == "not_run":
        warnings.append(f"deck_geometry: 未运行（exit {result['exit_code']}，输入/用法错误）")
    row = {"gate": "deck_geometry", "status": status, "command": command,
           "target": str(pptx), "exit_code": result["exit_code"],
           "stdout_tail": result["stdout_tail"], "stderr_tail": result["stderr_tail"]}
    return row, warnings


def gate_sources(run_dir: Path) -> tuple[dict, list[str]]:
    manifest = run_dir / "input" / "sources-manifest.json"
    if not manifest.is_file() and not (run_dir / "sources-manifest.json").is_file():
        return ({"gate": "sources_manifest", "status": "not_run",
                 "detail": "run 目录未找到 input/sources-manifest.json"},
                ["sources_manifest: 未运行（无 manifest）"])
    command = [sys.executable, str(SCRIPTS_DIR / "check_sources_manifest.py"),
               str(run_dir), "--strict"]
    result = _run_gate(command)
    code = result["exit_code"]
    status = {0: "passed", 1: "failed", 2: "warn"}.get(code, "not_run")
    warnings: list[str] = []
    if status == "warn":
        warnings.append("sources_manifest: WARN 档（可交付但须披露低审查状态图等）")
    if status == "not_run":
        warnings.append(f"sources_manifest: 未运行（exit {code}）")
    return ({"gate": "sources_manifest", "status": status, "command": command,
             "exit_code": code, "stdout_tail": result["stdout_tail"],
             "stderr_tail": result["stderr_tail"]}, warnings)


def gate_sensitive(master: Path | None) -> tuple[dict, list[str]]:
    if master is None:
        return ({"gate": "sensitive_text", "status": "not_run",
                 "detail": "未定位到母版（可用 --master 指定）"},
                ["sensitive_text: 未运行（无母版输入）"])
    command = [sys.executable, str(SCRIPTS_DIR / "check_sensitive_text.py"),
               str(master), "--json"]
    result = _run_gate(command)
    if result["exit_code"] != 0:
        return ({"gate": "sensitive_text", "status": "not_run", "command": command,
                 "target": str(master), "exit_code": result["exit_code"],
                 "stderr_tail": result["stderr_tail"]},
                [f"sensitive_text: 未运行（exit {result['exit_code']}）"])
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        payload = {}
    candidates = payload.get("candidate_count")
    # Candidates are leads, not verdicts (two-layer discipline): they warn,
    # they never block delivery.
    status = "warn" if isinstance(candidates, int) and candidates > 0 else "passed"
    warnings = ([f"sensitive_text: {candidates} 处词面候选（线索级，待语境层复核）"]
                if status == "warn" else [])
    return ({"gate": "sensitive_text", "status": status, "command": command,
             "target": str(master), "candidate_count": candidates,
             "exit_code": result["exit_code"]}, warnings)


def _load_receipt_verifier():
    """Import the runtime verifier when its source tree is importable."""
    runtime_src = SCRIPTS_DIR.parents[0] / "runtime" / "src"
    if not runtime_src.is_dir():
        return None
    sys.path.insert(0, str(runtime_src))
    try:
        from leo_ppt_generator.render.receipt import verify_delivery_receipt
        return verify_delivery_receipt
    except Exception:
        return None


def gate_receipt(run_dir: Path) -> tuple[dict, list[str]]:
    receipt_path = run_dir / RECEIPT_RELATIVE
    if not receipt_path.is_file():
        return ({"gate": "delivery_receipt", "status": "not_run",
                 "detail": "无交付收据（delivery-receipt.json 缺失）",
                 "target": str(receipt_path)},
                ["delivery_receipt: 未运行（无收据文件）"])
    verifier = _load_receipt_verifier()
    if verifier is None:
        # Honest degradation: we can see the receipt exists but cannot
        # recompute its fingerprints here — report as unverified, not passed.
        try:
            json.loads(receipt_path.read_text(encoding="utf-8"))
            parseable = True
        except (OSError, json.JSONDecodeError):
            parseable = False
        status = "warn" if parseable else "failed"
        return ({"gate": "delivery_receipt", "status": status,
                 "detail": None if parseable else "收据 JSON 不可解析",
                 "verification": "present_unverified",
                 "target": str(receipt_path)},
                (["delivery_receipt: 收据存在但无法在本环境重算指纹（present_unverified）"]
                 if parseable else ["delivery_receipt: 收据 JSON 不可解析"]))
    try:
        outcome = verifier(run_dir)
    except Exception:
        outcome = {"status": "invalid", "fresh": False}
    status = {"fresh": "passed", "stale": "failed", "invalid": "failed"}.get(
        outcome.get("status"), "failed")
    warnings = ([] if status == "passed"
                else [f"delivery_receipt: 收据 {outcome.get('status')}（指纹不匹配或缺字段）"])
    return ({"gate": "delivery_receipt", "status": status,
             "verification": outcome.get("status"), "fresh": outcome.get("fresh"),
             "changed_count": len(outcome.get("changed") or []),
             "target": str(receipt_path)}, warnings)


def build_report(run_dir: Path, master: Path | None, pptx: Path | None) -> dict:
    rows: list[dict] = []
    warnings: list[str] = []
    for builder in (lambda: gate_geometry(pptx),
                    lambda: gate_sources(run_dir),
                    lambda: gate_sensitive(master),
                    lambda: gate_receipt(run_dir)):
        row, gate_warnings = builder()
        rows.append(row)
        warnings.extend(gate_warnings)
    not_run = [row["gate"] for row in rows if row["status"] == "not_run"]
    blocked = any(row["status"] == "failed" for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "delivery-preflight",
        "run": run_dir.name,
        "run_dir": str(run_dir),
        "gates": rows,
        "blocked": blocked,
        "not_run": not_run,
        "warnings": warnings,
        "note": "交付披露应引用本文件；未过门如实列出，候选敏感项是线索不是结论。",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="交付预检聚合（R-59）：geometry/sources/sensitive/receipt → "
                    "单文件 delivery-preflight.json")
    parser.add_argument("run", help="run 目录")
    parser.add_argument("--master", default=None, help="敏感扫描对象母版（默认探测 run 内母版）")
    parser.add_argument("--pptx", default=None, help="交付 PPTX（默认探测 run 内 *.pptx）")
    parser.add_argument("--out", default=None,
                        help="输出路径（默认 <run>/reports/delivery-preflight.json）")
    args = parser.parse_args(argv)

    run_dir = Path(args.run).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"run 目录不存在: {run_dir}", file=sys.stderr)
        return EXIT_USAGE

    master = probe_master(run_dir, args.master)
    pptx = probe_pptx(run_dir, args.pptx)
    report = build_report(run_dir, master, pptx)

    out = (Path(args.out).expanduser().resolve() if args.out
           else run_dir / "reports" / "delivery-preflight.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({
        "out": str(out),
        "blocked": report["blocked"],
        "gates": {row["gate"]: row["status"] for row in report["gates"]},
        "not_run": report["not_run"],
    }, ensure_ascii=False))
    return EXIT_BLOCKED if report["blocked"] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
