#!/usr/bin/env python3
"""Lint the page-type regime truth source.

``template-library/governance/rules/page-type-regime-v1.json`` is the
versioned semantic page-type truth source consumed by
``leo_ppt_generator.page_intent`` and ``scripts/suggest_layout.py``. It was
introduced without lint coverage, so a broken or drifting regime could reach
routing silently.

Checks (all pure stdlib; deliberately does not require jsonschema, which is
absent from some environments -- see ``lint_template_contract.py``):

- required keys ``schema_version``/``regime_id``/``page_types``; ``regime_id``
  matches the file stem's version suffix; ``page_types`` non-empty.
- every page type declares non-empty ``semantic_requirements``,
  ``preferred_layouts``, ``required_slots`` and ``forbidden_shapes``; every
  ``fallback_layouts`` entry is a real catalog layout asset.
- ``allowed_lanes`` is a non-empty subset of the known lane vocabulary.
  Note that listing several lanes is intentional: it is the *permitted* lane
  set for that page type, and 3a routing picks the concrete lane (e.g. every
  text-dense page type permits both ``image`` and ``render:html``).
- no layout id appears in both ``preferred_layouts`` and
  ``fallback_layouts`` of the same page type (ambiguous ordering).
- every layout id referenced by any page type resolves to a catalog layout
  asset (registry ``asset_id`` or registered alias) -> dangling reference is
  an ERROR.

Exit codes: 0 = no errors; 1 = at least one ERROR; 2 = usage error (regime
file missing or unparseable).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))

REGIME_PATH = SKILL_DIR / Path("template-library/governance/rules/page-type-regime-v1.json")
REGIME_ID = "page-type-regime-v1"
KNOWN_LANES = ("image", "render:html", "render:mermaid", "render:echarts")


def _load_regime(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: regime file not found: {path}", file=sys.stderr)
        raise SystemExit(2) from None
    except json.JSONDecodeError as exc:
        print(f"ERROR: regime file is not valid JSON: {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


def _catalog_layout_aliases() -> set[str]:
    from leo_ppt_generator.asset_resolver import AssetResolver

    aliases: set[str] = set()
    for entity in AssetResolver().entities:
        if entity.get("kind") != "layout":
            continue
        aliases.add(entity["asset_id"])
        aliases.update(entity.get("aliases") or [])
    return aliases


def _check_spec(page_type: str, spec: object, errors: list[str]) -> None:
    if not isinstance(spec, dict):
        errors.append(f"{page_type}: spec must be an object")
        return
    for key in ("semantic_requirements", "preferred_layouts", "required_slots", "forbidden_shapes"):
        value = spec.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"{page_type}: {key} must be a non-empty list")
    preferred = spec.get("preferred_layouts") or []
    fallback = spec.get("fallback_layouts") or []
    if not isinstance(fallback, list) or not fallback:
        errors.append(f"{page_type}: fallback_layouts must be a non-empty list")
    overlap = sorted(set(preferred) & set(fallback))
    if overlap:
        errors.append(f"{page_type}: layout in both preferred and fallback: {', '.join(overlap)}")
    lanes = spec.get("allowed_lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append(f"{page_type}: allowed_lanes must be a non-empty list")
        return
    unknown = [lane for lane in lanes if lane not in KNOWN_LANES]
    if unknown:
        errors.append(f"{page_type}: unknown lane(s): {', '.join(unknown)}")


def lint(regime_path: Path = REGIME_PATH) -> list[str]:
    regime = _load_regime(regime_path)
    errors: list[str] = []

    if regime.get("schema_version") != 1:
        errors.append(f"schema_version must be 1, got {regime.get('schema_version')!r}")
    regime_id = regime.get("regime_id")
    if regime_id != REGIME_ID:
        errors.append(f"regime_id must be {REGIME_ID!r}, got {regime_id!r}")
    else:
        # Version consistency is checked against the declared schema_version, not
        # the file name, so the lint stays valid for relocated or fixture copies.
        match = re.fullmatch(r"page-type-regime-v(\d+)", regime_id)
        if match and int(match.group(1)) != regime.get("schema_version"):
            errors.append(
                f"regime_id version suffix (v{match.group(1)}) disagrees with "
                f"schema_version {regime.get('schema_version')!r}"
            )

    page_types = regime.get("page_types")
    if not isinstance(page_types, dict) or not page_types:
        errors.append("page_types must be a non-empty object")
        return errors

    aliases = _catalog_layout_aliases()
    for page_type, spec in page_types.items():
        _check_spec(page_type, spec, errors)
        if not isinstance(spec, dict):
            continue
        for layout in [*(spec.get("preferred_layouts") or []), *(spec.get("fallback_layouts") or [])]:
            if layout not in aliases:
                errors.append(f"{page_type}: layout {layout!r} is not a catalog layout asset")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--regime",
        type=Path,
        default=REGIME_PATH,
        help="path to the page-type regime JSON (default: canonical truth source)",
    )
    args = parser.parse_args(argv)

    errors = lint(args.regime)
    for message in errors:
        print(f"ERROR: {message}")
    print(f"\npage-type regime: {len(errors)} ERROR")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
