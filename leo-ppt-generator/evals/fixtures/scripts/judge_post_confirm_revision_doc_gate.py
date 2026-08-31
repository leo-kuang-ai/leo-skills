#!/usr/bin/env python3
# 确认后修订文档门：母版确认后的写回必须产出新版本文档（deck-master-v2.md）并
# 登记确认后修订标记（继承 confirmed 状态），不重新走完整确认；不声称已开始生成。

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


def forbid_positive(patterns, label):
    hit = positive(patterns)
    if hit is not None:
        fail(f"出现不应有的{label}: {hit.strip()[:60]}")


require_any(("母版", "逐页", "内容稿"), "母版阶段表述")
# 修订门：必须引用写回后的 v2 文档路径。
if not re.search(r"(content/)?deck-master-v2\.md", text):
    fail("缺少写回版母版文档路径引用: (content/)?deck-master-v2.md")
# 确认后修订语义：登记修订标记或声明继承已确认状态（本步不设确认等待）。
require_any(
    (
        "post-confirm",
        "revision_kind",
        "确认后修订",
        "继承已确认",
        "状态继承",
        "保持已确认",
        "确认状态保持",
    ),
    "确认后修订标记/继承声明",
)
forbid_positive((r"已(开始)?生成", r"开始直接生成", r"图片已生成"), "生成声明")
