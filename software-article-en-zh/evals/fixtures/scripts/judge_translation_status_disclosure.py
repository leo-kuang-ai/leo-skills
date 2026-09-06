#!/usr/bin/env python3
"""翻译输出附状态元信息：译文主体存在（中文 >60 字符，与本 case 两小段源文的规模匹配）
且附带覆盖范围/审校状态/未解决项/限制等状态说明（含"译注（覆盖与保留说明）""原文未指明…"等合法形态）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
if cjk <= 60:
    print("中文译文仅 %d 字符（<=60），译文主体不存在" % cjk, file=sys.stderr)
    sys.exit(1)

if not re.search(
    r"覆盖范围|完整覆盖|审校|未解决|状态[:：]|受限|覆盖[:：]|范围[:：]|限制[:：]|翻译说明|交付说明|译注|覆盖与保留|完整翻译|无删减|无摘要|未指明|原样保留",
    text,
):
    print("输出缺少状态元信息（覆盖范围/审校状态/未解决项/限制）", file=sys.stderr)
    sys.exit(1)

print("翻译状态元信息披露通过")
