#!/usr/bin/env python3
"""链接/占位符保护 + 可译义务：URL、{USER_TOKEN}、%s、$HOME/bin、图片路径原样保留，链接标签(Configuration Guide)与 alt(Architecture)确实译出中文。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

for needle, label in [
    ("https://docs.example.com/config", "链接目标"),
    ("{USER_TOKEN}", "占位符 {USER_TOKEN}"),
    ("%s", "格式占位符 %s"),
    ("$HOME/bin", "路径 $HOME/bin"),
    ("/assets/arch.png", "图片路径"),
]:
    if needle not in text:
        print("%s 被改写或丢失: %s" % (label, needle), file=sys.stderr)
        sys.exit(1)

# 可译义务：链接标签 Configuration Guide 须译出（"指南"类），alt Architecture 须译出（"架构"类）
if not re.search(r"配置指南|部署指南|指南", text):
    print("链接标签 Configuration Guide 未翻译（可译内容应译出）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"架构", text):
    print("图片 alt 文本 Architecture 未翻译（可译内容应译出）", file=sys.stderr)
    sys.exit(1)

# 目标未被翻译替换（防标签译了但目标被中文化）
if re.search(r"docs\.example\.com/配置|文档\.示例", text):
    print("链接目标被翻译", file=sys.stderr)
    sys.exit(1)

print("链接与占位符保护+可译义务通过")
