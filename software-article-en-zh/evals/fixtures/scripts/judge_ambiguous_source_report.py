#!/usr/bin/env python3
"""歧义句报告：结构歧义句（quickly 修饰 deploying 还是 breaks）须给出译法的同时报告歧义，仅译不报即失败。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 10:
    print("缺少中文译文（未给出一种译法）", file=sys.stderr)
    sys.exit(1)

if not re.search(
    r"歧义|两种理解|不确定|可能有|或指|两种译|存疑|理解不一|两读|不同理解|若原意|如原文|若原文|也可译|另一种|另一种理解|另解|两种解读|辖域|修饰(范围|对象)|修饰[^。，]{0,8}不明确|修饰[^。\n]{0,12}(还是|或是)|取舍|本意|实际意图|改用|应改为|应译为|也可(表述|译|写作)|想表达|建议对照|否定(范围|作用)|范围错译|部分否定|(含义|意思|译法)[^。\n]{0,6}不同|若[^。\n]{0,12}(确认|上下文)|按上下文|请(告知|确认)",
    text,
) and not re.search(r"存在[^。\n]{0,12}(两种|歧义)", text):
    print("源文为辖域歧义句，输出未报告歧义即擅自选定一种理解", file=sys.stderr)
    sys.exit(1)

# 译文主体在场（给出了一种译法）
if not re.search(r"测试", text):
    print("缺少译文主体内容词（测试）", file=sys.stderr)
    sys.exit(1)

print("歧义句报告通过")
