#!/usr/bin/env python3
"""推测动词弱证据语气：suggest 译“表明/显示/提示”类而非“证明”；appears to confirm 保留“似乎/初步”级弱化。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

if not re.search(r"表明|显示|提示|指向|指出|暗示", text):
    print("suggest 未译作“表明/显示/提示”类弱证据动词（疑被强化为“证明”）", file=sys.stderr)
    sys.exit(1)

if not re.search(r"似乎|看起来|看上去|貌似|表面|初步", text):
    print("appears to confirm 的“似乎/初步”级弱化未保留", file=sys.stderr)
    sys.exit(1)

# 证实/确认表述必须伴随弱化词（句内出现证据相关词时才检查，避免误伤状态说明）
for s in sentences:
    if re.search(r"证实|确认", s) and re.search(r"日志|剖析|画像|性能|分析|泄漏|连接池", s) \
            and not re.search(r"似乎|看起来|看上去|貌似|可能|初步|尚|表面|部分", s):
        print("appears to 的弱化被去掉，证实表述过于确定: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

print("推测动词弱证据语气保留通过")
