#!/usr/bin/env python3
"""at most/at least/no more than 的上下界标记必须紧邻对应数字，不得互换，也不得出现无否定限定的“超过 30 秒”。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

MOST = r"(?:最多|不超过|至多|不多于|最长|以内|之内|上限(?:为|是)?|顶多)"
LEAST = r"(?:至少|不少于|最少)"


def near(pattern, number):
    # 界限词与数字之间只允许少量非数字字符（空格、“有”、“为”、“约”等）
    return re.search(pattern + r"[^0-9]{0,4}" + number + r"(?![0-9])", text) or re.search(
        number + r"(?![0-9])[^0-9]{0,4}" + pattern, text
    )


# ① at most 10：最多/不超过 紧邻 10，且不得降为“至少”
if not near(MOST, "10"):
    print("at most 10 未译出“最多/不超过”邻接 10 的上界", file=sys.stderr)
    sys.exit(1)
if re.search(r"至少[^0-9]{0,4}10(?![0-9])", text):
    print("at most 10 被译成“至少 10”（上下界互换）", file=sys.stderr)
    sys.exit(1)

# ② at least 2：至少 紧邻 2，且不得升为“最多”
if not near(LEAST, "2"):
    print("at least 2 未译出“至少”邻接 2 的下界", file=sys.stderr)
    sys.exit(1)
if re.search(MOST + r"[^0-9]{0,4}2(?![0-9])", text):
    print("at least 2 被译成“最多 2”（上下界互换）", file=sys.stderr)
    sys.exit(1)

# ③ no more than 30：上界标记紧邻 30
if not near(MOST, "30"):
    print("no more than 30 未译出“不超过/最多”邻接 30 的上界", file=sys.stderr)
    sys.exit(1)

# ④ “超过 30 秒”必须带否定限定
for s in sentences:
    if re.search(r"超过[^0-9]{0,3}30(?![0-9])", s) and not re.search(r"不|未|不得|不能|没有|不会", s):
        print("“超过 30 秒”缺少否定限定（no more than 被丢掉上界）: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("范围上下界保留通过")
