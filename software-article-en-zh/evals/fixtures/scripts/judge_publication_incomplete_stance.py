#!/usr/bin/env python3
"""不完整立场保持：suggest 的余地（表明/初步/可能）、单一负载限定（仅/只）、
cannot rule out 的风险保留（不能排除/无法排除/不排除）必须在场；
句级否定感知禁止把初步结论润色成“证明/显著/全面”。先剥离五件套元信息区。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

m = re.search(
    r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*\**\s*(?:交付说明|交付信息|逐句对照说明|审校状态|技术复核|编辑复核|翻译说明|译注|说明|覆盖范围|保护检查|未解决项|未解决事项|术语表|歧义与原文问题|歧义清单|原文问题|需作者确认)\s*[:：]?\**.*$",
    text,
)
body = text[: m.start()] if m else text

if not re.search(r"表明|显示|初步|可能", body):
    print("正文缺少 suggest 的余地锚点（表明/显示/初步/可能）", file=sys.stderr)
    sys.exit(1)

found_single_workload = False
for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"负载|工作负载", s):
        if re.search(r"仅|只|单一|一个", s):
            found_single_workload = True
if not found_single_workload:
    print("单一负载限定（only tested one workload）疑似丢失", file=sys.stderr)
    sys.exit(1)

if not re.search(r"不能排除|无法排除|不排除|无法排除在外", body):
    print("正文缺少 cannot rule out 的风险保留锚点", file=sys.stderr)
    sys.exit(1)

for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"证明|显著|全面|彻底", s) and not re.search(r"不|未|无|并非|并没有|尚未|原文|计划", s):
        print("初步结论被润色成确定性: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

for a in ("分配器", "延迟"):
    if a not in body:
        print("正文缺少内容词 %s（疑未翻译或剥离过界）" % a, file=sys.stderr)
        sys.exit(1)

print("不完整立场保持通过")
