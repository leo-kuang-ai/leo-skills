#!/usr/bin/env python3
"""审校结构化：须指出数字误译（128 译成 1280）与模态强度问题（MUST 译成可以），并使用严重性分级词汇。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# ① 数字误译：引用了错误值 1280 且给出/对照了正确值 128（独立数字，非 1280 的子串），或明确提“数字/数值”
has_1280 = re.search(r"1280", text)
has_standalone_128 = re.search(r"(?<!\d)128(?!\d)", text)
if not ((has_1280 and has_standalone_128) or re.search(r"数字(类)?(误|错|问)|数值(误|错|问)|误译|译错", text)):
    print("未指出数字误译（128 被译成 1280）", file=sys.stderr)
    sys.exit(1)

# ② 模态强度问题：MUST 译成“可以”
if not re.search(r"必须|强度|规范|MUST|情态|模态|语气", text, re.IGNORECASE):
    print("未指出 MUST 被弱化为“可以”的模态强度问题", file=sys.stderr)
    sys.exit(1)

# ③ 严重性分级（接受英文分级或中文分级：严重/重要/轻微、分级标题带序号）
if not re.search(r"critical|major|minor|严重性|严重\s*[:：]?\s*\d|重要问?题|轻微|\d\s*[级类]", text, re.IGNORECASE):
    print("审校意见未使用严重性分级（critical/major/minor 等）", file=sys.stderr)
    sys.exit(1)

print("审校结构化分级通过")
