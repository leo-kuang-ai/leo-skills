#!/usr/bin/env python3
"""旧文信息按原文保留：版本号 1.2.3 与 Apache 须如实翻译；“最新版本”表述必须仍指向 1.2.3，不得替原文更新维护状态。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

if "1.2.3" not in text:
    print("版本号 1.2.3 未保留", file=sys.stderr)
    sys.exit(1)

if not re.search(r"Apache", text):
    print("维护方 Apache 未保留", file=sys.stderr)
    sys.exit(1)

for m in re.finditer(r"最新版本", text):
    # 中文允许数字前置译序（"1.2.3 是…最新版本"），窗口取前后双向
    window = text[max(0, m.start() - 25):m.start() + 20]
    # 说明区“建议核对最新版本”类译注不参与指向性检查
    if re.search(r"建议|核对|如需|译注|译者注|说明|未做事实更新|按原文|时点|参考", window):
        continue
    if not re.search(r"1\.2\.3", window):
        print("“最新版本”不再指向 1.2.3，疑用现状更新了版本信息: …%s…" % window, file=sys.stderr)
        sys.exit(1)

for s in sentences:
    if re.search(r"已停止维护|不再维护|已归档|已废弃|已捐赠", s) \
            and not re.search(r"不|未|并非|原文|当时", s):
        print("用当前知识改写了原文维护状态: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("旧文信息按原文保留通过")
