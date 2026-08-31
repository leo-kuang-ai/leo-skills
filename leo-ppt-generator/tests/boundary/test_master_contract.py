#!/usr/bin/env python3
"""check_master_contract.py 单元测试：合规母版 / 缺标题段 / 无落位声明 /
悬空落位引用 / 缺登记表 / 交叉引用越界 / 标题连读稿输出。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_master_contract.py"

GOOD = """# 母版
## S1 封面
argument_role: 开场
- 标题：增长质量是本季主叙事
- 要点 1：三大指标全面向好
视觉行：要点1→巨字卡
- 备注：口播 30 秒

## S2 财务
argument_role: 支柱1
- 标题：营收 1.24 亿元创单季新高
- 要点 1：环比 +18%
视觉行：要点1→KPI 塔
- 备注：引用财报

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 |
"""

NO_TITLE = GOOD.replace("- 标题：增长质量是本季主叙事\n", "")
NO_MAPPING = GOOD.replace("视觉行：要点1→巨字卡", "视觉行：巨字卡")
DANGLING = GOOD.replace("视觉行：要点1→KPI 塔", "视觉行：要点3→KPI 塔")
NO_LEDGER = GOOD.split("## 数字登记表")[0]
BAD_XREF = GOOD.replace("- 要点 1：三大指标全面向好", "- 要点 1：三大指标全面向好（见第 9 页）")


def run(content):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as f:
        f.write(content)
        path = f.name
    r = subprocess.run([sys.executable, str(SCRIPT), path],
                       capture_output=True, text=True)
    return r.returncode, r.stderr, r.stdout


class MasterContractTest(unittest.TestCase):
    def test_good_master_passes_and_outputs_readthrough(self):
        code, err, out = run(GOOD)
        self.assertEqual(code, 0, err)
        self.assertIn("TITLE-READTHROUGH:", out)
        self.assertIn("增长质量是本季主叙事", out)

    def test_missing_title_fails(self):
        code, err, _ = run(NO_TITLE)
        self.assertEqual(code, 1)
        self.assertIn("标题", err)

    def test_mapping_absent_fails(self):
        code, err, _ = run(NO_MAPPING)
        self.assertEqual(code, 1)
        self.assertIn("无点无家", err)

    def test_dangling_mapping_fails(self):
        code, err, _ = run(DANGLING)
        self.assertEqual(code, 1)
        self.assertIn("不存在要点", err)

    def test_missing_ledger_fails(self):
        code, err, _ = run(NO_LEDGER)
        self.assertEqual(code, 1)
        self.assertIn("数字登记表", err)

    def test_crossref_overflow_fails(self):
        code, err, _ = run(BAD_XREF)
        self.assertEqual(code, 1)
        self.assertIn("交叉引用", err)


if __name__ == "__main__":
    unittest.main()
