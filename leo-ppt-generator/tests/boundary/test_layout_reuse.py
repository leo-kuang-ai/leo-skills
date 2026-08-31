#!/usr/bin/env python3
"""check_layout_reuse.py（B1-T6）边界测试：P9 两次被拦、P36 尊重
max_per_deck=2、缺 layout 字段 exit 2、布局对象形态解析。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_layout_reuse.py"


def run(spec: dict) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(spec, fh, ensure_ascii=False)
        fh.flush()
        return subprocess.run(
            [sys.executable, str(SCRIPT), fh.name],
            capture_output=True, text=True,
        )


class LayoutReuseTests(unittest.TestCase):
    def test_rejects_strong_visual_layout_used_twice(self):
        proc = run({"slides": [
            {"page": 5, "layout": "P9"},
            {"page": 12, "layout": {"layout_name": "P9 · Closing Manifesto"}},
        ]})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("P9", proc.stdout)
        self.assertIn("5", proc.stdout)  # 列出页号
        self.assertIn("12", proc.stdout)

    def test_allows_single_use_of_strong_visual_layout(self):
        proc = run({"slides": [
            {"page": 1, "layout": "P1"},
            {"page": 9, "layout": "P9"},
            {"page": 6, "layout": "P4"},  # reuse_friendly 版式不受限
        ]})
        self.assertEqual(proc.returncode, 0)

    def test_allows_ambience_up_to_max_per_deck(self):
        twice = run({"slides": [
            {"page": 2, "layout": "P36"}, {"page": 8, "layout": "P36"},
        ]})
        self.assertEqual(twice.returncode, 0)  # P36 max_per_deck=2
        thrice = run({"slides": [
            {"page": 2, "layout": "P36"}, {"page": 8, "layout": "P36"},
            {"page": 9, "layout": "P36"},
        ]})
        self.assertEqual(thrice.returncode, 1)
        self.assertIn("上限 2", thrice.stdout)

    def test_usage_error_exit_two_on_missing_layout_field(self):
        proc = run({"slides": [{"page": 1, "title": "无版式列"}]})
        self.assertEqual(proc.returncode, 2)

    def test_missing_file_exit_two(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "/nonexistent-deck.json"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
