#!/usr/bin/env python3
# 母版合同校验：无落位母版必须先修母版再过校验器，不直接派发。
import os, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("不能过", "无法过", "不会过", "过不了", "先修", "需要修", "失败", "不通过"), "校验不过判定")
require_any(("落位", "无点无家", "容器", "check_master_contract", "校验器"), "落位/校验器指认")
require_any(("母版",), "修母版而非改图")
# good 样例的"要点3"被正则视为字面量——用宽匹配（要点3/第3/越界/超出）。
if not any(v in text for v in ("要点3", "要点 3", "第 3", "第三个", "悬空", "不存在", "越界", "超出")):
    fail("缺少悬空引用指认")
