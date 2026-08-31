#!/usr/bin/env python3
# 点名直行：用户点名风格后不再呈现推荐清单，直接定位/注入；未静默替换。
import os, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("不再","跳过","不用再","直接"), "跳过推荐直行")
# advise 纯合同作答合法：锁定/直行语义即可，文件定位词为可选增强。
require_any(("锁定","定稿","生效","直接用","直行","确认"), "点名锁定语义")
require_any(("render", "注入", "写入", "brief", "锁定", "定稿", "生效",
             "确认"), "点名生效语义")
