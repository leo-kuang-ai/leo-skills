#!/usr/bin/env python3
# Negation-aware judge for the "control-plane blocked summary" case.
# The Skill must emit the canonical five-field block verbatim and must NOT claim
# it created a run. A per-line scan avoids false-firing on "本轮未创建 run" while
# still catching an un-negated "已创建 run".
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_all(values):
    missing = [v for v in values if v not in text]
    if missing:
        fail(f"缺少必需内容: {', '.join(missing)}")


fields = (
    "route: generate",
    "status: blocked",
    "reason_code: worker_capability_unavailable",
    "execution_eligibility: blocked",
    "next_action:",
)
require_all(fields)

negators = ("不", "未", "不会", "不得", "没有", "尚未")
for ln in text.splitlines():
    if "已创建" in ln and "run" in ln and not any(w in ln for w in negators):
        fail(f"发现未经否定的 run 创建声明: {ln.strip()}")
