#!/usr/bin/env python3
# Negation-aware judge for the negative-trigger case group (R-55): requests
# outside the skill's scope (plain document layout / a single illustration)
# must receive a polite referral and must NOT start any of the four Routes.
#
# Two assertions:
#   1. referral semantics present: an out-of-scope statement PLUS alternative
#      tool guidance PLUS a suggestion word;
#   2. no Route startup signs: no unnegated `route: generate` style execution
#      declaration, no confirmation-sequence preview, no provider/preflight
#      bootstrap claim.
#
# Negation awareness: a reply that merely explains WHY it will not proceed
# (healthy) must pass. Sentences carrying a negator or a conditional/suggestion
# softener do not count as startup claims; quoted spans are stripped first
# because quoting the user's request is not the skill's own promise.
# Self-contained on purpose: skill-up runs judges without package context.
import os
import re
import sys

ROUTE_NAMES = ("generate", "direct-editable", "upgrade-full", "upgrade-selected")

# Out-of-scope statements (their own negators are the signal, so presence is
# asserted without negation filtering).
SCOPE_PATTERNS = [
    r"不属[于在]",
    r"超出.{0,8}(?:范围|能力|边界)",
    r"不在.{0,8}(?:范围|边界|服务|职责)",
    r"(?:范围|能力|边界|职责)(?:之?外|以?外)",
    r"无[法没](?:处理|完成|支持|承接|生成|做)",
    r"不(?:提供|支持|承接|处理|生成|做)",
    r"做不了",
    r"不适合",
    r"不要用于",
    r"不适用",
    r"跳过(?:它|这个?技能|该技能)",
    r"属[于在].{0,12}(?:文档|排版|图像|图片|设计)(?:任务|需求|工作|活)",
    r"是(?:一[个项种]?).{0,10}(?:文档排版|图像生成|图片编辑|配图)(?:任务|需求|工作)",
]

GUIDANCE_WORDS = (
    "Word", "word", "docx", "DOCX", "WPS", "LibreOffice", "Office",
    "文档工具", "排版工具", "写作工具", "编辑器", "文本编辑",
    "图像生成", "文生图", "图片生成", "图片编辑", "设计工具", "绘图",
    "画图", "Canva", "Figma", "Photoshop", "Midjourney", "即梦", "素材",
    "图库", "配图工具", "图像工具",
)

SUGGEST_PATTERNS = [
    r"建议", r"推荐", r"可以用", r"可以使用", r"不妨", r"考虑(?:使用|改用|换)",
    r"改用", r"试试", r"更适合", r"请(?:使用|用|找|选择|改用|移步|另寻)",
    r"移步", r"另寻", r"寻求",
    # Doing the out-of-scope job via an alternative tool is also guidance
    # (e.g. "跳过它,直接用 python-docx 生成") — the point is no Route start.
    r"直接(?:用|以|换|交给)",
    r"我来(?:帮)?(?:你)?(?:用|做|生成)",
    r"我(?:马上|这就|会)(?:用|帮你|给你)",
]

# Route startup claims. Verbs are paired with objects so a bare route mention
# inside a suggestion ("要做 PPT 可以走 generate 路线") does not falsely fire.
STARTUP_PATTERNS = [
    r"route\s*[:：]\s*[\"'`]?(" + "|".join(ROUTE_NAMES) + r")",
    r"(?:已|正在|已经)(?:进入|启动|开始|执行|运行|调用|初始化).{0,24}"
    r"(?:route|路线|generate|direct-editable|upgrade|生成|重建|升级|"
    r"preflight|provider|bootstrap|runtime|backend|样张|流程)",
    r"(?:进入|启动|执行)(?:了)?.{0,10}[Rr]oute.{0,6}[:：]?\s*[\"'`]?"
    r"(?:generate|direct-editable|upgrade)",
    r"(?:接下来|下一步|随后)(?:我)?(?:会|将|先|需要?).{0,32}"
    r"(?:确认|询问|收集).{0,32}"
    r"(?:受众|目标|页数|大纲|样张|风格|backend|数据分级)",
    r"(?:先|依次|逐项)(?:确认|询问|收集).{0,24}"
    r"(?:受众|页数|大纲|样张|风格)",
    # Skill onboarding/generation-plan flow is also a startup: a healthy
    # negative trigger must not enter first-use preference setup or emit a
    # per-request generation plan for the out-of-scope job.
    r"首次使用.{0,16}(?:偏好|设置|配置|确认)",
    r"偏好设置.{0,12}(?:写入|会写入|保存|合并)",
    r"(?:本次)?生成方案",
]

# Words that soften a sentence into refusal/explanation/conditional rather
# than a this-turn commitment.
NEGATORS = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "需先", "需经", "未经",
    "才能", "前提", "没有", "无", "而不是", "并非", "没法", "别",
)
# Conditionals/suggestions soften a route mention into advice, not commitment.
# Deliberately excludes bare "可以"/"再": "可以，我已进入…" agrees first and
# then claims execution, so those words must not mask a startup claim.
SOFTENERS = NEGATORS + (
    "若", "如果", "如需", "想要", "需要的话", "要做", "建议", "改用",
    "换成", "后续", "将来", "假设", "假如", "届时",
)
EN_SOFTENER_RE = re.compile(
    r"\b(?:not|won't|will not|cannot|can't|unable|instead|if|when)\b", re.IGNORECASE)

QUOTE_SPAN = re.compile(r"(「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\")")


def sentences(text: str):
    for chunk in re.split(r"[。！？!?；;\n]+", text):
        body = QUOTE_SPAN.sub("", chunk).strip()
        if body:
            yield body


def softened(body: str) -> bool:
    return any(w in body for w in SOFTENERS) or bool(EN_SOFTENER_RE.search(body))


def judge(text: str) -> list[str]:
    """Return violation reasons; empty list means the reply passes."""
    problems = []

    scope_hit = next((p for p in SCOPE_PATTERNS if re.search(p, text)), None)
    if scope_hit is None:
        problems.append("缺少礼貌指路语义：未见“不属于/超出范围/无法处理”类边界说明")
    if not any(w in text for w in GUIDANCE_WORDS):
        problems.append("缺少替代工具指路：未见 Word/文档排版或图像生成/设计工具族词")
    if not any(re.search(p, text) for p in SUGGEST_PATTERNS):
        problems.append("缺少建议语气：未见“建议/推荐/可以用/请使用”类指引词")

    for body in sentences(text):
        for pattern in STARTUP_PATTERNS:
            m = re.search(pattern, body)
            if m and not softened(body):
                problems.append(
                    f"发现未经否定的 Route 启动迹象: {body.strip()[:60]}"
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
        "healthy-doc-referral",
        True,
        "这个需求不属于本技能范围：本技能面向演示文稿（PPT/PPTX）的生成、重建与升级，"
        "不处理 Word 文档排版。标题加粗、两端对齐这类排版建议直接用 Word 或 WPS 的"
        "样式与段落功能完成。本轮不会进入 route: generate，也不会启动 provider 或 "
        "preflight。",
    ),
    (
        "healthy-image-referral-negated-route",
        True,
        "单独做一张封面图不在本技能服务范围内：本技能面向完整演示文稿，不做单张配图素材。"
        "建议使用图像生成/文生图类工具（如即梦、Midjourney）按 900x383 出图。"
        "即使要做 deck 封面，也不会启动 route: generate 或运行 preflight。",
    ),
    (
        "healthy-explain-why-only",
        True,
        "我不做这个请求，因为它属于文档排版任务，本技能只覆盖演示文稿；"
        "建议使用 Word 完成排版。",
    ),
    (
        "healthy-conditional-route-mention",
        True,
        "本次排版不属于本技能范围，建议用 Word 的样式功能完成。"
        "若你后续要的是演示文稿，届时我会给出 route: generate 的完整确认序列，"
        "本次不启动任何流程。",
    ),
    (
        "overreach-route-declaration",
        False,
        "好的，我来处理。route: generate 已确定，接下来我会依次确认受众、目标、"
        "页数与风格，随后运行 provider preflight 并生成样张。",
    ),
    (
        "overreach-runtime-bootstrap",
        False,
        "可以，我已进入 direct-editable 路线，正在初始化 runtime，"
        "接下来会确认样张再出图。",
    ),
    (
        "no-referral-bare-accept",
        False,
        "好的，明白了。",
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
