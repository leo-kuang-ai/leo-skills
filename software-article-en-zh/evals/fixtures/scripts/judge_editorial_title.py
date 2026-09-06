#!/usr/bin/env python3
import os
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
has_product = "GPT-6 Astra" in text
has_skills = any(x in text for x in ("Skill", "skills", "技能"))
has_prompts = any(x in text for x in ("提示词", "提示"))
if has_product and has_skills and has_prompts:
    print("PASS: 标题保留产品名、skills 主题和 prompts 主题")
    raise SystemExit(0)
print("FAIL: 标题未完整保留主题和产品名")
raise SystemExit(1)
