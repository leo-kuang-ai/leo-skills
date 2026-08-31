#!/usr/bin/env python3
# 品牌优先序：用户 VI（brands/）优先于内置预设；--brand 注入与对比度护栏语义。
import os, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("brands", "用户品牌", "LEO_PPT_HOME"), "用户 VI 优先通道")
require_any(("优先", "先读", "覆盖内置", "优先于"), "优先序表述")
require_any(("对比度", "4.5", "不达标", "fail", "建议色"), "对比度护栏")
require_any(("--brand", "brand", "品牌"), "--brand 注入语义")
