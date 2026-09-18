"""image recipe 的正式 owner；只投影冻结内容，不能授予渲染或视觉资格。"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from string import Formatter

from ..storage import canonical_json_bytes


class ImageRecipeError(ValueError):
    pass


def validate_recipe(recipe, layout=None):
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).parents[1] / "schemas/image-recipe-v1.schema.json").read_text())
    if list(Draft202012Validator(schema).iter_errors(recipe)):
        raise ImageRecipeError("image_recipe_schema_mismatch")
    fields = []
    try:
        for _, name, spec, conversion in Formatter().parse(recipe["prompt_skeleton"]):
            if name is not None:
                if spec or conversion or name not in {"content", "expression", "theme", "layout"}:
                    raise ImageRecipeError("image_recipe_placeholder_invalid")
                fields.append(name)
    except ValueError as exc:
        raise ImageRecipeError("image_recipe_placeholder_invalid") from exc
    if sorted(fields) != ["content", "expression", "layout", "theme"]:
        raise ImageRecipeError("image_recipe_projection_incomplete")
    if layout is not None:
        if layout["asset_id"] not in recipe["layout_profiles"]:
            raise ImageRecipeError("image_recipe_layout_mismatch")
        if set(layout["slots"]) != set(recipe["slot_map"]):
            raise ImageRecipeError("image_recipe_slot_closure_missing")
        for name, slot in layout["slots"].items():
            if recipe["slot_map"][name]["content_type"] != slot.get("content_type"):
                raise ImageRecipeError("image_recipe_slot_type_mismatch")
            mapping = recipe["slot_map"][name]
            path = mapping.get("input_path")
            if path is not None:
                expected_type = "text" if path == "rows.*.*" else "table"
                if mapping["projection"] != "structures" or mapping["content_type"] != expected_type:
                    raise ImageRecipeError("image_recipe_input_path_projection_invalid")
            if (mapping["projection"] == "structures" and path is None
                    and any(key in slot for key in ("count_min", "count_max", "max_chars", "max_lines"))):
                raise ImageRecipeError("image_recipe_input_path_missing")
    return recipe


def validate_recipe_content(recipe, *, page, layout):
    """按 recipe 路径检查内容；容量只读取 layout owner，不复制其限制。"""
    validate_recipe(recipe, layout)
    mapped = {name: spec["input_path"] for name, spec in recipe["slot_map"].items() if "input_path" in spec}
    if not mapped:
        return {}
    structures = page.get("structures") or {}
    sources = [structures[key] for key in ("table", "fields") if key in structures]
    if not sources or any(not isinstance(source, dict) for source in sources):
        raise ImageRecipeError("image_recipe_structure_missing")
    data = {}
    for source in sources:
        for name in ("rows", "columns"):
            if name not in source:
                continue
            if name in data and data[name] != source[name]:
                raise ImageRecipeError("image_recipe_structure_conflict")
            data[name] = source[name]
    if set(data) != {"rows", "columns"}:
        raise ImageRecipeError("image_recipe_input_missing")
    rows, columns = data["rows"], data["columns"]
    if (not isinstance(rows, list) or not isinstance(columns, list)
            or any(not isinstance(column, str) for column in columns)
            or any(not isinstance(row, list) or len(row) != len(columns)
                   or any(not isinstance(cell, str) for cell in row) for row in rows)):
        raise ImageRecipeError("image_recipe_table_shape_invalid")
    data["rows.*.*"] = [cell for row in rows for cell in row]
    checks = {}
    from ..render.layout import capacity_level
    for name, path in mapped.items():
        values, slot = data[path], layout["slots"][name]
        check = {"input_path": path, "count": len(values)}
        for bound, relation in (("count_min", "below_min"), ("count_max", "over_max")):
            if bound in slot and ((len(values) < slot[bound]) if bound == "count_min" else (len(values) > slot[bound])):
                raise ImageRecipeError(f"image_recipe_count_{relation}:{name}")
        if slot["content_type"] == "text":
            check["max_chars_used"] = max(map(len, values), default=0)
            check["max_lines_used"] = max((len(value.splitlines()) for value in values), default=0)
            if slot.get("max_chars"):
                check["text_capacity"] = capacity_level(check["max_chars_used"], slot["max_chars"])
                if check["text_capacity"] == "overflow":
                    raise ImageRecipeError(f"image_recipe_text_overflow:{name}")
            if slot.get("max_lines") and check["max_lines_used"] > slot["max_lines"]:
                raise ImageRecipeError(f"image_recipe_lines_over_max:{name}")
        checks[name] = check
    return checks


def project_recipe(recipe, *, page, layout, theme, numbers):
    validate_recipe_content(recipe, page=page, layout=layout)
    content = {key: deepcopy(page.get(key)) for key in ("claim", "items", "structures", "required_text")}
    refs = set(page["expression"]["fact_refs"])
    content["numbers"] = [deepcopy(entry) for entry in numbers if entry["item_id"] in refs]
    if refs != {entry["item_id"] for entry in content["numbers"]}:
        raise ImageRecipeError("image_recipe_fact_reference_missing")
    values = {"content": content, "expression": page["expression"], "theme": theme,
              "layout": {key: layout.get(key) for key in ("canvas", "regions", "slots", "structure")}}
    if layout.get("slot_mapping"):
        values["layout"]["slot_mapping"] = deepcopy(layout["slot_mapping"])
    prompt = recipe["prompt_skeleton"].format(**{key: canonical_json_bytes(value).decode() for key, value in values.items()})
    return {"schema_version": 1, "kind": "image-recipe-input", "recipe_id": recipe["asset_id"],
            "recipe_version": recipe["version"], "page_id": page["page_id"],
            "canvas": deepcopy(recipe["canvas"]), "provider": deepcopy(recipe["provider"]),
            "required_text": deepcopy(page["required_text"]),
            "content": content, "expression": deepcopy(page["expression"]), "prompt": prompt,
            "semantic_output_status": "not_run"}
