#!/usr/bin/env python3
# RST same-unit 硬规则与 advisory 边界：same-unit 绝不拆页，容量不够走降级顺序；
# RST/禅档位为双判据且均 advisory，不得说成母版硬校验强制项。
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
        # M1.1 (2026-08-31): question-restatement exemption (M0.1 precedent:
        # healthy replies restate the user's ask before denying it). A fragment
        # ending in 吗/呢, or containing 能否/能不能/可不可以/可否, is the echoed
        # question itself, not an affirmative answer, so forbid checks skip it.
        stripped = sentence.strip()
        if re.search(r"(吗|呢)\s*$", stripped) or re.search(
            r"(能否|能不能|可不可以|可否)", stripped
        ):
            continue
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


# ① same-unit 绝不拆页（危险正向句＝同句允许"拆成两页"且无否定）
forbid_positive((r"可以拆成两页", r"可以拆开", r"可以拆页", r"拆成两页各放一半"),
                "same-unit 拆页放行表述")
require_any(("不拆", "不能拆", "不得拆", "绝不拆", "不拆页", "不拆分",
             "整体.{0,6}一页", "保持同页"), "same-unit 不拆判定")
# ② 容量不够走降级顺序（拆图/减结构/升档任一）
require_any(("降级顺序", "减解释结构", "减结构", "升档", "放大.{0,8}图",
             "拆图", "减小.{0,6}内容", "精简"), "降级顺序处置")
# ③ 双判据关系：RST 管结构、禅档位管容量
require_any(("双判据", "RST.{0,10}(结构|分组)", "禅档位.{0,10}(容量|装多少)",
             "结构.{0,6}容量", "分页依据"), "双判据关系")
# ④ advisory 语义：不是硬校验（危险表述＝把 rst 标注说成强制校验/直接 FAIL）
forbid_positive((r"rst.{0,12}(会|将被?|会被).{0,8}(强制|硬)校验",
                 r"校验(器)?(会)?.{0,6}直接.{0,4}(失败|FAIL|打回).{0,10}rst",
                 r"rst.{0,10}判失败"), "rst 当硬校验表述")
require_any(("advisory", "参考判据", "不做硬校验", "不进硬校验", "不强制",
             "非强制", "不会.{0,6}校验失败", "校验器.{0,8}不(会)?检查"), "advisory 边界")
