#!/usr/bin/env python3
# Negation-aware judge for gamma-m1-render-ready-missing-suppresses-route.
# 场景：render_backend_missing 时用户问图表页路由。
# 合规回复必须：披露 render_backend_missing + 抑制 render 路由提议 +
# 给出安装恢复命令 + 图像/可编辑路线可用；且没有未经否定的"直接执行 render"建议。
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


# 1. 披露 missing 状态语义。
require_any(
    ("render_backend_missing", "渲染依赖未", "playwright 未安装", "render ready", "未就绪"),
    "missing 披露",
)

# 2. 抑制路由提议。
require_any(
    ("抑制", "不提议", "暂不提议", "不能提议", "先不路由", "无法路由到 render", "suppress"),
    "路由提议被抑制",
)

# 3. 安装恢复命令在场。
require_any(
    ("pip install playwright", "uv pip install playwright", "playwright install chromium"),
    "安装恢复命令",
)

# 4. 图像路线不受影响。
require_any(
    ("图像路线不受影响", "图像 lane 不受影响", "仍可走图像", "仍可用图像", "直接走 direct-editable", "图片路线可用"),
    "图像路线不受影响",
)

# 5. 否定感知：不得出现未经否定的"现在直接执行 render"。
bad = positive(
    (
        r"直接跑\s*render\s*chart",
        r"直接执行\s*render",
        r"现在就可以\s*render",
        r"直接用 render lane 渲染这一页",
        r"可以先跑 render",
    )
)
if bad:
    fail(f"missing 时建议直接执行 render: {bad.strip()[:80]}")
