#!/usr/bin/env python3
"""Render the stable control-plane fields from a Leo CLI JSON envelope."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


ROUTES = {"generate", "direct-editable", "upgrade-full", "upgrade-selected"}
ELIGIBILITY = {"allowed", "blocked", "retryable", "unknown"}

# SKILL.md 固定阻断块的机器化出口：宿主可运行脚本时必须由此产生，禁止手写改写。
FIXED_BLOCKS = {
    "gate0": (
        "route: direct-editable\n"
        "status: blocked\n"
        "reason_code: untrusted_office_input\n"
        "input_handling: not_opened\n"
        "next_action: 提供可信确认，或改用 PDF/逐页图片"
    ),
    "worker-unavailable": (
        "route: generate\n"
        "status: blocked\n"
        "reason_code: worker_capability_unavailable\n"
        "execution_eligibility: blocked\n"
        "next_action: 提供可调用的 worker 能力后从逐页派发阶段恢复"
    ),
}


def _text(value: Any, default: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def render(payload: dict[str, Any]) -> str:
    route = _text(payload.get("route"), "未选择")
    if route not in ROUTES:
        route = "未选择"
    status = _text(payload.get("status"), "unknown")
    reason = _text(payload.get("reason_code"), "none")
    eligibility = _text(payload.get("execution_eligibility"), "unknown")
    if eligibility not in ELIGIBILITY:
        eligibility = "unknown"
    action = payload.get("next_action")
    if isinstance(action, dict):
        action = action.get("command") or action.get("kind") or action.get("step")
    action_text = _text(action, "none")
    lines = [
        f"route: {route}",
        f"status: {status}",
        f"reason_code: {reason}",
        f"execution_eligibility: {eligibility}",
        f"next_action: {action_text}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a stable Leo control-plane summary.")
    parser.add_argument("json_file", nargs="?", help="JSON file; defaults to stdin.")
    parser.add_argument(
        "--fixed",
        choices=sorted(FIXED_BLOCKS),
        help="直接输出一个固定阻断块；不读取任何文件或 stdin。",
    )
    args = parser.parse_args()
    if args.fixed:
        print(FIXED_BLOCKS[args.fixed])
        return 0
    try:
        raw = open(args.json_file, encoding="utf-8").read() if args.json_file else sys.stdin.read()
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"invalid control-plane JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("invalid control-plane JSON: expected object", file=sys.stderr)
        return 2
    print(render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
