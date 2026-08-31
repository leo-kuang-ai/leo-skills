"""Deterministic PPTX zip repacking (CI-2).

python-pptx and the vendored zipfile writer both stamp the wall-clock time into
zip directory entries, so identical inputs produce differing bytes. This module
canonicalizes the container layer only: fixed entry order, fixed timestamps,
fixed compression and attributes. XML content is passed through untouched.

Canonical rules:
- entry order: ``[Content_Types].xml`` → ``_rels/.rels`` → remaining parts in
  lexicographic partname order;
- every entry: ``date_time`` = 1980-01-01 (minimum legal zip timestamp),
  ``compress_type`` = DEFLATE, ``external_attr`` = 0o600 << 16,
  ``create_system`` = 3 (unix) — nothing host- or clock-derived.

``replacements`` allows byte-faithful part substitution during the same pass
(used for frozen ``notes_xml`` bytes, F2-T2 semantics).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
HEAD_ORDER = ("[Content_Types].xml", "_rels/.rels")


def _canonical_order(names: list[str]) -> list[str]:
    heads = [name for name in HEAD_ORDER if name in names]
    rest = sorted(name for name in names if name not in HEAD_ORDER)
    return heads + rest


def canonical_bytes(source: bytes | io.BytesIO, *, replacements: dict[str, bytes] | None = None) -> bytes:
    """Return the canonical repacking of ``source`` as raw bytes."""
    replacements = replacements or {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source) if isinstance(source, bytes) else source) as incoming:
        names = incoming.namelist()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as outgoing:
            for name in _canonical_order(names):
                payload = replacements.get(name)
                if payload is None:
                    payload = incoming.read(name)
                info = zipfile.ZipInfo(filename=name, date_time=ZIP_EPOCH)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                info.create_system = 3
                outgoing.writestr(info, payload)
    return buffer.getvalue()


def repack_zipstream(
    source: bytes | io.BytesIO,
    out_path: str | Path,
    *,
    replacements: dict[str, bytes] | None = None,
) -> Path:
    """Repack ``source`` canonically onto ``out_path`` (parent dirs created)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canonical_bytes(source, replacements=replacements))
    return out


def save_canonical(
    presentation,
    out_path: str | Path,
    *,
    replacements: dict[str, bytes] | None = None,
) -> Path:
    """Serialize a python-pptx Presentation and repack it canonically."""
    buffer = io.BytesIO()
    presentation.save(buffer)
    return repack_zipstream(buffer.getvalue(), out_path, replacements=replacements)
