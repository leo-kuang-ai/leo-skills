#!/usr/bin/env python3
"""generate_style_gallery.py 单测：确定性生成 / --check 漂移守卫 / active 内置风格在场 /
金样板渲染（R-26）、嵌图行、双跑 sha 确定性、--check 金样板回归（R-65）、
降级模式（渲染后端缺失时回落输入 sha 对比）、S5 家族代表扩展（18 风格名单 /
canonical brief 解析 / 主题合同 / 代表渲染与画廊新节）。"""
import atexit
from functools import lru_cache
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import quote, unquote

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "generate_style_gallery.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import generate_style_gallery as gallery  # noqa: E402


def _run(args, *, gallery_path, thumbs_root, library_root=gallery.LIBRARY_DIR, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), "--library-root", str(library_root),
        "--gallery", str(gallery_path), "--thumbs-root", str(thumbs_root), *args],
        capture_output=True, text=True, env=env)


def _no_backend_env() -> dict:
    return dict(os.environ, LEO_PPT_RUNTIME_PYTHON="/nonexistent/python")


@lru_cache(maxsize=2)
def _canonical_subset(name="清爽专业风") -> Path:
    """复制真实资产依赖闭包，使用正式迁移器和 catalog owner 构建隔离 v2 库。"""
    from leo_ppt_generator.library_migration import materialize_shadow_library
    from leo_ppt_generator.template_catalog import build_catalog, publish_catalog
    temporary = tempfile.TemporaryDirectory(prefix="gallery-canonical-subset-")
    atexit.register(temporary.cleanup)
    root = Path(temporary.name).resolve()
    source = gallery._canonical_resolver()
    ids = [source.require(name, kind="style")["asset_id"], "builtin:template:cover-basic",
           "builtin:template:body-basic", "builtin:font:noto-sans-sc"]
    entities = {entity["asset_id"]: entity for identity in ids for entity in source.resolve_dependencies(identity)}
    frozen = source.freeze_assets(root / "snapshot", [source.fingerprint(identity) for identity in entities])
    library_source = frozen.builtin_root
    shutil.copyfile(gallery.LIBRARY_DIR / "library.json", library_source / "library.json")
    shutil.copytree(gallery.LIBRARY_DIR / "governance", library_source / "governance", dirs_exist_ok=True)
    library = root / "explicit-v2-library"
    materialize_shadow_library(library_source, library)
    publish_catalog(library, build_catalog(library))
    return library


class GalleryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gallery-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.gallery = self.root / "gallery.md"
        self.thumbs = self.root / "style-gallery"

    def run_cli(self, args=(), *, env=None):
        return _run(list(args), gallery_path=self.gallery, thumbs_root=self.thumbs, env=env)

    def prepare_degraded_inputs(self):
        for name in gallery.golden_style_names():
            gallery.write_inputs(self.thumbs / name, gallery.golden_inputs(name))

    def test_actual_v2_axis_counts_use_manifest_families(self):
        from tests.test_template_catalog_v2 import make_reference_bundle
        with tempfile.TemporaryDirectory() as temporary:
            library = make_reference_bundle(Path(temporary).resolve())
            with mock.patch.object(gallery, "LIBRARY_DIR", library):
                self.assertEqual(gallery.axis_counts(), [("argument（axis）", 1),
                    ("infographic（axis）", 1), ("rendering（axis）", 1)])

    def test_canonical_theme_reaches_both_chart_and_page(self):
        from leo_ppt_generator.render.theme import compute_effective_theme
        resolver = gallery._canonical_resolver()
        expected = compute_effective_theme(resolver.resolve(
            "builtin:theme:consulting-pyramid-light")["data"])
        inputs = gallery.golden_inputs("咨询金字塔风")
        self.assertEqual(inputs["theme.json"], expected)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            gallery, "_run_render", return_value=({}, False)
        ) as render:
            root = Path(tmp)
            gallery.render_page("builtin:template:body-basic", root / "slide.json", root / "out.png",
                                theme=root / "theme.json")
            request = render.call_args.kwargs["page_request"]
            self.assertEqual(request["theme"], str(root / "theme.json"))
            self.assertEqual(request["library_root"], str(resolver.builtin_root))
            self.assertEqual(request["generation"], resolver.generation)

    def test_backend_missing_on_stderr_uses_documented_degradation(self):
        result = subprocess.CompletedProcess([], 2, "", json.dumps({"status": "blocked", "reason_code": "render_backend_missing"}))
        with mock.patch.object(gallery, "runtime_python", return_value=Path(sys.executable)), mock.patch.object(gallery.subprocess, "run", return_value=result):
            envelope, degraded = gallery._run_render(["render", "chart"])
        self.assertTrue(degraded)
        self.assertEqual(envelope["reason_code"], "render_backend_missing")

    def test_generation_is_deterministic(self):
        self.run_cli()
        first = self.gallery.read_text(encoding="utf-8")
        self.run_cli()
        second = self.gallery.read_text(encoding="utf-8")
        self.assertEqual(first, second)

    def test_active_builtins_present(self):
        self.assertEqual(self.run_cli().returncode, 0)
        content = self.gallery.read_text(encoding="utf-8")
        for name in (
            "学术克制风", "品牌创意风", "清爽专业风", "咨询金字塔风",
            "教育明快风", "金融藏青风", "政务庄重风", "医疗洁净风",
            "管理清晰风", "科技暗色风",
        ):
            self.assertIn(name, content)
        self.assertIn("## 内置风格（10 套，直接可选）", content)

    def test_family_representatives_section_present(self):
        for name in gallery.golden_style_names():
            destination = self.thumbs / name
            destination.mkdir(parents=True)
            for page in gallery.PAGES:
                source = SKILL_DIR / "samples/style-gallery" / name / f"thumb-{page}.png"
                shutil.copyfile(source, destination / source.name)
        self.run_cli()
        content = self.gallery.read_text(encoding="utf-8")
        self.assertIn("## 新家族代表金样板（S5 进货 · R-65）", content)
        for family, name, _ in gallery.FAMILY_REPRESENTATIVES:
            self.assertIn(f"### {family} · {name}", content)
            self.assertIn(f"style-gallery/{quote(name)}/thumb-cover.png", content)
        # 10 active builtins + 8 representatives each embed three thumbnails
        self.assertEqual(len(re.findall(r"thumb-cover\.png", content)), 18)

    def test_check_passes_when_up_to_date(self):
        self.run_cli()
        self.prepare_degraded_inputs()
        result = self.run_cli(["--check"], env=_no_backend_env())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_fails_when_stale(self):
        self.run_cli()
        original = self.gallery.read_text(encoding="utf-8")
        try:
            self.gallery.write_text(original + "手工追加行\n", encoding="utf-8")
            self.prepare_degraded_inputs()
            result = self.run_cli(["--check"], env=_no_backend_env())
            self.assertEqual(result.returncode, 1)
            self.assertIn("STALE", result.stderr)
        finally:
            self.gallery.write_text(original, encoding="utf-8")


class FamilyRepresentativeTest(unittest.TestCase):
    """S5 家族代表扩展：18 风格名单 / canonical brief 解析 / 主题合同。"""

    def test_golden_roster_covers_current_catalog_styles(self):
        names = gallery.golden_style_names()
        self.assertEqual(len(names), 18)
        self.assertEqual(len(set(names)), 18)
        for _, name, _ in gallery.FAMILY_REPRESENTATIVES:
            self.assertIn(name, names)
        for name, _ in gallery.builtin_styles():
            self.assertIn(name, names)

    def test_representative_briefs_resolve_to_family_dir(self):
        for family, name, _ in gallery.FAMILY_REPRESENTATIVES:
            path = gallery._brief_path(name)
            expected = Path(gallery._canonical_resolver().require(name, kind="style")["path"])
            self.assertEqual(path, expected)
            self.assertTrue(path.is_file(), f"missing {path}")

    def test_family_uses_canonical_theme(self):
        # terminal (dark canvas + light foreground) and cream families (dark
        # neutral ink, hex-free canvas note) must not land dark backgrounds
        # or washed-out plot anchors on the light templates
        for name in ("Dracula紫风", "奶油温柔风"):
            inputs = gallery.golden_inputs(name)
            theme = inputs["theme.json"]
            self.assertIn("colors", theme)
            self.assertIn("fonts", theme)

    def test_light_family_uses_canonical_theme(self):
        inputs = gallery.golden_inputs("故宫墨红风")
        theme = inputs["theme.json"]
        self.assertEqual(theme["colors"]["primary"], "#8C3232")
        self.assertEqual(theme["colors"]["background"], "#F4F1E9")


class CanonicalContextTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gallery-context-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.library = self.root / "arbitrary-library-name"
        shutil.copytree(_canonical_subset(), self.library)

    def test_explicit_library_mapping_controls_real_chart_palette(self):
        from leo_ppt_generator.storage import atomic_write_json
        from leo_ppt_generator.template_catalog import build_catalog, publish_catalog
        mapping_path = self.library / "governance/rules/chart-theme-mapping.json"
        mapping = json.loads(mapping_path.read_text())
        mapping["dialects"]["mermaid-xychart"]["xyChart"]["plotColorPalette"] = "accent"
        atomic_write_json(mapping_path, mapping)
        publish_catalog(self.library, build_catalog(self.library))
        thumbs = self.root / "thumbs"
        gallery.render_golden(thumbs_root=thumbs, styles=["清爽专业风"], library_root=self.library)
        theme = json.loads((thumbs / "清爽专业风/theme.json").read_text())
        chart = json.loads((thumbs / "清爽专业风/slide-chart.json").read_text())["chart_svg"]
        import xml.etree.ElementTree as ET
        bars = ET.fromstring(chart).findall('.//{http://www.w3.org/2000/svg}g[@class="bar-plot-0"]/{http://www.w3.org/2000/svg}rect')
        self.assertEqual(len(bars), 4)
        self.assertEqual({bar.get("fill") for bar in bars}, {theme["colors"]["accent"]})

    def test_custom_gallery_and_thumbnail_paths_link_real_builtin_and_family_images(self):
        for name in ("清爽专业风", "Dracula紫风"):
            with self.subTest(style=name):
                gallery_path = self.root / name / "文档 (输出)" / "gallery.md"
                thumbs = self.root / name / "图像 (金样板)"
                result = _run(["--render-golden"], gallery_path=gallery_path, thumbs_root=thumbs,
                              library_root=_canonical_subset(name))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                links = re.findall(r"!\[[^\]]+\]\(([^)]+)\)", gallery_path.read_text())
                self.assertEqual(len(links), 3)
                for link in links:
                    self.assertFalse(any(character in link for character in " ()"), link)
                    path = gallery_path.parent / unquote(link)
                    self.assertTrue(path.is_file(), str(path))
                    from PIL import Image
                    with Image.open(path) as image:
                        self.assertEqual(image.size, (1280, 720))

    def test_missing_v2_catalog_does_not_fall_back_to_delivery(self):
        (self.library / "catalog/current.json").unlink()
        with self.assertRaises(SystemExit) as caught:
            gallery.builtin_styles(self.library)
        self.assertEqual(caught.exception.code, 2)

    def test_missing_canonical_theme_is_not_replaced_by_palette(self):
        from leo_ppt_generator.storage import atomic_write_json
        from leo_ppt_generator.template_catalog import build_catalog, publish_catalog
        resolver = gallery._canonical_resolver(self.library)
        style = resolver.require("清爽专业风", kind="style")
        style["data"]["bindings"].pop("theme_default")
        atomic_write_json(Path(style["path"]), style["data"])
        publish_catalog(self.library, build_catalog(self.library))
        with self.assertRaisesRegex(ValueError, "缺少 canonical theme"):
            gallery.golden_inputs("清爽专业风", self.library)

    def test_changed_generation_is_rejected_by_parent_and_managed_renderer(self):
        from leo_ppt_generator.storage import atomic_write_json
        from leo_ppt_generator.template_catalog import build_catalog, publish_catalog
        resolver = gallery._canonical_resolver(self.library)
        before = resolver.generation
        style = resolver.require("清爽专业风", kind="style")
        style["data"]["visual_language"]["direction"] += " 漂移检查"
        atomic_write_json(Path(style["path"]), style["data"])
        publish_catalog(self.library, build_catalog(self.library))
        with self.assertRaisesRegex(ValueError, "gallery_catalog_generation_changed"):
            gallery._assert_generation(resolver)
        request = {"library_root": str(self.library), "generation": before,
                   "template_id": "builtin:template:cover-basic", "data": "unused", "theme": "unused",
                   "out": str(self.root / "must-not-render.png")}
        for worker in ("--_render-page", "--_render-chart"):
            with self.subTest(worker=worker):
                result = subprocess.run([sys.executable, str(SCRIPT), worker], input=json.dumps(request),
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)["reason_code"], "gallery_catalog_generation_changed")
                self.assertFalse((self.root / "must-not-render.png").exists())

    def test_missing_local_chart_mapping_never_uses_delivery_mapping(self):
        resolver = gallery._canonical_resolver(self.library)
        inputs = self.root / "inputs"
        gallery.write_inputs(inputs, gallery.golden_inputs("清爽专业风", resolver=resolver))
        (self.library / "governance/rules/chart-theme-mapping.json").unlink()
        output = self.root / "must-not-render.svg"
        with self.assertRaises(SystemExit) as caught:
            gallery.render_chart_svg(inputs / "chart.mmd", inputs / "theme.json", output, resolver=resolver)
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(output.exists())

    def test_missing_local_template_never_uses_valid_delivery_template(self):
        resolver = gallery._canonical_resolver(self.library)
        template = resolver.resolve("builtin:template:cover-basic")
        Path(template["path"]).with_name("page.html").unlink()
        inputs = self.root / "inputs"
        gallery.write_inputs(inputs, gallery.golden_inputs("清爽专业风", resolver=resolver))
        output = self.root / "must-not-render.png"
        with mock.patch.dict(os.environ, {"LEO_PPT_BUNDLE": str(SKILL_DIR)}), self.assertRaises(SystemExit):
            gallery.render_page("builtin:template:cover-basic", inputs / "slide-cover.json", output,
                                theme=inputs / "theme.json", resolver=resolver)
        self.assertFalse(output.exists())


class GoldenSampleTest(unittest.TestCase):
    """R-26 金样板渲染 + R-65 回归（scoped fixture，走真实渲染 lane）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-gallery-test-")
        self.tmp = Path(self._tmp.name)
        self.styles = _canonical_subset()
        self.thumbs = self.tmp / "thumbs"
        if gallery.runtime_python() is None:
            self.skipTest("render backend (runtime venv) unavailable")

    def tearDown(self):
        self._tmp.cleanup()

    def test_render_golden_produces_three_thumbs_and_inputs(self):
        gallery.render_golden(thumbs_root=self.thumbs, styles=["清爽专业风"],
                              library_root=self.styles)
        style_dir = self.thumbs / "清爽专业风"
        for page in ("cover", "content", "chart"):
            self.assertTrue((style_dir / f"thumb-{page}.png").is_file(), page)
            self.assertTrue((style_dir / f"slide-{page}.json").is_file(), page)
            from PIL import Image
            with Image.open(style_dir / f"thumb-{page}.png") as rendered:
                self.assertEqual(rendered.size, (1280, 720))
                self.assertEqual(rendered.format, "PNG")
        for aux in ("chart.mmd", "theme.json"):
            self.assertTrue((style_dir / aux).is_file(), aux)
        data = json.loads((style_dir / "slide-cover.json").read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "清爽专业风")
        self.assertNotIn("background_color", data)
        self.assertEqual(json.loads((style_dir / "theme.json").read_text())["colors"]["background"], "#FFFFFF")
        # chart page embeds the rendered SVG (deck palette lands verbatim)
        chart = (style_dir / "slide-chart.json").read_text(encoding="utf-8")
        self.assertIn("chart_svg", chart)
        self.assertIn("<svg", json.loads(chart)["chart_svg"])

    def test_double_run_sha_deterministic(self):
        names = ["清爽专业风"]
        gallery.render_golden(thumbs_root=self.thumbs, styles=names,
                              library_root=self.styles)
        style_dir = self.thumbs / "清爽专业风"
        first = {page: gallery._sha256(style_dir / f"thumb-{page}.png") for page in gallery.PAGES}
        gallery.render_golden(thumbs_root=self.thumbs, styles=names, library_root=self.styles)
        second = {page: gallery._sha256(style_dir / f"thumb-{page}.png") for page in gallery.PAGES}
        self.assertEqual(first, second)

    def test_check_golden_detects_thumbnail_drift(self):
        style = ["清爽专业风"]
        gallery.render_golden(thumbs_root=self.thumbs, styles=style,
                              library_root=self.styles)
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs, styles=style,
                                        library_root=self.styles)
        self.assertEqual(drift, 0)
        # tamper one committed thumbnail: re-render must flag the drift (R-65)
        thumb = self.thumbs / "清爽专业风" / "thumb-cover.png"
        thumb.write_bytes(thumb.read_bytes()[:-8] + b"\x00" * 8)
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs, styles=style,
                                        library_root=self.styles)
        self.assertGreaterEqual(drift, 1)

    def test_check_golden_detects_input_drift(self):
        style = ["清爽专业风"]
        gallery.render_golden(thumbs_root=self.thumbs, styles=style,
                              library_root=self.styles)
        committed = self.thumbs / "清爽专业风" / "slide-cover.json"
        payload = json.loads(committed.read_text(encoding="utf-8"))
        payload["subtitle"] += "（手改）"
        committed.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs, styles=style,
                                        library_root=self.styles)
        self.assertGreaterEqual(drift, 1)

    def test_check_golden_detects_missing_thumbnail(self):
        style = ["清爽专业风"]
        gallery.render_golden(thumbs_root=self.thumbs, styles=style,
                              library_root=self.styles)
        (self.thumbs / "清爽专业风" / "thumb-chart.png").unlink()
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs, styles=style,
                                        library_root=self.styles)
        self.assertGreaterEqual(drift, 1)

    def test_gallery_embeds_golden_thumbs_when_present(self):
        gallery.render_golden(thumbs_root=self.thumbs, styles=["清爽专业风"],
                              library_root=self.styles)
        builtins = gallery.builtin_styles(self.styles)
        content = gallery.render(builtins, gallery.axis_counts(self.styles),
                                 thumbs_root=self.thumbs, gallery_path=self.tmp / "gallery.md")
        self.assertIn("## 内置风格金样板", content)
        self.assertIn(f"thumbs/{quote('清爽专业风')}/thumb-cover.png", content)
        self.assertIn(f"thumbs/{quote('清爽专业风')}/thumb-chart.png", content)
        self.assertEqual(len(re.findall(r"thumb-cover\.png", content)), 1)

    def test_render_golden_family_representative(self):
        # S5 representative renders through the same lane from its family
        # subdirectory brief; visibility guard keeps the cover readable
        library_root = _canonical_subset("Dracula紫风")
        gallery.render_golden(thumbs_root=self.thumbs, styles=["Dracula紫风"],
                              library_root=library_root)
        style_dir = self.thumbs / "Dracula紫风"
        for page in ("cover", "content", "chart"):
            self.assertTrue((style_dir / f"thumb-{page}.png").is_file(), page)
            self.assertTrue((style_dir / f"slide-{page}.json").is_file(), page)
        data = json.loads((style_dir / "slide-cover.json").read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "Dracula紫风")
        self.assertNotIn("background_color", data)
        chart = json.loads((style_dir / "slide-chart.json").read_text(encoding="utf-8"))
        self.assertIn("<svg", chart["chart_svg"])
        self.assertIn("#F8F8F2", chart["chart_svg"])  # canonical 单系列主色
        self.assertEqual(json.loads((style_dir / "theme.json").read_text())["colors"]["accent"], "#FF79C6")
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs,
                                        styles=["Dracula紫风"],
                                        library_root=library_root)
        self.assertEqual(drift, 0)


class DegradedModeTest(unittest.TestCase):
    """渲染后端缺失：降级为输入 sha 对比，不静默放弃（R-65 fallback）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-gallery-degraded-")
        self.tmp = Path(self._tmp.name)
        self.styles = _canonical_subset()
        self.thumbs = self.tmp / "thumbs"

    def tearDown(self):
        self._tmp.cleanup()

    def test_degraded_render_writes_inputs_without_thumbs(self):
        with mock.patch.dict(os.environ, _no_backend_env()):
            self.assertIsNone(gallery.runtime_python())
            gallery.render_golden(thumbs_root=self.thumbs, styles=["清爽专业风"],
                                  library_root=self.styles)
        style_dir = self.thumbs / "清爽专业风"
        self.assertTrue((style_dir / "slide-cover.json").is_file())
        self.assertTrue((style_dir / "chart.mmd").is_file())
        self.assertFalse((style_dir / "thumb-cover.png").exists())

    def test_degraded_check_skips_thumbnail_compare(self):
        # inputs committed, thumbnails never rendered: degraded check must not
        # count missing thumbnails as drift (baseline degrades to inputs)
        gallery.write_inputs(
            self.thumbs / "清爽专业风",
            gallery.golden_inputs("清爽专业风", self.styles),
        )
        with mock.patch.dict(os.environ, _no_backend_env()):
            drift, degraded = gallery.check_golden(
                thumbs_root=self.thumbs, styles=["清爽专业风"],
                library_root=self.styles)
        self.assertTrue(degraded)
        self.assertEqual(drift, 0)

    def test_degraded_check_detects_input_drift(self):
        with mock.patch.dict(os.environ, _no_backend_env()):
            gallery.render_golden(thumbs_root=self.thumbs, styles=["清爽专业风"],
                                  library_root=self.styles)
        committed = self.thumbs / "清爽专业风" / "slide-cover.json"
        payload = json.loads(committed.read_text(encoding="utf-8"))
        payload["kicker"] = "手改"
        committed.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        with mock.patch.dict(os.environ, _no_backend_env()):
            drift, degraded = gallery.check_golden(
                thumbs_root=self.thumbs, styles=["清爽专业风"],
                library_root=self.styles)
        self.assertTrue(degraded)
        self.assertGreaterEqual(drift, 1)

    def test_degraded_family_representative_writes_inputs(self):
        library_root = _canonical_subset("Dracula紫风")
        with mock.patch.dict(os.environ, _no_backend_env()):
            gallery.render_golden(thumbs_root=self.thumbs, styles=["Dracula紫风"],
                                  library_root=library_root)
        style_dir = self.thumbs / "Dracula紫风"
        self.assertTrue((style_dir / "slide-cover.json").is_file())
        self.assertTrue((style_dir / "theme.json").is_file())
        self.assertFalse((style_dir / "thumb-cover.png").exists())


if __name__ == "__main__":
    unittest.main()
