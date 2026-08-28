#!/usr/bin/env python3
# 断言-来源三级：无来源数字须标 unknown 或求证，不得直接入页；修辞对比须标"示意"
# 且不得用图表版式。规则表述句天然含"不得/不能"，用直接短语匹配。

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

require_any(("unknown", "求证", "确认来源", "来源不明", "来源不足"), "unknown/求证处理")
require_any(("不得直接", "不能直接", "不入页", "不直接写入", "先求证", "向你确认",
             "标 unknown", "标为 unknown", "标记 unknown"), "无来源数字不入页")
require_any(("示意",), "示意标注")
# 示意不用图表版式：禁止类表达与图表词的组合变体多，用正则族覆盖。
if not re.search(
    r"(禁止|不能|不得|不应|不宜|不该|无法|拒绝|避免).{0,8}(用|使用|采用).{0,8}"
    r"(图表|柱状|bar|kpi)|(不用|避免)(图表|柱状)"
    r"|(图表版式|柱状图).{0,12}(不成立|不适用|不可|不能|就不|就不成立)",
    text, re.IGNORECASE,
) and not any(v in text for v in ("观点大字", "非图表", "大字对比")):
    fail("缺少示意不用图表版式的判定")
