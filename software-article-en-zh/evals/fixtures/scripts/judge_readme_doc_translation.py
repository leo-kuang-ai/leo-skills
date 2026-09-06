#!/usr/bin/env python3
"""真实文档全文翻译冒烟：MIT 与安装命令在场、sh 围栏保留、章节结构对齐、中文规模下限
（下限兼防"源文件不可读后静默降级"——真读了 README 才可能达到该规模）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

for needle, label in [
    ("MIT", "许可证声明"),
    ("npx skills add leo-kuang-ai/leo-skills", "安装命令"),
    ("claude plugin marketplace add", "插件市场命令"),
]:
    if needle not in text:
        print("%s 缺失: %s" % (label, needle), file=sys.stderr)
        sys.exit(1)

# 源文 2 个 ```sh 块（4 行围栏）+ 3 处行内代码；结构允许包装，围栏行计数 >= 4
fence_lines = len(re.findall(r"(?m)^```", text))
if fence_lines < 4:
    print("代码围栏行不足：期望至少 4 行（2 个 sh 块），实际 %d" % fence_lines, file=sys.stderr)
    sys.exit(1)

# 章节结构：源文 9 个二级标题（Routes…License），译文二级标题 >= 7（允许说明区占用后仍有主体章节）
h2 = len(re.findall(r"(?m)^##(?!#)", text))
if h2 < 7:
    print("二级章节数不足：期望至少 7 个，实际 %d" % h2, file=sys.stderr)
    sys.exit(1)

# 中文规模下限：完整译文（源文 3514 ASCII）中文显著在场；低于此线疑为"文件不可读"降级输出
cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
if cjk < 400:
    print("中文译文仅 %d 字符（完整 README 译文应显著高于此；疑源文件读取失败后降级）" % cjk, file=sys.stderr)
    sys.exit(1)

print("真实文档翻译冒烟通过")
