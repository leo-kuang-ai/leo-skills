"""layout-bank sidecar 只读加载器（layout-bank-v1，B1）。

双层结构：版式层（``references/styles/12_版式库/<stem>.layouts.json``，36 份
唯一真值）+ 风格层（``references/styles/<风格名>.layouts.json``，11 份薄路由
视图，只引用不复制）。本模块只做只读查询（``leo-ppt style layouts``）；
``compose_style`` / ``compose_layout`` 渲染路径零改动——sidecar 不进 render
输出（render 字节确定红线）。

归一化采用防御式 setdefault 模式。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .styles import StyleStoreError, builtin_style_path


class LayoutBankError(StyleStoreError):
    """layout-bank sidecar 读取失败的稳定 reason code 族。"""

    reason_code = "layout_bank_error"


class CapacityFilterError(LayoutBankError):
    """``--capacity`` 条件语法错误的稳定 reason code（信封边界不坍缩）。"""

    reason_code = "capacity_filter_invalid"


def _styles_root() -> Path:
    return builtin_style_path("_placeholder").parent


def _layout_dir() -> Path:
    return _styles_root() / "12_版式库"


def _fail(code: str, detail: str) -> "LayoutBankError":
    return LayoutBankError(f"{code}: {detail}")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise _fail("layout_bank_unreadable", str(path)) from exc
    except json.JSONDecodeError as exc:
        raise _fail("layout_bank_invalid", f"{path.name} ({exc})") from exc
    if not isinstance(data, dict):
        raise _fail("layout_bank_invalid", f"{path.name} 不是 JSON 对象")
    return data


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_layout(data: dict, path: Path) -> dict:
    """防御式归一化：缺键补默认、类型不对即 fail-fast（adapted 模式）。"""
    if data.get("entity") != "layout":
        raise _fail("layout_bank_invalid", f"{path.name} entity != 'layout'")
    layout_id = data.get("layout_id")
    if not isinstance(layout_id, str) or not layout_id:
        raise _fail("layout_bank_invalid", f"{path.name} 缺 layout_id")
    data.setdefault("name", layout_id)
    data.setdefault("page_type", "content")
    capacity = data.setdefault("content_capacity", {})
    if not isinstance(capacity, dict) or not capacity:
        raise _fail(
            "layout_bank_invalid", f"{path.name} content_capacity 为空"
        )
    data.setdefault("best_for", [])
    data.setdefault("avoid_for", [])
    data.setdefault("reuse_friendly", True)
    data.setdefault("max_per_deck", 1 if not data["reuse_friendly"] else None)
    return data


def _layout_sidecar_path(layout_id: str) -> Path:
    for path in sorted(_layout_dir().glob("*.layouts.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("layout_id") == layout_id:
            return path
    raise _fail("layout_bank_not_found", layout_id)


def load_layout_bank(layout_id: str) -> dict:
    """按 P 码读版式 sidecar（含文件 sha256 指纹，服务 CI-2 资产指纹）。

    fail-fast：未知 P 码报 ``layout_bank_not_found``；JSON 不可解析/结构非法
    报 ``layout_bank_invalid`` / ``layout_bank_unreadable``。
    """
    path = _layout_sidecar_path(layout_id)
    data = _read_json(path)
    data = _normalize_layout(data, path)
    data["sha256"] = _sha256_of(path)
    data["source"] = str(path.relative_to(_styles_root().parent))
    return data


def load_style_layouts(style_name: str) -> dict:
    """读内置风格薄路由视图（routing 引用 + capacity_factor + 文件指纹）。

    悬空引用在加载边界拒绝（对齐"Markdown-only 在加载边界拒绝"的上游纪律）：
    routing 引用了版式库中不存在的 P 码即报 ``layout_bank_invalid``。
    """
    path = _styles_root() / f"{style_name}.layouts.json"
    if not path.is_file():
        raise _fail("layout_bank_not_found", f"{style_name} 的路由视图缺失")
    data = _read_json(path)
    if data.get("entity") != "style-layout-bank":
        raise _fail(
            "layout_bank_invalid", f"{path.name} entity != 'style-layout-bank'"
        )
    data.setdefault("style_id", style_name)
    factor = data.setdefault("capacity_factor", {})
    if not isinstance(factor, dict):
        raise _fail("layout_bank_invalid", f"{path.name} capacity_factor 非对象")
    factor.setdefault("text", 1.0)
    routing = data.setdefault("routing", [])
    if not isinstance(routing, list) or not routing:
        raise _fail("layout_bank_invalid", f"{path.name} routing 为空")
    known = {item["layout_id"] for item in list_layout_bank()}
    for rule in routing:
        if not isinstance(rule, dict):
            raise _fail("layout_bank_invalid", f"{path.name} routing 项非对象")
        rule.setdefault("preferred", [])
        rule.setdefault("discouraged", [])
        for key in ("preferred", "discouraged"):
            for ref in rule[key]:
                if ref not in known:
                    raise _fail(
                        "layout_bank_invalid",
                        f"{path.name} 悬空版式引用 {ref!r}",
                    )
    data["sha256"] = _sha256_of(path)
    data["source"] = str(path.relative_to(_styles_root().parent))
    return data


def list_layout_bank() -> list[dict]:
    """枚举 36 版式 sidecar 摘要（layout_id/name/page_type/reuse_friendly/
    max_per_deck/sha256，按 layout_id 排序，确定性输出）。"""
    items: list[dict] = []
    for path, data in _iter_layout_sidecars():
        items.append(
            {
                "layout_id": data.get("layout_id"),
                "name": data.get("name"),
                "page_type": data.get("page_type"),
                "reuse_friendly": bool(data.get("reuse_friendly", True)),
                "max_per_deck": data.get(
                    "max_per_deck", 1 if not data.get("reuse_friendly", True) else None
                ),
                "sha256": _sha256_of(path),
            }
        )
    items.sort(key=lambda item: str(item["layout_id"]))
    return items


def _iter_layout_sidecars():
    """按路径序产出 ``(path, data)``；读取失败或 entity 不符的文件跳过。

    list 与 capacity 过滤共用的遍历入口，避免两份逐字重复的 sidecar 扫描块。
    """
    for path in sorted(_layout_dir().glob("*.layouts.json")):
        try:
            data = _read_json(path)
            if data.get("entity") != "layout":
                continue
        except LayoutBankError:
            continue
        yield path, data


def _parse_capacity_conditions(text: str) -> list[tuple[str, int]]:
    """解析 ``槽名<=N`` 逗号分隔条件（仅支持 ``<=``，MVP 语义：够小才装得下）。

    语法错误抛 ``CapacityFilterError``（reason_code=capacity_filter_invalid），
    保证 CLI 信封边界拿到稳定错误码而非泛化 layout_bank_error。
    """
    conditions: list[tuple[str, int]] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "<=" not in chunk:
            raise CapacityFilterError(
                f"capacity_filter_invalid: {chunk!r} 缺 <= 操作符"
                "（语法：槽名<=N，逗号分隔）"
            )
        slot, _, bound = chunk.partition("<=")
        slot = slot.strip()
        if not slot:
            raise CapacityFilterError(
                "capacity_filter_invalid: 空槽名（语法：槽名<=N）"
            )
        try:
            limit = int(bound.strip())
        except ValueError:
            raise CapacityFilterError(
                f"capacity_filter_invalid: {bound!r} 不是整数"
            ) from None
        conditions.append((slot, limit))
    if not conditions:
        raise CapacityFilterError("capacity_filter_invalid: 空条件")
    return conditions


def _slot_upper_bound(slot_def: dict) -> int | None:
    """槽位容量上限：计数槽取 ``count_max``，文本槽取 ``max_chars``。"""
    for key in ("count_max", "max_chars"):
        value = slot_def.get(key)
        if isinstance(value, int):
            return value
    return None


def filter_layout_bank_by_capacity(conditions: str) -> dict:
    """按容量条件筛选版式（UB2 容量查询面，只读，不进 render 路径）。

    判定语义：``items<=6`` 要求该版式 ``items`` 槽的上限（``count_max``，无则
    ``max_chars``）≤ 6；多条件 AND。槽不存在的版式不匹配（该版式无此槽位
    概念，属正常不匹配）；**槽存在但既无 ``count_max`` 也无 ``max_chars`` 的
    版式进 ``missing``（如实报缺，不静默通过）**。来源思想：dashi 容量选页
    硬条件（title-chars/item-count），2026-09-02 落地。
    """
    parsed = _parse_capacity_conditions(conditions)
    matched: list[dict] = []
    missing: dict[str, list[str]] = {}
    for path, data in _iter_layout_sidecars():
        layout_id = data.get("layout_id")
        capacity = data.get("content_capacity") or {}
        ok = True
        bounds: dict[str, int] = {}
        miss_slots: list[str] = []
        for slot, limit in parsed:
            slot_def = capacity.get(slot)
            if not isinstance(slot_def, dict):
                ok = False
                continue  # 不 break：后续条件的缺键槽仍要如实进 missing
            bound = _slot_upper_bound(slot_def)
            if bound is None:
                miss_slots.append(slot)
                ok = False
                continue
            if bound > limit:
                ok = False
            bounds[slot] = bound
        if miss_slots:
            missing[str(layout_id)] = miss_slots
        if ok:
            matched.append(
                {
                    "layout_id": layout_id,
                    "name": data.get("name"),
                    "page_type": data.get("page_type"),
                    "capacity_bounds": bounds,
                    "sha256": _sha256_of(path),
                }
            )
    matched.sort(key=lambda item: str(item["layout_id"]))
    return {"matched": matched, "missing": missing}
