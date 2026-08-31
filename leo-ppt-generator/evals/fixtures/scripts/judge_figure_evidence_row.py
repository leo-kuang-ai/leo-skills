#!/usr/bin/env python3
# 图行合同：含图页母版图行必须三段（承载/服务/避免误读）齐备，缺段即校验失败，
# 先修母版再重跑。判定句天然含"不/须"字，用直接短语匹配；对"缺段也能过"类
# 危险表述用分句级共现检测拦截（危险句自带的"不/缺"不作为否定豁免）。
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


def forbid_positive(patterns, label):
    hit = positive(patterns)
    if hit is not None:
        fail(f"出现不应有的{label}: {hit.strip()[:60]}")


PASS_WORDS = (r"能过|能通过|可以通过|可以过|也行|也可以|没关系|没问题|不妨|"
              r"直接派发|就够|够了")
GUARD_WORDS = r"不能|不得|无法|不可以|不会|切勿|禁止|别"


def clause_allows_missing_segment():
    """分句级陷阱检测：同一小句里同时出现「缺/漏 三段或避免误读」与放行词。"""
    for clause in re.split(r"[。！？\n，,；;、]", text):
        if not (re.search(r"避免误读|误读|三段", clause)
                and re.search(r"缺|没有|不写|省略|漏|少写", clause)):
            continue
        if re.search(PASS_WORDS, clause) and not re.search(GUARD_WORDS, clause):
            return clause
    return None


# ① 判定不能过校验/须先修
require_any(("不能过", "无法过", "不会过", "不通过", "失败", "过不了", "先修",
             "需要修", "须补", "须补齐", "打回", "缺三段", "不合格"), "校验不过判定")
# ② 三段逐一点名（承载/服务/避免误读）
require_any(("承载", "承载元素"), "承载段指认")
require_any(("服务的比较", "服务"), "服务段指认")
require_any(("避免误读", "误读"), "避免误读段指认")
# ③ 先修母版再重跑校验器
require_any(("母版", "check_master_contract", "校验器"), "修母版/校验器")
# ④ 图行语法在场（图行或其字段）
require_any(("图[F", "图行", "模式", "状态", "焦点"), "图行语法")
# ⑤ 分句级陷阱：缺段仍放行
trap = clause_allows_missing_segment()
if trap is not None:
    fail(f"出现不应有的缺段放行表述: {trap.strip()[:60]}")
