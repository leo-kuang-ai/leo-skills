#!/usr/bin/env python3
"""Lint layout skeletons against the page-canon token scale.

Checks every ``Nvw``/``Nvh`` value in ``references/styles/12_版式库/*.md``:
- ``min(Xvw, Yvh)`` dual-constraint ratio Y >= X * 1.6  -> error when violated
- values must sit on the 0.4vw modulus -> warning (legacy = registered
  exemption; files listed in EXEMPT_NEW_FILES must not add new off-grid values)

Layout-bank sidecar pairing checks (layout-bank-v1, B1):
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
1 = dual-constraint, off-grid, or sidecar pairing errors.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
LAYOUT_DIR = SKILL_DIR / "references" / "styles" / "12_版式库"
STYLES_DIR = SKILL_DIR / "references" / "styles"

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


def lint() -> int:
    errors: list[str] = []
    exemptions: list[str] = []
    for path in sorted(LAYOUT_DIR.glob("*.md")):
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
    print("== dual-constraint & off-grid lint ==")
    if errors:
        print("ERRORS:")
        for e in errors:
            print("  -", e)
    else:
        print("errors: 0")
    print(f"registered exemptions (legacy files): {len(exemptions)}")
    for e in exemptions:
        print("  ~", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(lint())
