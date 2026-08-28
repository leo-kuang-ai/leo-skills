#!/usr/bin/env python3
# 内容层失败先修母版再重建：视觉门打回后，回复须指向母版/逐页稿更新并重建受影响页，
# 而不是绕过内容真值直接改图。

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

require_any(("母版", "逐页稿", "内容稿"), "母版更新入口")
require_any(("先改母版", "先改逐页母版", "改母版", "更新母版", "修改母版",
             "修母版", "母版更新", "修正母版", "回到母版", "先修母版",
             "改第 ?\d+ ?页.{0,6}母版", "改母版要点"), "母版更新动作")
require_any(("重建", "重验", "重新生成", "重做", "重派", "重渲染",
             "重新渲染", "复检", "再检"), "受影响页重建/重验")
