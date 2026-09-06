#!/usr/bin/env python3
"""倍数语义：3x/twice/in half/order of magnitude 各自译出，比较方向不得颠倒（新编译器不得变慢）。"""
import os
import re
import sys
import unicodedata

text = unicodedata.normalize("NFKC", os.environ.get("EVAL_FINAL_MESSAGE", ""))
sentences = re.split(r"[。！？；;\n]+", text)

# ① 3x faster：倍数在场
if not re.search(r"3\s*倍|三倍", text):
    print("3x faster 的倍数语义丢失（3 倍/三倍）", file=sys.stderr)
    sys.exit(1)

# ② twice as fast：两倍/2倍/快一倍/加倍
if not re.search(r"两倍|二倍|2\s*倍|快了?一倍|加倍|翻倍", text):
    print("twice as fast 的倍数语义丢失（两倍/快一倍）", file=sys.stderr)
    sys.exit(1)

# ③ in half：减半/一半
if not re.search(r"减半|一半|缩短一半|减掉一半| halve", text):
    print("cuts in half 的减半语义丢失", file=sys.stderr)
    sys.exit(1)

# ④ an order of magnitude：数量级
if not re.search(r"数量级", text):
    print("an order of magnitude 的数量级语义丢失", file=sys.stderr)
    sys.exit(1)

# ⑤ 方向禁令（句级否定感知）：新编译器/新版本不得译成更慢
for s in sentences:
    if re.search(r"(编译器|新版本|新版)[^。\n]{0,30}(更?慢|变慢|慢了)", s) and not re.search(r"不|未|并非|而不是|不会", s):
        print("比较方向颠倒（新编译器被译成更慢）: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# ⑥ 内容词在场
for anchor in ("编译", "构建", "测试"):
    if anchor not in text:
        print("缺少内容词 %s" % anchor, file=sys.stderr)
        sys.exit(1)

print("倍数与减半语义通过")
