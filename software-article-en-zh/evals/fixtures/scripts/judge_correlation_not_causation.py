#!/usr/bin/env python3
"""相关性不得改为因果：correlate with 须译“相关/关联”；延迟句内出现因果动词必须带否定/限定语境。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

if not re.search(r"相关|关联", text):
    print("correlate with 未译作“相关/关联”类表述", file=sys.stderr)
    sys.exit(1)

# 含延迟相关词的句子若出现因果动词，必须有否定/限定语境（如“尚未证明因果”）。
# 术语/译法说明句（译为、对应、指代、引用原文）中出现的因果动词不属译文正文，豁免。
for s in sentences:
    if re.search(r"译为|译作|对应|指代|指|「|」|→|术语", s):
        continue
    if re.search(r"延迟|毛刺|尖峰", s) and re.search(r"导致|引起|造成", s) \
            and not re.search(r"不|未|没有|并非|尚|无法|而不是|而非", s):
        print("相关性句被改写为因果表述: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("相关性保留通过")
