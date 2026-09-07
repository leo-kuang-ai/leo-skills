#!/usr/bin/env python3
"""未明确正文时采用成品总页数，不追加结构页或无必要口径等待。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
if not re.search(r"(?:总共|成品|总计|总数|共|总页数|总页数为).{0,12}15|15\s*页.{0,16}(?:总页数|包含|包括|含封面|成品)", text):
    print("未按成品总数15页说明", file=sys.stderr)
    sys.exit(1)
if not re.search(r"封面|结构页", text):
    print("未说明结构页包含在总数内", file=sys.stderr)
    sys.exit(1)
for sentence in re.split(r"[。！？；;\n]+", text):
    if re.search(r"17\s*页", sentence) and not re.search(r"不|无需|不会|不是", sentence):
        print("错误追加结构页", file=sys.stderr)
        sys.exit(1)
    if re.search(r"请.{0,8}确认.{0,10}(页数|口径)|是.{0,8}正文.{0,8}还是|先.{0,6}回复.{0,6}口径", sentence):
        print("再次索取无必要页数确认", file=sys.stderr)
        sys.exit(1)
print("总页数默认口径通过")
