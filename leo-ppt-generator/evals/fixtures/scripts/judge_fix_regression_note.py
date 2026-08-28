#!/usr/bin/env python3
# 修复波及复查：worker 重做后 qa_note 只写"已修复"不构成通过；须要求目标判据结论
# 与波及面结论两部分。拒绝类断言天然含否定词，用直接短语匹配。

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

require_any(("目标判据", "本次失败", "失败项"), "目标判据要求")
require_any(("波及", "新缺陷", "副作用"), "波及面要求")
require_any(("不能接受", "不算通过", "不构成通过", "不能过", "应补", "需要补",
             "应同时写", "需要同时写", "不算数"), "拒绝只写已修复")
require_any(("密度", "截断", "对比度", "双线索", "样张继承", "遮挡"), "波及面示例通道")
