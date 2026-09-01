#!/usr/bin/env python3
"""generate_style_gallery.py 单测：确定性生成 / --check 漂移守卫 / 内置 11 套在场 /
金样板渲染（R-26）、嵌图行、双跑 sha 确定性、--check 金样板回归（R-65）、
降级模式（渲染后端缺失时回落输入 sha 对比）、S5 家族代表扩展（19 风格名单 /
子目录 brief 解析 / 暗底家族可见性守护 / 代表渲染与画廊新节）。"""
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

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "generate_style_gallery.py"
GALLERY = SKILL_DIR / "samples" / "style-gallery.md"
SAMPLE_BRIEF = SKILL_DIR / "references" / "styles" / "清爽专业风.md"
FAMILY_STYLES_DIR = SKILL_DIR / "references" / "styles" / "01_通用母版"
REP_BRIEF = FAMILY_STYLES_DIR / "终端配色" / "Dracula紫风.md"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import generate_style_gallery as gallery  # noqa: E402


def _run(args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args, capture_output=True, text=True, env=env
    )


def _fixture_root(tmp: Path, brief_name: str = "清爽专业风") -> Path:
    """One-brief styles root for scoped golden tests (real brief, real lane)."""
    styles = tmp / "styles"
    styles.mkdir(parents=True)
    shutil.copy(SAMPLE_BRIEF, styles / f"{brief_name}.md")
    sidecar = SKILL_DIR / "references" / "styles" / f"{brief_name}.layouts.json"
    if sidecar.is_file():
        shutil.copy(sidecar, styles / f"{brief_name}.layouts.json")
    return styles


def _no_backend_env() -> dict:
    return dict(os.environ, LEO_PPT_RUNTIME_PYTHON="/nonexistent/python")


def _family_fixture_root(tmp: Path) -> Path:
    """One-representative styles root keeping the family subdirectory layout
    (real brief, real lane) for S5 representative golden tests."""
    styles = tmp / "styles" / "01_通用母版" / "终端配色"
    styles.mkdir(parents=True)
    shutil.copy(REP_BRIEF, styles / "Dracula紫风.md")
    return tmp / "styles"


class GalleryTest(unittest.TestCase):
    def test_generation_is_deterministic(self):
        _run([])
        first = GALLERY.read_text(encoding="utf-8")
        _run([])
        second = GALLERY.read_text(encoding="utf-8")
        self.assertEqual(first, second)

    def test_all_eleven_builtins_present(self):
        content = GALLERY.read_text(encoding="utf-8")
        for name in (
            "党政红风格", "创意杂志风", "手绘白板风", "教学课件风",
            "数据仪表盘风", "清爽专业风", "电子墨水杂志风", "科研答辩风",
        ):
            self.assertIn(name, content)
        self.assertIn("## 内置风格（11 套，直接可选）", content)

    def test_family_representatives_section_present(self):
        _run([])  # gallery is a generated artifact; rebuild before asserting
        content = GALLERY.read_text(encoding="utf-8")
        self.assertIn("## 新家族代表金样板（S5 进货 · R-65）", content)
        for family, name, _ in gallery.FAMILY_REPRESENTATIVES:
            self.assertIn(f"### {family} · {name}", content)
            self.assertIn(f"style-gallery/{name}/thumb-cover.png", content)
        # 11 builtins + 8 representatives each embed three thumbnails
        self.assertEqual(len(re.findall(r"thumb-cover\.png", content)), 19)

    def test_check_passes_when_up_to_date(self):
        _run([])
        result = _run(["--check"])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_fails_when_stale(self):
        _run([])
        original = GALLERY.read_text(encoding="utf-8")
        try:
            GALLERY.write_text(original + "手工追加行\n", encoding="utf-8")
            result = _run(["--check"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("STALE", result.stderr)
        finally:
            GALLERY.write_text(original, encoding="utf-8")


class FamilyRepresentativeTest(unittest.TestCase):
    """S5 家族代表扩展：19 风格名单 / 子目录 brief 解析 / 可见性守护。"""

    def test_golden_roster_covers_nineteen_styles(self):
        names = gallery.golden_style_names()
        self.assertEqual(len(names), 19)
        self.assertEqual(len(set(names)), 19)
        for _, name, _ in gallery.FAMILY_REPRESENTATIVES:
            self.assertIn(name, names)
        for name, _ in gallery.builtin_styles():
            self.assertIn(name, names)

    def test_representative_briefs_resolve_to_family_dir(self):
        for family, name, _ in gallery.FAMILY_REPRESENTATIVES:
            path = gallery._brief_path(name)
            expected = (
                gallery.STYLES_DIR / "01_通用母版" / family / f"{name}.md"
            )
            self.assertEqual(path, expected)
            self.assertTrue(path.is_file(), f"missing {path}")

    def test_dark_family_palette_falls_back_to_paper(self):
        # terminal (dark canvas + light foreground) and cream families (dark
        # neutral ink, hex-free canvas note) must not land dark backgrounds
        # or washed-out plot anchors on the light templates
        for name, kept_anchor in (("Dracula紫风", "#FF79C6"),
                                  ("奶油温柔风", "#A3B18A")):
            inputs = gallery.golden_inputs(name)
            self.assertNotIn("background_color", inputs["slide-cover.json"])
            theme = inputs["theme.json"]
            self.assertNotIn("background", theme)
            self.assertEqual(sorted(theme), ["accent"])
            self.assertEqual(theme["accent"], kept_anchor)

    def test_light_family_keeps_palette_background(self):
        inputs = gallery.golden_inputs("故宫墨红风")
        self.assertEqual(inputs["slide-cover.json"]["background_color"], "#E6E1D3")
        theme = inputs["theme.json"]
        self.assertEqual(theme["primary"], "#8C3232")
        self.assertEqual(theme["background"], "#E6E1D3")


class GoldenSampleTest(unittest.TestCase):
    """R-26 金样板渲染 + R-65 回归（scoped fixture，走真实渲染 lane）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-gallery-test-")
        self.tmp = Path(self._tmp.name)
        self.styles = _fixture_root(self.tmp)
        self.thumbs = self.tmp / "thumbs"
        if gallery.runtime_python() is None:
            self.skipTest("render backend (runtime venv) unavailable")

    def tearDown(self):
        self._tmp.cleanup()

    def test_render_golden_produces_three_thumbs_and_inputs(self):
        gallery.render_golden(thumbs_root=self.thumbs, styles=["清爽专业风"],
                              styles_root=self.styles)
        style_dir = self.thumbs / "清爽专业风"
        for page in ("cover", "content", "chart"):
            self.assertTrue((style_dir / f"thumb-{page}.png").is_file(), page)
            self.assertTrue((style_dir / f"slide-{page}.json").is_file(), page)
        for aux in ("chart.mmd", "theme.json"):
            self.assertTrue((style_dir / aux).is_file(), aux)
        data = json.loads((style_dir / "slide-cover.json").read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "清爽专业风")
        self.assertEqual(data["background_color"], "#FFFFFF")
        # chart page embeds the rendered SVG (deck palette lands verbatim)
        chart = (style_dir / "slide-chart.json").read_text(encoding="utf-8")
        self.assertIn("chart_svg", chart)
        self.assertIn("<svg", json.loads(chart)["chart_svg"])

    def test_double_run_sha_deterministic(self):
        names = ["清爽专业风"]
        gallery.render_golden(thumbs_root=self.thumbs, styles=names,
                              styles_root=self.styles)
        style_dir = self.thumbs / "清爽专业风"
        for page in ("cover", "content", "chart"):
            first = gallery._sha256(style_dir / f"thumb-{page}.png")
            gallery.render_golden(thumbs_root=self.thumbs, styles=names,
                                  styles_root=self.styles)
            second = gallery._sha256(style_dir / f"thumb-{page}.png")
            self.assertEqual(first, second, f"thumb-{page} not deterministic")

    def test_check_golden_detects_thumbnail_drift(self):
        style = ["清爽专业风"]
        gallery.render_golden(thumbs_root=self.thumbs, styles=style,
                              styles_root=self.styles)
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs, styles=style,
                                        styles_root=self.styles)
        self.assertEqual(drift, 0)
        # tamper one committed thumbnail: re-render must flag the drift (R-65)
        thumb = self.thumbs / "清爽专业风" / "thumb-cover.png"
        thumb.write_bytes(thumb.read_bytes()[:-8] + b"\x00" * 8)
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs, styles=style,
                                        styles_root=self.styles)
        self.assertGreaterEqual(drift, 1)

    def test_check_golden_detects_input_drift(self):
        style = ["清爽专业风"]
        gallery.render_golden(thumbs_root=self.thumbs, styles=style,
                              styles_root=self.styles)
        committed = self.thumbs / "清爽专业风" / "slide-cover.json"
        payload = json.loads(committed.read_text(encoding="utf-8"))
        payload["subtitle"] += "（手改）"
        committed.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs, styles=style,
                                        styles_root=self.styles)
        self.assertGreaterEqual(drift, 1)

    def test_check_golden_detects_missing_thumbnail(self):
        style = ["清爽专业风"]
        gallery.render_golden(thumbs_root=self.thumbs, styles=style,
                              styles_root=self.styles)
        (self.thumbs / "清爽专业风" / "thumb-chart.png").unlink()
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs, styles=style,
                                        styles_root=self.styles)
        self.assertGreaterEqual(drift, 1)

    def test_gallery_embeds_golden_thumbs_when_present(self):
        gallery.render_golden(thumbs_root=self.thumbs, styles=["清爽专业风"],
                              styles_root=self.styles)
        builtins = gallery.builtin_styles(self.styles)
        content = gallery.render(builtins, gallery.axis_counts(self.styles),
                                 thumbs_root=self.thumbs)
        self.assertIn("## 内置风格金样板", content)
        self.assertIn("style-gallery/清爽专业风/thumb-cover.png", content)
        self.assertIn("style-gallery/清爽专业风/thumb-chart.png", content)
        self.assertEqual(len(re.findall(r"thumb-cover\.png", content)), 1)

    def test_render_golden_family_representative(self):
        # S5 representative renders through the same lane from its family
        # subdirectory brief; visibility guard keeps the cover readable
        styles_root = _family_fixture_root(self.tmp)
        gallery.render_golden(thumbs_root=self.thumbs, styles=["Dracula紫风"],
                              styles_root=styles_root)
        style_dir = self.thumbs / "Dracula紫风"
        for page in ("cover", "content", "chart"):
            self.assertTrue((style_dir / f"thumb-{page}.png").is_file(), page)
            self.assertTrue((style_dir / f"slide-{page}.json").is_file(), page)
        data = json.loads((style_dir / "slide-cover.json").read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "Dracula紫风")
        self.assertNotIn("background_color", data)
        chart = json.loads((style_dir / "slide-chart.json").read_text(encoding="utf-8"))
        self.assertIn("<svg", chart["chart_svg"])
        self.assertIn("#FF79C6", chart["chart_svg"])  # accent anchor verbatim
        drift, _ = gallery.check_golden(thumbs_root=self.thumbs,
                                        styles=["Dracula紫风"],
                                        styles_root=styles_root)
        self.assertEqual(drift, 0)


class DegradedModeTest(unittest.TestCase):
    """渲染后端缺失：降级为输入 sha 对比，不静默放弃（R-65 fallback）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-gallery-degraded-")
        self.tmp = Path(self._tmp.name)
        self.styles = _fixture_root(self.tmp)
        self.thumbs = self.tmp / "thumbs"

    def tearDown(self):
        self._tmp.cleanup()

    def test_degraded_render_writes_inputs_without_thumbs(self):
        with mock.patch.dict(os.environ, _no_backend_env()):
            self.assertIsNone(gallery.runtime_python())
            gallery.render_golden(thumbs_root=self.thumbs, styles=["清爽专业风"],
                                  styles_root=self.styles)
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
                styles_root=self.styles)
        self.assertTrue(degraded)
        self.assertEqual(drift, 0)

    def test_degraded_check_detects_input_drift(self):
        with mock.patch.dict(os.environ, _no_backend_env()):
            gallery.render_golden(thumbs_root=self.thumbs, styles=["清爽专业风"],
                                  styles_root=self.styles)
        committed = self.thumbs / "清爽专业风" / "slide-cover.json"
        payload = json.loads(committed.read_text(encoding="utf-8"))
        payload["kicker"] = "手改"
        committed.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        with mock.patch.dict(os.environ, _no_backend_env()):
            drift, degraded = gallery.check_golden(
                thumbs_root=self.thumbs, styles=["清爽专业风"],
                styles_root=self.styles)
        self.assertTrue(degraded)
        self.assertGreaterEqual(drift, 1)

    def test_degraded_family_representative_writes_inputs(self):
        styles_root = _family_fixture_root(self.tmp)
        with mock.patch.dict(os.environ, _no_backend_env()):
            gallery.render_golden(thumbs_root=self.thumbs, styles=["Dracula紫风"],
                                  styles_root=styles_root)
        style_dir = self.thumbs / "Dracula紫风"
        self.assertTrue((style_dir / "slide-cover.json").is_file())
        self.assertTrue((style_dir / "theme.json").is_file())
        self.assertFalse((style_dir / "thumb-cover.png").exists())


if __name__ == "__main__":
    unittest.main()
