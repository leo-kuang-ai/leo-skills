"""双层摘要验证只声明机制结果；当前没有能力证据的候选仍不可物化。"""
from copy import deepcopy
from pathlib import Path
import unittest

from leo_ppt_generator.content_pack import compile_content_pack
from leo_ppt_generator.content_projection import (
    ProjectionError, compute_expression_binding_digest, compute_materialization_binding_digest,
    precompile_binding, verify_dual_binding_digests, verify_binding_reference,
    binding_impact,
)
from leo_ppt_generator.execution_pairing import PairingError, pairing_identity, pairing_key
from leo_ppt_generator.templates import resolve_design_context


class BindingV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.pack = compile_content_pack((root / "references/authoring/page-expression-example.md").read_text(),
                                       master_path="references/authoring/page-expression-example.md")
        cls.context = resolve_design_context("清爽专业风")
        cls.page = cls.pack["pages"][1]
        cls.binding = precompile_binding(cls.page, cls.context, "builtin:layout:p8-08-duo-compare-layouts",
            content_digest=cls.pack["content_digest"], numbers=cls.pack["numbers"])

    def test_current_unverified_binding_is_well_formed_but_not_executable(self):
        verify_dual_binding_digests(self.binding)
        self.assertFalse(self.binding["eligibility"]["qualified"])
        self.assertNotIn("binding_digest", self.binding)

    def test_lane_neutral_digest_does_not_use_theme_layout_slots_or_catalog(self):
        for key, value in (("backend", "image"), ("layout_id", "builtin:layout:other"),
                           ("template_id", "builtin:template:other"), ("slot_map", {}),
                           ("execution_pairing_identity", {"different": "pairing"}),
                           ("effective", {"generation": "other", "theme": {"color": "red"}})):
            other = deepcopy(self.binding)
            other[key] = value
            with self.subTest(key=key):
                self.assertEqual(compute_expression_binding_digest(other), self.binding["expression_binding_digest"])
                self.assertNotEqual(compute_materialization_binding_digest(other), self.binding["materialization_binding_digest"])

    def test_real_precompile_both_lanes_share_expression_digest(self):
        image = precompile_binding(self.page, self.context, "builtin:layout:p8-08-duo-compare-layouts", backend="image",
            content_digest=self.pack["content_digest"], numbers=self.pack["numbers"])
        self.assertEqual(self.binding["expression_binding_digest"], image["expression_binding_digest"])
        self.assertNotEqual(self.binding["materialization_binding_digest"], image["materialization_binding_digest"])
        self.assertIsNone(image["template_id"])
        self.assertFalse(image["eligibility"]["qualified"])

    def test_deck_integrity_update_does_not_invalidate_unchanged_page(self):
        other = deepcopy(self.binding)
        other["content_digest"] = "b" * 64
        self.assertEqual(compute_expression_binding_digest(other), self.binding["expression_binding_digest"])
        self.assertEqual(compute_materialization_binding_digest(other), self.binding["materialization_binding_digest"])
        other["page_content_digest"] = "c" * 64
        self.assertNotEqual(compute_expression_binding_digest(other), self.binding["expression_binding_digest"])

    def test_impact_rejects_cross_lane_expression_disagreement(self):
        image = precompile_binding(self.page, self.context, "builtin:layout:p8-08-duo-compare-layouts", backend="image",
            content_digest=self.pack["content_digest"], numbers=self.pack["numbers"])
        image["page_content_digest"] = "e" * 64
        image["expression_binding_digest"] = compute_expression_binding_digest(image)
        image["materialization_binding_digest"] = compute_materialization_binding_digest(image)
        snapshot = {"image": {self.page["page_id"]: image}, "render:html": {self.page["page_id"]: self.binding}}
        with self.assertRaisesRegex(ProjectionError, "expression_binding_lane_mismatch"):
            binding_impact({}, snapshot)

    def test_display_page_number_does_not_change_expression_but_changes_pixels_binding(self):
        other = deepcopy(self.binding)
        other["number"] += 1
        self.assertEqual(compute_expression_binding_digest(other), self.binding["expression_binding_digest"])
        self.assertNotEqual(compute_materialization_binding_digest(other), self.binding["materialization_binding_digest"])

    def test_missing_old_and_mixed_schema_fail_uniformly(self):
        for mutation in ("old", "mixed", "expression_binding_digest", "materialization_binding_digest", "slot_map"):
            candidate = deepcopy(self.binding)
            if mutation == "old": candidate = {"schema_version": 1, "binding_digest": "a" * 64}
            elif mutation == "mixed": candidate["binding_digest"] = "a" * 64
            else: del candidate[mutation]
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ProjectionError, "^binding_schema_mismatch$"):
                verify_dual_binding_digests(candidate)

    def test_each_tampered_layer_and_cross_lane_receipt_rejected(self):
        for key in ("expression_binding_digest", "materialization_binding_digest"):
            candidate = deepcopy(self.binding)
            candidate[key] = "a" * 64
            with self.subTest(key=key), self.assertRaisesRegex(ProjectionError, key + "_mismatch"):
                verify_dual_binding_digests(candidate)
        receipt = {key: self.binding[key] for key in ("expression_binding_digest", "materialization_binding_digest")}
        receipt["backend"] = "image"
        with self.assertRaisesRegex(ProjectionError, "materialization_binding_lane_mismatch"):
            verify_binding_reference(receipt, self.binding)
        del receipt["materialization_binding_digest"]
        with self.assertRaisesRegex(ProjectionError, "binding_schema_mismatch"):
            verify_binding_reference(receipt, self.binding)


class PairingIdentityTests(unittest.TestCase):
    def test_all_discriminators_participate_without_canonical_proposal_collision(self):
        layout = {"asset_id": "builtin:layout:l", "revision": "a"}
        template = {"asset_id": "builtin:template:t", "revision": "b", "kind": "template", "data": {"lane": "render:html"}}
        identity = pairing_identity(layout=layout, executable=template, lane="render:html", catalog_generation="g", evidence_digest="a" * 64)
        self.assertEqual(identity["source_kind"], "canonical-derived-pairing")
        with self.assertRaises(PairingError):
            pairing_key({**identity, "source_kind": "canonical"})
        key = pairing_key(identity)
        self.assertEqual(pairing_key(deepcopy(identity)), key)
        for field, value in (("catalog_generation", "g2"), ("capability_evidence_digest", "b" * 64),
                             ("template_identity", {"asset_id": "builtin:template:t2", "revision": "b"})):
            self.assertNotEqual(pairing_key({**identity, field: value}), key)
        proposal = pairing_identity(layout=layout, executable=template, lane="render:html", catalog_generation="g", evidence_digest="a" * 64,
                                    proposal={"proposal_digest": "c" * 64, "run_scope": "r1"})
        self.assertNotEqual(pairing_key(proposal), key)
        self.assertNotEqual(pairing_key({**proposal, "run_scope": "r2"}), pairing_key(proposal))
        for malformed in ({**identity, "run_scope": "r1"}, {**identity, "template_identity": None},
                          {**proposal, "source_kind": "canonical-derived-pairing"}):
            with self.assertRaises(PairingError): pairing_key(malformed)
