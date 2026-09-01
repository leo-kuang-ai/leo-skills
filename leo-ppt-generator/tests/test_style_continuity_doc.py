#!/usr/bin/env python3
"""style-continuity.md 文档合同测试（机制线 M1）：跨页继承字段清单、
原图嵌入二选一政策、默认 preserve、伪图禁令、学术六模式衔接防漂移。"""
import unittest
from pathlib import Path

DOC = (
    Path(__file__).resolve().parents[1]
    / "references" / "style-continuity.md"
)
LINE_BUDGET = 32


class StyleContinuityDocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = DOC.read_text(encoding="utf-8")

    def test_doc_exists_and_within_line_budget(self):
        self.assertTrue(DOC.exists())
        self.assertLessEqual(len(self.content.splitlines()), LINE_BUDGET)

    def test_inheritance_field_checklist_present(self):
        # Confirmed sample becomes the deck-wide visual master: the six-field
        # inheritance checklist must stay enumerable, not free prose.
        for fragment in (
            "## 继承合同",
            "色彩 token 面",
            "图片处理",
            "边框与线重",
            "排版层级",
            "装饰语汇",
            "栅格与密度",
            "不发明新视觉模板",
        ):
            self.assertIn(fragment, self.content)

    def test_two_page_master_baseline_declared(self):
        # Slide 2 inherits slide 1; slides 3+ inherit the 1-2 page pair.
        self.assertIn("第 2 页继承第 1 页", self.content)
        self.assertIn("第 1–2 页为双页母版基准", self.content)

    def test_asset_policy_is_exclusive_pair_with_default(self):
        # Asset embedding must be a declared either/or policy, defaulting to
        # fidelity-preserving embed.
        self.assertIn("`preserve`（默认）", self.content)
        self.assertIn("`stylize`", self.content)
        self.assertIn("二选一", self.content)

    def test_fidelity_hard_rules_present(self):
        for fragment in (
            "不重画",
            "不替换相似伪图",
            "不改变原图内容",
            "须留原图引用",
        ):
            self.assertIn(fragment, self.content)

    def test_figure_usage_discipline_present(self):
        # Figures are evidence, not decoration; no cover-sized user figures.
        for fragment in (
            "figure 是证据不是装饰",
            "最多两页",
            "封面默认不放",
        ):
            self.assertIn(fragment, self.content)

    def test_delegates_to_academic_figure_evidence(self):
        # The policy is a master switch only; the six academic figure modes
        # stay owned by academic-figure-evidence.md.
        self.assertIn("academic-figure-evidence.md", self.content)
        self.assertIn("不改其封闭枚举", self.content)


if __name__ == "__main__":
    unittest.main()
