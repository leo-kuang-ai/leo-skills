#!/usr/bin/env python3
# 中断恢复文档门：新会话恢复必须以 content/ 版本化文档为确认状态真值（引用母版
# 文档、推进到下一确认门），不要求用户重述已确认内容，不重新起草大纲/母版，
# 不声称已开始生成。

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


# 恢复真值：必须引用磁盘上的母版文档（或 content/ 目录）作为确认状态来源。
if not re.search(r"(content/)?deck-master-v\d+\.md|content/", text):
    fail("缺少恢复真值来源引用: content/ 或 deck-master-v<N>.md")
# 下一确认门：视觉方向 / backend / 风格。
require_any(("视觉方向", "视觉", "风格", "backend"), "下一确认门表述")
forbid_positive(
    (r"请(重新)?(提供|发送|贴|发我|重述)", r"重新(提供|发送)"),
    "要求重述已确认内容",
)
forbid_positive(
    (r"重新(起草|制定|输出)大纲", r"重新出大纲", r"重新(起草|制定)母版"),
    "重新起草已确认内容",
)
forbid_positive((r"已(开始)?生成", r"图片已生成"), "生成声明")
