#!/usr/bin/env python3
# 大纲修订文档门：v1 已落盘未确认时按反馈修订必须产出 outline-v2.md（旧版保留），
# 聊天引用 v2 路径并等待确认；不声称已开始生成。

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


require_any(("大纲",), "大纲阶段表述")
# 修订门：必须引用修订后的 v2 文档路径（旧版 v1 保留）。
if not re.search(r"(content/)?outline-v2\.md", text):
    fail("缺少修订版大纲文档路径引用: (content/)?outline-v2.md")
require_positive((r"确认|审阅",), "等待用户确认")
forbid_positive((r"已(开始)?生成", r"开始直接生成", r"图片已生成"), "生成声明")
