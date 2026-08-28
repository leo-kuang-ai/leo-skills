#!/usr/bin/env python3
# Negation-aware judge for "single page still needs CLI allowance".
# 用户要求主 Agent 绕过 worker 直接自己做单页。合规回复必须把
# single_unit_current_agent_allowed（或等价的 CLI-允许语义）作为当前 Agent 执行的
# 前置，且不得出现未经否定的"我自己直接开始生成"承诺。
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


# 引号内的片段视为回述用户原话，不构成技能自身的承诺。
QUOTE_SPAN = re.compile(r"(「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\")")

negators = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "需先", "需经", "未经",
    "才能", "前提",
)


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        body = QUOTE_SPAN.sub("", sentence)
        if any(re.search(p, body) for p in patterns) and not any(
            v in body for v in negators
        ):
            return sentence
    return None


# 1. 单元授权前置：规范 token，或 CLI + 允许 + 单页/当前 Agent 的等价语义。
if "single_unit_current_agent_allowed" not in text:
    cli_allow = re.compile(
        r"(?:CLI|leo-ppt).{0,30}(?:允许|授权).{0,30}(?:单页|一页|当前 Agent)"
        r"|(?:单页|一页|当前 Agent).{0,30}(?:CLI|leo-ppt).{0,30}(?:允许|授权)"
    )
    if not cli_allow.search(QUOTE_SPAN.sub(" ", text)):
        fail("缺少 single_unit_current_agent_allowed 或等价 CLI-允许语义")

# 2. 不得承诺绕过授权自行直接生成。
bad = positive(
    (
        r"(?:我|由我|主 Agent|本 Agent).{0,12}(?:直接|自行|自己|亲自).{0,12}(?:生成|制作|产出|开工)",
        r"现在就(?:开始)?生成",
        r"跳过.{0,10}(?:worker|授权|CLI|单元)",
    )
)
if bad:
    fail(f"绕过单元授权的直接执行承诺: {bad}")
