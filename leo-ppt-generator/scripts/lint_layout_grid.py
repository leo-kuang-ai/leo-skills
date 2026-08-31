#!/usr/bin/env python3
"""Lint layout skeletons against the page-canon token scale.

Checks every ``Nvw``/``Nvh`` value in ``references/styles/12_版式库/*.md``:
- ``min(Xvw, Yvh)`` dual-constraint ratio Y >= X * 1.6  -> error when violated
- values must sit on the 0.4vw modulus -> warning (legacy = registered
  exemption; files listed in EXEMPT_NEW_FILES must not add new off-grid values)

Exit code 0 = no errors (warnings allowed with --allow-exemptions, the default);
exit code 1 = dual-constraint errors or new off-grid values in new files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
LAYOUT_DIR = SKILL_DIR / "references" / "styles" / "12_版式库"

RULE_FILE_PREFIXES = ("00_", "01_常犯", "02_关键类")
MODULUS = 0.4
MIN_RATIO = 1.6
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


def _on_modulus(value: float) -> bool:
    steps = round(value / MODULUS)
    return steps >= 1 and abs(steps * MODULUS - value) < 1e-9


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
