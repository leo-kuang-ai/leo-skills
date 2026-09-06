#!/usr/bin/env python3
"""MUST NOT/SHOULD/MAY 三级规范强度各自保持：禁止、建议（不升为必须）、许可（不升为应该/必须）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)


def find(keyword_pattern):
    hits = [s for s in sentences if re.search(keyword_pattern, s)]
    return hits


def strengthened_by(sentence, strong_words):
    # 句内出现强化词且没有否定/对比语境（并非必须 / 而非必须）才算拉平
    if re.search(strong_words, sentence) and not re.search(r"并非|而不是|而非|不是|不强制|无须|无需", sentence):
        return True
    return False


# MUST NOT 句：写 replica/snapshot 的句子必须是禁止性表述
must_not_hits = find(r"副本|快照|replica|snapshot")
if not must_not_hits:
    print("未找到 replica/snapshot 相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"不得|禁止|必须不|不许|不能够?写入", s) for s in must_not_hits):
    print("MUST NOT 未译为禁止性表述（不得/禁止/必须不）", file=sys.stderr)
    sys.exit(1)

# SHOULD 句：checksum 句应为应该/应当/建议，不得强化为必须
should_hits = find(r"校验和|校验码|checksum")
if not should_hits:
    print("未找到 checksum 相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"应该|应当|建议|宜|应(?![对答变用急])", s) for s in should_hits):
    print("SHOULD 未译为应该/应当/建议类表述", file=sys.stderr)
    sys.exit(1)
for s in should_hits:
    if strengthened_by(s, r"必须|务必|一定要"):
        print("SHOULD 被强化为必须: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# MAY 句：reuse connection 句应为可以/允许类许可，不得强化为应该/必须
may_hits = find(r"复用|重用|连接")
if not may_hits:
    print("未找到 connection/reuse 相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"可以|允许|均可|得以|可复用|可重用|可再次使用", s) for s in may_hits):
    print("MAY 未译为可以/允许类许可表述", file=sys.stderr)
    sys.exit(1)
for s in may_hits:
    if strengthened_by(s, r"必须|应该|应当|须要|务须"):
        print("MAY 被强化为应该/必须: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("RFC 2119 模态强度分层通过")
