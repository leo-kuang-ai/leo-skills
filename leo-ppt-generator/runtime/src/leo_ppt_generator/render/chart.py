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
    is_effective_theme = isinstance(theme.get("colors"), dict)
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
    if is_effective_theme:
        # 结构化主题由治理映射拥有语义；旧扁平锚仅用于兼容历史输入。
        for key, anchor in governed.get("mermaid-flowchart", {}).items():
            value = theme.get(anchor)
            if isinstance(value, (str, int, float)):
                resolved[key] = f"{value}px" if key == "fontSize" and isinstance(value, (int, float)) else value
        xy_mapping = governed.get("mermaid-xychart", {}).get("xyChart", {})
        for key, anchor in xy_mapping.items():
            value = theme.get(anchor)
            if isinstance(value, str):
                resolved.setdefault("xyChart", {})[key] = value
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
    chart_options: dict[str, Any] | None = None,
    timeout_ms: int = 30_000,
) -> str:
    """浏览器实例内 mermaid.render → SVG 字符串（不落盘）。"""

    options = dict(chart_options or {})
    bounds = {"width": (320, 2560), "height": (180, 1440), "label_size": (12, 96)}
    for key, value in options.items():
        if key == "data_labels" and isinstance(value, bool):
            continue
        if key not in bounds or type(value) is not int or not bounds[key][0] <= value <= bounds[key][1]:
            raise RenderError("render_data_invalid", f"非法 XY 图表选项 {key}")
    xy_config = {k: options[k] for k in ("width", "height") if k in options}
    if "label_size" in options:
        axis = {"labelFontSize": options["label_size"], "titleFontSize": options["label_size"]}
        xy_config.update(xAxis=axis, yAxis=axis, legendFontSize=options["label_size"])
    if "data_labels" in options:
        xy_config.update(showDataLabel=options["data_labels"], showDataLabelOutsideBar=True)

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
            context.route("**/*", lambda route: route.abort())
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
                    """async ([code, themeVariables, fontFamily, xyConfig, labelSize]) => {
                        mermaid.initialize({
                            startOnLoad: false,
                            fontFamily: fontFamily,
                            securityLevel: 'strict',
                            // Mermaid 11 同时读取顶层与方言配置；只设 flowchart 不足。
                            htmlLabels: false,
                            flowchart: { htmlLabels: false },
                            themeVariables: themeVariables,
                            xyChart: xyConfig,
                        });
                        const parsed = await mermaid.parse(code);
                        if (!parsed) { throw new Error('mermaid parse rejected'); }
                        if (Object.keys(xyConfig).length && parsed.diagramType !== 'xychart') {
                            throw new Error('chart options require xychart');
                        }
                        const { svg } = await mermaid.render('leo-chart-0', code);
                        // 仅移除 Mermaid 自动附带的装饰阴影；标签保留原生 SVG，
                        // 不再用简化 HTML→text 转换改变换行、字体和节点位置。
                        const doc = new DOMParser().parseFromString(svg, 'image/svg+xml');
                        if (doc.querySelector('parsererror')) {
                            throw new Error('mermaid output is not valid XML');
                        }
                        doc.querySelectorAll('filter').forEach((f) => f.remove());
                        doc.querySelectorAll('[filter]').forEach((el) => {
                            el.removeAttribute('filter');
                        });
                        if (xyConfig.showDataLabel) {
                            // vendored Mermaid 错用第一序列的数值，且字号随柱宽膨胀。
                            // 从同一语法解析器读取各序列，不从源码猜测或重算业务数据。
                            const diagram = await mermaid.mermaidAPI.getDiagramFromText(code);
                            const plots = diagram.db.getXYChartData().plots;
                            const horizontal = diagram.db.getChartConfig().chartOrientation === 'horizontal';
                            doc.querySelectorAll('g[class^="bar-plot-"]').forEach((group) => {
                                const index = Number(group.getAttribute('class').slice('bar-plot-'.length));
                                const series = plots[index];
                                const bars = Array.from(group.querySelectorAll('rect'));
                                if (!series || bars.length !== series.data.length) {
                                    throw new Error('xychart data label series mismatch');
                                }
                                group.querySelectorAll('text').forEach((el) => el.remove());
                                bars.forEach((bar, i) => {
                                    const x = Number(bar.getAttribute('x')), y = Number(bar.getAttribute('y'));
                                    const w = Number(bar.getAttribute('width')), h = Number(bar.getAttribute('height'));
                                    const label = doc.createElementNS('http://www.w3.org/2000/svg', 'text');
                                    label.textContent = String(series.data[i][1]);
                                    label.setAttribute('x', String(horizontal ? x + w + 5 : x + w / 2));
                                    label.setAttribute('y', String(horizontal ? y + h / 2 : y - 5));
                                    label.setAttribute('text-anchor', horizontal ? 'start' : 'middle');
                                    label.setAttribute('dominant-baseline', horizontal ? 'middle' : 'auto');
                                    label.setAttribute('font-size', String(labelSize || 18));
                                    label.setAttribute('fill', themeVariables.xyChart?.dataLabelColor ||
                                        themeVariables.primaryTextColor || '#333333');
                                    group.appendChild(label);
                                });
                            });
                        }
                        if (labelSize) {
                            // 刻度空间不足时稀疏显示，保留两个端点和零点；不改变坐标尺度。
                            for (const side of ['left-axis', 'right-axis']) {
                                const labels = Array.from(doc.querySelectorAll(`.${side} .label text`));
                                const position = (el) => Number((el.getAttribute('transform') || '').match(/translate\\([^,]+,\\s*([^)]+)\\)/)?.[1]);
                                const sorted = labels.sort((a,b) => position(a) - position(b));
                                if (sorted.length < 3) continue;
                                const spacing = Math.min(...sorted.slice(1).map((el,i) => position(el) - position(sorted[i])));
                                const stride = Math.ceil(labelSize * 1.4 / spacing);
                                if (!Number.isFinite(stride) || stride <= 1) continue;
                                const required = new Set([0, sorted.length - 1]);
                                sorted.forEach((el,i) => { if (Number(el.textContent) === 0) required.add(i); });
                                const keep = new Set(required);
                                for (let i = stride; i < sorted.length - 1; i += stride) {
                                    if (Array.from(keep).every(j => Math.abs(position(sorted[i])-position(sorted[j])) >= labelSize * 1.4)) keep.add(i);
                                }
                                sorted.forEach((el,i) => { if (!keep.has(i)) el.remove(); });
                            }
                        }
                        return new XMLSerializer().serializeToString(doc.documentElement);
                    }""",
                    [code, theme_variables or {}, font_family, xy_config, options.get("label_size")],
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
    chart_options: dict[str, Any] | None = None,
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
        code, theme_variables=theme_variables, font_family=font_family,
        chart_options=chart_options, timeout_ms=timeout_ms
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
        "chart_options": chart_options or {},
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
