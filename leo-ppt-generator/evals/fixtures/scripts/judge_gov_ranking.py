#!/usr/bin/env python3
# 政务排序合规：指出排序错误并按职务级别给序。
import os, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("错|不正确|应|需调整|顺序"), "指出排序问题")
require_any(("职务","级别","层级","党委","书记"), "按职务级别给序依据")
require_any(("王局长|李副局长|排序后|正确顺序|应为|改为"), "给出修正排序")
