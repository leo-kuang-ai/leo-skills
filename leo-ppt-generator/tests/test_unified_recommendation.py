"""轻量摘要与完整池共享排序，语义偏好不能被 ID 或第二次排序覆盖。"""
import sys
from pathlib import Path
import unittest

from leo_ppt_generator import layout_selection as selection
from leo_ppt_generator.page_intent import analyze_page_intent
from tests.test_deck_layout_selection import allocation_inputs, _pack_for


class UnifiedRecommendationTests(unittest.TestCase):
    def test_script_is_thin_adapter_over_runtime_ranking(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import suggest_layout
        bank = {"P1": {"page_type": "cover", "content_capacity": {}, "reuse_friendly": True}}
        page = {"page": 1, "page_role": "封面", "points": 0}
        runtime = selection.rank_page(page, bank, 1.0, {})
        script = suggest_layout.score_page(page, bank, 1.0, {})
        self.assertEqual(runtime["candidates"][:2], script["candidates"])
        self.assertEqual(runtime["intent"], script["intent"])

    def test_full_pool_top_summary_and_choice_preserve_semantic_preference(self):
        resolver, context = allocation_inputs(prefer_b=True)
        pack = _pack_for([("pg-11111111", "并列·事项", "三项独立推进", ["甲", "乙", "丙"])], decided=True)
        intent = analyze_page_intent({"semantic_structure": "independent", "points": 3})
        self.assertTrue(intent["preferred_layouts"])
        result = selection.allocate_deck(pack, context, resolver=resolver, qualification_purpose="validation",
                                         candidates=["bullets-a", "bullets-b"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["selection"]["pg-11111111"]["layout_id"], "builtin:layout:bullets-b")
        self.assertEqual(result["top2"]["pg-11111111"][0], "builtin:layout:bullets-b")

    def test_equal_rank_without_global_constraints_preserves_local_top(self):
        resolver, context = allocation_inputs(prefer_b=True)
        pack = _pack_for([("pg-11111111", "并列·事项", "三项独立推进", ["甲", "乙", "丙"])])
        result = selection.allocate_deck(pack, context, resolver=resolver, qualification_purpose="validation",
                                         candidates=["bullets-a", "bullets-b"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["selection"]["pg-11111111"]["layout_id"], result["top2"]["pg-11111111"][0])

    def test_constrained_infeasible_is_not_budget_exhausted(self):
        resolver, context = allocation_inputs()
        pack = _pack_for([("pg-11111111", "封面", "封面一", ["a"]),
                          ("pg-22222222", "封面", "封面二", ["b"])])
        result = selection.allocate_deck(pack, context, resolver=resolver, candidates=["hero"],
                                         qualification_purpose="validation")
        self.assertEqual(result["status"], "constraints_unsatisfied")

    def test_v2_undecided_is_not_promoted_by_keyword(self):
        result = analyze_page_intent({"page_role": "流程·路径", "confidence": "undecided",
                                      "semantic_structure": "undecided", "points": 3})
        self.assertEqual(result["decision"], "undecided")


if __name__ == "__main__":
    unittest.main()
