"""U11/R-75 版式重排提案行为测试。

覆盖计划场景：overflow 正负闭环（提案 → preview_apply → fits 复检通过；
未溢出页无提案）、不可行不硬凑（如实 infeasible + 替代路线）、确定性、
候选 ≤3 + 一句话代价 + 首选标注、永不自动应用与不缩字号红线。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.layout_proposals import (  # noqa: E402
    MAX_PROPOSALS,
    ProposalError,
    capacity_proposals,
    fits,
    preview_apply,
)


def _sidecar(name: str, page_type: str, *, bullets=None, title_chars=None) -> dict:
    capacity = {}
    if bullets:
        capacity["bullets"] = {"count_min": bullets[0], "count_max": bullets[1],
                               "content_type": "points"}
    if title_chars:
        capacity["title"] = {"max_chars": title_chars, "content_type": "text"}
    return {"name": name, "page_type": page_type, "content_capacity": capacity}


BANK = {
    "P1": _sidecar("Cover", "cover", title_chars=20),
    "P8": _sidecar("Compare", "content", bullets=(2, 4), title_chars=24),
    "P13": _sidecar("Cards", "content", bullets=(3, 5), title_chars=30),
    "P14": _sidecar("Grid", "content", bullets=(2, 6), title_chars=40),
}


def _overflow_page() -> dict:
    return {"page": "S7", "layout": "P8", "page_role": "content",
            "points": [f"要点{index}" for index in range(1, 7)],  # 6 > 4
            "slots": {"title": "一个远远超出二十四字宽度的标题" * 2}}


class CapacityProposalTest(unittest.TestCase):
    def test_overflow_page_gets_feasible_menu_and_closes_loop(self):
        report = capacity_proposals(page=_overflow_page(), bank=BANK)
        self.assertFalse(report["fits"])
        self.assertTrue(report["proposals"], "overflow 页必须给出 ≥1 项提案")
        # 闭环：每个提案应用后容量复检通过（switch 装下原内容；reduce 减到容量内）。
        for proposal in report["proposals"]:
            applied = preview_apply(_overflow_page(), proposal)
            self.assertTrue(fits(BANK, applied),
                            f"提案 {proposal['kind']}→{proposal.get('layout')} 应用后必须复检通过")

    def test_non_overflow_page_gets_no_proposal(self):
        page = {"page": "S1", "layout": "P8", "points": ["甲", "乙"],
                "slots": {"title": "短标题"}}
        report = capacity_proposals(page=page, bank=BANK)
        self.assertTrue(report["fits"])
        self.assertEqual(report["proposals"], [])

    def test_at_most_three_proposals_with_preferred_and_cost_line(self):
        report = capacity_proposals(page=_overflow_page(), bank=BANK)
        self.assertLessEqual(len(report["proposals"]), MAX_PROPOSALS)
        preferred = [p for p in report["proposals"] if p["preferred"]]
        self.assertEqual(len(preferred), 1, "必须恰好一个首选标注")
        self.assertEqual(preferred[0]["rank"], 1)
        for proposal in report["proposals"]:
            self.assertTrue(proposal["cost_line"].strip(), "每项必须一句话代价")
            self.assertIn("不自动应用", proposal["apply_hint"])

    def test_switch_layout_preferred_over_content_reduction(self):
        report = capacity_proposals(page=_overflow_page(), bank=BANK)
        self.assertEqual(report["proposals"][0]["kind"], "switch-layout",
                         "内容不动的换版式代价最低，应为首选")

    def test_no_font_shrinking_in_any_proposal(self):
        report = capacity_proposals(page=_overflow_page(), bank=BANK)
        for proposal in report["proposals"]:
            self.assertNotIn("字号", proposal["cost_line"])
            self.assertNotIn("缩", proposal["cost_line"].replace("缩减", ""))

    def test_deterministic_output(self):
        first = capacity_proposals(page=_overflow_page(), bank=BANK)
        second = capacity_proposals(page=_overflow_page(), bank=BANK)
        self.assertEqual(first, second)

    def test_infeasible_reported_with_alternatives_not_fabricated(self):
        # 真不可行：内容条数低于全部同型版式的 count_min（减法只会更糟，
        # 换版式也装不下）——如实 infeasible + 替代路线，不硬凑提案。
        page = {"page": "S9", "layout": "P13", "points": ["孤要点"],
                "slots": {}}
        report = capacity_proposals(page=page, bank=BANK)
        self.assertFalse(report["fits"])
        self.assertEqual(report["proposals"], [])
        self.assertIsNotNone(report["infeasible"])
        self.assertTrue(report["infeasible"]["alternatives"],
                        "不可行必须给替代路线（拆页/降密度/混合确认）")

    def test_unknown_layout_rejected(self):
        with self.assertRaises(ProposalError) as ctx:
            capacity_proposals(page={"page": "S1", "layout": "NOPE"}, bank=BANK)
        self.assertEqual(ctx.exception.reason_code, "proposal_layout_unknown")

    def test_proposal_apply_hint_never_mutates_state(self):
        page = _overflow_page()
        before = json_copy(page)
        report = capacity_proposals(page=page, bank=BANK)
        preview_apply(page, report["proposals"][0])
        self.assertEqual(page, before, "提案与预演不得改写调用方页面状态")


def json_copy(value):
    import copy

    return copy.deepcopy(value)


if __name__ == "__main__":
    unittest.main()
