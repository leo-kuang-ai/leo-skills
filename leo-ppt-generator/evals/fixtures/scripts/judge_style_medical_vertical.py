#!/usr/bin/env python3
# Negation-aware judge for the medical-context case (style-medical-vertical-
# density): a hospital department annual-review deck asking for a professional,
# steady medical look must be answered with the medical-health family (any
# real in-library medical style name or the family word), and obviously
# mismatched families (cyberpunk / Y2K chrome / fluorescent / vaporwave and
# other high-aggression families) must NOT be presented as a recommendation
# or candidate. A negated/excluding mention ("医疗语境会排除荧光系") is
# healthy and must not fire.
#
# Presence assertion: a concrete medical-family signal (real style names —
# bare "医学风" would echo the user prompt "医学风格", so only full names or
# the family word count).
# Violation assertion: an unnegated sentence that pairs a mismatched-family
# word with recommendation semantics (推荐/建议/适合/候选/出彩...).
# Self-contained on purpose: skill-up runs judges without package context.
import os
import re
import sys

# Real in-library medical-health signals. None appear verbatim in the user
# prompt ("医院/医学风格/专业稳重" — the substring "医学风" of "医学风格" is
# deliberately excluded to prevent echo passes).
MEDICAL_SIGNALS = (
    "医疗健康", "医疗学术风", "医药发布会风", "健康科普插画风", "医院品牌风",
    "临床试验风", "深蓝灰科研风", "冷蓝斜切医学风", "医学书卷风",
    "医学手稿答辩风", "暖陶土医学风", "深海军蓝医学风",
    "秋叶麦田水彩医学风", "深蓝菱形答辩风", "青蓝水墨医学风",
    "雾感鼠尾草风", "医养同源水墨风", "森林绿临床水彩风",
    "黑白水墨临床风", "医疗系", "医学系", "医疗家族",
)

# Obviously mismatched families for a professional medical context.
MISMATCH_WORDS = (
    "赛博朋克", "赛博", "Y2K", "y2k", "铬金属", "荧光", "蒸汽波", "合成波",
    "霓虹", "多巴胺", "新粗野", "波普", "孟菲斯", "像素复古", "高攻击",
    "迷幻",
)

# Recommendation semantics that turn a mismatch mention into a violation.
REC_RE = re.compile(
    r"(?:推荐|建议|适合|候选|方向|可选|出彩|亮眼|抢眼|吸睛|不错|很配|"
    r"加分|印象深|试试|不如用|换用)")

# Softeners for the mismatch-recommendation check: exclusion phrasing is
# healthy ("排除/避开/不建议/不适合..."). Compound forms only; bare "不"
# stays OUT on purpose because "不适合" already carries it while "不过/特别"
# would over-soften.
MISMATCH_SOFTENER_RE = re.compile(
    r"(?:不会|不能|不得|不要|不建议|不推荐|不适合|不选|不妥|欠|并非|"
    r"而不是|没有|排除|避开|避开不|慎|慎用|别用|禁止|拒绝|若|如果|"
    r"除非|相比)")
EN_SOFTENER_RE = re.compile(
    r"\b(?:not|won't|will not|cannot|can't|unable|instead|if|when)\b",
    re.IGNORECASE)


def sentences(text: str):
    for chunk in re.split(r"[。！？!?；;\n]+", text):
        body = chunk.strip()
        if body:
            yield body


def mismatch_softened(body: str) -> bool:
    return bool(MISMATCH_SOFTENER_RE.search(body)) \
        or bool(EN_SOFTENER_RE.search(body))


def judge(text: str) -> list[str]:
    """Return violation reasons; empty list means the reply passes."""
    problems = []

    medical_hit = next((w for w in MEDICAL_SIGNALS if w in text), None)
    if medical_hit is None:
        problems.append(
            "缺少医疗健康家族推荐：未见任一真实医疗风格名"
            "（医疗学术风/医院品牌风/深蓝灰科研风等）或「医疗健康」家族词")

    for body in sentences(text):
        mismatch = next((w for w in MISMATCH_WORDS if w in body), None)
        if mismatch is not None and REC_RE.search(body) \
                and not mismatch_softened(body):
            problems.append(
                f"发现明显错配家族被当作推荐: {body[:60]}"
                f" (错配词: {mismatch})")
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
        "healthy-medical-recommendation",
        True,
        "interaction_mode: advise\n"
        "医院科室年度总结属医疗健康语境：推荐医疗学术风（临床与科研的严谨、"
        "文献感）或深蓝灰科研风（黑白灰医学底图 + 深蓝灰压色带），专业稳重。"
        "医疗场景的硬规则会排除荧光高对比科技风这类高攻击系。本轮只咨询。",
    ),
    (
        "healthy-negated-mismatch-mention",
        True,
        "不建议赛博朋克/Y2K 这类高攻击系；雾感鼠尾草风低饱和、更合适医院"
        "年度汇报的稳重诉求。",
    ),
    (
        "fail-mismatch-recommended",
        False,
        "来点出彩的：推荐蒸汽波风，粉色渐变会让评委印象深，医院汇报也适用。",
    ),
    (
        "fail-no-medical-family",
        False,
        "用稳重商务风就行，模板都差不多，选个顺眼的。",
    ),
    (
        "fail-mismatch-listed-as-candidate",
        False,
        "医疗语境候选：A 医院品牌风；B Y2K铬金属风（年轻亮眼）。",
    ),
    (
        "fail-cyberpunk-suggestion",
        False,
        "医院年度总结想让人记住，建议用赛博朋克风，很吸睛；"
        "稳妥一点也有临床试验风可选。",
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
