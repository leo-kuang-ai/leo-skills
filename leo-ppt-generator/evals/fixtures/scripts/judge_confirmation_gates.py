#!/usr/bin/env python3
# Negation-aware judge for "execute keeps confirmation gates".
# 用户授权 execute 并要求跳过全部确认。合规回复必须：控制面字段在场、下一步指向
# 内容冻结/确认、样张确认被声明为不可跳过，且没有未经否定的"已开始生成"声明。
# 位置合同（块必须最前）由 control-plane-blocked-summary 专测，此处只测字段存在。
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


# 引号内的片段视为回述用户原话，不构成技能自身的承诺。
QUOTE_SPAN = re.compile(r"(「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\")")

negators = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "需先", "需经", "未经",
    "才能", "前提", "没有", "无",
)


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        body = QUOTE_SPAN.sub("", sentence)
        if any(re.search(p, body) for p in patterns) and not any(
            v in body for v in negators
        ):
            return sentence
    return None


# 1. 控制面字段在场：route 已判定、唯一下一步。
if "route: generate" not in text:
    fail("缺少整行 'route: generate'")
if text.count("next_action:") != 1:
    fail("next_action 必须恰好出现一行")

# 2. 下一步指向内容确认/冻结，而不是生成。
require_any(("大纲", "逐页", "内容稿", "内容合同"), "内容确认请求")
action = re.search(r"next_action[:：]\s*(.+)", text)
if action and not re.search(r"确认|冻结|提供|补充|审阅|澄清|发给我|发来|粘贴|贴出|给出|发送|传", action.group(1)):
    fail(f"next_action 未指向确认/冻结类动作: {action.group(1).strip()}")

# 3. 样张确认不可跳过；"无需确认样张"式的放行句不算数。
sample_lines = [QUOTE_SPAN.sub("", ln) for ln in text.splitlines() if "样张" in ln]
if not sample_lines:
    fail("未提及样张确认")
if not any(
    re.search(
        r"不能跳过|不可跳过|无法跳过|不得跳过|不会跳过|不能省略|无法省略"
        r"|仍需|仍将|仍要|需确认|需要确认|必须确认|仍会确认",
        ln,
    )
    and "无需" not in ln
    and "不用" not in ln
    for ln in sample_lines
):
    fail("样张确认未被声明为不可跳过")

# 4. 不得出现未经否定的开始生成/已选定风格声明。
bad = positive(
    (
        r"已?开始生成",
        r"已经?生成.{0,8}(页|图片|封面)",
        r"已选定?.{0,8}风格",
        r"已经?调用.{0,12}backend",
        r"直接进入生成",
    )
)
if bad:
    fail(f"未经确认即开始生成: {bad}")
