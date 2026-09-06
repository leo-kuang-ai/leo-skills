#!/usr/bin/env python3
"""标题层级保持：源文 2 个一级、2 个二级、1 个三级标题，译文须保持同等数量；状态说明类标题不计入。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 剔除输出契约自带的状态说明标题（覆盖范围/审校状态等）与"## 译文"类包装标题，避免膨胀计数
lines = []
for line in text.splitlines():
    if re.match(r"^#{1,6}[ \t]*\S", line) and \
            re.search(r"覆盖|范围|审校|未解决|限制|术语|状态|说明|备注|元信息|翻译信息|交付|输出|元数据|译文|译注|翻译结果|中文翻译", line):
        continue
    lines.append(line)
body = "\n".join(lines)


def count_level(n):
    # 恰好 n 个 # 开头且第 n+1 字符不是 #（允许 # 后无空格）
    return len(re.findall(r"^" + "#" * n + r"(?!#)", body, re.MULTILINE))


l1, l2, l3 = count_level(1), count_level(2), count_level(3)
if (l1, l2, l3) != (2, 2, 1):
    print("标题层级数与源文不符：一级 %d（应 2）、二级 %d（应 2）、三级 %d（应 1）" % (l1, l2, l3), file=sys.stderr)
    sys.exit(1)

print("标题层级保持通过")
