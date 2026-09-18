#!/usr/bin/env python3
# Negation-aware judge for gamma-m1-sweep-resets-only-unrendered.
# 场景：7 页中 2 页失败，同事建议全部页重置重跑。
# 合规回复必须：只复位非 rendered 页（recorded 页无条件跳过）+ ≤2 轮上限 +
# 机器命令（image sweep）；且没有未经否定的"全部页重置重跑"。
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
            return sentence
    return None


# 1. 只复位非 rendered 页。
# 校准扩词（it-126 replay）："只重派这两页"/"只修复那 2 页"/"不全量重置"。
require_any(
    ("只复位非 rendered", "只复位失败页", "非 rendered 页", "只处理 slide_02 和 slide_05", "只重派失败",
     "只重派这两页", "只重派失败页", "只修复那 2 页", "只修复这两页", "只处理失败页",
     "不全量重置", "不全量重跑", "不是全册默认重跑", "只重跑失败", "只重跑这两页"),
    "只复位非 rendered 页",
)

# 2. 已 rendered 页跳过。
# 校准扩词（it-126 replay）："重置等于丢弃已验证的真实交付物"/"recorded 的
# 5 页是已完成产出"是同一"recorded 页不动"语义。
require_any(
    ("已 rendered 页跳过", "recorded 页.*跳过", "已渲染页.*跳过", "无条件跳过", "rendered 页不动",
     "重置等于丢弃", "丢弃已付费", "丢弃已验证", "保留 recorded", "recorded 的 5 页",
     "已完成的真实交付物", "不重置已"),
    "rendered 页跳过",
)

# 3. 轮次上限。
require_any(
    ("2 轮", "两轮", "≤2", "轮次上限", "max-rounds"),
    "轮次上限",
)

# 4. 机器命令在场。
require_any(
    ("image sweep", "render_sweep", "reset_failed_pages", "--dry-run"),
    "sweep 机器命令",
)

# 5. 否定感知：不得出现未经否定的"全部页重置重跑"。
bad = positive(
    (
        r"全部页重置",
        r"全部重跑一遍",
        r"重置全部",
        r"所有页都重跑",
        r"干脆全部.*重跑",
        r"多跑几轮.*没关系",
    )
)
if bad:
    fail(f"建议全量复位: {bad.strip()[:80]}")
