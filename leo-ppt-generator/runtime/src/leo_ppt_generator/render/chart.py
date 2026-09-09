"""D2 ``render chart --dialect mermaid``：11_图表语法方言 → SVG。

数据面（零改写升级）：``references/styles/11_图表语法/*.md`` 的
```` ```mermaid-example ```` fenced 块是现成输入——本模块只抽取，不解析
语义；数值/单位/标签的逐字保真由 mermaid 原生渲染承担。

渲染面：与 D1 同一 playwright 依赖，同一浏览器实例内
``mermaid.initialize({startOnLoad:false})`` → ``mermaid.render`` → SVG 字符串。
mermaid 运行时 vendored 为本地单文件
（``assets/render-vendor/mermaid/mermaid.min.js``，版本 pin 进
``vendor-lock.json``），不走 CDN，离线确定。

themeVariables 映射（D2-T2）：deck colors 锚 → mermaid 键，初始 8 键
（映射表见 references/render-contract.md）；未提供 theme 时用 mermaid
默认并 WARN。
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage import sha256_file
from .assets import vendor_dir
from .errors import RenderError
from .readiness import _apply_browsers_path
from .svg_policy import sanitize_chart_output

DIALECTS = ("mermaid",)
MERMAID_BUNDLE = vendor_dir("mermaid", "mermaid.min.js")
EXAMPLE_BLOCK_RE = re.compile(r"```mermaid-example\n(.*?)\n```", re.S)

# deck colors 锚 → mermaid themeVariables（初始 8 键；映射表登记于
# references/render-contract.md）。锚侧接受 deck palette 常见命名。
THEME_VARIABLE_MAP = {
    "primaryColor": ("primary", "accent", "accent_color"),
    "primaryTextColor": ("on_primary", "text_on_primary", "primary_text"),
    "primaryBorderColor": ("primary_border", "border", "line"),
    "lineColor": ("grid_line", "line_color", "axis_line"),
    "secondaryColor": ("secondary", "secondary_color"),
    "tertiaryColor": ("tertiary", "tertiary_color", "surface"),
    "mainBkg": ("background", "bg", "canvas"),
    "fontSize": ("font_size", "base_font_size"),
}

# xychart 系（折线/柱状）不消费全局 primaryColor/mainBkg——主色走
# themeVariables.xyChart 域（plotColorPalette 是序列调色板）。锚 → xyChart
# 键的补充映射，保证"主色进 SVG 可 grep 验证"对图表方言成立。
XYCHART_VARIABLE_MAP = {
    "plotColorPalette": ("chart_series_csv", "primary", "accent", "accent_color"),
    "backgroundColor": ("background", "bg", "canvas"),
    "titleColor": ("on_primary", "title_color", "primary_text"),
}

DEFAULT_THEME_WARNING = "chart_theme_missing_using_mermaid_defaults"


def _governed_mapping() -> dict[str, dict[str, str]]:
    """治理区逐方言映射（chart-theme-mapping.json）；缺失即配置错误。"""
    from ..asset_resolver import builtin_library_root

    path = builtin_library_root() / "governance" / "rules" / "chart-theme-mapping.json"
    if not path.is_file():
        raise RenderError("chart_theme_mapping_missing",
                          f"governance mapping absent: {path}")
    mapping = json.loads(path.read_text(encoding="utf-8"))
    return mapping.get("dialects") or {}


def _flatten_theme(theme: dict[str, Any]) -> dict[str, Any]:
    """effective theme {colors, fonts, chart_palette} → 扁平语义角色锚。"""
    if "colors" in theme and isinstance(theme["colors"], dict):
        flat = dict(theme["colors"])
        chart = theme.get("chart_palette") or {}
        series = chart.get("series") or []
        if series:
            flat["chart_series_csv"] = ",".join(str(s) for s in series)
        fonts = theme.get("fonts") or {}
        label = fonts.get("chart_label") or fonts.get("body") or {}
        if isinstance(label.get("size"), (int, float)):
            flat["chart_label_size"] = label["size"]
        return flat
    return dict(theme)


def extract_mermaid_example(text: str) -> tuple[str, int]:
    """抽取 ```mermaid-example 块；多块取第一块。返回 (code, block_count)。

    无块或空块 → ``render_data_invalid``。
    """

    blocks = EXAMPLE_BLOCK_RE.findall(text)
    if not blocks:
        raise RenderError(
            "render_data_invalid", "no ```mermaid-example block found in source"
        )
    code = blocks[0].strip()
    if not code:
        raise RenderError("render_data_invalid", "mermaid-example block is empty")
    return code, len(blocks)


def load_chart_code(
    *, source: str | Path | None = None, code_file: str | Path | None = None
) -> tuple[str, dict[str, Any]]:
    """--source（方言 md）或 --code-file（内联 .mmd）→ (code, warnings)。"""

    warnings: list[str] = []
    if source:
        path = Path(source)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RenderError("render_data_invalid", f"source unreadable: {exc}") from exc
        code, count = extract_mermaid_example(text)
        if count > 1:
            warnings.append(
                f"source contains {count} mermaid-example blocks; using the first"
            )
        return code, warnings
    if code_file:
        path = Path(code_file)
        try:
            code = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RenderError("render_data_invalid", f"code file unreadable: {exc}") from exc
        if not code:
            raise RenderError("render_data_invalid", "code file is empty")
        return code, warnings
    raise RenderError("render_data_invalid", "one of --source/--code-file is required")


def build_theme_variables(theme: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """deck colors 锚 → mermaid themeVariables；缺省时 WARN + mermaid 默认。"""

    warnings: list[str] = []
    if not theme:
        warnings.append(DEFAULT_THEME_WARNING)
        return {}, warnings
    theme = _flatten_theme(theme)
    governed = _governed_mapping()
    resolved: dict[str, Any] = {}
    for mermaid_key, anchor_keys in THEME_VARIABLE_MAP.items():
        for anchor in anchor_keys:
            if isinstance(theme.get(anchor), (str, int, float)):
                value = theme[anchor]
                resolved[mermaid_key] = (
                    f"{value}px" if mermaid_key == "fontSize" and isinstance(value, (int, float)) else value
                )
                break
    xychart: dict[str, Any] = {}
    for mermaid_key, anchor_keys in XYCHART_VARIABLE_MAP.items():
        for anchor in anchor_keys:
            if isinstance(theme.get(anchor), str):
                xychart[mermaid_key] = theme[anchor]
                break
    if xychart:
        resolved["xyChart"] = xychart
    if not resolved:
        # §8.2：给了主题但一个映射键都对不上 → 阻断，不回落 mermaid 默认。
        missing = sorted(set(governed.get("mermaid-flowchart", {})) -
                         set(resolved))
        raise RenderError(
            "chart_theme_mapping_missing",
            f"theme provided but no mermaid keys resolved (missing: {missing[:6]}); "
            "governance mapping requires semantic roles, not silent defaults")
    return resolved, warnings


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def render_mermaid_svg(
    code: str,
    *,
    theme_variables: dict[str, Any] | None = None,
    font_family: str = "Noto Sans SC",
    timeout_ms: int = 30_000,
) -> str:
    """浏览器实例内 mermaid.render → SVG 字符串（不落盘）。"""

    if not MERMAID_BUNDLE.is_file():
        raise RenderError(
            "render_backend_missing",
            f"vendored mermaid bundle missing: {MERMAID_BUNDLE}",
        )
    _apply_browsers_path()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RenderError("render_backend_missing", f"playwright unavailable: {exc}") from exc

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, timeout=timeout_ms)
        except Exception as exc:
            raise RenderError("render_backend_missing", f"chromium launch failed: {exc}") from exc
        try:
            context = browser.new_context(locale="zh-CN", timezone_id="Asia/Shanghai")
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            page.set_content("<!doctype html><html><body><div id='leo-chart'></div></body></html>")
            try:
                page.add_script_tag(path=str(MERMAID_BUNDLE))
            except Exception as exc:
                raise RenderError(
                    "render_backend_missing", f"mermaid bundle injection failed: {exc}"
                ) from exc
            try:
                svg = page.evaluate(
                    """async ([code, themeVariables, fontFamily]) => {
                        mermaid.initialize({
                            startOnLoad: false,
                            fontFamily: fontFamily,
                            securityLevel: 'strict',
                            themeVariables: themeVariables,
                        });
                        const parsed = await mermaid.parse(code);
                        if (!parsed) { throw new Error('mermaid parse rejected'); }
                        const { svg } = await mermaid.render('leo-chart-0', code);
                        return svg;
                    }""",
                    [code, theme_variables or {}, font_family],
                )
            except Exception as exc:
                message = str(exc).strip().splitlines()[0][:300] if str(exc).strip() else "unknown"
                raise RenderError("render_data_invalid", f"mermaid render failed: {message}") from exc
            if not isinstance(svg, str) or "<svg" not in svg:
                raise RenderError("render_data_invalid", "mermaid returned no SVG")
            try:
                svg = sanitize_chart_output(svg, dialect="mermaid")
            except Exception as exc:
                raise RenderError("render_data_invalid", f"mermaid SVG policy rejected output: {exc}") from exc
            context.close()
            return svg
        finally:
            browser.close()


def render_chart(
    *,
    dialect: str,
    source: str | Path | None = None,
    code_file: str | Path | None = None,
    out: str | Path,
    theme: dict[str, Any] | None = None,
    theme_file: str | Path | None = None,
    font_family: str = "Noto Sans SC",
    timeout_ms: int = 30_000,
) -> dict[str, Any]:
    """``render chart`` 主入口：抽块/读文件 → SVG 落盘 + provenance sidecar。"""

    if dialect not in DIALECTS:
        raise RenderError(
            "render_data_invalid",
            f"unsupported dialect {dialect!r}; M1 supports {DIALECTS}",
        )
    if theme is None and theme_file:
        try:
            theme = json.loads(Path(theme_file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RenderError("render_data_invalid", f"theme file invalid: {exc}") from exc

    code, warnings = load_chart_code(source=source, code_file=code_file)
    theme_variables, theme_warnings = build_theme_variables(theme)
    warnings.extend(theme_warnings)

    started = time.monotonic()
    svg = render_mermaid_svg(
        code, theme_variables=theme_variables, font_family=font_family, timeout_ms=timeout_ms
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")

    input_identity = Path(source) if source else Path(code_file)
    provenance = {
        "schema_version": 1,
        "kind": "render_provenance",
        "backend": "render:mermaid",
        "template_id": None,
        "template_sha256": None,
        "data_sha256": sha256_file(input_identity) if input_identity and input_identity.is_file() else None,
        "dialect": dialect,
        "mermaid_source_sha256": sha256_file(MERMAID_BUNDLE),
        "renderer": "mermaid-vendored",
        "out": str(out_path.resolve()),
        "out_sha256": sha256_file(out_path),
        "render_ms": int((time.monotonic() - started) * 1000),
        "rendered_at": _utc_now(),
        "warnings": warnings,
    }
    sidecar = out_path.with_name(out_path.name + ".render.json")
    sidecar.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**provenance, "sidecar": str(sidecar)}
