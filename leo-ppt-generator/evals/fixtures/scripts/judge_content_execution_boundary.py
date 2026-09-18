#!/usr/bin/env python3
"""Content-quality case inline gate: enforce the declared stop boundary."""
from __future__ import annotations

import json
import os
import re
import sys


def records(raw: str) -> list[object]:
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        out = []
        for line in raw.splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


def calls(raw: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if value.get("type") == "tool_use":
                found.append((str(value.get("name", "")), json.dumps(
                    value.get("input", {}), ensure_ascii=False)))
            elif value.get("role") == "tool_call":
                call = value.get("tool_call", {})
                if isinstance(call, dict):
                    found.append((str(call.get("name", "")), json.dumps(
                        call.get("arguments", {}), ensure_ascii=False)))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for record in records(raw):
        walk(record)
    return found


def check(final_message: str, transcript: str) -> list[str]:
    errors: list[str] = []
    if "project/" not in final_message and "./project" not in final_message:
        errors.append("最终摘要未提供 project/ 产物路径")

    forbidden = re.compile(
        r"(?:image\s*[-_ ]?(?:generate|provider)|generate\s*[-_ ]?image|"
        r"dispatch\s+[^\n]{0,80}\bworker\b|\bworker\b[^\n]{0,80}\bdispatch\b)",
        re.I,
    )
    for name, payload in calls(transcript):
        lower = f"{name} {payload}"
        if re.search(r"worker", name, re.I) or re.search(r"provider", name, re.I):
            errors.append(f"停止点后仍调用 worker/provider: {name}")
        elif forbidden.search(lower):
            errors.append(f"停止点后出现图片生成或 worker 派发: {name}")
    return errors


def main() -> int:
    transcript_path = os.environ.get("EVAL_TRANSCRIPT_PATH", "")
    transcript = ""
    if transcript_path:
        try:
            with open(transcript_path, encoding="utf-8") as stream:
                transcript = stream.read()
        except OSError as exc:
            print(f"无法读取 transcript: {exc}", file=sys.stderr)
            return 1
    errors = check(os.environ.get("EVAL_FINAL_MESSAGE", ""), transcript)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
