#!/usr/bin/env python3
"""否定辖域覆盖析取：does not support A or B → 否定须覆盖两项（同句含 Windows+macOS+否定）；
不得出现只肯定不否定的支持句（句级否定感知）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

# ① Windows 与 macOS 同句且带否定（既不支持…也不支持 / 不支持 A 或 B）
support_ok = any(
    re.search(r"Windows", s) and re.search(r"macOS", s) and re.search(r"不|未|无法|并非|既不", s)
    for s in sentences
)
if not support_ok:
    print("否定未覆盖析取（未找到 Windows+macOS 同句带否定的表述）", file=sys.stderr)
    sys.exit(1)

# ② 支持句禁令：句子声称支持 Windows 而无否定语境即失败
for s in sentences:
    if re.search(r"Windows", s) and re.search(r"支持|兼容|可运行", s):
        if not re.search(r"不|未|无法|并非|既不|也不|都没", s):
            print("否定辖域丢失（Windows 变为被支持）: %s" % s.strip(), file=sys.stderr)
            sys.exit(1)

# ③ 需求句：shell/终端 同句带否定
require_ok = any(
    re.search(r"shell|终端", s) and re.search(r"不|未|无需|不需要|不必", s) for s in sentences
)
if not require_ok:
    print("does not require 的否定未覆盖 shell/终端", file=sys.stderr)
    sys.exit(1)
for s in sentences:
    if re.search(r"shell", s) and re.search(r"需要|要求|依赖", s):
        if not re.search(r"不|未|无需|不必|并非", s):
            print("否定需求句被译成肯定需求: %s" % s.strip(), file=sys.stderr)
            sys.exit(1)

print("否定辖域析取通过")
