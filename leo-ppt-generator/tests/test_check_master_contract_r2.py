#!/usr/bin/env python3
"""check_master_contract.py R2 迭代判据单测：⑪ 反方承载 / ⑫ 收束金额测算行。

两个新判据均为 WARN 级（向后兼容）；直接单测 helper 函数（完整 main() 依赖
四段完备等结构，最小夹具无法独立过全检）。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_master_contract as cmc  # noqa: E402


PAGES_WITH_BOUNDARY = [(
    "S1 边界（页面角色：边界；argument_role：反方）",
    "- 标题：反方与失效\n- 反方一：替代解释A\n")]
PAGES_WITHOUT = [(
    "S1 证据（页面角色：证据；argument_role：论据）",
    "- 标题：证据一\n- 登记表核对通过\n")]
PAGES_TITLE_ONLY = [(
    "S1 证据（页面角色：证据）",
    "- 标题：判断、反方与失效线\n- speaker_script：口头讲反方\n")]


class CounterCarriageTest(unittest.TestCase):
    def test_boundary_page_present_no_warn(self):
        w = []
        cmc.check_counter_carriage(PAGES_WITH_BOUNDARY, w)
        self.assertEqual(w, [])

    def test_counter_point_present_no_warn(self):
        w = []
        cmc.check_counter_carriage([(
            "S2 方案（页面角色：方案）",
            "- 标题：方案\n- 失效触发：转化低于阈值即回滚\n")], w)
        self.assertEqual(w, [])

    def test_absent_carriage_warns(self):
        w = []
        cmc.check_counter_carriage(PAGES_WITHOUT, w)
        self.assertTrue(w and "反方/边界承载" in w[0])

    def test_title_mention_alone_does_not_count(self):
        # R2 校准 C1 教训：标题/口播提及 ≠ 实质承载。
        w = []
        cmc.check_counter_carriage(PAGES_TITLE_ONLY, w)
        self.assertTrue(w and "反方/边界承载" in w[0])


LEDGER = """## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1499 | S2 | 本轮测算 | 测算：BOM520+返点330+询价中安装 | 方案 | 元 | 估算 | no | — |
| 1599 | S2 | 来源A | 实验组标价 | 2026-08 | 元 | 引用 | yes | 2026-08-30 |
"""
CLOSING_WITH_AMOUNT = [(
    "S3 收束（页面角色：收束）",
    "- 标题：请批\n- 决策：套组试点 ¥1,499 与守价 ¥1,599\n")]
CLOSING_WITH_UNKNOWN = [(
    "S3 收束（页面角色：收束）",
    "- 标题：请批\n- 决策：追加预算 ¥0.9M（unknown，两周内补测算）\n")]
CLOSING_NO_AMOUNT = [(
    "S3 收束（页面角色：收束）",
    "- 标题：请批\n- 决策：立项与排期\n")]


class ClosingAmountTest(unittest.TestCase):
    def test_derived_row_covers_amount(self):
        w = []
        cmc.check_closing_amounts(LEDGER, CLOSING_WITH_AMOUNT, w)
        # 1499 有测算行；1599 的口径列无测算标记 → 仅 1599 报
        self.assertEqual(len(w), 1)
        self.assertIn("「¥1,599」", w[0])
        self.assertNotIn("「¥1,499」", w[0])

    def test_evidence_level_reference_is_not_a_marker(self):
        # 词表碰撞回归：1599 行证据等级列为「引用」，不得当作测算标记。
        w = []
        cmc.check_closing_amounts(LEDGER, CLOSING_WITH_AMOUNT, w)
        self.assertTrue(w)  # 1599 仍应报

    def test_inline_unknown_exempts(self):
        w = []
        cmc.check_closing_amounts(LEDGER, CLOSING_WITH_UNKNOWN, w)
        self.assertEqual(w, [])

    def test_no_amounts_no_warn(self):
        w = []
        cmc.check_closing_amounts(LEDGER, CLOSING_NO_AMOUNT, w)
        self.assertEqual(w, [])

    def test_thousand_separator_amount_matches_row(self):
        ledger = LEDGER.replace("| 1499 |", "| 1,499 |")
        w = []
        cmc.check_closing_amounts(
            ledger,
            [("S3 收束（页面角色：收束）",
              "- 标题：请批\n- 决策：套组试点 ¥1,499\n")], w)
        self.assertEqual(w, [])


if __name__ == "__main__":
    unittest.main()
