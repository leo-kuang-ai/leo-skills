#!/usr/bin/env python3
# δ-M1 builder 冻结字段优先于环境变量：finalize/重建按 run 冻结字段分派，
# 环境变量新值不得改写已建 run 的构建路径。自包含 + 否定感知
# （窗口化否定：只看命中起点前的窗口，"不会影响"类正确否定句不受累）。

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


def require_window_positive(patterns, label):
    if window_positive(patterns) is None:
        fail(f"缺少未被否定的{label}: {patterns}")


def forbid_window_positive(patterns, label):
    hit = window_positive(patterns)
    if hit is not None:
        fail(f"出现不应有的{label}: {hit.group(0)[:60]}")


def require_any(values, label):
    if not any(v in text for v in values):
        fail(f"缺少{label}: {' | '.join(values[:6])}")


# 1. 结论：这次 finalize 仍用 pptx / 对象级 builder（窗口化或直陈否定式）
if window_positive(
    [
        r"(仍|依旧|还是|会|将|继续).{0,12}(用|使用|走|按|是).{0,20}(pptx|对象级|object[- ]?builder)",
        r"(finalize|重建|构建).{0,24}(pptx|对象级)",
    ]
) is None and not any(
    v in text
    for v in ("仍用 pptx", "依旧使用 pptx", "仍然用 pptx", "还是会用 pptx", "仍会使用 pptx", "保持 pptx", "保持对象级", "仍是 pptx", "还是 pptx")
):
    fail("缺少结论：finalize 仍按冻结值使用 pptx/对象级 builder")

# 2. 冻结优先于环境变量（肯定式窗口匹配，或直陈"不影响已建 run"否定式）
# M1.1 扩词（it-94 replay）："不会改变这个已建 run" / "finalize 不会重新解析该环境变量"。
if window_positive(
    [
        r"(冻结|builder|run).{0,24}(优先于?|高于|覆盖|决定).{0,24}(环境变量|LEO_EDITABLE_BUILDER)",
    ]
) is None and not any(
    v in text
    for v in ("不影响已", "不会影响已", "不会改变已", "不会改变这个", "不会重新解析",
              "不改写已", "不受环境变量影响", "不会因环境变量", "无法改变已建", "不能改变已")
):
    fail("缺少冻结优先于环境变量的声明（肯定式或'不影响已建 run'式）")

# 3. 陷阱：不得声明环境变量接管该 run / 这次走 legacy
forbid_window_positive(
    [
        r"(环境变量|LEO_EDITABLE_BUILDER).{0,24}(优先于?|高于|覆盖|接管|改写).{0,24}(冻结|run|字段)",
        r"(这次|此次|这回).{0,24}(finalize|重建|构建|用|走|切到|切回).{0,16}legacy",
        r"(改用|切换到?|变成).{0,8}legacy",
    ],
    "环境变量接管已建 run / 本次走 legacy",
)

# 4. 术语在场
require_any(["builder", "冻结"], "术语 builder/冻结")

print("judge passed")
