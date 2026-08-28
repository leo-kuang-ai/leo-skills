#!/usr/bin/env python3
# Shared negation-aware judge helpers for quality-loop eval cases.
# 遵循仓库评测准则：安全/门禁类断言做否定感知匹配，引号内回述视为用户原话，
# 不构成技能自身承诺。
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
    """原文包含任一关键词（不做否定过滤，用于字段/名词在场断言）。"""
    if not any(v in text for v in values):
        fail(f"缺少{label}: {' | '.join(values)}")


def positive(patterns):
    """返回第一条未被否定词修饰且不在引号内的命中句；无则 None。"""
    for sentence in re.split(r"[。！？\n]+", text):
        body = QUOTE_SPAN.sub("", sentence)
        if any(re.search(p, body) for p in patterns) and not any(
            v in body for v in NEGATORS
        ):
            return sentence
    return None


def require_positive(patterns, label):
    """要求存在至少一句未被否定的承诺/判断句。"""
    if positive(patterns) is None:
        fail(f"缺少未被否定的{label}: {' | '.join(patterns)}")


def forbid_positive(patterns, label):
    """禁止出现未被否定的声明句（如'已开始生成'）。"""
    hit = positive(patterns)
    if hit is not None:
        fail(f"出现不应有的{label}: {hit.strip()[:60]}")
