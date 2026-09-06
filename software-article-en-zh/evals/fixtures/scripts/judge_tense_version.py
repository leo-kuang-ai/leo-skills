#!/usr/bin/env python3
"""版本演进时态：will be deprecated 保留将来标记，has been replaced 完成时，is being rewritten 进行时；
未来计划不得提前为既成事实（句级否定感知）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

# ① will be deprecated：将来标记 + 弃用
if not re.search(r"(将|计划|即将|以后)[^。\n]{0,12}(弃用|废弃)", text):
    print("will be deprecated 丢失将来时标记（将于 v4.2 弃用）", file=sys.stderr)
    sys.exit(1)

# ② has been replaced：完成时（已被替换/取代，允许中间插入施动者名词）
if not re.search(r"已[^。\n]{0,24}(替换|取代|更换)", text):
    print("has been replaced 丢失完成时（已被替换）", file=sys.stderr)
    sys.exit(1)

# ③ is being rewritten：进行时（正在被重写，允许插入工具/语言名词）
if not re.search(r"正在[^。\n]{0,24}(重写|改写|重构|迁移)", text):
    print("is being rewritten 丢失进行时（正在被重写）", file=sys.stderr)
    sys.exit(1)

# ④ 版本号在场
for v in ("4.2", "5.0"):
    if v not in text:
        print("版本号 %s 丢失" % v, file=sys.stderr)
        sys.exit(1)

# ⑤ 时态提前禁令（否定感知）：v4.2 句不得声称已经弃用
for s in sentences:
    if re.search(r"4\.2", s) and re.search(r"已(经)?(弃用|废弃|移除)", s):
        if not re.search(r"不|未|并非|而非|计划|将", s):
            print("未来弃用被提前为既成事实: %s" % s.strip(), file=sys.stderr)
            sys.exit(1)

print("版本演进时态通过")
