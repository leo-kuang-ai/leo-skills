#!/usr/bin/env python3
# Text Fidelity Fallback：不得直接贴字交付；TF-1 压预算先行；TF-2 = 方法变更
# 须样张重确认；贴字逐字来自 required_text 白名单。
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


# ① 不可以直接贴（否定感知：危险正向句＝同句"直接贴/贴上去交付"且无否定）
forbid_positive((r"直接(用 Pillow )?把.{0,6}字贴上去", r"直接贴字",
                 r"贴上去(就)?交付", r"可以直接贴"), "直接贴字放行表述")
require_any(("不可以直接", "不能直接", "不得直接", "不可以贴", "不能贴", "先不贴",
             "禁止.{0,6}贴字", "不允许.{0,6}贴"), "禁止直接贴字判定")
# ② TF-1 压文本预算先行（回母版减法/压预算/重生成）
require_any(("TF-1", "压.{0,6}预算", "文本预算", "回母版.{0,8}减法", "母版减法",
             "要点减法", "压缩.{0,8}重生成", "禅档位.{0,8}降"), "TF-1 先行")
# ③ TF-2 = generation method 变更须样张重确认
require_any(("TF-2", "generation method 变更", "生成方法变更", "方法变更",
             "重新确认样张", "样张重确认", "重新生成.{0,6}样张", "再确认样张"),
            "TF-2 样张重确认")
# ④ 贴字逐字来自白名单
require_any(("白名单", "required_text", "逐字"), "白名单逐字约束")
# ⑤ 工具指认（overlay_text.py 是唯一授权通道，worker 不得自己贴）
require_any(("overlay_text", "确定性贴字", "确定性叠加"), "overlay_text 通道")
