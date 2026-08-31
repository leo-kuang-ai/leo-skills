#!/usr/bin/env python3
# 护栏注入可见性：style render --guardrail 的输出须含护栏摘要关键行。
# 最终消息须展示 --guardrail 调用与摘要内容（字号双口径/对比度锚点行）。

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


def positive(patterns, exempt=()):
    for sentence in re.split(r"[。！？\n]+", text):
        body = QUOTE_SPAN.sub("", sentence)
        for p in patterns:
            if re.search(p, body) and (
                p in exempt or not any(v in body for v in NEGATORS)
            ):
                return True
    return False


def require_positive(patterns, label, exempt=()):
    if not positive(patterns, exempt=exempt):
        fail(f"缺少肯定表述{label}（或仅出现在否定语境）: {' | '.join(patterns)}")


if "--guardrail" not in text:
    # 环境态分支：eval 沙箱通常没有内容材料可注入，此时合同正确行为是按
    # 输入材料缺失 blocked 并向用户索要材料，注入参数只作冻结预告，不声称
    # 已注入/已渲染——与真实调用 --guardrail 的可见性等价受认可。
    if not (
        re.search(r"input_material_missing|status:\s*blocked|状态[:：]\s*blocked", text)
        and re.search(r"材料|文章|报告|笔记|大纲", text)
        and re.search(r"提供|发给我|粘贴|路径", text)
    ):
        fail("缺少 guardrail 旗标调用: --guardrail（或按材料缺失正确 blocked 并索要材料）")
    print("guardrail-visible: ok (blocked-on-missing-material)")
    sys.exit(0)
require_any(["设计护栏摘要"], "护栏摘要块标识")
# 数值锚点（1920…18 / 2560…32 / 4.5:1）本身方向不可反写，豁免句级否定词
# 否决：实测健康响应的锚点句常同句携带无关的否定式规则（如「不得只靠颜色区分」）。
require_positive(
    [r"字号下限双口径", r"1920.*18", r"2560.*32"],
    "字号双口径锚点",
    exempt=(r"1920.*18", r"2560.*32"),
)
require_positive(
    [r"4\.5:1", r"对比度"],
    "对比度锚点行",
    exempt=(r"4\.5:1",),
)
print("guardrail-visible: ok")
