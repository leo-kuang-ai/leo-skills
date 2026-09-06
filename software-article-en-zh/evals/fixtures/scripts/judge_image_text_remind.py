#!/usr/bin/env python3
"""图片文字提醒：路径原样、remind 信号在场、无图像证据时不断言图片一定含某种文字（否定感知）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

# ① 图片路径原样保留
for p in ("images/onboarding.png", "assets/capacity-flow.svg"):
    if p not in text:
        print("图片路径未原样保留: %s" % p, file=sys.stderr)
        sys.exit(1)

# ② remind 信号：提醒候选图片，或说明图片可能含未翻译文字（窗口放宽容纳图片路径列表）
remind = (
    re.search(r"(提醒|候选|注意|需要|本地化)[^。\n]{0,40}(图|截图|图表)", text)
    or re.search(r"(图|截图|图表)[^。\n]{0,80}(可能|疑似|或|如有|或许|建议|另行)", text)
    or re.search(r"(中文|本地化)[^。\n]{0,24}(版本)?图片", text)
)
if not remind:
    print("未按 image_text_policy: remind 给出图片文字候选提醒", file=sys.stderr)
    sys.exit(1)

# ③ 越权断言禁令：断言图中文字内容必须带不确定限定（可能/疑似/若/如需/通常等）
for s in sentences:
    if re.search(r"(图中|图片中|截图中的?|图表中)", s) and re.search(r"(英文|中文|文字|未翻译)", s):
        if not re.search(r"可能|疑似|或|如有|或许|需要|建议|候选|若|如果|如需|通常|一般", s):
            print("无图像证据却断言图片文字内容（越权）: %s" % s.strip(), file=sys.stderr)
            sys.exit(1)

# ④ 正文内容在场
if not re.search(r"引导|入职|入驻", text):
    print("缺少 onboarding 内容词（引导/入职/入驻）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"容量", text):
    print("缺少 capacity 内容词（容量）", file=sys.stderr)
    sys.exit(1)

print("图片文字提醒策略通过")
