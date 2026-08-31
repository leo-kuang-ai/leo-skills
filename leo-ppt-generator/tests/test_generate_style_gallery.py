#!/usr/bin/env python3
"""generate_style_gallery.py 单测：确定性生成 / --check 漂移守卫 / 内置 11 套在场。"""
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_style_gallery.py"
GALLERY = Path(__file__).resolve().parents[1] / "samples" / "style-gallery.md"


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args, capture_output=True, text=True
    )


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


if __name__ == "__main__":
    unittest.main()
