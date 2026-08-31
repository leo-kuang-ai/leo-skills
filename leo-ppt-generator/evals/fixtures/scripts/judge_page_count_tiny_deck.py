#!/usr/bin/env python3
# 极小页数卡片处理门 v2:用户要求「做一页 PPT」时,不自动加封面与尾页(不产出 3 页),
# 按字面 1 页交付并附卡片处理说明。
# v2:中文数字/量词入 forbid、"要不要"否定自豁免修复、违规跨逗号可见(全文匹配)。

import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

NEG_TOKEN = re.compile(
    r"没有|不会|不能|不得|无法|禁止|拒绝|尚未|还没|还未|暂不|先不|不再|并非|而不是"
    r"|待确认|等待确认|需先|需经|未经|才能|前提"
    r"|(?<![要需这不])不(?![要需过得断少说到错好比可能用会必宜再仅限同久])"
)


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def _unnegated_hit(pattern, t):
    for m in re.finditer(pattern, t):
        window = t[max(0, m.start() - 4):m.start()]
        if not NEG_TOKEN.search(window):
            return m
    return None


def require_any(values, label):
    if not any(v in text for v in values):
        fail(f"缺少{label}: {' | '.join(values)}")


def forbid_positive(patterns, label):
    for p in patterns:
        m = _unnegated_hit(p, text)
        if m:
            fail(f"出现不应有的{label}: {m.group(0)[:60]}")


# 卡片处理说明:不加结构页,或按卡片/单页交付。否定性表述用裸子串。
require_any(
    [
        "不加", "不自动加", "不另加", "不添加", "未加", "没有加",
        "卡片", "单页", "1 页交付", "一页交付", "按一页交付",
    ],
    "卡片处理说明(不加结构页或按单页交付)",
)

# 不得声明成品 3 页(含中文数字与量词;排除"第3页"类页内引用)。
forbid_positive(
    [
        r"(?<![0-9第其中约])(三|3)\s*(页|张)",
    ],
    "声明成品 3 页",
)

# 不得声明自动补齐结构页(跨逗号可见)。
forbid_positive(
    [
        r"(自动|帮你|为你|我)[^。]{0,10}(加|添加|补|凑)[^。]{0,10}(封面|尾页|结构页|一页封面)",
        r"(会|将)[^。]{0,8}(加|添加|补|凑)[^。]{0,10}(封面|尾页|结构页)",
        r"(做成了?|变成|产出|凑成?)[^。]{0,3}(三|3)[^。]{0,3}(页|张)",
    ],
    "自动加结构页",
)

print("page-count-tiny-deck: pass")
