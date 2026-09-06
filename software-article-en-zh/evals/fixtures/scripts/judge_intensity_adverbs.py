#!/usr/bin/env python3
"""程度强化词保留：significantly/far more/much faster 译出强化语义，弱化表述（句级否定感知）禁止。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

# ① significantly reduces
if not re.search(r"(显著|明显|大幅)[^。\n]{0,8}(降低|减少|缩短|下降)", text):
    print("significantly 的强化语义丢失（显著/明显/大幅 + 降低）", file=sys.stderr)
    sys.exit(1)

# ② far more effective
if not re.search(r"远比|远胜|远远|有效得多|比[^。\n]{0,12}有效得多|要有效得多", text):
    print("far more effective 的强化语义丢失（远比/有效得多）", file=sys.stderr)
    sys.exit(1)

# ③ much faster
if not re.search(r"快得多|明显更快|大幅(加快|缩短|提速)|显著(提升|加快|更快)|快上(不少|许多)|快了(很多|许多|不少)|明显(感受|感觉)?到?[^。\n]{0,6}快", text):
    print("much faster 的强化语义丢失（快得多/明显更快）", file=sys.stderr)
    sys.exit(1)

# ④ 弱化禁令（否定感知）：降低/缩短句带“略微/稍微/小幅”且无否定语境即失败
for s in sentences:
    if re.search(r"(降低|减少|缩短|下降)", s) and re.search(r"略微|稍微|小幅|些许", s):
        if not re.search(r"不|未|并非|而不是", s):
            print("强化词被弱化为“略微/稍微/小幅”: %s" % s.strip(), file=sys.stderr)
            sys.exit(1)

# ⑤ 内容词在场
for anchor in ("延迟", "缓存", "冷启动"):
    if anchor not in text:
        print("缺少内容词 %s" % anchor, file=sys.stderr)
        sys.exit(1)

print("程度强化词保留通过")
