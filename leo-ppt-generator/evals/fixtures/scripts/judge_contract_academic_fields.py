#!/usr/bin/env python3
# 学术合同三字段：硕士答辩/论文场景 math_load/figure_orientation/section_priority
# 必填且取值在封闭词表内；缺字段判失败；通用 deck 不一刀切。判定句天然含
# "不/须"字，用直接短语匹配；对"所有 deck 都必须"与非法枚举值 medium-heavy
# 的正向认可做否定感知拦截。
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


# ① 学术场景三字段必填判定（不行/须先补齐）
require_any(("不行", "不可以", "不能直接", "须先补", "需要先", "必须先", "先补齐",
             "先声明", "先冻结", "必填", "不通过", "判失败", "打回", "不建议直接"), "学术必填判定")
# ② 字段词表：三字段至少点名；取值词表允许"枚举在场"或"正确延迟到 execute 核实"
# （advise 模式禁读 reference，诚实延迟不是缺口）
DEFER = ("无法核实", "进入 execute", "execute 后", "读取", "reference", "可选值",
         "合法取值", "枚举", "不凭印象", "再确认", "schema")
require_any(("math_load", "数学量级", "公式密度"), "math_load 字段")
if not any(v in text for v in ("light", "medium", "heavy", "轻", "中", "重")) and not any(
    d in text for d in DEFER
):
    fail("缺少 math_load 词表或 execute 核实延迟")
require_any(("figure_orientation", "图表取向"), "figure_orientation 字段")
if not any(v in text for v in ("figure-first", "balanced", "text-first")) and not any(
    d in text for d in DEFER
):
    fail("缺少 figure_orientation 词表或 execute 核实延迟")
require_any(("section_priority", "优先级", "页数分配", "节级"), "section_priority 字段")
# ③ 通用 deck 不强制的边界意识（可选/非学术不强制 在场）
require_any(("通用", "非学术", "商务", "可选", "不强制", "不阻断"), "通用可选边界")
# ④ 否定感知：禁止"所有 deck 都必须"类一刀切正向句
forbid_positive((r"所有 deck 都必须", r"任何 deck 都必须", r"所有场景都必须",
                 r"一律必填", r"商务 deck 也必须", r"通用 deck 也必须"),
                "一刀切误伤")
# ⑤ 分句级陷阱：medium-heavy 等词表外取值被**无条件**放行才判败；
# 同句带核实/确认/execute 延迟语义属 advise 诚实处置；疑问句（回述用户提问
# "可以吗"）不是背书——均不算放行。
for clause in re.split(r"[。！？\n，,；;、]", text):
    if "medium-heavy" not in clause and "heavy-medium" not in clause:
        continue
    if any(d in clause for d in DEFER) or "可以吗" in clause or "吗" in clause[-2:]:
        continue
    for m in re.finditer(r"可以|合法|有效|也行|没问题|准确|允许", clause):
        prefix = clause[max(0, m.start() - 2):m.start()]
        if not any(n in prefix for n in ("不", "别", "勿", "难", "非")):
            fail(f"出现不应有的非法枚举值放行: {clause.strip()[:60]}")
