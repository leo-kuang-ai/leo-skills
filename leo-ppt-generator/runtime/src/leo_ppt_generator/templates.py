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

from .styles import (
    StyleStoreError,
    StyleSelectionChanged,
    StyleSelectionInvalid,
    load_style,
    parse_style_document,
    selection_fingerprint,
)
from .asset_resolver import (
    AssetNotFoundError,
    AssetResolver,
    ResolverError,
    builtin_library_root,
)


def _styles_root() -> Path:
    """旧轴文档根：迁移归档树（retired-styles-tree）只读供 legacy 轴加载。"""
    return builtin_library_root().parent / "template-library/reference/sources/retired-styles-tree/styles"


class TemplateError(ValueError):
    reason_code = "template_store_error"


def _read_axis_body(group: str, name: str) -> str:
    """经统一 resolver 定位轴，再按 manifest.body_ref 读取正文。"""
    try:
        resolver = AssetResolver()
        hits = [hit for hit in resolver.lookup(name, kind="axis")
                if Path(hit["path"]).parts[-3] == group]
        if not hits:
            # 兼容旧入口传入未带轴前缀的短名（如“漏斗图”“故事弧”），
            # 仍从 resolver 实体集合消歧，不再按物理目录嗅探。
            query = name.casefold()
            hits = [hit for hit in resolver.entities
                    if hit["asset_id"].split(":")[1] == "axis"
                    and Path(hit["path"]).parts[-3] == group
                    and query in str(hit.get("name", "")).casefold()]
    except ResolverError as exc:
        raise TemplateError(f"template_not_found: axes/{group}/{name} ({exc.reason_code})") from exc
    if len(hits) > 1:
        raise TemplateError(
            f"template_ambiguous: axes/{group}/{name} -> "
            + ", ".join(sorted(hit["asset_id"] for hit in hits))
        )
    if not hits:
        raise TemplateError(f"template_not_found: axes/{group}/{name}")
    try:
        resolved = resolver.resolve(hits[0]["asset_id"])
        manifest_path = Path(resolved["path"]).resolve()
        body_ref = resolved["data"].get("body_ref")
        if not isinstance(body_ref, str) or not body_ref.strip():
            raise TemplateError(f"template_unreadable: axes/{group}/{name} body_ref missing")
        body_path = (manifest_path.parent / body_ref).resolve()
        if not body_path.is_relative_to(manifest_path.parent) or not body_path.is_file():
            raise TemplateError(f"template_unreadable: axes/{group}/{name} body_ref invalid")
        return body_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TemplateError(f"template_unreadable: axes/{group}/{name}") from exc


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
    """Load a canonical rendering axis into {positioning, paste_ready, ltd}."""
    text = _read_axis_body("rendering", name)
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


def _layouts_root() -> Path:
    return builtin_library_root() / "canonical" / "layouts"


def _notes_title(text: str) -> str:
    return text.splitlines()[0] if text else ""


def _parse_notes(title: str, text: str, fallback: dict | None = None) -> dict:
    """解析可读投影，并从 JSON 回填缺失字段。

    简化 notes 无须复制全部字段；几何和图片路线构图提示以
    ``layout.json`` 为真值。
    """
    fallback = fallback or {}
    renderer_support = fallback.get("renderer_support") or {}
    image_skeleton = renderer_support.get("image")
    return {
        "name": title.replace("# 版式：", "").lstrip("# ").strip(),
        "purpose": _field(text, "**用途**") or str(fallback.get("page_role") or ""),
        "content_type": _field(text, "**适用内容类型**"),
        "skeleton": _field(text, "**骨架**") or (
            str(image_skeleton) if isinstance(image_skeleton, str) else ""
        ),
        "key_classes": _field(text, "**关键类**"),
        "motion": _field(text, "**动效 recipe**"),
    }


def _notes_for_entity(resolved: dict) -> tuple[str, str] | None:
    """定位已解析版式实体的 notes.md：同目录 sibling 优先，其次按
    标题 P 码/名称匹配（layout.json 与 notes.md 分目录共存于新库）。"""
    entity_dir = Path(resolved["path"]).parent
    sibling = entity_dir / "notes.md"
    if sibling.is_file():
        try:
            text = sibling.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None
        return _notes_title(text), text
    aliases = [str(a).upper() for a in (resolved.get("aliases") or [])]
    display = str(resolved.get("name") or "")
    matches: list[tuple[str, str]] = []
    for path in sorted(_layouts_root().glob("*/notes.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        title = _notes_title(text)
        code = re.match(r"#\s*版式[:：]\s*(P\d+)\b", title)
        if (code and code.group(1) in aliases) or (display and display in title):
            matches.append((title, text))
    if len(matches) == 1:
        return matches[0]
    return None


def load_layout(name: str, *, home: Path | None = None) -> dict:
    """Load a page layout（新库协议：P 码/名称/ID 经 resolver，语义字段读
    canonical/layouts/&lt;slug&gt;/notes.md，缺 notes 时回退 layout.json 几何面）。

    身份解析委托 asset_resolver（kind=layout）：P 码别名精确命中，规则文档
    （00_选版式P0原则等）不是版式实体，天然不命中。resolver 无命中时按旧
    语义降级为 notes.md 标题扫描：P 码精确匹配（P1 绝不子串命中 P10-P19），
    其余子串命中必须唯一，否则 layout_ambiguous 列出候选。
    """
    try:
        resolver = AssetResolver(home=home)
        hits = resolver.lookup(name, kind="layout")
    except ResolverError as exc:
        raise TemplateError(f"layout_not_found: {name} ({exc.reason_code})") from exc
    if len(hits) > 1:
        raise TemplateError(
            f"layout_ambiguous: {name} -> "
            + ", ".join(sorted(hit["asset_id"] for hit in hits))
        )
    if hits:
        resolved = resolver.resolve(hits[0]["asset_id"])
        notes = _notes_for_entity(resolved)
        if notes is not None:
            title, text = notes
            return _parse_notes(title, text, resolved.get("data"))
        # 回退：实体缺 notes.md 时从 layout.json 投影语义字段（几何/容量
        # 真值仍在 layout.json；此处仅供展示面，空 purpose/skeleton 由
        # compose_layout 的 fail-fast 拦截）。
        data = resolved["data"]
        p_code = next((a for a in (resolved.get("aliases") or [])
                       if re.fullmatch(r"P\d+", str(a))), None)
        return {
            "name": " · ".join(part for part in (p_code, data.get("name")) if part),
            "purpose": str(data.get("page_role") or ""),
            "content_type": "",
            "skeleton": str((data.get("renderer_support") or {}).get("image") or ""),
            "key_classes": "",
            "motion": "",
        }
    # 旧语义降级：notes.md 标题扫描（P 码精确 / 子串唯一）。
    exact: list[tuple[str, str]] = []
    by_title: list[tuple[Path, str]] = []
    for path in sorted(_layouts_root().glob("*/notes.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        title = _notes_title(text)
        code = re.match(r"#\s*版式[:：]\s*(P\d+)\b", title)
        if code and name.upper() == code.group(1):
            exact.append((title, text))
            continue
        if name in title:
            by_title.append((path, title))
    if len(exact) == 1:
        title, text = exact[0]
    elif len(exact) > 1:
        raise TemplateError(
            f"layout_ambiguous: {name} -> "
            + ", ".join(t.strip("# ").strip() for t, _ in exact)
        )
    elif len(by_title) == 1:
        path = by_title[0][0]
        text = path.read_text(encoding="utf-8")
        title = _notes_title(text)
    elif len(by_title) > 1:
        raise TemplateError(
            f"layout_ambiguous: {name} -> "
            + ", ".join(t.strip("# ").strip() for _, t in by_title)
        )
    else:
        raise TemplateError(f"layout_not_found: {name}")
    return _parse_notes(title, text)


def load_image_type(name: str) -> dict:
    """Load a canonical infographic axis into {positioning, skeleton}.
    The positioning is the first prose paragraph under the title (no bold
    label), and the skeleton is the `## 1. 构图骨架` section."""
    text = _read_axis_body("infographic", name)
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
    """Load a canonical argument axis into {name, skeleton}."""
    text = _read_axis_body("argument", name)
    return {
        "name": name,
        "skeleton": _section(text, "1. 论证骨架") or text,
    }


# --------------------------------------------------------------------------- #
# Pairing map (视觉风格 ↔ 图片渲染), parsed from the pairing table doc
# --------------------------------------------------------------------------- #

def _pairs() -> dict[str, str]:
    path = builtin_library_root() / "governance" / "authoring" / "index" / "视觉风格配对.md"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
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


def _brand_candidates(name: str, *, home: Path | None = None) -> list[Path]:
    """品牌解析：新库 resolver（用户 overlay 优先）→ 兼容文件回退。

    只有明确的 ``asset_not_found`` 才允许回退。陈旧 catalog、作用域违规、
    重复 ID 或歧义等 resolver 错误必须原样阻断，避免使用旧品牌文件掩盖
    canonical 资产漂移。
    """

    candidates: list[Path] = []
    try:
        resolved = AssetResolver(home=home).require(name, kind="brand")
        return [Path(resolved["path"])]
    except AssetNotFoundError:
        pass
    from .config.runtime_config import default_home

    home_brands = (home or default_home()) / "brands" / f"{name}.md"
    legacy = _styles_root() / _BRAND_SUBDIR / f"{name}.md"
    return [home_brands, legacy]


def load_brand(name: str, *, home: Path | None = None) -> dict:
    """Load a brand-identity brief.

    Resolution order honors the deck contract: 新库 brand 实体（用户 overlay
    优先）→ 用户 MD（``${LEO_PPT_HOME}/brands/<name>.md``）→ 旧树归档 MD。
    新库 brand.json 按结构化字段读取（colors/typography/tone/verification）；
    MD 路径沿用字段式解析。Returns primary/accent HEX (empty string when
    absent), typography, tone, and the verified_at provenance.
    """
    for path in _brand_candidates(name, home=home):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise TemplateError(f"brand_unreadable: {name}") from exc
        if path.suffix == ".json":
            try:
                data = json.loads(text)
            except ValueError as exc:
                raise TemplateError(f"brand_unreadable: {name}") from exc
            colors = data.get("colors") or {}
            verification = data.get("verification") or {}
            return {
                "name": str(data.get("name") or name),
                "primary": str(colors.get("primary") or ""),
                "accent": str(colors.get("accent") or ""),
                "typography": str(data.get("typography") or ""),
                "tone": str(data.get("tone") or ""),
                "verified_at": str(verification.get("verified_at") or ""),
                "source": str(path),
            }
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
        # 新协议 guard：身份/类型/资格由 resolver 保证（require(kind="style")
        # 已拒绝非 style 实体与不可读文档）；此处复核生命周期可加载与文档
        # 形状，摘要与 render 必须消费同一 resolver 视图。
        brief_doc = style.get("brief")
        if (not isinstance(brief_doc, dict)
                or brief_doc.get("entity") != "style-brief"
                or style.get("lifecycle") not in {"active", "draft"}):
            raise StyleSelectionInvalid("style_selection_invalid")
    if isinstance(style.get("brief"), dict):
        brief = style["brief"]
        legacy = brief.get("legacy_payload") or {}
        # 兼容旧字段消费面：legacy_payload（旧 brief JSON 块字段）全量提升到
        # 顶层，v2 协议键冲突时以 brief 顶层为准 —— 与 load_style 重建的
        # compat content 形状一致（palette/typography/token_sidecar/layout/
        # visual_direction 等旧消费面直接可读）。
        if legacy:
            brief = {**legacy, **brief}
    else:
        m = re.search(r"```json\n(.*?)\n```", style["content"], re.S)
        if not m:
            raise TemplateError(f"style_brief_missing: {visual_style}")
        try:
            brief = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            raise TemplateError(f"style_brief_invalid: {visual_style}") from exc
    palette: object = brief.get("color_palette")
    if not isinstance(palette, dict) or not palette:
        # 新协议单源：完整转换的 brief 不携带 prose 色板，生效色板来自
        # bindings.theme_default 指向的主题（modes.<default_mode> 色彩角色）。
        theme_query = (brief.get("bindings") or {}).get("theme_default")
        if theme_query:
            try:
                theme = AssetResolver(home=home).require(theme_query, kind="theme")["data"]
                theme_colors = theme.get("modes", {}).get(theme.get("default_mode")) or {}
                if isinstance(theme_colors, dict) and theme_colors:
                    palette = dict(theme_colors)
            except ResolverError:
                pass
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
        bd = load_brand(brand, home=home)
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
    layout: str, *, image_type: str | None = None, materialize: bool = False,
    home: Path | None = None
) -> dict:
    """Merge a page layout's skeleton and an optional infographic type into one
    deterministic dict for `slides[].layout`.

    Empty purpose/skeleton fields raise instead of silently injecting a layout
    with zero structural constraints. `materialize=True` adds a
    `composition_hint` for the image-generation route (CSS dialect translated
    into canvas-block terms)."""
    layout_data = load_layout(layout, home=home)
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


def _canonical_axis_names(group: str, resolver: AssetResolver) -> list[str]:
    """Enumerate axis slugs from the same resolver snapshot as layouts."""
    prefix = f"{group}-"
    names: list[str] = []
    for entity in resolver.entities:
        if entity.get("kind") != "axis":
            continue
        path = Path(str(entity.get("path", "")))
        if len(path.parts) < 3 or path.parts[-3] != group:
            continue
        name = path.parent.name.removeprefix(prefix)
        if name:
            names.append(name)
    return sorted(set(names))


def list_templates() -> dict[str, list[str]]:
    """Enumerate executable template axes from canonical assets and the catalog."""
    try:
        resolver = AssetResolver()
        layouts = sorted(
            str(entity.get("name"))
            for entity in resolver.entities
            if entity.get("kind") == "layout" and entity.get("name")
        )
    except ResolverError as exc:
        raise TemplateError(f"template_catalog_unavailable: {exc}") from exc
    return {
        "renderings": _canonical_axis_names("rendering", resolver),
        "layouts": layouts,
        "image_types": _canonical_axis_names("infographic", resolver),
        "modes": _canonical_axis_names("argument", resolver),
    }


# --------------------------------------------------------------------------- #
# 统一设计组合（F3，方案 §7.0）：风格 → 主题组合 → 版式/模板 → 冻结 resolved_design
# --------------------------------------------------------------------------- #

class DesignCompositionError(StyleStoreError):
    """组合阶段确定性失败（含 design_constraint_conflict）。"""

    reason_code = "design_composition_invalid"


class DesignConstraintConflict(DesignCompositionError):
    reason_code = "design_constraint_conflict"


_DESIGN_COMPILER = {"name": "leo-ppt-generator/templates.compose_design", "version": "2"}


def resolve_design_context(
    style_query: str,
    *,
    mode: str | None = None,
    theme_query: str | None = None,
    brand_data: dict | None = None,
    color_overrides: dict | None = None,
    font_overrides: dict | None = None,
    resolver=None,
) -> dict:
    """共用设计上下文（dashi 集成 K2）：选择 → 主题 → effective → 约束。

    候选预编译（content_projection）与最终组合器消费同一快照，不另写主题
    覆盖规则。返回对象包含 style/theme 实体引用、effective theme、硬约束
    与 context_digest；不解析页面、不做容量、不冻结设计。
    """
    import hashlib

    from .asset_resolver import AssetResolver, ResolverError as _ResolverError
    from .render.theme import ThemeError, compute_effective_theme

    if resolver is None:
        resolver = AssetResolver()

    try:
        style = resolver.require(style_query, kind="style")
    except _ResolverError as exc:
        raise DesignCompositionError(f"design_composition_invalid: {exc}") from exc

    theme_query = theme_query or style["data"].get("bindings", {}).get("theme_default")
    if not theme_query:
        raise DesignCompositionError(
            "design_composition_invalid: 风格缺 bindings.theme_default")
    try:
        theme_entity = (resolver.require(theme_query, kind="theme")
                        if ":" in str(theme_query)
                        else resolver.require(str(theme_query), kind="theme"))
    except _ResolverError as exc:
        raise DesignCompositionError(f"design_composition_invalid: {exc}") from exc

    try:
        effective = compute_effective_theme(
            theme_entity["data"], mode=mode, brand=brand_data,
            color_overrides=color_overrides, font_overrides=font_overrides)
    except ThemeError as exc:
        raise DesignCompositionError(f"design_composition_invalid: {exc}") from exc

    constraints: list[dict] = []
    seen_texts: set[str] = set()
    for i, text in enumerate(style["data"].get("constraints", {}).get("negative", [])):
        if text in seen_texts:
            continue
        seen_texts.add(text)
        constraints.append({"id": f"style:{style['asset_id']}:negative:{i}",
                            "source": "style", "constraint": text})
    if brand_data:
        for role in sorted(brand_data.get("locked_roles") or []):
            constraints.append({"id": f"brand:{brand_data.get('name', 'brand')}:lock:{role}",
                                "source": "brand", "constraint": f"角色 {role} 由品牌锁定"})

    context = {
        "style": style,
        "theme_entity": theme_entity,
        "effective": effective,
        "constraints": constraints,
        "seen_constraint_texts": sorted(seen_texts),
    }
    context["context_digest"] = hashlib.sha256(_canonical_json({
        "style": style["asset_id"],
        "theme": theme_entity["asset_id"],
        "effective_theme": {
            "colors": effective["colors"],
            "fonts": effective["fonts"],
            "chart_palette": effective["chart_palette"],
        },
        "constraints": sorted(constraints, key=lambda c: c["id"]),
        "compiler": dict(_DESIGN_COMPILER),
    })).hexdigest()
    return context


def _canonical_json(value) -> bytes:
    import hashlib

    body = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
    return body.encode("utf-8")


def _design_digest(record: dict) -> str:
    import hashlib

    digest_input = {
        "selection": {k: v for k, v in record["selection"].items() if k != "source_map"},
        "effective_theme": record["effective_theme"],
        "effective_constraints": record["effective_constraints"],
        "pages": [{k: v for k, v in page.items()} for page in record["pages"]],
        "dependencies": sorted(record["dependencies"], key=lambda d: d["asset_id"]),
        "compiler": record["compiler"],
    }
    return hashlib.sha256(_canonical_json(digest_input)).hexdigest()


def compose_design(
    style_query: str,
    *,
    mode: str | None = None,
    theme_query: str | None = None,
    brand_data: dict | None = None,
    color_overrides: dict | None = None,
    font_overrides: dict | None = None,
    pages: list[dict] | None = None,
    selection: dict | None = None,
    selection_digest: str | None = None,
    design_context: dict | None = None,
    resolver=None,
) -> dict:
    """唯一设计组合器（§7.0 阶段表）：产出冻结 resolved_design。

    阶段：共用设计上下文（resolve_design_context，K2）→ 页面解析（页级显式
    layout > 风格路由）→ 容量校验 → 冻结（design_digest 固定键序，不含时间/
    绝对路径/自身）。候选预编译与最终组合器消费同一上下文快照。
    """
    from .asset_resolver import AssetResolver, ResolverError as _ResolverError
    from .render.layout import CapacityOverflowError, require_capacity, validate_profile
    from .application.expression_pipeline import selection_digest as _selection_digest
    from .content_projection import verify_binding_reference
    if not isinstance(selection, dict) or not selection.get("selection_frozen") or not pages:
        raise DesignCompositionError("selection_frozen_mismatch")
    frozen = selection.get("selection")
    expected = selection_digest or selection.get("selection_digest")
    try:
        if expected != _selection_digest(frozen):
            raise DesignCompositionError("selection_frozen_mismatch")
        if {page.get("page_id") for page in pages} != set(frozen) or len(pages) != len(frozen):
            raise DesignCompositionError("selection_frozen_mismatch")
        for page in pages:
            entry = frozen[page["page_id"]]
            verify_binding_reference(entry, entry.get("binding"))
            if page.get("layout") not in (None, entry["layout_id"]):
                raise DesignCompositionError("selection_frozen_mismatch")
    except (ValueError, KeyError, TypeError) as exc:
        raise DesignCompositionError("selection_frozen_mismatch") from exc
    selection = frozen

    if resolver is None:
        resolver = AssetResolver()

    # 1–5) 共用设计上下文（K2 抽取）：选择/主题/覆盖/约束与候选预编译同源。
    context = copy.deepcopy(design_context) if design_context is not None else resolve_design_context(
        style_query, mode=mode, theme_query=theme_query, brand_data=brand_data,
        color_overrides=color_overrides, font_overrides=font_overrides, resolver=resolver)
    if any(entry["binding"]["context_digest"] != context["context_digest"] for entry in selection.values()):
        raise DesignCompositionError("selection_frozen_mismatch")
    style = context["style"]
    theme_entity = context["theme_entity"]
    effective = context["effective"]
    constraints = context["constraints"]
    seen_texts = set(context["seen_constraint_texts"])

    # layout 只来自已冻结 selection，不能再使用风格路由。
    resolved_pages: list[dict] = []
    capacity_reports: list[dict] = []
    for page in pages:
        role = page.get("page_role", "content")
        layout_query = selection[page["page_id"]]["layout_id"]
        try:
            layout_entity = (resolver.require(layout_query, kind="layout")
                              if isinstance(layout_query, str) else
                              resolver.resolve(layout_query))
        except _ResolverError as exc:
            raise DesignCompositionError(f"design_composition_invalid: {exc}") from exc
        profile = layout_entity["data"]
        try:
            validate_profile(profile)
        except _ResolverError as exc:
            raise DesignCompositionError(f"design_composition_invalid: {exc}") from exc
        selected_binding = selection[page["page_id"]]["binding"]
        template_id = selected_binding["template_id"]
        slots = page.get("slots") or {}
        capacity = None
        if profile.get("layout_type") == "table" and "rows" in slots:
            try:
                capacity = require_capacity(
                    profile, effective, rows=slots["rows"],
                    columns=len(slots.get("columns") or []) or None)
            except CapacityOverflowError as exc:
                raise DesignCompositionError(f"design_composition_invalid: {exc}") from exc
            capacity_reports.append({"page_no": page.get("page_no", 1), **capacity})
        resolved_pages.append({
            "page_id": page["page_id"],
            "recipe_id": selected_binding.get("recipe_id"),
            "page_no": page.get("page_no", 1),
            "page_role": role,
            "content_ref": page.get("content_ref") or "inline",
            "layout_id": layout_entity["asset_id"],
            "profile_id": layout_entity["asset_id"],
            "template_id": template_id,
            "slots": slots,
        })
        if profile.get("layout_type") == "table":
            for text in [profile.get("notes") or ""]:
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    constraints.append({
                        "id": f"layout:{layout_entity['asset_id']}:note",
                        "source": "layout", "constraint": text})

    # 7) 依赖快照 + 冻结。
    dependencies: list[dict] = []
    seen_ids = {style["asset_id"]}
    for entity in [style, theme_entity]:
        for dep in resolver.resolve_dependencies(entity["asset_id"]):
            if dep["asset_id"] in seen_ids:
                continue
            seen_ids.add(dep["asset_id"])
            dependencies.append({
                "asset_id": dep["asset_id"],
                "revision": dep["revision"],
                "sha256": _sha256_of_path(dep["path"]),
            })
    for page in resolved_pages:
        for key in ("layout_id", "profile_id"):
            if page[key] and page[key] not in seen_ids:
                seen_ids.add(page[key])
                dep = resolver.resolve(page[key])
                dependencies.append({"asset_id": dep["asset_id"],
                                     "revision": dep["revision"],
                                     "sha256": _sha256_of_path(dep["path"])})
        if page["template_id"] and page["template_id"] not in seen_ids:
            seen_ids.add(page["template_id"])
            dep = resolver.resolve(page["template_id"])
            dependencies.append({"asset_id": dep["asset_id"],
                                 "revision": dep["revision"],
                                 "sha256": _sha256_of_path(dep["path"])})
    dependencies.sort(key=lambda item: item["asset_id"])

    record = {
        "schema_version": 1,
        "entity": "resolved-design",
        "selection": {
            "style": {"asset_id": style["asset_id"], "revision": style["revision"]},
            "theme": {"asset_id": theme_entity["asset_id"], "revision": theme_entity["revision"]},
            "mode": effective["mode"],
            "brand": ({"name": brand_data.get("name"), "locked_roles": brand_data.get("locked_roles", [])}
                      if brand_data else None),
            "preset": None,
            "source_map": effective["source_map"],
        },
        "effective_theme": {
            "colors": effective["colors"],
            "fonts": effective["fonts"],
            "chart_palette": effective["chart_palette"],
        },
        "effective_constraints": constraints,
        "design_context_digest": context["context_digest"],
        "pages": resolved_pages,
        "dependencies": dependencies,
        "compiler": dict(_DESIGN_COMPILER),
        "design_digest": "",
        "capacity_reports": capacity_reports,
    }
    record["design_digest"] = _design_digest(record)
    return record


def _sha256_of_path(path: str) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_design_freshness(resolved_design: dict, resolver=None) -> dict:
    """U8 恢复/续跑校验：冻结设计的依赖摘要必须仍与库内一致。

    旧 run 恢复的唯一入口：逐依赖重解析并比对 sha256——任何漂移
    （资产修订/替换/不可解析）都返回 stale 并列出波及面，调用方必须
    拒绝续跑而不是静默重组设计。新 run 不消费本函数（现场组合）。
    """

    if resolved_design.get("entity") != "resolved-design":
        raise DesignCompositionError("design_freshness_invalid: 非 resolved-design 输入")
    if resolver is None:
        from .asset_resolver import AssetResolver
        resolver = AssetResolver()
    mismatches = []
    deps = resolved_design.get("dependencies") or []
    for dep in deps:
        try:
            current = resolver.resolve(dep["asset_id"])
        except Exception as exc:  # 不可解析即漂移（改名/退役/越界）
            mismatches.append({"asset_id": dep["asset_id"], "reason": "unresolvable",
                               "detail": str(exc)[:160]})
            continue
        current_sha = _sha256_of_path(current["path"])
        if current_sha != dep.get("sha256"):
            mismatches.append({"asset_id": dep["asset_id"],
                               "reason": "sha256_mismatch",
                               "recorded": dep.get("sha256"),
                               "current": current_sha})
    return {"status": "fresh" if not mismatches else "stale",
            "checked": len(deps), "mismatches": mismatches}


# --------------------------------------------------------------------------- #
# 图像路线投影（F3/U4）：冻结 resolved_design → 图像 prompt 块
# --------------------------------------------------------------------------- #

class DesignProjectionError(StyleStoreError):
    reason_code = "design_projection_invalid"


_PROJECTION_FORBIDDEN_KEYS = (
    "curation", "evidence", "verified", "score", "license", "path",
    "source_map", "authored_digest", "reviewer", "label_source",
)


def project_design_to_prompt(resolved_design: dict, page: dict) -> dict:
    """把冻结设计编译为图像 prompt 块（§7.1 唯一当前投影）。

    输入只有冻结记录：不重读 preset/brand/theme 活动文件（适配器不得再次
    选择风格/合并品牌/读取最新主题）。治理值（分数/许可/路径/来源标记）
    不进入投影；正文来自冻结母版（content_ref），主题负责颜色/排印指令，
    layout 负责语义关系。确定性：同输入同字节。
    """
    if resolved_design.get("entity") != "resolved-design":
        raise DesignProjectionError("design_projection_invalid: 非 resolved-design 输入")
    theme = resolved_design["effective_theme"]
    colors = theme["colors"]
    color_lines = [f"{role}={value}" for role, value in sorted(colors.items())]
    fonts = theme.get("fonts") or {}
    font_line = "; ".join(
        f"{role}:{defn.get('family')} {defn.get('weight')}"
        for role, defn in sorted(fonts.items()))
    negatives = [item["constraint"]
                 for item in resolved_design["effective_constraints"]
                 if item.get("source") == "style"]
    page_entry = next((p for p in resolved_design["pages"]
                       if p["page_no"] == page.get("page_no")), None)
    if page_entry is None:
        raise DesignProjectionError(
            f"design_projection_invalid: 页 {page.get('page_no')} 不在冻结设计中")
    composition = page.get("composition_hint") or ""
    prompt_block = {
        "schema_version": 1,
        "kind": "design-prompt-projection",
        "design_digest": resolved_design["design_digest"],
        "style": resolved_design["selection"]["style"]["asset_id"],
        "mode": resolved_design["selection"]["mode"],
        "colors": color_lines,
        "typography": [font_line] if font_line else [],
        "negative_constraints": negatives,
        "page_role": page_entry["page_role"],
        "layout_id": page_entry["layout_id"],
        "composition_hint": composition,
        "canvas": "16:9 full-slide, 2560x1440 render target",
    }
    encoded = json.dumps(prompt_block, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    for forbidden in _PROJECTION_FORBIDDEN_KEYS:
        if forbidden + '":' in encoded.replace('"_', '"'):
            # 宽筛查：治理键出现在投影值中即拒绝（防泄漏硬闸）。
            for key in ("curation", "evidence_digest", "verified", "score",
                        "license", "source_map"):
                if f'"{key}"' in encoded:
                    raise DesignProjectionError(
                        f"design_projection_invalid: 治理值 {key} 泄漏进投影")
    return prompt_block
