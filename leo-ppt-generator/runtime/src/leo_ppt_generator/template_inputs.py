"""模板输入声明的共享校验：候选预编译与直接渲染使用同一合同。"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET

from jsonschema import Draft7Validator


_NON_DISPLAY_KEYS = {
    "x", "y", "width", "height", "fill", "color", "background",
    "border", "font_size", "fontSize", "weight", "line_height",
    "kind", "deco_filled", "ratio", "corners", "shadow", "bg", "inset",
    "fit", "device", "image_src", "image_alt", "background_color", "page_no",
}


def load_template_json(text: str):
    """拒绝重复键、NaN/Infinity 及溢出为 Infinity 的 JSON 数值。"""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"重复键 {key}")
            result[key] = value
        return result

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"不允许非有限数值 {value}")
        return number

    return json.loads(text, object_pairs_hook=unique_object,
                      parse_float=finite_float, parse_constant=finite_float)


def _schema(field: dict) -> dict:
    schema = {k: v for k, v in field.items()
              if k not in ("name", "required", "count_min", "count_max", "fields")}
    if isinstance(field.get("required"), list):
        schema["required"] = field["required"]
    field_type = field.get("type")
    if field_type in ("data-uri", "image", "media", "enum"):
        schema["type"] = "string"
    if field_type == "enum":
        values = field.get("enum")
        if not isinstance(values, list) or not values:
            # 裸 enum 不提供可接受值，不能作为有效合同放行。
            schema["enum"] = []
        else:
            schema["enum"] = values
    if field.get("name") == "page_no":
        # 历史显示输入使用 "01"；保留显示值，稳定页身份仍由内容包持有。
        schema.pop("type", None)
        schema["anyOf"] = [{"type": "integer", "minimum": 0},
                           {"type": "string", "pattern": "^[0-9]+$"}]
    for source, target in (("count_min", "minItems"), ("count_max", "maxItems")):
        if source in field:
            schema[target] = field[source]
    if isinstance(field.get("items"), dict):
        schema["items"] = _schema(field["items"])
    if isinstance(field.get("fields"), list):
        schema["properties"] = {f["name"]: _schema(f) for f in field["fields"]}
        schema["required"] = [f["name"] for f in field["fields"] if f.get("required")]
        schema["additionalProperties"] = False
    return schema


def field_errors(field: dict, value) -> list[str]:
    errors = Draft7Validator(_schema(field)).iter_errors(value)
    return [f"{field.get('name', 'data')}{''.join(f'[{p}]' for p in e.path)}: {e.message}"
            for e in errors]


def validate_template_data(manifest: dict, data) -> list[str]:
    if not isinstance(data, dict):
        return ["模板输入必须为 JSON object"]
    errors = []
    fields = manifest.get("input_fields", [])
    declared = {field["name"] for field in fields}
    # 历史封面调用传入页码元数据，但封面不显示；保持该兼容边界。
    for name in sorted(set(data) - declared - {"page_no"}):
        errors.append(f"未登记字段 {name} 不允许直接渲染")
    for field in fields:
        name = field["name"]
        if name not in data:
            if field.get("required"):
                errors.append(f"必填字段 {name} 缺失")
        else:
            errors.extend(field_errors(field, data[name]))
    # 跨字段约束无法由单字段 items 表达。
    if "columns" in data and "rows" in data and isinstance(data["rows"], list):
        columns = data["columns"]
        if isinstance(columns, list):
            for i, row in enumerate(data["rows"]):
                if isinstance(row, list) and len(row) != len(columns):
                    errors.append(f"rows[{i}] 单元格数与 columns 不一致")
    if "quote_em" in data:
        emphasis, quote = data.get("quote_em"), data.get("quote")
        if not isinstance(emphasis, str) or not isinstance(quote, str) or emphasis not in quote:
            errors.append("quote_em 必须是 quote 中的原文，不能追加未提供的引文")
    if "chart_svg" in data and isinstance(data["chart_svg"], str):
        # 解析 SVG 以获得真正可见的文本；绝不把坐标/颜色属性当作数字证据。
        try:
            ET.fromstring(data["chart_svg"])
        except ET.ParseError as exc:
            errors.append(f"chart_svg 必须是合法 SVG: {exc}")
    return errors


def slot_input_path_errors(manifest: dict, layout: dict) -> list[str]:
    """容量槽位必须能追溯到输入字段与 DOM；结构装饰不冒充内容槽位。"""
    errors = []
    bindings = {binding.get("slot"): binding for binding in manifest.get("slot_bindings", [])}
    fields = {field.get("name"): field for field in manifest.get("input_fields", [])}
    for slot in layout.get("slots", {}):
        binding = bindings.get(slot)
        if not binding:
            errors.append(f"slot_binding_missing:{slot}")
            continue
        path = binding.get("input_path", slot)
        if not isinstance(path, str) or not path or any(not part for part in path.split(".")):
            errors.append(f"slot_input_path_invalid:{slot}")
            continue
        segments = path.split(".")
        schema = fields.get(segments[0])
        for part in segments[1:]:
            if not isinstance(schema, dict):
                break
            if part == "*" and schema.get("type") == "array":
                schema = schema.get("items")
            elif schema.get("type") == "object":
                schema = next((f for f in schema.get("fields", []) if f.get("name") == part), None)
            else:
                schema = None
        if not isinstance(schema, dict):
            errors.append(f"slot_input_path_invalid:{slot}")
    return errors


def display_texts(value, *, _key: str | None = None):
    """显示字段叶值；布尔值是样式开关，不计入文字覆盖。"""
    if _key in _NON_DISPLAY_KEYS:
        return
    if _key == "chart_svg" and isinstance(value, str):
        try:
            root = ET.fromstring(value)
        except ET.ParseError:
            return
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] == "text":
                text = "".join(element.itertext()).strip()
                if text:
                    yield text
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, int) and not isinstance(value, bool):
        yield str(value)
    elif isinstance(value, float) and math.isfinite(value):
        yield str(value)
    elif isinstance(value, list):
        for item in value:
            yield from display_texts(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from display_texts(item, _key=str(key))
