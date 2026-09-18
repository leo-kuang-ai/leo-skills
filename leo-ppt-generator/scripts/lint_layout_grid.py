#!/usr/bin/env python3
"""Lint layout skeletons against the page-canon token scale.

Checks every canonical layout profile and its sibling notes. The retired
sidecar checks are available only through the explicit ``--legacy-sidecars``
migration mode. Canonical layout profiles live under
``template-library/canonical/layouts/*/layout.json`` and are the active
machine-readable source.

For canonical notes, checks every ``Nvw``/``Nvh`` value in
``template-library/canonical/layouts/*/notes.md``:
- ``min(Xvw, Yvh)`` dual-constraint ratio Y >= X * 1.6  -> error when violated
- values must sit on the 0.4vw modulus -> warning (legacy = registered
  exemption; files listed in EXEMPT_NEW_FILES must not add new off-grid values)

Legacy layout-bank sidecar pairing checks (layout-bank-v1, B1):
- Check A: every layout ``.md`` (rule docs excluded) must carry a parseable
  same-stem ``.layouts.json`` whose ``layout_id`` matches the ``.md`` title
  P-code -> missing / bad JSON / P-code mismatch = ERROR.
- Check B: every top-level builtin style brief must carry a same-stem
  ``.layouts.json``; every ``routing[].preferred/discouraged`` id must
  resolve to one of the 36 layout sidecars -> dangling reference = ERROR.
- Check C: every text slot must satisfy
  ``max_chars == floor(chars_per_line * max_lines * 1.2)`` (TOLERANCE
  identity, GordenPPTSkill calibration) -> drift = ERROR.

Exit codes (CI-4): 0 = no errors (warnings/exemptions allowed);
1 = canonical geometry/manifest errors, or legacy sidecar errors when that
mode is explicitly requested.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
LEGACY_LAYOUT_DIR = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles") / "12_版式库"
LEGACY_STYLES_DIR = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles")
# Compatibility aliases for callers that imported the old constants.
LAYOUT_DIR = LEGACY_LAYOUT_DIR
STYLES_DIR = LEGACY_STYLES_DIR
CANONICAL_LAYOUTS_DIR = SKILL_DIR / Path("template-library/canonical/layouts")
CANONICAL_TEMPLATES_DIR = SKILL_DIR / Path("template-library/canonical/templates")
CANONICAL_STYLES_DIR = SKILL_DIR / Path("template-library/canonical/styles")
CANONICAL_LAYOUT_MANIFEST = CANONICAL_LAYOUTS_DIR / "manifest.json"

RULE_FILE_PREFIXES = ("00_", "01_常犯", "02_关键类")
MODULUS = 0.4
MIN_RATIO = 1.6
CAPACITY_TOLERANCE = 1.2
# Layouts authored before the canon (2026-08-29) keep legacy off-grid values as
# registered exemptions. Files created after the canon must be modulus-clean.
LEGACY_FILES = {
    "01_Cover", "02_Vertical_Timeline", "03_Statement", "04_Six_Cells",
    "05_Three_Sub_cards", "06_KPI_Tower", "07_H_Bar_Chart", "08_Duo_Compare",
    "09_Closing_Manifesto", "10_Dot_Matrix_Statement", "11_Horizontal_Timeline",
    "12_Manifesto_Ink_Banner", "13_Three_Forces_Cards", "14_Loop_Diagram",
    "15_Image_Matrix_Hero_Stat", "16_Multi_card_Brief", "17_System_Diagram",
    "18_Why_Now", "19_Four_Cards", "20_Stacked_KPI_Ledger",
    "21_Tech_Spec_Sheet", "22_Image_Hero",
}

_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)vw")
_MIN_RE = re.compile(r"min\((\d+(?:\.\d+)?)vw,\s*(\d+(?:\.\d+)?)vh\)")
_P_CODE_RE = re.compile(r"^#\s*版式[:：]\s*(P\d+)\b", re.M)
_JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)
_ASSET_ID_RE = re.compile(r"^builtin:template:[A-Za-z0-9\-\u4e00-\u9fff]+$")
# ``agenda`` is present in the published P32 profile; keep it as the runtime
# compatibility spelling while the governance schema is converged.
_PAGE_ROLES = {"cover", "agenda", "section", "content", "data", "quote", "evidence", "closing"}
_LAYOUT_TYPES = {"fixed-regions", "stack-row", "stack-column", "grid", "table"}
# These values are registered legacy exceptions in the page-canon baseline.
_CANONICAL_LEGACY_EXEMPTIONS = {
    "p10-10-dot-matrix-statement-layouts", "p12-12-manifesto-ink-banner-layouts",
    "p20-20-stacked-kpi-ledger-layouts",
}


def _on_modulus(value: float) -> bool:
    steps = round(value / MODULUS)
    return steps >= 1 and abs(steps * MODULUS - value) < 1e-9


def _builtin_style_stems() -> list[str]:
    """Top-level *.md carrying a parseable style brief (the 11 builtins)."""
    stems: list[str] = []
    for path in sorted(STYLES_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for block in _JSON_BLOCK_RE.findall(text):
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "style_name" in parsed:
                stems.append(path.stem)
                break
    return stems


def _lint_sidecars(errors: list[str]) -> None:
    """Checks A/B/C: sidecar pairing, dangling routing refs, capacity identity."""
    known_layout_ids: set[str] = set()
    layout_mds = [
        p for p in sorted(LAYOUT_DIR.glob("*.md"))
        if not p.stem.startswith(RULE_FILE_PREFIXES)
    ]
    # 检查 A：版式 .md 必须有同名 sidecar，且 layout_id 与标题 P 码一致。
    for md in layout_mds:
        sidecar_path = LAYOUT_DIR / f"{md.stem}.layouts.json"
        if not sidecar_path.is_file():
            errors.append(
                f"sidecar_missing: {md.name} 缺同名 {md.stem}.layouts.json"
            )
            continue
        try:
            data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"sidecar_invalid: {sidecar_path.name} ({exc})")
            continue
        if not isinstance(data, dict) or data.get("entity") != "layout":
            errors.append(
                f"sidecar_invalid: {sidecar_path.name} entity != 'layout'"
            )
            continue
        text = md.read_text(encoding="utf-8")
        m = _P_CODE_RE.search(text)
        md_code = m.group(1) if m else None
        sidecar_code = data.get("layout_id")
        if not md_code:
            errors.append(
                f"sidecar_p_code_mismatch: {md.name} 标题无 P 码，无法配对"
            )
        elif sidecar_code != md_code:
            errors.append(
                f"sidecar_p_code_mismatch: {md.name} 标题 {md_code} != "
                f"sidecar layout_id {sidecar_code!r}"
            )
        known_layout_ids.add(str(sidecar_code))
        # 检查 C：文本 slot 容量恒等式（TOLERANCE 移植值）。
        capacity = data.get("content_capacity")
        if not isinstance(capacity, dict) or not capacity:
            errors.append(f"sidecar_invalid: {sidecar_path.name} 缺 content_capacity")
            continue
        for slot_name, slot in capacity.items():
            if not isinstance(slot, dict) or "chars_per_line" not in slot:
                continue
            cpl, lines, mx = (
                slot.get("chars_per_line"), slot.get("max_lines"),
                slot.get("max_chars"),
            )
            if not all(isinstance(v, int) for v in (cpl, lines, mx)):
                errors.append(
                    f"capacity_invalid: {sidecar_path.name}.{slot_name} "
                    "三值须为整数"
                )
                continue
            expected = math.floor(cpl * lines * CAPACITY_TOLERANCE)
            if mx != expected:
                errors.append(
                    f"capacity_drift: {sidecar_path.name}.{slot_name} "
                    f"max_chars={mx} != floor({cpl}×{lines}×1.2)={expected}"
                )
    # 检查 B：内置风格薄路由视图存在 + 引用零悬空。
    for stem in _builtin_style_stems():
        sidecar_path = STYLES_DIR / f"{stem}.layouts.json"
        if not sidecar_path.is_file():
            errors.append(
                f"style_sidecar_missing: 内置风格 {stem} 缺 {stem}.layouts.json"
            )
            continue
        try:
            data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"style_sidecar_invalid: {sidecar_path.name} ({exc})")
            continue
        routing = data.get("routing")
        if not isinstance(routing, list) or not routing:
            errors.append(f"style_sidecar_invalid: {sidecar_path.name} 缺 routing")
            continue
        for rule in routing:
            if not isinstance(rule, dict):
                continue
            for key in ("preferred", "discouraged"):
                for ref in rule.get(key, []) or []:
                    if ref not in known_layout_ids:
                        errors.append(
                            f"dangling_layout_ref: {sidecar_path.name} "
                            f"{key} 引用 {ref!r} 无法解析到版式库 sidecar"
                        )


def _template_assets() -> set[str]:
    """Return renderer template IDs from canonical manifests."""
    assets: set[str] = set()
    for path in sorted(CANONICAL_TEMPLATES_DIR.glob("*/template.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        asset_id = data.get("asset_id") if isinstance(data, dict) else None
        if isinstance(asset_id, str):
            assets.add(asset_id)
    return assets


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lint_canonical_profile(path: Path, errors: list[str], template_assets: set[str]) -> None:
    """Check one layout-profile-v1 without consulting the retired tree."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"canonical_profile_invalid: {path} ({exc})")
        return
    if not isinstance(data, dict):
        errors.append(f"canonical_profile_invalid: {path} 须为对象")
        return

    required = {"schema_version", "entity", "asset_id", "name", "canvas",
                "page_role", "layout_type", "slots", "renderer_support"}
    missing = sorted(required - data.keys())
    if missing:
        errors.append(f"canonical_profile_invalid: {path} 缺字段 {','.join(missing)}")
    if data.get("schema_version") != 1 or data.get("entity") != "layout-profile":
        errors.append(f"canonical_profile_invalid: {path} schema_version/entity 不符")
    canvas = data.get("canvas")
    if not isinstance(canvas, dict) or (canvas.get("width"), canvas.get("height"),
                                        canvas.get("units")) != (1280, 720, "logical-px"):
        errors.append(f"canonical_profile_invalid: {path} 画布必须为 1280×720 logical-px")
    if data.get("page_role") not in _PAGE_ROLES:
        errors.append(f"canonical_profile_invalid: {path} page_role 非法")
    if data.get("layout_type") not in _LAYOUT_TYPES:
        errors.append(f"canonical_profile_invalid: {path} layout_type 非法")

    slots = data.get("slots")
    if not isinstance(slots, dict) or not slots:
        errors.append(f"canonical_profile_invalid: {path} slots 不能为空")
    else:
        for slot_name, slot in slots.items():
            if not isinstance(slot, dict) or not isinstance(slot.get("region"), str):
                errors.append(f"canonical_profile_invalid: {path}.{slot_name} 缺 region")
                continue
            for key in ("count_min", "count_max", "max_chars", "chars_per_line", "max_lines"):
                if key in slot and (not isinstance(slot[key], int) or isinstance(slot[key], bool)
                                    or slot[key] < (0 if key == "count_min" else 1)):
                    errors.append(f"canonical_profile_invalid: {path}.{slot_name}.{key} 须为正整数")
            text_keys = ("chars_per_line", "max_lines", "max_chars")
            if all(key in slot for key in text_keys):
                expected = math.floor(slot["chars_per_line"] * slot["max_lines"] * CAPACITY_TOLERANCE)
                if slot["max_chars"] != expected:
                    errors.append(
                        f"capacity_drift: {path.name}.{slot_name} max_chars={slot['max_chars']} "
                        f"!= floor({slot['chars_per_line']}×{slot['max_lines']}×1.2)={expected}"
                    )

    renderer = data.get("renderer_support")
    if not isinstance(renderer, dict) or not renderer:
        errors.append(f"canonical_profile_invalid: {path} renderer_support 不能为空")
    else:
        for lane, binding in renderer.items():
            if not isinstance(binding, (str, type(None))):
                errors.append(f"canonical_renderer_invalid: {path}.{lane} 绑定须为 string/null")
            elif lane == "render:html" and isinstance(binding, str):
                if not _ASSET_ID_RE.fullmatch(binding):
                    errors.append(f"canonical_renderer_invalid: {path} render:html asset_id 非法 {binding!r}")
                elif binding not in template_assets:
                    errors.append(f"canonical_renderer_missing: {path} 未找到模板 {binding}")

    regions = data.get("regions")
    if regions is not None:
        if not isinstance(regions, dict) or not regions:
            errors.append(f"canonical_profile_invalid: {path} regions 不能为空对象")
        else:
            for name, region in regions.items():
                if not isinstance(region, dict):
                    errors.append(f"canonical_region_invalid: {path}.{name} 须为对象")
                    continue
                values = [region.get(key) for key in ("x", "y", "width", "height")]
                if any(not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
                       for value in values):
                    errors.append(f"canonical_region_invalid: {path}.{name} 坐标/尺寸非法")
                elif region["x"] + region["width"] > 1280 or region["y"] + region["height"] > 720:
                    errors.append(f"canonical_region_invalid: {path}.{name} 越出画布")


def _lint_canonical_profiles(errors: list[str]) -> None:
    """Lint canonical profiles, colocated notes, and their digest manifest."""
    template_assets = _template_assets()
    profiles = sorted(CANONICAL_LAYOUTS_DIR.glob("*/layout.json"))
    if not profiles:
        errors.append(f"canonical_profile_missing: {CANONICAL_LAYOUTS_DIR} 没有 layout.json")
        return

    manifest_entries: dict[str, dict] = {}
    try:
        manifest = json.loads(CANONICAL_LAYOUT_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"canonical_layout_manifest_invalid: {CANONICAL_LAYOUT_MANIFEST} ({exc})")
        manifest = {}
    if isinstance(manifest, dict):
        if manifest.get("schema_version") != 1 or manifest.get("entity") != "layout-profile-manifest":
            errors.append(f"canonical_layout_manifest_invalid: {CANONICAL_LAYOUT_MANIFEST} schema_version/entity 不符")
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            errors.append(f"canonical_layout_manifest_invalid: {CANONICAL_LAYOUT_MANIFEST} entries 须为数组")
        else:
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("profile"), str):
                    errors.append(f"canonical_layout_manifest_invalid: {CANONICAL_LAYOUT_MANIFEST} entry 非法")
                    continue
                profile_key = entry["profile"]
                if profile_key in manifest_entries:
                    errors.append(f"canonical_layout_manifest_duplicate: {profile_key}")
                manifest_entries[profile_key] = entry

    known_layout_ids: set[str] = set()
    seen_profiles: set[str] = set()
    for path in profiles:
        profile_key = path.relative_to(CANONICAL_LAYOUTS_DIR).as_posix()
        seen_profiles.add(profile_key)
        profile = None
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(profile, dict) and isinstance(profile.get("asset_id"), str):
                known_layout_ids.add(profile["asset_id"])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        _lint_canonical_profile(path, errors, template_assets)
        notes = path.parent / "notes.md"
        if not notes.is_file():
            errors.append(f"canonical_notes_missing: {notes}")
            continue
        entry = manifest_entries.get(profile_key)
        if entry is None:
            errors.append(f"canonical_layout_manifest_missing: {profile_key}")
        else:
            expected_notes = notes.relative_to(CANONICAL_LAYOUTS_DIR).as_posix()
            if entry.get("notes") != expected_notes:
                errors.append(f"canonical_notes_owner_mismatch: {profile_key} notes={entry.get('notes')!r}")
            if not isinstance(profile, dict) or entry.get("asset_id") != profile.get("asset_id"):
                errors.append(f"canonical_layout_manifest_asset_mismatch: {profile_key}")
            layout_sha = _sha256(path)
            notes_sha = _sha256(notes)
            if entry.get("layout_sha256") != layout_sha:
                errors.append(f"canonical_layout_digest_mismatch: {profile_key} layout_sha256")
            if entry.get("revision") != layout_sha[:16]:
                errors.append(f"canonical_layout_revision_mismatch: {profile_key}")
            if entry.get("notes_sha256") != notes_sha:
                errors.append(f"canonical_notes_digest_mismatch: {profile_key}")
        try:
            text = notes.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"canonical_notes_invalid: {notes} ({exc})")
            continue
        for match in _MIN_RE.finditer(text):
            x, y = float(match.group(1)), float(match.group(2))
            if y < x * MIN_RATIO:
                errors.append(f"{notes.name}: min({x}vw,{y}vh) ratio {y/x:.2f} < {MIN_RATIO}")
        if path.parent.name in _CANONICAL_LEGACY_EXEMPTIONS:
            continue
        for match in _VALUE_RE.finditer(text):
            value = float(match.group(1))
            if value > 0 and not _on_modulus(value):
                errors.append(f"{notes.name}: {value}vw off-grid (modulus {MODULUS}vw) [canonical]")
    for profile_key in sorted(set(manifest_entries) - seen_profiles):
        errors.append(f"canonical_layout_manifest_orphan: {profile_key}")
    # Canonical style route bindings must point at canonical layout entities.
    for path in sorted(CANONICAL_STYLES_DIR.glob("*/brief.json")):
        try:
            brief = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"canonical_style_invalid: {path} ({exc})")
            continue
        routes = (brief.get("bindings") or {}).get("layout_routes") if isinstance(brief, dict) else None
        if not isinstance(routes, list):
            continue
        for route in routes:
            if not isinstance(route, dict):
                continue
            for key in ("preferred", "discouraged"):
                refs = route.get(key) or []
                if not isinstance(refs, list):
                    errors.append(f"canonical_route_invalid: {path}.{key} 须为数组")
                    continue
                for ref in refs:
                    if ref not in known_layout_ids:
                        errors.append(f"canonical_route_dangling: {path.name} {key} 引用 {ref!r}")


def _lint_legacy_grid(errors: list[str], exemptions: list[str]) -> None:
    """Run the retired Markdown grid and sidecar checks on demand."""

    for path in sorted(LEGACY_LAYOUT_DIR.glob("*.md")):
        if path.stem.startswith(RULE_FILE_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8")
        for m in _MIN_RE.finditer(text):
            x, y = float(m.group(1)), float(m.group(2))
            if y < x * MIN_RATIO:
                errors.append(
                    f"{path.name}: min({x}vw,{y}vh) ratio {y/x:.2f} < {MIN_RATIO}"
                )
        for m in _VALUE_RE.finditer(text):
            value = float(m.group(1))
            if value > 0 and not _on_modulus(value):
                entry = f"{path.name}: {value}vw off-grid (modulus {MODULUS}vw)"
                if path.stem in LEGACY_FILES:
                    exemptions.append(entry)
                else:
                    errors.append(entry + " [new file, no exemption]")
    _lint_sidecars(errors)


def lint(*, include_legacy_sidecars: bool = False) -> int:
    errors: list[str] = []
    exemptions: list[str] = []
    _lint_canonical_profiles(errors)
    if include_legacy_sidecars:
        _lint_legacy_grid(errors, exemptions)
    print("== canonical layout lint (source=canonical) ==")
    if errors:
        print("ERRORS:")
        for e in errors:
            print("  -", e)
    else:
        print("errors: 0")
    if include_legacy_sidecars:
        print(f"legacy sidecar mode: enabled; registered exemptions: {len(exemptions)}")
        for e in exemptions:
            print("  ~", e)
    else:
        print("legacy sidecar mode: disabled (use --legacy-sidecars for migration checks)")
    return 1 if errors else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="校验 canonical layout profiles；可选检查退役 sidecar 迁移输入")
    parser.add_argument(
        "--legacy-sidecars", "--legacy-fixtures", dest="legacy_sidecars", action="store_true",
        help="显式加入 retired-styles-tree 的 Markdown/layouts.json 迁移检查",
    )
    args = parser.parse_args()
    sys.exit(lint(include_legacy_sidecars=args.legacy_sidecars))
