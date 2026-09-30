#!/usr/bin/env python3
"""校验 canonical render template 的 JSON/HTML/layout 闭合合同。"""
from __future__ import annotations
import argparse, json, re, sys
from html.parser import HTMLParser
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime/src"))
from leo_ppt_generator.asset_resolver import AssetResolver, ASSET_ID_RE, builtin_library_root
from leo_ppt_generator.qualification import read_evidence_bytes
ASSET_RE = ASSET_ID_RE
SELECTOR_RE = re.compile(r"\[data-leo-block\s*=\s*([\'\"])([^\'\"]+)\1\]")


class _AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors: set[str] = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "data-leo-block" and value:
                self.anchors.add(value)


def _schema_errors(data: dict, schema: Path | None = None) -> list[str]:
    schema = schema or builtin_library_root() / "governance/schemas/template-v1.schema.json"
    try:
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
        resources = []
        for p in schema.parent.glob("*.schema.json"):
            doc = json.loads(read_evidence_bytes(schema.parents[2], p.relative_to(schema.parents[2]).as_posix()))
            if "$id" in doc:
                resources.append((doc["$id"], Resource.from_contents(doc)))
        validator = Draft7Validator(json.loads(read_evidence_bytes(schema.parents[2], schema.relative_to(schema.parents[2]).as_posix())), registry=Registry().with_resources(resources))
        return [e.message for e in validator.iter_errors(data)]
    except Exception as exc:
        return [f"schema validator unavailable: {exc}"]


def lint_one(directory: Path, known_layouts: dict[str, dict], *, schema: Path | None = None, expected_id: str | None = None) -> list[str]:
    slug = directory.name
    errors: list[str] = []
    manifest_path, html_path = directory / "template.json", directory / "page.html"
    if any(p.is_symlink() for p in (manifest_path, html_path, directory, *directory.parents)):
        return [f"{slug}: symlink rejected"]
    if not manifest_path.is_file():
        return [f"{slug}: missing template.json"]
    if not html_path.is_file():
        return [f"{slug}: missing page.html"]
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{slug}: invalid template.json: {exc}"]
    errors += [f"{slug}: schema: {e}" for e in _schema_errors(data, schema)]
    if errors:
        return errors
    identity = data.get("asset_id", "")
    if not ASSET_RE.fullmatch(identity) or identity.split(":")[1] != "template":
        errors.append(f"{slug}: invalid template identity")
    if expected_id is not None and identity != expected_id:
        errors.append(f"{slug}: asset_id must be {expected_id}")
    html = html_path.read_text(encoding="utf-8")
    parser = _AnchorParser()
    parser.feed(html)
    anchors = parser.anchors
    input_names = {x.get("name") for x in data.get("input_fields", []) if isinstance(x, dict)}
    slots = data.get("slot_bindings", [])
    seen_slots = set()
    for binding in slots:
        slot, selector = binding.get("slot"), binding.get("selector")
        if slot in seen_slots:
            errors.append(f"{slug}: duplicate slot {slot}")
        seen_slots.add(slot)
        input_name = str(binding.get("input_path", slot)).split(".")[0]
        if input_name not in input_names and binding.get("binding_kind") != "structural":
            errors.append(f"{slug}: slot {slot} missing from input_fields (or binding_kind=structural)")
        match = SELECTOR_RE.search(selector or "")
        if not match:
            errors.append(f"{slug}: selector for {slot} must contain static data-leo-block anchor")
            continue
        anchor = match.group(2)
        if anchor not in anchors:
            errors.append(f"{slug}: selector for {slot} references missing DOM anchor {anchor}")
    selector_anchors = set()
    for binding in slots:
        match = SELECTOR_RE.search(binding.get("selector") or "")
        if match:
            selector_anchors.add(match.group(2))
    for anchor in sorted(anchors - selector_anchors):
        errors.append(f"{slug}: DOM anchor {anchor} has no slot_binding")
    profile_ids = data.get("layout_profiles", [])
    if not profile_ids:
        errors.append(f"{slug}: layout_profiles must contain at least one layout asset")
    for ref in [*data.get("dependencies", []), *profile_ids]:
        m = ASSET_RE.fullmatch(ref or "")
        if not m:
            errors.append(f"{slug}: invalid asset reference {ref!r}")
            continue
        kind = ref.split(":", 2)[1]
        if kind != "layout":
            errors.append(f"{slug}: template dependency must reference layout, got {ref}")
        if ref not in known_layouts:
            errors.append(f"{slug}: dangling layout reference {ref}")
    for ref in profile_ids:
        layout = known_layouts.get(ref)
        if layout and (layout.get("renderer_support") or {}).get("render:html") != data.get("asset_id"):
            errors.append(f"{slug}: layout {ref} renderer_support.render:html does not point to {data.get('asset_id')}")
        # 显式 input_path 是容量槽位到原有输入的映射，不能指向未声明的字段。
        if layout and any("input_path" in b for b in slots):
            from leo_ppt_generator.template_inputs import slot_input_path_errors
            errors.extend(f"{slug}: {e}" for e in slot_input_path_errors(data, layout))
    # dashi K3/U3：输入字段数量能力与同名 layout slot 交叉一致；嵌套结构
    # 字段（items 形状）必须声明数量边界。
    for field in data.get("input_fields", []):
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        declared_bounds = (field.get("count_min"), field.get("count_max"))
        has_items_shape = isinstance(field.get("items"), dict)
        if has_items_shape and declared_bounds == (None, None):
            errors.append(
                f"{slug}: input field {name} declares nested items shape but no count bounds")
        for ref in profile_ids:
            layout = known_layouts.get(ref)
            slot = (layout or {}).get("slots", {}).get(name)
            if not slot:
                continue
            slot_bounds = (slot.get("count_min"), slot.get("count_max"))
            if slot_bounds == (None, None):
                continue
            for label, tpl_value, layout_value in (
                    ("count_min", declared_bounds[0], slot_bounds[0]),
                    ("count_max", declared_bounds[1], slot_bounds[1])):
                if tpl_value is not None and layout_value is not None and tpl_value != layout_value:
                    errors.append(
                        f"{slug}: input field {name}.{label}={tpl_value} conflicts with "
                        f"layout slot {name}.{label}={layout_value}")
    if data.get("lane") != "render:html":
        errors.append(f"{slug}: lane must be render:html")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, help="明确被检查的 current 库")
    parser.add_argument("--templates-dir", type=Path, help="显式目录审计；schema/layout 来自所选库")
    args = parser.parse_args(argv)
    root = Path(args.library_root or builtin_library_root()).absolute()
    try:
        read_evidence_bytes(root, "catalog/current.json")
        resolver = AssetResolver(library=root, home=root / ".lint-no-user-home")
        if resolver.user_root is not None or resolver.registry_source != "catalog":
            raise ValueError("template_lint_current_library_required")
        generation = resolver.generation
        layouts = {row["asset_id"]: resolver.resolve(row["asset_id"])["data"]
                   for row in resolver.entities if row["kind"] == "layout"}
        if args.templates_dir is not None:
            directories = [(p, None) for p in sorted(args.templates_dir.iterdir())
                           if not p.name.startswith(".") and not (p.name == "README.md" and p.is_file() and not p.is_symlink())]
        else:
            directories = []
            for row in resolver.entities:
                if row["kind"] != "template":
                    continue
                resolved = resolver.resolve(row["asset_id"])
                resolver.fingerprint(row["asset_id"])
                directories.append((Path(resolved["path"]).parent, row["asset_id"]))
        if not directories:
            raise ValueError("template_lint_empty")
        schema = root / "governance/schemas/template-v1.schema.json"
        errors = []
        for directory, identity in directories:
            found = lint_one(directory, layouts, schema=schema, expected_id=identity)
            errors.extend(found)
            print(f"{directory.name}: {'ERROR' if found else 'OK'}")
            for item in found:
                print("  [XX] " + item)
        if AssetResolver(library=root, home=root / ".lint-no-user-home").generation != generation:
            raise ValueError("template_lint_generation_changed")
        print(f"TOTAL: {len(directories)} templates, ERROR={len(errors)}")
        return 1 if errors else 0
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
