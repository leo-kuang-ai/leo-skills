#!/usr/bin/env python3
"""艰深长句不漏译：嵌套从句中 monotonic、happens-before、linearizable 三个技术要素须全部译出（原词或标准译名）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 30:
    print("缺少中文译文主体", file=sys.stderr)
    sys.exit(1)

# 简单段落的锚点：30 秒落后告警
if not re.search(r"30\s*秒|30秒", text) and not re.search(r"超过\s*30|多于\s*30|落后", text):
    print("首段（30 秒复制延迟告警）疑未翻译", file=sys.stderr)
    sys.exit(1)

if not re.search(r"单调|monotonic", text, re.IGNORECASE):
    print("monotonic (logical clock) 要素缺失", file=sys.stderr)
    sys.exit(1)

if not re.search(r"happens[\s_-]{0,2}before", text, re.IGNORECASE):
    print("happens-before 要素缺失", file=sys.stderr)
    sys.exit(1)

if not re.search(r"线性一致|可线性化|linearizable", text, re.IGNORECASE):
    print("linearizable 要素缺失", file=sys.stderr)
    sys.exit(1)

print("艰深长句核心要素保留通过")
