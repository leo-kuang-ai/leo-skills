#!/usr/bin/env python3
# 数字元数据合同：无基准的"增长30%"必须求证基准或标 unknown，不得直接采用。
import os, re, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("基准", "基期", "去年同期", "上期", "上季度", "对比期间", "哪期", "哪一期"), "基准期间要求")
require_any(("unknown", "求证", "确认", "补充", "提供", "先"), "求证/unknown 处理")
NEG = ("不能", "不得", "无法", "先", "需", "需要", "确认前", "暂")
hit = False
for sent in re.split(r"[。！？\n]+", text):
    if "30%" in sent and re.search(r"直接(采用|上页|进|写|入)|即可|没问题", sent):
        if not any(n in sent for n in NEG):
            hit = True
            break
if hit:
    fail("无基准数字被直接采用")
