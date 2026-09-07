#!/usr/bin/env python3
# 样张反演（B7）：选定样张后、锁定 deck_spec.style 前，读回样张输出三组
# 结构化判读；随样张确认同一轮呈现（零新增等待）；结论随 spec 落盘。
# 否定感知拦截"把偶然成立的效果锁死为整套风格要求"。
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
    "暂不", "先不", "无法", "待确认", "等待确认", "除非", "不建议", "避免",
)


def positive(patterns):
    """否定感知匹配：句级命中后若含否定词，再降到逗号/分号子句级复核——
    仅当违规模式命中的子句自身无否定词才算真命中。"""
    for sentence in re.split(r"[。！？\n]+", text):
        if re.match(r"^\s*#{1,6}\s+", sentence) and re.search(r"[，,：:]\s*(?:行不行|可以吗|是否可行)\s*$", sentence):
            continue
        body = plain(sentence)
        for clause in re.split(r"[；;，,]", body):
            if clause and any(re.search(p, clause) for p in patterns) and not any(
                v in clause for v in negators
            ):
                return sentence
    return None


# ① 三组判读呈现
require_any(("应延续", "inherit_stable", "稳定.{0,6}(事实|视觉|风格)", "明确延续"),
            "第一组：明确应延续")
require_any(("需确认", "needs_confirmation", "是否整套延续", "整套.{0,6}确认"),
            "第二组：需确认是否整套延续")
require_any(("偶然", "one_off", "不锁死", "不建议直接锁", "锁死"), "第三组：偶然不锁死")
# ② 同一轮呈现 / 零新增等待
require_any(("同一轮", "同回合", "同一.{0,8}确认轮", "无异议", "不新增", "不必再", "不再等待", "一次交互", "随样张确认"),
            "同一轮呈现")
# ③ 结论随 spec 落盘
require_any(("style_inversion", "随 spec", "落盘", "manifest", "deck_spec"), "落盘通道")
# ④ 证据优先序（样张实证 > prompt 措辞）
require_any(("样张实证", "实证", "读回", "样张证据", "以样张"), "样张实证优先")

# ⑤ 否定感知：不得承诺把偶然成立/装饰性效果直接锁死为整套风格要求。
bad = positive((
    r"(?:手绘箭头|箭头|装饰|偶然).{0,20}(?:每页|整套|全部|所有页|一律).{0,12}(?:加|用|上|沿用|应用|延续)",
    r"(?:每页|整套|全部|所有页|一律).{0,12}(?:加|用|上|沿用|应用).{0,12}(?:手绘箭头|箭头|装饰)",
    r"(?:偶然|装饰).{0,15}(?:直接|一律|全部).{0,10}(?:锁|定|沿)",
    r"(?:三组|全部效果|所有效果).{0,10}(?:都|均|全部).{0,10}(?:锁|沿用|进 spec)",
))
if bad:
    fail(f"把偶然效果锁死为整套风格要求: {bad}")
