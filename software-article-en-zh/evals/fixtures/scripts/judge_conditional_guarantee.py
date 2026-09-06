#!/usr/bin/env python3
"""条件性保证：exactly-once 译“恰好一次/精确一次”，only when 条件结构保留；保证表述不得脱离条件词。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if not re.search(r"恰好一次|精确一次|精确交付一次|正好一次", text):
    print("exactly-once 未译作“恰好一次/精确一次”", file=sys.stderr)
    sys.exit(1)

if not re.search(r"只有|仅在|仅当|惟有|唯有", text):
    print("only when 的条件结构（只有/仅在/仅当）未保留", file=sys.stderr)
    sys.exit(1)

# 段落级否定感知：谈投递保证的段落必须同时含条件词，除非是否定/限定语境（如“不保证”“并非无条件保证”）
blocks = re.split(r"\n\s*\n", text)
for b in blocks:
    if re.search(r"保证", b) and re.search(r"投递|交付|恰好一次|精确一次", b) \
            and not re.search(r"只有|仅当|仅在|提供|前提|条件|才|不保证|并非|不是", b):
        print("投递保证被去条件化（段落内无条件词）: %s" % b.strip().replace("\n", " ")[:120], file=sys.stderr)
        sys.exit(1)

print("条件性保证保留通过")
