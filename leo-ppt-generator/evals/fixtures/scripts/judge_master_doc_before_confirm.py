#!/usr/bin/env python3
# 母版文档门：大纲已确认的前置状态下，逐页母版必须先写入 content/ 版本化文档
# （deck-master-v<N>.md），聊天引用该文档路径与摘要并等待确认；不声称已开始生成。

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
    """句级命中后若含否定词，降子句级复核：仅当命中模式的那半句自身无否定词
    才算真命中（"确认门不能省，需要你点头"的点头半句是正向语义）。"""
    for sentence in re.split(r"[。！？\n]+", text):
        body = QUOTE_SPAN.sub("", sentence)
        if not any(re.search(p, body) for p in patterns):
            continue
        if not any(v in body for v in NEGATORS):
            return sentence
        for clause in re.split(r"[；;，,——]", body):
            if clause and any(re.search(p, clause) for p in patterns) and not any(
                v in clause for v in NEGATORS
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


require_any(("母版", "逐页", "内容稿"), "母版/逐页稿请求")
# 文档门：回复必须引用已写入的母版文档路径（content/ 下 deck-master-v<N>.md，
# 绝对或相对路径均可命中）。
if not re.search(r"(content/)?deck-master-v\d+\.md", text):
    # 环境态分支：eval 沙箱通常没有上次会话的项目状态（outline-v1.md 不存在），
    # 此时合同正确行为是按输入材料缺失 blocked 并向用户索要真值（outline 路径
    # 或重建授权），而不是凭空出母版——门禁语义与落盘路径等价受认可。
    if not (
        re.search(r"input_material_missing|status:\s*blocked|状态[:：]\s*blocked", text)
        and re.search(r"outline-v\d+\.md|大纲", text)
        and re.search(r"提供|给我|授权|路径|重建|选 ?A", text)
    ):
        fail(
            "缺少母版文档路径引用: (content/)?deck-master-v<N>.md"
            "（或按材料缺失正确 blocked 并索要 outline 真值）"
        )
require_positive((r"确认|审阅|等待",), "等待用户确认")
forbid_positive((r"已(开始)?生成", r"开始直接生成", r"图片已生成"), "生成声明")
