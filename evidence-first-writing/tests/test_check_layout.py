#!/usr/bin/env python3
"""Behavioral tests for the layout contract checker (scripts/check_layout.py).

Covers the six rule families (halfwidth punctuation with CJK adjacency,
callout quota, highlight quota, bold quota, table column quota, plain
paragraph rhythm), the six protected-zone exemptions, quota boundaries,
the exit-code contract (0 clean / 1 FAIL / 2 WARN-only / 3 usage error),
the five-field finding format, and the absence of a Han guard (rules run
identically on documents that contain no Han character at all).
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "check_layout.py"


class CheckLayoutTests(unittest.TestCase):
    def run_checker(self, content: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.md"
            path.write_text(content, encoding="utf-8")
            return subprocess.run(
                ["python3", str(SCRIPT), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

    # --- Rule 1: halfwidth punctuation adjacent to CJK characters ---

    def test_halfwidth_comma_between_cjk_reports_fail(self) -> None:
        result = self.run_checker("今天,天气不错，明天更好。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | halfwidth-punct", result.stdout)

    def test_halfwidth_period_after_cjk_reports_fail(self) -> None:
        result = self.run_checker("他把话说完了.")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | halfwidth-punct", result.stdout)

    def test_halfwidth_paren_around_cjk_reports_fail(self) -> None:
        result = self.run_checker("这是(重点)内容。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | halfwidth-punct", result.stdout)

    def test_number_and_english_context_halfwidth_not_flagged(self) -> None:
        result = self.run_checker("圆周率约 3.14，共 1,000 行，时刻 12:30，参见 e.g. 示例。")
        self.assertEqual(result.returncode, 0)
        self.assertIn("未发现这份检查器覆盖的问题", result.stdout)

    def test_halfwidth_in_fenced_code_not_flagged(self) -> None:
        result = self.run_checker("正文一句。\n\n```python\nprint(1, 2)\n```\n\n结尾一句。")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("halfwidth-punct", result.stdout)

    def test_halfwidth_in_inline_code_url_link_frontmatter_not_flagged(self) -> None:
        result = self.run_checker(
            "---\ntitle: a, b: c\n---\n\n"
            "文内 `x, y` 与 https://example.com/a,b 和 [链接](http://x.com/p?q=1) 均在保护区。"
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("halfwidth-punct", result.stdout)

    # --- Rule 2: callout quota (consecutive "> " lines count as one block) ---

    def test_four_callout_blocks_pass(self) -> None:
        result = self.run_checker("> 一\n\n> 二\n\n> 三\n\n> 四\n\n正文收尾一句。")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("callout-quota", result.stdout)

    def test_five_callout_blocks_fail(self) -> None:
        result = self.run_checker("> 一\n\n> 二\n\n> 三\n\n> 四\n\n> 五\n\n正文收尾一句。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | callout-quota", result.stdout)

    def test_consecutive_quote_lines_count_as_one_block(self) -> None:
        result = self.run_checker("> 一\n> 二\n> 三\n> 四\n> 五\n\n正文收尾一句。")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("callout-quota", result.stdout)

    # --- Rule 3: highlight quota ---

    def test_five_highlights_pass(self) -> None:
        result = self.run_checker("==甲== ==乙== ==丙== ==丁== ==戊==。")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("highlight-quota", result.stdout)

    def test_six_highlights_fail(self) -> None:
        result = self.run_checker("==甲== ==乙== ==丙== ==丁== ==戊== ==己==。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | highlight-quota", result.stdout)

    def test_highlight_inside_fenced_code_not_counted(self) -> None:
        result = self.run_checker(
            "正文一句。\n\n```\n==a== ==b== ==c== ==d== ==e== ==f==\n```\n\n结尾一句。"
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("highlight-quota", result.stdout)

    # --- Rule 4: bold quota per paragraph ---

    def test_two_bold_pairs_pass(self) -> None:
        result = self.run_checker("**甲**与**乙**并列。")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("bold-quota", result.stdout)

    def test_three_bold_pairs_in_one_paragraph_fail(self) -> None:
        result = self.run_checker("**甲**、**乙**、**丙**并列。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | bold-quota", result.stdout)

    def test_triple_star_not_counted_as_bold_pair(self) -> None:
        result = self.run_checker("***甲***、***乙***、***丙***并列。")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("bold-quota", result.stdout)

    def test_bold_inside_list_marker_counts(self) -> None:
        result = self.run_checker("- **甲**\n- **乙**\n- **丙**")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | bold-quota", result.stdout)

    def test_bold_inside_fenced_code_not_counted(self) -> None:
        result = self.run_checker("正文一句。\n\n```\n**a** **b** **c**\n```\n\n结尾一句。")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("bold-quota", result.stdout)

    # --- Rule 5: table column quota ---

    def test_four_column_table_pass(self) -> None:
        result = self.run_checker(
            "| 甲 | 乙 | 丙 | 丁 |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |"
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("table-columns", result.stdout)

    def test_five_column_table_fail(self) -> None:
        result = self.run_checker(
            "| 甲 | 乙 | 丙 | 丁 | 戊 |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | table-columns", result.stdout)

    # --- Rule 6: three consecutive plain paragraphs ---

    def test_three_plain_paragraphs_warn(self) -> None:
        result = self.run_checker(
            "第一段陈述一个较长的事实。\n\n第二段陈述另一个事实。\n\n第三段陈述第三个事实。"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("WARN | paragraph-rhythm", result.stdout)
        self.assertNotIn("FAIL", result.stdout)

    def test_list_between_paragraphs_suppresses_rhythm_warning(self) -> None:
        result = self.run_checker(
            "第一段陈述一个较长的事实。\n\n- 项目一\n- 项目二\n\n第三段陈述第三个事实。"
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("paragraph-rhythm", result.stdout)

    # --- Exit-code contract and output shape ---

    def test_clean_document_exit_zero(self) -> None:
        result = self.run_checker("2026 年 8 月，李敏在杭州见张伟，聊了三个小时。")
        self.assertEqual(result.returncode, 0)

    def test_fail_dominates_warn_in_exit_code(self) -> None:
        result = self.run_checker("第一段事实。\n\n第二段事实。\n\n今天,天气不错。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | halfwidth-punct", result.stdout)
        self.assertIn("WARN | paragraph-rhythm", result.stdout)

    def test_multiple_rules_reported_together(self) -> None:
        content = (
            "今天,天气不错。\n\n"
            "==甲== ==乙== ==丙== ==丁== ==戊== ==己==\n\n"
            "**甲**、**乙**、**丙**。\n\n"
            "| a | b | c | d | e |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |"
        )
        result = self.run_checker(content)
        self.assertEqual(result.returncode, 1)
        for rule in ("halfwidth-punct", "highlight-quota", "bold-quota", "table-columns"):
            self.assertIn(rule, result.stdout)

    def test_finding_lines_use_five_field_format(self) -> None:
        result = self.run_checker("今天,天气不错。")
        lines = [line for line in result.stdout.splitlines() if line.startswith("FAIL |")]
        self.assertTrue(lines)
        self.assertEqual(len(lines[0].split(" | ")), 5)

    def test_output_has_header_and_exit_code_footer(self) -> None:
        result = self.run_checker("今天,天气不错。")
        self.assertRegex(result.stdout, r"^# ")
        self.assertIn("# 退出码：0=干净，1=存在失败级，2=仅警告级，3=输入或参数错误。", result.stdout)

    def test_missing_file_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.md"
            result = subprocess.run(
                ["python3", str(SCRIPT), str(missing)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 3)

    def test_no_arguments_exit_three(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 3)

    def test_empty_file_exit_three(self) -> None:
        result = self.run_checker("")
        self.assertEqual(result.returncode, 3)

    def test_whitespace_only_file_exit_three(self) -> None:
        result = self.run_checker(" \n\n  \n")
        self.assertEqual(result.returncode, 3)

    # --- No Han guard: rules run on documents without any Han character ---

    def test_english_document_without_han_runs_clean(self) -> None:
        result = self.run_checker(
            "Hello, world. The time is 12:30 and pi is about 3.14 (see e.g. the docs)."
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("未发现这份检查器覆盖的问题", result.stdout)

    def test_english_rhythm_still_warns_without_han(self) -> None:
        result = self.run_checker(
            "First paragraph of prose.\n\nSecond paragraph of prose.\n\nThird paragraph of prose."
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("WARN | paragraph-rhythm", result.stdout)

    def test_table_only_document_without_han_reports_columns(self) -> None:
        result = self.run_checker(
            "| a | b | c | d | e |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL | table-columns", result.stdout)


if __name__ == "__main__":
    unittest.main()


class ReviewFixRegressionTests(unittest.TestCase):
    """T003 评审修复的判别性回归（P1 围栏 callout / P3 半边框列数 / P2 三项测试缺口）。"""

    def run_checker(self, content: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.md"
            path.write_text(content, encoding="utf-8")
            return subprocess.run(
                ["python3", str(SCRIPT), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_callout_examples_inside_fenced_code_not_counted(self):
        # P1 复现场景：3 个真实 callout + 围栏内 2 个 "> " 示例行 = 修复前误判 5 块 FAIL
        text = (
            "> 真实提示一。\n\n> 真实提示二。\n\n> 真实提示三。\n\n"
            "```markdown\n> 示例行一（在围栏内）\n> 示例行二（在围栏内）\n```\n"
        )
        result = self.run_checker(text)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_halfwidth_in_html_tag_not_flagged(self):
        # 保护区六类中 HTML 标签类此前后零覆盖（评审 P2）：删 mask 分支套件应红
        text = '文内 <span data-note="注,释">标记</span>。正文无其他问题。\n'
        result = self.run_checker(text)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("halfwidth-punct", result.stdout)

    def test_quote_between_paragraphs_suppresses_rhythm_warning(self):
        # 场景③引用中断变体：三段中间夹引用块不得触发 paragraph-rhythm
        text = "第一段事实陈述。\n\n> 引用一句打断节奏。\n\n第三段事实陈述。\n"
        result = self.run_checker(text)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("paragraph-rhythm", result.stdout)

    def test_half_border_separator_counts_columns_correctly(self):
        # P3：仅首管 4 管 = 4 列（合规），修复前误报 5 列
        text = "a|b|c|d\n|---|---|---|---\n1|2|3|4\n"
        result = self.run_checker(text)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_borderless_separator_counts_columns_correctly(self):
        # 无边框 4 管 = 5 列（越限 FAIL）；pipes+1 分支此前后零覆盖
        text = "a|b|c|d|e\n---|---|---|---|---\n1|2|3|4|5\n"
        result = self.run_checker(text)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("table-columns", result.stdout)

    def test_stdin_dash_path_reads_content(self):
        import subprocess

        proc = subprocess.run(
            ["python3", str(SCRIPT), "-"],
            input="hello stdin, world\n",
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
