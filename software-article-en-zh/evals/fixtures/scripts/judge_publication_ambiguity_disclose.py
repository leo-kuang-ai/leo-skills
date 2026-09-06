#!/usr/bin/env python3
"""发布型歧义披露：辖域歧义句（all ... did not pass）在 publication 润色语境下必须
披露歧义/邀请作者确认，或译文以部分否定措辞保留歧义；静默译为全称否定即失败。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 10:
    print("缺少中文译文", file=sys.stderr)
    sys.exit(1)

disclosed = bool(
    re.search(
        r"歧义|两种理解|不确定|可能有|或指|两种译|存疑|理解不一|两读|不同理解|若原意|如原文|若原文|也可译|另一种|另解|两种解读|辖域|部分否定|并非全部|并非所有|取舍|本意|实际意图|应译为|也可(表述|译|写作)|想表达|建议对照|否定(范围|作用)|若[^。\n]{0,12}(确认|上下文)|按上下文|请(告知|确认)",
        text,
    )
)

partial_rendering = bool(re.search(r"并非(全部|所有)|部分(测试|集成)|没有全部|未全部", text))

silent_full_negation = bool(
    re.search(r"所有[^。]{0,12}(集成)?测试(都|均|全部)?(未|没有)通过|集成测试(全部|都|均)(未|没有)通过", text)
)

if silent_full_negation and not (disclosed or partial_rendering):
    print("歧义句被静默译为全称否定，未披露歧义", file=sys.stderr)
    sys.exit(1)

if not disclosed and not partial_rendering:
    print("输出未报告歧义也未保留部分否定措辞", file=sys.stderr)
    sys.exit(1)

for a in ("测试", "灰度"):
    if a not in text:
        print("缺少译文内容词 %s" % a, file=sys.stderr)
        sys.exit(1)

print("发布型歧义披露通过")
