#!/usr/bin/env python3
"""校验所选 current 库的版式几何、容量、附属 notes 与模板/风格引用。

v2 附属字节由 current catalog 固定；v1 过渡库额外核验同目录 manifest。
退役 Markdown/sidecar 仅在显式 --legacy-sidecars 下作为迁移输入检查。
退出码：0 = 无错误；1 = 输入无效或检查失败。
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
sys.path.insert(0, str(SKILL_DIR / "runtime/src"))
from leo_ppt_generator.asset_resolver import AssetResolver, ASSET_ID_RE, builtin_library_root
from leo_ppt_generator.qualification import read_evidence_bytes

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


def _builtin_style_stems(styles_dir: Path) -> list[str]:
    """Top-level *.md carrying a parseable style brief (the 11 builtins)."""
    stems: list[str] = []
    for path in sorted(styles_dir.glob("*.md")):
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


def _lint_sidecars(errors: list[str], *, layout_dir: Path, styles_dir: Path) -> None:
    """Checks A/B/C: sidecar pairing, dangling routing refs, capacity identity."""
    known_layout_ids: set[str] = set()
    layout_mds = [
        p for p in sorted(layout_dir.glob("*.md"))
        if not p.stem.startswith(RULE_FILE_PREFIXES)
    ]
    # 检查 A：版式 .md 必须有同名 sidecar，且 layout_id 与标题 P 码一致。
    for md in layout_mds:
        sidecar_path = layout_dir / f"{md.stem}.layouts.json"
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
    for stem in _builtin_style_stems(styles_dir):
        sidecar_path = styles_dir / f"{stem}.layouts.json"
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
                    if not isinstance(ref, str) or ref not in known_layout_ids:
                        errors.append(
                            f"dangling_layout_ref: {sidecar_path.name} "
                            f"{key} 引用 {ref!r} 无法解析到版式库 sidecar"
                        )


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
    if not isinstance(data.get("page_role"), str) or data["page_role"] not in _PAGE_ROLES:
        errors.append(f"canonical_profile_invalid: {path} page_role 非法")
    if not isinstance(data.get("layout_type"), str) or data["layout_type"] not in _LAYOUT_TYPES:
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
            if all(isinstance(slot.get(key), int) and not isinstance(slot[key], bool) and slot[key] > 0 for key in text_keys):
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
                if not ASSET_ID_RE.fullmatch(binding) or binding.split(":")[1] != "template":
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


def _lint_profile_files(errors: list[str], profiles: list[Path], template_assets: set[str],
                        styles: list[Path], *, root: Path, manifest_path: Path | None = None) -> None:
    """校验已经由 current 枚举的实体；v1 附属 manifest 仅作过渡字节校验。"""
    if not profiles:
        errors.append("canonical_profile_missing: current 库没有 layout 实体")
        return
    layouts_root = profiles[0].parent.parent
    manifest_entries: dict[str, dict] = {}
    if manifest_path is not None:
        try:
            manifest = json.loads(read_evidence_bytes(root, manifest_path.relative_to(root).as_posix()))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"canonical_layout_manifest_invalid: {manifest_path} ({exc})")
            manifest = {}
        if isinstance(manifest, dict):
            if manifest.get("schema_version") != 1 or manifest.get("entity") != "layout-profile-manifest":
                errors.append(f"canonical_layout_manifest_invalid: {manifest_path} schema_version/entity 不符")
            entries = manifest.get("entries")
            if not isinstance(entries, list):
                errors.append(f"canonical_layout_manifest_invalid: {manifest_path} entries 须为数组")
            else:
                for entry in entries:
                    if not isinstance(entry, dict) or not isinstance(entry.get("profile"), str):
                        errors.append(f"canonical_layout_manifest_invalid: {manifest_path} entry 非法")
                        continue
                    profile_key = entry["profile"]
                    if profile_key in manifest_entries:
                        errors.append(f"canonical_layout_manifest_duplicate: {profile_key}")
                    manifest_entries[profile_key] = entry

    known_layout_ids: set[str] = set()
    seen_profiles: set[str] = set()
    for path in profiles:
        profile_key = path.relative_to(layouts_root).as_posix()
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
        if manifest_path is not None:
            entry = manifest_entries.get(profile_key)
            if entry is None:
                errors.append(f"canonical_layout_manifest_missing: {profile_key}")
            else:
                expected_notes = notes.relative_to(layouts_root).as_posix()
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
            text = read_evidence_bytes(root, notes.relative_to(root).as_posix()).decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"canonical_notes_invalid: {notes} ({exc})")
            continue
        for match in _MIN_RE.finditer(text):
            x, y = float(match.group(1)), float(match.group(2))
            if y < x * MIN_RATIO:
                errors.append(f"{notes.name}: min({x}vw,{y}vh) ratio {y/x:.2f} < {MIN_RATIO}")
        if isinstance(profile, dict) and profile.get("asset_id", "").split(":")[-1] in _CANONICAL_LEGACY_EXEMPTIONS:
            continue
        for match in _VALUE_RE.finditer(text):
            value = float(match.group(1))
            if value > 0 and not _on_modulus(value):
                errors.append(f"{notes.name}: {value}vw off-grid (modulus {MODULUS}vw) [canonical]")
    for profile_key in sorted(set(manifest_entries) - seen_profiles):
        errors.append(f"canonical_layout_manifest_orphan: {profile_key}")
    # Canonical style route bindings must point at canonical layout entities.
    for path in styles:
        try:
            brief = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"canonical_style_invalid: {path} ({exc})")
            continue
        bindings = brief.get("bindings") if isinstance(brief, dict) else None
        if not isinstance(bindings, dict):
            errors.append(f"canonical_route_invalid: {path} bindings 须为对象")
            continue
        routes = bindings.get("layout_routes")
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
                    if not isinstance(ref, str) or ref not in known_layout_ids:
                        errors.append(f"canonical_route_dangling: {path.name} {key} 引用 {ref!r}")


def _lint_canonical_profiles(errors: list[str], library_root: Path | None = None) -> None:
    root = Path(library_root or builtin_library_root()).absolute()
    try:
        read_evidence_bytes(root, "catalog/current.json")
        resolver = AssetResolver(library=root, home=root / ".lint-no-user-home")
        if resolver.user_root is not None or resolver.registry_source != "catalog":
            raise ValueError("layout_lint_current_library_required")
        generation = resolver.generation
        profiles, styles, templates = [], [], set()
        pins = {}
        for row in resolver.entities:
            if row["kind"] not in {"layout", "template", "style"}:
                continue
            entity = resolver.resolve(row["asset_id"])
            pins[row["asset_id"]] = resolver.fingerprint(row["asset_id"])
            if row["kind"] == "layout":
                profiles.append(Path(entity["path"]))
            elif row["kind"] == "style":
                styles.append(Path(entity["path"]))
            else:
                templates.add(row["asset_id"])
        declaration = json.loads(read_evidence_bytes(root, "library.json"))
        manifest = profiles[0].parent.parent / "manifest.json" if profiles and declaration.get("schema_version") == 1 else None
        _lint_profile_files(errors, profiles, templates, styles, root=root, manifest_path=manifest)
        if AssetResolver(library=root, home=root / ".lint-no-user-home").generation != generation:
            raise ValueError("layout_lint_generation_changed")
        for identity, pin in pins.items():
            if resolver.fingerprint(identity) != pin:
                raise ValueError("layout_lint_asset_changed:" + identity)
    except (OSError, ValueError) as exc:
        errors.append(f"layout_lint_current_invalid: {exc}")


def _lint_legacy_grid(errors: list[str], exemptions: list[str]) -> None:
    """Run the retired Markdown grid and sidecar checks on demand."""

    if not LEGACY_LAYOUT_DIR.is_dir() or not list(LEGACY_LAYOUT_DIR.glob("*.layouts.json")):
        errors.append("legacy_layout_inputs_missing")
        return
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
    _lint_sidecars(errors, layout_dir=LEGACY_LAYOUT_DIR, styles_dir=LEGACY_STYLES_DIR)


def lint(*, include_legacy_sidecars: bool = False, library_root: Path | None = None) -> int:
    errors: list[str] = []
    exemptions: list[str] = []
    if library_root is not None and include_legacy_sidecars:
        print("ERROR: explicit library root cannot use repository legacy sidecars")
        return 1
    _lint_canonical_profiles(errors, library_root)
    if include_legacy_sidecars:
        _lint_legacy_grid(errors, exemptions)
    print("== canonical layout lint (source=current-catalog) ==")
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
    parser.add_argument("--library-root", type=Path, help="明确被检查的 current 库")
    args = parser.parse_args()
    sys.exit(lint(include_legacy_sidecars=args.legacy_sidecars, library_root=args.library_root))
