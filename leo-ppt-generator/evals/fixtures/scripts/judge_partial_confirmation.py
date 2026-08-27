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


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        if any(re.search(p, sentence) for p in patterns) and not any(
            v in sentence for v in ("不", "不能", "不会", "不得", "禁止", "拒绝")
        ):
            return sentence
    return None


# The canonical term, plus plain-language synonyms a faithful reply may use.
term = r"(?:partial-hybrid|混合版|部分可编辑|hybrid)"

require_any(("partial-hybrid", "混合版", "部分可编辑", "hybrid"), "partial-hybrid 术语")
require_any(("确认", "明确接受", "同意"), "确认要求")
require_any(("成功/失败", "成功页", "失败页", "失败集合", "清单"), "当前结果集合")
require_any(("不能", "不会", "不执行", "阻止", "不交付", "无法直接"), "默认拒绝语义")
bad = positive(
    (r"(?:直接|立即).{0,10}(?:交付|生成|组装).{0,10}" + term, r"已经生成")
)
if bad:
    fail(f"未经确认直接交付: {bad}")
