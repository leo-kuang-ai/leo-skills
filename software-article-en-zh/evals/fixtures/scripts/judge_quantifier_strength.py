#!/usr/bin/env python3
"""量词强度保持：some=一些/部分、many=许多、most=大多数、all=所有，句子内不得向上或向下拉平。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)


def hits(keywords):
    return [s for s in sentences if re.search(keywords, s)]


# some modules：一些/部分/某些；不得放大为 许多/大量
some_hits = hits(r"模块|module")
if not some_hits:
    print("未找到 modules 相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"一些|部分|某些|有些|有的", s) for s in some_hits):
    print("some 未译为“一些/部分/某些”", file=sys.stderr)
    sys.exit(1)
for s in some_hits:
    # 译法对照说明句（含 →/译为/逐项对应）引用各量词原文与译文，不属译文正文
    if re.search(r"→|译为|译作|逐项对应|对应|保真要点", s):
        continue
    if re.search(r"许多|很多|大量|不少", s) and not re.search(r"并非|而不是|不是", s):
        print("some 被放大为“许多/大量”: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# many users：许多/很多/不少；不得放大为 所有/全部
many_hits = hits(r"用户|user")
if not many_hits:
    print("未找到 users 相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"许多|很多|不少|大量|众多", s) for s in many_hits):
    print("many 未译为“许多/很多”", file=sys.stderr)
    sys.exit(1)
for s in many_hits:
    if re.search(r"所有用户|全部用户|每个用户|所有使用者", s) and not re.search(r"并非|不是|并不是", s):
        print("many 被放大为“所有”: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# most deployments：大多数/大部分/多数；不得强化为 几乎全部/所有
most_hits = [s for s in hits(r"部署|deployment") if re.search(r"不受影响|未受影响|没有受到影响|无影响", s)]
if not most_hits:
    print("未找到 deployments unaffected 相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"大多数|大部分|多数|多半", s) for s in most_hits):
    print("most 未译为“大多数/大部分/多数”", file=sys.stderr)
    sys.exit(1)
for s in most_hits:
    if re.search(r"几乎所有|几乎全部|所有部署|全部部署", s) and not re.search(r"并非|不是|并不是", s):
        print("most 被强化为“几乎全部/所有”: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# all critical paths：所有/全部 + 覆盖
all_hits = hits(r"关键路径|critical path")
if not all_hits:
    print("未找到 critical paths 相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"所有|全部|全部都|均|都", s) and re.search(r"覆盖|涵盖", s) for s in all_hits):
    print("all critical paths 未译为“所有/全部…覆盖”", file=sys.stderr)
    sys.exit(1)

print("量词强度分层通过")
