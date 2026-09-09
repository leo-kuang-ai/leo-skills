#!/usr/bin/env python3
"""check_master_contract.py 单元测试：合规母版 / 缺标题段 / 无落位声明 /
悬空落位引用 / 缺登记表 / 交叉引用越界 / 标题连读稿输出；
deck-promises 承诺表判据（R-34）：兑现通过 / 伪造目录多宣称一章 FAIL /
无承诺表静默跳过 / 锚页不存在 FAIL / 状态 closed 豁免 / open 缺兑现页
FAIL / 非法状态 FAIL / 确定性；
要点级四级标注与 source_ref 判据（R-08/R-09）：引用级缺 source_ref FAIL /
行尾 [src:] 等价合法 / 用户确认级 round·note 合法而缺失 FAIL / 估算示意豁免 /
无标注向后兼容 / 承诺判据并存回归 / 确定性。"""
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

## S3 边界
argument_role: 反方
页面角色：边界
- 标题：最强反方与失效线
- 要点 1：反方——增长或含一次性因素，失效触发：增速回落即重议
视觉行：要点1→对照条
- 备注：边界页

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

    def test_same_unit_relation_is_a_hard_failure(self):
        split = GOOD.replace(
            "argument_role: 支柱1\n- 标题：营收",
            "argument_role: 支柱1\nrst_relation: same-unit\n- 标题：营收")
        code, err, _ = run(split)
        self.assertEqual(code, 1)
        self.assertIn("same-unit", err)


# --- deck-promises 承诺表判据（R-34） ---

PROMISES_GOOD = """# 母版
deck-promises:
  | 承诺 | 锚页 | 兑现页 | 状态 |
  | --- | --- | --- | --- |
  | 方法章给出消融实验 | S2 | S3 | open |
  | 附录给出数据字典 | S2 | 附 | fulfilled |
  | 竞品对比已裁剪 | S2 | — | closed |

## S1 封面
argument_role: 开场
- 标题：增长质量是本季主叙事
- 要点 1：三大指标全面向好
视觉行：要点1→巨字卡
- 备注：口播 30 秒

## S2 目录
页面角色：目录
argument_role: 组织
- 标题：本季三章主线
- 要点 1：三章承诺清单
视觉行：要点1→目录卡
- 备注：口播 10 秒

## S3 方法
页面角色：边界
argument_role: 反方
- 标题：反方与失效线
- 要点 1：反方——消融或含数据泄漏，失效触发：复检置信区间覆盖零即重议
视觉行：要点1→对照条
- 备注：边界页

## S3 方法
argument_role: 论据
- 标题：消融实验证明结构有效
- 要点 1：三项消融全部显著
视觉行：要点1→对比表
- 备注：引用实验记录

## 附 数据字典
argument_role: 附录
- 标题：字段口径一览
- 要点 1：18 个字段全部登记
视觉行：要点1→附录表
- 备注：备查

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 18 个 | 附 | 数据字典 | 全量 | 2026Q3 | 个 | 引用 |
"""


class MasterContractPromisesTest(unittest.TestCase):
    def test_fulfilled_promises_pass_with_count(self):
        code, err, out = run(PROMISES_GOOD)
        self.assertEqual(code, 0, err)
        self.assertIn("承诺表 3 条核对通过", out)

    def test_fabricated_agenda_chapter_fails(self):
        # 目录页多宣称一章：承诺表为第五章登记 open，兑现页 S9 不存在
        bad = PROMISES_GOOD.replace(
            "  | 承诺 | 锚页 | 兑现页 | 状态 |\n  | --- | --- | --- | --- |\n"
            "  | 方法章给出消融实验 | S2 | S3 | open |",
            "  | 承诺 | 锚页 | 兑现页 | 状态 |\n  | --- | --- | --- | --- |\n"
            "  | 方法章给出消融实验 | S2 | S3 | open |\n"
            "  | 第五章给出路线图 | S2 | S9 | open |")
        code, err, _ = run(bad)
        self.assertEqual(code, 1)
        self.assertIn("兑现页「S9」不存在", err)

    def test_legacy_master_without_promises_table_skips_silently(self):
        # 旧母版（含目录页型但无承诺表）：本判据静默跳过，不 FAIL 不 WARN
        legacy_toc = GOOD.replace(
            "## S1 封面\nargument_role: 开场",
            "## S1 封面\nargument_role: 开场\n页面角色：开场")
        legacy_toc = legacy_toc.replace(
            "## S2 财务\nargument_role: 支柱1",
            "## S2 财务\nargument_role: 支柱1\n页面角色：目录")
        code, err, out = run(legacy_toc)
        self.assertEqual(code, 0, err)
        self.assertNotIn("承诺表", out)
        self.assertNotIn("承诺", err)

    def test_missing_anchor_page_fails(self):
        bad = PROMISES_GOOD.replace(
            "| 方法章给出消融实验 | S2 | S3 | open |",
            "| 方法章给出消融实验 | S12 | S3 | open |")
        code, err, _ = run(bad)
        self.assertEqual(code, 1)
        self.assertIn("锚页「S12」不存在", err)

    def test_closed_status_is_exempt_from_payoff_check(self):
        exempt = PROMISES_GOOD.replace(
            "| 竞品对比已裁剪 | S2 | — | closed |",
            "| 竞品对比已裁剪 | S99 | — | closed |")
        code, err, _ = run(exempt)
        self.assertEqual(code, 0, err)

    def test_open_promise_without_payoff_page_fails(self):
        bad = PROMISES_GOOD.replace(
            "| 方法章给出消融实验 | S2 | S3 | open |",
            "| 方法章给出消融实验 | S2 |  | open |")
        code, err, _ = run(bad)
        self.assertEqual(code, 1)
        self.assertIn("缺兑现页", err)

    def test_invalid_status_fails(self):
        bad = PROMISES_GOOD.replace(
            "| 附录给出数据字典 | S2 | 附 | fulfilled |",
            "| 附录给出数据字典 | S2 | 附 | pending |")
        code, err, _ = run(bad)
        self.assertEqual(code, 1)
        self.assertIn("不在封闭枚举", err)

    def test_promise_check_is_deterministic(self):
        runs = [run(PROMISES_GOOD) for _ in range(2)]
        self.assertEqual(runs[0], runs[1])


# --- 要点级四级标注与 source_ref 判据（R-08 / R-09） ---

TIERS = """# 母版
## S1 封面
argument_role: 开场
- 标题：增长质量是本季主叙事
- 要点 1：营收 1.24 亿元【引用|src:Q3财报§2】
视觉行：要点1→巨字卡
- 备注：口播 30 秒

## S2 财务
argument_role: 支柱1
- 标题：明年目标锚定新台阶
- 要点 1：用户口述目标【用户确认|round:3】
- 要点 2：利润 3500 万元（估算）
- 要点 3：行业格局（示意）
视觉行：要点1→KPI 塔；要点2→对照表
- 备注：引用财报

## S3 边界
argument_role: 反方
页面角色：边界
- 标题：最强反方与失效线
- 要点 1：反方——增长或含一次性因素，失效触发：增速回落即重议
视觉行：要点1→对照条
- 备注：边界页

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 |
"""


class MasterContractTierTest(unittest.TestCase):
    def test_citation_with_pipe_src_and_exemptions_pass(self):
        # 引用级带 source_ref、用户确认级带 round、估算/示意无 src 豁免
        code, err, out = run(TIERS)
        self.assertEqual(code, 0, err)
        self.assertIn("要点标注 4 条核对通过", out)
        self.assertNotIn("source_ref", err)

    def test_citation_without_source_ref_fails(self):
        bad = TIERS.replace("【引用|src:Q3财报§2】", "（引用）")
        code, err, _ = run(bad)
        self.assertEqual(code, 1)
        self.assertIn("缺 source_ref", err)

    def test_trailing_square_src_is_accepted(self):
        ok = TIERS.replace("【引用|src:Q3财报§2】", "（引用）[src:Q3财报]")
        code, err, _ = run(ok)
        self.assertEqual(code, 0, err)

    def test_user_confirmed_with_bare_round_marker_passes(self):
        ok = TIERS.replace("【用户确认|round:3】", "（用户确认）round:3")
        code, err, _ = run(ok)
        self.assertEqual(code, 0, err)

    def test_user_confirmed_with_note_field_passes(self):
        ok = TIERS.replace("【用户确认|round:3】",
                           "（用户确认）[note:用户口述明年目标]")
        code, err, _ = run(ok)
        self.assertEqual(code, 0, err)
        ok2 = TIERS.replace("【用户确认|round:3】",
                            "（用户确认）说明:口径为用户口述")
        code2, err2, _ = run(ok2)
        self.assertEqual(code2, 0, err2)

    def test_user_confirmed_without_round_or_note_fails(self):
        bad = TIERS.replace("【用户确认|round:3】", "（用户确认）")
        code, err, _ = run(bad)
        self.assertEqual(code, 1)
        self.assertIn("会话轮标记", err)

    def test_unmarked_bullets_are_not_checked(self):
        # 向后兼容：无标注要点的旧母版不触发本判据、不输出标注计数
        code, err, out = run(GOOD)
        self.assertEqual(code, 0, err)
        self.assertNotIn("要点标注", out)

    def test_promises_criterion_unaffected_by_tier_check(self):
        # 承诺判据回归：同一母版两个判据并存，各自计数互不干扰
        both = PROMISES_GOOD.replace(
            "- 要点 1：三项消融全部显著",
            "- 要点 1：三项消融全部显著【引用|src:实验记录§4】")
        code, err, out = run(both)
        self.assertEqual(code, 0, err)
        self.assertIn("承诺表 3 条核对通过", out)
        self.assertIn("要点标注 1 条核对通过", out)

    def test_tier_check_is_deterministic(self):
        runs = [run(TIERS) for _ in range(2)]
        self.assertEqual(runs[0], runs[1])


if __name__ == "__main__":
    unittest.main()
