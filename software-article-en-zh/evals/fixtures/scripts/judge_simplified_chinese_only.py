#!/usr/bin/env python3
"""简体字形回归：繁体独占字形不得出现（可诊断列出），内容词在场保证确实翻译了。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

TRAD_ONLY = "與為譯監說條應內後務數據庫對還時開間術語顯錯誤讀寫運叢儀錶層據"
found = [c for c in TRAD_ONLY if c in text]
if found:
    print("检测到繁体独占字形（目标语言 zh-CN）: %s" % " ".join(found), file=sys.stderr)
    sys.exit(1)

cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
if cjk < 40:
    print("中文字符仅 %d，疑未翻译" % cjk, file=sys.stderr)
    sys.exit(1)

for anchor in ("迁移", "集群"):
    if anchor not in text:
        print("缺少内容词 %s" % anchor, file=sys.stderr)
        sys.exit(1)

print("简体字形回归通过")
