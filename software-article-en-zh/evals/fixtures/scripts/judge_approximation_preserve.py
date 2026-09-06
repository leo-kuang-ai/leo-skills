#!/usr/bin/env python3
"""约数标记保留：approximately/roughly 译出“大约/约/左右”，不得强化为“整整/恰好/正好”。"""
import os
import re
import sys
import unicodedata

text = unicodedata.normalize("NFKC", os.environ.get("EVAL_FINAL_MESSAGE", ""))
sentences = re.split(r"[。！？；;\n]+", text)

APPROX = r"(?:大约|约|大概|近似|差不多)"

# ① approximately 2 hours：约数词邻接“2 小时/两小时”，或“2 小时左右”
hours_ok = re.search(APPROX + r".{0,8}(2|两)\s*个?\s*小时", text) or re.search(
    r"(2|两)\s*个?\s*小时[^0-9]{0,3}左右", text
)
if not hours_ok:
    print("approximately 2 hours 未保留约数标记（大约/约/左右）", file=sys.stderr)
    sys.exit(1)

# ② roughly 40%：约数词邻接 40%（兼容全角％与中文数词“四成”），或“40% 左右”
percent_ok = (
    re.search(APPROX + r".{0,8}40\s*[%％]", text)
    or re.search(r"40\s*[%％][^0-9]{0,3}左右", text)
    or re.search(r"(?:约|大约|近)四成", text)
)
if not percent_ok:
    print("roughly 40% 未保留约数标记（大约/约/左右）", file=sys.stderr)
    sys.exit(1)

# ③ 不得精确化：句内“整整/恰好/正好/刚好 + 数值”且无否定语境即失败
for s in sentences:
    if re.search(r"(整整|恰好|正好|刚好|准?确到).{0,6}(2|两).{0,4}小时", s) and not re.search(r"不|并非|未|并非正好", s):
        print("approximately 被精确化为“整整/恰好 2 小时”: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)
    if re.search(r"(整整|恰好|正好|刚好|准?确到).{0,6}40\s*%", s) and not re.search(r"不|并非|未", s):
        print("roughly 被精确化为“正好 40%”: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("约数标记保留通过")
