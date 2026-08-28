#!/usr/bin/env python3
# 固定件一致性：合同约定右下页码，某页落右上 = 失败，须逐页核对位置与字号。

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

# 判不通过类断言天然含否定词，直接短语匹配（否定过滤会自指误杀）。
require_any(("不能过", "不能通过", "判不通过", "不通过", "应判失败", "判失败",
             "打回", "不达标", "过不了", "未通过"), "判不通过")
# 逐页核对常以引用合同原文形式出现（在引号内），不做引号/否定过滤。
require_any(("逐页核对", "逐页一致", "每页一致", "逐页都", "页页"), "逐页核对要求")
require_any(("页码",), "页码议题")
# 类别词接受语义等价（本 case 主题即页码固定件；bad 回复不含页码/固定件词）。
require_any(("固定件", "页脚", "署名", "页码"), "固定件类别")
