#!/usr/bin/env python3
"""从明确的 canonical 库生成风格画廊与金样板。

同次操作固定 resolver generation；风格、主题、页模板和字体均由同一库解析。
页面通过托管解释器转发给 render.page owner，图表复用 render chart。
默认写 samples/style-gallery.md；--library-root、--gallery、--thumbs-root 可显式隔离。
--render-golden 生成三页 1280×720 PNG 及确定性输入；--check 重渲染比较摘要。
后端缺失时明确退化为输入字节对比，不能作为视觉通过。
退出码：0 为生成或核验通过，1 为漂移，2 为输入或渲染错误。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))
from leo_ppt_generator.asset_resolver import AssetResolver, ResolverError
from leo_ppt_generator.render.theme import compute_effective_theme

LIBRARY_DIR = SKILL_DIR / "template-library"
GALLERY = SKILL_DIR / "samples" / "style-gallery.md"
THUMBS_ROOT = SKILL_DIR / "samples" / "style-gallery"
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

# S5 intake families (canonical/styles/<style>/) and the one
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

def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def warn(message: str) -> None:
    print(f"WARN: {message}", file=sys.stderr)


# ---------------------------------------------------------------- styles ---

def _canonical_resolver(library_root: Path | None = None) -> AssetResolver:
    """只通过正式 resolver 读取明确的库根，不加载用户覆盖。"""
    root = Path(library_root or LIBRARY_DIR).absolute()
    try:
        resolver = AssetResolver(library=root, home=root / ".gallery-no-user-home")
        if resolver.user_root is not None:
            raise ValueError("gallery_user_overlay_forbidden")
        _ = resolver.generation
        return resolver
    except (ResolverError, ValueError) as exc:
        fail(f"canonical template library unavailable: {exc}")
    raise AssertionError("unreachable")


def _gallery_resolver(library_root=None, resolver=None):
    if resolver is not None:
        if library_root is not None and Path(library_root).absolute() != resolver.builtin_root:
            raise ValueError("gallery_library_context_mismatch")
        return resolver
    return _canonical_resolver(library_root)


def _assert_generation(resolver):
    if _canonical_resolver(resolver.builtin_root).generation != resolver.generation:
        raise ValueError("gallery_catalog_generation_changed")


def builtin_styles(library_root=None, *, resolver=None) -> "list[tuple[str, list[str]]]":
    resolver = _gallery_resolver(library_root, resolver)
    entries = []
    for entity in resolver.entities:
        if entity["kind"] != "style" or entity.get("lifecycle") != "active":
            continue
        data = resolver.resolve(entity["asset_id"])["data"]
        scenarios = (data.get("taxonomy") or {}).get("scenarios") or []
        if not scenarios:
            direction = (data.get("visual_language") or {}).get("direction")
            scenarios = [direction] if direction else []
        entries.append((entity["name"], [str(item) for item in scenarios]))
    return sorted(entries, key=lambda item: item[0])


def axis_counts(library_root=None, *, resolver=None) -> "list[tuple[str, int]]":
    """按 resolver 参考清单与 manifest family 统计轴，目录位置不定义语义。"""
    resolver = _gallery_resolver(library_root, resolver)
    counts: dict[str, int] = {}
    for entity in resolver.references:
        group = resolver.resolve(entity["asset_id"])["data"]["kind"]
        counts[group] = counts.get(group, 0) + 1
    return [(f"{group}（axis）", counts[group]) for group in sorted(counts)]


def _brief_path(name, library_root=None, *, resolver=None) -> Path:
    return Path(_gallery_resolver(library_root, resolver).require(name, kind="style")["path"])


def _brief_json(name, library_root=None, *, resolver=None) -> dict:
    return _gallery_resolver(library_root, resolver).require(name, kind="style")["data"]


def _representatives(resolver):
    available = {row["name"] for row in resolver.entities if row["kind"] == "style"}
    return [row for row in FAMILY_REPRESENTATIVES if row[1] in available]


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


# ---------------------------------------------------------- golden data ---

def golden_style_names(library_root=None, *, resolver=None) -> "list[str]":
    resolver = _gallery_resolver(library_root, resolver)
    names = [name for name, _ in builtin_styles(resolver=resolver)]
    return list(dict.fromkeys(names + [row[1] for row in _representatives(resolver)]))


def golden_inputs(name, library_root=None, *, resolver=None) -> dict:
    """输入只消费 canonical brief 和主题；金样板不代表视觉验收。"""
    resolver = _gallery_resolver(library_root, resolver)
    brief = _brief_json(name, resolver=resolver)
    language = brief.get("visual_language") or {}
    best_for = _clip(str(language.get("direction") or name), 56)
    patterns = [_clip(str(item), 44) for item in
                (language.get("features") or language.get("composition_discipline") or [])[:4]]
    patterns = patterns or ["围绕一个论点组织支撑材料"]
    theme_id = (brief.get("bindings") or {}).get("theme_default")
    if not theme_id:
        raise ValueError(f"画廊风格 {name} 缺少 canonical theme 绑定")
    theme = compute_effective_theme(resolver.require(theme_id, kind="theme")["data"])
    return {
        "slide-cover.json": {"kicker": "LEO 风格金样板", "title": name, "subtitle": best_for,
                             "footer_left": "leo-ppt-generator", "footer_right": "golden sample"},
        "slide-content.json": {"title": f"{name} · 主题预览", "bullets": patterns, "page_no": "02"},
        "slide-chart.json": {"title": f"{name} · 图表页", "bullets": ["数据口径固定：季度交付吞吐示例"], "page_no": "03"},
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


def _run_render(args: "list[str]", *, page_request=None, chart_request=None) -> "tuple[dict | None, bool]":
    """Run one render-lane CLI call. Returns (envelope, degraded)."""
    python = runtime_python()
    if python is None:
        return None, True
    request = page_request if page_request is not None else chart_request
    worker = "--_render-page" if page_request is not None else "--_render-chart"
    command = ([str(python), str(Path(__file__).resolve()), worker] if request is not None
               else [str(python), "-m", "leo_ppt_generator", *args])
    result = subprocess.run(command, input=json.dumps(request) if request is not None else None,
                            capture_output=True, text=True, timeout=180)
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


def render_chart_svg(mmd: Path, theme: Path, out: Path,
                     *, library_root=None, resolver=None) -> "tuple[str | None, bool]":
    """将固定图表与明确的库上下文转发给 chart owner。"""
    resolver = _gallery_resolver(library_root, resolver)
    envelope, degraded = _run_render([], chart_request={
        "library_root": str(resolver.builtin_root), "generation": resolver.generation,
        "code_file": str(mmd.absolute()), "out": str(out.absolute()),
        "theme": str(theme.absolute()),
    })
    if degraded:
        return None, True
    try:
        return out.read_text(encoding="utf-8"), False
    except OSError as exc:
        fail(f"cannot read rendered chart SVG: {exc}")


def render_page(template_id: str, data: Path, out: Path,
                *, theme: Path, library_root=None, resolver=None) -> "tuple[dict | None, bool]":
    resolver = _gallery_resolver(library_root, resolver)
    envelope, degraded = _run_render([], page_request={
        "library_root": str(resolver.builtin_root), "generation": resolver.generation,
        "template_id": template_id, "data": str(data.absolute()), "out": str(out.absolute()),
        "theme": str(theme.absolute()),
    })
    if not degraded:
        sidecar = out.with_name(out.name + ".render.json")
        if sidecar.is_file():
            # provenance sidecar carries timestamps; golden baseline stays
            # byte-deterministic, so it is not part of the committed assets.
            sidecar.unlink()
    return envelope, degraded


def _render_page_worker(request):
    """托管解释器只转发显式库上下文给现有 renderer，不另建渲染实现。"""
    from leo_ppt_generator.render.page import render_page as render_owner
    try:
        resolver = _canonical_resolver(Path(request["library_root"]))
        if resolver.generation != request["generation"]:
            raise ValueError("gallery_catalog_generation_changed")
        result = render_owner(request["template_id"], request["data"], request["out"], size=(1280, 720),
                              theme_variables=json.loads(Path(request["theme"]).read_text()), resolver=resolver)
        _assert_generation(resolver)
        print(json.dumps({"status": "ready", "render": result}, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason_code": getattr(exc, "reason_code", str(exc))}, ensure_ascii=False))
        return 2


def _render_chart_worker(request):
    """图表与页面使用同库 generation；不通过全局环境切换资产来源。"""
    from leo_ppt_generator.render.chart import render_chart
    try:
        resolver = _canonical_resolver(Path(request["library_root"]))
        if resolver.generation != request["generation"]:
            raise ValueError("gallery_catalog_generation_changed")
        result = render_chart(dialect="mermaid", code_file=request["code_file"], out=request["out"],
                              theme_file=request["theme"], resolver=resolver)
        _assert_generation(resolver)
        print(json.dumps({"status": "ready", "render": result}, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason_code": getattr(exc, "reason_code", str(exc))}, ensure_ascii=False))
        return 2


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
                  library_root=None, *, resolver=None) -> int:
    """Write golden inputs + thumbnails for every golden style (R-26/R-65)."""
    resolver = _gallery_resolver(library_root, resolver)
    _assert_generation(resolver)
    names = styles or golden_style_names(resolver=resolver)
    degraded = False
    for name in names:
        style_dir = thumbs_root / name
        inputs = golden_inputs(name, resolver=resolver)
        write_inputs(style_dir, inputs)
        # chart inputs live in style_dir (deterministic baseline); the SVG and
        # its timestamped provenance sidecar are rendered into a temp dir so
        # only the embedded chart_svg lands in the committed baseline.
        with tempfile.TemporaryDirectory(prefix="leo-golden-chart-") as tmp:
            chart_svg, chart_degraded = render_chart_svg(
                style_dir / "chart.mmd", style_dir / "theme.json", Path(tmp) / "chart.svg", resolver=resolver
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
            template = "builtin:template:cover-basic" if page == "cover" else "builtin:template:body-basic"
            _, page_degraded = render_page(template, data, out, theme=style_dir / "theme.json", resolver=resolver)
            degraded = degraded or page_degraded
        print(f"golden: {name} rendered" + (" (chart png skipped: backend missing)" if chart_svg is None else ""))
    _assert_generation(resolver)
    if degraded:
        warn("render backend unavailable: golden thumbnails degraded to deterministic inputs only (R-65 check compares input shas)")
    return 0


# ------------------------------------------------------------- regression ---

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_golden(thumbs_root: Path = THUMBS_ROOT, styles: "list[str] | None" = None,
                 library_root=None, *, resolver=None) -> "tuple[int, bool]":
    """R-65 golden regression: re-render into a temp dir and compare shas.

    Returns (drift_count, degraded). Committed thumbnails are compared by
    sha256; when the render backend is missing the comparison falls back to
    the deterministic golden inputs (byte compare) and reports degraded.
    ``slide-chart.json`` embeds the rendered chart_svg, so it is compared
    after chart assembly, not in the pure-input loop.
    """
    resolver = _gallery_resolver(library_root, resolver)
    _assert_generation(resolver)
    names = styles or golden_style_names(resolver=resolver)
    drift = 0
    degraded = runtime_python() is None
    if degraded:
        warn("render backend unavailable: R-65 check degraded to golden-input byte compare")
    for name in names:
        committed_dir = thumbs_root / name
        inputs = golden_inputs(name, resolver=resolver)
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
                workdir / "chart.mmd", workdir / "theme.json", Path(tmp) / "chart.svg", resolver=resolver
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
                template = "builtin:template:cover-basic" if page == "cover" else "builtin:template:body-basic"
                _, page_degraded = render_page(template, data, fresh, theme=workdir / "theme.json", resolver=resolver)
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
    _assert_generation(resolver)
    return drift, degraded


# ---------------------------------------------------------------- gallery ---

def _thumbs_present(style_dir: Path) -> bool:
    return all((style_dir / f"thumb-{page}.png").is_file() for page in PAGES)


def _thumbnail_row(name: str, thumbs_root: Path, gallery_path: Path) -> str:
    cells = []
    for page, label in zip(PAGES, ("封面", "内容", "图表")):
        relative = os.path.relpath(thumbs_root / name / f"thumb-{page}.png", gallery_path.parent)
        url = quote(Path(relative).as_posix(), safe="/")
        cells.append(f"![{name} {label}金样板]({url})")
    return "| " + " | ".join(cells) + " |"


def render(builtins: "list[tuple[str, list[str]]]", axes: "list[tuple[str, int]]",
           representatives: "list[tuple[str, str, str]] | None" = None,
           thumbs_root: Path = THUMBS_ROOT, gallery_path: Path = GALLERY) -> str:
    if representatives is None:
        representatives = FAMILY_REPRESENTATIVES
    lines = [
        "# 风格画廊（生成物）",
        "",
        "> 由 `python3 scripts/generate_style_gallery.py` 从 `template-library/catalog/current.json` 指向的 canonical catalog 确定性生成；",
        "> 手工编辑会被 `--check` 判漂移。执行期身份索引见",
        "> [`template-library/catalog/current.json`](../template-library/catalog/current.json) 与其 generation 下的 `registry.json`。",
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
            "> 页面与图表共同消费 canonical theme；哈希一致仅证明可重复，不代表设计质量通过。",
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
                _thumbnail_row(name, thumbs_root, gallery_path),
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
            "> `--check` 回归；各家族按 canonical theme 的明暗模式渲染，",
            "> 图表和页面共同消费同一份主题。",
            "> 预览不授予 draft 风格生产资格，也不代表审美验收通过。",
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
                _thumbnail_row(name, thumbs_root, gallery_path),
            ]

    lines += [
        "",
        f"## 结构轴目录（{len(axes)} 个分组，catalog 口径）",
        "",
        "| 轴 | 份数 |",
        "| --- | --- |",
    ]
    for label, count in axes:
        lines.append(f"| {label} | {count} |")
    total = sum(count for _, count in axes) + len(builtins)
    lines += [
        "",
        f"上述结构轴与 active 内置风格共 {total} 项；draft 风格和治理参考资产不计入直接可选区。",
        "全库实体数量以 catalog generation 的 `registry.json` 为准，不以画廊条目数代替可执行资格。",
        "选定后由 `style render` 确定性注入，流程见 [`references/style-library.md`](../references/style-library.md)。",
        "",
    ]
    return "\n".join(lines)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the style gallery from the canonical template library.")
    parser.add_argument("--check", action="store_true", help="verify the gallery and golden samples are up to date instead of writing")
    parser.add_argument("--render-golden", action="store_true",
                        help="render golden sample thumbnails for active styles and family representatives (R-26/R-65) before writing the gallery")
    parser.add_argument("--library-root", type=Path, default=LIBRARY_DIR, help="明确的 canonical 库根")
    parser.add_argument("--gallery", type=Path, default=GALLERY, help="画廊 Markdown 输出路径")
    parser.add_argument("--thumbs-root", type=Path, default=THUMBS_ROOT, help="金样板输出目录")
    parser.add_argument("--_render-page", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_render-chart", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args._render_page:
        return _render_page_worker(json.load(sys.stdin))
    if args._render_chart:
        return _render_chart_worker(json.load(sys.stdin))
    resolver = _canonical_resolver(args.library_root)

    if args.render_golden:
        render_golden(thumbs_root=args.thumbs_root, resolver=resolver)

    builtins = builtin_styles(resolver=resolver)
    content = render(builtins, axis_counts(resolver=resolver), representatives=_representatives(resolver),
                     thumbs_root=args.thumbs_root, gallery_path=args.gallery)
    _assert_generation(resolver)

    if args.check:
        try:
            current = args.gallery.read_text(encoding="utf-8")
        except OSError:
            print(f"STALE: {args.gallery} missing; run without --check to generate", file=sys.stderr)
            return 1
        if current != content:
            print(f"STALE: {args.gallery} differs from canonical catalog; regenerate", file=sys.stderr)
            return 1
        drift, _degraded = check_golden(thumbs_root=args.thumbs_root, resolver=resolver)
        if drift:
            print(f"STALE: golden sample regression found {drift} drift(s); re-run --render-golden and review", file=sys.stderr)
            return 1
        print("OK: gallery and golden samples up to date")
        return 0

    try:
        args.gallery.parent.mkdir(parents=True, exist_ok=True)
        args.gallery.write_text(content, encoding="utf-8")
    except OSError as exc:
        fail(f"cannot write {args.gallery}: {exc}")
    print(f"wrote {args.gallery}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
