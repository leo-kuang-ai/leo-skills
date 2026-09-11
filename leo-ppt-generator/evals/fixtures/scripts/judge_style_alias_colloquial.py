#!/usr/bin/env python3
# Negation-aware judge for the colloquial alias case (style-alias-colloquial-hit):
# an advise-mode question phrased with a colloquial alias ("dracula 那种终端暗紫
# 配色") must resolve to a REAL in-library style name (terminal palette family)
# or explicitly confirm the hard-rule context (tech sharing is not a defense
# genre, so the terminal family is not excluded). The reply must not fabricate
# style names absent from the library, nor claim to have created a new style.
#
# Presence assertion: a real terminal-family name/alias hit, OR a hard-rule
# context confirmation sentence (技术分享 + not-excluded semantics).
# Violation assertion: an unnegated style-creation claim ("已为你创建…"), or a
# quoted "…风" style name presented as an in-library option that the current
# catalog/resolver cannot resolve.  The judge loads the same generation pointer
# used by runtime execution; it fails closed on stale or malformed catalog data.
# Bare "dracula" is excluded from the hit list on purpose: the user prompt
# already contains it, so accepting it would let a lazy echo pass.
# Self-contained on purpose: skill-up runs judges without package context; the
# package-local runtime source is loaded by path when available.
import os
import re
import sys
from pathlib import Path

# Query hints used to identify terminal/developer styles in the live catalog.
# A hint is accepted only after resolver lookup succeeds in the current
# generation; this tuple is not a style-name whitelist.
TERMINAL_QUERY_HINTS = (
    "Dracula紫风", "Dracula紫", "终端配色", "终端命令行风", "代码开发者风",
    "Catppuccin拿铁风", "Catppuccin摩卡风", "Gruvbox暗风", "东京夜风",
    "玫瑰松风", "日光浅风", "北极冷风", "北欧风", "Solarized", "Nord",
    "Rosé Pine", "Tokyo Night", "Catppuccin", "Gruvbox",
)

# Hard-rule context confirmation: the sentence ties the tech-sharing context to
# the fact that no exclusion rule fires (only defense genres exclude).
NOT_EXCLUDED = r"(?:不.{0,2}排除|无需排除|未.{0,2}排除|不在排除|不触发)"
CONTEXT_CONFIRM_PATTERNS = [
    r"(?:技术分享|开发者|分享场景)[^。！？!?；;\n]{0,40}" + NOT_EXCLUDED,
    NOT_EXCLUDED + r"[^。！？!?；;\n]{0,40}(?:技术分享|终端)",
    r"答辩[^。！？!?；;\n]{0,16}(?:才|才会|方)会?[^。！？!?；;\n]{0,12}排除",
]

# Style-creation claims (fabrication of library content). Applied per sentence
# with negation filtering: "不建议为此新建风格" is healthy honesty.
CREATION_PATTERNS = [
    r"已为你创建",
    r"已(?:经)?为你?新建",
    r"新建了",
    r"创建[了出]",
    r"新建(?:一[个套种])?(?:专属|新|自定义)?风格",
    r"创建.{0,6}(?:新|专属|自定义)?风格",
    r"新增.{0,4}风格",
    r"刚(?:刚|才)[^。！？!?；;\n]{0,8}(?:入库|收录)",
]

QUOTED_NAME = re.compile(r"[「『“]([^」』”]{2,24})[」』”]")

NEGATORS = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "没有", "无", "而不是", "并非",
    "没法", "别",
)
SOFTENERS = NEGATORS + (
    "若", "如果", "如需", "想要", "需要的话", "要做", "建议", "后续",
    "将来", "届时", "可以再", "候选",
)
# Compound negators for fabrication/creation claims: bare single chars ("不",
# "别", "无") would over-soften via words like "不过/特别/毫无", letting real
# fabrication slip through, so they are anchored to compound forms.
CLAIM_NEG_RE = re.compile(
    r"(?:不会|不能|不得|不要|不建议|不推荐|不创建|不新建|不编造|并非|而不是|"
    r"没有|禁止|拒绝|尚未|还没|还未|暂不|先不|无法|没法|"
    r"别(?:用|做|创建|新建|急)|无(?:需|须|法))")
CLAIM_SOFTENERS = ("若", "如果", "如需", "需要的话", "后续")
EN_SOFTENER_RE = re.compile(
    r"\b(?:not|won't|will not|cannot|can't|unable|instead|if|when)\b",
    re.IGNORECASE)


def sentences(text: str):
    for chunk in re.split(r"[。！？!?；;\n]+", text):
        body = chunk.strip()
        if body:
            yield body


def softened(body: str) -> bool:
    return any(w in body for w in SOFTENERS) or bool(EN_SOFTENER_RE.search(body))


def claim_softened(body: str) -> bool:
    return bool(CLAIM_NEG_RE.search(body)) \
        or any(w in body for w in CLAIM_SOFTENERS) \
        or bool(EN_SOFTENER_RE.search(body))


def looks_like_style_name(name: str) -> bool:
    # Chinese style names carry 风; imported names may carry style/theme.
    # 真实风格名以「风」结尾；以「风格」结尾的引号短语（如「用户点名风格」）
    # 是规则词汇而非风格名宣称——迭代 120 的实测误判来源。
    if name.endswith("风格") or name.endswith("风格」"):
        return False
    if "点名" in name or "规则" in name or "预设" in name:
        return False  # 规则/机制用语，不是风格名
    return "风" in name or bool(re.search(r"(?i)\b(style|theme)\b", name))


def _bundle_root() -> Path | None:
    override = os.environ.get("LEO_PPT_BUNDLE")
    if override:
        candidate = Path(override).expanduser()
        if (candidate / "template-library" / "library.json").is_file():
            return candidate
    for parent in Path(__file__).resolve().parents:
        if (parent / "template-library" / "library.json").is_file():
            return parent
    return None


def _live_style_index() -> tuple[dict | None, str | None]:
    """Load and resolve the current catalog generation for this judge run."""
    root = _bundle_root()
    if root is None:
        return None, "未找到包含 template-library/library.json 的技能包"
    runtime_src = root / "runtime" / "src"
    if not runtime_src.is_dir():
        runtime_src = Path(__file__).resolve().parents[3] / "runtime" / "src"
    if str(runtime_src) not in sys.path:
        sys.path.insert(0, str(runtime_src))
    try:
        from leo_ppt_generator.asset_resolver import AssetResolver, ResolverError

        resolver = AssetResolver(
            library=root / "template-library",
            home=root / ".judge-no-user-home",
        )
        entities = [entity for entity in resolver.entities
                    if entity.get("kind") == "style"]
        styles: set[str] = set()
        terminal_hits: set[str] = set()
        for entity in entities:
            # Resolve every style so a revision mismatch cannot be hidden by
            # the registry name list alone.
            resolved = resolver.resolve(entity["asset_id"])
            names = {
                str(resolved.get("name") or entity.get("name") or ""),
                *(str(alias) for alias in resolved.get("aliases", [])),
                entity["asset_id"].rsplit(":", 1)[-1],
            }
            names.discard("")
            styles.update(names)
            data = resolved.get("data") or {}
            families = (data.get("taxonomy") or {}).get("families") or []
            haystack = " ".join((*names, *(str(f) for f in families)))
            if any(token.casefold() in haystack.casefold() for token in (
                "终端", "dracula", "catppuccin", "gruvbox", "科技暗色", "tech-dark",
            )):
                # Generic aliases such as "开发者" or "科技" must not pass
                # presence by substring echo; accept the canonical name and
                # qualified aliases only.
                terminal_hits.update(
                    value for value in names
                    if "风" in value or "终端" in value
                    or any(token.casefold() in value.casefold()
                           for token in ("dracula", "catppuccin", "gruvbox"))
                )
        # Validate the colloquial query hints against the same resolver.  This
        # keeps the terminal-family presence assertion tied to actual lookup,
        # including aliases, rather than to a copied name table.
        queried_hits: set[str] = set()
        for hint in TERMINAL_QUERY_HINTS:
            for entity in resolver.lookup(hint, kind="style"):
                resolved = resolver.resolve(entity["asset_id"])
                queried_hits.add(str(resolved.get("name") or entity.get("name")))
        terminal_hits.update(queried_hits)
        return {"styles": styles, "terminal_hits": terminal_hits}, None
    except (OSError, ValueError, ImportError, ResolverError) as exc:
        reason = getattr(exc, "reason_code", "catalog_error")
        return None, f"{reason}: {exc}"


def judge(text: str) -> list[str]:
    """Return violation reasons; empty list means the reply passes."""
    problems = []

    catalog, catalog_error = _live_style_index()
    if catalog_error:
        problems.append(f"无法验证当前 canonical style catalog: {catalog_error}")
        catalog = {"styles": set(), "terminal_hits": set()}

    # Presence: real in-library terminal-family hit, or context confirmation.
    name_hit = next((w for w in sorted(catalog["terminal_hits"], key=len, reverse=True)
                     if w and w in text), None)
    context_hit = next(
        (p for p in CONTEXT_CONFIRM_PATTERNS if re.search(p, text)), None)
    if name_hit is None and context_hit is None:
        problems.append(
            "缺少真实在库风格命中：未见 Dracula紫风/终端配色/终端命令行风等"
            "终端族真实名，也未见硬规则语境确认（技术分享不在排除范围）")

    for body in sentences(text):
        for pattern in CREATION_PATTERNS:
            m = re.search(pattern, body)
            if m and not claim_softened(body):
                problems.append(
                    f"发现未经否定的风格创建/编造宣称: {body[:60]}"
                    f" (命中: {m.group(0)[:30]})")
                break

    # Quoted style names presented as in-library options must resolve in the
    # current catalog; a negated mention ("库里没有「X风」") is honesty.
    for body in sentences(text):
        for m in QUOTED_NAME.finditer(body):
            name = m.group(1).strip()
            if looks_like_style_name(name) and name not in catalog["styles"] \
                    and not claim_softened(body):
                problems.append(
                    f"疑似编造不在库的风格名: 「{name}」"
                    f"(所在句: {body[:60]})")
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
        "healthy-alias-resolved-to-real-name",
        True,
        "interaction_mode: advise\n"
        "route: 未选择\n"
        "库里对应的正是 Dracula紫风（终端配色家族：紫夜深底 + 荧光粉/薰衣草紫，"
        "别名含 dracula），同族还有终端命令行风、Gruvbox暗风、东京夜风。"
        "技术分享面向开发者与该族气质匹配。本轮只咨询，不启动任何流程。",
    ),
    (
        "healthy-context-confirmation-only",
        True,
        "先给判断：你的场景是技术分享，不是学术答辩，硬规则层面不会排除终端"
        "暗色系（排除复古潮流/高攻击系的是答辩类语境），可以放心选；"
        "确定方向后我再帮你定位具体风格名。",
    ),
    (
        "healthy-negated-fabrication-mention",
        True,
        "没有「赛博终端紫风」这个名字；库里真实收录的是 Dracula紫风"
        "（终端配色家族）。我不会为此新建风格。",
    ),
    (
        "fail-no-real-hit-bare-echo",
        False,
        "好的，暗紫色很有氛围感，给开发者的 deck 用很合适，"
        "到时候直接做就行。",
    ),
    (
        "fail-creation-claim",
        False,
        "库里最接近的是 Dracula紫风，但既然你想要更暗的紫：已为你创建 "
        "Dracula暗紫终端风 这个新风格，可以直接用。",
    ),
    (
        "fail-quoted-fabricated-name",
        False,
        "点名可以命中 Dracula紫风；不过更推荐「紫红赛博终端风」，"
        "就是 dracula 那种感觉，特别配技术分享。",
    ),
    (
        # 回归：迭代 120 实测误判——引号内规则词汇「用户点名风格」被判为
        # 编造风格名。真实风格名以「风」结尾，以「风格」结尾的是词汇。
        "healthy-rule-vocab-quote",
        True,
        "库里可以命中 Dracula紫风（终端配色族）。\n"
        "- **点名规则**：你属于「用户点名风格」，按选择优先序直接锁定该风格。"
        "本轮只咨询不执行。",
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
