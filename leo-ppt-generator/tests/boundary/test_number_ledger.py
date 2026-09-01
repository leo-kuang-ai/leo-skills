#!/usr/bin/env python3
"""check_number_ledger.py 单元测试：合规表 / 缺节 / 缺列 / 空单元格 /
非法证据等级 / 行业扩展列。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_number_ledger.py"

GOOD = """# deck 母版
## S1 封面
- 要点：营收 1.24 亿元（引用）
## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S3 | Q3 财报 | 合并报告期 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
| 37 家 | S5 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 引用 | yes | 2026-10-28 |
"""

MISSING_SECTION = """# deck 母版
## S1 封面
- 要点：无表
"""

BAD_HEADER = GOOD.replace(
    "| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |",
    "| 数值 | 页 | 来源 | 期间 |")

EMPTY_CELL = GOOD.replace(
    "| 37 家 | S5 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 引用 | yes | 2026-10-28 |",
    "| 37 家 | S5 | CRM 导出 | 新签口径 |  | 家 | 引用 | yes | 2026-10-28 |")

BAD_TIER = GOOD.replace(
    "| 37 家 | S5 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 引用 | yes | 2026-10-28 |",
    "| 37 家 | S5 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 大致 | yes | 2026-10-28 |")

INDUSTRY = """# deck 母版
## S1 封面
- 要点：缓解率（引用）
## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of | n | CI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 55% | S5 | II 期研究 | 主要终点 | 2026 | % | 引用 | yes | 2026-03 | 412 | 95% CI 51–59 |
"""


def run(content, extra=()):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as f:
        f.write(content)
        path = f.name
    r = subprocess.run([sys.executable, str(SCRIPT), path, *extra],
                       capture_output=True, text=True)
    return r.returncode, r.stderr


class NumberLedgerTest(unittest.TestCase):
    def test_good_table_passes(self):
        code, err = run(GOOD)
        self.assertEqual(code, 0, err)

    def test_missing_section_fails(self):
        code, err = run(MISSING_SECTION)
        self.assertEqual(code, 1)
        self.assertIn("缺少", err)

    def test_missing_column_fails(self):
        code, err = run(BAD_HEADER)
        self.assertEqual(code, 1)
        self.assertIn("表头缺列", err)

    def test_empty_cell_fails(self):
        code, err = run(EMPTY_CELL)
        self.assertEqual(code, 1)
        self.assertIn("为空", err)

    def test_invalid_tier_fails(self):
        code, err = run(BAD_TIER)
        self.assertEqual(code, 1)
        self.assertIn("证据等级", err)

    def test_industry_fields_pass(self):
        code, err = run(INDUSTRY, ("--industry-fields", "n,CI"))
        self.assertEqual(code, 0, err)


DIFF_OLD = """# deck 母版 v1
## S1 封面
- 要点：营收 1.24 亿元（引用）
## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S3 | Q3 财报 | 合并报告期 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
| 37 家 | S5 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 引用 | open | 2026-10-28 |
"""

DIFF_VERIFIED_KEPT = DIFF_OLD.replace(
    "| 37 家 | S5 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 引用 | open | 2026-10-28 |",
    "| 37 家 | S5 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 引用 | yes | 2026-10-28 |")

DIFF_VERIFIED_LOST = """# deck 母版 v2
## S1 封面
- 要点：要点删减
## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12 项 | S7 | 复核台账 | 复核口径 | 2026Q4 | 项 | 估算 | no | 2026-11-01 |
"""

DIFF_REVALUED = DIFF_OLD.replace("1.24 亿元", "1.31 亿元")

DIFF_ADDED = DIFF_OLD + (
    "| 12 项 | S7 | 复核台账 | 复核口径 | 2026Q4 | 项 | 估算 | no | 2026-11-01 |\n")

DIFF_DOWNGRADED = DIFF_OLD.replace(
    "| 1.24 亿元 | S3 | Q3 财报 | 合并报告期 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |",
    "| 1.24 亿元 | S3 | Q3 财报 | 合并报告期 | 2026Q3 | 人民币元 | 示意 | open | 2026-10-28 |")

# TF-1 extreme: the new master drops the whole ledger section (or empties
# the table) — every verified=yes row disappears at once.
DIFF_NEW_NO_SECTION = """# deck 母版 v2
## S1 封面
- 要点：减法删表
"""

DIFF_NEW_EMPTY_TABLE = """# deck 母版 v2
## S1 封面
- 要点：减法清空表格

## 数字登记表
"""

DIFF_OLD_NO_VERIFIED = DIFF_OLD.replace("引用 | yes", "引用 | open")

DIFF_OLD_NO_SECTION = """# deck 母版 v1
## S1 封面
- 要点：旧版本身无表
"""


def run_diff(old, new, extra=()):
    paths = []
    for content in (old, new):
        f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                        encoding="utf-8")
        f.write(content)
        f.close()
        paths.append(f.name)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--diff", *paths, *extra],
        capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


class NumberLedgerDiffTest(unittest.TestCase):
    """R-19 --diff: verified evidence must survive TF-1 subtraction."""

    def test_verified_yes_row_lost_fails_with_tf1_hint(self):
        code, out, err = run_diff(DIFF_OLD, DIFF_VERIFIED_LOST)
        self.assertEqual(code, 1)
        self.assertIn("verified?=yes 登记行在新版消失", err)
        self.assertIn("1.24 亿元", err)
        self.assertIn("TF-1", err)
        self.assertIn("显式降级", err)

    def test_verified_row_kept_and_added_row_reports_info(self):
        code, out, err = run_diff(DIFF_OLD, DIFF_ADDED)
        self.assertEqual(code, 0, err)
        self.assertIn("INFO: 新增登记行", out)
        self.assertIn("12 项", out)
        self.assertNotIn("[FAIL]", out)
        self.assertNotIn("FAIL:", err)

    def test_value_change_on_same_scope_is_info_not_fail(self):
        code, out, err = run_diff(DIFF_OLD, DIFF_REVALUED)
        self.assertEqual(code, 0, err)
        self.assertIn("INFO: 数值变化", out)
        self.assertIn("1.31 亿元", out)
        self.assertNotIn("FAIL", err)

    def test_field_downgrade_is_listed_as_info(self):
        code, out, err = run_diff(DIFF_OLD, DIFF_DOWNGRADED)
        self.assertEqual(code, 0, err)
        self.assertIn("INFO: 行变化", out)
        self.assertIn("证据等级: 引用→示意", out)

    def test_identical_ledgers_exit_clean(self):
        code, out, err = run_diff(DIFF_VERIFIED_KEPT, DIFF_VERIFIED_KEPT)
        self.assertEqual(code, 0, err)
        self.assertIn("OK: --diff 对账完成", out)
        self.assertNotIn("INFO:", out)
        self.assertNotIn("FAIL", err)

    def test_unverified_row_removal_is_info_not_fail(self):
        new = DIFF_OLD.replace(
            "| 37 家 | S5 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 引用 | open | 2026-10-28 |\n",
            "")
        code, out, err = run_diff(DIFF_OLD, new)
        self.assertEqual(code, 0, err)
        self.assertIn("INFO: 删除登记行（非 verified?=yes）", out)
        self.assertIn("37 家", out)

    def test_diff_with_missing_file_exits_2(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                        encoding="utf-8")
        f.write(DIFF_OLD)
        f.close()
        r = subprocess.run([sys.executable, str(SCRIPT), "--diff",
                            f.name, "/no/such/new-master.md"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("ERROR", r.stderr)

    def test_diff_old_master_without_section_still_exits_2(self):
        # Only the OLD side missing its ledger is a usage-grade error:
        # there is no baseline to diff against.
        code, out, err = run_diff(DIFF_OLD_NO_SECTION, DIFF_OLD)
        self.assertEqual(code, 2)
        self.assertIn("ERROR", err)
        self.assertIn("缺少", err)

    def test_diff_new_master_without_section_fails_when_verified_lost(self):
        # TF-1 extreme: the whole ledger vanished; verified=yes evidence is
        # gone and must FAIL (exit 1), not slip through as a usage error.
        code, out, err = run_diff(DIFF_OLD, DIFF_NEW_NO_SECTION)
        self.assertEqual(code, 1)
        self.assertIn("登记表整体消失", err)
        self.assertIn("显式降级", err)
        self.assertIn("TF-1", err)
        self.assertIn("1.24 亿元", err)
        # The unverified sibling row is only listed as INFO, not lost evidence.
        self.assertIn("INFO: 删除登记行（非 verified?=yes）", out)
        self.assertIn("37 家", out)

    def test_diff_new_master_with_emptied_table_fails_when_verified_lost(self):
        code, out, err = run_diff(DIFF_OLD, DIFF_NEW_EMPTY_TABLE)
        self.assertEqual(code, 1)
        self.assertIn("登记表整体消失", err)
        self.assertIn("verified?=yes 登记行在新版消失", err)

    def test_diff_new_master_without_section_passes_without_verified_rows(self):
        # No verified=yes rows in the old ledger -> no evidence lost, INFO only.
        code, out, err = run_diff(DIFF_OLD_NO_VERIFIED, DIFF_NEW_NO_SECTION)
        self.assertEqual(code, 0)
        self.assertIn("无证据损失", out)
        self.assertIn("INFO: 删除登记行（非 verified?=yes）", out)
        self.assertNotIn("FAIL", err)

    def test_single_file_mode_missing_file_exits_2(self):
        r = subprocess.run([sys.executable, str(SCRIPT),
                            "/no/such/master.md"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("ERROR", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_diff_requires_two_paths(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--diff",
                            "/no/such/old.md"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
