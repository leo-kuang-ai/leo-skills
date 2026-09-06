#!/usr/bin/env python3
"""编辑不新增事实：译文主体不得出现承诺类表述（一定/保证/确保/务必/万无一失），
先剥离交付说明/逐句对照/审校状态等元信息区（其中讨论原文保证属健康行为），句级否定感知。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 剥离元信息区：首个说明类标题/加粗标题行或行内式“标题：内容”行之后不参与承诺词检查
m = re.search(
    r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*\**\s*(?:交付说明|交付信息|逐句对照说明|审校状态|技术复核|编辑复核|翻译说明|译注|说明|覆盖范围|保护检查|未解决项|未解决事项|技术术语表|术语表|术语对照|术语清单|歧义与原文问题|歧义清单|原文问题|需作者确认)\s*[:：]?\**.*$",
    text,
)
body = text[: m.start()] if m else text

for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"一定|保证|确保|务必|万无一失|所有测试", s) and not re.search(r"不|未|无|并非|并不是|没有|而非|原文", s):
        print("编辑润色引入承诺类新事实: " + s.strip(), file=sys.stderr)
        sys.exit(1)

# 译文主体内容词在场（防回显/防空洞）
for a in ("一次性", "生产", "修复"):
    if a not in body:
        print("译文主体缺少内容词 %s（疑未翻译或剥离过界）" % a, file=sys.stderr)
        sys.exit(1)

print("编辑不新增事实通过")
