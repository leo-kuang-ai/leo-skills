#!/usr/bin/env python3
"""软件 UI 边界：技术句（调度/重试）正常翻译；UI 标签要么给出界面/按钮类边界说明，要么至少两个标签按数据原样保留。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# ① 技术句子正常翻译
if not re.search(r"调度", text):
    print("缺少 scheduler 的内容词（调度）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"重试", text):
    print("缺少 retries 的内容词（重试）", file=sys.stderr)
    sys.exit(1)

# ② UI 标签处理有边界：提及 UI/界面/按钮，或至少两个标签原样保留
labels = ["OK", "Cancel", "Submit", "Retry Now"]
kept = [label for label in labels if label in text]
if not re.search(r"UI|界面|按钮|控件|产品文案", text) and len(kept) < 2:
    print("UI 标签既无界面/按钮类边界说明，也未按数据保留至少两个标签", file=sys.stderr)
    sys.exit(1)

print("软件 UI 边界处理通过")
