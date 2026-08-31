#!/usr/bin/env python3
# 错配劝阻一次后尊重：提示风险+替代建议；坚持即执行并记录依据；不重复劝阻。
import os, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("风险","削弱","不合适","慎重","可能","建议改","替代"), "风险提示")
# 「写入 style 合同/锁定/记录依据」即执行承诺；显式尊重词为增强。
require_any(("尊重","按你","那就","执行","继续用","坚持","写入 style 合同","锁定","记录"), "尊重执行")
require_any(("记录","依据","原因","选择依据"), "记录选择依据")
require_any(("一次","不再","不会重复","不再重复","仅提示"), "只劝阻一次")
