"""Shared geometry/normalization layer for the editable manifest IR.

This module is a tested replica of the pure functions in the vendored
``build_pptx_from_manifest.py`` (constants, pixel→inch mapping, letterbox
``fit_content_box`` proportion contract, and text fit heuristics). The vendored
file stays frozen; both builders resolve manifests through this shared layer so
the object builder and the legacy builder cannot drift apart geometrically.

Equivalence contract (F1-T1): for any manifest,
``geometry.normalize_manifest(m)`` must be field-by-field equal to
``_vendor...build_pptx_from_manifest.normalize_manifest(m)``. Keep every
computation, default, and rounding rule byte-compatible when editing.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy

EMU_PER_INCH = 914400
ASPECT_16_9 = 16 / 9
ASPECT_TOLERANCE = 0.03
DEFAULT_TEXT_FIT_SAFETY = 0.9
DEFAULT_TEXT_LINE_HEIGHT = 1.22
DEFAULT_MIN_FONT_SIZE = 4.0
TEXT_ALIGNMENTS = {
    "left": ("l", "left"),
    "center": ("ctr", "center"),
    "right": ("r", "right"),
    "l": ("l", "left"),
    "ctr": ("ctr", "center"),
    "r": ("r", "right"),
}
TEXT_VERTICAL_ALIGNMENTS = {
    "top": ("t", "top"),
    "middle": ("ctr", "middle"),
    "center": ("ctr", "middle"),
    "bottom": ("b", "bottom"),
    "t": ("t", "top"),
    "ctr": ("ctr", "middle"),
    "b": ("b", "bottom"),
}


def emu(value):
    return int(round(float(value) * EMU_PER_INCH))


def hex_color(value, default="000000"):
    if not value:
        return default
    return str(value).strip().lstrip("#").upper()


def text_alignment(value="left"):
    key = str(value or "left").strip().lower()
    if key not in TEXT_ALIGNMENTS:
        raise ValueError(f"Unsupported text align value: {value}")
    return TEXT_ALIGNMENTS[key]


def text_vertical_alignment(value="top"):
    key = str(value or "top").strip().lower()
    if key not in TEXT_VERTICAL_ALIGNMENTS:
        raise ValueError(f"Unsupported text valign value: {value}")
    return TEXT_VERTICAL_ALIGNMENTS[key]


def source_size_px(manifest):
    source = manifest.get("source", {})
    width = source.get("width_px")
    height = source.get("height_px")
    if width and height:
        return float(width), float(height)
    return None


def slide_size(manifest):
    slide = manifest.get("slide", {})
    return float(slide.get("width", 13.333)), float(slide.get("height", 7.5))


def fit_content_box(source_width, source_height, slide_width, slide_height):
    source_aspect = source_width / source_height
    slide_aspect = slide_width / slide_height
    if source_aspect >= slide_aspect:
        width = slide_width
        height = width / source_aspect
        left = 0
        top = (slide_height - height) / 2
    else:
        height = slide_height
        width = height * source_aspect
        left = (slide_width - width) / 2
        top = 0
    return {"left": left, "top": top, "width": width, "height": height}


def content_box_for_manifest(manifest):
    content_box = manifest.get("content_box")
    if content_box:
        return {
            "left": float(content_box.get("left", 0)),
            "top": float(content_box.get("top", 0)),
            "width": float(content_box.get("width", 1)),
            "height": float(content_box.get("height", 1)),
        }
    source_size = source_size_px(manifest)
    slide_width, slide_height = slide_size(manifest)
    if not source_size:
        return {"left": 0, "top": 0, "width": slide_width, "height": slide_height}
    source_width, source_height = source_size
    return fit_content_box(source_width, source_height, slide_width, slide_height)


def px_to_inches(manifest, x, y, width, height):
    source_size = source_size_px(manifest)
    if not source_size:
        raise ValueError("Manifest uses pixel coordinates but lacks source.width_px/source.height_px")
    source_width, source_height = source_size
    content_box = content_box_for_manifest(manifest)
    return {
        "left": content_box["left"] + float(x) / source_width * content_box["width"],
        "top": content_box["top"] + float(y) / source_height * content_box["height"],
        "width": float(width) / source_width * content_box["width"],
        "height": float(height) / source_height * content_box["height"],
    }


def normalize_position_item(manifest, item):
    item = dict(item)
    if "polygon_px" in item:
        points = [(float(point[0]), float(point[1])) for point in item["polygon_px"]]
        if points and "box_px" not in item:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            item["box_px"] = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
        item["polygon"] = [
            [px_to_inches(manifest, point[0], point[1], 0, 0)["left"], px_to_inches(manifest, point[0], point[1], 0, 0)["top"]]
            for point in points
        ]
    if "box_px" in item:
        x, y, width, height = item["box_px"]
        item.update(px_to_inches(manifest, x, y, width, height))
    if "points_px" in item:
        x1, y1, x2, y2 = item["points_px"]
        left = min(float(x1), float(x2))
        top = min(float(y1), float(y2))
        width = abs(float(x2) - float(x1))
        height = abs(float(y2) - float(y1))
        item.update(px_to_inches(manifest, left, top, width, height))
        start = px_to_inches(manifest, x1, y1, 0, 0)
        end = px_to_inches(manifest, x2, y2, 0, 0)
        item["points"] = [start["left"], start["top"], end["left"], end["top"]]
        if float(x2) < float(x1):
            item["flip_h"] = True
        if float(y2) < float(y1):
            item["flip_v"] = True
    if item.get("source_corner_radius_px") is not None and "radius" not in item:
        radius = float(item.get("source_corner_radius_px") or 0)
        item["radius"] = px_to_inches(manifest, 0, 0, radius, radius)["width"]
    return item


def iter_text_lines(item):
    if item.get("paragraphs"):
        lines = []
        for paragraph in item["paragraphs"]:
            if isinstance(paragraph, str):
                lines.append(paragraph)
            else:
                runs = paragraph.get("runs")
                if runs:
                    lines.append("".join(str(run.get("text", "")) for run in runs))
                else:
                    lines.append(str(paragraph.get("text", "")))
        return lines or [""]
    if item.get("runs"):
        return ["".join(str(run.get("text", "")) for run in item["runs"])]
    return str(item.get("text", "")).splitlines() or [""]


def text_width_units(text):
    units = 0.0
    for char in str(text):
        codepoint = ord(char)
        if char.isspace():
            units += 0.32
        elif codepoint <= 0x7F:
            units += 0.55
        elif 0xFF00 <= codepoint <= 0xFFEF:
            units += 1.0
        elif 0x4E00 <= codepoint <= 0x9FFF:
            units += 1.0
        else:
            units += 0.85
    return max(units, 1.0)


def longest_unbreakable_units(text):
    tokens = [token for token in re.split(r"\s+", str(text)) if token]
    if not tokens:
        return text_width_units(text)
    return max(text_width_units(token) for token in tokens)


def is_measured_text(item):
    """True when the author marked this box as sized from `page hints` measurement."""
    return str(item.get("font_size_source", "")).strip().lower() in {"measured", "hints"}


def fitted_font_size(item, manifest):
    if item.get("fit_text") is False or manifest.get("fit_text") is False:
        return None
    if "width" not in item or "height" not in item:
        return None
    lines = iter_text_lines(item)
    requested = float(item.get("font_size", 18))
    width_pt = max(1.0, float(item.get("width", 1)) * 72)
    height_pt = max(1.0, float(item.get("height", 0.4)) * 72)
    if is_measured_text(item):
        # Box and font size were both measured from source ink; the safety
        # discount exists to absorb estimation error in hand-written boxes
        # and would systematically shrink correct text here. Clamp only at
        # the geometric limit.
        safety = 1.0
    else:
        safety = float(item.get("text_fit_safety", manifest.get("text_fit_safety", DEFAULT_TEXT_FIT_SAFETY)))
    line_height = float(item.get("line_height", manifest.get("text_line_height", DEFAULT_TEXT_LINE_HEIGHT)))
    wrap_enabled = item.get("wrap") not in (None, "", "none")
    if wrap_enabled:
        line_count = sum(max(1, math.ceil(text_width_units(line) * requested / width_pt)) for line in lines)
        width_limit = width_pt / max(longest_unbreakable_units(line) for line in lines)
    else:
        line_count = max(1, len(lines))
        width_limit = width_pt / max(text_width_units(line) for line in lines)
    height_limit = height_pt / (line_count * max(line_height, 1.0))
    max_font_size = min(width_limit, height_limit) * safety
    explicit_max = item.get("max_font_size")
    if explicit_max not in (None, ""):
        max_font_size = min(max_font_size, float(explicit_max))
    min_font_size = float(item.get("min_font_size", manifest.get("min_font_size", DEFAULT_MIN_FONT_SIZE)))
    return max(min_font_size, max_font_size)


def scale_run_font_sizes(item, ratio):
    def scale_run(run):
        if run.get("font_size") not in (None, ""):
            run["font_size"] = round(float(run["font_size"]) * ratio, 1)

    for run in item.get("runs", []):
        scale_run(run)
    for paragraph in item.get("paragraphs", []):
        if isinstance(paragraph, dict):
            for run in paragraph.get("runs", []):
                scale_run(run)


def fit_text_item(item, manifest):
    fitted = fitted_font_size(item, manifest)
    if fitted is None:
        return item
    requested = float(item.get("font_size", fitted))
    effective = min(requested, fitted)
    if effective < requested:
        item["_requested_font_size"] = requested
        item["font_size"] = round(effective, 1)
        scale_run_font_sizes(item, effective / requested)
    elif "font_size" not in item:
        item["font_size"] = round(effective, 1)
    return item


def normalize_manifest(manifest):
    """Return a manifest copy with pixel authoring fields resolved to inches."""
    normalized = deepcopy(manifest)
    normalized["text_boxes"] = [
        fit_text_item(normalize_position_item(normalized, item), normalized) for item in normalized.get("text_boxes", [])
    ]
    for key in ("images", "shapes"):
        normalized[key] = [normalize_position_item(normalized, item) for item in normalized.get(key, [])]
    return normalized


def is_wide_slide(width, height):
    return abs((float(width) / float(height)) / ASPECT_16_9 - 1) <= ASPECT_TOLERANCE


def slide_size_type(width, height):
    return "wide" if is_wide_slide(width, height) else "custom"


def round_rect_adjustment(item):
    box_px = item.get("box_px")
    if item.get("source_corner_radius_px") is not None and box_px and len(box_px) == 4:
        radius = float(item.get("source_corner_radius_px") or 0)
        min_dim = max(1.0, min(float(box_px[2]), float(box_px[3])))
    elif item.get("radius") is not None:
        radius = float(item.get("radius") or 0)
        min_dim = max(0.01, min(float(item.get("width", 1)), float(item.get("height", 1))))
    else:
        return None
    return max(0, min(50000, int(round(radius / min_dim * 100000))))
