#!/usr/bin/env python3
"""串行验证表达重构；记录真实进程退出码、完整日志与验证期间源码漂移。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "runtime/.venv/bin/python"


def source_snapshot():
    paths = subprocess.check_output(["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    hashes = {}
    prefixes = ("runtime/src/", "scripts/", "tests/", "evals/fixtures/", "template-library/canonical/",
                "template-library/governance/", "template-library/catalog/", "template-library/evidence/")
    for relative in sorted(set(paths)):
        path = ROOT / relative
        if relative and (relative.startswith(prefixes) or relative == "template-library/library.json") and path.is_file():
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "files": hashes}


def commands():
    python = str(PYTHON)
    def tests(*names):
        return [python, "-m", "unittest", *["tests." + name for name in names]]
    return [
        ("compileall", [python, "-m", "compileall", "-q", "runtime/src", "scripts", "tests"]),
        ("schemas", tests("test_library_contracts", "test_page_expression_contract", "test_execution_pairing", "test_image_expression_adapter")),
        ("regime-lint", [python, "scripts/lint_page_type_regime.py"]),
        ("layout-lint", [python, "scripts/lint_layout_grid.py"]),
        ("template-lint", [python, "scripts/lint_template_contract.py"]),
        ("expression-consumers", tests("test_content_pack", "test_content_projection", "test_content_preview",
            "test_binding_v2", "test_deck_layout_selection", "test_expression_pipeline", "test_deck_projection_view",
            "test_task_local_expression_proposals", "test_qualification_evidence", "test_relation_oracle")),
        ("migration", tests("test_migration_phases", "test_library_catalog", "test_library_bundle", "test_style_aliases_migration")),
        ("quality", tests("test_expression_quality_channels", "test_quality_scorecard", "test_quality_metrics",
                           "test_compute_impact", "test_visual_measure_rules", "test_visual_qa")),
        ("full-suite", [python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--step", action="append", choices=[name for name, _ in commands()])
    args = parser.parse_args(argv)
    out = args.out.absolute()
    if not out.is_relative_to(ROOT) or any(p.is_symlink() for p in (out, *out.parents)):
        parser.error("验证证据输出必须在当前技能目录内，且不能包含符号链接")
    out.mkdir(parents=True, exist_ok=False)
    from leo_ppt_generator.storage import atomic_write_json
    report = {"schema_version": 1, "kind": "expression-verification-run", "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running", "full_ordered_run": args.step is None, "source_before": source_snapshot(), "commands": []}
    manifest = out / "verification.json"
    atomic_write_json(manifest, report)
    environment = dict(os.environ, PYTHONPATH="runtime/src")
    for name, command in commands():
        if args.step is not None and name not in args.step:
            continue
        row = {"step": name, "argv": command, "cwd": str(ROOT), "log": name + ".log", "status": "running"}
        report["commands"].append(row)
        started = time.monotonic()
        with (out / row["log"]).open("wb") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
            row["pid"] = process.pid
            atomic_write_json(manifest, report)
            try:
                code = process.wait()
            except BaseException:
                process.terminate()
                code = process.wait()
                row.update(status="interrupted", exit_code=code)
                report["status"] = "interrupted"
                atomic_write_json(manifest, report)
                raise
        row.update(exit_code=code, status="passed" if code == 0 else "failed", duration_seconds=round(time.monotonic() - started, 3),
                   log_sha256=hashlib.sha256((out / row["log"]).read_bytes()).hexdigest())
        atomic_write_json(manifest, report)
        print(json.dumps({key: row[key] for key in ("step", "exit_code", "duration_seconds", "log")}), flush=True)
    report["source_after"] = source_snapshot()
    report["source_stable"] = report["source_before"] == report["source_after"]
    report["status"] = "passed" if report["source_stable"] and all(row["exit_code"] == 0 for row in report["commands"]) else "failed"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(manifest, report)
    print(json.dumps({"manifest": str(manifest), "status": report["status"], "source_stable": report["source_stable"]}), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
