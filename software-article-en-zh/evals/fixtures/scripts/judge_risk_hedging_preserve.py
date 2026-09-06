#!/usr/bin/env python3
"""风险弱化保留：may cause data loss 须保留“可能”级弱化；损坏句须带弱化语气；不得出现“一定会导致/必将造成”。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

# may 的弱化由“可能”或低概率语境（极少数/罕见/…情况下）任一承担，均须与“数据丢失”同句
loss_hits = [s for s in sentences if re.search(r"数据丢失|丢失数据|丢失", s)]
if not loss_hits:
    print("译文缺少 data loss 内容（丢失）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"可能|或许|也许|极少数|罕见|情况下|或会|或将|往往", s) for s in loss_hits):
    print("may cause data loss 的风险弱化未保留（“可能”或低概率语境与“丢失”同句）", file=sys.stderr)
    sys.exit(1)

hedged = [s for s in sentences if re.search(r"损坏", s) and re.search(r"可能|或许|会|往往|容易|或引发|或将|或会", s)]
if not hedged:
    bad = [s for s in sentences if re.search(r"损坏", s)]
    print("could lead to corruption 句未保留弱化语气: %s" % (bad[0].strip() if bad else "（损坏句缺失）"), file=sys.stderr)
    sys.exit(1)

for s in sentences:
    if re.search(r"一定会导致|必将造成|肯定导致|必然导致", s) and not re.search(r"不|未|并非|而非|而不是", s):
        print("风险弱化被强化为必然表述: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("风险弱化保留通过")
