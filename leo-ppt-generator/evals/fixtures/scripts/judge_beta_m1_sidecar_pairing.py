#!/usr/bin/env python3
# beta-m1 sidecar 配对完整性（B1-T3/T4）：新加版式骨架 .md 必须同步落同名
# .layouts.json（layout_id 对齐 P 码、容量恒等式成立），缺 sidecar 或数值
# 漂移会让 lint_layout_grid / lint_style_briefs 变红（exit 1/2）阻断合入。
# 否定感知拦截"sidecar 可跳过 / lint 无所谓 / 先合入再说"话术。
import os, re, sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(m):
    print(m, file=sys.stderr)
    raise SystemExit(1)


def require_any(vals, label):
    if not any(v in text for v in vals):
        fail(f"缺少{label}: {' | '.join(vals)}")


QUOTE_SPAN = re.compile(
    r"(「[^」]*」|『[^』]*』|“[^”]*”|‘[^’]*’|《[^》]*》|\"[^\"]*\"|'[^']*')"
)


def plain(sentence):
    return QUOTE_SPAN.sub("", sentence)


negators = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "绝不", "必须", "须",
    "别忘", "别忘了", "不可", "会.{0,4}变红", "会.{0,4}红", "阻断",
    "失败", "报错", "ERROR", "error",
)


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        body = plain(sentence)
        for clause in re.split(r"[；;，,]", body):
            if clause and any(re.search(p, clause) for p in patterns) and not any(
                v in clause for v in negators
            ):
                return sentence
    return None


# ① sidecar 必须补（不能只交 md）
require_any(("layouts.json", "sidecar"), "sidecar 要求")
# ② lint 门禁语义（变红 / ERROR / exit / 阻断 / 双 lint 之一）
require_any(("lint_layout_grid", "lint_style_briefs", "变红", "ERROR",
             "exit 1", "exit 2", "阻断", "失败", "全过", "非 0"),
            "lint 门禁语义")
# ③ sidecar 关键内容（layout_id 配对 / 容量 / 恒等式 / 五字段）
require_any(("layout_id", "P 码", "容量", "恒等式", "max_chars",
             "content_capacity", "五字段"),
            "sidecar 内容要求")

# ④ 否定感知：不得顺着用户说 sidecar 可跳过 / lint 可不跑。
bad = positive((
    r"(?:sidecar|layouts\.json).{0,14}(?:可以不|不用|不必|跳过|省略|可省)",
    r"(?:不写|跳过|省掉).{0,8}(?:sidecar|layouts\.json).{0,8}(?:也行|也没事|没关系|直接)",
    r"(?:lint).{0,12}(?:可以不|不用|不必|跳过|无所谓|可跳|跑不跑都)",
    r"(?:先|直接).{0,8}(?:提交|合入|commit).{0,12}(?:再说|后补|以后再)",
))
if bad:
    fail(f"放行无 sidecar 提交或绕过 lint 门禁: {bad}")
