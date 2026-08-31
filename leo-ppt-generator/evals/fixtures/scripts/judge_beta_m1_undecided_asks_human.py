#!/usr/bin/env python3
# beta-m1 调度师 undecided 交人工（B2-T3）：内容介于两版式之间时，母版该页
# 标注待定 + 给 2 个候选 + 理由，在母版确认交互里交用户裁决。否定感知拦截
# "直接替用户定死 / 不用问 / 就用 X"的静默落版式承诺。
import os, re, sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(m):
    print(m, file=sys.stderr)
    raise SystemExit(1)


def require_any(vals, label):
    if not any(re.search(v, text) for v in vals):
        fail(f"缺少{label}: {' | '.join(vals)}")


QUOTE_SPAN = re.compile(
    r"(「[^」]*」|『[^』]*』|“[^”]*”|‘[^’]*’|《[^》]*》|\"[^\"]*\"|'[^']*')"
)


def plain(sentence):
    return QUOTE_SPAN.sub("", sentence)


negators = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待定", "待确认", "等待确认", "除非", "仅当",
    "需要你", "请你", "由你", "二选一", "两选一",
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


# ① 待定呈现（undecided / 版式待定 / 待人工裁决）
require_any(("待定", "undecided", "待人工", "版式.{0,6}(定|决)", "置信度"),
            "待定标注")
# ② 两个候选被给出（P8 与 P13 或 左右对比 与 三卡/三力）
require_any(("P8", "Duo", "左右.{0,6}对比", "两栏"), "候选一（对照类）")
require_any(("P13", "Three Forces", "三力", "三张卡", "三卡", "P4", "P5"),
            "候选二（三卡类）")
# ③ 交用户裁决（母版确认 / 你来定 / 确认时）
require_any(("母版确认", "确认时", "你来", "你定", "二选一", "选一个",
             "需要你", "请你确认", "待确认"), "人工裁决点")

# ④ 否定感知：不得宣称已替用户定死、无需再问。
bad = positive((
    r"(?:直接|已经|就|干脆).{0,10}(?:定|选|落).{0,10}(?:P8|P13|Duo|三力|两栏|三卡)",
    r"(?:不用问|不必问|无需确认|不用确认|已定死|直接锁定).{0,14}",
    r"(?:我替你|帮你).{0,8}(?:定|选).{0,10}(?:版式|P8|P13)",
))
if bad:
    fail(f"静默替用户落定版式（未走 undecided 人工裁决）: {bad}")
