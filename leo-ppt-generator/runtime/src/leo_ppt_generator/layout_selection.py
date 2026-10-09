"""layout_selection.py — 结构声明准入与整册分配（dashi 集成 K5/U5）。

职责：
  - 结构指纹：对 canonical layout 的受 schema 约束 `structure` 声明做版本化
    规范化——引用重命名（资产名/主题名/颜色）不参与，阅读顺序、分组关系或
    图表编码改变则指纹改变；缺声明记 ``unknown``，不获得多样性加分，也不
    冒充新的结构族。指纹证明「声明的结构相同」，不证明最终图片相同。
  - 完整合格候选池：按页对全部 canonical 候选跑 content_projection 硬资格
    （角色/容量/媒体/backend/必需覆盖），Top-2 仅是面向人的推荐摘要。
  - 整册分配：确定性有界搜索——先满足显式选择、角色、容量、backend、
    禁复用与最大次数等硬约束，再按整册匹配分、相邻重复、结构族频率和
    叙事节拍排序；固定策略版本与搜索预算，平分按稳定 page_id/资产 ID 决
    定。候选存在但搜索预算耗尽与完全没有合格候选分别报告；预算耗尽不得
    宣称无解或放宽硬约束。
"""
from __future__ import annotations

import hashlib
import json

from pathlib import Path
from .asset_resolver import AssetResolver, ResolverError
from .content_projection import page_types_for_role
from .page_intent import (analyze_page_intent, load_page_type_regime,
                          semantic_layout_adjustment)
from .render.layout import capacity_level

W_ROLE, W_CAPACITY, W_RHYTHM = 0.45, 0.40, 0.15
CONFIDENCE_FLOOR = 0.5
SCORE_MARGIN_FLOOR = 0.05

SELECTION_POLICY_VERSION = "3"
DEFAULT_SEARCH_BUDGET = 20_000
UNKNOWN_FINGERPRINT = "unknown"


class LayoutSelectionError(ValueError):
    reason_code = "layout_selection_invalid"


from .storage import canonical_json_bytes as _canonical_json


def structure_fingerprint(profile: dict) -> str:
    """结构声明的版本化规范化指纹；缺声明记 unknown。"""
    structure = profile.get("structure")
    if not isinstance(structure, dict) or not structure.get("reading_order"):
        return UNKNOWN_FINGERPRINT
    groups = sorted(
        ({"relation": g.get("relation"), "members": sorted(g.get("members") or [])}
         for g in structure.get("groups") or []),
        key=lambda g: _canonical_json(g).decode("utf-8"))
    encodings = sorted(
        ({"kind": e.get("kind"), "slot": e.get("slot")}
         for e in structure.get("encodings") or []),
        key=lambda e: _canonical_json(e).decode("utf-8"))
    normalized = {
        "v": 1,
        "reading_order": list(structure["reading_order"]),
        "groups": groups,
        "encodings": encodings,
    }
    return "fp-" + hashlib.sha256(_canonical_json(normalized)).hexdigest()[:16]


def structure_family(profile: dict) -> str:
    """结构族 = 结构指纹（unknown 单列，不与任何声明结构合并）。"""
    return structure_fingerprint(profile)


def qualified_pool(
    pack_page: dict,
    design_context: dict,
    *,
    content_digest: str,
    numbers: list[dict] | None = None,
    backend: str = "render:html",
    candidates: list[str] | None = None,
    resolver=None,
    qualification_purpose="publication",
    provider_contract=None,
    proposal_factory=None,
) -> dict:
    """完整合格候选池（K5）：全部候选跑硬资格；不合格带原因保留在
    ``excluded``，供「无合格候选返回原因」与准入报告使用。
    """
    from .asset_resolver import AssetResolver, AssetNotFoundError, DependencyMissingError
    from .content_projection import precompile_binding, ProjectionError

    if resolver is None:
        resolver = AssetResolver()
    if candidates is None:
        candidates = sorted(entity["asset_id"] for entity in resolver.entities if entity["kind"] == "layout")
    pool: list[dict] = []
    excluded: list[dict] = []
    seen = set()
    proposal_attempts = []

    def candidate_sources():
        for query in candidates:
            yield query, None
        if not pool and proposal_factory is not None:
            for proposal in proposal_factory(pack_page, backend):
                if proposal.get("status") == "failed":
                    proposal_attempts.append(proposal)
                else:
                    yield proposal["base_asset"], proposal

    for query, proposal in candidate_sources():
        try:
            binding = precompile_binding(
                pack_page, design_context, query, backend=backend,
                content_digest=content_digest, numbers=numbers, resolver=resolver,
                qualification_purpose=qualification_purpose, provider_contract=provider_contract, proposal=proposal)
        except (AssetNotFoundError, DependencyMissingError, ProjectionError) as exc:
            if isinstance(exc, ProjectionError) and not isinstance(exc.__cause__, (AssetNotFoundError, DependencyMissingError)):
                raise
            excluded.append({"layout_id": query, "hard_failures": ["lane_dependency_missing: " + str(exc)]})
            if proposal:
                proposal_attempts.append({"candidate_id": proposal["candidate_id"], "status": "failed", "gap": str(exc)})
            continue
        entry = {
            "layout_id": binding["layout_id"],
            "binding": binding,
        }
        if binding["eligibility"]["qualified"]:
            from .execution_pairing import pairing_key, derive_execution_pairings
            identity_digest = pairing_key(binding["execution_pairing_identity"])
            qualification = binding["eligibility"]["checks"]["qualification"]
            relation = pack_page["expression"]["relation"]["kind"]
            view = derive_execution_pairings([resolver.resolve(binding["layout_id"])],
                [resolver.resolve(binding["template_id"] if backend == "render:html" else binding["recipe_id"])],
                {binding["layout_id"]: {"lanes": {backend: {"relations": {relation: qualification}}}}},
                catalog_generation=resolver.generation, qualification_purpose=qualification_purpose, proposal=proposal)
            if not any(candidate["identity_digest"] == identity_digest for candidate in view["candidates"]):
                excluded.append({**entry, "hard_failures": ["execution_pairing_not_admitted"], "pairing_gaps": view["gaps"]})
                if proposal:
                    proposal_attempts.append({"candidate_id": proposal["candidate_id"], "status": "failed", "gap": "execution_pairing_not_admitted"})
                continue
            if identity_digest in seen:
                continue
            seen.add(identity_digest)
            entry["identity_digest"] = identity_digest
            pool.append(entry)
            if proposal:
                proposal_attempts.append({"candidate_id": proposal["candidate_id"], "status": "qualified",
                                          "identity_digest": identity_digest, "visual_status": "not_run"})
        else:
            excluded.append({**entry,
                             "hard_failures": binding["eligibility"]["hard_failures"]})
            if proposal:
                proposal_attempts.append({"candidate_id": proposal["candidate_id"], "status": "failed",
                                          "gap": binding["eligibility"]["hard_failures"]})
    signals = page_rank_signals(pack_page)
    signals["binding_text_capacity"] = {
        entry["identity_digest"]: (
            entry["binding"].get("eligibility", {}).get("checks", {}).get("text_capacity", {}))
        for entry in pool
    }
    bank = {}
    for entry in pool:
        profile = resolver.resolve(entry["layout_id"])["data"]
        bank[entry["identity_digest"]] = {
            "ranking_layout_id": entry["layout_id"],
            "asset_id": entry["layout_id"], "aliases": profile.get("aliases", []),
            "page_type": profile.get("page_role", "content"),
            "content_capacity": profile.get("slots") or {},
            "reuse_friendly": profile.get("reuse_friendly", True),
            "renderer_support": profile.get("renderer_support") or {}}
    factor, adjust = load_style_routing(
        design_context.get("style", {}).get("asset_id"), resolver=resolver,
        page_types=set(page_types_for_role(signals["page_role"]) or []))
    ranked = rank_page(signals, bank, factor, adjust, backend, hard_qualified=True)
    pool = [{**entry, "ranking": candidate}
            for candidate in ranked["candidates"]
            for entry in sorted(pool, key=lambda row: row["identity_digest"])
            if entry["identity_digest"] == candidate["candidate_key"]]
    return {"qualified": pool, "excluded": excluded, "intent": ranked["intent"],
            "ranking": {key: ranked[key] for key in ("confidence", "score_margin", "decision", "decision_reasons")},
            "proposal_attempts": proposal_attempts}


def _canonical_layouts() -> dict[str, dict]:
    from .layout_bank import list_layout_bank
    return {entry["asset_id"]: entry for entry in list_layout_bank()}


def page_rank_signals(page: dict) -> dict:
    """把完整页表达转为与轻量入口可比较的统计分量，不授予生产资格。"""
    points = [item["text"] for item in page.get("items", []) if item.get("kind") == "point"]
    expression = page.get("expression") if isinstance(page.get("expression"), dict) else {}
    relation = expression.get("relation") if isinstance(expression.get("relation"), dict) else {}
    relation_kind = relation.get("kind") if isinstance(relation.get("kind"), str) else None
    semantic_structure = page.get("semantic_structure")
    # 明确的 reading task 可消歧；缺任务时仅采用 regime 的唯一关系映射。
    if semantic_structure in (None, "", "undecided") and relation_kind:
        regime = load_page_type_regime()
        mapped_types = [page_type for page_type, spec in regime["page_types"].items()
                        if spec.get("relation_kind") == relation_kind]
        task = expression.get("reading_task")
        if (task in mapped_types and regime.get("reading_task_relations", {}).get(task) == relation_kind):
            semantic_structure = task
        elif len(mapped_types) == 1:
            semantic_structure = mapped_types[0]
    reading_order = expression.get("reading_order")
    expression_evidence = {
        "relation_kind": relation_kind,
        "reading_task": expression.get("reading_task"),
        "focus": expression.get("focus"),
        "reading_order_count": len(reading_order) if isinstance(reading_order, list) else None,
    }
    return {"page": page.get("number"), "page_role": page.get("narrative_role") or "",
            "claim": page.get("claim"), "points": len(points), "est_chars": sum(map(len, points)),
            "data_points": sum(i.get("kind") == "number-ref" for i in page.get("items", [])),
            "image_sources": sum(i.get("kind") == "figure" for i in page.get("items", [])),
            "structures": page.get("structures", {}), "semantic_structure": semantic_structure,
            "confidence": page.get("confidence"), "argument_role": page.get("argument_role"),
            "expression_uncertainty": expression.get("uncertainty") or [],
            "expression_evidence": expression_evidence}


def _no_reuse_limit(profile: dict) -> tuple[bool, int]:
    """禁复用约束：仅 reuse_friendly=false 生效（K5：不给普通版式默加一次限制）。"""
    if profile.get("reuse_friendly") is False:
        return True, int(profile.get("max_per_deck") or 1)
    return False, 0


def allocate_deck(
    pack: dict,
    design_context: dict,
    *,
    backend: str = "render:html",
    explicit: dict[str, str] | None = None,
    candidates: list[str] | None = None,
    search_budget: int = DEFAULT_SEARCH_BUDGET,
    resolver=None,
    qualification_purpose="publication",
    provider_contract=None,
    proposal_factory=None,
) -> dict:
    """整册分配：确定性有界搜索，返回选中绑定 + 摘要 + 报告。

    输出含 ``selection``（page_id → layout_id/binding）、``top2``（面向人的
    Top-2 摘要）、``status``（``complete`` / ``no_candidates`` /
    ``budget_exhausted`` / ``explicit_unqualified``）与逐页原因。
    """
    from .asset_resolver import AssetResolver
    from .content_projection import precompile_binding

    if resolver is None:
        resolver = AssetResolver()
    explicit = explicit or {}
    pages = pack.get("pages", [])
    if not pages or type(search_budget) is not int or search_budget < 0:
        raise LayoutSelectionError("non-empty pages and non-negative integer search_budget required")
    pools: dict[str, dict] = {}
    page_status: dict[str, dict] = {}
    for page in pages:
        pid = page["page_id"]
        page_pool = qualified_pool(
            page, design_context, content_digest=pack["content_digest"],
            numbers=pack.get("numbers"), backend=backend,
            candidates=candidates, resolver=resolver, qualification_purpose=qualification_purpose,
            provider_contract=provider_contract, proposal_factory=proposal_factory)
        pools[pid] = page_pool
        explicit_query = explicit.get(pid)
        if explicit_query:
            match = next(
                (e for e in page_pool["qualified"]
                 if e["layout_id"].endswith(f":{explicit_query}")
                 or e["layout_id"] == explicit_query), None)
            if match is None:
                page_status[pid] = {
                    "status": "explicit_unqualified",
                    "reason": f"显式指定 {explicit_query} 未通过硬资格检查，"
                    "显式选择不能绕过资格入口",
                }
            else:
                page_status[pid] = {"status": "explicit", "layout_id": match["layout_id"]}
        elif not page_pool["qualified"]:
            page_status[pid] = {
                "status": "no_candidates",
                "reasons": [e["hard_failures"] for e in page_pool["excluded"][:5]],
                "proposal_attempts": page_pool["proposal_attempts"],
            }
        elif page_pool["ranking"]["decision"] == "undecided":
            page_status[pid] = {
                "status": "recommendation_undecided",
                "reason": "推荐尚不能自动裁决，保留人工选择信号",
                "score_margin": page_pool["ranking"]["score_margin"],
                "decision_reasons": page_pool["ranking"]["decision_reasons"],
            }

    if any(s["status"] == "no_candidates" for s in page_status.values()):
        return _selection_result(pack, pools, {}, page_status, "no_candidates")

    # 确定性有界搜索：硬约束 = 显式选择 + 禁复用/最大次数；其余页按排序键
    # 贪心 + 回溯（预算内）。相邻重复与结构族频率作为排序惩罚参与选择。
    order = [p["page_id"] for p in pages]
    pages_by_id = {page["page_id"]: page for page in pages}
    profiles: dict[str, dict] = {}
    for pool in pools.values():
        for entry in pool["qualified"]:
            if entry["layout_id"] not in profiles:
                profiles[entry["layout_id"]] = resolver.resolve(entry["layout_id"])["data"]

    used_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    selection: dict[str, dict] = {}
    budget_left = [search_budget]
    exhausted = [False]

    def page_candidates(pid: str) -> list[dict]:
        ranked = pools[pid]["qualified"]
        local_order = {entry["identity_digest"]: index for index, entry in enumerate(ranked)}
        # 相邻重复与结构族频率惩罚：重排（稳定键保持确定性）。
        prev = selection.get(_prev_pid(order, pid))
        prev_layout = prev["layout_id"] if prev else None
        repeated_task = _same_reading_context(
            pages_by_id.get(_prev_pid(order, pid)), pages_by_id[pid])

        def penalty(entry: dict) -> tuple:
            layout_id = entry["layout_id"]
            family = structure_family(profiles[layout_id])
            adjacent = 1 if layout_id == prev_layout and not repeated_task else 0
            family_freq = (family_counts.get(family, 0)
                           if family != UNKNOWN_FINGERPRINT and not repeated_task else 0)
            rank = entry["ranking"]
            return (-rank["raw_score"] + adjacent * 0.06 + family_freq * 0.015,
                    -rank["semantic_score"])

        # 同分且无全局惩罚时保留统一资格池的顺序，不能按另一摘要再次翻转 Top-N。
        return sorted(ranked, key=lambda e: (*penalty(e), local_order[e["identity_digest"]]))

    def search(index: int) -> bool:
        if index >= len(order):
            return True
        if budget_left[0] <= 0:
            exhausted[0] = True
            return False
        pid = order[index]
        status = page_status.get(pid, {})
        if status.get("status") == "explicit":
            entry = next(e for e in pools[pid]["qualified"]
                         if e["layout_id"] == status["layout_id"])
            choices = [entry]
        elif status.get("status") == "explicit_unqualified":
            return False
        else:
            choices = page_candidates(pid)
        for entry in choices:
            layout_id = entry["layout_id"]
            profile = profiles[layout_id]
            limited, max_count = _no_reuse_limit(profile)
            if limited and used_counts.get(layout_id, 0) >= max_count:
                continue
            budget_left[0] -= 1
            selection[pid] = entry
            used_counts[layout_id] = used_counts.get(layout_id, 0) + 1
            family = structure_family(profile)
            family_counts[family] = family_counts.get(family, 0) + 1
            if search(index + 1):
                return True
            del selection[pid]
            used_counts[layout_id] -= 1
            family_counts[family] -= 1
            if budget_left[0] <= 0:
                exhausted[0] = True
                return False
        return False

    solved = search(0)
    if not solved:
        has_explicit_failure = any(
            s["status"] == "explicit_unqualified" for s in page_status.values())
        status = ("explicit_unqualified" if has_explicit_failure
                  else "budget_exhausted" if exhausted[0] else "constraints_unsatisfied")
        return _selection_result(pack, pools, selection, page_status, status)

    for pid, entry in selection.items():
        if _same_reading_context(pages_by_id.get(_prev_pid(order, pid)), pages_by_id[pid]):
            page_status.setdefault(pid, {}).update(rhythm_context="continuous-reading-task")
        local_top = pools[pid]["qualified"][0]["layout_id"]
        if entry["layout_id"] != local_top:
            page_status.setdefault(pid, {}).update(
                local_top=local_top, selected=entry["layout_id"],
                adjustment_reason="explicit-choice" if pid in explicit else "global-reuse-or-rhythm")
    return _selection_result(pack, pools, selection, page_status, "complete")


def _same_reading_context(previous: dict | None, page: dict) -> bool:
    """仅明确同章、同阅读任务的普通内容页减免节奏惩罚。"""
    if not previous or not page.get("chapter_id") or previous.get("chapter_id") != page["chapter_id"]:
        return False
    if previous.get("narrative_role") != page.get("narrative_role"):
        return False
    allowed = page_types_for_role(page.get("narrative_role"))
    if not allowed or set(allowed) - {"content", "data"}:
        return False
    if page.get("argument_role") == "论点" or previous.get("argument_role") == "论点":
        return False
    left, right = previous.get("expression") or {}, page.get("expression") or {}
    return (page.get("semantic_structure") not in (None, "undecided")
            and previous.get("semantic_structure") == page.get("semantic_structure")
            and bool(right.get("reading_task"))
            and left.get("reading_task") == right.get("reading_task")
            and left.get("relation", {}).get("kind") == right.get("relation", {}).get("kind")
            and not left.get("uncertainty") and not right.get("uncertainty"))


def _prev_pid(order: list[str], pid: str) -> str | None:
    idx = order.index(pid)
    return order[idx - 1] if idx > 0 else None


def _selection_result(pack: dict, pools: dict, selection: dict,
                      page_status: dict, status: str) -> dict:
    chosen = {
        pid: {
            "layout_id": entry["layout_id"],
            "expression_binding_digest": entry["binding"].get("expression_binding_digest"),
            "materialization_binding_digest": entry["binding"].get("materialization_binding_digest"),
            "binding": entry["binding"],
        }
        for pid, entry in selection.items()}
    top2 = {
        pid: [e["layout_id"] for e in pool["qualified"][:2]]
        for pid, pool in pools.items()}
    return {
        "schema_version": 1,
        "kind": "deck-layout-selection",
        "policy_version": SELECTION_POLICY_VERSION,
        "status": status,
        "selection": chosen,
        "top2": top2,
        "top3": {pid: [{"identity": entry["binding"]["execution_pairing_identity"], "identity_digest": entry["identity_digest"]}
                       for entry in pool["qualified"][:3]] for pid, pool in pools.items()},
        "page_status": page_status,
        "proposal_attempts": {pid: pool.get("proposal_attempts", []) for pid, pool in pools.items()},
        "content_digest": pack.get("content_digest"),
    }


def _compact_id(entity: dict) -> str:
    """Return the stable public alias while retaining the canonical asset ID."""
    aliases = entity.get("aliases") or []
    return str(aliases[0] if aliases else entity["asset_id"])


def load_style_routing(
    style_name: str | None, *, home: Path | None = None,
    resolver: AssetResolver | None = None,
    page_types: set[str] | None = None,
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
    except (ResolverError, KeyError):
        return 1.0, {}
    bindings = style["data"].get("bindings") or {}
    factor = float(bindings.get("capacity_factor", {}).get("text", 1.0))
    adjust: dict[str, float] = {}
    for rule in bindings.get("layout_routes", []):
        route_page_type = rule.get("page_type")
        # layout_routes 是页型级合同。未知页面不应套用某个页型的风格偏好；
        # 未声明 page_type 的旧路由才视为全局规则。
        if route_page_type and (page_types is None or route_page_type not in page_types):
            continue
        for key, delta in (("preferred", 0.1), ("discouraged", -0.2)):
            for ref in rule.get(key, []) or []:
                try:
                    resolved = resolver.resolve(ref)
                    layout_id = _compact_id(resolved)
                except (ResolverError, KeyError):
                    continue
                adjust[layout_id] = adjust.get(layout_id, 0.0) + delta
    return factor, adjust


def _role_fit(page: dict, layout: dict) -> tuple[float | None, str]:
    """角色对齐分；None = 出局。"""
    role = str(page.get("page_role", ""))
    allowed = page_types_for_role(role)
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
) -> tuple[float | None, list[str]]:
    """区间包含度 × 字数覆盖度；None 表示硬超排除。"""
    reasons: list[str] = []
    capacity = layout.get("content_capacity", {})
    table = (page.get("structures") or {}).get("table")
    if isinstance(table, dict):
        if not {"rows", "columns"}.issubset(capacity):
            return None, ["显式表格结构缺少行列槽"]
        for key in ("rows", "columns"):
            limit = capacity[key].get("count_max")
            if limit is not None and len(table.get(key, [])) > limit:
                return None, [f"表格 {key} 超出容量"]
        cell_limit = capacity.get("cell", {}).get("max_chars")
        if cell_limit is not None and any(len(str(cell)) > cell_limit * factor
                                         for row in table.get("rows", []) for cell in row):
            return None, ["表格单元格超出容量"]
        return 1.0, ["按显式表格行列及单元格容量核对"]
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
            elif capacity_level(points, best["count_max"]) != "overflow":
                containment = 0.5
                reasons.append(f"条数偏多:{points}>{best['count_max']}")
            else:
                reasons.append(f"条数硬超:{points}≫{best['count_max']}")
                return None, reasons
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
            elif capacity_level(est_chars, limit) != "overflow":
                coverage = 0.5
                reasons.append(f"容量偏紧 {est_chars:.0f}/{limit:.0f} chars")
            else:
                reasons.append(
                    f"容量硬超 {est_chars:.0f}/{limit:.0f} chars"
                )
                return None, reasons
    return containment * coverage, reasons


def _binding_capacity_fit(page: dict, layout_id: str) -> tuple[float | None, list[str]]:
    """读取预编译 binding 的逐槽容量摘要，缺失时保持中性。

    这里不重算槽位映射或把软容量变成第二个资格门；硬溢出已由
    ``precompile_binding`` 排除。排序只用其已冻结的 ``used/limit/level``。
    """
    by_layout = page.get("binding_text_capacity")
    slots = by_layout.get(layout_id) if isinstance(by_layout, dict) else None
    if not isinstance(slots, dict) or not slots:
        return None, []
    observations = []
    for name, entry in sorted(slots.items()):
        if not isinstance(entry, dict):
            continue
        used, limit, level = entry.get("used"), entry.get("limit"), entry.get("level")
        if not isinstance(used, (int, float)) or not isinstance(limit, (int, float)) or limit <= 0:
            continue
        ratio = used / limit
        observations.append((str(name), used, limit, str(level or capacity_level(used, limit)), ratio))
    if not observations:
        return None, []
    tightest = max(observations, key=lambda row: row[4])
    if any(level == "overflow" for _, _, _, level, _ in observations):
        return 0.0, [f"逐槽容量硬超: {tightest[0]} {tightest[1]:.0f}/{tightest[2]:.0f}"]
    if any(level == "over" for _, _, _, level, _ in observations):
        return 0.35, [f"逐槽容量偏紧: {tightest[0]} {tightest[1]:.0f}/{tightest[2]:.0f}"]
    # 已经落在槽位中仍应反映接近上限的差别，但不得把正常内容大幅降权。
    fit = max(0.75, 1.0 - max(0.0, tightest[4] - 0.75) * 0.4)
    return fit, [f"逐槽容量余量: {tightest[0]} {tightest[1]:.0f}/{tightest[2]:.0f}"]


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


def rank_page(page: dict, bank: dict[str, dict], factor: float,
               adjust: dict[str, float], backend: str | None = None, *, hard_qualified=False) -> dict:
    known_ids = {layout.get("ranking_layout_id", key) for key, layout in bank.items()}
    intent = analyze_page_intent(page)
    candidates: list[dict] = []
    used = set(page.get("already_used") or [])
    for candidate_key in sorted(bank):
        layout = bank[candidate_key]
        layout_id = layout.get("ranking_layout_id", candidate_key)
        if backend and not layout.get("renderer_support", {}).get(backend):
            continue
        # 节奏硬排除：强视觉版式已用即出局（与 check_layout_reuse 同口径）。
        if layout.get("reuse_friendly") is False and layout_id in used:
            continue
        role_fit, role_reason = _role_fit(page, layout)
        if role_fit is None:
            if not hard_qualified:
                continue
            role_fit = 0.0
        capacity_fit, cap_reasons = _capacity_fit(page, layout, factor)
        if capacity_fit is None:
            if not hard_qualified:
                continue
            capacity_fit = 0.0
        binding_capacity_fit, binding_capacity_reasons = _binding_capacity_fit(page, candidate_key)
        if binding_capacity_fit is not None:
            # 硬资格后使用实际槽位读数，避免总量估算盖过已完成的绑定；
            # 轻量调用仍保留总量预筛，缺少 binding 的输入保持原行为。
            capacity_fit = (binding_capacity_fit if hard_qualified
                            else capacity_fit * 0.6 + binding_capacity_fit * 0.4)
        rhythm, rhythm_reasons = _rhythm(page, layout_id, layout)
        semantic_id = _compact_id({"aliases": layout.get("aliases", []), "asset_id": layout_id})
        routing = adjust.get(layout_id, adjust.get(semantic_id, 0.0))
        semantic, semantic_reason = semantic_layout_adjustment(semantic_id, intent)
        score = (
            W_ROLE * role_fit + W_CAPACITY * capacity_fit + W_RHYTHM * rhythm
            + routing + semantic
        )
        raw_score = score
        score = max(0.0, min(1.0, score))
        reasons = [role_reason, *cap_reasons, *binding_capacity_reasons, *rhythm_reasons]
        evidence = page.get("expression_evidence")
        if isinstance(evidence, dict) and any(value is not None for value in evidence.values()):
            details = []
            if evidence.get("relation_kind"):
                details.append("relation=" + str(evidence["relation_kind"]))
            if evidence.get("reading_task"):
                details.append("task=" + str(evidence["reading_task"]))
            if evidence.get("focus"):
                details.append("focus=" + str(evidence["focus"]))
            if evidence.get("reading_order_count") is not None:
                details.append("order=" + str(evidence["reading_order_count"]))
            if details:
                reasons.append("冻结表达: " + ", ".join(details))
        if routing:
            reasons.append(
                f"风格路由 {'+' if routing > 0 else ''}{routing:.1f}"
            )
        if semantic_reason:
            reasons.append(semantic_reason)
        candidates.append(
            {
                "layout": layout_id,
                "score": round(score, 2),
                "semantic_score": round(semantic, 2),
                "raw_score": round(raw_score, 6),
                "_raw_score": raw_score,
                "reasons": reasons,
                "renderer_support": layout.get("renderer_support", {}),
            }
        )
        if candidate_key != layout_id:
            candidates[-1]["candidate_key"] = candidate_key
    # score 在历史合同中封顶 1.0；同分时用语义层级稳定打破并列，避免
    # 一个“容量刚好”的通用模板遮住内容形态的首选/回退版式。
    candidates.sort(key=lambda c: (-c["_raw_score"], -c["semantic_score"], c["layout"], c.get("candidate_key", "")))
    top = candidates
    confidence = top[0]["score"] if top else 0.0
    score_margin = (top[0]["_raw_score"] - top[1]["_raw_score"]
                    if len(top) > 1 else None)
    decision_reasons = []
    if confidence < CONFIDENCE_FLOOR:
        decision_reasons.append("首选绝对分未达到自动选择阈值")
    if intent["decision"] != "auto":
        decision_reasons.append("页面语义尚未达到自动判定置信度")
    if page.get("expression_uncertainty"):
        decision_reasons.append("冻结表达仍有待确认项，需人工裁决")
    if score_margin is not None and score_margin < SCORE_MARGIN_FLOOR:
        decision_reasons.append("前两候选分差不足，需人工裁决")
    # 禁编造 id：防御断言——输出 id 必须全部来自枚举集。
    for cand in top:
        if cand["layout"] not in known_ids:
            raise LayoutSelectionError("fabricated_layout_id")
        cand.pop("_raw_score", None)
    return {
        "page": page.get("page"),
        "candidates": top,
        "confidence": round(confidence, 2),
        "score_margin": round(score_margin, 6) if score_margin is not None else None,
        "intent": intent,
        # 语义层低置信时即使容量分数较高也保留人工裁决出口。
        "decision_reasons": decision_reasons,
        "decision": "auto" if not decision_reasons else "undecided",
    }


# --------------------------------------------------------------------------- #
# U10/R-74 lane 成本读数（KTD3：附加读出面，不改语义排序主键）
# --------------------------------------------------------------------------- #

DEFAULT_LANES = ("image", "render:html")
ATMOSPHERE_VISUAL_WEIGHT = "high"


def lane_cost_comparison(
    *,
    backend_stats_path,
    visual_weight: str | None = None,
    allowed_lanes=None,
    frozen_backend: str | None = None,
) -> dict:
    """资格集合内的 lane 成本对比读数；纯附加，供呈现与人工裁决。

    口径（R-74/AE-74）：
    - 成本只读 ``backend_stats.jsonl`` 的真实生产记录（tokens 为记录累计，
      不乘 attempts）；无记录的 lane 报 ``unknown``，不回退假设带。
    - ``visual_weight=high``（氛围页）受保护：不输出任何成本改道建议。
    - ``frozen_backend`` 冻结后不自动切换：建议恒为保持，且仅在非冻结、
      非保护、双方都有观测时给出 advisory。
    - 与 ``page_intent`` 的内容分类正交：本函数不读版式、不参与
      ``rank_page`` 排序，语义主键不受影响。
    """

    from .storage import canonical_json_bytes  # 统一复用，不引入第二套序列化

    del canonical_json_bytes  # 显式声明：本函数只读不写，序列化不在此发生
    lanes = tuple(allowed_lanes) if allowed_lanes else DEFAULT_LANES
    rows: list[dict] = []
    if backend_stats_path is not None:
        path = Path(backend_stats_path)
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    rows.append(entry)
    lanes_out = []
    for lane in lanes:
        lane_rows = [row for row in rows if row.get("backend") == lane]
        token_rows = [row["tokens"] for row in lane_rows
                      if isinstance(row.get("tokens"), int)]
        attempts = sum(max(1, int(row.get("attempts", 1) or 1)) for row in lane_rows)
        if token_rows and attempts:
            tokens_total = sum(token_rows)
            lanes_out.append({
                "lane": lane,
                "basis": "observed",
                "pages": attempts,
                "tokens_total": tokens_total,
                "tokens_per_page": round(tokens_total / attempts, 1),
            })
        else:
            lanes_out.append({
                "lane": lane,
                "basis": "unknown",
                "pages": attempts,
                "tokens_total": None,
                "tokens_per_page": None,
            })
    protected = visual_weight == ATMOSPHERE_VISUAL_WEIGHT
    recommendation = None
    if protected:
        reason = "atmosphere-protection"
    elif frozen_backend is not None:
        reason = "frozen-backend-no-auto-switch"
    elif all(lane["basis"] == "observed" for lane in lanes_out) and len(lanes_out) > 1:
        cheapest = min(lanes_out, key=lambda lane: lane["tokens_per_page"])
        recommendation = cheapest["lane"]
        reason = "observed-cost-advisory"
    else:
        reason = "insufficient-cost-evidence"
    return {
        "schema_version": 1,
        "kind": "lane-cost-comparison",
        "lanes": lanes_out,
        "visual_weight": visual_weight,
        "protected": protected,
        "frozen_backend": frozen_backend,
        "recommendation": recommendation,
        "reason": reason,
        "advisory_only": True,
        "note": "读数不改写语义排序；真实改道须走 runtime 修订通道并更新页级 provenance",
    }
