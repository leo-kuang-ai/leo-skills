#!/usr/bin/env python3
"""附带术语表（token→令牌、stream→流）：译文按表执行，且输出附带术语处理说明（术语/译名/词表）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if not re.search(r"令牌", text):
    print("术语表要求 token 译作“令牌”，译文中未出现“令牌”", file=sys.stderr)
    sys.exit(1)

if not re.search(r"事件流|审计流|数据流|的流|流中|条流|流式", text):
    print("术语表要求 stream 译作“流”，译文中未见 stream 的“流”译法", file=sys.stderr)
    sys.exit(1)

if not re.search(r"术语|译名|词表", text):
    print("输出缺少术语处理说明（应提及术语表/译名决策）", file=sys.stderr)
    sys.exit(1)

print("术语表沿用与决策披露通过")
