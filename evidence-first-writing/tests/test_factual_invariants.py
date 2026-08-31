#!/usr/bin/env python3
"""Regression tests for the factual-invariant checker."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "check_factual_invariants.py"

HASH_LINE = re.compile(r"^invariant_hash: before=([0-9a-f]{64}) after=([0-9a-f]{64})$")


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

    def parse_output(self, result: subprocess.CompletedProcess[str]):
        """stdout 首行是 invariant_hash 行，其余行是 JSON 报告。"""
        lines = result.stdout.splitlines()
        hash_match = HASH_LINE.match(lines[0])
        payload = json.loads("\n".join(lines[1:]))
        return hash_match, payload

    def test_reports_changed_invariants(self) -> None:
        result = self.run_checker(
            '2026 年 8 月 26 日，比例 12.5%。[报告](https://example.com/a) 使用 `E001`。「原始引语」',
            '2026 年 8 月 27 日，比例 8%。[报告](https://example.com/b) 使用 `E002`。「改写引语」',
        )
        payload = self.parse_output(result)[1]
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "changed")
        self.assertTrue(
            {"urls", "markdown_targets", "evidence_ids", "numbers", "inline_code", "chinese_quotes"}
            .issubset(payload["changed_categories"])
        )

    def test_reports_unchanged_text(self) -> None:
        text = '2026 年 8 月 26 日，比例 12.5%。[报告](https://example.com/a) 使用 `E001`。'
        result = self.run_checker(text, text)
        payload = self.parse_output(result)[1]
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "unchanged")
        self.assertEqual(payload["changed_categories"], [])

    def test_fail_on_change_is_nonzero(self) -> None:
        result = self.run_checker("比例 12.5%", "比例 8%", "--fail-on-change")
        self.assertEqual(result.returncode, 1)

    def test_curly_quote_swap_is_flagged(self) -> None:
        result = self.run_checker('他说“关键引语一”保持原样。', '他说“完全不同的引语”被替换。')
        payload = self.parse_output(result)[1]
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "changed")
        self.assertIn("curly_quotes", payload["changed_categories"])

    def test_url_not_absorbing_cjk_text(self) -> None:
        result = self.run_checker(
            "数据见（https://example.com/a）在此。",
            "数据见 https://example.com/a 在此。",
        )
        payload = self.parse_output(result)[1]
        self.assertEqual(payload["status"], "unchanged")
        self.assertEqual(payload["categories"]["urls"], {"removed": [], "added": []})

    def test_url_change_inside_cjk_prose_is_flagged(self) -> None:
        result = self.run_checker(
            "数据见（https://example.com/a）在此。",
            "数据见（https://example.com/b）在此。",
        )
        payload = self.parse_output(result)[1]
        self.assertEqual(payload["status"], "changed")
        self.assertIn("urls", payload["changed_categories"])

    def test_hash_line_reports_sha256_of_inputs(self) -> None:
        before = "比例 12.5%"
        after = "比例 8%"
        result = self.run_checker(before, after)
        hash_match, _ = self.parse_output(result)
        self.assertIsNotNone(hash_match)
        assert hash_match is not None
        self.assertEqual(hash_match.group(1), hashlib.sha256(before.encode("utf-8")).hexdigest())
        self.assertEqual(hash_match.group(2), hashlib.sha256(after.encode("utf-8")).hexdigest())

    def test_hash_stable_across_runs(self) -> None:
        text = "2026 年 8 月 26 日，比例 12.5%。"
        first = self.run_checker(text, text)
        second = self.run_checker(text, text)
        hash_match, _ = self.parse_output(first)
        self.assertIsNotNone(hash_match)
        self.assertEqual(
            first.stdout.splitlines()[0], second.stdout.splitlines()[0]
        )

    def test_single_char_edit_changes_after_hash_only(self) -> None:
        before = "比例 12.5%"
        edited = "比例 12.6%"
        identical = self.run_checker(before, before)
        changed = self.run_checker(before, edited)
        identical_match, _ = self.parse_output(identical)
        changed_match, changed_payload = self.parse_output(changed)
        assert identical_match is not None and changed_match is not None
        self.assertEqual(identical_match.group(1), changed_match.group(1))
        self.assertNotEqual(identical_match.group(2), changed_match.group(2))
        self.assertEqual(changed_payload["status"], "changed")


if __name__ == "__main__":
    unittest.main()
