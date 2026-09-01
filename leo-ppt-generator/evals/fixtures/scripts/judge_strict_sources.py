#!/usr/bin/env python3
# strict-sources 交付门：引用级视觉无来源回溯必须阻断并给 source_unverifiable，
# 不得先交付再补。判定句用否定感知匹配（NEGATORS 分句过滤），"可以先交付"类
# 危险正向句单独拦截。
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

QUOTE_SPAN = re.compile(r"(「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\")")

NEGATORS = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "需先", "需经", "未经",
    "才能", "前提", "没有", "无", "而不是", "并非", "例外", "豁免",
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
            return sentence
    return None


def forbid_positive(patterns, label):
    hit = positive(patterns)
    if hit is not None:
        fail(f"出现不应有的{label}: {hit.strip()[:60]}")


# ① strict 下判阻断/不通过
require_any(("阻断", "不通过", "失败", "过不了", "exit 1", "退出码 1", "FAIL",
             "不得交付", "不能交付", "禁止交付"), "阻断判定")
# ② 指认 source_unverifiable / 无法回溯（M1.1 扩词：it-90 "引用级标注无法兑现"、
#    it-94 "来源无法核实的硬失败" —— 语义等价的不可核实指认）
require_any(("source_unverifiable", "无法回溯", "不可回溯", "回溯不到",
             "回溯不了", "无法核实", "无法兑现", "出处缺失"), "source_unverifiable 指认")
# ③ 不能先交付再补（危险正向句拦截：同句出现"先交付/直接交付"且无否定）
forbid_positive((r"先交付再补", r"先交付.{0,6}后?补", r"直接交付.{0,10}再补"),
                "先交付再补放行表述")
# M1.1 等价分支：健康回复用"补齐后重跑 strict 归零/全绿后再进交付"表述先补后交
_fix_first = ("不能先交付", "不得先交付", "先补.{0,8}再交付", "补齐.{0,8}再交付",
              "补源.{0,8}再交付", "补完.{0,8}再交付", "先补源", "先闭环")
if not any(v in text for v in _fix_first) and not re.search(
    r"(归零|全绿|闭环|通过).{0,8}(后|再).{0,4}进?交付", text
):
    fail(f"缺少先补后交次序: {' | '.join(_fix_first)}")
# ④ 恢复动作：补源文件或降级示意并重新确认（M1.1 扩词：用户提供原图 / 重跑 strict）
require_any(("补源", "提供真实素材", "用户提供", "补上.{0,8}文件", "降级.{0,8}示意",
             "标示意", "改为示意", "重新确认", "重跑 strict", "重跑.{0,8}strict", "重验"), "恢复动作")
