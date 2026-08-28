#!/usr/bin/env python3
# 母版先行：execute 授权后仍须先产出逐页母版并等待确认，四段结构被提及，
# 且没有未经否定的"已开始生成"声明。

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

require_any(("母版", "逐页", "内容稿"), "母版/逐页稿请求")
# 标题段断言：接受"结论句"语义词，或逐页母版中"标题：/- 标题"字段式传达。
require_any(("结论句", "结论式标题", "一句话结论", "标题即结论", "结论先行",
             "标题：", "- 标题", "＊?标题段"), "结论句标题段")
require_any(("视觉行", "落位", "容器"), "视觉行/落位段")
require_any(("备注",), "备注段")
require_positive((r"确认|审阅|等待", ), "等待用户确认")
forbid_positive((r"已(开始)?生成", r"开始直接生成", r"图片已生成"), "生成声明")
