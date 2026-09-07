#!/usr/bin/env python3
"""Generate the browsable style gallery (samples/style-gallery.md) and the
builtin styles' golden sample thumbnails (R-26 / R-65).

Scans ``references/styles/`` directly (filesystem is the truth, not the
hand-maintained index): the 11 top-level builtin briefs with their 适用场景
bullets, plus per-axis markdown counts for the subdirectories.

Golden samples (金样板, 一物三用: 预览图 / 编译回归基准 / 审美对照):
for each golden style three pages are rendered through the M1 render lane
CLI (``render page`` / ``render chart``) with fixed sample data derived
deterministically from the brief itself (style name, best_for excerpt,
layout patterns, palette HEX anchors). Golden styles = the 11 top-level
builtin briefs + one representative per S5 intake family (R-65 extends
golden coverage to every deterministic-render style family). Artifacts
under ``samples/style-gallery/<风格名>/``:

- ``slide-cover.json`` / ``slide-content.json`` / ``slide-chart.json`` —
  deterministic render inputs (always written; double as the degraded-mode
  regression baseline when no browser is available);
- ``chart.mmd`` / ``theme.json`` — fixed chart dialect source and the
  deck-color anchors mapped from the brief palette;
- ``thumb-cover.png`` / ``thumb-content.png`` / ``thumb-chart.png`` —
  1280x720 golden thumbnails rendered by the managed runtime.

Modes:

- default: rebuild ``samples/style-gallery.md`` (embeds thumbnails for the
  styles whose three PNGs exist);
- ``--render-golden``: (re)write golden inputs and thumbnails, then rebuild
  the gallery;
- ``--check``: verify the committed gallery markdown **and** run the golden
  regression (R-65): re-render into a temp dir and compare sha256 against
  the committed thumbnails; drift exits 1. When the render backend is
  unavailable the regression degrades to byte-comparing the deterministic
  golden inputs (reported as WARN, never silently skipped).

Determinism contract: same runtime, same chromium, same fonts → identical
PNG bytes across runs (verified on the managed runtime); SVG chart output is
bit-deterministic by the render lane contract.

Exit codes: 0 = written or up to date; 1 = --check found drift; 2 = IO or
render error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))
from leo_ppt_generator.styles import parse_style_document

STYLES_DIR = SKILL_DIR / "references" / "styles"
GALLERY = SKILL_DIR / "samples" / "style-gallery.md"
THUMBS_ROOT = SKILL_DIR / "samples" / "style-gallery"
SCENARIO_HEADER = "**适用场景"
JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")

# Fixed golden chart (sample data identical for every style; the palette is
# what differentiates styles — deck color anchors land in the SVG verbatim).
# Single series on purpose: plotColorPalette maps one primary anchor, a
# second series would fall back to mermaid's default purple.
GOLDEN_CHART_MMD = """xychart-beta
    title "季度交付吞吐（示例数据）"
    x-axis [Q1, Q2, Q3, Q4]
    y-axis "交付需求数" 0 --> 40
    bar [12, 18, 27, 35]
"""
PAGES = ("cover", "content", "chart")

# S5 intake families (references/styles/01_通用母版/<家族>/) and the one
# representative brief per family admitted to the golden baseline — picked
# for the most complete palette / strongest family character; every family
# brief has the full 5-role palette, so the tiebreakers are family-iconic
# anchors (e.g. Dracula's soul pink/purple pair) and layout depth.
# (family directory, representative style name, one-line family blurb)
FAMILY_REPRESENTATIVES: "list[tuple[str, str, str]]" = [
    ("终端配色", "Dracula紫风", "知名终端配色方案直迁，暗底霓虹前景的开发者视觉方言"),
    ("设计流派", "杂志衬线风", "杂志、播报、撞色等设计史流派的编辑排版语汇"),
    ("东方意蕴", "故宫墨红风", "墨红、水墨、宋韵等新中式东方诗意的十种色温"),
    ("柔和治愈", "奶油温柔风", "奶油白、豆沙粉、抹茶绿的低饱和温柔色系"),
    ("夜空氛围", "星火夜空风", "星河、极光、烟火的深底高对比夜空舞台"),
    ("质感专业", "黑金期刊风", "黑金、勃艮第、象牙的期刊级质感与单金锚克制"),
    ("中式载体", "中式书卷风", "书卷、宣纸、竹简的古典载体与朱红钤印"),
    ("印象派油画", "星月夜风", "梵高、莫奈的笔触、光影与强色彩张力"),
]

# Visibility guard thresholds (perceived luminance 0-255): the cover/body
# templates use fixed dark ink on light paper and the chart lane falls back
# to mermaid's light canvas, so a dark-family palette (terminal/night
# themes are light-on-dark) must not land verbatim — see golden_inputs.
BACKGROUND_LUM_FLOOR = 128
ANCHOR_LUM_CEILING = 180


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def warn(message: str) -> None:
    print(f"WARN: {message}", file=sys.stderr)


# ---------------------------------------------------------------- styles ---

def builtin_styles(styles_root: Path = STYLES_DIR) -> "list[tuple[str, list[str]]]":
    entries: "list[tuple[str, list[str]]]" = []
    for path in sorted(styles_root.glob("*.md")):
        scenarios: list[str] = []
        in_scenarios = False
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            fail(f"cannot read {path}: {exc}")
        for raw in lines:
            line = raw.strip()
            if line.startswith(SCENARIO_HEADER):
                in_scenarios = True
                continue
            if in_scenarios:
                if line.startswith("- "):
                    scenarios.append(line[2:].strip())
                else:
                    break
        entries.append((path.stem, scenarios))
    return entries


def axis_counts(styles_root: Path = STYLES_DIR) -> "list[tuple[str, int]]":
    entries: "list[tuple[str, int]]" = []
    for directory in sorted(p for p in styles_root.iterdir() if p.is_dir()):
        if directory.name in {"00_索引", "generated", "generated.previous"} or directory.name.startswith(".style-index-"):
            continue
        count = len(list(directory.glob("*.md")))
        label = directory.name.split("_", 1)[1] if "_" in directory.name else directory.name
        entries.append((f"{label}（{directory.name.split('_')[0]}）", count))
    return entries


def _brief_path(name: str, styles_root: Path = STYLES_DIR) -> Path:
    """Resolve a style name to its brief file: top-level builtin first, then
    the family directory for S5 representatives, then a single-name search
    across the sub-directory axes (explicit golden renders of later intake
    batches, e.g. S5 gap briefs living under 01/02)."""
    top_level = styles_root / f"{name}.md"
    if top_level.is_file():
        return top_level
    for family, representative, _ in FAMILY_REPRESENTATIVES:
        if representative == name:
            return styles_root / "01_通用母版" / family / f"{name}.md"
    matches = sorted(p for p in styles_root.glob(f"0[123]_*/*/{name}.md"))
    if len(matches) == 1:
        return matches[0]
    return top_level  # canonical path for the failure message


def _brief_json(name: str, styles_root: Path = STYLES_DIR) -> dict:
    path = _brief_path(name, styles_root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {path}: {exc}")
    parsed = parse_style_document(text)
    if parsed["brief"] is None:
        fail(f"no JSON brief block in {path}")
    return parsed["brief"]


def _first_hex(*values: object) -> "str | None":
    for value in values:
        if isinstance(value, str):
            found = HEX_RE.search(value)
            if found:
                return found.group(0)
    return None


def _luminance(hex_value: str) -> int:
    """Perceived luminance 0-255 (deterministic; golden cover title and chart
    title colors are fixed by the templates, so the page background must be
    the lightest anchor to keep contrast)."""
    r, g, b = (int(hex_value[i:i + 2], 16) for i in (1, 3, 5))
    return round(0.299 * r + 0.587 * g + 0.114 * b)


def _lightest_hex(*values: object) -> "str | None":
    """Pick the highest-luminance HEX among the candidates (stable: first
    occurrence wins ties). Falls back to None (template paper default)."""
    best: "tuple[int, str] | None" = None
    for value in values:
        if not isinstance(value, str):
            continue
        for found in HEX_RE.finditer(value):
            hex_value = found.group(0)
            lum = _luminance(hex_value)
            if best is None or lum > best[0]:
                best = (lum, hex_value)
    return best[1] if best else None


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


# ---------------------------------------------------------- golden data ---

def golden_style_names(styles_root: Path = STYLES_DIR) -> "list[str]":
    """Golden baseline roster: 11 top-level builtins + one representative
    per S5 intake family (R-65, 19 styles total)."""
    names = [name for name, _ in builtin_styles(styles_root)]
    names += [representative for _, representative, _ in FAMILY_REPRESENTATIVES]
    return names


def golden_inputs(name: str, styles_root: Path = STYLES_DIR) -> dict:
    """Deterministic golden sample inputs derived from the brief itself.

    Fixed sample data (kicker/bullets/chart numbers are constants; per-style
    variation comes from style name, best_for, layout patterns and palette).
    """
    brief = _brief_json(name)
    palette = brief.get("color_palette", {})
    canvas = brief.get("canvas", {})
    best_for = _clip(str(brief.get("best_for", name)), 56)
    patterns = [
        _clip(str(item), 44)
        for item in (brief.get("layout_patterns") or [])[:4]
    ] or ["problem-process-result-next steps"]

    background = _lightest_hex(canvas.get("background"), palette.get("neutral"))
    # Visibility guard: templates use fixed dark ink, so only a light enough
    # anchor may become the page background. Dark-family palettes (terminal
    # / night themes carry dark canvases, e.g. cream families carry a dark
    # neutral ink instead) fall back to the template paper default.
    if background is not None and _luminance(background) < BACKGROUND_LUM_FLOOR:
        background = None
    cover_data: dict = {
        "kicker": "LEO 风格金样板",
        "title": name,
        "subtitle": best_for,
        "footer_left": "leo-ppt-generator",
        "footer_right": "golden sample",
    }
    if background:
        cover_data["background_color"] = background
    content_data = {
        "title": f"{name} · 代表版式",
        "bullets": patterns,
        "page_no": "02",
    }
    chart_data = {
        "title": f"{name} · 图表页",
        "bullets": ["数据口径固定：季度交付吞吐示例"],
        "page_no": "03",
    }
    theme: dict = {}
    for anchor, role in (
        ("primary", "primary"),
        ("secondary", "secondary"),
        ("accent", "accent"),
    ):
        hex_value = _first_hex(palette.get(role))
        if hex_value is None:
            continue
        # Same guard for plot anchors: on the paper-default fallback a
        # light-on-dark family anchor (near-white terminal foreground)
        # would vanish on mermaid's light chart canvas.
        if background is None and _luminance(hex_value) >= ANCHOR_LUM_CEILING:
            continue
        theme[anchor] = hex_value
    if background:
        theme["background"] = background
        # xyChart title color follows background luminance (light page needs
        # dark ink; fixed white would vanish on the lightest-anchor pick).
        theme["on_primary"] = "#1F2430" if _luminance(background) >= 128 else "#FFFFFF"
        theme["grid_line"] = "#E2E8F0"
    return {
        "slide-cover.json": cover_data,
        "slide-content.json": content_data,
        "slide-chart.json": chart_data,
        "chart.mmd": GOLDEN_CHART_MMD,
        "theme.json": theme,
    }


# ---------------------------------------------------------- render lane -----

def runtime_python() -> "Path | None":
    """Locate the managed runtime interpreter that has leo_ppt_generator."""
    override = os.environ.get("LEO_PPT_RUNTIME_PYTHON")
    if override:
        # authoritative: a stale override means "no backend", never a silent
        # fallback to the managed runtime (degraded mode must be observable)
        candidate = Path(override)
        return candidate if candidate.is_file() else None
    for candidate in (
        SKILL_DIR / "runtime" / ".venv" / "bin" / "python",
        SKILL_DIR / "runtime" / "venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return candidate
    return None


def _run_render(args: "list[str]") -> "tuple[dict | None, bool]":
    """Run one render-lane CLI call. Returns (envelope, degraded)."""
    python = runtime_python()
    if python is None:
        return None, True
    result = subprocess.run(
        [str(python), "-m", "leo_ppt_generator", *args],
        capture_output=True, text=True, timeout=180,
    )
    try:
        envelope = json.loads(result.stdout or result.stderr)
    except json.JSONDecodeError:
        if result.returncode == 0:
            fail(f"render CLI output not JSON: {result.stdout[:200]}")
        fail(f"render CLI failed ({result.returncode}): {result.stderr[:400]}")
    if envelope.get("status") == "ready":
        return envelope, False
    reason = envelope.get("reason_code", "unknown")
    if reason == "render_backend_missing":
        return envelope, True
    fail(f"render blocked ({reason}): {json.dumps(envelope.get('suggested_actions'), ensure_ascii=False)}")


def render_chart_svg(mmd: Path, theme: Path, out: Path) -> "tuple[str | None, bool]":
    """Render the fixed chart to SVG text via ``render chart``."""
    envelope, degraded = _run_render([
        "render", "chart",
        "--code-file", str(mmd),
        "--out", str(out),
        "--theme-file", str(theme),
    ])
    if degraded:
        return None, True
    try:
        return out.read_text(encoding="utf-8"), False
    except OSError as exc:
        fail(f"cannot read rendered chart SVG: {exc}")


def render_page(template_id: str, data: Path, out: Path) -> "tuple[dict | None, bool]":
    envelope, degraded = _run_render([
        "render", "page",
        "--template", template_id,
        "--data", str(data),
        "--out", str(out),
        "--size", "1280x720",
    ])
    if not degraded:
        sidecar = out.with_name(out.name + ".render.json")
        if sidecar.is_file():
            # provenance sidecar carries timestamps; golden baseline stays
            # byte-deterministic, so it is not part of the committed assets.
            sidecar.unlink()
    return envelope, degraded


def write_inputs(style_dir: Path, inputs: dict) -> None:
    style_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in inputs.items():
        if isinstance(payload, str):
            style_dir.joinpath(filename).write_text(payload, encoding="utf-8")
        else:
            style_dir.joinpath(filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )


def render_golden(thumbs_root: Path = THUMBS_ROOT, styles: "list[str] | None" = None,
                  styles_root: Path = STYLES_DIR) -> int:
    """Write golden inputs + thumbnails for every golden style (R-26/R-65)."""
    names = styles or golden_style_names(styles_root)
    degraded = False
    for name in names:
        style_dir = thumbs_root / name
        inputs = golden_inputs(name, styles_root)
        write_inputs(style_dir, inputs)
        # chart inputs live in style_dir (deterministic baseline); the SVG and
        # its timestamped provenance sidecar are rendered into a temp dir so
        # only the embedded chart_svg lands in the committed baseline.
        with tempfile.TemporaryDirectory(prefix="leo-golden-chart-") as tmp:
            chart_svg, chart_degraded = render_chart_svg(
                style_dir / "chart.mmd", style_dir / "theme.json", Path(tmp) / "chart.svg"
            )
        degraded = degraded or chart_degraded
        for page in PAGES:
            out = style_dir / f"thumb-{page}.png"
            data = style_dir / f"slide-{page}.json"
            if page == "chart":
                if chart_svg is None:
                    continue  # backend missing: keep committed inputs/thumbs
                payload = inputs[f"slide-{page}.json"]
                payload["chart_svg"] = chart_svg
                data.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            template = "cover-basic" if page == "cover" else "body-basic"
            _, page_degraded = render_page(template, data, out)
            degraded = degraded or page_degraded
        print(f"golden: {name} rendered" + (" (chart png skipped: backend missing)" if chart_svg is None else ""))
    if degraded:
        warn("render backend unavailable: golden thumbnails degraded to deterministic inputs only (R-65 check compares input shas)")
    return 0


# ------------------------------------------------------------- regression ---

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_golden(thumbs_root: Path = THUMBS_ROOT, styles: "list[str] | None" = None,
                 styles_root: Path = STYLES_DIR) -> "tuple[int, bool]":
    """R-65 golden regression: re-render into a temp dir and compare shas.

    Returns (drift_count, degraded). Committed thumbnails are compared by
    sha256; when the render backend is missing the comparison falls back to
    the deterministic golden inputs (byte compare) and reports degraded.
    ``slide-chart.json`` embeds the rendered chart_svg, so it is compared
    after chart assembly, not in the pure-input loop.
    """
    names = styles or golden_style_names(styles_root)
    drift = 0
    degraded = runtime_python() is None
    if degraded:
        warn("render backend unavailable: R-65 check degraded to golden-input byte compare")
    for name in names:
        committed_dir = thumbs_root / name
        inputs = golden_inputs(name, styles_root)
        with tempfile.TemporaryDirectory(prefix="leo-golden-check-") as tmp:
            workdir = Path(tmp) / name
            write_inputs(workdir, inputs)
            # input drift (always comparable, browser or not)
            for filename in inputs:
                if filename == "slide-chart.json":
                    continue
                committed = committed_dir / filename
                if not committed.is_file():
                    print(f"STALE: golden input missing {committed}", file=sys.stderr)
                    drift += 1
                elif _sha256(committed) != _sha256(workdir / filename):
                    print(f"STALE: golden input drifted {committed}", file=sys.stderr)
                    drift += 1
            if degraded:
                continue  # no backend: baseline is the deterministic inputs
            chart_svg, chart_degraded = render_chart_svg(
                workdir / "chart.mmd", workdir / "theme.json", Path(tmp) / "chart.svg"
            )
            degraded = degraded or chart_degraded
            if degraded:
                warn("render backend failed mid-run: thumbnail compare skipped for the rest")
                continue
            for page in PAGES:
                committed = committed_dir / f"thumb-{page}.png"
                data = workdir / f"slide-{page}.json"
                if page == "chart":
                    if chart_svg is None:
                        continue
                    payload = inputs["slide-chart.json"]
                    payload["chart_svg"] = chart_svg
                    data.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    # assembled chart data is itself a golden baseline byte set
                    committed_data = committed_dir / "slide-chart.json"
                    if not committed_data.is_file():
                        print(f"STALE: golden input missing {committed_data}", file=sys.stderr)
                        drift += 1
                    elif _sha256(committed_data) != _sha256(data):
                        print(f"STALE: golden input drifted {committed_data}", file=sys.stderr)
                        drift += 1
                if not committed.is_file():
                    print(f"STALE: golden thumbnail missing {committed}", file=sys.stderr)
                    drift += 1
                    continue
                fresh = workdir / f"thumb-{page}.png"
                template = "cover-basic" if page == "cover" else "body-basic"
                _, page_degraded = render_page(template, data, fresh)
                degraded = degraded or page_degraded
                if page_degraded:
                    continue
                if _sha256(committed) != _sha256(fresh):
                    print(
                        f"STALE: golden thumbnail drifted {committed} "
                        f"(committed {_sha256(committed)[:12]} != fresh {_sha256(fresh)[:12]})",
                        file=sys.stderr,
                    )
                    drift += 1
    return drift, degraded


# ---------------------------------------------------------------- gallery ---

def _thumbs_present(style_dir: Path) -> bool:
    return all((style_dir / f"thumb-{page}.png").is_file() for page in PAGES)


def render(builtins: "list[tuple[str, list[str]]]", axes: "list[tuple[str, int]]",
           representatives: "list[tuple[str, str, str]] | None" = None,
           thumbs_root: Path = THUMBS_ROOT) -> str:
    if representatives is None:
        representatives = FAMILY_REPRESENTATIVES
    lines = [
        "# 风格画廊（生成物）",
        "",
        "> 由 `python3 scripts/generate_style_gallery.py` 从 `references/styles/` 文件系统确定性生成；",
        "> 手工编辑会被 `--check` 判漂移。完整索引与选风格路由见",
        "> [`references/styles/00_索引/_INDEX.md`](../references/styles/00_索引/_INDEX.md)。",
        "",
        f"## 内置风格（{len(builtins)} 套，直接可选）",
        "",
        "| 风格 | 适用场景（摘自 brief） |",
        "| --- | --- |",
    ]
    for name, scenarios in builtins:
        summary = " / ".join(scenarios[:4]) if scenarios else "（见 brief）"
        lines.append(f"| **{name}** | {summary} |")

    golden = [(name, _thumbs_present(thumbs_root / name)) for name, _ in builtins]
    if any(present for _, present in golden):
        lines += [
            "",
            "## 内置风格金样板（R-26 / R-65）",
            "",
            "> 每风格三页（封面 / 内容 / 图表），M1 渲染 lane 固定示例数据确定性生成：",
            "> `python3 scripts/generate_style_gallery.py --render-golden` 重建，",
            "> `--check` 以 sha256 对比金样板防漂移（编译回归判据）。",
        ]
        for name, present in golden:
            if not present:
                continue
            lines += [
                "",
                f"### {name}",
                "",
                "| 封面 | 内容 | 图表 |",
                "| --- | --- | --- |",
                "| ![{} 封面金样板](style-gallery/{}/thumb-cover.png) "
                "| ![{} 内容金样板](style-gallery/{}/thumb-content.png) "
                "| ![{} 图表金样板](style-gallery/{}/thumb-chart.png) |".format(
                    name, name, name, name, name, name),
            ]

    family_golden = [
        (family, name, blurb, _thumbs_present(thumbs_root / name))
        for family, name, blurb in representatives
    ]
    if any(present for *_, present in family_golden):
        lines += [
            "",
            "## 新家族代表金样板（S5 进货 · R-65）",
            "",
            f"> S5 进货的 {len(family_golden)} 个新风格家族各选 1 个代表",
            "> （色板最完整 / 最具家族气质），与内置风格同一渲染 lane 与",
            "> `--check` 回归；暗底家族经可见性守护回退纸色底，",
            "> 色板锚点仍逐字进图表 SVG。",
        ]
        for family, name, blurb, present in family_golden:
            if not present:
                continue
            lines += [
                "",
                f"### {family} · {name}",
                "",
                f"> {blurb}",
                "",
                "| 封面 | 内容 | 图表 |",
                "| --- | --- | --- |",
                "| ![{} 封面金样板](style-gallery/{}/thumb-cover.png) "
                "| ![{} 内容金样板](style-gallery/{}/thumb-content.png) "
                "| ![{} 图表金样板](style-gallery/{}/thumb-chart.png) |".format(
                    name, name, name, name, name, name),
            ]

    lines += [
        "",
        f"## 目录直层文档（{len(axes)} 个目录，兼容口径）",
        "",
        "| 轴 | 份数 |",
        "| --- | --- |",
    ]
    for label, count in axes:
        lines.append(f"| {label} | {count} |")
    total = sum(count for _, count in axes) + len(builtins)
    lines += [
        "",
        f"上述目录直层及内置 Markdown 共 {total} 份，不递归统计家族子目录，不代表全库资产或可推荐风格总数。",
        "全库角色与独立风格数量见[派生分类计数](../references/styles/generated/counts.md)。",
        "选定后由 `style render` 确定性注入，流程见 [`references/style-library.md`](../references/style-library.md)。",
        "",
    ]
    return "\n".join(lines)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the style gallery from the styles directory.")
    parser.add_argument("--check", action="store_true", help="verify the gallery and golden samples are up to date instead of writing")
    parser.add_argument("--render-golden", action="store_true",
                        help="render the golden sample thumbnails for the 19 golden styles "
                             "(11 builtins + 8 family representatives, R-26/R-65) before writing the gallery")
    args = parser.parse_args(argv)

    if not STYLES_DIR.is_dir():
        fail(f"styles directory not found: {STYLES_DIR}")

    if args.render_golden:
        render_golden()

    builtins = builtin_styles()
    content = render(builtins, axis_counts())

    if args.check:
        try:
            current = GALLERY.read_text(encoding="utf-8")
        except OSError:
            print(f"STALE: {GALLERY} missing; run without --check to generate", file=sys.stderr)
            return 1
        if current != content:
            print(f"STALE: {GALLERY} differs from styles directory; regenerate", file=sys.stderr)
            return 1
        drift, _degraded = check_golden()
        if drift:
            print(f"STALE: golden sample regression found {drift} drift(s); re-run --render-golden and review", file=sys.stderr)
            return 1
        print("OK: gallery and golden samples up to date")
        return 0

    try:
        GALLERY.parent.mkdir(parents=True, exist_ok=True)
        GALLERY.write_text(content, encoding="utf-8")
    except OSError as exc:
        fail(f"cannot write {GALLERY}: {exc}")
    print(f"wrote {GALLERY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
