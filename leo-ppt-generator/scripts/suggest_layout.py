#!/usr/bin/env python3
"""suggest_layout.py — 逐页版式匹配的确定性打分器（B2，模板调度师）。

四步链（原创规则链，机制吸收自优先级序思想；无上游文本）：

    角色对齐 → 结构匹配 → 节奏感 → 置信度裁决

- 角色对齐：``page_role``（13_页面语义 25 角色）映射到版式 ``page_type``
  （cover/agenda/section/content/data/closing）；角色不符的候选直接出局。
- 结构匹配：页面侧 {要点条数, 预估字数, 数据点数} 对 sidecar
  ``content_capacity``（count 区间包含度 × max_chars 字数覆盖度；超容量
  候选容量分乘 0）。
- 节奏感：``reuse_friendly=false`` 且已用 → 硬排除（与
  check_layout_reuse.py 同口径）；已用版式 -0.4、与上一页同版式再 -0.4；
  风格路由 preferred +0.1 / discouraged -0.2（风格层参与但不越权）。
- 置信度裁决：top1 综合分 < 0.5 → ``decision: "undecided"``（合法结果，
  不是失败）；**禁止编造版式 id**——候选只能来自 sidecar 枚举集，输出 id
  不在枚举集内即脚本自身 bug（防御断言 exit 2）。

打分公式（固定、可解释）::

    score = 0.45 * role_fit + 0.40 * capacity_fit + 0.15 * rhythm + routing_adj

无状态只读：不写任何文件、不记忆跨调用状态。

用法::

    python3 scripts/suggest_layout.py [input.json] [--style 清爽专业风] [--json-schema]
    cat input.json | python3 scripts/suggest_layout.py

输入（stdin 或文件）::

    {"pages": [{"page": 3, "page_role": "对比·多维", "points": 2,
                "est_chars": 120, "data_points": 0, "image_sources": 0,
                "already_used": ["P1", "P4"]}]}

输出（stdout，键排序、确定性、无时间戳）：逐页 candidates（top 2）、
confidence、decision（auto / undecided）。

退出码（CI-4）：0 = 正常产出（auto 与 undecided 均合法）；2 = 输入 schema
错误 / 脚本防御断言触发。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.asset_resolver import AssetResolver, ResolverError

W_ROLE, W_CAPACITY, W_RHYTHM = 0.45, 0.40, 0.15
CONFIDENCE_FLOOR = 0.5
OVERFLOW_TOLERANCE = 1.2
TOP_CANDIDATES = 2

# 13_页面语义 25 角色 → 版式 page_type（6 值枚举）。未列角色按中性 0.5 评分。
ROLE_PAGE_TYPES: dict[str, list[str]] = {
    "封面": ["cover"],
    "拆解·目录": ["agenda"],
    "分隔·过渡": ["section"],
    "陈述·金句": ["section", "content"],
    "氛围页": ["closing", "section"],
    "结尾": ["closing"],
    "指标·计分榜": ["data"],
    "结论·数字海报": ["data"],
    "对比·多维": ["content", "data"],
    "分布·漏斗": ["data"],
    "趋势·时间线": ["content", "data"],
    "流程·路径": ["content"],
    "关系·网络": ["content"],
    "团队": ["content"],
    "图片主导": ["content", "closing"],
    "案例·分镜": ["content"],
    "小结·回顾": ["content", "closing"],
    "参考·文献": ["content"],
    "目标·学习目标": ["content"],
    "练习·检测": ["content"],
    "风险·问答": ["content"],
    "洞察·展望": ["content"],
    "背景·定位矩阵": ["content", "data"],
    "落地·下一步": ["content"],
    "融资路演链": ["content"],
}

INPUT_SCHEMA = {
    "type": "object",
    "required": ["pages"],
    "properties": {
        "pages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["page", "page_role"],
                "properties": {
                    "page": {"type": "integer"},
                    "page_role": {"type": "string"},
                    "points": {"type": "integer"},
                    "est_chars": {"type": "number"},
                    "data_points": {"type": "integer"},
                    "image_sources": {"type": "integer"},
                    "already_used": {"type": "array", "items": {"type": "string"}},
                    "previous_layout": {"type": "string"},
                },
            },
        }
    },
}


def _compact_id(entity: dict) -> str:
    """Return the stable public alias while retaining the canonical asset ID."""
    aliases = entity.get("aliases") or []
    return str(aliases[0] if aliases else entity["asset_id"])


def load_bank(*, home: Path | None = None) -> dict[str, dict]:
    """Load layout profiles through the catalog-backed resolver.

    The scorer consumes a small compatibility projection (page type, slots and
    reuse policy), while ``layout.json`` remains the only source of truth.
    """
    bank: dict[str, dict] = {}
    resolver = AssetResolver(home=home)
    for entity in resolver.entities:
        if entity.get("kind") != "layout":
            continue
        resolved = resolver.resolve(entity["asset_id"])
        data = resolved["data"]
        layout_id = _compact_id({**data, "asset_id": entity["asset_id"]})
        bank[layout_id] = {
            "layout_id": layout_id,
            "asset_id": entity["asset_id"],
            "name": data.get("name"),
            "page_type": data.get("page_role", "content"),
            "content_capacity": data.get("slots") or {},
            "reuse_friendly": data.get("reuse_friendly", True),
            "max_per_deck": data.get("max_per_deck", 1),
        }
    return bank


def load_style_routing(
    style_name: str | None, *, home: Path | None = None,
    resolver: AssetResolver | None = None,
) -> tuple[float, dict[str, float]]:
    """Return ``(capacity_factor.text, {compact layout id: adjustment})``.

    Missing user routing is deliberately neutral: a user overlay must not
    inherit a same-name builtin route by accident.
    """
    if not style_name:
        return 1.0, {}
    resolver = resolver or AssetResolver(home=home)
    try:
        style = resolver.require(style_name, kind="style")
    except ResolverError:
        return 1.0, {}
    bindings = style["data"].get("bindings") or {}
    factor = float(bindings.get("capacity_factor", {}).get("text", 1.0))
    adjust: dict[str, float] = {}
    for rule in bindings.get("layout_routes", []):
        for key, delta in (("preferred", 0.1), ("discouraged", -0.2)):
            for ref in rule.get(key, []) or []:
                try:
                    resolved = resolver.resolve(ref)
                    layout_id = _compact_id(resolved)
                except ResolverError:
                    continue
                adjust[layout_id] = adjust.get(layout_id, 0.0) + delta
    return factor, adjust


def _role_fit(page: dict, layout: dict) -> tuple[float | None, str]:
    """角色对齐分；None = 出局。"""
    role = str(page.get("page_role", ""))
    allowed = ROLE_PAGE_TYPES.get(role)
    ptype = layout.get("page_type", "content")
    if allowed is None:
        return 0.5, f"角色未识别:{role}（中性评分）"
    if ptype in allowed:
        fit = 1.0
        if int(page.get("data_points", 0) or 0) >= 3 and ptype != "data":
            fit = 0.5
            return fit, f"角色对齐:{role}（数据点≥3，非 data 版式减半）"
        return fit, f"角色对齐:{role}"
    return None, f"角色不符:{role}≠{ptype}"


def _capacity_fit(
    page: dict, layout: dict, factor: float
) -> tuple[float, list[str]]:
    """区间包含度 × 字数覆盖度；超容量乘 0。"""
    reasons: list[str] = []
    capacity = layout.get("content_capacity", {})
    points = page.get("points")
    containment = 0.5
    if points is not None and any("count_min" in s for s in capacity.values()):
        count_slots = [s for s in capacity.values() if "count_min" in s]
        inside = any(
            s["count_min"] <= points <= s["count_max"] for s in count_slots
        )
        if inside:
            containment = 1.0
            reasons.append(f"条数 {points} 在区间内")
        else:
            best = max(count_slots, key=lambda s: s["count_max"])
            if points < best["count_min"]:
                containment = max(0.0, points / best["count_min"])
                reasons.append(f"条数不足:{points}<{best['count_min']}")
            elif points <= best["count_max"] * OVERFLOW_TOLERANCE:
                containment = 0.5
                reasons.append(f"条数偏多:{points}>{best['count_max']}")
            else:
                reasons.append(f"条数硬超:{points}≫{best['count_max']}")
                return 0.0, reasons
    est_chars = page.get("est_chars")
    coverage = 1.0
    if est_chars is not None:
        widest = max(
            (s.get("max_chars", 0) for s in capacity.values()
             if "max_chars" in s),
            default=None,
        )
        if widest is not None:
            limit = widest * factor
            if est_chars <= limit:
                reasons.append(f"容量 {est_chars:.0f}/{limit:.0f} chars")
            elif est_chars <= limit * OVERFLOW_TOLERANCE:
                coverage = 0.5
                reasons.append(f"容量偏紧 {est_chars:.0f}/{limit:.0f} chars")
            else:
                reasons.append(
                    f"容量硬超 {est_chars:.0f}/{limit:.0f} chars（乘 0）"
                )
                return 0.0, reasons
    return containment * coverage, reasons


def _rhythm(page: dict, layout_id: str, layout: dict) -> tuple[float, list[str]]:
    """节奏分（∈ [0, 1]）：已用 -0.4，与上一页同版式再 -0.4。"""
    score = 1.0
    reasons: list[str] = []
    used = page.get("already_used") or []
    if layout_id in used:
        score -= 0.4
        reasons.append("已用版式 -0.4")
    previous = page.get("previous_layout")
    if previous and previous == layout_id:
        score -= 0.4
        reasons.append("与上一页同版式 -0.4")
    return max(0.0, min(1.0, score)), reasons


def score_page(page: dict, bank: dict[str, dict], factor: float,
               adjust: dict[str, float]) -> dict:
    known_ids = set(bank)
    candidates: list[dict] = []
    used = set(page.get("already_used") or [])
    for layout_id in sorted(bank):
        layout = bank[layout_id]
        # 节奏硬排除：强视觉版式已用即出局（与 check_layout_reuse 同口径）。
        if layout.get("reuse_friendly") is False and layout_id in used:
            continue
        role_fit, role_reason = _role_fit(page, layout)
        if role_fit is None:
            continue
        capacity_fit, cap_reasons = _capacity_fit(page, layout, factor)
        rhythm, rhythm_reasons = _rhythm(page, layout_id, layout)
        routing = adjust.get(layout_id, 0.0)
        score = (
            W_ROLE * role_fit + W_CAPACITY * capacity_fit + W_RHYTHM * rhythm
            + routing
        )
        score = max(0.0, min(1.0, score))
        reasons = [role_reason, *cap_reasons, *rhythm_reasons]
        if routing:
            reasons.append(
                f"风格路由 {'+' if routing > 0 else ''}{routing:.1f}"
            )
        candidates.append(
            {
                "layout": layout_id,
                "score": round(score, 2),
                "reasons": reasons,
            }
        )
    candidates.sort(key=lambda c: (-c["score"], c["layout"]))
    top = candidates[:TOP_CANDIDATES]
    confidence = top[0]["score"] if top else 0.0
    # 禁编造 id：防御断言——输出 id 必须全部来自枚举集。
    for cand in top:
        if cand["layout"] not in known_ids:
            print(
                f"fabricated_layout_id: {cand['layout']} 不在枚举集（脚本 bug）",
                file=sys.stderr,
            )
            raise SystemExit(2)
    return {
        "page": page.get("page"),
        "candidates": top,
        "confidence": round(confidence, 2),
        "decision": "auto" if confidence >= CONFIDENCE_FLOOR else "undecided",
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:]]
    style_name = None
    if "--json-schema" in args:
        print(json.dumps(INPUT_SCHEMA, ensure_ascii=False, indent=2))
        return 0
    home = None
    if "--home" in args:
        idx = args.index("--home")
        if idx + 1 >= len(args):
            print("用法错误: --home 需要目录", file=sys.stderr)
            return 2
        home = Path(args[idx + 1]).expanduser().resolve()
        args = args[:idx] + args[idx + 2:]
    if "--style" in args:
        idx = args.index("--style")
        if idx + 1 >= len(args):
            print("用法错误: --style 需要风格名", file=sys.stderr)
            return 2
        style_name = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    input_text = ""
    if args:
        path = Path(args[0])
        if not path.is_file():
            print(f"[ERROR] {path}: 文件不存在", file=sys.stderr)
            return 2
        input_text = path.read_text(encoding="utf-8")
    else:
        input_text = sys.stdin.read()
    try:
        payload = json.loads(input_text)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] 输入 JSON 不可解析（{exc}）", file=sys.stderr)
        return 2
    if not isinstance(payload, dict) or not isinstance(payload.get("pages"), list):
        print("[ERROR] 输入须为 {\"pages\": [...]}（--json-schema 查看 schema）",
              file=sys.stderr)
        return 2
    pages = payload["pages"]
    if not pages or not all(
        isinstance(p, dict) and "page" in p and "page_role" in p for p in pages
    ):
        print("[ERROR] pages[] 每页必须含 page 与 page_role", file=sys.stderr)
        return 2

    try:
        resolver = AssetResolver(home=home)
        bank = load_bank(home=home)
    except ResolverError as exc:
        print(f"[ERROR] canonical 版式目录不可用（{exc.reason_code}）", file=sys.stderr)
        return 2
    if not bank:
        print("[ERROR] canonical 版式库为空（template-library/canonical/layouts/*/layout.json）",
              file=sys.stderr)
        return 2
    inline_style = payload.get("style")
    effective_style = style_name or (
        inline_style if isinstance(inline_style, str) else None
    )
    factor, adjust = load_style_routing(
        effective_style, home=home, resolver=resolver
    )
    results = [score_page(page, bank, factor, adjust) for page in pages]
    output = {"pages": results}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
