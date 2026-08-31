#!/usr/bin/env python3
# 台账驳回依据：P3 发现可驳回，但驳回必须记录依据/理由，不得无理由忽略。

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

require_any(("可以驳回", "可驳回", "可以不采纳", "可不采纳", "驳回不修",
             "不需要修", "可以不修", "不必修", "不修它们", "不阻塞", "搁置"),
             "P3 可驳回/不阻塞")
require_any(("依据", "理由"), "驳回依据要求")
require_any(("记录", "台账", "保留"), "驳回留痕")
# 划掉/删除类禁止表达变体多，按语义组收词：否定 + 划掉/删除。
if not re.search(
    r"(不能|不得|不应|不行|别|拒绝|等于|不建议|不推荐|不要).{0,12}(划掉|删掉|删除|抹掉|直接.{0,4}忽略|忽略)"
    r"|(划掉|删掉|删除|抹掉|忽略).{0,10}(不行|不可以|不允许|等于抹掉)",
    text,
):
    fail("缺少禁止无理由划掉/忽略的表态")
