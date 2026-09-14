"""content_projection.py — 候选绑定预编译与选定后物化（dashi 集成 K3/U3）。

两阶段（方案 K3 表）：
  1. 候选预编译：已冻结内容包 + 同一设计上下文 + 候选 layout/template + 页级
     backend → 只读候选绑定（内容项 ID → 槽位/数据路径、完整显示值引用、
     媒体引用与使用策略、输入/资产/编译器摘要）。不需要 resolved design，
     不调用 Provider。
  2. 选定后物化：selected 绑定 + 由该绑定生成的冻结设计 → HTML data 或
     image prompt 输入。复用同一绑定——不重新概括内容、不重选布局、不改字号。

硬资格检查（K2 顺序：内容包 + 设计上下文 → 角色规范化 → 候选预编译 →
容量/媒体/backend/必需内容覆盖 → 合格池）：硬失败候选不合格，软评分不可
抵消；无合格候选返回待定与具体原因。角色映射唯一来自
page-type-regime-v2 治理文件。
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from .template_inputs import display_texts, field_errors, validate_template_data

PROJECTION_COMPILER = {"name": "leo-ppt-generator/content_projection", "version": "2"}

CANONICAL_PAGE_ROLES = ("cover", "agenda", "section", "content", "data", "closing")

def page_types_for_role(role: str | None) -> list[str] | None:
    """Derive role/page-type view exclusively from page-type-regime-v2."""
    if not role:
        return None
    from .page_intent import load_page_type_regime
    role = role.strip()
    result = []
    for ptype, spec in load_page_type_regime().get("page_types", {}).items():
        if role in (spec.get("role_aliases") or []):
            result.extend(spec.get("layout_page_types") or [ptype])
    return sorted(set(result)) or None


# 模板输入字段的显示文本族（string 且名字在此集合 → 承载 claim/要点文本）。
TITLE_FIELD_NAMES = {
    "title", "quote", "kicker", "subtitle", "caption",
    "source_name", "source_meta", "footer_left", "footer_right",
}
# 媒体类输入字段类型：承载图行/媒体引用（数据由执行期素材填充）。
MEDIA_FIELD_TYPES = {"data-uri", "image", "media"}
PAGE_NO_FIELD_NAMES = {"page_no"}


class ProjectionError(ValueError):
    reason_code = "content_projection_invalid"


def normalize_page_role(narrative_role: str | None) -> list[str] | None:
    """中文叙事角色 → canonical page_type 集合；未知角色返回 None。"""
    if not narrative_role:
        return None
    return page_types_for_role(narrative_role)


from .storage import canonical_json_bytes as _canonical_json


def _sha(value) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def expression_choice_identity(page: dict) -> dict:
    from .page_intent import load_page_type_regime
    expression = page.get("expression")
    regime = load_page_type_regime()
    return {"page_expression_digest": _sha(expression), "expression": deepcopy(expression),
            "primary_expression": page.get("semantic_structure"),
            "supporting_expression": page.get("media_role"),
            "selection_policy_revision": "expression-policy-v1", "regime_revision": _sha(regime)}


def _effective_page_digest(page):
    return _sha({key: value for key, value in page.items() if key not in {"number", "master_page"}})


def compute_expression_binding_digest(binding: dict) -> str:
    """lane-neutral；不使用映射后的 item_ids、catalog、主题、slot 或执行资产。"""
    return _sha({"page_id": binding["page_id"], "page_content_digest": binding["page_content_digest"],
                 "page_expression_digest": binding["page_expression_digest"],
                 "expression_choice_identity": binding["expression_choice_identity"]})


def compute_materialization_binding_digest(binding: dict) -> str:
    """每条 lane 的实际执行身份；整册完整性摘要和展示页号不参与失效。"""
    return _sha({"expression_binding_digest": compute_expression_binding_digest(binding),
                 "execution_pairing_identity": binding["execution_pairing_identity"],
                 "layout_id": binding["layout_id"], "template_id": binding["template_id"],
                 "recipe_id": binding["recipe_id"], "backend": binding["backend"],
                 "qualification_purpose": binding["qualification_purpose"],
                 "display_page_number": binding["number"],
                 "slot_map": binding["slot_map"], "effective": binding["effective"],
                 "eligibility": binding["eligibility"], "proposal": binding.get("proposal")})


def verify_dual_binding_digests(binding: dict) -> None:
    """仅接收完整 binding/v2；旧字段、缺字段和新旧混用返回同一错误。"""
    if (not isinstance(binding, dict) or binding.get("schema_version") != 2
            or "binding_digest" in binding or not binding.get("expression_binding_digest")
            or not binding.get("materialization_binding_digest")):
        raise ProjectionError("binding_schema_mismatch")
    try:
        verify_binding_reference(binding)
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).parent / "schemas/binding-v2.schema.json").read_text())
        if list(Draft202012Validator(schema).iter_errors(binding)):
            raise ProjectionError("binding_schema_mismatch")
        expression = compute_expression_binding_digest(binding)
        materialization = compute_materialization_binding_digest(binding)
        if binding["eligibility"].get("qualified"):
            from .execution_pairing import pairing_key
            from .qualification import qualification_admits
            pairing_key(binding["execution_pairing_identity"])
            if (not binding["page_content_digest"] or not binding["expression_choice_identity"].get("expression")
                    or not qualification_admits(binding["eligibility"].get("checks", {}).get("qualification", {}),
                                                purpose=binding["qualification_purpose"])):
                raise ProjectionError("binding_schema_mismatch")
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectionError("binding_schema_mismatch") from exc
    if binding["expression_binding_digest"] != expression:
        raise ProjectionError("expression_binding_digest_mismatch")
    if binding["materialization_binding_digest"] != materialization:
        raise ProjectionError("materialization_binding_digest_mismatch")


def verify_binding_reference(reference, expected=None):
    """receipt/selection/RunIndex 只引用两级摘要；不可把一种摘要当作另一种。"""
    import re
    fields = ("expression_binding_digest", "materialization_binding_digest")
    if (not isinstance(reference, dict) or "binding_digest" in reference
            or any(not isinstance(reference.get(key), str)
                   or not re.fullmatch(r"[0-9a-f]{64}", reference[key]) for key in fields)):
        raise ProjectionError("binding_schema_mismatch")
    if expected is not None:
        verify_binding_reference(expected)
        for key in fields:
            if reference[key] != expected[key]:
                raise ProjectionError(key + "_mismatch")
        if reference.get("backend") is not None and reference.get("backend") != expected.get("backend"):
            raise ProjectionError("materialization_binding_lane_mismatch")


def verify_effective_binding(binding: dict, pack_page: dict, *, resolver=None,
                             frozen_design: dict | None = None) -> None:
    """校验同一 binding/v2、页面和冻结资产；不接受旧 run 的隐式降级。"""
    verify_dual_binding_digests(binding)
    if binding.get("page_id") != pack_page.get("page_id"):
        raise ProjectionError("effective_binding_page_mismatch")
    effective = binding["effective"]
    if effective.get("page_digest") != _effective_page_digest(pack_page):
        raise ProjectionError("effective_binding_content_changed")
    if frozen_design is not None:
        from .templates import _design_digest
        if (frozen_design.get("design_digest") != _design_digest(frozen_design)
                or frozen_design.get("effective_theme") != effective.get("theme")):
            raise ProjectionError("effective_binding_design_mismatch")
        if frozen_design.get("design_context_digest") != binding["context_digest"]:
            raise ProjectionError("effective_binding_design_mismatch")
        selected = next((p for p in frozen_design.get("pages", [])
                         if p.get("page_id") == pack_page.get("page_id")), None)
        if selected is None or selected.get("layout_id") != binding["layout_id"]:
            raise ProjectionError("effective_binding_layout_mismatch")
    if resolver is None:
        from .asset_resolver import AssetResolver
        resolver = AssetResolver()
    from .asset_resolver import ResolverError
    for pin in effective.get("assets", []):
        try:
            current = resolver.fingerprint(pin["asset_id"])
        except (ResolverError, OSError) as exc:
            raise ProjectionError(f"effective_binding_asset_unavailable: {pin['asset_id']}") from exc
        if current != pin:
            raise ProjectionError(f"effective_binding_asset_changed: {pin['asset_id']}")
    from .qualification import QualificationError, verify_bound_qualification
    try:
        verify_bound_qualification(binding["eligibility"]["checks"].get("qualification", {}),
            layout_entity=resolver.resolve(binding["layout_id"]), resolver=resolver,
            relation=pack_page["expression"]["relation"]["kind"], lane=binding["backend"],
            purpose=binding["qualification_purpose"])
    except (QualificationError, KeyError, TypeError) as exc:
        raise ProjectionError(str(exc)) from exc


def load_run_binding(run_path: str | Path, page_identity: str | int, *, backend: str | None = None) -> dict:
    """生成/record 必须读取完整冻结 binding/v2，不能退回无绑定执行。"""
    from .asset_resolver import AssetResolver
    from .content_pack import verify_content_pack

    from .application.expression_pipeline import load_committed_input
    committed = load_committed_input(run_path)
    root = committed["root"]
    selections = committed["payload"]["lane_selections"]
    if backend is None and len(selections) != 1:
        raise ProjectionError("materialization_binding_lane_required")
    backend = backend or next(iter(selections))
    if backend not in selections:
        raise ProjectionError("materialization_binding_lane_unsupported")
    selection = selections[backend]
    if str(selection.get("policy_version")) != "2" or selection.get("status") != "complete":
        raise ProjectionError("effective_binding_selection_invalid")
    pack = json.loads((root / "page-content-pack.json").read_text(encoding="utf-8"))
    verify_content_pack(pack)
    page = next((p for p in pack["pages"] if p["page_id"] == page_identity
                 or (isinstance(page_identity, int) and p["number"] == page_identity)), None)
    if page is None:
        raise ProjectionError("effective_binding_page_mismatch")
    entry = (selection.get("selection") or {}).get(page["page_id"]) or {}
    binding = entry.get("binding") or {}
    if (binding.get("schema_version") != 2
            or "binding_digest" in binding or "binding_digest" in entry
            or not entry.get("expression_binding_digest") or not entry.get("materialization_binding_digest")
            or binding.get("expression_binding_digest") != entry["expression_binding_digest"]
            or binding.get("materialization_binding_digest") != entry["materialization_binding_digest"]
            or binding.get("layout_id") != entry.get("layout_id")
            or binding.get("content_digest") != pack["content_digest"]
            or selection.get("content_digest") != pack["content_digest"]
            or not binding.get("effective", {}).get("assets")):
        raise ProjectionError("binding_schema_mismatch")
    resolver = AssetResolver.from_snapshot(root / "asset-snapshot")
    design = committed["payload"]["designs"][backend]
    verify_effective_binding(binding, page, resolver=resolver, frozen_design=design)
    return {"binding": binding, "pack_page": page, "resolver": resolver}


def _field_count_bounds(field: dict) -> tuple[int | None, int | None]:
    return field.get("count_min"), field.get("count_max")


def _slot_for_field(field_name: str, profile: dict) -> dict | None:
    return (profile.get("slots") or {}).get(field_name)


def _items_of(pack_page: dict, kind: str) -> list[dict]:
    return [i for i in pack_page.get("items", []) if i.get("kind") == kind]


def precompile_binding(
    pack_page: dict,
    design_context: dict,
    layout_query: str,
    *,
    backend: str = "render:html",
    content_digest: str,
    numbers: list[dict] | None = None,
    resolver=None,
    qualification_purpose="publication",
    provider_contract=None,
) -> dict:
    """候选绑定预编译：硬资格检查 + 只读映射；不合格也返回（带原因）。

    ``design_context`` 来自 ``templates.resolve_design_context``（K2 共用
    快照）。返回的绑定不包含 resolved design，不调用 Provider；``qualified``
    为 False 时绑定不得进入合格池/被物化。
    """
    from .asset_resolver import AssetResolver, ResolverError
    from .render.layout import capacity_level, validate_profile

    if resolver is None:
        resolver = AssetResolver()
    numbers = numbers or []

    hard_failures: list[str] = []
    checks: dict[str, dict] = {}

    # 角色规范化：未知角色或角色不匹配 → 硬失败（K2）。
    role_types = normalize_page_role(pack_page.get("narrative_role"))
    requested_pairing = None
    try:
        if isinstance(layout_query, dict):
            from .execution_pairing import pairing_key
            requested_pairing = layout_query.get("identity", layout_query)
            pairing_key(requested_pairing)
            layout_entity = resolver.resolve(requested_pairing["layout_identity"]["asset_id"])
        else:
            layout_entity = resolver.require(layout_query, kind="layout")
        profile = layout_entity["data"]
        validate_profile(profile)
    except ResolverError as exc:
        raise ProjectionError(f"content_projection_invalid: {exc}") from exc
    layout_role = profile.get("page_role")
    if role_types is None:
        hard_failures.append(
            f"role_unknown: 页面角色「{pack_page.get('narrative_role')}」不在角色映射内，"
            "不能自动入选（回母版补明确角色或人工选择）")
        checks["role"] = {"result": "unknown"}
    elif layout_role not in role_types:
        hard_failures.append(
            f"role_mismatch: 页面角色「{pack_page.get('narrative_role')}」→ "
            f"{sorted(set(role_types))}，候选 layout 为 {layout_role}")
        checks["role"] = {"result": "mismatch", "expected": sorted(set(role_types)),
                          "actual": layout_role}
    else:
        checks["role"] = {"result": "ok"}

    # backend 能力：layout.renderer_support 必须声明该 backend。
    # render:html 的值是 template asset_id（可解析 manifest）；image 的值是
    # 构图说明文本（K5：不是结构指纹），不作为资产解析，容量预检直接用
    # layout slots 声明。
    renderer = profile.get("renderer_support") or {}
    template_id = renderer.get(backend)
    if not template_id:
        hard_failures.append(
            f"backend_unsupported: layout 未声明 backend {backend}")
        checks["backend"] = {"result": "unsupported"}
    else:
        checks["backend"] = {"result": "ok", "template_id": template_id}

    template_manifest = None
    if template_id and backend == "render:html":
        try:
            template_entity = resolver.resolve(template_id)
            template_manifest = template_entity["data"]
        except ResolverError as exc:
            raise ProjectionError(
                f"content_projection_invalid: 模板解析失败 {template_id}: {exc}") from exc

    recipe = None
    if backend == "image":
        try:
            from .config.backend_contract import BackendRegistry
            from .image_deck.recipe import validate_recipe
            if not provider_contract:
                raise ValueError("provider_contract_missing")
            BackendRegistry.default().load(provider_contract, required={"generate"})
            if provider_contract["mode"] != "generate":
                raise ValueError("provider_contract_mode_mismatch")
            recipe = resolver.resolve(profile.get("image_recipe", ""))
            validate_recipe(recipe["data"], profile)
        except ValueError as exc:
            hard_failures.append(str(exc))

    points = _items_of(pack_page, "point")
    figures = _items_of(pack_page, "figure")
    number_refs = _items_of(pack_page, "number-ref")
    claim = pack_page.get("claim")
    sides = (pack_page.get("structures") or {}).get("sides")
    table = (pack_page.get("structures") or {}).get("table")
    explicit_fields = (pack_page.get("structures") or {}).get("fields") or {}

    slot_map: dict[str, dict] = {}
    mapped_item_ids: set[str] = set()
    bound_structured_texts: list[str] = []
    if explicit_fields and backend != "render:html" and recipe is None:
        hard_failures.append("structured_backend_unsupported: 结构数据需要声明输入合同的 HTML 模板")

    if template_manifest is None and template_id and backend != "render:html":
        # image 等 lane：无模板 manifest，容量预检直接用 layout slots 声明
        #（K2：image 使用已声明的字数/条数/媒体容量作预检；几何为指导性，
        # 预检资格与成品 QA 分别记录，预检不冒充最终像素布局可用）。
        declared_slots = profile.get("slots") or {}
        points_slot = next((s for s in declared_slots.values()
                            if s.get("content_type") == "points"), None)
        if points_slot is not None:
            count_min, count_max = points_slot.get("count_min"), points_slot.get("count_max")
            if count_max is not None and len(points) > count_max:
                hard_failures.append(
                    f"points_over_max: 要点 {len(points)} > 声明上限 {count_max}（预检排除）")
            if count_min is not None and len(points) < count_min:
                hard_failures.append(
                    f"points_below_min: 要点 {len(points)} < 声明下限 {count_min}（预检排除）")
            checks.setdefault("points", {"count": len(points),
                                         "count_min": count_min,
                                         "count_max": count_max})
        for idx, point in enumerate(points):
            slot_map[f"points[{idx}]"] = {"source": "point", "item_id": point["item_id"]}
            mapped_item_ids.add(point["item_id"])
        text_slot = next((s for s in declared_slots.values()
                          if s.get("content_type") == "text"), None)
        if claim and text_slot is not None and text_slot.get("max_chars"):
            level = capacity_level(len(claim), text_slot["max_chars"])
            checks.setdefault("text_capacity", {})["claim"] = {
                "used": len(claim), "limit": text_slot["max_chars"], "level": level}
            if level == "overflow":
                hard_failures.append(
                    f"text_overflow: claim 字数 {len(claim)} 硬超声明容量 "
                    f"{text_slot['max_chars']}（image 预检）")
        media_slots = [name for name, s in declared_slots.items()
                       if s.get("content_type") == "media"]
        media_cap = sum((declared_slots[name].get("count_max") or 1)
                        for name in media_slots) if media_slots else 0
        checks.setdefault("media", {"declared_capacity": media_cap})
        if figures:
            if len(figures) > media_cap:
                hard_failures.append(
                    f"media_over_capacity: 媒体需求 {len(figures)} > 声明能力 {media_cap}")
            else:
                for idx, figure in enumerate(figures):
                    slot_map[f"media[{idx}]"] = {"source": "figure",
                                                 "item_id": figure["item_id"]}
                    mapped_item_ids.add(figure["item_id"])
        if claim:
            slot_map["claim"] = {"source": "claim"}
        if recipe is not None:
            # recipe 完整携带结构数据；只有独立输出 oracle 能证明成图保真。
            def collect_values(value):
                if isinstance(value, dict):
                    for child in value.values(): collect_values(child)
                elif isinstance(value, list):
                    for child in value: collect_values(child)
                elif isinstance(value, (str, int, float)):
                    bound_structured_texts.append(str(value))
            collect_values(pack_page.get("structures", {}))

    if template_manifest is not None:
        fields = template_manifest.get("input_fields") or []
        has_title_field = any(f.get("name") == "title" for f in fields)
        claim_field = "title" if has_title_field else next(
            (f.get("name") for f in fields
             if f.get("name") in TITLE_FIELD_NAMES and f.get("required")), None)
        by_name = {f["name"]: f for f in fields}
        for name, value in explicit_fields.items():
            if name not in by_name or name in PAGE_NO_FIELD_NAMES:
                hard_failures.append(f"structured_field_unknown: {name} 无可绑定显示字段")
                continue
            if name == claim_field and value != claim:
                hard_failures.append(f"claim_conflict: {name} 与母版标题不一致")
                continue
            errors = field_errors(by_name[name], value)
            if errors:
                hard_failures.extend(f"structured_field_invalid: {e}" for e in errors)
                continue
            slot_map[name] = {"source": "structures.fields", "field": name}
            bound_structured_texts.extend(display_texts({name: value}))
        for point in points:
            if point.get("text") in bound_structured_texts:
                mapped_item_ids.add(point["item_id"])
        for field in fields:
            name = field.get("name")
            ftype = (field.get("type") or "").lower()
            required = bool(field.get("required"))
            count_min, count_max = _field_count_bounds(field)
            # 同名 layout slot 提供计数容量（交叉校验：两处声明冲突即拒绝）。
            slot = _slot_for_field(name, profile)
            if slot is not None and slot.get("count_min") is not None:
                s_min, s_max = slot.get("count_min"), slot.get("count_max")
                if count_min is not None and count_min != s_min:
                    raise ProjectionError(
                        "content_projection_invalid: 字段 count_min 冲突 "
                        f"({name}: template={count_min}, layout={s_min})")
                if count_max is not None and s_max is not None and count_max != s_max:
                    raise ProjectionError(
                        "content_projection_invalid: 字段 count_max 冲突 "
                        f"({name}: template={count_max}, layout={s_max})")
                count_min, count_max = s_min, s_max
            if name in explicit_fields:
                continue
            if name in PAGE_NO_FIELD_NAMES:
                slot_map[name] = {"source": "page_number"}
                continue
            if ftype in MEDIA_FIELD_TYPES:
                # 媒体槽：能力来自声明；数量能力 = count_max（缺省按已声明槽 1）。
                media_cap = count_max if count_max is not None else 1
                checks.setdefault("media", {"declared_capacity": media_cap})
                if figures:
                    if len(figures) > media_cap:
                        hard_failures.append(
                            f"media_over_capacity: 媒体需求 {len(figures)} > 声明能力 {media_cap}")
                    for idx, figure in enumerate(figures):
                        slot_map[name if len(figures) == 1 else f"{name}[{idx}]"] = {
                            "source": "figure", "item_id": figure["item_id"]}
                        mapped_item_ids.add(figure["item_id"])
                continue
            if ftype == "array" and name in ("columns", "rows") and table is not None:
                value = table.get(name)
                errors = field_errors(field, value)
                if errors:
                    hard_failures.extend(f"structured_field_invalid: {e}" for e in errors)
                else:
                    slot_map[name] = {"source": f"structures.table.{name}"}
                    bound_structured_texts.extend(display_texts(value))
                continue
            if ftype == "array" and isinstance(field.get("items"), dict):
                # 嵌套结构输入（如 compare sides）：结构必须来自母版标记。
                if name == "sides":
                    if not sides:
                        if required:
                            hard_failures.append(
                                "required_item_unmapped: 母版未声明对照侧标记"
                                "（对照侧: 标签｜标题｜要点），sides 无来源；"
                                "回母版补结构标记，不由编译器猜测")
                        continue
                    if count_min is not None and len(sides) < count_min:
                        hard_failures.append(
                            f"sides_count_below_min: 对照侧 {len(sides)} < 声明下限 {count_min}")
                    if count_max is not None and len(sides) > count_max:
                        hard_failures.append(
                            f"sides_count_over_max: 对照侧 {len(sides)} > 声明上限 {count_max}")
                    slot_map["sides"] = {"source": "structures.sides",
                                         "count": len(sides)}
                    hard_failures.extend(f"structured_field_invalid: {e}"
                                         for e in field_errors(field, sides))
                    bound_structured_texts.extend(display_texts(sides))
                    for side in sides:
                        for point_text in side.get("points", []):
                            match = next((p for p in points
                                          if p.get("text") == point_text), None)
                            if match:
                                mapped_item_ids.add(match["item_id"])
                continue
            if ftype == "array":
                # 字符串数组（bullets/steps）：承载要点项，计数容量来自 slot。
                bound_points = [p for p in points
                                if p["item_id"] not in mapped_item_ids]
                if count_min is not None and len(bound_points) < count_min and required:
                    hard_failures.append(
                        f"points_below_min: 要点 {len(bound_points)} < 声明下限 {count_min}")
                if count_max is not None and len(bound_points) > count_max:
                    hard_failures.append(
                        f"points_over_max: 要点 {len(bound_points)} > 声明上限 {count_max}"
                        "（硬超排除；降档或换版式，不缩字号）")
                for idx, point in enumerate(bound_points):
                    slot_map[f"{name}[{idx}]"] = {"source": "point",
                                                  "item_id": point["item_id"]}
                    mapped_item_ids.add(point["item_id"])
                checks.setdefault("points", {"count": len(bound_points),
                                             "count_min": count_min,
                                             "count_max": count_max})
                continue
            if ftype == "string" and name in TITLE_FIELD_NAMES:
                if name == claim_field and claim:
                    slot_map[name] = {"source": "claim"}
                else:
                    # 剩余未映射要点按声明顺序填充其他显示字段（可见落位）。
                    fallback = next((p for p in points
                                     if p["item_id"] not in mapped_item_ids), None)
                    if fallback is not None:
                        slot_map[name] = {"source": "point",
                                          "item_id": fallback["item_id"]}
                        mapped_item_ids.add(fallback["item_id"])
                # 字符容量：layout slot 声明 max_chars 时做硬检查（三态）。
                if slot is not None and slot.get("max_chars"):
                    ref = slot_map.get(name, {})
                    text = claim if ref.get("source") == "claim" else next(
                        (p.get("text") for p in points
                         if p["item_id"] == ref.get("item_id")), "")
                    if text:
                        level = capacity_level(len(text), slot["max_chars"])
                        checks.setdefault("text_capacity", {})[name] = {
                            "used": len(text), "limit": slot["max_chars"],
                            "level": level}
                        if level == "overflow":
                            hard_failures.append(
                                f"text_overflow: {name} 字数 {len(text)} 硬超 "
                                f"声明容量 {slot['max_chars']}（×1.2 容差内为软超）")
                continue

        # 必需内容覆盖：任何 required 项无落点 → 硬失败（AE：字段无落点直接拒绝）。
        required_template_fields = [f["name"] for f in fields if f.get("required")]
        bound_fields = {key.split("[")[0] for key in slot_map}
        missing_fields = [f for f in required_template_fields
                          if f not in bound_fields and f not in PAGE_NO_FIELD_NAMES]
        for missing in missing_fields:
            hard_failures.append(f"required_item_unmapped: 必填字段 {missing} 无内容来源")

    unmapped = [i["item_id"] for i in pack_page.get("items", [])
                if i.get("required") and i["item_id"] not in mapped_item_ids
                and i.get("kind") != "number-ref"]
    if unmapped:
        hard_failures.append(
            f"required_item_unmapped: 必需内容项无槽位落点 {sorted(unmapped)}")

    # 数值覆盖：每个 number-ref 的数值必须出现在某个已绑定显示文本中。
    if number_refs:
        bound_texts = []
        for key, ref in slot_map.items():
            if ref.get("source") == "claim":
                bound_texts.append(claim or "")
            elif ref.get("source") == "point":
                item = next((p for p in points if p["item_id"] == ref["item_id"]), None)
                if item:
                    bound_texts.append(item.get("text") or "")
        bound_texts.extend(bound_structured_texts)
        missing_numbers = []
        for ref in number_refs:
            entry = next((n for n in numbers if n["item_id"] == ref["number_item_id"]), None)
            if entry is None:
                missing_numbers.append(ref["number_item_id"])
            elif not any(entry["value"] in text for text in bound_texts):
                missing_numbers.append(f"{ref['number_item_id']}({entry['value']})")
        if missing_numbers:
            hard_failures.append(
                f"number_coverage_missing: 数值未出现在任何绑定显示文本 {missing_numbers}")

    binding = {
        "schema_version": 2,
        "kind": "candidate-binding",
        "page_id": pack_page.get("page_id"),
        "number": pack_page.get("number"),
        "layout_id": layout_entity["asset_id"],
        "template_id": template_id if backend == "render:html" else None,
        "backend": backend,
        "qualification_purpose": qualification_purpose,
        "recipe_id": profile.get("image_recipe") if backend == "image" else None,
        "execution_pairing_identity": None,
        "expression_choice_identity": expression_choice_identity(pack_page),
        "page_content_digest": pack_page.get("page_content_digest"),
        "page_expression_digest": _sha(pack_page.get("expression")),
        "effective": {"generation": getattr(resolver, "generation", None),
                      "page_digest": _effective_page_digest(pack_page),
                      "theme": deepcopy(design_context.get("effective", {})), "assets": []},
        "slot_map": slot_map,
        "item_ids": sorted(mapped_item_ids),
        "context_digest": design_context["context_digest"],
        "content_digest": content_digest,
        "compiler": dict(PROJECTION_COMPILER),
        "eligibility": {
            "qualified": not hard_failures,
            "hard_failures": hard_failures,
            "checks": checks,
        },
    }
    if hasattr(resolver, "fingerprint"):
        asset_ids = {layout_entity["asset_id"]}
        if template_manifest is not None:
            asset_ids.add(template_id)
        if recipe is not None:
            asset_ids.add(recipe["asset_id"])
        for key in ("style", "theme_entity"):
            entity = design_context.get(key)
            if entity:
                asset_ids.add(entity["asset_id"])
        for font in design_context.get("effective", {}).get("fonts", {}).values():
            if isinstance(font, dict) and font.get("family"):
                asset_ids.add(resolver.require(font["family"], kind="font")["asset_id"])
        # 依赖闭包固定在同一 resolver generation，不重新做名称选择。
        dependencies = set(asset_ids)
        for asset_id in sorted(asset_ids - {design_context.get("style", {}).get("asset_id")}):
            dependencies.update(e["asset_id"] for e in resolver.resolve_dependencies(asset_id))
        binding["schema_version"] = 2
        binding["effective"] = {
            "generation": resolver.generation,
            "page_digest": _effective_page_digest(pack_page),
            "theme": {key: deepcopy(design_context.get("effective", {}).get(key, {}))
                      for key in ("colors", "fonts", "chart_palette")},
            "assets": [resolver.fingerprint(a) for a in sorted(dependencies)],
        }
        if backend == "image":
            from .storage import json_document_bytes
            binding["effective"]["provider_contract_sha256"] = hashlib.sha256(json_document_bytes(provider_contract)).hexdigest() if provider_contract else None
            refs = set((pack_page.get("expression") or {}).get("fact_refs", []))
            binding["effective"]["number_facts"] = [deepcopy(n) for n in numbers if n["item_id"] in refs]
    if template_manifest is not None and not hard_failures and not figures:
        errors = validate_template_data(template_manifest, _materialize_html_data(binding, pack_page))
        if errors:
            hard_failures.extend(f"template_input_invalid: {e}" for e in errors)
    # 投影/容量验证完成后统一核验证据；explicit 与自动候选没有旁路。
    from .content_pack import ContentPackError, compile_page_expression
    from .qualification import QualificationError, qualify_layout, qualification_admits
    expression = pack_page.get("expression")
    try:
        if not isinstance(expression, dict):
            raise ContentPackError("expression_incomplete: page expression required")
        compiled = compile_page_expression({"pages": [pack_page], "numbers": numbers}, pack_page["page_id"],
            reading_task=expression.get("reading_task"), focus=expression.get("focus"),
            reading_order=expression.get("reading_order"), relation_encoding=(expression.get("relation") or {}).get("encoding"),
            fact_refs=expression.get("fact_refs"), uncertainty=expression.get("uncertainty"))
        if compiled != expression:
            raise ContentPackError("expression_declaration_conflict")
        qualification = qualify_layout(layout_entity, resolver=resolver,
            relation=expression["relation"]["kind"], lane=backend)
        checks["qualification"] = qualification
        admitted = qualification_admits(qualification, purpose=qualification_purpose)
        if admitted:
            from .execution_pairing import pairing_identity
            executable = resolver.resolve(template_id if backend == "render:html" else profile["image_recipe"])
            binding["execution_pairing_identity"] = pairing_identity(layout=layout_entity, executable=executable,
                lane=backend, catalog_generation=resolver.generation,
                evidence_digest=qualification["evidence_set_digest"])
            if requested_pairing is not None and requested_pairing != binding["execution_pairing_identity"]:
                hard_failures.append("execution_pairing_stale")
        if not admitted:
            hard_failures.extend(["capability_unqualified: " + reason for reason in qualification["gaps"]]
                                 or ["capability_unqualified: " + qualification["status"]])
    except (ContentPackError, QualificationError) as exc:
        hard_failures.append(str(exc))
        checks["qualification"] = {"status": "rejected", "gaps": [str(exc)]}
    binding["eligibility"]["qualified"] = not hard_failures
    binding["expression_binding_digest"] = compute_expression_binding_digest(binding)
    binding["materialization_binding_digest"] = compute_materialization_binding_digest(binding)
    return binding


def materialize_html(binding: dict, pack_page: dict, *, media: dict | None = None,
                     resolver=None) -> dict:
    """选定后物化（render:html）：绑定 → 模板 data dict。

    复用同一绑定：值直接来自内容包显示值；媒体字段值由执行期素材提供
    （``media``：figure item_id → data-uri）。缺媒体值即拒绝，不留空图。
    """
    verify_effective_binding(binding, pack_page, resolver=resolver)
    if not binding.get("eligibility", {}).get("qualified"):
        raise ProjectionError(
            "content_projection_invalid: 绑定不合格，不得物化 "
            f"({binding['eligibility']['hard_failures'][:3]})")
    return _materialize_html_data(binding, pack_page, media=media)


def _materialize_html_data(binding, pack_page, *, media=None):
    """候选容量检查复用纯字段投影；只有公开 materialize_html 执行绑定资格校验。"""
    points = {i["item_id"]: i for i in pack_page.get("items", [])
              if i.get("kind") == "point"}
    sides = (pack_page.get("structures") or {}).get("sides")
    table = (pack_page.get("structures") or {}).get("table")
    data: dict = {}
    for key, ref in binding["slot_map"].items():
        field, _, idx_s = key.partition("[")
        if ref.get("source") == "page_number":
            data[field] = pack_page.get("number")
        elif ref.get("source") == "claim":
            data.setdefault(field, pack_page.get("claim"))
        elif ref.get("source") == "structures.fields":
            fields = (pack_page.get("structures") or {}).get("fields") or {}
            if ref["field"] not in fields:
                raise ProjectionError(f"content_projection_invalid: 结构字段缺失 {ref['field']}")
            data[field] = deepcopy(fields[ref["field"]])
        elif (ref.get("source") or "").startswith("structures.table."):
            column = ref["source"].rsplit(".", 1)[-1]
            value = (table or {}).get(column)
            if value is None:
                raise ProjectionError(
                    f"content_projection_invalid: 绑定引用的表格结构缺失 {column}")
            data[field] = deepcopy(value)
        elif ref.get("source") == "point":
            item = points.get(ref["item_id"])
            if item is None:
                raise ProjectionError(
                    f"content_projection_invalid: 绑定引用的内容项缺失 {ref['item_id']}")
            idx = int(idx_s.rstrip("]")) if idx_s else None
            if idx is None:
                data[field] = item.get("text")
            else:
                data.setdefault(field, [])
                while len(data[field]) <= idx:
                    data[field].append(None)
                data[field][idx] = item.get("text")
        elif ref.get("source") == "figure":
            uri = (media or {}).get(ref["item_id"])
            if not uri:
                raise ProjectionError(
                    f"content_projection_invalid: 媒体内容缺失 figure {ref['item_id']}"
                    "（执行期素材未提供，拒绝空媒体）")
            if idx_s:
                idx = int(idx_s.rstrip("]"))
                data.setdefault(field, [])
                while len(data[field]) <= idx:
                    data[field].append(None)
                data[field][idx] = uri
            else:
                data[field] = uri
        elif ref.get("source") == "structures.sides":
            data[field] = [
                {"label": s.get("label"), "title": s.get("title"),
                 "points": list(s.get("points") or [])}
                for s in sides or []]
    return data


def materialize_image_prompt(binding: dict, pack_page: dict,
                             frozen_design: dict | None = None, *, resolver=None) -> dict:
    """选定后物化（image）：绑定 → prompt 输入与必需文本清单。

    image 预检不冒充成品保真：``required_text`` 是生成合同输入，真实图片
    文字保真由成品 QA 核验（方案 K3/7.1）。
    """
    verify_effective_binding(binding, pack_page, resolver=resolver, frozen_design=frozen_design)
    if not binding.get("eligibility", {}).get("qualified"):
        raise ProjectionError(
            "content_projection_invalid: 绑定不合格，不得物化 "
            f"({binding['eligibility']['hard_failures'][:3]})")
    from .asset_resolver import AssetResolver
    from .image_deck.recipe import project_recipe
    resolver = resolver or AssetResolver()
    prompt_inputs = project_recipe(resolver.resolve(binding["recipe_id"])["data"], page=pack_page,
        layout=resolver.resolve(binding["layout_id"])["data"], theme=binding["effective"]["theme"],
        numbers=binding["effective"]["number_facts"])
    for name in ("content_digest", "expression_binding_digest", "materialization_binding_digest"):
        prompt_inputs[name] = binding[name]
    return prompt_inputs


def materialize_page(binding: dict, pack_page: dict,
                     frozen_design: dict | None = None,
                     *, media: dict | None = None, resolver=None) -> dict:
    """按绑定的 backend 物化；同绑定同输入结果确定。"""
    if binding["backend"] == "render:html":
        return {"backend": "render:html",
                "data": materialize_html(binding, pack_page, media=media, resolver=resolver)}
    if binding["backend"] == "image":
        return {"backend": "image",
                **materialize_image_prompt(binding, pack_page, frozen_design, resolver=resolver)}
    raise ProjectionError(
        f"content_projection_invalid: 未知 backend {binding['backend']}")


def binding_impact(before: dict, after: dict) -> dict:
    """从两份真实 binding 集合计算最小页/lane 失效，不接受手工 changed 标记。"""
    for snapshot in (before, after):
        if not isinstance(snapshot, dict):
            raise ProjectionError("binding_schema_mismatch")
        expressions = {}
        for lane, pages in snapshot.items():
            if lane not in {"render:html", "image"} or not isinstance(pages, dict):
                raise ProjectionError("binding_schema_mismatch")
            for pid, binding in pages.items():
                verify_dual_binding_digests(binding)
                if binding["page_id"] != pid or binding["backend"] != lane:
                    raise ProjectionError("binding_schema_mismatch")
                if pid in expressions and expressions[pid] != binding["expression_binding_digest"]:
                    raise ProjectionError("expression_binding_lane_mismatch")
                expressions[pid] = binding["expression_binding_digest"]
    ids = {pid for snapshot in (before, after) for pages in snapshot.values() for pid in pages}
    pages = {}
    for pid in sorted(ids):
        lanes, reasons = {}, set()
        expression_stale = False
        for lane in sorted(set(before) | set(after)):
            old, new = before.get(lane, {}).get(pid), after.get(lane, {}).get(pid)
            if old is None and new is None:
                continue
            changed = []
            if old is None or new is None:
                changed.append("lane")
                # 新增/删除整页的表达也失效；仅增加一条 lane 时表达仍可复用。
                if not any(pid in entries for entries in (before if old is None else after).values()):
                    changed.append("content")
            else:
                if old["page_content_digest"] != new["page_content_digest"]:
                    changed.append("content")
                if old["expression_choice_identity"] != new["expression_choice_identity"]:
                    changed.append("expression")
                if old["effective"].get("theme") != new["effective"].get("theme"):
                    changed.append("theme")
                if any(old.get(key) != new.get(key) for key in ("execution_pairing_identity", "slot_map", "proposal")) or old["effective"].get("assets") != new["effective"].get("assets"):
                    changed.append("asset")
                if old["number"] != new["number"]:
                    changed.append("display_order")
                if not changed and old["materialization_binding_digest"] != new["materialization_binding_digest"]:
                    changed.append("asset")
            reasons.update(changed)
            expression_stale |= bool({"content", "expression"}.intersection(changed))
            lanes[lane] = {"status": "stale" if changed else "passed", "reasons": sorted(set(changed))}
        pages[pid] = {"page_id": pid, "reasons": sorted(reasons), "status": "stale" if reasons else "passed",
                      "expression_status": "stale" if expression_stale else "passed", "materializations": lanes}
    content = {pid: binding["page_content_digest"] for entries in after.values() for pid, binding in entries.items()}
    expression = {pid: binding["expression_binding_digest"] for entries in after.values() for pid, binding in entries.items()}
    return {"schema_version": 2, "input_digests": {"before": _sha(before), "after": _sha(after)},
            "content_digest": _sha(content), "expression_digest": _sha(expression), "pages": pages}
