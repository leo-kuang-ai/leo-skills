#!/usr/bin/env python3
"""may 保留可能性、does not guarantee 保留否定，lock-free 句中"保证"必须带否定词。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

if not re.search(r"延迟|时延", text):
    print("译文缺少 latency 的内容词（延迟/时延）", file=sys.stderr)
    sys.exit(1)

# ① may 的可能性模态保留：可能/或许/也许
if not re.search(r"可能|或许|也许|或能|有可能", text):
    print("may 的可能性模态丢失", file=sys.stderr)
    sys.exit(1)

# ① does not guarantee 的否定保留：不保证/无法保证/不能保证
if not re.search(r"不保证|不确保|无法保证|无法确保|不能保证|不能确保|未能保证", text):
    print("does not guarantee 的否定丢失", file=sys.stderr)
    sys.exit(1)

# ② 句级否定过滤：谈 lock-free 的句子若出现"保证/确保"必须伴随否定词。
# 术语说明/译注句引用原文或解释译法时出现“保证”属健康行为，跳过。
for sentence in sentences:
    if re.search(r"术语|译为|译作|「|」|『|』|liveness|guarantee|→", sentence):
        continue
    if re.search(r"无锁|lock-free|lock free", sentence) and re.search(r"保证|确保", sentence):
        if not re.search(r"不|未|并非|并不|不能|无法|没能|没有", sentence):
            print("lock-free 句中的“保证”缺少否定词: %s" % sentence.strip(), file=sys.stderr)
            sys.exit(1)

# ③ 不得强化为确定性降低延迟
for sentence in sentences:
    if re.search(r"(一定|必定|必然|肯定会|必将|定能|势必).{0,8}(降低|减少|缩短)", sentence) and not re.search(
        r"不|并非|未必|不一定", sentence
    ):
        print("may 被强化为确定性表述: %s" % sentence.strip(), file=sys.stderr)
        sys.exit(1)

print("否定与模态保留通过")
