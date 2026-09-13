"""逐页内容意图分析与 page_type_regime 路由。

这个模块是整稿风格推荐与版式调度之间的窄中间层。它不生成文案，也不替用户
决定业务论点；优先消费母版显式字段，缺失时只使用可解释的结构和关键词推断。
无法可靠判断时返回 ``decision=undecided``，调用方必须保留人工裁决出口。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


REGIME_PATH = (
    Path(__file__).resolve().parents[3]
    / "template-library"
    / "governance"
    / "rules"
    / "page-type-regime-v2.json"
)

_KEYWORDS = {
    "comparison": ("对比", "比较", "差异", "优劣", "之前", "之后", "vs", " versus "),
    "trend": ("趋势", "增长", "下降", "变化", "环比", "同比", "季度", "年度", "演进"),
    "process": ("流程", "步骤", "路径", "阶段", "实施", "落地", "先", "再", "最后"),
    "system": ("架构", "系统", "机制", "关系", "协同", "网络", "闭环", "模块", "因果"),
    "evidence": ("证据", "实拍", "案例", "来源", "截图", "访谈", "样本", "验证", "证明"),
    "table": ("清单", "台账", "矩阵", "明细", "分类", "规格", "字段", "表格"),
    "kpi": ("指标", "金额", "数量", "占比", "率", "成本", "规模", "效率", "预算"),
    "statement": ("结论", "关键发现", "核心判断", "一句话", "必须", "应该", "机会"),
}


def _role_shape(role: str, regime: dict[str, Any]) -> str | None:
    """Derive role aliases from the v2 regime; no second hand-authored map."""
    for page_type, spec in regime.get("page_types", {}).items():
        for alias in spec.get("role_aliases", []):
            if alias == role:
                return page_type
    return None


@lru_cache(maxsize=1)
def load_page_type_regime() -> dict[str, Any]:
    """读取版本化页型真值源；缺失或非法时快速失败。"""
    try:
        document = json.loads(REGIME_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"page_type_regime_unavailable: {REGIME_PATH}") from exc
    if document.get("schema_version") not in (1, 2) or not isinstance(document.get("page_types"), dict):
        raise RuntimeError("page_type_regime_invalid")
    return document


def _text(page: dict[str, Any]) -> str:
    bits: list[str] = []
    for key in ("title", "claim", "argument_role", "page_role", "section_role"):
        value = page.get(key)
        if isinstance(value, str):
            bits.append(value)
    for key in ("points", "items", "bullets"):
        value = page.get(key)
        if isinstance(value, list):
            bits.extend(str(item) for item in value)
        elif isinstance(value, str):
            bits.append(value)
    structures = page.get("structures")
    if isinstance(structures, dict):
        bits.append(json.dumps(structures, ensure_ascii=False, sort_keys=True))
    return " ".join(bits).lower()


def _count(page: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = page.get(key)
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, list):
            return len(value)
    return 0


def _explicit_shape(page: dict[str, Any]) -> str | None:
    value = page.get("content_shape") or page.get("semantic_structure")
    if isinstance(value, dict):
        value = value.get("kind") or value.get("type")
    if isinstance(value, str):
        aliases = {
            "list": "text_list", "text": "text_list", "bullets": "text_list",
            "kpi-stat": "kpi", "chart": "trend", "timeline": "trend",
            "comparison": "comparison", "process": "process", "system-diagram": "system",
            "evidence-grid": "evidence", "image-hero": "statement",
            "causal": "system",
        }
        normalized = aliases.get(value.strip().lower(), value.strip().lower())
        if normalized in load_page_type_regime()["page_types"]:
            return normalized
    return None


def _structure_shape(page: dict[str, Any]) -> str | None:
    structures = page.get("structures") or {}
    if not isinstance(structures, dict):
        return None
    if structures.get("sides"):
        return "comparison"
    if structures.get("table") or structures.get("columns") or structures.get("rows"):
        return "table"
    if structures.get("steps") or structures.get("timeline"):
        return "process"
    if structures.get("nodes") or structures.get("relations"):
        return "system"
    if structures.get("kpis") or structures.get("metrics"):
        return "kpi"
    if structures.get("evidence") or structures.get("figures"):
        return "evidence"
    return None


def _keyword_shape(text: str) -> tuple[str | None, int]:
    ranked: list[tuple[int, str]] = []
    for shape, words in _KEYWORDS.items():
        score = sum(1 for word in words if word in text)
        if score:
            ranked.append((score, shape))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return (ranked[0][1], ranked[0][0]) if ranked else (None, 0)


def analyze_page_intent(page: dict[str, Any]) -> dict[str, Any]:
    """返回可解释的逐页意图；同输入保证稳定。"""
    if not isinstance(page, dict):
        raise TypeError("page must be an object")
    regime = load_page_type_regime()
    role = str(page.get("page_role") or page.get("narrative_role") or "").strip()
    text = _text(page)
    explicit = _explicit_shape(page)
    structural = _structure_shape(page)
    keyword, keyword_hits = _keyword_shape(text)
    role_shape = _role_shape(role, regime)
    shape = explicit or structural or role_shape or keyword
    source = "explicit" if explicit else "structure" if structural else "role" if role_shape else "keyword" if keyword else "unknown"

    # 只有结构和显式字段能给出高置信；单一关键词只提供候选，不直接自动定稿。
    confidence = 1.0 if explicit else 0.9 if structural else 0.82 if role_shape else min(0.74, 0.45 + keyword_hits * 0.1) if keyword else 0.0
    if page.get("confidence") == "undecided" or page.get("semantic_structure") == "undecided":
        confidence = min(confidence, 0.35)
    if shape is None:
        shape = "text_list" if _count(page, "points", "items", "bullets") else "statement"
        source = "conservative-default"
        confidence = 0.35

    data_points = _count(page, "data_points", "numbers", "metrics")
    images = _count(page, "image_sources", "figures", "images")
    points = _count(page, "points", "items", "bullets")
    chars = float(page.get("est_chars") or 0)
    if images or shape in {"evidence", "system", "statement"}:
        visual_weight = "high"
    elif data_points or shape in {"kpi", "comparison", "trend", "process", "table"}:
        visual_weight = "medium"
    else:
        visual_weight = "low"
    if chars >= 420 or points >= 7:
        text_density = "high"
    elif chars >= 220 or points >= 4:
        text_density = "balanced"
    elif chars > 0 or points > 0:
        text_density = "low"
    else:
        text_density = "very-low"

    if data_points or shape in {"kpi", "trend", "table"}:
        evidence_type = "numeric" if data_points or shape in {"kpi", "trend"} else "categorical"
    elif images or shape == "evidence":
        evidence_type = "testimonial-or-artifact"
    elif shape in {"process", "system"}:
        evidence_type = "relational"
    else:
        evidence_type = "none"

    spec = regime["page_types"][shape]
    required = list(spec.get("required_slots") or [])
    return {
        "regime_version": regime["regime_id"],
        "page_type": shape,
        "content_shape": shape,
        "section_role": role or None,
        "argument_role": page.get("argument_role"),
        "evidence_type": evidence_type,
        "visual_weight": visual_weight,
        "text_density": text_density,
        "layout_affordances_required": required,
        "preferred_layouts": list(spec.get("preferred_layouts") or []),
        "fallback_layouts": list(spec.get("fallback_layouts") or []),
        "allowed_lanes": list(spec.get("allowed_lanes") or []),
        "forbidden_shapes": list(spec.get("forbidden_shapes") or []),
        "inference": {"source": source, "keyword_hits": keyword_hits},
        "confidence": round(confidence, 2),
        "decision": "auto" if confidence >= 0.7 else "undecided",
    }


def semantic_layout_adjustment(layout_id: str, intent: dict[str, Any]) -> tuple[float, str | None]:
    """给调度器一个小幅、可解释的语义加权；硬资格仍由调度器负责。"""
    preferred = intent.get("preferred_layouts") or []
    fallback = intent.get("fallback_layouts") or []
    if layout_id in preferred:
        return 0.18, f"内容意图首选:{intent['page_type']}→{layout_id}"
    if layout_id in fallback:
        return 0.06, f"内容意图回退:{intent['page_type']}→{layout_id}"
    return 0.0, None
