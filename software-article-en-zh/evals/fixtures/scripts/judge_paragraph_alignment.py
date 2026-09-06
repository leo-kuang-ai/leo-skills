#!/usr/bin/env python3
"""段落对齐：源文 4 个自然段，译文按空行分块后须仍有至少 4 个含实质中文内容的段落。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def cjk_count(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
substantial = [b for b in blocks if sum(cjk_count(line) for line in b.splitlines()) >= 10]
# 兼容译文以单个换行分段的情况：退化为按行统计
if len(substantial) < 4:
    substantial = [ln for ln in text.splitlines() if cjk_count(ln) >= 10]

if len(substantial) < 4:
    print("含实质内容的段落仅 %d 个（源文 4 段），段落被合并或改写塌缩" % len(substantial), file=sys.stderr)
    sys.exit(1)

print("段落结构对齐通过")
