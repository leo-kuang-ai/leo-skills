"""轻量摘要与完整池共享排序，语义偏好不能被 ID 或第二次排序覆盖。"""
import sys
from copy import deepcopy
from pathlib import Path
import unittest

from leo_ppt_generator import layout_selection as selection
from leo_ppt_generator.page_intent import analyze_page_intent
from tests.test_deck_layout_selection import allocation_inputs, _pack_for
from tests.test_chapter_content_model import compile_text, master
from tests.test_page_expression_contract import content, declaration
from leo_ppt_generator.content_pack import compile_page_expression


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
        pool = selection.qualified_pool(pack["pages"][0], context, content_digest=pack["content_digest"],
            numbers=pack["numbers"], resolver=resolver, qualification_purpose="validation",
            candidates=["bullets-a", "bullets-b"])
        for candidate in pool["qualified"]:
            readings = candidate["binding"]["eligibility"]["checks"].get("text_capacity", {})
            self.assertEqual(any(reason.startswith("逐槽容量") for reason in candidate["ranking"]["reasons"]),
                             bool(readings))

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

    def test_frozen_expression_relation_drives_semantic_preference(self):
        page = compile_text(master().replace('"semantic_structure": "comparison"',
                                             '"semantic_structure": "undecided"'))["pages"][1]
        signals = selection.page_rank_signals(page)
        self.assertEqual(signals["semantic_structure"], "comparison")
        bank = {
            "compare": {"aliases": ["compare"], "page_type": "content", "content_capacity": {},
                        "reuse_friendly": True, "renderer_support": {"render:html": "template"}},
            "plain": {"aliases": ["plain"], "page_type": "content", "content_capacity": {},
                      "reuse_friendly": True, "renderer_support": {"render:html": "template"}},
        }
        report = selection.rank_page(signals, bank, 1.0, {}, "render:html", hard_qualified=True)
        self.assertEqual(report["candidates"][0]["layout"], "compare")
        self.assertTrue(any(reason.startswith("冻结表达: relation=comparison")
                            for reason in report["candidates"][0]["reasons"]))

    def test_continuous_task_reuses_structure_without_artificial_alternation(self):
        resolver, context = allocation_inputs()
        pack = _pack_for([
            ("pg-11111111", "并列·事项", "学习第一组词汇", ["甲", "乙", "丙"]),
            ("pg-22222222", "并列·事项", "学习第二组词汇", ["丁", "戊", "己"]),
        ], decided=True)
        result = selection.allocate_deck(pack, context, resolver=resolver,
            qualification_purpose="validation", candidates=["bullets-a", "bullets-b"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["selection"]["pg-11111111"]["layout_id"],
                         result["selection"]["pg-22222222"]["layout_id"])
        self.assertEqual(result["page_status"]["pg-22222222"]["rhythm_context"],
                         "continuous-reading-task")
        self.assertEqual(result["page_status"]["pg-22222222"]["score_margin"], 0)

    def test_compiled_process_and_causal_relations_override_misleading_role(self):
        for kind in ("process", "causal"):
            with self.subTest(kind=kind):
                pack = content()
                page = pack["pages"][0]
                page.update(semantic_structure="undecided", narrative_role="并列·事项", confidence="decided")
                page["expression"] = compile_page_expression(pack, page["page_id"], **declaration(kind))
                signals = selection.page_rank_signals(page)
                self.assertEqual(signals["semantic_structure"], kind)
                self.assertEqual(selection.rank_page(signals, {}, 1.0, {})["intent"]["page_type"], kind)

    def test_expression_uncertainty_keeps_manual_decision(self):
        page = compile_text(master().replace('"uncertainty": []',
                                             '"uncertainty": ["耗时待核对"]'))["pages"][1]
        self.assertEqual(page["confidence"], "medium")
        signals = selection.page_rank_signals(page)
        report = selection.rank_page(signals, {"compare": {"page_type": "content", "content_capacity": {},
                                                       "reuse_friendly": True}}, 1.0, {})
        self.assertEqual(report["decision"], "undecided")
        self.assertIn("冻结表达仍有待确认项，需人工裁决", report["decision_reasons"])

    def test_chapter_change_or_core_claim_keeps_rhythm_penalty(self):
        first = _pack_for([("pg-11111111", "并列·事项", "词汇", ["甲", "乙"])],
                          decided=True)["pages"][0]
        second = deepcopy(first)
        self.assertTrue(selection._same_reading_context(first, second))
        second["chapter_id"] = "ch-next"
        self.assertFalse(selection._same_reading_context(first, second))
        second = deepcopy(first)
        second["argument_role"] = "论点"
        self.assertFalse(selection._same_reading_context(first, second))
        second = deepcopy(first)
        second["expression"]["uncertainty"] = ["任务尚待确认"]
        self.assertFalse(selection._same_reading_context(first, second))

    def test_binding_slot_capacity_breaks_equal_total_capacity_tie(self):
        page = {"page_role": "并列·事项", "points": 3, "est_chars": 30,
                "binding_text_capacity": {
                    "tight": {"title": {"used": 42, "limit": 40, "level": "over"}},
                    "roomy": {"title": {"used": 18, "limit": 40, "level": "ok"}},
                }}
        bank = {
            name: {"page_type": "content", "content_capacity": {"bullets": {"count_min": 1, "count_max": 6}},
                   "reuse_friendly": True, "renderer_support": {"render:html": "template"}}
            for name in ("tight", "roomy")
        }
        report = selection.rank_page(page, bank, 1.0, {}, "render:html", hard_qualified=True)
        self.assertEqual(report["candidates"][0]["layout"], "roomy")
        self.assertIn("逐槽容量余量: title 18/40", report["candidates"][0]["reasons"])

    def test_real_title_binding_readings_distinguish_long_title_from_short_title(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.templates import resolve_design_context
        from leo_ppt_generator.content_projection import precompile_binding
        resolver = AssetResolver()
        context = resolve_design_context("clean-professional", resolver=resolver)
        observations = []
        for title in ("短标题", "题" * 39):
            pack = _pack_for([("pg-11111111", "封面", title, ["短要点"])])
            binding = precompile_binding(pack["pages"][0], context, "P1",
                content_digest=pack["content_digest"], numbers=pack["numbers"], resolver=resolver)
            readings = binding["eligibility"]["checks"]["text_capacity"]
            self.assertEqual(readings["title"]["used"], len(title))
            fit, reasons = selection._binding_capacity_fit({"binding_text_capacity": {"P1": readings}}, "P1")
            observations.append(fit)
            self.assertTrue(any("title" in reason or "kicker" in reason for reason in reasons))
            # 只验证真实编译摘要，不将缺资格的资产当作生产候选。
        self.assertGreater(observations[0], observations[1])

    def test_explicit_specific_page_type_is_not_erased_by_general_reading_task(self):
        pack = content()
        page = pack["pages"][0]
        page.update(semantic_structure="system", narrative_role="关系·网络", confidence="medium")
        page["expression"] = compile_page_expression(pack, page["page_id"], **declaration("causal"))
        signals = selection.page_rank_signals(page)
        self.assertEqual(signals["semantic_structure"], "system")
        self.assertEqual(signals["expression_evidence"]["reading_task"], "causal")

    def test_close_candidates_are_marked_undecided_with_margin(self):
        page = {"page_role": "并列·事项", "points": 3}
        bank = {
            name: {"page_type": "content", "content_capacity": {}, "reuse_friendly": True,
                   "renderer_support": {"render:html": "template"}}
            for name in ("a", "b")
        }
        report = selection.rank_page(page, bank, 1.0, {"a": 0.30, "b": 0.29}, "render:html")
        self.assertEqual(report["decision"], "undecided")
        self.assertLess(report["score_margin"], selection.SCORE_MARGIN_FLOOR)
        self.assertIn("前两候选分差不足，需人工裁决", report["decision_reasons"])

    def test_margin_uses_unsaturated_scores_and_clear_preference_stays_auto(self):
        page = {"page_role": "并列·事项", "points": 3}
        bank = {name: {"page_type": "content", "content_capacity": {}, "reuse_friendly": True}
                for name in ("a", "b")}
        report = selection.rank_page(page, bank, 1.0, {"a": 0.6, "b": 0.5})
        self.assertEqual([c["score"] for c in report["candidates"]], [1.0, 1.0])
        self.assertAlmostEqual(report["score_margin"], 0.1)
        self.assertEqual(report["decision"], "auto")

    def test_slot_readings_apply_to_both_lanes_and_missing_is_neutral(self):
        page = {"page_role": "并列·事项", "points": 3, "est_chars": 40,
                "binding_text_capacity": {
                    "a": {"title": {"used": 40, "limit": 40, "level": "ok"}},
                    "b": {"title": {"used": 20, "limit": 40, "level": "ok"}}}}
        bank = {name: {"page_type": "content", "content_capacity": {}, "reuse_friendly": True,
                       "renderer_support": {"image": "recipe", "render:html": "template"}}
                for name in ("a", "b")}
        for lane in ("image", "render:html"):
            with self.subTest(lane=lane):
                report = selection.rank_page(page, bank, 1.0, {}, lane, hard_qualified=True)
                self.assertEqual(report["candidates"][0]["layout"], "b")
                without_readings = {k: v for k, v in page.items() if k != "binding_text_capacity"}
                missing = selection.rank_page(without_readings, bank, 1.0, {}, lane)
                empty = selection.rank_page({**without_readings, "binding_text_capacity": {}}, bank, 1.0, {}, lane)
                self.assertEqual(missing, empty)

    def test_single_candidate_does_not_become_undecided_for_missing_margin(self):
        page = {"page_role": "并列·事项", "points": 3}
        bank = {"only": {"page_type": "content", "content_capacity": {}, "reuse_friendly": True,
                          "renderer_support": {"render:html": "template"}}}
        report = selection.rank_page(page, bank, 1.0, {"only": 0.30}, "render:html")
        self.assertEqual(report["score_margin"], None)
        self.assertEqual(report["decision"], "auto")

    def test_lightweight_alias_is_preserved_with_canonical_asset_metadata(self):
        bank = {"bullets": {"asset_id": "builtin:layout:bullets", "page_type": "content",
                            "content_capacity": {}, "reuse_friendly": True}}
        report = selection.rank_page({"page_role": "并列·事项", "points": 3}, bank, 1.0, {})
        self.assertEqual(report["candidates"][0]["layout"], "bullets")
        self.assertNotIn("candidate_key", report["candidates"][0])

    def test_same_layout_execution_identities_keep_separate_capacity_readings(self):
        page = {"page_role": "并列·事项", "points": 3,
                "binding_text_capacity": {
                    "execution-tight": {"title": {"used": 45, "limit": 40, "level": "over"}},
                    "execution-roomy": {"title": {"used": 15, "limit": 40, "level": "ok"}}}}
        bank = {key: {"ranking_layout_id": "builtin:layout:bullets", "page_type": "content",
                      "content_capacity": {}, "reuse_friendly": True}
                for key in page["binding_text_capacity"]}
        report = selection.rank_page(page, bank, 1.0, {}, hard_qualified=True)
        self.assertEqual(len(report["candidates"]), 2)
        self.assertEqual(report["candidates"][0]["candidate_key"], "execution-roomy")
        self.assertGreater(report["candidates"][0]["raw_score"], report["candidates"][1]["raw_score"])


if __name__ == "__main__":
    unittest.main()
