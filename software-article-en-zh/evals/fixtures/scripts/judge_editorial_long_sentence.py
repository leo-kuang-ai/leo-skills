#!/usr/bin/env python3
import os
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
has_only_if = any(x in text for x in ("只有", "仅当", "仅在", "仅...才", "只有在"))
has_unless = any(x in text for x in ("除非", "除非是", "除外"))
if has_only_if and has_unless:
    print("PASS: 保留 only if 与 unless 的逻辑关系")
    raise SystemExit(0)
print("FAIL: 未同时保留必要条件与 unless 例外关系")
raise SystemExit(1)
