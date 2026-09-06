#!/usr/bin/env python3
"""脚注结构：[^1]/[^shared] 引用与定义各 ≥2 次，定义行保持 Markdown 脚注语法，定义内容译出中文。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# ① 引用与定义成对（正文 1 次 + 定义 1 次 = 2）
if text.count("[^1]") < 2:
    print("[^1] 引用/定义未成对保留（出现 %d 次，应 ≥2）" % text.count("[^1]"), file=sys.stderr)
    sys.exit(1)
if text.count("[^shared]") < 2:
    print("[^shared] 引用/定义未成对保留（出现 %d 次，应 ≥2）" % text.count("[^shared]"), file=sys.stderr)
    sys.exit(1)

# ② 定义行保持脚注语法（ASCII 冒号，结构原样）
def_lines = [l for l in text.splitlines() if re.match(r"^ {0,3}\[\^(1|shared)\]:", l)]
if len(def_lines) < 2:
    print("脚注定义行语法缺失或被改写（[^id]: 形式不足 2 行）", file=sys.stderr)
    sys.exit(1)

# ③ 定义内容译为中文
def_text = "\n".join(def_lines)
if len(re.findall(r"[\u4e00-\u9fff]", def_text)) < 4:
    print("脚注定义内容未翻译", file=sys.stderr)
    sys.exit(1)

# ④ 正文锚点与版本号
for anchor in ("预算", "租户"):
    if anchor not in text:
        print("缺少正文内容词 %s" % anchor, file=sys.stderr)
        sys.exit(1)
if "3.2" not in text:
    print("版本号 3.2 丢失", file=sys.stderr)
    sys.exit(1)

print("脚注结构保留通过")
