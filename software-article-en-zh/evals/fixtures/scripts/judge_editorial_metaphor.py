#!/usr/bin/env python3
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
# Evaluate the delivered translation, not notes that explicitly discuss rejected literal forms.
# 保真对照/忠实初译 sections legitimately restate the literal draft for verification.
body = text
for marker in ("交付说明", "审校说明", "审校记录", "保真对照", "忠实初译", "初译对照", "faithful 初译", "翻译说明", "技术术语表", "术语表", "歧义与原文问题", "未解决事项"):
    body = body.split(marker, 1)[0]
# Literal-form check ignores quoted spans: analysis sections legitimately mention the rejected
# literal translation inside quotes when explaining the chosen transcription.
body_unquoted = re.sub(r"[「『\"“”'‘’][^」』\"“”‘’]*[」』\"“”‘’]", "", body)
has_cleanup = any(x in body for x in ("清理", "整理", "梳理", "重新整理"))
has_audit = any(x in body for x in ("审计", "审查"))
literal = "打扫你的房子" in body_unquoted or "打扫房子" in body_unquoted
if has_cleanup and has_audit and not literal:
    print("PASS: 隐喻已上下文化且保留审计行动")
    raise SystemExit(0)
print("FAIL: 隐喻或审计行动未被准确转写")
raise SystemExit(1)
