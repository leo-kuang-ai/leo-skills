#!/usr/bin/env python3
# 交叉引用存在性：10 页 deck 内写"见第 12 页"= 失败，须与实际页码核对。

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

require_any(("不能过", "不能通过", "判失败", "应判失败", "须修正", "需要修正",
             "打回", "应修正"), "判失败/须修正")
require_any(("实际页码", "页码核对", "存在性", "核对", "页数"), "与实际页码核对")
require_any(("第 12 页", "第12页", "12 页", "越界", "不存在的页"), "越界引用议题")
