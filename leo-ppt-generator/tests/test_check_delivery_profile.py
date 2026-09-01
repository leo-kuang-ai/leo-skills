#!/usr/bin/env python3
"""check_delivery_profile.py 单测：必填字段缺失 / 未知字段 WARN / 业务数据
启发式 / 涉密默认偏好 / 合法数字字段豁免 / 读写失败 exit 2。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_delivery_profile.py"

VALID = """# delivery profile: 管理层季报
audience: 管理层（保守度：中高）
scenario: 季度经营复盘会
page_count_policy: 成品=封面1+内容10+收尾1
duration: 15 分钟
data_classification_default: 内部资料
density: 论点页为主
preferred_style: 清爽专业
"""


def _run(text=None, expect_ok=True):
    path = None
    if text is not None:
        handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        path = Path(handle.name)
    args = [sys.executable, str(SCRIPT)] + ([str(path)] if path else [])
    result = subprocess.run(args, capture_output=True, text=True)
    if expect_ok and result.returncode != 0:
        raise AssertionError(f"expected exit 0, got {result.returncode}: {result.stderr}")
    return result


class ValidProfileTest(unittest.TestCase):
    def test_valid_profile_passes_with_zero_warnings(self):
        result = _run(VALID)
        self.assertIn("OK: 7 fields valid (0 warnings)", result.stdout)


class StructuralErrorTest(unittest.TestCase):
    def test_missing_required_field_exits_2(self):
        result = _run("audience: 管理层\n", expect_ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing or empty required fields", result.stderr)
        self.assertIn("scenario", result.stderr)

    def test_empty_value_counts_as_missing(self):
        result = _run(VALID.replace("density: 论点页为主", "density:"), expect_ok=False)
        self.assertEqual(result.returncode, 2)

    def test_unreadable_file_exits_2(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "/nonexistent/profile.md"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)


class HeuristicWarningTest(unittest.TestCase):
    def test_business_number_in_audience_warns_but_passes(self):
        result = _run(VALID.replace("audience: 管理层（保守度：中高）", "audience: 营收 1.24 亿元相关管理层"))
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARN: audience:疑似业务数据", result.stdout)

    def test_secret_level_default_warns(self):
        result = _run(VALID.replace("data_classification_default: 内部资料", "data_classification_default: 机密"))
        self.assertEqual(result.returncode, 0)
        self.assertIn("涉密定级", result.stdout)

    def test_numbers_in_legit_fields_do_not_warn(self):
        result = _run(VALID)
        self.assertNotIn("WARN", result.stdout)

    def test_unknown_field_warns_but_passes(self):
        result = _run(VALID + "client_name: 某公司\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARN: unknown fields ignored: client_name", result.stdout)


class StyleSampleTest(unittest.TestCase):
    """R-20: optional style_sample text block — non-empty check, multi-line
    collection, quotation heuristics exemption, short-sample warning."""

    def test_multiline_style_sample_block_collected(self):
        profile = VALID + (
            "style_sample:\n"
            "  我们把复杂留给自己，把简单留给用户。\n"
            "  说话直接，先给结论再给理由。\n"
        )
        result = _run(profile)
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK: 8 fields valid", result.stdout)
        self.assertNotIn("WARN", result.stdout)

    def test_empty_style_sample_exits_2(self):
        result = _run(VALID + "style_sample:\n", expect_ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("style_sample present but empty", result.stderr)

    def test_short_sample_warns_but_passes(self):
        result = _run(VALID + "style_sample: 太短\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn("样本过短", result.stdout)
        self.assertIn("WARN", result.stdout)

    def test_business_numbers_inside_sample_do_not_warn(self):
        profile = VALID + (
            "style_sample:\n"
            "  原文摘录：本季度营收 1.24 亿元，同比增长 55%。\n"
        )
        result = _run(profile)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("疑似业务数据", result.stdout)


if __name__ == "__main__":
    unittest.main()
