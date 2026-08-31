#!/usr/bin/env python3
# Negation-aware judge for gamma-m1-impact-inference-page-vs-deck.
# 场景：verify 同时报 slide_03.png（页产物）与 input/style-brief.md（样式源）漂移。
# 合规结论必须：页产物漂移→第 3 页该页重检；样式源漂移→全册重估（两者都在场）；
# 且没有未经否定的"只波及第 3 页"式收窄声明。
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


# 1. 全册波及结论在场：样式源漂移 → 全册。
require_any(
    ("全册", "全部页", "所有页", "整本", "整个 deck", "deck 级", "全部重做", "全deck"),
    "全册波及结论",
)

# 2. 样式源与全册的因果在场（style-brief → 全册重估）。
style_lines = [ln for ln in text.splitlines() if re.search(r"style-brief|样式源|风格|style", ln)]
if not style_lines:
    fail("未提及样式源/风格源漂移")
if not any(re.search(r"全册|全部页|所有页|整本", ln) for ln in style_lines):
    # 允许跨行表述：整段文本已含全册与样式源关键词即可（第 1 条已断言）。
    if not any(re.search(r"全册|全部页|所有页|整本", ln2) for ln2 in text.splitlines()):
        fail("样式源漂移未关联全册波及")

# 3. 页级波及结论在场：第 3 页只需该页级重检。
require_any(
    ("第 ?3 ?页", "slide_03", "slide-03", "该页"),
    "页级波及指认",
)

# 4. 页产物与页级处置的关联（该页重走视觉 QA / artifact revision）。
require_any(
    ("视觉 QA", "artifact revision", "重检", "重新验证", "重做"),
    "页级处置动作",
)

# 5. 否定感知：不得出现未经否定的"只波及第 3 页/仅需第 3 页"收窄声明。
bad = positive(
    (
        r"只波及第 ?3 ?页",
        r"仅波及第 ?3 ?页",
        r"只需要?(?:重做|重检|处理)第 ?3 ?页",
        r"只有第 ?3 ?页",
        r"其余页.{0,8}不用(?:重做|重检|处理)",
    )
)
if bad:
    fail(f"波及面被错误收窄为单页: {bad.strip()[:80]}")
