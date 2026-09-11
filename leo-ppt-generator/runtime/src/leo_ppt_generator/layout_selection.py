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

SELECTION_POLICY_VERSION = "1"
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
) -> dict:
    """完整合格候选池（K5）：全部候选跑硬资格；不合格带原因保留在
    ``excluded``，供「无合格候选返回原因」与准入报告使用。
    """
    from .asset_resolver import AssetResolver
    from .content_projection import precompile_binding

    if resolver is None:
        resolver = AssetResolver()
    if candidates is None:
        candidates = sorted(_canonical_layouts())
    pool: list[dict] = []
    excluded: list[dict] = []
    for query in candidates:
        binding = precompile_binding(
            pack_page, design_context, query, backend=backend,
            content_digest=content_digest, numbers=numbers, resolver=resolver)
        entry = {
            "layout_id": binding["layout_id"],
            "binding": binding,
        }
        if binding["eligibility"]["qualified"]:
            pool.append(entry)
        else:
            excluded.append({**entry,
                             "hard_failures": binding["eligibility"]["hard_failures"]})
    return {"qualified": pool, "excluded": excluded}


def _canonical_layouts() -> dict[str, dict]:
    from .layout_bank import list_layout_bank
    return {entry["asset_id"]: entry for entry in list_layout_bank()}


def _soft_rank(pack_page: dict, binding: dict, profile: dict) -> tuple:
    """整册匹配排序键（确定性）：结构声明优先于 unknown，容量余量大的优先，
    平分按资产 ID。"""
    fingerprint = structure_fingerprint(profile)
    points = sum(1 for i in pack_page.get("items", []) if i.get("kind") == "point")
    checks = binding["eligibility"]["checks"]
    slot = (checks.get("points") or {}) if isinstance(checks, dict) else {}
    count_max = slot.get("count_max")
    headroom = (count_max - points) if isinstance(count_max, (int, float)) else 0
    return (
        0 if fingerprint != UNKNOWN_FINGERPRINT else 1,  # unknown 无加分
        -headroom,  # 余量大者优先（稳定降序 → 负号升序）
        binding["layout_id"],  # 稳定平分裁决
    )


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
    pools: dict[str, dict] = {}
    page_status: dict[str, dict] = {}
    for page in pages:
        pid = page["page_id"]
        page_pool = qualified_pool(
            page, design_context, content_digest=pack["content_digest"],
            numbers=pack.get("numbers"), backend=backend,
            candidates=candidates, resolver=resolver)
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
            }

    if any(s["status"] == "no_candidates" for s in page_status.values()):
        return _selection_result(pack, pools, {}, page_status, "no_candidates")

    # 确定性有界搜索：硬约束 = 显式选择 + 禁复用/最大次数；其余页按排序键
    # 贪心 + 回溯（预算内）。相邻重复与结构族频率作为排序惩罚参与选择。
    order = [p["page_id"] for p in pages]
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
        ranked = sorted(
            pools[pid]["qualified"],
            key=lambda e: _soft_rank(
                next(p for p in pages if p["page_id"] == pid),
                e["binding"], profiles[e["layout_id"]]))
        # 相邻重复与结构族频率惩罚：重排（稳定键保持确定性）。
        prev = selection.get(_prev_pid(order, pid))
        prev_layout = prev["layout_id"] if prev else None
        prev_family = (structure_family(profiles[prev_layout])
                       if prev_layout in profiles else None)

        def penalty(entry: dict) -> tuple:
            layout_id = entry["layout_id"]
            family = structure_family(profiles[layout_id])
            adjacent = 1 if layout_id == prev_layout else 0
            family_freq = family_counts.get(family, 0)
            return (adjacent, family_freq)

        return sorted(ranked, key=lambda e: (*penalty(e), e["layout_id"]))

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
                  else "budget_exhausted")
        return _selection_result(pack, pools, selection, page_status, status)

    return _selection_result(pack, pools, selection, page_status, "complete")


def _prev_pid(order: list[str], pid: str) -> str | None:
    idx = order.index(pid)
    return order[idx - 1] if idx > 0 else None


def _selection_result(pack: dict, pools: dict, selection: dict,
                      page_status: dict, status: str) -> dict:
    chosen = {
        pid: {
            "layout_id": entry["layout_id"],
            "binding_digest": entry["binding"]["binding_digest"],
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
        "page_status": page_status,
        "content_digest": pack.get("content_digest"),
    }
