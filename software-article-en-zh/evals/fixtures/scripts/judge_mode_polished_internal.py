#!/usr/bin/env python3
"""显式 polished（内部轻量）：长句可拆，但 only when 阈值条件、otherwise 例外与
数值（0.1%、30 分钟）保真；不得强化为确定性或弱化为建议。不要求五件套。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

m = re.search(
    r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*\**\s*(?:交付说明|交付信息|翻译说明|译注|说明|覆盖范围|保护检查|审校状态|未解决项|未解决事项|术语表|歧义与原文问题|需作者确认)\s*[:：]?.*$",
    text,
)
body = text[: m.start()] if m else text

# 条件保真：只有/仅当…才 + 低于阈值
if not re.search(r"只有|仅当|仅在", body):
    print("缺少 only when 条件锚点", file=sys.stderr)
    sys.exit(1)
if not re.search(r"低于|不超过|小于", body):
    print("缺少阈值方向锚点（低于/不超过）", file=sys.stderr)
    sys.exit(1)

# 例外保真：否则/一旦超阈值 → 暂停 + 记录事件
if not re.search(r"否则|若超过|一旦超过|超出", body):
    print("缺少 otherwise 例外锚点", file=sys.stderr)
    sys.exit(1)
for a in ("暂停", "区域"):
    if a not in body:
        print("缺少内容词 %s" % a, file=sys.stderr)
        sys.exit(1)
if not re.search(r"事件|事故|工单|incident", body):
    print("缺少 incident 内容锚点", file=sys.stderr)
    sys.exit(1)

# 数值守恒：0.1 与 30 在场
for num in ("0.1", "30"):
    if num not in body:
        print("数值 %s 缺失（数字保真失败）" % num, file=sys.stderr)
        sys.exit(1)

# 不强化为确定性（句级否定感知）
for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"一定|保证|必然|绝对", s) and not re.search(r"不|未|无|并非|没有|原文", s):
        print("润色引入确定性表述: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("显式 polished 内部润色通过")
