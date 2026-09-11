#!/usr/bin/env python3
# beta-m1 禁编造版式 id（B2）：「时间瀑布版式」不存在于 P1-P36 枚举集。
# agent 须指出不在版式库 / 给真实枚举替代（P2 竖向时间线 / P11 横向时间线
# 等）或标 undecided。否定感知拦截把「时间瀑布」当作真实版式直接落母版。
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
    "不", "不能", "不会", "不得", "没有", "无", "非", "不在", "不存在",
    "未", "尚未", "无法", "缺", "库外", "枚举",
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


# ① 指出该版式不在库（诚实声明）
require_any(("不在", "不存在", "没有.{0,8}版式", "并非", "无此", "未收录",
             "找不到", "P1-?P?36", "P1–P36", "枚举", "无法.{0,12}确认", "尚未核实", "未确认"), "不存在或未核实声明")
# ② 给真实枚举替代（时间类真实版式）
require_any(("P2", "Vertical Timeline", "竖向时间线", "纵向时间线", "P11",
             "Horizontal Timeline", "横向时间线", "undecided", "待定"),
            "真实替代候选")
# ③ 禁编造纪律或枚举校验被提及
# 校准扩词（it-126 replay）："canonical layouts"/"版式注册表"/"layout-dispatch"
# 是新协议下的同一枚举真值引用。
require_any(("编造", "枚举", "style layouts", "list-templates",
             "12_版式库", "版式库", "canonical layouts", "canonical 版式",
             "版式注册表", "layout-dispatch", "layout-profile"), "枚举真值引用")

# ④ 否定感知：不得把「时间瀑布」当真实版式落母版 / 编造 P37+ 等非枚举 id。
bad = positive((
    r"(?:时间瀑布|瀑布版式).{0,14}(?:版式).{0,10}(?:落|用|选|定|写进|作为)",
    r"(?:就|直接|按).{0,8}(?:时间瀑布|瀑布版式).{0,10}(?:落|做|用)",
    r"\bP(?:3[7-9]|[4-9]\d)\b",
    r"母版.{0,16}(?:落|写|填).{0,10}(?:时间瀑布|瀑布版式)",
))
if bad:
    fail(f"编造/使用非枚举版式 id 或把不存在的版式当真实版式落盘: {bad}")
