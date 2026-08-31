#!/usr/bin/env python3
"""Regression tests for the vendored Chinese prose-style checker."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "check_prose.py"


class CheckProseTests(unittest.TestCase):
    def run_checker(self, content: str, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.md"
            path.write_text(content, encoding="utf-8")
            return subprocess.run(
                ["python3", str(SCRIPT), str(path), *args],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_hard_stop_reports_failure_level(self) -> None:
        result = self.run_checker("说白了，这个方案就是省钱。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | hard-stop", result.stdout)

    def test_jargon_reports_failure_level(self) -> None:
        result = self.run_checker("这个平台为创作者赋能。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | jargon", result.stdout)

    def test_model_road_sign_reports_failure_level(self) -> None:
        result = self.run_checker("值得注意的是，成本并没有下降。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | model-road-sign", result.stdout)

    def test_literal_pivot_in_single_sentence(self) -> None:
        result = self.run_checker("这不是工具问题，而是流程问题。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | pivot", result.stdout)

    def test_literal_pivot_across_sentences(self) -> None:
        result = self.run_checker("他没打算解释。而是直接把东西收走了。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | pivot", result.stdout)

    def test_prompt_colon_reports_failure_level(self) -> None:
        result = self.run_checker("一句话总结：这次改动没有解决根因。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | punctuation", result.stdout)

    def test_colon_introducing_direct_quote_downgrades_to_warning(self) -> None:
        result = self.run_checker('李敏说：“我们先把数据跑一遍再定。”')
        self.assertEqual(result.returncode, 2)
        self.assertIn("WARN | quote-colon", result.stdout)
        self.assertNotIn("FAIL", result.stdout)

    def test_triple_anaphora_reported_as_warning(self) -> None:
        result = self.run_checker("我们先建了流程，我们先建了规范，我们先建了台账。")
        self.assertEqual(result.returncode, 2)
        self.assertIn("WARN | anaphora", result.stdout)

    def test_nominalization_reported_as_warning(self) -> None:
        result = self.run_checker("团队完成了对流程的优化。")
        self.assertEqual(result.returncode, 2)
        self.assertIn("WARN | nominalization", result.stdout)

    def test_uniform_sentence_rhythm_flags_low_cv(self) -> None:
        result = self.run_checker("他每天早上七点准时出门跑步锻炼。" * 14)
        self.assertEqual(result.returncode, 2)
        self.assertIn("WARN | sentence-cv", result.stdout)

    def test_conjunction_density_flagged(self) -> None:
        result = self.run_checker(
            "因为天气不好，所以我们改了计划，但是他坚持要出门，同时其他人都同意。" * 25
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("WARN | conjunction-density", result.stdout)

    def test_metaphor_fields_cluster_flagged(self) -> None:
        result = self.run_checker("行业的齿轮还在转，这条赛道的尽头还没到，蓝海的水也没退。")
        self.assertEqual(result.returncode, 2)
        self.assertIn("WARN | metaphor-cluster", result.stdout)

    def test_two_item_parallel_not_flagged(self) -> None:
        result = self.run_checker("我们建立了流程，我们建立了规范。")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("anaphora", result.stdout)
        self.assertIn("未发现这份检查器覆盖的问题", result.stdout)

    def test_concrete_text_with_names_dates_numbers_is_clean(self) -> None:
        result = self.run_checker(
            "2026 年 8 月 26 日，李敏在杭州的一家面馆见到张伟，两人聊了 3 个小时。"
            "她记得那天下着小雨，店里只有 5 桌客人。张伟临走时说，下个月会把样机寄过来。"
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("FAIL", result.stdout)
        self.assertNotIn("WARN", result.stdout)

    def test_failure_level_dominates_warning_in_exit_code(self) -> None:
        result = self.run_checker('说白了，事情定了。李敏说：“今天先到这。”')
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | hard-stop", result.stdout)
        self.assertIn("WARN | quote-colon", result.stdout)

    def test_missing_file_fails_with_exit_code_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.md"
            result = subprocess.run(
                ["python3", str(SCRIPT), str(missing)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 3)
        self.assertIn("无法读取稿件", result.stderr)

    def test_usage_error_fails_with_exit_code_three(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 3)


if __name__ == "__main__":
    unittest.main()
