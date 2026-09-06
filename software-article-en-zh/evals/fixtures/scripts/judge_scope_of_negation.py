#!/usr/bin/env python3
"""部分否定辖域保持：Not all → “并非所有/不是所有/部分用户”，不得放大为“所有用户都不”；does not remove all 不得变成移除全部或一个不删。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

# ① Not all → 并非所有/不是所有/部分用户 任一
if not re.search(r"(并非|不是|并不是|未必)(所有|全部|每个)|部分用户|有些用户|某些用户", text):
    print("Not all 未译出部分否定（并非所有/不是所有/部分用户）", file=sys.stderr)
    sys.exit(1)

# ② 否定辖域不得放大：句内出现“所有用户/全部用户”必须有部分否定限定词
for s in sentences:
    if re.search(r"所有用户|全部用户|每个用户", s) and not re.search(r"并非|不是|并不是|并不都|未|部分|有些|某些", s):
        print("部分否定被放大为全称（如“所有用户都不受影响”）: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# ③ does not remove all legacy flags：移除句必须带否定，且不得翻转成“移除任何”（一个不删）
remove_hits = [s for s in sentences if re.search(r"移除|删除|去掉|清理", s) and re.search(r"旧|遗留|legacy|传统", s)]
if not remove_hits:
    print("未找到 legacy flags 移除相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
for s in remove_hits:
    if not re.search(r"不|未|并非|并不|没有|不会", s):
        print("does not remove 的否定丢失: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)
    # 说明区常引用被否定的错误读法（“避免误译成‘不移除任何…’”），带引用/避免标记的句子豁免
    if re.search(r"(移除|删除|去掉|清理)(了)?(任何|任何一个)", s) and not re.search(
        r"避免|误译|≠|而非|而不是|不是|说明|「|」|『|』|→", s
    ):
        print("does not remove all 被翻转为“一个也不移除”: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("否定辖域保留通过")
