"""封闭 proposal 只移动几何和置换同类型槽，不改事实、主题或 canonical。"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

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
        before = self.apply()[0]["proposal_digest"]
        digest = self.proposal["proposal_digest"]
        self.proposal["candidates"][0]["ops"].reverse()
        self.seal()
        self.assertEqual(digest, self.proposal["proposal_digest"])
        self.assertEqual(before, self.apply()[0]["proposal_digest"])

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
