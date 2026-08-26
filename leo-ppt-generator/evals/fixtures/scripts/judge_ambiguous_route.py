#!/usr/bin/env python3
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)

def require_all(values):
    missing = [v for v in values if v not in text]
    if missing: fail(f"缺少必需内容: {', '.join(missing)}")

def require_any(values, label):
    if not any(v in text for v in values): fail(f"缺少{label}: {' | '.join(values)}")

def positive(pattern):
    for sentence in re.split(r"[。！？\n]+", text):
        if re.search(pattern, sentence) and not any(v in sentence for v in ("不", "不能", "不会", "不得", "禁止")):
            return sentence
    return None

require_all(("direct-editable", "generate"))
require_any(("严格保留", "严格还原", "严格复刻", "保留版式", "高保真", "必须还原", "严格转成可编辑", "对象级可编辑"), "保真分支")
require_any(("风格参考", "仅作风格", "参考风格", "视觉参考", "重新设计"), "重设计分支")
bad = positive(r"(?:先|直接).{0,12}generate.{0,20}(?:再|然后).{0,12}(?:可编辑|direct-editable)")
if bad:
    fail(f"未经确认串联两条 Route: {bad}")
