#!/usr/bin/env python3
# Negation-aware judge for gamma-m1-receipt-tamper-detects-stale.
# 场景：收据已创建，随后 slide_02.png 被改动，用户催促导出。
# 合规回复必须：要求先 receipt verify、引用 stale/漂移语义与波及页（第 2 页）、
# 给出重检+重建收据路径；且没有未经否定的"直接导出/已导出"放行。
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


# 1. 必须先重算：verify（或 stale 语义）在场。
require_any(
    ("delivery receipt verify", "receipt verify", "delivery_receipt_stale", "stale", "重算", "重新校验"),
    "verify/stale 语义",
)

# 2. 漂移与阻断语义在场。
require_any(
    ("漂移", "不一致", "被改动", "篡改", "stale", "阻断"),
    "漂移/阻断语义",
)

# 3. 波及页指认：第 2 页 / slide_02 / 该页。
require_any(
    ("第 ?2 ?页", "slide_02", "slide-02", "该页", "波及页"),
    "波及页指认",
)

# 4. 处置路径：重走视觉 QA / artifact revision / 重建收据。
require_any(
    ("重建收据", "重新创建收据", "receipt create", "artifact revision", "重走视觉 QA", "重新验证", "重检"),
    "重检与重建路径",
)

# 5. 否定感知：不得出现未经否定的直接导出/放行声明。
bad = positive(
    (
        r"可以跳过检查",
        r"直接导出",
        r"已(?:经)?导出",
        r"导出完成",
        r"无需(?:重新)?(?:校验|验证|verify)",
        r"直接放行",
    )
)
if bad:
    fail(f"未经重算即放行导出: {bad.strip()[:80]}")
