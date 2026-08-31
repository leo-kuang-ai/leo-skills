#!/usr/bin/env python3
"""母版机读语法 v2 行为测试：图行校验（枚举/唯一/三段/位置性标注）、
TAKEAWAY-READTHROUGH（功能页排除）、学术 deck-contract 块（缺字段 FAIL、
Σ页数失配 WARN、非学术缺块合法）、数字登记表 v2（verified? 枚举与
no+引用组合、--schema v1 迁移 WARN）。减法审计第二问为 advisory，校验器
不检查（legacy 母版不含第二问文本仍通过）。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]
MASTER_SCRIPT = PKG / "scripts" / "check_master_contract.py"
LEDGER_SCRIPT = PKG / "scripts" / "check_number_ledger.py"

GOOD_ACADEMIC = """# 学术母版
deck-contract:
  math_load: medium
  figure_orientation: figure-first
  section_priority:
    | 节 | H/M/L | 页数 |
    | --- | --- | --- |
    | 方法 | H | 1 |
    | 实验 | H | 1 |

## S1 封面
角色：开场
argument_role: 开场
- 标题：消融实验证明方法A显著优于基线
- 要点 1：方法A 在三个基准上全面领先
视觉行：要点1→巨字卡
- 备注：口播 30 秒

## S2 实验结果
角色：证据
argument_role: 论据
- 标题：方法A 以 2.3 个百分点优势胜出
- 要点 1：误差线与均值对比支持显著性结论
- 要点 2：消融设置剔除两个混杂因素
视觉行：要点1→证据图卡；要点2→对照表
图[F1] 模式:preserve 状态:vision-reviewed 焦点:消融对比的主表
承载:表2的误差线与均值 | 服务:方法A与基线的显著性比较 | 避免误读:误差线不等于统计显著性
- 备注：引用论文表 2

## S3 结论
角色：结论
argument_role: 结论
- 标题：方法A 可直接用于产线部署
- 要点 1：部署成本与收益已闭环验证
视觉行：要点1→结论条
- 备注：回扣 one_thing

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2.3pp | S2 | 论文表2 | 主指标 | 2026 | 百分点 | 引用 | yes | 2026-06 |
"""

LEGACY = """# 通用母版
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
- 备注：引用 Q3 财报

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
"""

LEDGER_V2 = """# 母版
## S1 封面
- 要点：营收 1.24 亿元（引用）
## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S3 | Q3 财报 | 合并报告期 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
"""

LEDGER_V1_LEGACY = """# 母版
## S1 封面
- 要点：营收 1.24 亿元（引用）
## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S3 | Q3 财报 | 合并报告期 | 2026Q3 | 人民币元 | 引用 |
"""


def run_script(script, content, extra=()):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as f:
        f.write(content)
        path = f.name
    r = subprocess.run([sys.executable, str(script), path, *extra],
                       capture_output=True, text=True)
    return r.returncode, r.stderr, r.stdout


class FigureRowAndTakeawayTest(unittest.TestCase):
    def test_good_master_with_figure_rows_passes(self):
        code, err, out = run_script(MASTER_SCRIPT, GOOD_ACADEMIC)
        self.assertEqual(code, 0, err)
        self.assertIn("MASTER-SCHEMA: v2", out)
        self.assertIn("TAKEAWAY-READTHROUGH:", out)

    def test_figure_row_missing_misread_segment_fails(self):
        bad = GOOD_ACADEMIC.replace(
            "承载:表2的误差线与均值 | 服务:方法A与基线的显著性比较 | "
            "避免误读:误差线不等于统计显著性",
            "承载:表2的误差线与均值 | 服务:方法A与基线的显著性比较")
        code, err, _ = run_script(MASTER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("F1", err)
        self.assertIn("避免误读", err)

    def test_figure_handling_mode_out_of_vocabulary_fails(self):
        bad = GOOD_ACADEMIC.replace("模式:preserve", "模式:crop")
        code, err, _ = run_script(MASTER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("模式", err)

    def test_duplicate_figure_id_across_pages_fails(self):
        bad = GOOD_ACADEMIC.replace(
            "视觉行：要点1→结论条",
            "视觉行：要点1→结论条\n"
            "图[F1] 模式:preserve 状态:vision-reviewed 焦点:部署收益图\n"
            "承载:部署成本曲线 | 服务:成本收益对账 | 避免误读:曲线非预测")
        code, err, _ = run_script(MASTER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("F1", err)
        self.assertIn("唯一", err)

    def test_non_vision_reviewed_figure_with_positional_annotation_fails(self):
        bad = GOOD_ACADEMIC.replace(
            "状态:vision-reviewed 焦点:消融对比的主表",
            "状态:caption-inferred 焦点:高亮右上子图的对比")
        code, err, _ = run_script(MASTER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("位置性标注", err)

    def test_legacy_master_without_figure_rows_still_passes(self):
        # 兼容旧母版：无图行、无 deck-contract、无减法审计第二问文本 → 合法
        code, err, out = run_script(MASTER_SCRIPT, LEGACY)
        self.assertEqual(code, 0, err)
        self.assertIn("MASTER-SCHEMA: v2", out)

    def test_takeaway_readthrough_excludes_functional_pages(self):
        code, err, out = run_script(MASTER_SCRIPT, GOOD_ACADEMIC)
        self.assertEqual(code, 0, err)
        line = [ln for ln in out.splitlines()
                if ln.startswith("TAKEAWAY-READTHROUGH:")][0]
        self.assertIn("误差线", line)      # S2（证据，内容页）第一条要点进连读
        self.assertIn("闭环验证", line)    # S3（结论，内容页）第一条要点进连读
        self.assertNotIn("三个基准", line)  # S1（开场，功能页）不进连读

    def test_academic_master_missing_deck_contract_fails(self):
        bad = GOOD_ACADEMIC.replace(
            "deck-contract:\n"
            "  math_load: medium\n"
            "  figure_orientation: figure-first\n"
            "  section_priority:\n"
            "    | 节 | H/M/L | 页数 |\n"
            "    | --- | --- | --- |\n"
            "    | 方法 | H | 1 |\n"
            "    | 实验 | H | 1 |\n\n",
            "")
        code, err, _ = run_script(MASTER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("deck-contract", err)

    def test_academic_master_missing_math_load_field_fails(self):
        bad = GOOD_ACADEMIC.replace("  math_load: medium\n", "")
        code, err, _ = run_script(MASTER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("math_load", err)

    def test_section_priority_sum_mismatch_warns(self):
        bad = GOOD_ACADEMIC.replace("    | 实验 | H | 1 |", "    | 实验 | H | 2 |")
        code, err, out = run_script(MASTER_SCRIPT, bad)
        self.assertEqual(code, 2, err)
        self.assertIn("WARN", err)
        self.assertIn("3", err)  # Σ=3 ≠ 内容页 2

    def test_invalid_math_load_enum_fails(self):
        bad = GOOD_ACADEMIC.replace("math_load: medium", "math_load: medium-heavy")
        code, err, _ = run_script(MASTER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("math_load", err)

    def test_ledger_verified_no_with_citation_tier_fails(self):
        bad = LEDGER_V2.replace("| 引用 | yes |", "| 引用 | no |")
        code, err, _ = run_script(LEDGER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("verified?=no", err)

    def test_ledger_verified_enum_violation_fails(self):
        bad = LEDGER_V2.replace("| 引用 | yes |", "| 引用 | maybe |")
        code, err, _ = run_script(LEDGER_SCRIPT, bad)
        self.assertEqual(code, 1)
        self.assertIn("verified?", err)

    def test_ledger_v1_schema_legacy_table_warns(self):
        code, err, out = run_script(LEDGER_SCRIPT, LEDGER_V1_LEGACY,
                                    ("--schema", "v1"))
        self.assertEqual(code, 2, err)
        self.assertIn("WARN", err)
        self.assertIn("迁移", err)
        self.assertIn("OK", out)

    def test_ledger_v2_default_rejects_legacy_seven_column_table(self):
        code, err, _ = run_script(LEDGER_SCRIPT, LEDGER_V1_LEGACY)
        self.assertEqual(code, 1)
        self.assertIn("verified?", err)


if __name__ == "__main__":
    unittest.main()
