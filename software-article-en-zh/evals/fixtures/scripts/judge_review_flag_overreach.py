#!/usr/bin/env python3
"""审校识别越界：译文含原文没有的“保证提升 300%/彻底消除所有问题”（编辑越界）与
“may 引入旧读”的弱化语气须被指出；技术与编辑复核分开记录；审校结论不得为发布就绪。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 10:
    print("缺少中文审校输出", file=sys.stderr)
    sys.exit(1)

# ① 标记编辑越界：300% / 彻底消除 被指为原文没有的新增
flagged_added = re.search(
    r"(原文(中)?没有|并无|未提及|新增|越界|无中生有|擅自添加|杜撰|不是原文|缺出处|无依据)[^。\n]{0,60}|(300%|300 ?%|彻底|所有)[^。\n]{0,40}(原文|没有|新增|越界|无依据|不存在)",
    text,
)
if not flagged_added:
    print("未标记编辑越界（保证提升 300%/彻底消除所有问题为原文没有的新增）", file=sys.stderr)
    sys.exit(1)

# ② 语义强化被识别：保证/彻底 一类表述被指为强化
if not re.search(r"强化|拔高|过强|绝对化|夸大|升级(了)?(语气|强度)|越权|过界", text):
    print("未识别语义强化（保证/彻底为原文没有的确定性）", file=sys.stderr)
    sys.exit(1)

# ③ 保留原文正确部分：5 秒旧读的弱化译法可被确认正确（审校应对照原文逐块）
if not re.search(r"旧读|过期读|脏读|stale read|可能|最长 5 秒|5 秒", text):
    print("未对照原文复核 5 秒旧读句", file=sys.stderr)
    sys.exit(1)

# ④ 技术复核与编辑复核分开记录
if not re.search(r"技术复核|technical_review|技术审校", text):
    print("缺少技术复核记录", file=sys.stderr)
    sys.exit(1)
if not re.search(r"编辑复核|editorial_review|编辑审校", text):
    print("缺少编辑复核记录", file=sys.stderr)
    sys.exit(1)

# ⑤ 结论不得为发布就绪（合取判定：越界存在即不可发布）
for s in re.split(r"[。！？；;\n]+", text):
    if re.search(r"发布就绪|可以发布|达到发布", s) and not re.search(r"不|未|尚|达不|不满足|修改", s):
        print("存在越界却给出发布就绪结论: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("审校识别越界通过")
