#!/usr/bin/env python3
# 双评审官可选档：两独立会话 + 分歧≥2 复议 + 不替代三证（可选档位）。

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

require_any(("双评审官", "两个独立", "两位独立", "独立评审", "独立会话"), "双评审官")
require_any(("大于等于 2", "大于等于2", "≥ 2", "≥2", ">= 2", "超过 2", "至少 2 分",
             "2 分"), "分歧阈值复议")
require_any(("不替代", "不代替", "补充", "不改变三证"), "不替代三证")
require_any(("可选", "显式", "高保障", "高要求", "高要求档"), "可选档位属性")
