"""Editable builder selection (F1-T4, CI-3 migration switch).

Selection order (frozen run field wins):

1. run freeze field — ``deck_manifest.builder.selection`` recorded at run
   creation (``EditableAdapter.prepare`` freezes it into ``page_jobs.json``);
   a run always rebuilds with the builder it was created with, regardless of
   later environment changes;
2. ``LEO_EDITABLE_BUILDER`` environment variable (``pptx`` or ``legacy``);
   any other value fails closed to the default rather than silently
   switching builders;
3. default ``legacy`` — the default flips to ``pptx`` only in release stage B,
   after the equivalence suite and full evals have run green for a full cycle.
"""

from __future__ import annotations

import os

ENV_VAR = "LEO_EDITABLE_BUILDER"
VALID_SELECTIONS = ("legacy", "pptx")
DEFAULT_SELECTION = "legacy"
LEGACY_BUILDER_ID = "vendored:build_pptx_from_manifest"


def current(env: dict | None = None, frozen: dict | None = None) -> str:
    """Resolve the effective builder selection (frozen field over env over default)."""
    selection = from_frozen(frozen)
    if selection is not None:
        return selection
    source = os.environ if env is None else env
    value = str(source.get(ENV_VAR, "") or "").lower()
    if not value:
        return DEFAULT_SELECTION
    if value not in VALID_SELECTIONS:
        return DEFAULT_SELECTION
    return value


def from_frozen(frozen: dict | None) -> str | None:
    """Read the frozen run field; missing/invalid fields mean legacy (old runs)."""
    if not isinstance(frozen, dict):
        return None
    selection = str(frozen.get("selection", "") or "").strip().lower()
    return selection if selection in VALID_SELECTIONS else None


def frozen_field(selection: str | None = None, env: dict | None = None) -> dict:
    """Build the freeze record written into run state at creation time."""
    effective = selection if selection in VALID_SELECTIONS else current(env=env)
    if effective == "pptx":
        from ..editable import object_builder

        builder_id = object_builder.BUILDER_ID
    else:
        builder_id = LEGACY_BUILDER_ID
    return {"id": builder_id, "selection": effective}
