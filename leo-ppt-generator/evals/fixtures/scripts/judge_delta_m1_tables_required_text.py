#!/usr/bin/env python3
# δ-M1 tables 对象面文本校验：tables[] 单元格文本进入 all_text/required_text
# 逐字校验，"表格可免校验"的说法必须被驳回。自包含 + 否定感知（窗口化）。

import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

BEFORE_NEGATORS = ("不", "没", "无法", "禁止", "并非", "而不是")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def _window_clean(match):
    return not any(v in text[max(0, match.start() - 10) : match.start()] for v in BEFORE_NEGATORS)


def window_positive(patterns):
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if _window_clean(match):
                return match
    return None


def forbid_window_positive(patterns, label):
    hit = window_positive(patterns)
    if hit is not None:
        fail(f"出现不应有的{label}: {hit.group(0)[:60]}")


def require_any(values, label):
    if not any(v in text for v in values):
        fail(f"缺少{label}: {' | '.join(values[:6])}")


# 1. 同事说法必须被驳回（直陈式判断词）
require_any(
    ["不对", "不成立", "有误", "不正确", "错的", "说错了", "不对外"],
    "驳回同事说法",
)

# 2. 表格文本在校验覆盖内（肯定式窗口匹配或直陈否定式）
if window_positive(
    [
        r"(表格|tables|单元格).{0,30}(校验|覆盖|逐字|进).{0,30}(required_text|text_inventory|all_text|校验|覆盖)",
        r"(required_text|text_inventory|all_text).{0,30}(覆盖|包含|校验).{0,30}(表格|tables|单元格|数字)",
        r"(表格|tables|单元格).{0,20}(同样|也|一样).{0,16}(校验|覆盖|逐字)",
    ]
) is None and not any(
    v in text for v in ("同样覆盖表格", "覆盖表格", "也覆盖表格", "表格文本也", "单元格文本也", "进入 all_text", "进 required_text", "进校验", "纳入校验")
):
    fail("缺少表格文本进校验的结论")

# 3. 登记动作：为表格单元格登记 required_text / 文本清单
if window_positive(
    [
        r"(要|需要|必须|应|建议|得).{0,24}(登记|写进|加入|放进|覆盖|补).{0,36}(required_text|text_inventory)",
        r"(required_text|text_inventory).{0,24}(要|需要|必须|应).{0,20}(含|包含|覆盖|登记).{0,24}(表格|tables|单元格|数字)",
    ]
) is None:
    fail("缺少登记 required_text/text_inventory 的动作")

# 4. 陷阱：不得声明表格文本免于校验（窗口化禁止，未被否定的声明）
forbid_window_positive(
    [
        r"(表格|tables|单元格).{0,30}(可以|可|能|免|跳过|豁免).{0,16}(不进|免|跳过|豁免|省略)",
        r"(表格|tables|单元格).{0,30}(不受|免于).{0,16}(校验|required_text|逐字)",
        r"(validation|校验).{0,24}(不管|不校验|不覆盖|不会管).{0,24}(表格|tables|单元格)",
    ],
    "表格免校验声明",
)

# 5. 术语在场
if not (("tables" in text.lower()) or ("表格" in text)):
    fail("缺少术语: tables/表格")
require_any(["required_text", "text_inventory", "校验"], "术语 required_text/text_inventory/校验")

print("judge passed")
