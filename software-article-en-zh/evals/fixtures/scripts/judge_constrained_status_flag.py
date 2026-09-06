#!/usr/bin/env python3
"""占位截断须标注：图 3 被占位符省略时，译文须说明该省略，且其余正文完整译出。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if not re.search(r"省略|占位|未提供|缺失|略去|未包含|图中内容", text):
    print("未说明图 3 被占位符省略的受限状态", file=sys.stderr)
    sys.exit(1)

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 15:
    print("缺少中文译文主体", file=sys.stderr)
    sys.exit(1)

if not re.search(r"队列|调度|延迟|尾延迟", text):
    print("正文（调度器/队列/尾延迟）疑未翻译", file=sys.stderr)
    sys.exit(1)

print("占位截断受限标注通过")
