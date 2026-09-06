#!/usr/bin/env python3
"""结构异常报告：源文 python 代码围栏未闭合，译文须翻译正常文本并报告结构异常，不得静默补全或静默丢弃。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 15:
    print("缺少中文译文主体（正常文本未翻译）", file=sys.stderr)
    sys.exit(1)

if not re.search(r"队列|轮询|调度", text):
    print("围栏后的正常文本（调度器轮询队列）疑未翻译", file=sys.stderr)
    sys.exit(1)

report = re.search(r"未闭合|不完整|结构异常|围栏|fence|代码块标记|闭合|缺少.{0,6}结束", text, re.IGNORECASE)
if not report:
    print("源文的 ```python 围栏未闭合，输出未报告该结构异常（疑静默补全或丢弃）", file=sys.stderr)
    sys.exit(1)

print("结构异常报告通过")
