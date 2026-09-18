"""layout-bank 只读加载器（v2：新库 layout 实体，U10 切换）。

旧 ``12_版式库`` sidecar 已迁入 template-library/canonical/layouts（几何/
容量真值）与 brief.bindings.layout_routes（风格路由）。本模块只做只读查询
（``leo-ppt style layouts``）；身份解析委托 asset_resolver，不扫描目录。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .asset_resolver import AssetResolver, ResolverError
from .styles import StyleStoreError


class LayoutBankError(StyleStoreError):
    """layout 读取失败的稳定 reason code 族。"""

    reason_code = "layout_bank_error"


class CapacityFilterError(LayoutBankError):
    """``--capacity`` 条件语法错误的稳定 reason code（信封边界不坍缩）。"""

    reason_code = "capacity_filter_invalid"


def _resolver() -> AssetResolver:
    try:
        return AssetResolver()
    except ResolverError as exc:
        raise LayoutBankError(f"layout_bank_library_missing: {exc}") from exc


def _require(query: str, *, kind: str) -> dict:
    """resolver 查询失败统一映射为 LayoutBankError（稳定 reason code 族）。"""
    try:
        return _resolver().require(query, kind=kind)
    except ResolverError as exc:
        raise LayoutBankError(f"layout_bank_not_found: {query} ({exc.reason_code})") from exc


def _fail(code: str, detail: str) -> "LayoutBankError":
    return LayoutBankError(f"{code}: {detail}")


def load_layout_bank(layout_id: str) -> dict:
    """按 P 码别名或完整 ID 读版式（含文件 sha256 指纹，服务 CI-2 资产指纹）。"""
    resolved = _require(layout_id, kind="layout")
    data = dict(resolved["data"])
    data["sha256"] = hashlib.sha256(Path(resolved["path"]).read_bytes()).hexdigest()
    data["source"] = resolved["relative_path"]
    data["layout_id"] = data.get("aliases", [None])[0] or resolved["asset_id"]
    return data


def load_style_layouts(style_name: str) -> dict:
    """读风格路由视图（brief.bindings.layout_routes + capacity_factor）。"""
    resolved = _require(style_name, kind="style")
    brief = resolved["data"]
    bindings = brief.get("bindings") or {}
    routes = bindings.get("layout_routes") or []
    if not routes:
        raise _fail("layout_bank_not_found", f"{style_name} 的路由视图缺失")
    known = {entity["asset_id"] for entity in _resolver().entities
             if entity["kind"] == "layout"}
    for rule in routes:
        for key in ("preferred", "discouraged"):
            for ref in rule.get(key) or []:
                if ref not in known:
                    raise _fail("layout_bank_invalid", f"悬空版式引用 {ref!r}")
    return {
        "entity": "style-layout-bank",
        "style_id": resolved["asset_id"],
        "capacity_factor": bindings.get("capacity_factor") or {"text": 1.0},
        "routing": routes,
        "sha256": hashlib.sha256(Path(resolved["path"]).read_bytes()).hexdigest(),
        "source": resolved["relative_path"],
    }


def list_layout_bank() -> list[dict]:
    """枚举版式摘要（layout_id/name/page_role/容量上限/sha256，确定性输出）。"""
    items: list[dict] = []
    for entity in _resolver().entities:
        if entity["kind"] != "layout":
            continue
        data = entity.get("data") or {}
        if not data:
            resolved = _resolver().resolve(entity["asset_id"])
            data = resolved["data"]
        items.append({
            "layout_id": (data.get("aliases") or [entity["asset_id"]])[0],
            "asset_id": entity["asset_id"],
            "name": data.get("name"),
            "page_type": data.get("page_role"),
            "slots": sorted((data.get("slots") or {}).keys()),
            "sha256": hashlib.sha256(
                (Path(entity["trusted_root"]) / entity["path"]).read_bytes()).hexdigest(),
        })
    # 紧凑码（P 码 / html-lane slug）字典序，asset_id 作次键保证全序
    items.sort(key=lambda item: (str(item["layout_id"]), str(item["asset_id"])))
    return items


def _parse_capacity_conditions(text: str) -> list[tuple[str, int]]:
    """解析 ``槽名<=N`` 逗号分隔条件（仅 ``<=``，MVP 语义：够小才装得下）。"""
    conditions: list[tuple[str, int]] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "<=" not in chunk:
            raise CapacityFilterError(
                f"capacity_filter_invalid: {chunk!r} 缺 <= 操作符（语法：槽名<=N，逗号分隔）")
        slot, _, bound = chunk.partition("<=")
        slot = slot.strip()
        if not slot:
            raise CapacityFilterError("capacity_filter_invalid: 空槽名（语法：槽名<=N）")
        try:
            limit = int(bound.strip())
        except ValueError:
            raise CapacityFilterError(
                f"capacity_filter_invalid: {bound!r} 不是整数") from None
        conditions.append((slot, limit))
    if not conditions:
        raise CapacityFilterError("capacity_filter_invalid: 空条件")
    return conditions


def _slot_upper_bound(slot_def: dict) -> int | None:
    for key in ("count_max", "max_chars"):
        value = slot_def.get(key)
        if isinstance(value, int):
            return value
    return None


def filter_layout_bank_by_capacity(conditions: str) -> dict:
    """按容量条件筛选版式（UB2 容量查询面，只读，不进 render 路径）。

    判定语义与旧合同一致：``items<=6`` 要求该槽上限 ≤ 6；多条件 AND；槽不
    存在的版式不匹配；槽存在但无上限的版式进 ``missing``（如实报缺）。
    """
    parsed = _parse_capacity_conditions(conditions)
    resolver = _resolver()
    matched: list[dict] = []
    missing: dict[str, list[str]] = {}
    for entity in resolver.entities:
        if entity["kind"] != "layout":
            continue
        data = resolver.resolve(entity["asset_id"])["data"]
        capacity = data.get("slots") or {}
        ok = True
        bounds: dict[str, int] = {}
        miss_slots: list[str] = []
        for slot, limit in parsed:
            slot_def = capacity.get(slot)
            if not isinstance(slot_def, dict):
                ok = False
                continue
            bound = _slot_upper_bound(slot_def)
            if bound is None:
                miss_slots.append(slot)
                ok = False
                continue
            if bound > limit:
                ok = False
            bounds[slot] = bound
        layout_id = (data.get("aliases") or [entity["asset_id"]])[0]
        if miss_slots:
            missing[str(layout_id)] = miss_slots
        if ok:
            matched.append({
                "layout_id": layout_id,
                "asset_id": entity["asset_id"],
                "name": data.get("name"),
                "page_type": data.get("page_role"),
                "capacity_bounds": bounds,
            })
    matched.sort(key=lambda item: str(item["asset_id"]))
    return {"matched": matched, "missing": missing}
