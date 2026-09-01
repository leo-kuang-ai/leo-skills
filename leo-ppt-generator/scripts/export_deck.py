#!/usr/bin/env python3
"""Multi-target deck exporter (R-47 first batch: handout-PDF + long-image).

Input is a run artifacts directory holding per-page PNGs, e.g.
``<run>/image-deck/origin_image`` with ``slide_01.png .. slide_NN.png``.

Page ordering (deterministic, two rules):
  1. If ``pages.json`` exists in the directory it wins. Accepted shapes: a
     JSON array of file names, or an array of objects whose ``file`` /
     ``png`` / ``out`` field names the page PNG. Entries listed there but
     absent on disk are reported as ``missing``. PNGs on disk but absent
     from the index are ignored (index is authoritative).
  2. Otherwise all ``*.png`` files are natural-sorted: names split into
     digit / non-digit runs, digit runs compared as integers, non-digit
     runs as text; the raw name is the final tie-breaker.

Missing-page detection without an index: when every PNG stem matches one
uniform pattern ``<prefix><digits><suffix>`` (same prefix, same suffix, same
digit width), page numbers are expected to be contiguous from min to max;
gaps are reported as ``missing`` with the reconstructed file name.

Formats:
  handout-pdf  per-page PNG -> multi-page PDF (PIL ``save_all``). Native
               pixel resolution is kept; the first page's PNG dpi (pHYs)
               sizes the PDF MediaBox when present, else 72 dpi (points ==
               pixels). Pillow 12.3 defaults stamp ``CreationDate`` /
               ``ModDate`` from the wall clock; we pass explicit ``None``
               so the output stays byte-deterministic (same input -> same
               sha256, independent of output path or run time).
  long-image   vertical concatenation: canvas width = widest page, every
               page horizontally centered, white background, flattened RGB.

Determinism contract: same input directory -> identical sha256 for both
formats (PIL PNG writes no timestamped chunks; PDF Info dates stripped as
above). RGBA/palette pages are composited onto white before encoding.

Speaker-notes synthesis (markdown notes appended to the handout PDF) is
deliberately out of scope here and left for a later batch; --notes-path is
intentionally not a flag yet.

Receipt (three states, per expert-5 E5-11): human-readable stdout by
default; ``--json`` emits JSON Lines — one ``started`` line after input
validation, then one terminal ``completed`` / ``failed`` line carrying the
artifact path, sha256, page count and ``failed_pages`` (each entry
``<file> (missing)`` or ``<file> (corrupt)``).

Exit codes: 0 = exported; 1 = failed (missing/corrupt pages or write
error); 2 = usage error (directory missing, no PNG found, bad args).
No network access; stdlib + Pillow only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image

PAGE_INDEX_NAME = "pages.json"
INDEX_ENTRY_KEYS = ("file", "png", "out")
WHITE = (255, 255, 255)
FORMATS = ("handout-pdf", "long-image")
DEFAULT_OUTPUT = {"handout-pdf": "export/handout.pdf", "long-image": "export/long-image.png"}


def _fail_usage(message: str) -> "SystemExit":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def _natural_key(name: str):
    # Digit runs sort as integers, text runs as strings; tags keep the
    # element types comparable so sort never raises on mixed names.
    return [(0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"(\d+)", name)] + [(2, name)]


def _index_pages(run_dir: Path):
    """Read pages.json -> ordered page names, or None when unusable."""
    index_path = run_dir / PAGE_INDEX_NAME
    if not index_path.is_file():
        return None
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"WARN: cannot parse {PAGE_INDEX_NAME} ({exc}); falling back to natural sort", file=sys.stderr)
        return None
    if isinstance(data, dict) and isinstance(data.get("pages"), list):
        data = data["pages"]
    if not isinstance(data, list):
        print(f"WARN: {PAGE_INDEX_NAME} is not a list; falling back to natural sort", file=sys.stderr)
        return None
    names = []
    for entry in data:
        if isinstance(entry, str):
            names.append(Path(entry).name)
        elif isinstance(entry, dict):
            value = next((entry[k] for k in INDEX_ENTRY_KEYS if isinstance(entry.get(k), str)), None)
            if value is None:
                print(f"WARN: {PAGE_INDEX_NAME} entry without a known file field; ignored: {entry!r}", file=sys.stderr)
                continue
            names.append(Path(value).name)
    if not names:
        print(f"WARN: {PAGE_INDEX_NAME} has no usable entries; falling back to natural sort", file=sys.stderr)
        return None
    return names


def _gap_missing(png_names):
    """Detect numbering gaps in a uniform ``prefix<digits>suffix`` family."""
    pattern = re.compile(r"^(?P<prefix>.*?)(?P<num>\d+)(?P<suffix>.*)$")
    stems = {}
    for name in png_names:
        stem = name[:-4] if name.lower().endswith(".png") else name
        match = pattern.match(stem)
        if not match:
            return []
        stems[stem] = match
    if not stems:
        return []
    first = next(iter(stems.values()))
    prefix, suffix, width = first.group("prefix"), first.group("suffix"), len(first.group("num"))
    numbers = []
    for stem, match in stems.items():
        if match.group("prefix") != prefix or match.group("suffix") != suffix:
            return []
        if len(match.group("num")) != width:
            return []
        numbers.append(int(match.group("num")))
    missing = []
    for number in range(min(numbers), max(numbers) + 1):
        if number in numbers:
            continue
        missing.append(f"{prefix}{str(number).zfill(width)}{suffix}.png")
    return missing


def discover_pages(run_dir: Path):
    """Return (ordered page names, missing names). Index wins over disk."""
    png_names = sorted(
        (p.name for p in run_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png"),
        key=_natural_key,
    )
    if not png_names:
        return [], []
    indexed = _index_pages(run_dir)
    if indexed is not None:
        on_disk = set(png_names)
        return list(dict.fromkeys(indexed)), [name for name in dict.fromkeys(indexed) if name not in on_disk]
    return png_names, _gap_missing(png_names)


def _flatten(page: Image.Image) -> Image.Image:
    """Composite transparency onto white and reduce to RGB (deterministic)."""
    if page.mode == "RGBA" or page.mode == "LA" or (page.mode == "P" and "transparency" in page.info):
        rgba = page.convert("RGBA")
        base = Image.new("RGB", rgba.size, WHITE)
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    if page.mode != "RGB":
        return page.convert("RGB")
    return page


def load_pages(run_dir: Path, names):
    """Open + fully decode each page; returns (pages, corrupt names)."""
    pages, corrupt = [], []
    for name in names:
        try:
            with Image.open(run_dir / name) as im:
                im.load()  # force full decode; header-only open hides truncation
                dpi = im.info.get("dpi")
                if not (isinstance(dpi, (tuple, list)) and len(dpi) == 2 and dpi[0] > 0 and dpi[1] > 0):
                    dpi = None
                pages.append((name, _flatten(im.copy()), dpi))
        except Exception:
            corrupt.append(name)
    return pages, corrupt


def build_handout_pdf(pages) -> bytes:
    images = [entry[1] for entry in pages]
    dpi = next((entry[2] for entry in pages if entry[2] is not None), None)
    params = {
        "save_all": True,
        "append_images": images[1:],
        # Pillow 12.3 defaults to time.gmtime() here; explicit None keeps
        # the PDF byte-deterministic (see module docstring).
        "creationDate": None,
        "modDate": None,
        "title": None,
    }
    if dpi is not None:
        params["dpi"] = (float(dpi[0]), float(dpi[1]))
    buf = io.BytesIO()
    images[0].save(buf, format="PDF", **params)
    return buf.getvalue()


def build_long_image(pages) -> bytes:
    images = [entry[1] for entry in pages]
    width = max(im.width for im in images)
    height = sum(im.height for im in images)
    canvas = Image.new("RGB", (width, height), WHITE)
    y = 0
    for im in images:
        canvas.paste(im, ((width - im.width) // 2, y))
        y += im.height
    dpi = next((entry[2] for entry in pages if entry[2] is not None), None)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", **({"dpi": (float(dpi[0]), float(dpi[1]))} if dpi is not None else {}))
    return buf.getvalue()


def write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def emit(receipt: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(receipt, ensure_ascii=True, sort_keys=True))
        return
    status = receipt["status"]
    if status == "started":
        print(f"[export] started：{receipt['format']}，共 {receipt['pages']} 页 -> {receipt['artifact']}")
    elif status == "completed":
        print(f"[export] completed：{receipt['artifact']}（{receipt['pages']} 页，sha256={receipt['sha256']}）")
    else:
        detail = "、".join(receipt.get("failed_pages") or []) or receipt.get("error", "unknown")
        print(f"[export] failed：{detail}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export per-page PNGs to handout PDF or long image.")
    parser.add_argument("run_dir", help="directory containing per-page PNGs")
    parser.add_argument("--format", required=True, choices=FORMATS, help="export target format")
    parser.add_argument("--output", type=Path, default=None, help="output file (default <run_dir>/export/...)")
    parser.add_argument("--json", action="store_true", help="emit JSON Lines receipt (started + terminal state)")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        _fail_usage(f"run directory not found: {run_dir}")
    names, missing = discover_pages(run_dir)
    if not names:
        _fail_usage(f"no PNG pages found in {run_dir}")

    output = args.output if args.output is not None else run_dir / DEFAULT_OUTPUT[args.format]
    output = Path(output)
    base = {"status": "started", "format": args.format, "run_dir": str(run_dir.resolve()), "pages": len(names),
            "artifact": str(output)}
    emit(base, args.json)

    def terminal(status, **extra):
        receipt = dict(base)
        receipt["status"] = status
        receipt.update(extra)
        emit(receipt, args.json)

    # Missing pages are already sentenced; do not re-report them as corrupt.
    pages, corrupt = load_pages(run_dir, [name for name in names if name not in set(missing)])
    failed_pages = [f"{name} (missing)" for name in missing] + [f"{name} (corrupt)" for name in corrupt]
    if failed_pages:
        # E5-11: list failed pages honestly; never claim a full export.
        terminal("failed", failed_pages=failed_pages, artifact=None, error="missing or corrupt pages")
        return 1

    try:
        payload = build_handout_pdf(pages) if args.format == "handout-pdf" else build_long_image(pages)
        write_atomic(output, payload)
    except Exception as exc:  # write/encode failure must not exit 0
        terminal("failed", artifact=None, error=f"write failed: {exc}")
        return 1

    terminal("completed", artifact=str(output), sha256=hashlib.sha256(payload).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
