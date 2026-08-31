#!/usr/bin/env python3
# 断言标题判据（advise）：金字塔模式下「市场分析」这类话题词标题应被判不合格，
# 回复须给出「标题须为完整句断言」的肯定表述，且不得无条件放行。

import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

QUOTE_SPAN = re.compile(r"(「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\")")

NEGATORS = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "需先", "需经", "未经",
    "才能", "前提", "没有", "无", "而不是", "并非",
)


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def _dequote_keep(sentence):
    # 只剥引号本身、保留内文：健康响应常把「市场分析」等关键词放进引号，
    # 整段剥离会让点名句失配（否定感知不应误伤正确点名）。
    return QUOTE_SPAN.sub(lambda m: m.group(0)[1:-1], sentence)


def positive(patterns, verdict_patterns=()):
    for sentence in re.split(r"[。！？\n]+", text):
        bodies = (QUOTE_SPAN.sub("", sentence), _dequote_keep(sentence))
        for body in bodies:
            if any(re.search(p, body) for p in patterns) and not any(
                v in body for v in NEGATORS
            ):
                return True
        # 判定句式豁免：模式自身编码了不可反向的判定方向（「X 是主题，不是结论」
        # 只可能是合格判定，反向响应会说「是合格的结论标题」），免句级否定词否决。
        for body in bodies:
            if any(re.search(p, body) for p in verdict_patterns):
                return True
    return False


# 话题词标题判定的结构化合取：四次实测掷骰证明逐词追赶不可收敛（标签词与
# 「不是结论」的相对位置每次重排），改为判定不变量本身——
# ①点名在场 ②存在被肯定（非「不是X」）的话题类定性 ③存在结论缺失判定。
LABEL_WORDS = r"(话题|主题|标签|分类名|名词短语)"
LACK_VERDICT = re.compile(r"不是结论|缺结论|没有结论|缺少结论|只有骨架没有结论")


def topic_word_verdict(dequoted):
    if "市场分析" not in dequoted:
        return False
    has_label = re.search(r"(?<!不)(?<!并非)是[^。]{0,4}" + LABEL_WORDS, dequoted) or re.search(
        r"这是[^。]{0,4}" + LABEL_WORDS, dequoted
    )
    return bool(has_label and LACK_VERDICT.search(dequoted))


if not positive(
    [
        r"标题[^。]{0,20}(完整句|断言|结论|判断句|观点句|主张句|中心思想)",
        r"(完整句|断言句|结论句|判断句)[^。]{0,12}标题",
        r"标题[^。]{0,16}(是|应为|须是|写成).{0,8}(结论|断言|判断)",
    ]
):
    fail("缺少「标题须为完整句断言」的肯定判据表述")

if not (
    positive(
        [
            r"市场分析[^。]{0,20}(话题词|标签|不是结论|主题词|不合格|改写)",
            r"(话题词|主题词)[^。]{0,20}(改写|补全|扩成|升格)",
        ],
        verdict_patterns=(
            # 已实证的合格判定句形家族（反向响应只会说「是合格的结论标题」，不会命中）：
            # ① 「市场分析」…是话题/主题/标签…，不是结论
            r"市场分析[^。]{0,24}(话题词?|主题|标签|分类名)[^。]{0,8}(不是结论|不承载)",
            # ② 标题不是结论，是话题标签（点名在邻近句，如「「市场分析」是分类名」）
            r"标题[^。]{0,8}不是结论[^。]{0,8}是(话题|主题|分类|标签)",
        ),
    )
    or topic_word_verdict(_dequote_keep(text))
):
    fail("未点名「市场分析」属话题词标题并给出改写方向")

print("assertion-headline: ok")
