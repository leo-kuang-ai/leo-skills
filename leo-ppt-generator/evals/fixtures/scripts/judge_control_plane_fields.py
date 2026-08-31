#!/usr/bin/env python3
# Order-aware judge for the "control-plane blocked summary" case.
# SKILL.md makes the block itself the contract (block-early, 2026-08-31 起):
# the five canonical lines must appear within the first 3 visible lines of the
# reply; lines preceding the block may only be metadata-like (each <=40 chars,
# e.g. interaction_mode or a short status label), values verbatim, and the
# reply must not claim it created a run nor explain capability gaps by
# enumerating host agent registries. Containment-only checking let
# narrative-first replies slip past in early iterations; the <=40-char bound
# keeps long narrative lead-ins failing while tolerating short metadata
# prefixes that models reliably emit.
import os
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


FIELDS = (
    ("route", "route: generate"),
    ("status", "status: blocked"),
    ("reason_code", "reason_code: worker_capability_unavailable"),
    ("execution_eligibility", "execution_eligibility: blocked"),
)


def visible_lines(raw):
    # 去掉代码围栏行本身，保留其内容参与顺序判定
    return [ln.strip() for ln in raw.splitlines() if ln.strip() and ln.strip() not in ("```", "```text")]


def check_block_order(lines):
    # block-early 合同：五行块必须出现在前 3 个非空行之内；先于块的行只能是
    # 元数据性行（每行 ≤40 字符，如 interaction_mode / 简短状态标签）。长叙述
    # 先行（前 3 行内无块，或先于块的行超过 40 字符）仍判定违约。
    block_start = None
    for i in range(min(3, len(lines))):
        if lines[i] == FIELDS[0][1]:
            block_start = i
            break
    if block_start is None:
        raise AssertionError("五字段块未出现在回复前 3 个非空行之内（block-early 位置合同）")
    for j in range(block_start):
        if len(lines[j]) > 40:
            raise AssertionError(
                f"第 {j + 1} 行先于五字段块且超过 40 字符，属叙述先行: {lines[j][:40]}…"
            )
    block = lines[block_start : block_start + 5]
    for offset, (_name, expected) in enumerate(FIELDS):
        if len(block) <= offset or block[offset] != expected:
            raise AssertionError(
                f"五字段块第 {offset + 1} 行应为整行 {expected!r}"
            )
    fifth = block[4]
    if not fifth.startswith("next_action:") or not fifth[len("next_action:"):].strip():
        raise AssertionError("第五行必须是 next_action: 且恢复动作非空")


def require_all(values):
    missing = [v for v in values if v not in text]
    if missing:
        fail(f"缺少必需内容: {', '.join(missing)}")


lines = visible_lines(text)

try:
    check_block_order(lines)
except AssertionError as exc:
    fail(str(exc))

require_all(
    (
        "route: generate",
        "status: blocked",
        "reason_code: worker_capability_unavailable",
        "execution_eligibility: blocked",
        "next_action:",
    )
)

# 值域防线：blocked 态全回复只允许恰一行 next_action:（SKILL.md：此类状态不得把
# alternatives 展开成多条用户步骤）
next_action_lines = [ln for ln in lines if ln.startswith("next_action:")]
if len(next_action_lines) != 1:
    fail(f"blocked 态只允许一个 next_action，实际发现 {len(next_action_lines)} 行")

negators = ("不", "未", "不会", "不得", "没有", "尚未")
for ln in text.splitlines():
    if "已创建" in ln and "run" in ln and not any(w in ln for w in negators):
        fail(f"发现未经否定的 run 创建声明: {ln.strip()}")

# 宿主信息泄漏红线：解释 worker 缺失时不得枚举/诊断宿主 Agent 清单
# （iter-2 与 iter-4 的失败回复都以 “Agent 类型列表只有 ppt-agent:*” 叙述缺因）
if "ppt-agent" in text or "Agent 类型列表" in text:
    fail("发现宿主 Agent 清单泄漏：worker 缺失只允许以 reason_code 口径表述")
