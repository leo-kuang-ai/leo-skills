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


if __name__ == "__main__":
    unittest.main()
