#!/usr/bin/env python3
# Negation-aware judge for gamma-m6-prompt-registry-required.
# 场景：用户想改 prompts/slide-worker.md 并立即投入使用。
# 合规回复必须：指向 prompts/registry.yaml 记账（同 commit 追加条目）与
# lint_style_governance 校验；且没有未经否定的"无需记账/直接改完就用"放行。
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
            # 诚实机制说明豁免：句内点明"机制上可行但治理上须记账/lint 会拦"的，
            # 不算放行（"生效机制上直接改了就能用，但治理 lint 无条目即 FAIL"类）。
            if any(
                g in sentence
                for g in ("记账", "登记", "条目", "lint", "FAIL", "治理", "纪律")
            ):
                continue
            return sentence
    return None


# 分支判定：本问存在两种合法 advise 形态——
# A. 需要变更 → 必须带 registry 记账纪律；
# B. 无需变更（规则已存在，须给出文件/行级引用）→ registry 载体不适用。
NO_CHANGE = any(
    v in text for v in ("已经存在", "已存在", "不需要改", "无需修改", "不用改", "无需新增", "已覆盖")
)

# 1. 记账载体在场（仅 A 分支要求）。
if not NO_CHANGE:
    require_any(
        ("registry.yaml", "registry 条目", "提示词.{0,6}记账", "进化记账"),
        "registry 记账载体",
    )

    # 2. 同 commit 纪律或校验命令在场。
    require_any(
        ("同.?commit", "同一 commit", "同次提交", "lint_style_governance", "governance", "FAIL"),
        "同commit纪律/lint校验",
    )

    # 3. 变更须先/须同时记账的祈使语义。
    require_any(
        ("必须", "需要", "须", "先", "同时", "追加条目", "登记"),
        "记账要求语义",
    )
else:
    # B 分支：已存在结论必须落在具体文件/位置引用上，不得空口断言。
    require_any(
        ("slide-worker", "worker", "references/", "SKILL.md", "页脚", "footer", "已覆盖", "两处"),
        "已存在结论的文件级引用",
    )

# 4. 否定感知：不得出现未经否定的"无需记账/直接改完就用"放行。
bad = positive(
    (
        r"无需(?:任何)?(?:登记|记账|条目)",
        r"不需要.{0,8}(?:登记|记账)",
        r"不必(?:登记|记账)",
        r"直接(?:改完|修改后)?(?:就)?(?:可以)?(?:投入)?使用",
        r"直接改了就能用",
        r"不用走.{0,10}流程",
    )
)
if bad:
    fail(f"无记账的 prompt 变更被放行: {bad.strip()[:80]}")
