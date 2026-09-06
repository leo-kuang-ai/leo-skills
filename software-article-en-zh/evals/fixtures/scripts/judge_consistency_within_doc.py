#!/usr/bin/env python3
"""同篇一致性：三段 idempotent 统一译作“幂等”，不得混入“幂次/等幂”等同义变体。
术语表/翻译说明等元信息区可能并列列出备选译名，先剥离后再做变体检查。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 剥离五件套元信息区（首个说明类标题行或行内式“标题：内容”行之后不参与变体检查）
m = re.search(
    r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*(?:交付说明|交付信息|翻译说明|译注|说明|覆盖范围|保护检查|审校状态|未解决项|未解决事项|技术术语表|术语表|术语对照|术语清单|歧义与原文问题|歧义清单|原文问题|需作者确认)\s*[:：]?.*$",
    text,
)
body = text[: m.start()] if m else text

count = len(re.findall(r"幂等", body))
if count < 2:
    print("“幂等”仅出现 %d 次（三处 idempotent 应统一译名）" % count, file=sys.stderr)
    sys.exit(1)

variant = re.search(r"幂次|等幂", body)
if variant:
    print("同篇内出现 idempotent 的变体译名: %s" % variant.group(0), file=sys.stderr)
    sys.exit(1)

print("同篇术语一致通过")
