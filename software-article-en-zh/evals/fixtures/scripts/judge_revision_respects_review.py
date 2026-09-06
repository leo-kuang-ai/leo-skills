#!/usr/bin/env python3
"""修订落实审校意见：may not work 的误译“一定能正常工作”须改为“可能无法/不一定/未必”级弱化；旧误译最多在修正说明中引用一次。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if not re.search(r"可能无法|不一定|未必|可能不|无法正常", text):
    print("修订版未落实审校意见，may not work 处仍是确定性表述", file=sys.stderr)
    sys.exit(1)

# 旧误译出现即需处于修正说明语境（引用、对比、箭头标记），否则视为未修订
EXPLAIN_CTX = re.compile(r"原|误|改|错误|修正|之前|上一版|→|«|»|「|」|『|』|引用")
real_hits = [h for h in (m.start() for m in re.finditer(r"一定能(?:正常)?工作", text))
             if not EXPLAIN_CTX.search(text[max(0, h - 30):h + 40])]
if real_hits:
    ctx = text[max(0, real_hits[0] - 30):real_hits[0] + 40]
    print("旧误译“一定能正常工作”脱离修正说明单独出现 %d 次，疑未修订: …%s…" % (len(real_hits), ctx), file=sys.stderr)
    sys.exit(1)

print("修订落实审校意见通过")
