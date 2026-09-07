#!/usr/bin/env python3
"""复核 skill-up 最终报告中的咨询工具边界，补足旧文本 Judge 的覆盖。"""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

JUDGE = Path(__file__).resolve().parents[1] / "evals/judges/judge_style_index.py"
SPEC = importlib.util.spec_from_file_location("style_trace_judge", JUDGE)
judge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge)


def check(result_path):
    result_path = Path(result_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    rows = []
    for case in result["case_results"]:
        response = case.get("response", "")
        prompt = case.get("prompt", "")
        advise = bool(re.search(r"interaction_mode\s*:\s*advise|status\s*:\s*advise", response) or re.search(r"\badvise\b", prompt))
        if not advise:
            continue
        directory = result_path.parent / case["case_id"] / case.get("configuration", "with_skill") / "outputs/agent/run"
        traces = sorted(directory.glob("*.jsonl"))
        raw = "\n".join(path.read_text(encoding="utf-8") for path in traces)
        errors = judge.advise_trace_errors(raw) if traces and judge.tool_calls(raw) else ["缺少原始工具轨迹"]
        rows.append({"case_id": case["case_id"], "status": "FAIL" if errors else "PASS", "errors": errors,
                     "trace_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in traces}})
    return {"kind": "style-advise-trace-check", "cases": rows, "checked": len(rows),
            "failed": sum(row["status"] == "FAIL" for row in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    report = check(args.result)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["failed"] > 0 or report["checked"] == 0)


if __name__ == "__main__":
    raise SystemExit(main())
