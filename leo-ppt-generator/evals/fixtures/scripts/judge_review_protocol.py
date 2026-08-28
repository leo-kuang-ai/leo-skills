#!/usr/bin/env python3
# 多轮审查协议：镜头池轮换 + 连续两轮无 P1/P2 才收敛 + 台账（驳回须有依据）。
# 收敛判据句天然含"没有/无"，用直接短语匹配。

import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

QUOTE_SPAN = re.compile(r"(「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\")")

NEGATORS = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "需先", "需经", "未经",
    "才能", "前提", "没有", "无", "而不是", "并非",
)


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_any(values, label):
    if not any(v in text for v in values):
        fail(f"缺少{label}: {' | '.join(values)}")


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        body = QUOTE_SPAN.sub("", sentence)
        if any(re.search(p, body) for p in patterns) and not any(
            v in body for v in NEGATORS
        ):
            return sentence
    return None


def require_positive(patterns, label):
    if positive(patterns) is None:
        fail(f"缺少未被否定的{label}: {' | '.join(patterns)}")


def forbid_positive(patterns, label):
    hit = positive(patterns)
    if hit is not None:
        fail(f"出现不应有的{label}: {hit.strip()[:60]}")

require_any(("镜头",), "镜头池")
require_any(("轮换", "每轮", "并行"), "镜头轮换")
require_any(("连续两轮", "两轮无", "两轮没有", "两轮都没有"), "两轮收敛判据")
require_any(("台账", "记录"), "台账记录")
require_any(("驳回",), "驳回机制在场")
require_any(("依据", "理由"), "驳回须有依据")
