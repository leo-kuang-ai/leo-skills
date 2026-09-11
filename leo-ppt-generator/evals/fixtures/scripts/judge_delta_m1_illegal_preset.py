#!/usr/bin/env python3
# δ-M1 非法 preset 守卫：object builder 对非法 preset 在 build 期清晰失败、
# 不产出损坏包；不得声明照常出包或自动纠正。自包含 + 否定感知（窗口化）。

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


# 1. build 期失败结论（肯定式窗口匹配；"不会静默"类否定式由第 2 步兜住）
# M1.1 扩形（it-94 replay）："校验会直接 fail 该页" / "在渲染环节炸出来" /
# "阻止进入 build" 是等价的 fails-closed 结论措辞。
if window_positive(
    [
        r"(build|构建|编译).{0,16}(期|时|阶段).{0,20}(失败|报错|抛|ValueError|拒绝)",
        r"ValueError",
        r"(非法|无效|不支持).{0,16}(preset|值|token).{0,36}(失败|报错|拒绝|抛|报错退出)",
        r"(会|将|直接).{0,12}(失败|报错|抛出?错误|拒绝构建|\bfail\b|炸出来)",
        r"(校验|validation|验证|渲染环节).{0,16}(fail|拦截|阻止|炸出来)",
        r"阻止进入 ?build",
    ]
) is None:
    fail("缺少 build 期失败/报错结论")

# 2. 不产出损坏包 / record 无法通过（直陈否定式，正确答案的必然形态）
require_any(
    [
        "不会产出", "不会生成", "不会写", "不产出", "不会落盘",
        "过不了", "无法通过", "会被拒", "无法 record", "不能 record",
        "损坏的包", "损坏的 page.pptx", "坏包", "打不开的文件",
        "阻止进入 build",
    ],
    "不产出损坏包/record 被拒",
)

# 3. 陷阱：不得声明照常出包或自动纠正（窗口化禁止）
# M1.1: bare "build" dropped from the object alternation — it swallowed the
# healthy blocked form "直接 fail 该页，阻止进入 build" (failure conclusion,
# added to check 1). Ship/produce/record objects keep the trap's bite.
# 校准收紧（it-126 replay）：如实警告"legacy 路径静默出坏包"与检查 2 的
# "坏包"结论互为印证，不得误拦；只拦接受性建议与自动纠正声明。
forbid_window_positive(
    [
        r"(可以|没问题|放心|建议直接|那就直接).{0,16}(record|出包|交付|收下|采用|照常)",
        r"(照常|正常).{0,20}(出包|产出|生成).{0,16}(去 ?record|后 record|直接用|交付)",
        r"(自动|会被|帮你|帮你把).{0,16}(纠正|修正|改写|转换|映射成?|当成|替换成).{0,24}(roundRect|合法|正确)",
    ],
    "照常出包/自动纠正声明",
)

# 4. 术语在场
if "preset" not in text.lower():
    fail("缺少术语: preset")
require_any(["失败", "报错", "ValueError", "拒绝", "非法", "无效", "不支持"], "失败术语")

print("judge passed")
