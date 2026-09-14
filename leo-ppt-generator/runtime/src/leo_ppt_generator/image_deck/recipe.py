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
            if recipe["slot_map"][name]["content_type"] != slot["content_type"]:
                raise ImageRecipeError("image_recipe_slot_type_mismatch")
    return recipe


def project_recipe(recipe, *, page, layout, theme, numbers):
    validate_recipe(recipe, layout)
    content = {key: deepcopy(page.get(key)) for key in ("claim", "items", "structures", "required_text")}
    refs = set(page["expression"]["fact_refs"])
    content["numbers"] = [deepcopy(entry) for entry in numbers if entry["item_id"] in refs]
    if refs != {entry["item_id"] for entry in content["numbers"]}:
        raise ImageRecipeError("image_recipe_fact_reference_missing")
    values = {"content": content, "expression": page["expression"], "theme": theme,
              "layout": {key: layout.get(key) for key in ("canvas", "regions", "slots", "structure")}}
    prompt = recipe["prompt_skeleton"].format(**{key: canonical_json_bytes(value).decode() for key, value in values.items()})
    return {"schema_version": 1, "kind": "image-recipe-input", "recipe_id": recipe["asset_id"],
            "recipe_version": recipe["version"], "page_id": page["page_id"],
            "canvas": deepcopy(recipe["canvas"]), "provider": deepcopy(recipe["provider"]),
            "content": content, "expression": deepcopy(page["expression"]), "prompt": prompt,
            "semantic_output_status": "not_run"}
