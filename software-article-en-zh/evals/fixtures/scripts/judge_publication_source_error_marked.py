#!/usr/bin/env python3
"""发布型原文错误标记：正文须保留原值 8080；正确值 6379 仅允许出现在带说明语境的
元信息区（审校提示/歧义与原文问题清单）；且必须存在标记/说明行为（原文如此/疑为/应为/请确认等），
只保留不标记同样失败。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if "8080" not in text:
    print("原文端口号 8080 在译文中缺失，疑被静默改写", file=sys.stderr)
    sys.exit(1)

# 正确值 6379 只能出现在说明语境（邻近元信息词），脱离语境即静默修正
META_WORDS = r"原文|实际|不符|事实|默认端口|审校|校对|译注|备注|注：|应为|疑为|似乎|清单|标记|请确认"
for sentence in re.split(r"[。！？；;\n]+", text):
    if "6379" in sentence and not re.search(META_WORDS, sentence):
        print("正文出现脱离说明语境的 6379，疑静默修正原文事实错误: %s" % sentence.strip(), file=sys.stderr)
        sys.exit(1)

# 标记并说明义务：必须存在对原文问题的显式标记/说明，仅保留原值不够
if not re.search(r"原文(如此|中|里)|疑为|应为|实际(上|为|是)|不符|事实(错误|有误)|有误|错误|请确认|建议核对|译注|存疑", text):
    print("保留了原值但未标记/说明原文疑似错误", file=sys.stderr)
    sys.exit(1)

for a in ("Redis", "重启"):
    if a not in text:
        print("缺少内容词 %s（疑未翻译）" % a, file=sys.stderr)
        sys.exit(1)

print("发布型原文错误标记通过")
