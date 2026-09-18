#!/usr/bin/env python3
"""E2 visual_qa.py 单元测试：检查族逐条（Pillow 合成 fixture）+ CI-4 退出码。

fixture 策略（设计 §5.2-3）：空白页/满内容页/底边亮条页全部 Pillow 合成，
不依赖真实渲染输出做 QA 测试输入。"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "visual_qa.py"

_VENV = os.environ.get("LEO_PPT_TEST_VENV", "")
_PY = _VENV if _VENV and Path(_VENV).is_file() else sys.executable

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:  # pragma: no cover
    HAS_PIL = False


def _load_module():
    spec = importlib.util.spec_from_file_location("visual_qa_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blank_png(path: Path, color=(240, 240, 240), size=(2560, 1440)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def _dense_png(path: Path, size=(2560, 1440)) -> Path:
    """满内容 fixture：多色卡 + 满宽噪声带（SIZE 熵）+ 纸色安全边距（CUT 不误报）。"""
    import random

    rng = random.Random(20260831)  # 确定性噪声（fixture 可复现）
    image = Image.new("RGB", size, (250, 249, 246))
    draw = ImageDraw.Draw(image)
    step = (size[0] - 160) // 8
    palette = [(31, 33, 45), (26, 88, 96), (176, 141, 87), (58, 90, 130),
               (120, 40, 40), (40, 100, 60), (70, 60, 110), (20, 73, 92)]
    for index in range(8):
        x0 = 80 + index * step
        draw.rectangle([x0, 80, x0 + step - 16, size[1] - 120], fill=palette[index])
    noise = Image.new("RGB", (size[0] - 200, 280))
    noise.putdata(
        [
            (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
            for _ in range((size[0] - 200) * 280)
        ]
    )
    image.paste(noise, (100, 580))
    image.save(path)
    return path


def _warn_only_png(path: Path, size=(2560, 1440)) -> Path:
    """仅 WARN fixture：深底 + 噪声带（SIZE/BLANK 过）+ 底部亮条（CUT WARN）。"""
    import random

    rng = random.Random(20260831)
    image = Image.new("RGB", size, (24, 24, 28))
    noise = Image.new("RGB", (size[0], 340))
    noise.putdata(
        [
            (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
            for _ in range(size[0] * 340)
        ]
    )
    image.paste(noise, (0, 480))
    ImageDraw.Draw(image).rectangle(
        [0, size[1] - 20, size[0], size[1]], fill=(235, 235, 235)
    )
    image.save(path)
    return path


def _bottom_cutoff_png(path: Path, size=(2560, 1440)) -> Path:
    """底边截断 fixture：深底 + 底部 20 行亮带（内容触底，安全区失守）。"""
    image = Image.new("RGB", size, (24, 24, 28))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, size[1] - 20, size[0], size[1]], fill=(235, 235, 235))
    image.save(path)
    return path


@unittest.skipUnless(HAS_PIL, "Pillow 缺失，视觉 QA fixture 无法合成")
class VisualQaCheckFamily(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()

    def test_blank_png_fails_on_pixels_not_compression(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = _blank_png(Path(tmp) / "slide_01.png")
            checks = {c["id"]: c for c in self.module.run_checks(png)}
            self.assertEqual(checks["BLANK-01"]["status"], "FAIL")
            self.assertEqual(checks["SIZE-01"]["status"], "WARN")
            self.assertEqual(checks["DIM-01"]["status"], "PASS")

    def test_sparse_readable_title_is_review_hint_not_blank_failure(self):
        image = Image.new("RGB", (2560, 1440), "white")
        draw = ImageDraw.Draw(image)
        for x in range(160, 1600, 90):
            draw.rectangle((x, 120, x + 45, 210), fill="black")
        self.assertEqual(self.module.check_blank_ratio(image)["status"], "WARN")

    def test_large_island_with_zero_quadrants_warns(self):
        image = Image.new("RGB", (2560, 1440), "white")
        ImageDraw.Draw(image).rectangle((100, 100, 1150, 620), fill="black")
        result = self.module.check_design_density(image)
        self.assertEqual(result["status"], "WARN")
        self.assertIn("象限", result["msg"])

    def test_equal_luminance_color_blocks_are_not_blank(self):
        image = Image.new("RGB", (2560, 1440), (240, 40, 40))
        ImageDraw.Draw(image).rectangle((100, 100, 1150, 1300), fill=(40, 240, 40))
        self.assertEqual(self.module.check_blank_ratio(image)["status"], "PASS")

    def test_dense_fixture_passes_all_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = _dense_png(Path(tmp) / "slide_01.png")
            results = self.module.run_checks(png)
            failed = [c for c in results if c["status"] == "FAIL"]
            self.assertEqual(failed, [])

    def test_edge_cutoff_warns_not_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = _bottom_cutoff_png(Path(tmp) / "slide_01.png")
            checks = {c["id"]: c for c in self.module.run_checks(png)}
            self.assertEqual(checks["CUT-01"]["status"], "WARN")

    def test_wrong_aspect_ratio_fails_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = _blank_png(Path(tmp) / "slide_01.png", size=(2000, 1440))
            checks = {c["id"]: c for c in self.module.run_checks(png)}
            self.assertEqual(checks["DIM-01"]["status"], "FAIL")


@unittest.skipUnless(HAS_PIL, "Pillow 缺失")
class VisualQaExitCodesFollowCi4Semantics(unittest.TestCase):
    def _run(self, *argv):
        return subprocess.run([_PY, str(SCRIPT), *argv], capture_output=True, text=True)

    def test_exit_0_when_all_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dense_png(Path(tmp) / "slide_01.png")
            result = self._run(str(Path(tmp) / "slide_01.png"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exit_1_on_fail_and_json_report_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "visual-qa.json"
            _blank_png(Path(tmp) / "slide_01.png")
            result = self._run(str(Path(tmp) / "slide_01.png"), "--report", str(report))
            self.assertEqual(result.returncode, 1)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["exit_code"], 1)
            self.assertEqual(payload["summary"]["fail_pages"], ["slide_01.png"])

    def test_exit_2_when_only_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = _warn_only_png(Path(tmp) / "slide_01.png")
            result = self._run(str(png))
            self.assertEqual(result.returncode, 2, result.stdout)

    def test_directory_mode_scans_slide_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dense_png(Path(tmp) / "slide_01.png")
            _blank_png(Path(tmp) / "slide_02.png")
            result = self._run(str(Path(tmp)))
            self.assertEqual(result.returncode, 1)
            self.assertIn("slide_02.png", result.stdout)


if __name__ == "__main__":
    unittest.main()
