#!/usr/bin/env python3
# Judge for "confirmation-batched-turns": with complete materials and an
# explicit batching request, the first execute turn must present the content
# contract AND the outline in the SAME reply (batched adjacent gates), still
# ask for per-artifact confirmation, and must not treat anything as confirmed
# or start generation without the user's reply. Confirmation-gate completeness
# itself is owned by execute-keeps-confirmation-gates; this judge only asserts
# the batching contract and premature-freeze red lines.
import os
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_any(values, what):
    if not any(v in text for v in values):
        fail(f"缺少{what}: {' / '.join(values)}")


# Batched evidence: contract elements and the outline ARTIFACT both presented
# in this reply. Merely mentioning the word 大纲 (e.g. "确认后我再出大纲") is a
# promise to produce it later, not a presentation, and must not pass.
require_any(("内容合同", "确认序列", "数据分级", "页数口径", "成品页数"), "合同要素")
require_any(
    ("outline-v", "content/", "大纲如下", "大纲已落盘", "大纲已写入", "分页如下", "大纲：", "大纲:"),
    "同回合呈现的大纲工件",
)

# The reply must still ask for explicit confirmation before proceeding.
# Wide semantic group: models rotate legal phrasings every run (known-issues
# 评测工程发现 #3) — 确认/拍板/回复 families all count as the ask. it-94 added
# quoted-ask variants ("回复一次「确认」" / "回复「确认」即冻结").
require_any(
    (
        "请确认", "等你确认", "等待确认", "确认后", "确认再", "逐件确认",
        "确认这两件", "回复确认", "等你回复", "是否确认", "确认或修改",
        "请拍板", "需要你拍板", "回复拍板", "等你拍板",
        "「确认」", "\u201c确认\u201d", "回复一次", "回个确认", "说确认",
        "确认即冻结", "确认后冻结",
    ),
    "逐件确认请求",
)

# Premature freeze / dispatch red lines (negative-aware scan per AGENTS.md).
negators = ("未", "待", "等待", "尚", "需要你", "请你", "不构成", "不算")
for line in text.splitlines():
    if ("已确认" in line or "已冻结" in line) and not any(w in line for w in negators):
        fail(f"未经用户回复即声称已确认/已冻结: {line.strip()}")
    if ("已生成" in line or "已派发" in line or "已开始生成" in line) and not any(w in line for w in negators):
        fail(f"未经确认即声称已生成/已派发: {line.strip()}")
