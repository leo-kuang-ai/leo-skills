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
    "才能", "前提", "没有", "无", "而不是", "并非", "例外", "豁免", "违规",
)


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_any(values, label):
    if not any(re.search(v, text) for v in values):
        fail(f"缺少{label}: {' | '.join(values)}")


def positive(patterns):
    for sentence in re.split(r"[。！？；;\n]+|但是|但(?:我|可以|允许)", text):
        body = QUOTE_SPAN.sub("", sentence)
        if (re.search(r"(?:踩|命中|触犯|违反).{0,12}(?:红线|硬规则)", body)
                and not re.search(r"(?:可以|允许|可直接|建议直接).{0,8}(?:贴字|贴上去)", body)):
            continue
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
# M1.1 扩词（it-90 "贴字交付不在允许路径内" / it-94 "未经确认不得贴字交付"）
require_any(("不可以直接", "不能直接", "不得直接", "不可以贴", "不能贴", "先不贴",
             "不得贴字", "贴字交付不", "禁止.{0,6}贴字", "不允许.{0,6}贴", "贴字.{0,12}违规",
             "贴.{0,20}(?:踩|命中|触犯|违反).{0,12}(?:红线|硬规则)", "贴字.{0,30}被.{0,4}禁止",
             "直接.{0,10}贴字.{0,8}红灯", "直接贴字.{0,6}不允许",
             "Pillow.{0,12}贴字.{0,6}不是允许路径", "未经确认的贴字交付.{0,6}禁止",
             "不可以[^。！？\\n]{0,48}(?:Pillow|贴字)", "贴字[^。！？\\n]{0,20}不可以",
             r"不可以。[\s*]*worker[^。！？\n]{0,24}Pillow[^。！？\n]{0,20}贴",
             "贴字不是自由动作", "交付即违规",
             "自写 Pillow.{0,20}(?:不许|禁止|违规)"), "禁止直接贴字判定")
# ② TF-1 压文本预算先行（回母版减法/压预算/重生成）
require_any(("TF-1", "压.{0,6}预算", "文本预算", "回母版.{0,8}减法", "母版减法",
             "要点减法", "压缩.{0,8}重生成", "禅档位.{0,8}降"), "TF-1 先行")
# ③ TF-2 = generation method 变更须样张重确认
require_any(("重新确认样张", "样张重确认", "重确认样张", "再确认样张"),
            "TF-2 样张重确认")
# ④ 贴字逐字来自白名单
require_any(("白名单", "required_text", "逐字"), "白名单逐字约束")
# ⑤ 工具指认（overlay_text.py 是唯一授权通道，worker 不得自己贴）
require_any(("overlay_text", "确定性贴字", "确定性叠加"), "overlay_text 通道")
