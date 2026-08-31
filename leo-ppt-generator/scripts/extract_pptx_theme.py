#!/usr/bin/env python3
"""extract_pptx_theme.py — 可信 PPTX 主题提取器（B4，纯 stdlib）。

语义链：

1. rels 链解析：``ppt/_rels/presentation.xml.rels`` → slideMaster →
   ``slideMaster.rels`` → ``ppt/theme/theme1.xml``（相对路径解析同上游
   ``resolveRelativePath``）。
2. clrMap + 12 slot 调色板：slideMaster ``clrMap``（默认 bg1→lt1 / tx1→dk1 /
   …）；theme ``clrScheme`` 逐 slot 取 ``srgbClr@val`` 或 ``sysClr@lastClr``；
   ``applyColorModifiers``（lumMod/lumOff/tint/shade/satMod/satOff，HSL 换算）。
3. 字体双槽 + Office→Web 映射 16 条（逐条直搬上游 OFFICE_FONT_MAP）；中文
   字体不在表内时 ``mapped: null`` 并注明「生图后端可用性需样张验证」。
4. 内容扫描角色色推导：文本 run 字号 ≥18pt（sz ≥1800）判 heading，权重
   ``max(1, sz) × 1/sqrt(slideNumber)``，多巨标色惩罚（>1 个 ≥25pt 色时按
   个数折减）；shape fill 频次；slide bg 频次。
5. leo 四角色映射（与三层 token 兼容）：primary（shapeFill 频次最高或
   accent1）/ accent（heading 高频高饱和色或 accent2）/ secondary
   （accent3-6 按色距分散度选一）/ neutral（dk1 或 body 高频色）。

**清晰失败不静默降级**（与上游 fallback 行为刻意不同）：theme1.xml 缺失或
不可解析 → exit 1 带 reason，不回退到「任意 theme 文件」或纯内容扫描。

**HEX 红线**：提取结果不写入任何风格 brief 的 color_palette；HEX 只进 deck
锚点覆盖通道——输出 ``suggested_overrides``，经
``"$LEO_PPT" style render <风格> --color primary=#RRGGBB …`` 生效
（templates.py 既有通道，含角色/HEX 校验）。提取的是「这份 deck 的身份色值」，
不是「风格的固有属性」（00_索引/设计体系.md 三层 token 的设计意图）。

输出：键排序确定性 JSON（无时间戳，CI-2 可哈希；``source_pptx_sha256``
标识来源）。仅 Office Trust Gate 通过 + CLI preflight 通过后运行（见
references/input-routing.md 与 editable-workflow.md 接入合同）。

用法::

    python3 scripts/extract_pptx_theme.py <可信.pptx> [--json out.json|-]

退出码（CI-4）：0 成功；1 提取失败（theme 缺失/不可解析，输出 reason）；
2 文件或用法错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------- #
# Office Font → Web Font Mapping（逐条直搬自 pptx-theme-extractor.ts，MIT）
# --------------------------------------------------------------------------- #

OFFICE_FONT_MAP: dict[str, str] = {
    "Calibri": "Inter",
    "Calibri Light": "Inter",
    "Cambria": "Merriweather",
    "Arial": "Inter",
    "Times New Roman": "Lora",
    "Verdana": "Open Sans",
    "Georgia": "Source Serif Pro",
    "Trebuchet MS": "Montserrat",
    "Tahoma": "Inter",
    "Century Gothic": "Poppins",
    "Garamond": "Cormorant Garamond",
    "Book Antiqua": "Libre Baskerville",
    "Palatino": "Libre Baskerville",
    "Franklin Gothic Medium": "Manrope",
    "Impact": "Sora",
    "Lucida Sans": "Nunito",
}

HEADING_SIZE_THRESHOLD = 1800  # OOXML 百分之一点：≥1800 = 18pt 判 heading
BIG_HEADING_SIZE_THRESHOLD = 2500

THEME_COLOR_SLOTS = [
    "dk1", "lt1", "dk2", "lt2",
    "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
    "hlink", "folHlink",
]

DEFAULT_CLR_MAP = {
    "bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2",
    "accent1": "accent1", "accent2": "accent2", "accent3": "accent3",
    "accent4": "accent4", "accent5": "accent5", "accent6": "accent6",
    "hlink": "hlink", "folHlink": "folHlink",
}


class ThemeExtractError(Exception):
    """提取失败（exit 1）：清晰失败不静默降级。"""


# ----------------------------- color utilities ----------------------------- #

def _clamp_byte(n: float) -> str:
    return f"{max(0, min(255, round(n))):02X}"


def _hex_to_hsl(hex_value: str) -> tuple[float, float, float]:
    r = int(hex_value[1:3], 16) / 255
    g = int(hex_value[3:5], 16) / 255
    b = int(hex_value[5:7], 16) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d + (6 if g < b else 0)) / 6
    elif mx == g:
        h = ((b - r) / d + 2) / 6
    else:
        h = ((r - g) / d + 4) / 6
    return h * 360, s, l


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    h = (h % 360 + 360) % 360
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))

    def hue2rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        v = round(l * 255)
        return f"#{_clamp_byte(v)}{_clamp_byte(v)}{_clamp_byte(v)}"
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = round(hue2rgb(p, q, h / 360 + 1 / 3) * 255)
    g = round(hue2rgb(p, q, h / 360) * 255)
    b = round(hue2rgb(p, q, h / 360 - 1 / 3) * 255)
    return f"#{_clamp_byte(r)}{_clamp_byte(g)}{_clamp_byte(b)}"


def apply_color_modifiers(hex_value: str, modifiers: list[tuple[str, int]]) -> str:
    """OOXML 颜色修饰（lumMod/lumOff/tint/shade/satMod/satOff；val 为 1/100000）。"""
    h, s, l = _hex_to_hsl(hex_value)
    for mod_type, val in modifiers:
        pct = val / 100000
        if mod_type == "lumMod":
            l *= pct
        elif mod_type == "lumOff":
            l += pct
        elif mod_type == "tint":
            l += (1 - l) * pct
        elif mod_type == "shade":
            l *= pct
        elif mod_type == "satMod":
            s *= pct
        elif mod_type == "satOff":
            s += pct
        # alpha 忽略（不需要透明度），同上游。
    return _hsl_to_hex(h, s, l)


def color_distance(a: str, b: str) -> float:
    ar, ag, ab = (int(a[i:i + 2], 16) for i in (1, 3, 5))
    br, bg, bb = (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return math.sqrt((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2)


def saturation_of(hex_value: str) -> float:
    return _hex_to_hsl(hex_value)[1]


# ------------------------------ xml utilities ------------------------------ #

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(el: ET.Element | None) -> list[ET.Element]:
    return list(el) if el is not None else []


def _find_child(parent: ET.Element | None, name: str) -> ET.Element | None:
    for child in _children(parent):
        if _local(child.tag) == name:
            return child
    return None


def _find_deep(root: ET.Element | None, name: str) -> ET.Element | None:
    if root is None:
        return None
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _color_from_element(parent: ET.Element | None) -> str | None:
    srgb = _find_deep(parent, "srgbClr")
    if srgb is not None and srgb.get("val"):
        return f"#{srgb.get('val').upper()}"
    sysc = _find_deep(parent, "sysClr")
    if sysc is not None and sysc.get("lastClr"):
        return f"#{sysc.get('lastClr').upper()}"
    return None


def _modifiers_of(el: ET.Element) -> list[tuple[str, int]]:
    mods: list[tuple[str, int]] = []
    for child in _children(el):
        val = child.get("val")
        if val and _local(child.tag):
            try:
                mods.append((_local(child.tag), int(val)))
            except ValueError:
                continue
    return mods


def _resolve_color_from_fill(
    solid_fill: ET.Element | None,
    palette: dict[str, str | None] | None,
    clr_map: dict[str, str],
) -> str | None:
    if solid_fill is None:
        return None
    srgb = _find_child(solid_fill, "srgbClr")
    if srgb is not None and srgb.get("val"):
        base = f"#{srgb.get('val').upper()}"
        mods = _modifiers_of(srgb)
        return apply_color_modifiers(base, mods) if mods else base
    if palette is not None:
        scheme = _find_child(solid_fill, "schemeClr")
        if scheme is not None and scheme.get("val"):
            slot = clr_map.get(scheme.get("val", ""), scheme.get("val", ""))
            base_color = palette.get(slot)
            if base_color:
                mods = _modifiers_of(scheme)
                return (
                    apply_color_modifiers(base_color, mods) if mods
                    else base_color
                )
    return None


def _resolve_relative_path(base_dir: str, relative: str) -> str:
    parts = base_dir.split("/")
    for seg in relative.split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg not in (".", ""):
            parts.append(seg)
    return "/".join(parts)


# ------------------------------ step 1: rels 链 ----------------------------- #

def resolve_theme_xml(zf: zipfile.ZipFile) -> tuple[str, str]:
    """rels 链：presentation.xml.rels → slideMaster → theme XML。

    清晰失败：链上任一环缺失都报 ThemeExtractError（不回退猜测路径）。
    返回 (theme_xml, slide_master_xml)。
    """
    pres_rels_name = "ppt/_rels/presentation.xml.rels"
    if pres_rels_name not in zf.namelist():
        raise ThemeExtractError(
            f"theme_unresolvable: 缺 {pres_rels_name}（rels 链起点缺失）"
        )
    rels = ET.fromstring(zf.read(pres_rels_name))
    slide_master_path = None
    for rel in rels:
        rtype = rel.get("Type", "")
        if "/slideMaster" in rtype and rel.get("Target"):
            target = rel.get("Target")
            slide_master_path = (
                target if target.startswith("ppt/") else f"ppt/{target}"
            )
            break
    if not slide_master_path:
        raise ThemeExtractError(
            "theme_unresolvable: presentation.xml.rels 无 slideMaster 关系"
        )
    if slide_master_path not in zf.namelist():
        raise ThemeExtractError(
            f"theme_unresolvable: slideMaster 缺失（{slide_master_path}）"
        )
    slide_master_xml = zf.read(slide_master_path).decode("utf-8")

    sm_dir = slide_master_path.rsplit("/", 1)[0]
    sm_file = slide_master_path.rsplit("/", 1)[1]
    sm_rels_name = f"{sm_dir}/_rels/{sm_file}.rels"
    if sm_rels_name not in zf.namelist():
        raise ThemeExtractError(
            f"theme_unresolvable: 缺 slideMaster 关系文件（{sm_rels_name}）"
        )
    sm_rels = ET.fromstring(zf.read(sm_rels_name))
    theme_path = None
    for rel in sm_rels:
        rtype = rel.get("Type", "")
        if "/theme" in rtype and rel.get("Target"):
            theme_path = _resolve_relative_path(sm_dir, rel.get("Target"))
            break
    if not theme_path:
        raise ThemeExtractError(
            "theme_unresolvable: slideMaster.rels 无 theme 关系"
        )
    if theme_path not in zf.namelist():
        raise ThemeExtractError(f"theme_missing: {theme_path} 不在包内")
    return zf.read(theme_path).decode("utf-8"), slide_master_xml


# --------------------------- step 2: clrMap 解析 ---------------------------- #

def parse_clr_map(slide_master_xml: str) -> dict[str, str]:
    doc = ET.fromstring(slide_master_xml)
    clr_map_el = _find_deep(doc, "clrMap")
    mapping = dict(DEFAULT_CLR_MAP)
    if clr_map_el is None:
        return mapping
    for attr, value in clr_map_el.attrib.items():
        if value in THEME_COLOR_SLOTS:
            mapping[attr] = value
    return mapping


# --------------------------- step 3: theme palette -------------------------- #

def parse_theme_palette(theme_xml: str) -> tuple[dict[str, str | None], str, str]:
    """返回 (12 slot palette, raw heading font, raw body font)。"""
    doc = ET.fromstring(theme_xml)
    clr_scheme = _find_deep(doc, "clrScheme")
    palette: dict[str, str | None] = {slot: None for slot in THEME_COLOR_SLOTS}
    for slot in THEME_COLOR_SLOTS:
        palette[slot] = _color_from_element(_find_child(clr_scheme, slot))
    if not any(palette.values()):
        raise ThemeExtractError("theme_invalid: clrScheme 无任何可解析颜色槽")
    font_scheme = _find_deep(doc, "fontScheme")
    major_font = _find_deep(font_scheme, "majorFont")
    minor_font = _find_deep(font_scheme, "minorFont")
    raw_heading = (
        _find_child(major_font, "latin").get("typeface", "")
        if _find_child(major_font, "latin") is not None else ""
    )
    raw_body = (
        _find_child(minor_font, "latin").get("typeface", "")
        if _find_child(minor_font, "latin") is not None else ""
    )
    return palette, raw_heading, raw_body


# --------------------------- step 4: 内容扫描推导 --------------------------- #

def scan_slide_content(
    zf: zipfile.ZipFile,
    palette: dict[str, str | None],
    clr_map: dict[str, str],
    theme_heading_font: str,
    theme_body_font: str,
) -> dict[str, dict[str, float]]:
    """频次/加权频次表：heading_colors / body_colors / background_colors /
    shape_fill_colors / heading_fonts / body_fonts（确定性：平频按 hex 升序）。"""
    analysis: dict[str, dict[str, float]] = {
        "heading_colors": {}, "body_colors": {}, "background_colors": {},
        "shape_fill_colors": {}, "heading_fonts": {}, "body_fonts": {},
    }

    def bump(bucket: dict[str, float], key: str, amount: float) -> None:
        bucket[key] = bucket.get(key, 0.0) + amount

    slide_names = sorted(
        (n for n in zf.namelist()
         if n.startswith("ppt/slides/slide") and n.endswith(".xml")),
        key=lambda n: int("".join(ch for ch in n if ch.isdigit()) or 1),
    )
    for name in slide_names:
        slide_number = int("".join(ch for ch in name if ch.isdigit()) or 1)
        slide_weight = 1 / math.sqrt(max(1, slide_number))
        doc = ET.fromstring(zf.read(name))
        elements = list(doc.iter())

        bg = _find_deep(doc, "bg")
        bg_color = _resolve_color_from_fill(
            _find_deep(bg, "solidFill"), palette, clr_map
        )
        if bg_color:
            bump(analysis["background_colors"], bg_color, 1.0)

        for el in elements:
            if _local(el.tag) != "spPr":
                continue
            fill_color = _resolve_color_from_fill(
                _find_child(el, "solidFill"), palette, clr_map
            )
            if fill_color:
                bump(analysis["shape_fill_colors"], fill_color, 1.0)

        slide_heading: dict[str, float] = {}
        slide_big = set()
        for el in elements:
            if _local(el.tag) != "r":
                continue
            text_el = _find_child(el, "t")
            if text_el is None or not (text_el.text or "").strip():
                continue
            rPr = _find_child(el, "rPr")
            font_size = 0
            if rPr is not None and rPr.get("sz"):
                try:
                    font_size = int(rPr.get("sz"))
                except ValueError:
                    font_size = 0
            if not font_size:
                pPr = _find_child(el, "pPr")
                defRPr = _find_child(pPr, "defRPr")
                if defRPr is not None and defRPr.get("sz"):
                    try:
                        font_size = int(defRPr.get("sz"))
                    except ValueError:
                        font_size = 0
            if not font_size:
                font_size = 1800  # 上游默认：18pt body

            color = None
            if rPr is not None:
                color = _resolve_color_from_fill(
                    _find_child(rPr, "solidFill"), palette, clr_map
                )
            if color is None:
                pPr = _find_child(el, "pPr")
                defRPr = _find_child(pPr, "defRPr")
                color = _resolve_color_from_fill(
                    _find_child(defRPr, "solidFill"), palette, clr_map
                )
            if color:
                if font_size >= HEADING_SIZE_THRESHOLD:
                    weighted = slide_weight * max(1, font_size)
                    bump(slide_heading, color, weighted)
                    if font_size >= BIG_HEADING_SIZE_THRESHOLD:
                        slide_big.add(color)
                else:
                    bump(analysis["body_colors"], color, 1.0)

            font_name = None
            latin = _find_child(rPr, "latin")
            tf = latin.get("typeface") if latin is not None else None
            if tf:
                if tf.startswith("+mj"):
                    font_name = theme_heading_font
                elif tf.startswith("+mn"):
                    font_name = theme_body_font
                else:
                    font_name = tf
            if font_name:
                bucket = (
                    analysis["heading_fonts"]
                    if font_size >= HEADING_SIZE_THRESHOLD
                    else analysis["body_fonts"]
                )
                bump(bucket, font_name, 1.0)

        if slide_heading:
            penalty = 1 / len(slide_big) if len(slide_big) > 1 else 1.0
            for color, weight in slide_heading.items():
                adjusted = weight * penalty if color in slide_big else weight
                bump(analysis["heading_colors"], color, adjusted)
    return analysis


def _top_of(bucket: dict[str, float], exclude: str | None = None) -> str | None:
    """频次最高者；平频按 hex 升序破平（确定性）。"""
    best_key, best_val = None, -1.0
    for key in sorted(bucket):
        if exclude is not None and key == exclude:
            continue
        if bucket[key] > best_val:
            best_key, best_val = key, bucket[key]
    return best_key


# --------------------------- step 5: leo 四角色 ----------------------------- #

def derive_roles(
    palette: dict[str, str | None],
    clr_map: dict[str, str],
    analysis: dict[str, dict[str, float]],
) -> tuple[dict[str, dict[str, str]], list[str]]:
    roles: dict[str, dict[str, str]] = {}
    trace: list[str] = []

    bg_top = _top_of(analysis["background_colors"])
    bg1 = palette.get(clr_map.get("bg1", "lt1")) or palette.get("lt1")
    background = bg_top or bg1 or "#FFFFFF"
    roles["background"] = {
        "hex": background,
        "derived_from": (
            f"slide bg top({int(analysis['background_colors'].get(bg_top, 0))} 处)"
            if bg_top else "theme bg1"
        ),
    }

    shape_top = _top_of(analysis["shape_fill_colors"])
    accent1 = palette.get("accent1")
    if shape_top:
        primary = shape_top
        same_as_accent1 = shape_top == accent1
        trace.append(
            f"primary: shapeFill {shape_top} ×"
            f"{int(analysis['shape_fill_colors'].get(shape_top, 0))}"
            + ("（与 theme accent1 一致）" if same_as_accent1 else "")
        )
    else:
        primary = accent1 or palette.get("accent2") or background
        trace.append(f"primary: 无 shapeFill，取 theme accent1 {primary}")
    roles["primary"] = {"hex": primary, "derived_from": "shapeFill top" if shape_top else "theme accent1"}

    heading_top = _top_of(analysis["heading_colors"], exclude=None)
    heading_excl_text = _top_of(
        analysis["heading_colors"],
        exclude=_top_of(analysis["body_colors"]),
    )
    heading_pick = heading_excl_text or heading_top
    accent2 = palette.get("accent2")
    if heading_pick:
        accent = heading_pick
        trace.append(
            f"accent: heading 加权高频 {heading_pick}"
            + (f"（theme accent2 {accent2} 对照）" if accent2 else "")
        )
    else:
        accent = accent2 or primary
        trace.append(f"accent: 无 heading 色，取 theme accent2 {accent}")
    roles["accent"] = {
        "hex": accent, "derived_from": "heading weighted top" if heading_pick else "theme accent2",
    }

    # secondary：accent3-6 中与 primary 色距最大者（分散度选一）
    candidates = {
        slot: palette[slot] for slot in
        ("accent3", "accent4", "accent5", "accent6") if palette.get(slot)
    }
    if candidates:
        secondary_slot = max(
            sorted(candidates),
            key=lambda s: (color_distance(candidates[s], primary), s),
        )
        secondary = candidates[secondary_slot]
        trace.append(
            f"secondary: accent3-6 中与 primary 色距最大 → {secondary_slot} "
            f"{secondary}（色距 {color_distance(secondary, primary):.0f}）"
        )
        derived = f"theme {secondary_slot}（色距分散度）"
    else:
        dk2 = palette.get("dk2") or palette.get("dk1") or accent
        secondary = dk2
        trace.append(f"secondary: theme 无 accent3-6，回退 dk2/dk1 {secondary}")
        derived = "theme dk2 fallback"
    roles["secondary"] = {"hex": secondary, "derived_from": derived}

    body_top = _top_of(analysis["body_colors"])
    dk1 = palette.get(clr_map.get("tx1", "dk1")) or palette.get("dk1")
    if body_top:
        neutral = body_top
        trace.append(
            f"neutral: body 高频色 {body_top}"
            + (f"（theme dk1 {dk1} 对照）" if dk1 else "")
        )
        neutral_from = "body top"
    else:
        neutral = dk1 or "#1F2937"
        trace.append(f"neutral: 无 body 色，取 theme dk1 {neutral}")
        neutral_from = "theme dk1"
    roles["neutral"] = {"hex": neutral, "derived_from": neutral_from}
    return roles, trace


# ------------------------------- main entry --------------------------------- #

def extract_theme(path: Path) -> dict:
    data = path.read_bytes()
    source_sha = hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(path) as zf:
        theme_xml, slide_master_xml = resolve_theme_xml(zf)
        try:
            clr_map = parse_clr_map(slide_master_xml)
            palette, raw_heading, raw_body = parse_theme_palette(theme_xml)
        except ET.ParseError as exc:
            raise ThemeExtractError(f"theme_invalid: XML 不可解析（{exc}）") from exc
        analysis = scan_slide_content(
            zf, palette, clr_map, raw_heading, raw_body
        )

    # 字体：slide 扫描 top 覆盖 theme 声明（同上游）；映射 applied 记录
    applied: list[str] = []

    def font_entry(raw: str, scanned: str | None, label: str) -> dict:
        chosen = scanned or raw
        if chosen in OFFICE_FONT_MAP:
            mapped = OFFICE_FONT_MAP[chosen]
            entry_note = None
            if f"{chosen}→{mapped}" not in applied:
                applied.append(f"{chosen}→{mapped}")
        else:
            mapped = None
            entry_note = "生图后端可用性需样张验证"
        entry = {
            "raw": chosen,
            "mapped": mapped,
            "source": "slide scan" if scanned else "theme fontScheme",
        }
        if entry_note:
            entry["note"] = entry_note
        return entry

    heading_font = font_entry(
        raw_heading, _top_of(analysis["heading_fonts"]), "heading"
    )
    body_font = font_entry(raw_body, _top_of(analysis["body_fonts"]), "body")

    roles, trace = derive_roles(palette, clr_map, analysis)
    background = roles.pop("background")

    result = {
        "schema_version": 1,
        "source_pptx_sha256": source_sha,
        "fonts": {"heading": heading_font, "body": body_font},
        "office_font_map_applied": sorted(applied),
        "roles": {
            "primary": roles["primary"],
            "secondary": roles["secondary"],
            "accent": roles["accent"],
            "neutral": roles["neutral"],
        },
        "role_derivation_trace": trace,
        "background": background,
        "suggested_overrides": [
            f"--color {role}={info['hex']}"
            for role, info in sorted(roles.items())
        ],
    }
    return result


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="可信 PPTX 主题提取（rels 链 + 12 slot + 字体映射 + 四角色推导；"
                    "仅 Trust Gate + preflight 通过后运行；HEX 只走 --color 覆盖通道）",
    )
    ap.add_argument("pptx", help="可信 PPTX 路径（Office Trust Gate 须已通过）")
    ap.add_argument(
        "--json", metavar="OUT",
        help="结果 JSON 写入 OUT（'-' 为 stdout，默认打印 stdout）；"
             "确定性键排序、无时间戳，可重放比对",
    )
    args = ap.parse_args(argv)
    path = Path(args.pptx)
    if not path.is_file():
        print(f"[ERROR] {path}: 文件不存在", file=sys.stderr)
        return 2
    try:
        result = extract_theme(path)
    except zipfile.BadZipFile:
        print(f"[ERROR] {path}: 不是合法 ZIP/PPTX", file=sys.stderr)
        return 2
    except ThemeExtractError as exc:
        print(f"[FAIL] {path}: {exc}", file=sys.stderr)
        print("reason: theme_extraction_failed（清晰失败不静默降级；"
              "确认源文件含 theme 关系链后重试）", file=sys.stderr)
        return 1
    except ET.ParseError as exc:
        print(f"[FAIL] {path}: XML 不可解析（{exc}）", file=sys.stderr)
        return 1
    payload = json.dumps(
        result, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    if args.json and args.json != "-":
        Path(args.json).write_text(payload, encoding="utf-8")
        print(f"wrote {args.json}")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
