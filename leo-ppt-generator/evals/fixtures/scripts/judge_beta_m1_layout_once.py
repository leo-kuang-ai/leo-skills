#!/usr/bin/env python3
# beta-m1 强视觉版式一 deck 一次（B1-T6）：两页都想用宣言收尾时，agent 指出
# P9 每 deck 只有一页 / 建议第二页改用其他版式 / 引用 check_layout_reuse.py
# 机器复核。否定感知拦截"两页都用 P9 / 连续两页宣言版式"的直接承诺。
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
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "除非", "仅当", "前提",
    "至多", "最多", "只能", "只有一", "一次", "别重复", "避免",
)


def positive(patterns):
    """否定感知匹配：句级命中后若含否定词，降到子句级复核——仅当违规模式
    命中的子句自身无否定词才算真命中（健康句"P9 每 deck 只有一页"放过；
    混合句"两页都用 P9"拦截）。"""
    for sentence in re.split(r"[。！？\n]+", text):
        body = plain(sentence)
        for clause in re.split(r"[；;，,]", body):
            if clause and any(re.search(p, clause) for p in patterns) and not any(
                v in clause for v in negators
            ):
                return sentence
    return None


# ① 强视觉版式一次性被点破
require_any(("每个 deck 只有一页", "只有一页", "一 deck 一次", "一次",
             "至多一页", "最多一页", "只用一次", "deck 终结", "唯一"),
            "P9 一次性说明")
# ② 第二页有替代出路
require_any(("其他版式", "别的版式", "换.*版式", "改用", "P3", "P36",
             "P12", "P34", "收尾"), "第二页替代方案")
# ③ 机器复核工具被引用（check_layout_reuse）
require_any(("check_layout_reuse", "复用检查", "layout_reuse"),
            "复用检查工具引用")

# ④ 否定感知：不得承诺两页都落宣言收尾版式。
bad = positive((
    r"(?:两页|第 ?7 ?页.{0,10}第 ?8 ?页|第 ?8 ?页.{0,10}第 ?7 ?页).{0,16}(?:都|均|同时).{0,10}(?:用|落|选|是).{0,10}P9",
    r"P9.{0,12}(?:×|x|以及|和|、).{0,6}P9",
    r"(?:两页|第 ?8 ?页).{0,14}(?:都|均).{0,10}(?:宣言|Closing|P9)",
))
if bad:
    fail(f"承诺两页同时使用宣言收尾版式: {bad}")
