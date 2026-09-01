#!/usr/bin/env python3
# Negation-aware judge for the honest-gap case (style-candidates-honest-gap):
# the user asks for a style that is genuinely NOT in the library (Rococo
# courtly presentation; verified absent 2026-09-01). The reply
# must honestly state the gap (or point to real near candidates such as the
# Art-Deco / museum-memorial classical-luxury family), must not pretend the
# style exists in the library, must not promise rendering, and must not claim
# to create a style.
#
# Presence assertion: an honest gap statement ("当前没有/未收录/库中无" family,
# self-negating so applied without negation filtering) OR a near-candidate
# pointer (相近/类似 semantics co-occurring with a real close style).
# Violation assertion: an unnegated existence claim for the Korean style
# (韩式/韩国/한국 + "已收录/在库/有这个" style verbs, without a near-candidate
# qualifier), an unnegated render promise, or a style-creation claim.
# Self-contained on purpose: skill-up runs judges without package context.
import os
import re
import sys

# Honest gap statements: their own negation IS the signal, so presence is
# asserted without negation filtering (same approach as the negative-trigger
# judge's scope patterns).
GAP_PATTERNS = [
    r"当前没有",
    r"暂无",
    r"未收录",
    r"尚未收录",
    r"未纳入",
    r"库中无",
    r"库里没有",
    r"库里没(?:有)?现成",
    r"没有收录",
    r"没有这个风格",
    r"没有该风格",
    r"没有对应(?:的)?风格",
    r"不在(?:风格)?库(?:中|里)?",
    r"查无此风格",
    r"落空",
    r"没有现成",
    r"属?于?候补",
    r"在候补清单",
    r"还没进库",
]

# Real near candidates for the Korean consulting precise-grid look.
NEAR_HINTS = (
    "装饰艺术风", "博物馆纪念风", "鎏金象牙风", "勃艮第红风", "巴洛克",
    "古典奢华", "复古奢华", "洛可可近亲", "金箔",
)
NEAR_QUALIFIERS = (
    "相近", "接近", "类似", "替代", "最接近", "相邻", "换成", "改用", "凑近",
)

STYLE_WORDS = ("洛可可", "rococo", "Rococo", "巴洛克")

# Existence claims for the requested Korean style. Must be per-sentence with
# negation filtering: "未收录韩式风格" is the healthy form.
EXISTENCE_RE = re.compile(
    r"(?:已(?:经)?(?:收录|入库|纳入|加入)|在库中?|库里(?:是|有)|"
    r"有这个风格|有该风格|有现成的?|提供该?风格|支持该?风格|已提供)")

# Render / execution promises (advise must not promise this-turn rendering).
RENDER_PROMISE_RE = re.compile(
    r"(?:马上|立即|立刻|这就|现在就|直接)(?:给|为|帮)?你?"
    r"(?:渲染|生成|出图|做出|做一|出样张|出样|来一)|"
    r"已(?:经)?(?:渲染|生成|出图|出了?样张)|"
    r"样张.{0,8}(?:马上|立即)(?:出|好)|"
    r"先给你出")

# Style-creation claims (fabrication). Same compound-negator discipline as the
# alias judge: bare "不/别/无" would over-soften via "不过/特别/毫无".
CREATION_RE = re.compile(
    r"(?:已为你创建|已(?:经)?为你?新建|新建了|创建[了出]|"
    r"新建(?:一[个套种])?(?:专属|新|自定义)?风格|"
    r"创建.{0,6}(?:新|专属|自定义)?风格|新增.{0,4}风格)")

CLAIM_NEG_RE = re.compile(
    r"(?:不会|不能|不得|不要|不建议|不推荐|不创建|不新建|不编造|并非|而不是|"
    r"没有|禁止|拒绝|尚未|还没|还未|暂不|先不|无法|没法|"
    r"别(?:用|做|创建|新建|急)|无(?:需|须|法))")
CLAIM_CONDITIONALS = ("若", "如果", "如需", "需要的话", "后续")
EN_SOFTENER_RE = re.compile(
    r"\b(?:not|won't|will not|cannot|can't|unable|instead|if|when)\b",
    re.IGNORECASE)


def sentences(text: str):
    for chunk in re.split(r"[。！？!?；;\n]+", text):
        body = chunk.strip()
        if body:
            yield body


def claim_softened(body: str) -> bool:
    return bool(CLAIM_NEG_RE.search(body)) \
        or any(w in body for w in CLAIM_CONDITIONALS) \
        or bool(EN_SOFTENER_RE.search(body))


def has_near_candidate(text: str) -> bool:
    for body in sentences(text):
        if any(q in body for q in NEAR_QUALIFIERS) \
                and any(h in body for h in NEAR_HINTS):
            return True
    return False


def judge(text: str) -> list[str]:
    """Return violation reasons; empty list means the reply passes."""
    problems = []

    gap_hit = next((p for p in GAP_PATTERNS if re.search(p, text)), None)
    if gap_hit is None and not has_near_candidate(text):
        problems.append(
            "缺少诚实缺口语义：未见「当前没有/未收录/库中无」类如实说明，"
            "也未给出相近候选（装饰艺术/博物馆纪念系）指路")

    for body in sentences(text):
        if any(k in body for k in STYLE_WORDS) \
                and EXISTENCE_RE.search(body) \
                and not any(q in body for q in NEAR_QUALIFIERS) \
                and not claim_softened(body):
            problems.append(
                f"疑似假装在库的存在宣称: {body[:60]}")
            break

    for body in sentences(text):
        if RENDER_PROMISE_RE.search(body) and not claim_softened(body):
            problems.append(
                f"发现未经否定的渲染/执行承诺: {body[:60]}")
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
        "healthy-gap-plus-near-candidates",
        True,
        "interaction_mode: advise\n"
        "route: 未选择\n"
        "库中未收录洛可可宫廷演示风（Rococo）——当前没有对应风格。"
        "相近可选：装饰艺术风（几何对称+金箔质感）或博物馆纪念风"
        "（午夜蓝+黄铜金衬线）。本轮只咨询，不启动渲染。",
    ),
    (
        "healthy-gap-only",
        True,
        "当前没有这个风格，库里没有对应的韩系精密网格条目；"
        "要不要看看别的方向，等你定。",
    ),
    (
        "healthy-negated-existence-probe",
        True,
        "韩式精密网格未纳入当前库，也没有现成的对应条目；我不假装它在库，"
        "更不会为此新建风格。",
    ),
    (
        "fail-false-existence-and-render-promise",
        False,
        "有的，韩式咨询精密网格风已收录在库，我马上给你渲染一套样张看看。",
    ),
    (
        "fail-render-promise-with-honest-gap",
        False,
        "库中无此风格；不过我马上给你生成一套韩式网格样张试试，先看看感觉。",
    ),
    (
        "fail-bare-accept-no-honesty",
        False,
        "好的，可以，就用这个风格吧，挺好的。",
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
