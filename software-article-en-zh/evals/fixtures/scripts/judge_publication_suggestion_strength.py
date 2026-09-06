#!/usr/bin/env python3
"""建议强度保持：recommend/should consider 译为建议类表达且不得句级升级为“必须/强制”；
requires 的硬性要求保持“需要/必须”强度。先剥离五件套元信息区。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

m = re.search(
    r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*\**\s*(?:交付说明|交付信息|逐句对照说明|审校状态|技术复核|编辑复核|翻译说明|译注|说明|覆盖范围|保护检查|未解决项|未解决事项|术语表|歧义与原文问题|歧义清单|原文问题|需作者确认)\s*[:：]?\**.*$",
    text,
)
body = text[: m.start()] if m else text

if not re.search(r"建议|推荐|应当考虑|可以考虑", body):
    print("正文缺少建议类表达（recommend/should consider 被弱化或丢失）", file=sys.stderr)
    sys.exit(1)

# 建议句不得升级为强制（句级否定感知）
for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"故障转移|固定 SDK|锁定 SDK|迁移窗口", s) and re.search(r"必须|强制|务必", s) and not re.search(
        r"不|未|并非|并不是|没有|而非|原文|无需", s
    ):
        print("建议被润色升级为要求: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# 硬性要求（requires dry run）保持强度：提及生产数据的句子须保留需要/必须
found_hard = False
for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"生产数据", s) and re.search(r"需要|必须|须|要求|要先|得先", s):
        found_hard = True
    if re.search(r"生产数据", s) and re.search(r"建议|可以考虑|可选", s) and not re.search(r"不|未|而非|原文", s):
        print("硬性要求被润色弱化为建议: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)
if not found_hard:
    print("未找到硬性要求的强度锚点（生产数据 + 需要/必须）", file=sys.stderr)
    sys.exit(1)

for a in ("故障转移", "迁移"):
    if a not in body:
        print("正文缺少内容词 %s（疑未翻译或剥离过界）" % a, file=sys.stderr)
        sys.exit(1)

print("建议强度保持通过")
