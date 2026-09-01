#!/usr/bin/env python3
# Negation-aware judge for the new-family renderable case (style-new-family-
# renderable): the user asks whether 竹简风 (Chinese-carrier family) and
# 星月夜风 (impressionist-oil-painting family) can be done and what they look
# like. The reply must CONFIRM they are in the library (a real style/family
# name co-occurring with an in-library/capability word in the same sentence —
# both names appear in the user prompt, so a bare echo must not pass) and must
# state the capability honestly without overreach: no "立即出图 / 马上出图 /
# 无需确认" promises and no style-creation claims.
#
# Presence assertion: sentence-level (real name + confirmation word, not
# negated) OR a family-name confirmation; plus a capability statement.
# Violation assertion: an unnegated overreach render promise or a
# style-creation claim.
# Self-contained on purpose: skill-up runs judges without package context.
import os
import re
import sys

# Real in-library names/families for the two asked directions.
REAL_NAMES = (
    "竹简风", "中式书卷风", "宣纸风", "莫奈风", "星月夜风",
    "中式载体", "印象派油画", "印象派",
)
FAMILY_WORDS = ("中式载体", "印象派油画", "印象派家族", "中式载体家族")

# Confirmation words: the real name must co-occur with one of these in the
# SAME sentence (the bare names alone would echo the user prompt).
CONFIRM_RE = re.compile(
    r"(?:在库|已收录|收录|库里|可选|能做|可以做|可渲染|可生成|能生成|"
    r"能实现|可实现|支持|有|可用|做得出来|都是|都在|能出)")

# Capability statements. Negation is checked LOCALLY (chars right before the
# match) rather than sentence-wide: a healthy reply often pairs the capability
# with a negated overreach in the same sentence ("可以渲染，但不会立即出图"),
# and sentence-level filtering would wrongly drop the capability half.
CAPABILITY_RE = re.compile(
    r"(?<![不难暂])(?<!无法)(?<!没法)"
    r"(?:可以(?:做|渲染|生成|实现)|能(?:做|渲染|生成|实现|出)|"
    r"可(?:渲染|生成|实现)|做得了|支持|能实现)")

# Overreach render promises: exaggeration the skill must not make.
OVERREACH_RE = re.compile(
    r"(?:立即出图|马上出图|直接出图|立刻出图|这就出图|"
    r"现在就(?:生成|出图|渲染)|无需(?:确认|样张)|跳过(?:样张|确认)|"
    r"已(?:经)?(?:生成|渲染|出图|出了?样张)|秒出)")

# Style-creation claims (fabrication). Compound negators only, matching the
# sibling style judges: bare "不/别/无" over-soften via "不过/特别/毫无".
CREATION_RE = re.compile(
    r"(?:已为你创建|已(?:经)?为你?新建|新建了|创建[了出]|"
    r"新建(?:一[个套种])?(?:专属|新|自定义)?风格|"
    r"创建.{0,6}(?:新|专属|自定义)?风格|新增.{0,4}风格)")

CLAIM_SOFTENER_RE = re.compile(
    r"(?:不会|不能|不得|不要|不建议|不推荐|不创建|不新建|并非|而不是|"
    r"没有|无|禁止|拒绝|尚未|还没|还未|暂不|先不|无法|没法|"
    r"别(?:用|做|创建|新建|急)|若|如果|如需|需要的话|后续|需先|"
    r"要先|得先|等你)")
# Softer set for the OVERREACH check: "无需" is deliberately absent because
# "无需确认/跳过样张" is itself the violation being asserted, not a softener.
OVERREACH_SOFTENER_RE = re.compile(
    r"(?:不会|不能|不得|不要|并非|而不是|没有|禁止|拒绝|暂不|先不|"
    r"无法|没法|别|若|如果|如需|需要的话|后续|需先|要先|得先|等你|除非)")
EN_SOFTENER_RE = re.compile(
    r"\b(?:not|won't|will not|cannot|can't|unable|instead|if|when)\b",
    re.IGNORECASE)


def sentences(text: str):
    for chunk in re.split(r"[。！？!?；;\n]+", text):
        body = chunk.strip()
        if body:
            yield body


def claim_softened(body: str) -> bool:
    return bool(CLAIM_SOFTENER_RE.search(body)) \
        or bool(EN_SOFTENER_RE.search(body))


def overreach_softened(body: str) -> bool:
    return bool(OVERREACH_SOFTENER_RE.search(body)) \
        or bool(EN_SOFTENER_RE.search(body))


def judge(text: str) -> list[str]:
    """Return violation reasons; empty list means the reply passes."""
    problems = []

    name_confirmed = any(
        (any(n in body for n in REAL_NAMES) and CONFIRM_RE.search(body))
        or any(f in body for f in FAMILY_WORDS)
        for body in sentences(text))
    if not name_confirmed:
        problems.append(
            "缺少在库确认：未见「竹简风/星月夜风/中式载体/印象派」与"
            "「在库/已收录/可以做」同现的确认句")

    capability = any(
        CAPABILITY_RE.search(body) for body in sentences(text))
    if not capability:
        problems.append(
            "缺少能力说明：未见「可以做/可渲染/支持」类未否定能力句")

    for body in sentences(text):
        m = OVERREACH_RE.search(body)
        if m and not overreach_softened(body):
            problems.append(
                f"发现越权渲染承诺: {body[:60]}"
                f" (命中: {m.group(0)[:30]})")
            break

    for body in sentences(text):
        m = CREATION_RE.search(body)
        if m and not claim_softened(body):
            problems.append(
                f"发现未经否定的风格创建宣称: {body[:60]}"
                f" (命中: {m.group(0)[:30]})")
            break
    return problems


def run_on(text: str, label: str, expect_pass: bool) -> bool:
    problems = judge(text)
    ok = (not problems) if expect_pass else bool(problems)
    status = "PASS" if ok else "FAIL"
    detail = "" if not problems else " | " + "; ".join(problems)
    print(f"[self-test] {status} {label}{detail}")
    return ok


SELF_TEST_SAMPLES = [
    (
        "healthy-both-families-confirmed",
        True,
        "interaction_mode: advise\n"
        "两个都在库：竹简风（中式载体家族：简牍条列 + 编绳线 + 朱砂强调）、"
        "星月夜风（印象派油画家族：群青夜空 + 熔金星芒 + 梵高笔触涡旋）。"
        "进入 execute 并过样张确认后即可渲染整套 deck，本轮只咨询不动手。",
    ),
    (
        "healthy-negated-overreach",
        True,
        "可以渲染，但不会立即出图——需要先过内容合同、母版与样张确认。"
        "竹简风与星月夜风均已收录在库。",
    ),
    (
        "fail-cannot-do",
        False,
        "这两个风格库里没有，做不了，换别的吧。",
    ),
    (
        "fail-overreach-promise",
        False,
        "竹简风可以做，马上出图给你看，无需确认，直接整套出完。",
    ),
    (
        "fail-bare-echo-no-confirmation",
        False,
        "可以，都行，你说了算。",
    ),
    (
        "fail-creation-claim",
        False,
        "竹简风在库可以渲染；星月夜那边我已为你新建了一个更暗的专属风格，"
        "同样能做。",
    ),
]


def self_test() -> int:
    results = [run_on(text, label, expect_pass)
               for label, expect_pass, text in SELF_TEST_SAMPLES]
    print(f"[self-test] {sum(results)}/{len(results)} 样本符合预期")
    return 0 if all(results) else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        return self_test()
    text = os.environ.get("EVAL_FINAL_MESSAGE", "")
    if not text.strip():
        print("EVAL_FINAL_MESSAGE 为空", file=sys.stderr)
        return 1
    problems = judge(text)
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
