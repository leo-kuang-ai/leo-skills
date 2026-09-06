#!/usr/bin/env python3
"""MDX 显式降级：可译文本译出（延迟/18% 在场）、<Chart>/<Callout 标签原样保留、并出现保留/无法解析/降级类说明。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# ① 可译文本正常翻译
if not re.search(r"延迟|时延", text):
    print("缺少 latency 的内容词（延迟/时延）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"18\s*[%％]", text):
    print("18% 数值丢失", file=sys.stderr)
    sys.exit(1)

# ② MDX 组件标签原样保留
if not re.search(r"<Chart", text):
    print("<Chart 组件标签未原样保留", file=sys.stderr)
    sys.exit(1)
if not re.search(r"<Callout", text):
    print("<Callout 组件标签未原样保留", file=sys.stderr)
    sys.exit(1)

# ③ 显式降级/保留说明
if not re.search(r"保留|原样|无法解析|降级|未翻译|未译|不做翻译|未做翻译|保持不变", text):
    print("未显式说明组件保留/无法解析/降级处理", file=sys.stderr)
    sys.exit(1)

print("MDX 显式降级通过")
