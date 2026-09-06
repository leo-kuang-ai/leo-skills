#!/usr/bin/env python3
"""内置术语表遵循：幻觉/护栏/对齐/上下文工程按内置译法在场，双译法词条接受约定变体。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
if cjk < 40:
    print("译文中文占比不足（疑未翻译或回显英文），中文字符 %d" % cjk, file=sys.stderr)
    sys.exit(1)

required = {"幻觉": "hallucination", "护栏": "guardrails", "对齐": "alignment", "上下文工程": "context engineering"}
missing = [zh for zh in required if zh not in text]

alt_ok = {"凭感觉编程": ("凭感觉式编程",), "AI 套壳": ("套壳",), "苦涩的教训": ("苦涩教训",)}
for zh, alts in alt_ok.items():
    if zh not in text and not any(a in text for a in alts):
        missing.append(zh)

if missing:
    print("内置术语表词条未按内置译法统一，缺失: %s" % "、".join(missing), file=sys.stderr)
    sys.exit(1)

print("内置术语表遵循通过")
