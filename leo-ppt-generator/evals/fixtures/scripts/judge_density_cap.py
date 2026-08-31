#!/usr/bin/env python3
# 密度上限判据（advise）：论点页 6 要点 + 150 字超档，回复须指出要点 ≤3 与
# 正文字数 ≤80 字的上限（肯定表述，否定语境不算命中）。

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


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        # 表格单元格分隔符归一化："| **论点页** | **≤3 条** |" 不应拆断词组匹配。
        body = QUOTE_SPAN.sub("", sentence)
        body = re.sub(r"\|\s*\*{0,2}\s*", "", body)
        if any(re.search(p, body) for p in patterns) and not any(
            v in body for v in NEGATORS
        ):
            return True
    return False


if not positive(
    [
        r"要点[^。]{0,14}(≤|不超过|最多|上限).{0,4}(3|三)\s*条",
        r"(论点|证据|方案)页[^。]{0,12}(3|三)\s*条",
        r"(3|三)\s*条以内的?要点",
        r"要点[^。]{0,10}(3|三)\s*条",
    ]
):
    fail("缺少「论点页要点 ≤3」档位上限表述")

if not positive([r"80\s*字", r"字数[^。]{0,12}(≤|不超过|上限).{0,4}80"]):
    fail("缺少「每页正文 ≤80 字」字数上限表述")

if not positive([r"(删|减|砍|压缩|合并|精简)[^。]{0,12}(要点|文字|正文|字)"]):
    fail("缺少减法处置建议（先删内容不缩字号）")

print("density-cap: ok")
