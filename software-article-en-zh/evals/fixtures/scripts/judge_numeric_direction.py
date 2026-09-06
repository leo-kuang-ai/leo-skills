#!/usr/bin/env python3
"""by/to 方向：decreased by 30% = 降低 30%（变化量），dropped to 1.2% = 降至 1.2%（终点）；不得互换。"""
import os
import re
import sys
import unicodedata

text = unicodedata.normalize("NFKC", os.environ.get("EVAL_FINAL_MESSAGE", ""))
sentences = re.split(r"[。！？；;\n]+", text)

# ① decreased by 30%：降低/下降 + 30%（变化量语义）
if not re.search(r"(降低|下降|减少)(了)?[^0-9]{0,3}30\s*%|30\s*%[^0-9]{0,3}(降低|下降|减少)", text):
    print("decreased by 30% 未译出“降低 30%”变化量语义", file=sys.stderr)
    sys.exit(1)

# ② dropped to 1.2%：降至/降到 + 1.2%（终点语义）
if not re.search(r"(降至|降到|下降到|跌至|降为)[^0-9]{0,3}1\.2\s*%", text):
    print("dropped to 1.2% 未译出“降至 1.2%”终点语义", file=sys.stderr)
    sys.exit(1)

# ③ grew by 15% 与 rose to 92%
if not re.search(r"(增加|增长|上升|提高)(了)?[^0-9]{0,3}15\s*%|15\s*%[^0-9]{0,3}(增长|增加)", text):
    print("grew by 15% 未译出“增长 15%”变化量语义", file=sys.stderr)
    sys.exit(1)
if not re.search(r"(升至|升到|上升到|提高至|升至为?)[^0-9]{0,3}92\s*%", text):
    print("rose to 92% 未译出“升至 92%”终点语义", file=sys.stderr)
    sys.exit(1)

# ④ by/to 互换禁令（句级否定感知；变化量误作终点须带“了”，“下降至”不算）
for s in sentences:
    if re.search(r"(降至|降到|下降到)[^0-9]{0,3}30\s*%", s) and not re.search(r"不|未|并非|而不是", s):
        print("by 30% 被译成“降至 30%”（变化量误作终点）: " + s.strip(), file=sys.stderr)
        sys.exit(1)
    if re.search(r"(降低|下降|减少)了[^0-9]{0,3}1\.2\s*%", s) and not re.search(r"不|未|并非|而不是", s):
        print("to 1.2% 被译成“降低了 1.2%”（终点误作变化量）: " + s.strip(), file=sys.stderr)
        sys.exit(1)

print("by/to 方向语义通过")
