#!/usr/bin/env python3
"""Caveats 段保留：Windows 限制句须带否定表述，loses precision 须译出精度损失，限制段不得省略。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

win_hits = [s for s in sentences if re.search(r"Windows", s, re.IGNORECASE)]
if not win_hits:
    print("Caveats 段的 Windows 限制句缺失（限制段被省略）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"不|无法|不能|不支持|没", s) for s in win_hits):
    print("Windows 限制句的否定表述丢失: %s" % win_hits[0].strip(), file=sys.stderr)
    sys.exit(1)

if not re.search(r"精度|精确", text):
    print("loses precision 的精度损失未译出", file=sys.stderr)
    sys.exit(1)

print("Caveats 限制段保留通过")
