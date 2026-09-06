#!/usr/bin/env python3
"""显式 faithful：隐喻保留原文意象（房间意象不得被抽象化转写），only then 条件保真，
不引入承诺/确定性表述，不要求五件套（faithful 为轻量输出）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 10:
    print("缺少中文译文", file=sys.stderr)
    sys.exit(1)

# 隐喻意象保留：房间意象在场（clean up your own room 的字面/近字面直译）
if not re.search(r"(打扫|清理|收拾)[^。]{0,8}(自己)?的?(房间|屋子|房子)|(房间|屋子|房子)[^。]{0,10}(打扫|清理|收拾)", text):
    print("隐喻意象疑似被编辑性改写（缺少“打扫/清理自己的房间”类直译意象）", file=sys.stderr)
    sys.exit(1)

# only then 条件保真
if not re.search(r"只有|仅在|之后才|然后再|先[^。]{0,20}(才|再)", text):
    print("缺少 only then 的条件锚点", file=sys.stderr)
    sys.exit(1)

# 内容词
for a in ("废弃", "日志"):
    if a not in text:
        print("缺少内容词 %s（疑未翻译）" % a, file=sys.stderr)
        sys.exit(1)

# 不引入原文没有的承诺（句级否定感知；先剥离说明类元信息区）
m = re.search(
    r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*\**\s*(?:交付说明|交付信息|翻译说明|译注|说明|覆盖范围|保护检查|审校状态|未解决项|未解决事项|术语表|歧义与原文问题|需作者确认)\s*[:：]?.*$",
    text,
)
body = text[: m.start()] if m else text
for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"保证|一定|确保|务必", s) and not re.search(r"不|未|无|并非|没有|原文", s):
        print("直译引入原文没有的承诺类表述: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("显式 faithful 保真直译通过")
