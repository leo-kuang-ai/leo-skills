#!/usr/bin/env python3
# 论断式第一条要点：内容页第一条要点必须是完整论断句+证据跟随；功能页豁免；
# TAKEAWAY-READTHROUGH 连读复核。判定句天然含"不/须"字，用直接短语匹配；
# 对"每页都要论断句"类一刀切正向句做否定感知拦截。
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

QUOTE_SPAN = re.compile(r"(「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\")")

NEGATORS = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "需先", "需经", "未经",
    "才能", "前提", "没有", "无", "而不是", "并非", "例外", "豁免",
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


# ① 判定不合格/须改写（"算法背景/相关工作"是话题词非论断句）
require_any(("不合格", "不合规", "须改写", "需要改写", "要改写", "不能过", "不通过",
             "无法过", "不会过", "打回", "话题词", "话题短语", "纯名词", "不算论断",
             "不是论断", "非论断", "未构成论断"), "不合格/须改写判定")
# ② 给出论断句改写方向（完整句断言）
require_any(("论断句", "完整论断", "完整句", "断言句", "结论句", "主谓宾"), "论断句方向")
# ③ 证据跟随（其后 1-2 条是数字/图/引用）
require_any(("证据跟随", "证据", "跟随", "支撑", "佐证", "论据"), "证据跟随")
# ④ takeaway 连读检查在场
require_any(("TAKEAWAY-READTHROUGH", "takeaway", "连读", "故事线"), "连读检查")
# ⑤ 功能页豁免不误伤：禁止"每一页都必须论断句"类未否定的一刀切正向句
forbid_positive((r"每一页都必须", r"每一页都要", r"所有页都必须", r"所有页都要",
                 r"全部页都", r"任何页都.{0,4}论断", r"封面也必须", r"目录也必须",
                 r"封面也要写论断"), "功能页一刀切误伤")
