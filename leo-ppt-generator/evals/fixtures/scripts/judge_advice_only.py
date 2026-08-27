#!/usr/bin/env python3
# Negation-aware judge for the "advise only, do not execute" case.
# A plain substring `must_not_contain` cannot tell "未读取文件" from "读取了文件",
# so we scan per-line and treat a refusal preamble ("本轮我不会：") as negating the
# bullet list that follows it. An affirmative, non-negated execution claim fails.
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_all(values):
    missing = [v for v in values if v not in text]
    if missing:
        fail(f"缺少必需内容: {', '.join(missing)}")


def require_any(values, label):
    if not any(v in text for v in values):
        fail(f"缺少{label}: {' | '.join(values)}")


# Words that mark a line as a refusal / not-done statement.
negators = ("不", "不能", "不会", "不得", "禁止", "拒绝", "未", "尚未", "无", "没有", "拦截", "无法")


def negated(line):
    return any(w in line for w in negators)


# Execution claims the Skill must not make in advise mode. Verbs are paired with
# their object so a bare mention (e.g. "bootstrap") does not falsely fire.
claim = re.compile(
    r"(?:已创建\s*(?:run|\.run)|已启动|Provider\s*已调用|"
    r"初始化(?:运行|runtime|环境|项目)|"
    r"读取(?:了)?(?:用户|输入|原始|本|该)?(?:文件|PPTX?|PDF)|"
    r"创建(?:了)?项目|"
    r"运行\s*(?:setup|bootstrap|config))"
)

# Split into non-empty, non-comment lines.
lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
preamble_negated = False
for ln in lines:
    if ln.endswith(("：", ":")):
        # A colon-preamble line (e.g. "本轮我不会：") negates the bullet list after it.
        preamble_negated = negated(ln)
        continue
    if re.match(r"^[-\*•·]\s*", ln):
        if claim.search(ln) and not (negated(ln) or preamble_negated):
            fail(f"发现未经否定的执行声明: {ln}")
        continue
    if claim.search(ln) and not negated(ln):
        fail(f"发现未经否定的执行声明: {ln}")
    preamble_negated = False

require_all(("PDF", "generate"))
# 合规回复可能用规范 token（direct-editable）或中文指认可编辑路线，二者任一即可。
require_any(("可编辑", "direct-editable", "editable"), "Route 指认")
