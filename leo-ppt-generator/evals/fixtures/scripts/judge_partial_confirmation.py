#!/usr/bin/env python3
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_any(values, label):
    if not any(v in text for v in values):
        fail(f"缺少{label}: {' | '.join(values)}")


# 引号内的片段视为回述用户原话或引用材料，不构成技能自身的承诺。
QUOTE_SPAN = re.compile(
    r"(「[^」]*」|『[^』]*』|“[^”]*”|‘[^’]*’|《[^》]*》|\"[^\"]*\"|'[^']*')"
)


def plain(sentence):
    return QUOTE_SPAN.sub("", sentence)


# 覆盖否定句式与时态未完成式；引号剥离后仍以残余文本判断。
negators = (
    "不",
    "不能",
    "不会",
    "不得",
    "禁止",
    "拒绝",
    "尚未",
    "还没",
    "还未",
    "暂不",
    "先不",
    "无法",
    "待确认",
    "等待确认",
)


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        body = plain(sentence)
        if any(re.search(p, body) for p in patterns) and not any(
            v in body for v in negators
        ):
            return sentence
    return None


# The canonical term, plus plain-language synonyms a faithful reply may use.
term = r"(?:partial-hybrid|混合版|部分可编辑|hybrid)"

require_any(("partial-hybrid", "混合版", "部分可编辑", "hybrid"), "partial-hybrid 术语")
require_any(("确认", "明确接受", "同意"), "确认要求")
require_any(("成功/失败", "成功页", "失败页", "失败集合", "清单"), "当前结果集合")
require_any(
    ("不能", "不会", "不执行", "阻止", "不交付", "无法直接"), "默认拒绝语义"
)
bad = positive((r"(?:直接|立即).{0,10}(?:交付|生成|组装).{0,10}" + term, r"已经生成"))
if bad:
    fail(f"未经确认直接交付: {bad}")
