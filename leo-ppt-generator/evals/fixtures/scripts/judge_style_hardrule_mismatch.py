#!/usr/bin/env python3
# Negation-aware judge for the hard-rule mismatch case (style-hardrule-defense-
# mismatch): an academic-defense deck asking for a flashy cyberpunk look must
# receive a FIRST-TURN risk warning (defense x aggressive/neon family is a
# hard-rule mismatch, per style-recommendation.md "硬规则前置"/"冲突劝阻一次")
# PLUS an academic-family alternative suggestion (real in-library names such
# as 科研答辩风). Complying directly without the warning is a FAIL. The
# "user insists -> respect" clause does not exempt the first warning.
#
# Presence assertion: a risk/mismatch warning word AND an academic alternative
# (concrete in-library academic style names — "学术答辩" alone echoes the user
# prompt, but presence B alone never passes since warning A also gates).
# Violation assertion: an unnegated execution claim ("已按…开始生成") or a
# style-creation claim while still in advise.
# Self-contained on purpose: skill-up runs judges without package context.
import os
import re
import sys

# First-turn risk warning semantics. None of these appear in the user prompt.
WARN_PATTERNS = [
    r"不建议", r"风险", r"错配", r"不适合", r"慎重", r"削弱", r"惯例",
    r"硬规则", r"排除", r"避开", r"更稳妥", r"答辩场合.{0,12}(?:偏|偏重|要)",
    r"拿不准", r"欠严肃", r"不严肃",
]

# Real in-library academic/defense style names plus family words.
ACADEMIC_ALTERNATIVES = (
    "科研答辩风", "学术论文答辩风", "学术期刊风", "学术会议风", "毕业答辩风",
    "课题申请风", "深蓝菱形答辩风", "医学手稿答辩风", "学术答辩",
    "学术系", "学术家族", "学术五拍", "稳重商务风", "清爽专业风",
    # A de-scoped compromise of the requested style (keep-neon-but-restrain)
    # is a legitimate first-offer alternative per the one-shot warning contract.
    "收敛", "折中", "点缀", "高对比浅色", "纯白卡片", "更稳",
)

# Execution claims (advise must not start producing the deck).
EXECUTION_RE = re.compile(
    r"(?:已(?:经)?(?:按|用|依)[^。！？!?；;\n]{0,16}"
    r"(?:生成|渲染|注入|套用)|"
    r"已(?:开始|启动)[^。！？!?；;\n]{0,16}"
    r"(?:生成|渲染|制作|出图|样张)|"
    r"(?:马上|立即|这就|现在就)(?:给你?)?(?:渲染|生成|出图|做)|"
    r"正在(?:渲染|生成|制作))")

# Style-creation claims (fabrication). Compound negators only, as in the
# sibling style judges: bare "不/别/无" over-soften via "不过/特别/毫无".
CREATION_RE = re.compile(
    r"(?:已为你创建|已(?:经)?为你?新建|新建了|创建[了出]|"
    r"新建(?:一[个套种])?(?:专属|新|自定义)?风格|"
    r"创建.{0,6}(?:新|专属|自定义)?风格|新增.{0,4}风格)")

CLAIM_SOFTENER_RE = re.compile(
    r"(?:不会|不能|不得|不要|不建议|不推荐|不创建|不新建|并非|而不是|"
    r"没有|禁止|拒绝|尚未|还没|还未|暂不|先不|无法|没法|"
    r"别(?:用|做|创建|新建|急)|无(?:需|须|法)|若|如果|如需|"
    r"需要的话|后续|等你|坚持)")
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


def judge(text: str) -> list[str]:
    """Return violation reasons; empty list means the reply passes."""
    problems = []

    warn_hit = next((p for p in WARN_PATTERNS if re.search(p, text)), None)
    alt_hit = next((w for w in ACADEMIC_ALTERNATIVES if w in text), None)
    if warn_hit is None:
        problems.append(
            "缺少首次风险提示：未见「风险/不建议/错配/硬规则/答辩惯例」类"
            "答辩×炫系错配警告（直接照办不提示属违约）")
    if alt_hit is None:
        problems.append(
            "缺少学术系替代建议：未见「科研答辩风/学术期刊风/学术系」类"
            "真实在库替代方向")

    for body in sentences(text):
        m = EXECUTION_RE.search(body)
        if m and not claim_softened(body):
            problems.append(
                f"发现未经否定的执行宣称: {body[:60]}"
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
        "healthy-warn-plus-alternative",
        True,
        "interaction_mode: advise\n"
        "学术答辩×赛博朋克这类荧光/高攻击系是硬规则明确排除的组合，风险是"
        "评委觉得欠严肃、削弱内容可信度。建议改用科研答辩风或学术期刊风"
        "这类学术系，稳重可信。你若坚持炫的方向，我提示这一次后会尊重并"
        "记录你的选择依据。本轮只咨询，不执行。",
    ),
    (
        "healthy-negation-aware-warn",
        True,
        "不是不让你炫：答辩惯例排除的是高攻击与复古潮流系；更稳妥的是"
        "毕业答辩风这类学术方向，低饱和、让数据说话。",
    ),
    (
        "fail-direct-compliance-no-warning",
        False,
        "行，赛博朋克很炫，答辩用它没问题，就这么定了。",
    ),
    (
        "fail-warning-without-alternative",
        False,
        "赛博朋克在答辩场合有风险，不太合适，你自己考虑。",
    ),
    (
        "fail-execution-despite-warning",
        False,
        "风险已知悉（答辩×炫系属错配，惯例上会削弱可信度），学术备选还有"
        "科研答辩风；但按你的要求来：已开始按赛博朋克风渲染样张。",
    ),
    (
        "fail-creation-claim",
        False,
        "答辩惯例上赛博朋克系欠稳妥，风险已知悉；学术系更稳，比如科研"
        "答辩风。另外已为你新建赛博朋克答辩专属风格备用。",
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
