#!/usr/bin/env python3
"""not uncommon 保留双重否定（“罕见”出现必须带否定词），cannot...without 译出条件否定而非丢掉前提。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

# ① not uncommon → 并非罕见/并不少见/不罕见（或语义等价的“很常见”类表述）
if not re.search(r"并非罕见|并不罕见|并不少见|不罕见|不是很少见|很常见|相当常见|十分常见|屡见不鲜|时有发生|并不鲜见|(并不算|不算|算不上|称不上)(罕见|少见)", text):
    print("not uncommon 的双重否定丢失", file=sys.stderr)
    sys.exit(1)

# ③ “罕见”一旦出现必须伴随否定词，防止直接翻转成“很罕见”
for s in sentences:
    if re.search(r"罕见", s) and not re.search(r"并非|并不|不是|不|未|毫不", s):
        print("双重否定被翻转成肯定否定式（如“很罕见”）: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# ② cannot debug without enabling trace logging → 条件否定三型任一（窗口放宽容纳插入的英文原词）
without_pattern = (
    re.search(r"(不|若不|如果不|若未|未|没有)(启用|开启|打开).{0,40}无法", text)
    or re.search(r"无法.{0,40}(除非|若不|如果不)", text)
    or re.search(r"(只有|唯有|必须|需要|得).{0,8}(启用|开启|打开).{0,40}(才能|方可|才可|才能够|来|以)", text)
)
if not without_pattern:
    print("cannot...without 的条件否定丢失（未译出“不启用…无法/只有…才能”）", file=sys.stderr)
    sys.exit(1)

# 内容词在场：重试/追踪日志
if not re.search(r"重试", text):
    print("译文缺少 retries 内容词（重试）", file=sys.stderr)
    sys.exit(1)

print("双重否定保留通过")
