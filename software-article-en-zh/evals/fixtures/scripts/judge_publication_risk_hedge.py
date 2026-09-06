#!/usr/bin/env python3
"""风险弱化保持：might→可能、cannot guarantee→不保证/无法保证、at most→最多 必须在场；
句级否定感知禁止把弱化语气润色成确定性（一定/必然/绝对/永远）。先剥离五件套元信息区。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

m = re.search(
    r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*\**\s*(?:交付说明|交付信息|逐句对照说明|审校状态|技术复核|编辑复核|翻译说明|译注|说明|覆盖范围|保护检查|未解决项|未解决事项|术语表|歧义与原文问题|歧义清单|原文问题|需作者确认)\s*[:：]?\**.*$",
    text,
)
body = text[: m.start()] if m else text

if not re.search(r"可能|或许", body):
    print("正文缺少 might 的弱化锚点（可能/或许）", file=sys.stderr)
    sys.exit(1)

if not re.search(r"不保证|无法保证|不能保证", body):
    print("正文缺少 cannot guarantee 的弱化锚点（不保证/无法保证）", file=sys.stderr)
    sys.exit(1)

if not re.search(r"最多|至多|不超过", body):
    print("正文缺少 at most 的上界锚点（最多/不超过）", file=sys.stderr)
    sys.exit(1)

for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"一定|必然|绝对|永远|万无一失", s) and not re.search(r"不|未|无|并非|并不是|没有|而非|原文", s):
        print("弱化风险被润色成确定性: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

for a in ("延迟", "副本"):
    if a not in body:
        print("正文缺少内容词 %s（疑未翻译或剥离过界）" % a, file=sys.stderr)
        sys.exit(1)

print("风险弱化保持通过")
