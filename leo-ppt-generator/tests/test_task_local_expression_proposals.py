"""封闭 proposal 只移动几何和置换同类型槽，不改事实、主题或 canonical。"""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import shutil
import tempfile

from leo_ppt_generator.task_local_layout_proposals import (
    ProposalError, _digest, proposal_digest, apply_task_local_proposal,
    validate_task_local_proposal, curation_feedback,
)

ROOT = Path(__file__).resolve().parents[1]


class ProposalContractTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "template-library/canonical/layouts/p2-02-vertical-timeline-layouts/layout.json").read_text())
        self.template = json.loads((ROOT / "template-library/canonical/templates/chain-flow/template.json").read_text())
        self.content = {"facts": [{"value": "2", "unit": "小时"}], "focus": "claim"}
        self.theme = {"font_size": 28}
        self.proposal = {"schema_version": 1, "base_asset": self.profile["asset_id"], "base_generation": "generation-a",
            "base_asset_digest": _digest(self.profile), "run_scope": "run-a", "candidates": [
                {"candidate_id": "one", "lane": "render:html", "ops": [
                    {"op": "set_span", "target": "chain", "value": {"width": 550, "height": 350},
                     "base_asset": self.profile["asset_id"], "lane": "render:html"},
                    {"op": "set_anchor_gap", "target": "chain", "anchor": "header", "value": 20,
                     "base_asset": self.profile["asset_id"], "lane": "render:html"}]}]}
        self.seal()

    def seal(self):
        self.proposal["proposal_digest"] = proposal_digest(self.proposal)

    def apply(self, **overrides):
        args = dict(base_profile=self.profile, base_generation="generation-a", run_scope="run-a",
            allowed_assets={self.profile["asset_id"]}, content=self.content, theme=self.theme, template=self.template)
        args.update(overrides)
        return apply_task_local_proposal(self.proposal, **args)

    def test_ops_apply_without_mutating_content_theme_or_canonical(self):
        before = deepcopy((self.profile, self.content, self.theme))
        result = self.apply()[0]
        self.assertEqual(result["profile"]["regions"]["chain"]["y"], 184)
        self.assertEqual(result["profile"]["regions"]["chain"]["width"], 550)
        self.assertEqual(result["qualification_status"], "unverified")
        self.assertEqual((self.profile, self.content, self.theme), before)

    def test_canonical_patch_identity_ignores_input_op_order(self):
        snapshot = self.apply()[0]
        before = snapshot["proposal_digest"]
        digest = self.proposal["proposal_digest"]
        self.proposal["candidates"][0]["ops"].reverse()
        self.seal()
        self.assertEqual(digest, self.proposal["proposal_digest"])
        self.assertEqual(before, self.apply()[0]["proposal_digest"])
        self.assertEqual(snapshot, self.apply()[0])

    def test_run_generation_asset_and_canonical_identity_cannot_be_impersonated(self):
        for override in ({"run_scope": "run-b"}, {"base_generation": "generation-b"}, {"allowed_assets": set()}):
            with self.subTest(override=override), self.assertRaises(ProposalError): self.apply(**override)
        self.proposal["candidates"][0]["candidate_id"] = self.profile["asset_id"]
        self.seal()
        with self.assertRaises(ProposalError): self.apply()

    def test_free_css_old_op_missing_anchor_overflow_and_deleted_fact_rejected(self):
        base = deepcopy(self.proposal)
        for field, value in (("css", "display:none"), ("path", "../../canonical"), ("delete_facts", True)):
            self.proposal = deepcopy(base)
            self.proposal["candidates"][0]["ops"][0][field] = value
            self.seal()
            with self.subTest(field=field), self.assertRaises(ProposalError): self.apply()
        self.proposal = deepcopy(base)
        self.proposal["candidates"][0]["ops"][0]["target"] = "missing"
        self.seal()
        with self.assertRaisesRegex(ProposalError, "proposal_anchor_unknown"): self.apply()
        self.proposal = deepcopy(base)
        self.proposal["candidates"][0]["ops"][0]["value"]["width"] = 1280
        self.seal()
        with self.assertRaisesRegex(ProposalError, "proposal_canvas_overflow"): self.apply()
        legacy = {"run_scope": "run-a", "base_asset": self.profile["asset_id"], "patch": [{"op": "set_slot"}]}
        legacy["proposal_digest"] = _digest(legacy)
        with self.assertRaisesRegex(ProposalError, "proposal_schema_invalid"):
            validate_task_local_proposal(legacy, run_scope="run-a", allowed_assets={self.profile["asset_id"]})

    def test_three_candidate_limit_and_one_attempt_per_candidate(self):
        base = deepcopy(self.proposal["candidates"][0])
        self.proposal["candidates"] = [{**base, "candidate_id": str(i)} for i in range(4)]
        self.seal()
        with self.assertRaises(ProposalError): self.apply()
        self.proposal["candidates"].pop()
        self.seal()
        self.assertEqual(len(self.apply()), 3)
        rows = [{"candidate_id": str(i), "status": "failed", "gap": "proposal_evidence_missing"} for i in range(3)]
        feedback = curation_feedback(self.proposal, rows)
        self.assertFalse(feedback["automatic_promotion"])
        self.assertEqual(len(feedback["attempts"]), 3)
        with self.assertRaises(ProposalError): curation_feedback(self.proposal, [rows[0], rows[0]])

    def test_failed_candidate_does_not_abort_remaining_finite_candidates(self):
        broken = deepcopy(self.proposal["candidates"][0])
        broken["candidate_id"] = "overflow"
        broken["ops"][0]["value"]["width"] = 1280
        self.proposal["candidates"].insert(0, broken)
        self.seal()
        rows = self.apply(collect_failures=True)
        self.assertEqual(rows[0]["gap"], "proposal_canvas_overflow")
        self.assertEqual(rows[1]["candidate_id"], "one")

    def test_unknown_operation_and_nonfinite_value_fail_closed(self):
        self.proposal["candidates"][0]["ops"][0]["op"] = "inject_css"
        self.seal()
        with self.assertRaisesRegex(ProposalError, "proposal_schema_invalid"):
            self.apply()
        self.proposal["candidates"][0]["ops"][0]["op"] = "set_span"
        self.proposal["candidates"][0]["ops"][0]["value"]["width"] = float("nan")
        with self.assertRaises(ValueError):
            self.seal()
            self.apply()


class ProposalPipelineTests(unittest.TestCase):
    def setUp(self):
        from tests.expression_test_support import real_validation_inputs
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.qualification import RECEIPTS_PATH
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.pack, original, self.context = real_validation_inputs()
        self.library = self.root / "library"
        shutil.copytree(original.builtin_root, self.library)
        # 只在本测试私有库移除共享资格；提案必须建立自己的真实正反证据。
        (self.library / RECEIPTS_PATH).unlink()
        self.resolver = AssetResolver(library=self.library, home=self.root / "user")
        self.cases = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())

    def request(self, *, probes=True):
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest
        profile = self.resolver.resolve("builtin:layout:body-basic")["data"]
        proposals = {}
        for index, page in enumerate(self.pack["pages"]):
            document = {"schema_version": 1, "run_scope": "proposal-runtime", "base_asset": profile["asset_id"],
                "base_generation": self.resolver.generation, "base_asset_digest": _digest(profile), "candidates": [
                    {"candidate_id": "overflow", "lane": "render:html", "ops": [{"op": "set_span", "target": "content",
                        "value": {"width": 1280, "height": 568}, "base_asset": profile["asset_id"], "lane": "render:html"}]},
                    {"candidate_id": "fit", "lane": "render:html", "ops": [{"op": "set_span", "target": "content",
                        "value": {"width": 1060 - index * 20, "height": 568}, "base_asset": profile["asset_id"], "lane": "render:html"}]}]}
            document["proposal_digest"] = proposal_digest(document)
            proposals[page["page_id"]] = document
        return PipelineRequest(self.pack, self.context, self.resolver.generation,
            {page["page_id"]: ["render:html"] for page in self.pack["pages"]}, str(self.root / "run"),
            "proposal-runtime", str(self.library), purpose="validation", proposals=proposals,
            proposal_probe_cases=self.cases if probes else None)

    def test_two_page_patches_use_own_probes_freeze_replay_and_preserve_canonical(self):
        from leo_ppt_generator.application.routes import generate
        from leo_ppt_generator.application.expression_pipeline import load_committed_input
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.content_projection import verify_effective_binding
        before = {p.relative_to(self.library).as_posix(): p.read_bytes() for p in self.library.rglob("*") if p.is_file()}
        request = self.request()
        result = generate(request, resolver=self.resolver)
        self.assertEqual(result["status"], "html_validated")
        self.assertFalse(result["publication_ready"])
        committed = load_committed_input(self.root / "run")
        frozen = AssetResolver.from_snapshot(committed["root"] / "asset-snapshot")
        digests = set()
        for page in self.pack["pages"]:
            binding = result["bindings"]["render:html"][page["page_id"]]
            self.assertEqual(binding["execution_pairing_identity"]["source_kind"], "task-local-proposal")
            self.assertEqual(binding["proposal"]["candidate_id"], "fit")
            digests.add(binding["proposal"]["proposal_digest"])
            verify_effective_binding(binding, page, resolver=frozen)
            self.assertTrue(any(ref["path"].endswith("proposal.json") for ref in binding["eligibility"]["checks"]["qualification"]["evidence_files"]))
            qualification = binding["eligibility"]["checks"]["qualification"]
            receipt = qualification["receipt_payloads"][0]
            observation = json.loads((frozen.builtin_root / receipt["probes"]["positive"]["observation"]["path"]).read_text())
            measurement = json.loads((frozen.builtin_root / observation["measurement"]["path"]).read_text())
            width = binding["proposal"]["profile"]["regions"]["content"]["width"]
            self.assertTrue(any(abs(block["box"][2] - width) < 1 for block in measurement["blocks"]), measurement["blocks"])
        self.assertEqual(len(digests), 2)
        after = {p.relative_to(self.library).as_posix(): p.read_bytes() for p in self.library.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(generate(request, resolver=self.resolver)["input_generation"], result["input_generation"])
        feedback = json.loads((self.root / "run/qa/proposal-curation-render-html.json").read_text())
        self.assertTrue(all(len(row["attempts"]) == 2 and not row["automatic_promotion"] for row in feedback.values()))
        binding = deepcopy(next(iter(result["bindings"]["render:html"].values())))
        from leo_ppt_generator.content_projection import compute_materialization_binding_digest
        binding["proposal"]["profile"]["regions"]["content"]["width"] -= 1
        binding["materialization_binding_digest"] = compute_materialization_binding_digest(binding)
        with self.assertRaisesRegex(ProposalError, "proposal_snapshot_changed"):
            verify_effective_binding(binding, self.pack["pages"][0], resolver=frozen)

    def test_same_patch_on_distinct_pages_keeps_content_evidence_separate(self):
        from leo_ppt_generator.application.routes import generate
        request = self.request()
        first, second = list(request.proposals)
        request.proposals[second] = deepcopy(request.proposals[first])
        result = generate(request, resolver=self.resolver)
        bindings = list(result["bindings"]["render:html"].values())
        self.assertEqual(bindings[0]["proposal"]["proposal_digest"], bindings[1]["proposal"]["proposal_digest"])
        self.assertNotEqual(bindings[0]["eligibility"]["checks"]["qualification"]["evidence_set_digest"],
                            bindings[1]["eligibility"]["checks"]["qualification"]["evidence_set_digest"])

    def test_absent_patch_evidence_returns_gap_without_committing_input(self):
        from leo_ppt_generator.application.routes import generate
        from leo_ppt_generator.application.expression_pipeline import ExpressionPipelineError
        with self.assertRaises(ExpressionPipelineError) as caught:
            generate(self.request(probes=False), resolver=self.resolver)
        self.assertIn("proposal_evidence_missing", str(caught.exception.details))
        self.assertFalse((self.root / "run/input/current.json").exists())

    def test_cross_run_reuse_is_rejected_before_any_materialization(self):
        from dataclasses import replace
        from leo_ppt_generator.application.routes import generate
        with self.assertRaisesRegex(ProposalError, "proposal_run_scope_mismatch"):
            generate(replace(self.request(), run_id="another-run"), resolver=self.resolver)
        self.assertFalse((self.root / "run").exists())
