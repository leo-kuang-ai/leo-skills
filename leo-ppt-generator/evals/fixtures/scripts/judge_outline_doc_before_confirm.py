#!/usr/bin/env python3
# 大纲文档门：execute 授权后大纲必须先写入 content/ 版本化文档（outline-v<N>.md），
# 聊天引用该文档路径与摘要并等待确认；不声称已开始生成。

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


require_any(("大纲", "目录"), "大纲阶段表述")
# 文档门：回复必须引用已写入的大纲文档路径（content/ 下 outline-v<N>.md，
# 绝对或相对路径均可命中）。
if not re.search(r"(content/)?outline-v\d+\.md", text):
    fail("缺少大纲文档路径引用: (content/)?outline-v<N>.md")
require_positive((r"确认|审阅|等待",), "等待用户确认")
forbid_positive((r"已(开始)?生成", r"开始直接生成", r"图片已生成"), "生成声明")
