"""模板知识库加载器：把分节轴文档（论证模式/信息图类型/图片渲染/版式库）结构化
读取，并组合成 deck_spec 的确定性注入内容。

The reference library has two kinds of markdown: full style briefs (embedded
JSON, handled by styles.py) and prose axis documents (论证模式、信息图类型、
图片渲染、结构布局、品牌身份、图表语法、版式库、页面语义). This module loads
the prose axes into structured dicts so that `leo-ppt style render` can compose
them deterministically into the deck_spec fields that prepare_slide_prompts.py
already injects (Global Style / Layout blocks).
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from .styles import StyleStoreError, StyleSelectionChanged, StyleSelectionInvalid, builtin_style_path, load_style, selection_fingerprint, parse_style_document, validate_style_metadata, describe_style_asset


class TemplateError(ValueError):
    reason_code = "template_store_error"


def _styles_root() -> Path:
    return builtin_style_path("_placeholder").parent


def _read_md(rel: str) -> str:
    path = _styles_root() / rel
    if not path.is_file():
        raise TemplateError(f"template_not_found: {rel}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TemplateError(f"template_unreadable: {rel}") from exc


def _field(text: str, key: str) -> str:
    """Extract the value after a bold field label. Supports both upstream
    conventions: the colon inside the closing asterisks (「**骨架:**」) and
    outside (「**骨架**:」), plus the fullwidth colon. The value ends at the
    first newline; empty values must not swallow the next field's content."""
    bare = key.strip("*")
    m = re.search(
        rf"\*{{0,2}}{bare}\*{{0,2}}[ \t]*[:\：][ \t]*\*{{0,2}}[ \t]*(.*?)(?=\n|\Z)",
        text,
        re.S,
    )
    return m.group(1).strip() if m else ""


def _section(text: str, heading: str) -> str:
    """Extract the body under a `## heading` until the next section or `---`.
    The heading is matched literally; only the rest of its line is loose."""
    m = re.search(
        rf"##\s+{re.escape(heading)}[^\n]*\n(.*?)(?=\n##|\n---|\Z)", text, re.S
    )
    return m.group(1).strip() if m else ""


def _blockquote(text: str) -> str:
    """Extract the first `> ...` quote block (the paste-ready paragraph)."""
    m = re.search(r"> (.+?)(?=\n\n|\Z)", text, re.S)
    return m.group(1).strip() if m else ""


def _table(text: str) -> dict[str, str]:
    """Parse a two-column markdown table into {row-key: row-value},
    skipping the `| --- | --- |` separator row."""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"\| ([^|]+) \| ([^|]+) \|", line)
        if not m:
            continue
        cells = (m.group(1), m.group(2))
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        rows[m.group(1).strip()] = m.group(2).strip()
    return rows


# --------------------------------------------------------------------------- #
# Axis loaders
# --------------------------------------------------------------------------- #

def load_rendering(name: str) -> dict:
    """Load an AI-image rendering (08_图片渲染) into {positioning, paste_ready, ltd}."""
    text = _read_md(f"08_图片渲染/{name}.md")
    style_para = _section(text, "1. 风格段落")
    if not style_para:  # heading variants
        style_para = text
    return {
        "name": name,
        "positioning": _field(text, "**定位**"),
        "paste_ready": _blockquote(style_para),
        "line_texture_depth": _table(_section(text, "2. 线条 · 纹理 · 深度")),
    }


_LAYOUT_RULE_FILES = ("00_", "01_常犯", "02_关键类清单")


def load_layout(name: str) -> dict:
    """Load a page layout (12_版式库, e.g. 'P6', 'KPI Tower', '06_KPI_Tower').

    Resolution is fail-fast: rule documents (00_选版式P0原则 / 01_常犯错误)
    are never layouts; an exact filename-stem match wins; otherwise a title
    substring match must be unambiguous, or candidates are listed in the error.
    """
    root = _styles_root() / "12_版式库"
    exact: list[Path] = []
    by_title: list[tuple[Path, str]] = []
    for path in sorted(root.glob("*.md")):
        if path.stem.startswith(_LAYOUT_RULE_FILES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        title = text.splitlines()[0] if text else ""
        # "P1"/"P6" are first-class layout ids and must match only P1/P6,
        # never P10-P19 via substring.
        code = re.match(r"#\s*版式[:：]\s*(P\d+)\b", title)
        if path.stem == name or (code and name.upper() == code.group(1)):
            exact.append(path)
            continue
        if name in title:
            by_title.append((path, title))
    if len(exact) == 1:
        path = exact[0]
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0] if text else ""
    elif len(exact) > 1:
        raise TemplateError(
            f"layout_ambiguous: {name} -> " + ", ".join(p.stem for p in exact)
        )
    elif len(by_title) == 1:
        path, title = by_title[0]
        text = path.read_text(encoding="utf-8")
    elif len(by_title) > 1:
        raise TemplateError(
            f"layout_ambiguous: {name} -> "
            + ", ".join(t.strip("# ").strip() for _, t in by_title)
        )
    else:
        raise TemplateError(f"layout_not_found: {name}")
    return {
        "name": title.replace("# 版式：", "").strip(),
        "purpose": _field(text, "**用途**"),
        "content_type": _field(text, "**适用内容类型**"),
        "skeleton": _field(text, "**骨架**"),
        "key_classes": _field(text, "**关键类**"),
        "motion": _field(text, "**动效 recipe**"),
    }


def load_image_type(name: str) -> dict:
    """Load an infographic type (07_信息图类型) into {positioning, skeleton}.
    The positioning is the first prose paragraph under the title (no bold
    label), and the skeleton is the `## 1. 构图骨架` section."""
    text = _read_md(f"07_信息图类型/{name}.md")
    positioning = ""
    for line in text.splitlines()[1:]:
        if line.startswith(("#", ">", "|")) or not line.strip():
            continue
        positioning = line.strip()
        break
    return {
        "name": name,
        "positioning": positioning,
        "skeleton": _section(text, "1. 构图骨架") or text,
    }


def load_mode(name: str) -> dict:
    """Load an argument mode (06_论证模式) into {name, skeleton}."""
    text = _read_md(f"06_论证模式/{name}.md")
    return {
        "name": name,
        "skeleton": _section(text, "1. 论证骨架") or text,
    }


# --------------------------------------------------------------------------- #
# Pairing map (视觉风格 ↔ 图片渲染), parsed from the pairing table doc
# --------------------------------------------------------------------------- #

def _pairs() -> dict[str, str]:
    text = _read_md("00_索引/视觉风格配对.md")
    pairs: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"\| ([^|]+) \| ([^|]+) \|", line)
        if m:
            pairs[m.group(1).strip()] = m.group(2).strip()
    return pairs


def paired_rendering(visual_style: str) -> str | None:
    return _pairs().get(visual_style)


# --------------------------------------------------------------------------- #
# Composers: deterministic injection content for deck_spec
# --------------------------------------------------------------------------- #

class StyleColorOverrideError(StyleStoreError):
    """Deck-level palette override violated the role/HEX contract."""

    reason_code = "style_color_override_invalid"


_COLOR_ROLES = ("primary", "secondary", "accent", "neutral")
_HEX_VALUE_RE = re.compile(r"#[0-9A-Fa-f]{6}\Z")
_HEX_ANCHOR_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def _merge_palette_override(brief_palette: object, colors: dict[str, str]) -> dict:
    """Merge a deck-level ``role -> #RRGGBB`` override onto the brief palette.

    Fails loud on every shadow path (unknown role, non-HEX value, role the
    target brief does not carry, brief without a palette): silently dropping
    a requested override would betray the fail-fast contract. Builtin briefs
    missing at least one role are real, not theoretical.
    """
    if not isinstance(brief_palette, dict) or not brief_palette:
        raise StyleColorOverrideError("style_color_override_invalid: no palette")
    merged = dict(brief_palette)
    for role, value in colors.items():
        if role not in _COLOR_ROLES:
            raise StyleColorOverrideError(
                f"style_color_override_invalid: role {role!r} not in {_COLOR_ROLES}"
            )
        if not isinstance(value, str) or not _HEX_VALUE_RE.match(value):
            raise StyleColorOverrideError(
                f"style_color_override_invalid: {role}={value!r} is not #RRGGBB"
            )
        if role not in brief_palette:
            raise StyleColorOverrideError(
                f"style_color_override_invalid: brief has no {role} role"
            )
        merged[role] = value
    return merged


class StyleLayoutLockError(StyleStoreError):
    """``--layout-lock`` requested but the brief/sidecar carries no usable
    layout-system key (fail-loud: never silently skip the lock)."""

    reason_code = "layout_lock_unavailable"


# Layout-system anchor fields (R-31, xhs-visual-director master-lock prefix):
# grid tokens / safe margins / page-number slot / corner radius / line weight.
# All five must be present non-empty before the lock block is injected —
# a partial lock would silently re-open the drift it exists to prevent.
_LAYOUT_LOCK_FIELDS = ("grid", "safe_margin", "page_no", "corner_radius", "line_weight")

_LAYOUT_LOCK_LABELS = {
    "grid": "网格锚",
    "safe_margin": "安全边距锚",
    "page_no": "页码位锚",
    "corner_radius": "圆角锚",
    "line_weight": "线重锚",
}


def _layout_lock_block(brief_layout: object, sidecar: object) -> list[str]:
    """Deterministic layout-system lock block for ``--layout-lock`` (R-31).

    Source resolution honors the deck contract: the machine-readable
    ``token_sidecar.layout`` key wins over the brief's top-level ``layout``
    key (the sidecar is the effective token surface, same as palette). With
    neither source carrying a usable dict the call fails with
    ``layout_lock_unavailable`` instead of silently skipping the lock; the
    same error names the first missing field when the dict is partial.
    """
    source: object = None
    origin = "brief"
    if isinstance(sidecar, dict) and isinstance(sidecar.get("layout"), dict):
        source = sidecar["layout"]
        origin = "token_sidecar"
    elif isinstance(brief_layout, dict):
        source = brief_layout
    if not isinstance(source, dict) or not source:
        raise StyleLayoutLockError(
            "layout_lock_unavailable: --layout-lock requires a layout key "
            "(grid/safe_margin/page_no/corner_radius/line_weight) on the "
            "brief top level or token_sidecar; this style carries none — "
            "add one or drop the flag (see references/render-contract.md §13)"
        )
    for field in _LAYOUT_LOCK_FIELDS:
        value = source.get(field)
        if not isinstance(value, str) or not value.strip():
            raise StyleLayoutLockError(
                f"layout_lock_unavailable: layout.{field} is missing/empty "
                f"(all of {_LAYOUT_LOCK_FIELDS} are required for the lock "
                f"block; source: {origin})"
            )
    lines = ["【版式锚（逐页逐字节相同注入，防网格/页码/边距漂移）】"]
    for field in _LAYOUT_LOCK_FIELDS:
        lines.append(f"{_LAYOUT_LOCK_LABELS[field]}：{source[field].strip()}")
    return lines


class StyleVarOverrideError(StyleStoreError):
    """Token-sidecar variable override violated the key/HEX/contrast contract."""

    reason_code = "style_var_override_invalid"


# Token-sidecar ink keys under the contrast hard gate. Floors follow the
# dual-threshold guardrail (00_索引/通用设计规范): body-text tokens
# (primary/text) must hold 4.5:1; accent is an emphasis/large-token face
# and only owes the 3:1 non-text floor — H-line theme.json ships real
# sub-4.5 accents, so gating them would false-block legitimate overrides.
_SIDECAR_INK_FLOORS = {"primary": 4.5, "text": 4.5, "accent": 3.0}


def _sidecar_hex(value: object) -> str | None:
    """Return the value when it is a pure ``#RRGGBB`` token, else None."""
    if isinstance(value, str) and _HEX_VALUE_RE.match(value):
        return value
    return None


def _enforce_sidecar_contrast(palette: dict, overridden: set[str]) -> None:
    """Hard contrast gate for ``--var`` palette overrides (brand_contrast
    reuse: same WCAG ratio math, same nearest-compliant suggestion).

    Checks the overridden ink keys against the effective background token
    (``palette.background`` when it is a HEX token, else #FFFFFF — the same
    default the brand path uses). Overriding ``background`` re-checks every
    ink key, so both directions of drift are caught; pre-existing tokens
    the user did not touch are not gated (fail on the override, not on the
    brief — mirrors ``brand_contrast_insufficient`` scope).
    """
    bg = _sidecar_hex(palette.get("background")) or "#FFFFFF"
    bg_overridden = "background" in overridden
    for key, floor in _SIDECAR_INK_FLOORS.items():
        if key not in overridden and not bg_overridden:
            continue
        value = _sidecar_hex(palette.get(key))
        if value is None:
            continue
        ratio = _contrast_ratio(value, bg)
        if ratio < floor:
            raise StyleVarOverrideError(
                f"style_var_contrast_insufficient: palette.{key} {value} vs "
                f"background {bg} = {ratio:.2f}:1（{key} 下限 {floor}）；"
                f"最近合规建议 {_suggest_accessible(value, bg, floor)}"
            )


def _merge_token_sidecar(sidecar: object, overrides: dict[str, str]) -> dict:
    """Merge ``--var key=value`` overrides onto the brief's token sidecar.

    Keys are dotted paths into the sidecar (``palette.primary`` /
    ``typography.title`` / ``density``); only keys the sidecar already
    carries can be overridden (same fail-fast shape as
    ``_merge_palette_override``). Palette values must be ``#RRGGBB``;
    typography/density values non-empty strings. Any ``palette.*``
    override triggers the contrast hard gate afterwards. The parsed brief
    is never mutated in place.
    """
    if not isinstance(sidecar, dict):
        raise StyleVarOverrideError(
            "style_var_override_invalid: no token_sidecar (brief must carry "
            "one before --var can override; see references/render-contract.md)"
        )
    merged = copy.deepcopy(sidecar)
    overridden_palette: set[str] = set()
    for path, value in overrides.items():
        section, dot, key = path.partition(".")
        if dot:
            sub = merged.get(section)
            if section not in ("palette", "typography") or not isinstance(sub, dict):
                raise StyleVarOverrideError(
                    f"style_var_override_invalid: unknown key {path!r}"
                )
            if key not in sub:
                raise StyleVarOverrideError(
                    f"style_var_override_invalid: sidecar has no {path!r} key"
                )
            if section == "palette":
                if _sidecar_hex(value) is None:
                    raise StyleVarOverrideError(
                        f"style_var_override_invalid: {path}={value!r} is not #RRGGBB"
                    )
                overridden_palette.add(key)
            elif not isinstance(value, str) or not value.strip():
                raise StyleVarOverrideError(
                    f"style_var_override_invalid: {path} value is empty"
                )
            sub[key] = value
        elif isinstance(merged.get(section), str):
            if not isinstance(value, str) or not value.strip():
                raise StyleVarOverrideError(
                    f"style_var_override_invalid: {section} value is empty"
                )
            merged[section] = value
        else:
            raise StyleVarOverrideError(
                f"style_var_override_invalid: unknown key {path!r}"
            )
    if overridden_palette:
        _enforce_sidecar_contrast(merged["palette"], overridden_palette)
    return merged


def _guardrail_block(palette: object) -> list[str]:
    """Deterministic design-guardrail digest for the ``--guardrail`` route.

    Fixed lines plus at most one accent anchor line derived from the
    *effective* (post-override) palette — first #RRGGBB inside the accent
    role's prose; when the accent carries no HEX the whole line is omitted
    instead of rendering empty. Same palette in, same bytes out.
    """
    lines = [
        "【设计护栏摘要】（依据 00_索引/通用设计规范.md 与 00_索引/版心Canon.md）",
        "字号下限双口径：1920 HTML 画布 正文≥18px/卡片图注≥16px/meta≥14px；"
        "2560 生图画布 正文≥32px/caption≥28px/meta≥24px。",
        "对比度：正文对背景 ≥4.5:1；大字与非文本 ≥3:1；双重编码铁律（关键信息不得只靠颜色区分）。",
        "字号一律取 版心Canon 字阶刻度；大字 min(Xvw,Yvh) 双约束且 Y≥1.6X；数值落 0.4vw 模数。",
        "图表数值呈现遵守 00_索引/图表样式规范.md（直接标注优先；估算 ~ 前缀+虚线；示意禁入量化图形）。",
    ]
    if isinstance(palette, dict):
        anchor = _HEX_ANCHOR_RE.search(str(palette.get("accent", "")))
        if anchor:
            lines.append(
                f"accent 锚点：{anchor.group(0)}（deck 级覆盖用 --color accent=#RRGGBB）。"
            )
    return lines


# --- Brand identity axis (10_品牌身份 / ${LEO_PPT_HOME}/brands) ---------------

_BRAND_SUBDIR = "10_品牌身份"


def _brand_candidates(name: str) -> list[Path]:
    from .config.runtime_config import default_home

    home_brands = default_home() / "brands" / f"{name}.md"
    return [home_brands, _styles_root() / _BRAND_SUBDIR / f"{name}.md"]


def load_brand(name: str) -> dict:
    """Load a brand-identity brief (field-style markdown, no JSON block).

    Resolution order honors the deck contract: user-saved brand
    (``${LEO_PPT_HOME}/brands/<name>.md``) wins over the builtin preset axis.
    Returns primary/accent HEX (empty string when absent), typography, tone,
    and the verified_at provenance the builtin files carry.
    """
    for path in _brand_candidates(name):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise TemplateError(f"brand_unreadable: {name}") from exc
        hexes = _HEX_ANCHOR_RE.findall(text)
        return {
            "name": name,
            "primary": hexes[0] if hexes else "",
            "accent": hexes[1] if len(hexes) > 1 else "",
            "typography": _field(text, "字体"),
            "tone": _field(text, "语气"),
            "verified_at": _field(text, "verified_at"),
            "source": str(path),
        }
    raise TemplateError(f"brand_not_found: {name}")


def _relative_luminance(hex_value: str) -> float:
    def chan(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r = chan(int(hex_value[1:3], 16))
    g = chan(int(hex_value[3:5], 16))
    b = chan(int(hex_value[5:7], 16))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: str, bg: str = "#FFFFFF") -> float:
    l1, l2 = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _suggest_accessible(hex_value: str, bg: str = "#FFFFFF",
                        target: float = 4.5) -> str:
    """Darken/Lighten toward the background until the target ratio holds."""
    bg_lum = _relative_luminance(bg)
    r, g, b = (int(hex_value[i:i + 2], 16) for i in (1, 3, 5))
    step = -8 if bg_lum > 0.5 else 8
    for _ in range(64):
        r = min(255, max(0, r + step))
        g = min(255, max(0, g + step))
        b = min(255, max(0, b + step))
        cand = f"#{r:02X}{g:02X}{b:02X}"
        if _contrast_ratio(cand, bg) >= target:
            return cand
    return "#000000" if bg_lum > 0.5 else "#FFFFFF"


def _style_anchor_block(palette: object, typography: object,
                        rendering_name: object) -> list[str]:
    """Deterministic style anchor appended to every page prompt (anti-drift).

    Same palette/typography/rendering in → same bytes out. HEX tokens keep
    their first-appearance order from the effective (post-override) palette.
    """
    lines = ["【风格锚（逐页逐字节相同注入，防风格漂移）】"]
    seen: list[str] = []
    if isinstance(palette, dict):
        for value in palette.values():
            for hx in _HEX_ANCHOR_RE.findall(str(value)):
                if hx not in seen:
                    seen.append(hx)
    if seen:
        lines.append("HEX 锚：" + " ".join(seen))
    if isinstance(typography, dict):
        fonts = typography.get("title") or typography.get("font") or ""
        if fonts:
            lines.append(f"字族锚：{str(fonts)[:80]}")
    if rendering_name:
        lines.append(f"渲染锚：{str(rendering_name)[:60]}")
    return lines if len(lines) > 1 else []


def compose_style(
    visual_style: str,
    *,
    mode: str | None = None,
    colors: dict[str, str] | None = None,
    var_overrides: dict[str, str] | None = None,
    brand: str | None = None,
    anchor: bool = False,
    guardrail: bool = False,
    layout_lock: bool = False,
    home: Path | None = None,
    expected_selection: str | None = None,
) -> dict:
    """Merge the visual-style brief, its paired image rendering (paste-ready
    paragraph), and the argument mode into one deterministic dict for
    `deck_spec.style`.

    ``colors`` applies a deck-level role override (see
    ``_merge_palette_override``; every invalid shape fails with
    ``style_color_override_invalid``). ``var_overrides`` applies ``--var``
    overrides onto the brief's machine-readable ``token_sidecar`` (see
    ``_merge_token_sidecar``; invalid shapes fail with
    ``style_var_override_invalid``, palette overrides additionally pass the
    contrast hard gate). ``guardrail=True`` appends the
    deterministic guardrail digest and ``layout_lock=True`` the
    layout-system lock block (``token_sidecar.layout`` wins over the
    brief's top-level ``layout`` key; neither present →
    ``layout_lock_unavailable``, see ``_layout_lock_block``) — both flags
    default off so the default output stays byte-identical to the
    no-flag path and snapshot consumers are unaffected.
    """
    if expected_selection is not None and not re.fullmatch(r"[a-f0-9]{64}", expected_selection):
        raise StyleSelectionInvalid("style_selection_invalid")
    if expected_selection is not None:
        style = load_style(visual_style, home=home, enforce_scope=True)
    elif home is not None:
        style = load_style(visual_style, home=home)
    else:
        style = load_style(visual_style)
    if expected_selection is not None and selection_fingerprint(style, home=home) != expected_selection:
        raise StyleSelectionChanged("style_selection_changed")
    if expected_selection is not None:
        from jsonschema import Draft7Validator

        document = parse_style_document(style["content"])
        parsed = document["brief"]
        selected_path = Path(style["path"])
        selected_asset = describe_style_asset(selected_path, selected_path.parent,
                                              body=style["content"].encode("utf-8"))
        schema = json.loads((Path(__file__).parent / "schemas/style-brief-v1.schema.json").read_text())
        if (parsed is None or not document["first_block_is_brief"] or document["problems"]
                or selected_asset["asset_role"] not in {"style", "pool"}
                or selected_asset["diagnostics"]
                or validate_style_metadata(parsed) or not Draft7Validator(schema).is_valid(parsed)):
            raise StyleSelectionInvalid("style_selection_invalid")
    m = re.search(r"```json\n(.*?)\n```", style["content"], re.S)
    if not m:
        raise TemplateError(f"style_brief_missing: {visual_style}")
    try:
        brief = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise TemplateError(f"style_brief_invalid: {visual_style}") from exc
    palette: object = brief.get("color_palette")
    if colors:
        palette = _merge_palette_override(palette, colors)
    # Token sidecar passthrough/override: absent sidecar + no --var → key
    # absent (byte red line for the 137 briefs without one).
    token_sidecar = None
    if var_overrides:
        token_sidecar = _merge_token_sidecar(brief.get("token_sidecar"), var_overrides)
    elif isinstance(brief.get("token_sidecar"), dict):
        token_sidecar = copy.deepcopy(brief["token_sidecar"])
    if brand:
        # 合并优先序（合同）：用户品牌 > 用户 colors > 风格默认 —— 品牌最后覆盖。
        bd = load_brand(brand)
        overrides = {r: bd[r] for r in ("primary", "accent") if bd[r]}
        if overrides:
            palette = _merge_palette_override(palette, overrides)
        for role, value in overrides.items():
            ratio = _contrast_ratio(value)
            if ratio < 4.5:
                raise StyleColorOverrideError(
                    f"brand_contrast_insufficient: {role} {value} vs #FFFFFF "
                    f"= {ratio:.2f}:1（浅底正文下限 4.5）；最近合规建议 "
                    f"{_suggest_accessible(value)}"
                )
        composed_brand = {k: bd[k] for k in
                          ("name", "tone", "typography", "verified_at")}
    composed: dict = {
        "name": visual_style,
        "visual_direction": brief.get("visual_direction"),
        "color_palette": palette,
        "typography": brief.get("typography"),
        "layout_patterns": brief.get("layout_patterns"),
    }
    if token_sidecar is not None:
        composed["token_sidecar"] = token_sidecar
    if brand:
        composed["brand"] = composed_brand
    if guardrail:
        composed["guardrail"] = _guardrail_block(palette)
    if layout_lock:
        # 版式锚读取生效 sidecar 的 layout 键优先于 brief 顶层（R-31）。
        composed["layout_lock"] = _layout_lock_block(
            brief.get("layout"), token_sidecar
        )
    rendering_name = None if expected_selection is not None and style["source"] == "user" else paired_rendering(visual_style)
    if rendering_name:
        try:
            composed["image_rendering"] = load_rendering(rendering_name)["paste_ready"]
        except TemplateError:
            composed["image_rendering"] = rendering_name
    if mode:
        composed["mode"] = load_mode(mode)["skeleton"]
    if anchor or brand:  # 默认路径保持 byte-identical；品牌与显式 --anchor 才注入锚
        anchor_block = _style_anchor_block(
            palette, composed.get("typography"), composed.get("image_rendering")
        )
        if anchor_block:
            composed["style_anchor"] = anchor_block
    return composed


def materialize_composition(layout_data: dict) -> str:
    """Translate a layout skeleton into an image-generation composition hint.

    The skeleton text is CSS dialect (`.cell-6`, `min(13vw,16vh)`) written for
    the editable route; a diffusion model has no use for class names or vw
    units. This strips CSS artifacts and restates sizes as percentages of the
    canvas so the injected prompt describes blocks, gutters and whitespace in
    the model's own resolution (deterministic for the same input).
    """
    skeleton = layout_data.get("skeleton", "")
    name = layout_data.get("name", "")

    def _min(match: re.Match) -> str:
        x, y = match.group(1), match.group(2)
        return f"不超过约{x}%画宽且不超过约{y}%画高"

    text = re.sub(r"min\(([\d.]+)vw,\s*([\d.]+)vh\)", _min, skeleton)
    text = re.sub(r"([\d.]+)vw", r"约\1%画宽", text)
    text = re.sub(r"([\d.]+)vh", r"约\1%画高", text)
    text = re.sub(r"\.[a-zA-Z][\w-]*", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return f"{name}:构图区块与占比——{text}"


def compose_layout(
    layout: str, *, image_type: str | None = None, materialize: bool = False
) -> dict:
    """Merge a page layout's skeleton and an optional infographic type into one
    deterministic dict for `slides[].layout`.

    Empty purpose/skeleton fields raise instead of silently injecting a layout
    with zero structural constraints. `materialize=True` adds a
    `composition_hint` for the image-generation route (CSS dialect translated
    into canvas-block terms)."""
    layout_data = load_layout(layout)
    for field in ("purpose", "skeleton"):
        if not layout_data[field]:
            raise TemplateError(
                f"layout_field_empty: {layout} ({field} is empty; fix the layout file)"
            )
    composed: dict = {
        "layout_name": layout_data["name"],
        "purpose": layout_data["purpose"],
        "content_requirements": layout_data["content_type"],
        "skeleton": layout_data["skeleton"],
    }
    if materialize:
        composed["composition_hint"] = materialize_composition(layout_data)
    if image_type:
        composed["image_type"] = load_image_type(image_type)["skeleton"]
    return composed


def list_templates() -> dict[str, list[str]]:
    """Enumerate the prose axis documents for discovery."""
    root = _styles_root()
    return {
        "renderings": sorted(p.stem for p in (root / "08_图片渲染").glob("*.md")),
        "layouts": sorted(p.stem for p in (root / "12_版式库").glob("*.md")
                          if not p.stem.startswith(_LAYOUT_RULE_FILES)),
        "image_types": sorted(p.stem for p in (root / "07_信息图类型").glob("*.md")),
        "modes": sorted(p.stem for p in (root / "06_论证模式").glob("*.md")),
    }
