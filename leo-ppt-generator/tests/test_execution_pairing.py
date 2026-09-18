"""执行视图只派生身份；这里的资格输入用于机制测试，不是发布证据。"""
from copy import deepcopy
import unittest

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.execution_pairing import derive_execution_pairings, validate_candidate_view, PairingError


class ExecutionPairingViewTests(unittest.TestCase):
    def setUp(self):
        self.resolver = AssetResolver()
        self.layout = self.resolver.resolve("builtin:layout:body-basic")
        self.template = self.resolver.resolve("builtin:template:body-basic")
        self.qualifications = {self.layout["asset_id"]: {
            "evidence_set_digest": "a" * 64,
            "lanes": {"render:html": {"relations": {
                name: {"status": "publication-qualified", "probe_receipts": ["mechanism-only"], "gaps": [], "evidence_set_digest": "a" * 64}
                for name in ("independent", "process")}}}}}

    def derive(self, layouts=None, templates=None):
        return derive_execution_pairings(layouts or [self.layout], templates or [self.template],
                                         self.qualifications, catalog_generation=self.resolver.generation)

    def test_one_complete_identity_groups_qualified_relations_and_deduplicates(self):
        result = self.derive(layouts=[self.layout, deepcopy(self.layout)])
        self.assertEqual(len(result["candidates"]), 1, result)
        self.assertEqual(set(result["candidates"][0]["relations"]), {"independent", "process"})

    def test_missing_nested_slot_source_and_stale_relation_are_excluded(self):
        template = deepcopy(self.template)
        next(b for b in template["data"]["slot_bindings"] if b["slot"] == "chart")["input_path"] = "absent"
        result = self.derive(templates=[template])
        self.assertFalse(result["candidates"])
        self.qualifications[self.layout["asset_id"]]["lanes"]["render:html"]["relations"]["process"]["status"] = "rejected"
        result = self.derive()
        self.assertEqual(set(result["candidates"][0]["relations"]), {"independent"})

    def test_tampered_duplicate_or_mixed_purpose_view_is_rejected(self):
        for mutation in ("missing", "digest", "duplicate", "evidence", "purpose"):
            view = self.derive()
            candidate = view["candidates"][0]
            if mutation == "missing":
                del candidate["identity"]["recipe_identity"]
            elif mutation == "digest":
                candidate["identity_digest"] = "f" * 64
            elif mutation == "duplicate":
                view["candidates"].append(deepcopy(candidate))
            elif mutation == "evidence":
                candidate["relations"]["independent"]["evidence_set_digest"] = "b" * 64
            else:
                candidate["relations"]["independent"].update(status="provisional", gaps=["visual_review_not_run"])
            with self.subTest(mutation=mutation), self.assertRaises(PairingError):
                validate_candidate_view(view)


if __name__ == "__main__":
    unittest.main()
