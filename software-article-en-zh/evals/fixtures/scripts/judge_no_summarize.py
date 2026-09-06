#!/usr/bin/env python3
"""完整翻译不摘要：六段内容须保留分散在各段的关键细节锚点，段落数不塌缩，且不出现“以下是摘要”类结构声明。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 源文 1656 字符；英译中密度约 0.3-0.45，完整译文远高于摘要
SOURCE_LEN = 1656
MIN_LEN = 460
if len(text) < MIN_LEN:
    print("输出仅 %d 字符（完整译文下限 %d），疑做了摘要" % (len(text), MIN_LEN), file=sys.stderr)
    sys.exit(1)

# 段落不得塌缩：空行分块后至少 5 个内容块（源文 6 段）；
# 兼容译文以单个换行分段的情况（退化为按行统计长行）
blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
long_lines = [ln for ln in text.splitlines() if len(re.findall(r"[\u4e00-\u9fff]", ln)) >= 25]
if len(blocks) < 5 and len(long_lines) < 5:
    print("按空行分段仅 %d 块、长行 %d 行（源文 6 段），段落被合并或省略" % (len(blocks), len(long_lines)), file=sys.stderr)
    sys.exit(1)

# 各段细节锚点：跨 6 段的 10 个具体细节至少保留 7 个
anchors = [r"214", r"\b31\b|31\s*GB", r"500", r"600", r"0\.5%", r"2,?000",
           r"p99", r"MySQL", r"PostgreSQL", r"CSV"]
hits = sum(1 for a in anchors if re.search(a, text))
if hits < 7:
    print("六段中的具体细节仅保留 %d/10 个（要求 >=7），疑存在漏译或摘要" % hits, file=sys.stderr)
    sys.exit(1)

# 不得以摘要形式交付（句级否定感知：“不是摘要/并非总结”类澄清句豁免）
for s in re.split(r"[。！？；;\n]+", text):
    if re.search(r"(?:以下|这里|如下|这?是).{0,6}(?:摘要|概要|总结)|(?:摘要|概要|总结)(?:如下|了以下)", s) and not re.search(r"不|未|无|而非|并非|免", s):
        print("输出声明以摘要形式交付: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("完整翻译不摘要通过")
