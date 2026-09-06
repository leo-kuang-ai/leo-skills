#!/usr/bin/env python3
"""默认模式翻转：无模式词的翻译请求默认按 publication 双层交付——五件套组件在场，
译文主体保真（排空→only after 条件与否定保留），缺失任一组件即默认仍为轻量交付。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 20:
    print("缺少中文译文主体", file=sys.stderr)
    sys.exit(1)

parts = [
    (r"翻译说明|译文说明|术语与处理说明|处理说明|翻译注记|译注", "翻译说明"),
    (r"术语表|术语对照|术语清单|术语说明|术语与\S{0,6}说明", "技术术语表"),
    (r"歧义与原文问题|歧义|原文问题|源文问题", "歧义与原文问题清单"),
    (r"未解决(事项|项|问题)|需作者确认|待确认", "未解决事项/需作者确认"),
]
missing = [label for pat, label in parts if not re.search(pat, text)]
if missing:
    print("默认请求未按 publication 双层交付，缺少组件：%s" % "、".join(missing), file=sys.stderr)
    sys.exit(1)

# 译文主体保真：only after 条件与否定保留
if not re.search(r"只有|仅在|之后才|完成后才", text):
    print("译文缺少 only after 的条件锚点", file=sys.stderr)
    sys.exit(1)
if not re.search(r"不会丢失|不丢失|没有(任何)?任务(会)?丢失|任务不(会)?丢失|不丢任务", text):
    print("译文缺少 no task is lost 的否定锚点", file=sys.stderr)
    sys.exit(1)

for a in ("调度器",):
    if a not in text:
        print("译文主体缺少内容词 %s（疑未翻译）" % a, file=sys.stderr)
        sys.exit(1)
if not re.search(r"排空|清空", text):
    print("译文主体缺少内容词 排空/清空（drain，疑未翻译）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"重载|重新加载", text):
    print("译文主体缺少内容词 重载/重新加载（reload，疑未翻译）", file=sys.stderr)
    sys.exit(1)

print("默认模式双层交付通过")
