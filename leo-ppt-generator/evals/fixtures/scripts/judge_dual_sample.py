#!/usr/bin/env python3
# 样张双生：提议制（纠结信号→一句提议含成本告知，点头才出）；双参考图直入；
# 同内容二选一、落选即弃、计入既有样张里程碑。
import os, re, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("各出一张","两张样张","二选一","双样张","两个方向各"), "双生提议/机制")
require_any(("多一张","多花","图片成本","成本"), "成本告知")
require_any(("点头","同意","确认后","你同意","回个","要不要","可以吗"), "点头才执行")
same_page = re.compile(r"同内容|相同内容|同一(?:个|张)?(?:正文|业务|内容){0,2}(?:页|张)")
if not any(not re.search(r"(?:不|不是|不用|不使用)\s*$", text[max(0, match.start() - 8):match.start()])
           for match in same_page.finditer(text)):
    fail("缺少肯定的同内容样张约束")
require_any(("落选","弃","不追加","失败方","输的"), "落选即弃")
