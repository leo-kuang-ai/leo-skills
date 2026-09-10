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
抵消；无合格候选返回待定与具体原因。角色映射的唯一所有者是本模块的
``ROLE_PAGE_TYPES``（scripts/suggest_layout.py 等从这里导入）。
"""
from __future__ import annotations

import hashlib
import json

PROJECTION_COMPILER = {"name": "leo-ppt-generator/content_projection", "version": "1"}

CANONICAL_PAGE_ROLES = ("cover", "agenda", "section", "content", "data", "closing")

# 13_页面语义 25 角色 → 版式 page_type（6 值枚举）。未列角色按未知处理，
# 不能自动入选。仅补真正缺少的别名，不另起角色系统（K2）。
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
    # evidence 版式（frame-shot 等）此前无角色入口——K2「仅补真正缺少的别名」。
    "证据·实拍": ["evidence"],
}

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
    return ROLE_PAGE_TYPES.get(narrative_role.strip())


from .storage import canonical_json_bytes as _canonical_json


def _sha(value) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def compute_binding_digest(binding: dict) -> str:
    """绑定摘要：同输入重编译必须相同；覆盖 page/资产/上下文/内容/编译器。"""
    digest_input = {
        "page_id": binding["page_id"],
        "layout_id": binding["layout_id"],
        "template_id": binding["template_id"],
        "backend": binding["backend"],
        "slot_map": binding["slot_map"],
        "item_ids": sorted(binding["item_ids"]),
        "context_digest": binding["context_digest"],
        "content_digest": binding["content_digest"],
        "compiler": binding["compiler"],
    }
    return _sha(digest_input)


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
    try:
        layout_entity = (resolver.require(layout_query, kind="layout")
                          if isinstance(layout_query, str)
                          else resolver.resolve(layout_query))
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

    points = _items_of(pack_page, "point")
    figures = _items_of(pack_page, "figure")
    number_refs = _items_of(pack_page, "number-ref")
    claim = pack_page.get("claim")
    sides = (pack_page.get("structures") or {}).get("sides")
    table = (pack_page.get("structures") or {}).get("table")

    slot_map: dict[str, dict] = {}
    mapped_item_ids: set[str] = set()

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

    if template_manifest is not None:
        fields = template_manifest.get("input_fields") or []
        has_title_field = any(f.get("name") == "title" for f in fields)
        claim_field = "title" if has_title_field else next(
            (f.get("name") for f in fields
             if f.get("name") in TITLE_FIELD_NAMES and f.get("required")), None)
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
                    for side in sides:
                        for point_text in side.get("points", []):
                            match = next((p for p in points
                                          if p.get("text") == point_text), None)
                            if match:
                                mapped_item_ids.add(match["item_id"])
                continue
            if ftype == "array":
                if name in ("columns", "rows") and table is not None:
                    # K6 台账/矩阵结构：columns/rows 来自母版 表列/表行 标记。
                    slot_map[name] = {"source": f"structures.table.{name}"}
                    continue
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
        for side in sides or []:
            bound_texts.append(side.get("title") or "")
            bound_texts.extend(side.get("points") or [])
        if table is not None:
            bound_texts.extend(table.get("columns") or [])
            for row in table.get("rows") or []:
                bound_texts.extend(cell for cell in row if isinstance(cell, str))
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
        "schema_version": 1,
        "kind": "candidate-binding",
        "page_id": pack_page.get("page_id"),
        "number": pack_page.get("number"),
        "layout_id": layout_entity["asset_id"],
        "template_id": template_id,
        "backend": backend,
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
    binding["binding_digest"] = compute_binding_digest(binding)
    return binding


def materialize_html(binding: dict, pack_page: dict, *, media: dict | None = None) -> dict:
    """选定后物化（render:html）：绑定 → 模板 data dict。

    复用同一绑定：值直接来自内容包显示值；媒体字段值由执行期素材提供
    （``media``：figure item_id → data-uri）。缺媒体值即拒绝，不留空图。
    """
    if not binding.get("eligibility", {}).get("qualified"):
        raise ProjectionError(
            "content_projection_invalid: 绑定不合格，不得物化 "
            f"({binding['eligibility']['hard_failures'][:3]})")
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
        elif (ref.get("source") or "").startswith("structures.table."):
            column = ref["source"].rsplit(".", 1)[-1]
            value = (table or {}).get(column)
            if value is None:
                raise ProjectionError(
                    f"content_projection_invalid: 绑定引用的表格结构缺失 {column}")
            data[field] = value
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
                             frozen_design: dict | None = None) -> dict:
    """选定后物化（image）：绑定 → prompt 输入与必需文本清单。

    image 预检不冒充成品保真：``required_text`` 是生成合同输入，真实图片
    文字保真由成品 QA 核验（方案 K3/7.1）。
    """
    from .templates import project_design_to_prompt

    if not binding.get("eligibility", {}).get("qualified"):
        raise ProjectionError(
            "content_projection_invalid: 绑定不合格，不得物化 "
            f"({binding['eligibility']['hard_failures'][:3]})")
    points = [i for i in pack_page.get("items", []) if i.get("kind") == "point"]
    required_text = [pack_page.get("claim")] + [p.get("text") for p in points]
    prompt_inputs: dict = {
        "page_id": pack_page.get("page_id"),
        "layout_id": binding["layout_id"],
        "composition": (binding.get("eligibility", {}).get("checks", {})
                        .get("backend", {}).get("template_id")),
        "required_text": [t for t in required_text if t],
        "content_digest": binding["content_digest"],
        "binding_digest": binding["binding_digest"],
    }
    if frozen_design is not None:
        page_for_prompt = {
            "page_no": pack_page.get("number"),
            "page_role": pack_page.get("narrative_role"),
            "layout": binding["layout_id"],
            "slots": {},
        }
        projected = project_design_to_prompt(frozen_design, page_for_prompt)
        prompt_inputs["style_projection"] = projected
    return prompt_inputs


def materialize_page(binding: dict, pack_page: dict,
                     frozen_design: dict | None = None,
                     *, media: dict | None = None) -> dict:
    """按绑定的 backend 物化；同绑定同输入结果确定。"""
    if binding["backend"] == "render:html":
        return {"backend": "render:html",
                "data": materialize_html(binding, pack_page, media=media)}
    if binding["backend"] == "image":
        return {"backend": "image",
                **materialize_image_prompt(binding, pack_page, frozen_design)}
    raise ProjectionError(
        f"content_projection_invalid: 未知 backend {binding['backend']}")
