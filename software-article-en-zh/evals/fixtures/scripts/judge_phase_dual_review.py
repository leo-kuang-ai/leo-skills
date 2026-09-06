#!/usr/bin/env python3
"""双轨复核披露：technical_review 与 editorial_review 分开记录（两个锚点都必须在场），
给出发布判定（发布就绪/合取类表述），且译文内容保真（时间/天数/行为不变）。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 20:
    print("缺少中文译文", file=sys.stderr)
    sys.exit(1)

# ① 技术复核与编辑复核分开记录
if not re.search(r"技术复核|technical_review|技术审校|技术评审", text):
    print("缺少 technical_review 记录", file=sys.stderr)
    sys.exit(1)
if not re.search(r"编辑复核|editorial_review|编辑审校|编辑评审", text):
    print("缺少 editorial_review 记录", file=sys.stderr)
    sys.exit(1)

# ② 发布判定披露（合取语义的结论性表述）
if not re.search(r"发布就绪|发布判定|合取|可以发布|达到发布|审校结论|复核结论", text):
    print("缺少发布判定/审校结论披露", file=sys.stderr)
    sys.exit(1)

# ③ 译文保真：时间、天数、行为
for a in ("02:00", "90"):
    if a not in text:
        print("数值锚点 %s 缺失" % a, file=sys.stderr)
        sys.exit(1)
for a in ("快照", "冷存储", "删除"):
    if a not in text:
        print("缺少内容词 %s" % a, file=sys.stderr)
        sys.exit(1)
if not re.search(r"延长|扩展|调整", text):
    print("缺少 extend retention 语义锚点", file=sys.stderr)
    sys.exit(1)

print("双轨复核披露通过")
