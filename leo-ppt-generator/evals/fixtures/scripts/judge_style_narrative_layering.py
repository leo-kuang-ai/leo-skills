#!/usr/bin/env python3
# Negation-aware judge for the narrative-layering case (narrative-pitch-
# layering): an advise-mode "how do I organize a 12-page funding pitch" question
# must surface the NARRATIVE layer semantics (融资路演 narrative skeleton:
# why-now / page order / the ask ...) AND mention the argument-mode pairing
# (论证模式 axis: 故事弧 / 结论先行金字塔 / 怎么证), without starting any Route
# and without adding a new confirmation gate.
#
# Presence assertion: one narrative-layer word beyond a bare echo of the user
# wording, plus one argument-mode pairing word.
# Violation assertion: unnegated Route startup / gate-adding claims, adapted
# from the negative-trigger judge. Control-plane field lines (route:/status:/
# interaction_mode:/...) are metadata per the advise contract and are exempt:
# in advise mode listing `route: generate` as a candidate is REQUIRED
# behavior, so only verb-paired execution/gate commitments in prose count.
# Self-contained on purpose: skill-up runs judges without package context.
import os
import re
import sys

# Narrative-layer semantics (page-order skeleton, beats, pitch-specific
# vocabulary). None of these appear verbatim in the user prompt.
NARRATIVE_WORDS = (
    "叙事", "页序", "骨架", "节位", "故事弧", "为什么是现在", "Why now",
    "why now", "The ask", "要价", "增长牵引", "尽调", "轮次", "主线",
    "一页一拍", "投资人故事", "附录", "权重", "节奏",
)

# Argument-mode pairing words ("怎么证" axis orthogonal to the narrative).
PAIRING_WORDS = (
    "论证模式", "论证形态", "怎么证", "配对", "结论先行金字塔", "故事弧",
    "学术五拍", "中性简报", "情绪弧线", "金字噬", "论证轴",
    # "论证配置" table-column phrasing and arc wording used by healthy replies.
    "论证配置", "论证骨架", "弧线", "张力", "释放", "定性", "定量锚点",
)

# Control-plane field lines are contract metadata, not prose commitments.
CONTROL_FIELD_RE = re.compile(
    r"^\s*(?:interaction_mode|route|status|reason_code|execution_eligibility|"
    r"next_action)\s*[:：]", re.IGNORECASE)

# Route startup / new-gate claims. Bare `route: <name>` is deliberately NOT a
# pattern here (advise lists candidate routes); verbs are paired with objects
# so advice mentions ("要做 deck 可以走 generate") do not falsely fire.
STARTUP_PATTERNS = [
    r"(?:已|正在|已经)(?:进入|启动|开始|执行|运行|调用|初始化).{0,24}"
    r"(?:route|路线|generate|direct-editable|upgrade|生成|重建|升级|"
    r"preflight|provider|bootstrap|runtime|backend|样张|流程|大纲|母版)",
    r"(?:进入|启动|执行)(?:了)?.{0,10}[Rr]oute.{0,6}[:：]?\s*[\"'`]?"
    r"(?:generate|direct-editable|upgrade)",
    r"(?:接下来|下一步|随后)(?:我)?(?:会|将|先|需要?).{0,32}"
    r"(?:确认|询问|收集).{0,32}"
    r"(?:受众|目标|页数|大纲|样张|风格|backend|数据分级|材料)",
    r"(?:先|依次|逐项)(?:确认|询问|收集).{0,24}"
    r"(?:受众|页数|大纲|样张|风格|材料)",
    r"首次使用.{0,16}(?:偏好|设置|配置|确认)",
    r"(?:开始|启动)(?:生成|渲染|制作|派发)",
]

# Words that soften a sentence into refusal/explanation/conditional rather
# than a this-turn commitment. Compound forms only: bare "不/别/无" would
# over-soften via "不过/特别/毫无".
SOFTENER_RE = re.compile(
    r"(?:不会|不能|不得|不要|不建议|未|尚未|还没|还未|暂不|先不|无法|没法|"
    r"禁止|拒绝|没有|无|而不是|并非|别|待确认|若|如果|如需|想要|"
    r"需要的话|要做|建议|后续|将来|届时|排除|避开)")
EN_SOFTENER_RE = re.compile(
    r"\b(?:not|won't|will not|cannot|can't|unable|instead|if|when)\b",
    re.IGNORECASE)


def sentences(text: str):
    for chunk in re.split(r"[。！？!?；;\n]+", text):
        body = chunk.strip()
        if body:
            yield body


def softened(body: str) -> bool:
    return bool(SOFTENER_RE.search(body)) or bool(EN_SOFTENER_RE.search(body))


def judge(text: str) -> list[str]:
    """Return violation reasons; empty list means the reply passes."""
    problems = []

    narrative_hit = next((w for w in NARRATIVE_WORDS if w in text), None)
    pairing_hit = next((w for w in PAIRING_WORDS if w in text), None)
    if narrative_hit is None:
        problems.append(
            "缺少叙事层语义：未见「叙事/页序/骨架/为什么是现在/要价」类"
            "融资路演叙事词")
    if pairing_hit is None:
        problems.append(
            "缺少论证模式配对提及：未见「论证模式/怎么证/故事弧/"
            "结论先行金字塔」类配对词")

    for body in sentences(text):
        if CONTROL_FIELD_RE.match(body):
            continue
        # 引用用户需要说出的授权口令不是当前执行；引用之外的动作仍需检查。
        body = re.sub(r'(?:明示|回复|说出)[“"「][^”"」]+[”"」]', "用户授权口令", body)
        for pattern in STARTUP_PATTERNS:
            m = re.search(pattern, body)
            if m and not softened(body):
                problems.append(
                    f"发现未经否定的 Route 启动/新增确认门迹象: {body[:60]}"
                    f" (命中: {m.group(0)[:40]})")
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
        "healthy-layering-with-control-block",
        True,
        "interaction_mode: advise\n"
        "route: 未选择\n"
        "status: advise\n"
        "融资路演的叙事骨架建议按节位走：为什么是现在 → 问题 → 方案 → "
        "增长牵引 → 团队 → 要价（The ask），12 页主弧保持稀疏、密度进附录，"
        "权重按轮次自适应。论证形态配对故事弧（情绪弧线说服），要价页辅"
        "结论先行金字塔。本轮不生成；候选路线是 generate，等你明确授权。"
        "next_action: 等你确认是否进入 execute",
    ),
    (
        "healthy-negated-startup",
        True,
        "叙事上可用融资路演叙事方法论：why now 打头、要价收尾。论证模式推荐"
        "配对故事弧。本轮不会启动 route: generate，也不先追加确认门，"
        "等你明确授权。",
    ),
    (
        "fail-no-narrative-semantics",
        False,
        "可以做，12 页没问题，走 generate 路线就行，材料给我即可。",
    ),
    (
        "fail-no-pairing",
        False,
        "叙事骨架：为什么是现在、增长牵引、要价，页序按这个排。",
    ),
    (
        "fail-gate-adding-startup",
        False,
        "叙事建议故事弧配结论先行金字塔。接下来我会先依次确认受众、页数、"
        "大纲与样张，然后启动生成流程。",
    ),
    (
        "fail-execution-claim",
        False,
        "叙事骨架与论证配对（故事弧+结论先行金字塔）已说明；我已开始生成"
        "12 页大纲并初始化 runtime。",
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
