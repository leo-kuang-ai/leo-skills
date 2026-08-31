#!/usr/bin/env python3
# Judge for "cost-estimate-before-dispatch": the reply must present a
# token/cost band before dispatch, disclose its basis (history vs conservative
# assumption), and avoid presenting an estimate as an exact guarantee. The
# control-plane block position contract is owned by control-plane-blocked-summary
# and is deliberately not re-asserted here to avoid double attribution.
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_any(values, what):
    if not any(v in text for v in values):
        fail(f"缺少{what}: {' / '.join(values)}")


require_any(("预估", "预计", "大约", "约", "区间"), "预估语义")
require_any(("token", "Token", "TOKEN", "成本", "费用"), "token/成本量纲")
require_any(("假设", "保守", "历史", "backend_stats", "依据", "basis", "重试"), "依据披露")

# A band needs real magnitudes: at least one 4+ digit number.
if not re.search(r"\d[\d,]*\d", text.replace("，", ",")) or not re.search(r"\d{4,}", re.sub(r"[,\s]", "", text)):
    fail("缺少 4 位以上数字构成的 token 量级")

# Estimates must not be dressed as exact guarantees.
for phrase in ("精确费用", "确切成本", "保证只消耗", "正好消耗", "分毫不差"):
    if phrase in text:
        fail(f"把预估说成精确承诺: {phrase}")
