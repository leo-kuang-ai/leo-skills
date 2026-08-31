#!/usr/bin/env python3
# 统计图门槛：无样本量/误差的疗效对比图必须降级示意版式，不得用数据图表。
import os, re, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("样本量", "n", "误差", "置信", "显著性"), "缺失统计量识别")
require_any(("示意", "降级", "观点大字", "非图表", "不能用.{0,6}(图表|柱状)"), "降级处置")
