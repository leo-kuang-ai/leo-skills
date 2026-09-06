#!/usr/bin/env python3
"""不自行补充内容：源文（168 字符、无 advise/recommend/suggest）的输出不得附带“建议/最佳实践”类扩展，篇幅不得超 5 倍。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

# 句级否定感知：出现建议类词必须处于否定或输出契约语境（术语/审校说明等），否则视为自行补充
context_markers = r"不|未|无|仅|译|术语|原文|审校|状态|覆盖|范围|限制|核对|复核|人工|说明|词"
for s in sentences:
    if re.search(r"建议|最佳实践|推荐|请务必|注意需要|记得|别忘了", s) and not re.search(context_markers, s):
        print("译文自行补充了原文没有的建议类内容: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# 篇幅上限只约束译文主体：先剥离输出契约要求的状态元信息区（含行内式“标题：内容”）
body = text
m = re.search(r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*(?:翻译说明|译注|交付说明|覆盖与保留说明|覆盖范围|审校状态|交付信息|状态信息|翻译信息|备注|技术术语表|术语表|术语对照|术语清单|歧义与原文问题|歧义清单|原文问题|未解决事项|需作者确认)\s*[:：]?.*$", text)
if m:
    body = text[: m.start()]
# 篇幅上限：防大段自由发挥（源文 168 字符的 5 倍）
MAX_LEN = 168 * 5
if len(body) > MAX_LEN:
    print("译文主体 %d 字符超过上限 %d，疑大幅自由发挥" % (len(body), MAX_LEN), file=sys.stderr)
    sys.exit(1)

if "batch_size" not in text:
    print("源文核心配置项 batch_size 缺失", file=sys.stderr)
    sys.exit(1)

print("不自行补充内容通过")
