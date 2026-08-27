#!/usr/bin/env python3
"""Regression tests for the factual-invariant checker."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "check_factual_invariants.py"


class FactualInvariantTests(unittest.TestCase):
    def run_checker(self, before: str, after: str, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            before_path = workdir / "before.md"
            after_path = workdir / "after.md"
            before_path.write_text(before, encoding="utf-8")
            after_path.write_text(after, encoding="utf-8")
            return subprocess.run(
                ["python3", str(SCRIPT), str(before_path), str(after_path), *args],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_reports_changed_invariants(self) -> None:
        result = self.run_checker(
            '2026 年 8 月 26 日，比例 12.5%。[报告](https://example.com/a) 使用 `E001`。「原始引语」',
            '2026 年 8 月 27 日，比例 8%。[报告](https://example.com/b) 使用 `E002`。「改写引语」',
        )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "changed")
        self.assertTrue(
            {"urls", "markdown_targets", "evidence_ids", "numbers", "inline_code", "chinese_quotes"}
            .issubset(payload["changed_categories"])
        )

    def test_reports_unchanged_text(self) -> None:
        text = '2026 年 8 月 26 日，比例 12.5%。[报告](https://example.com/a) 使用 `E001`。'
        result = self.run_checker(text, text)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "unchanged")
        self.assertEqual(payload["changed_categories"], [])

    def test_fail_on_change_is_nonzero(self) -> None:
        result = self.run_checker("比例 12.5%", "比例 8%", "--fail-on-change")
        self.assertEqual(result.returncode, 1)

    def test_curly_quote_swap_is_flagged(self) -> None:
        result = self.run_checker('他说“关键引语一”保持原样。', '他说“完全不同的引语”被替换。')
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "changed")
        self.assertIn("curly_quotes", payload["changed_categories"])

    def test_url_not_absorbing_cjk_text(self) -> None:
        result = self.run_checker(
            "数据见（https://example.com/a）在此。",
            "数据见 https://example.com/a 在此。",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "unchanged")
        self.assertEqual(payload["categories"]["urls"], {"removed": [], "added": []})

    def test_url_change_inside_cjk_prose_is_flagged(self) -> None:
        result = self.run_checker(
            "数据见（https://example.com/a）在此。",
            "数据见（https://example.com/b）在此。",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "changed")
        self.assertIn("urls", payload["changed_categories"])


if __name__ == "__main__":
    unittest.main()
