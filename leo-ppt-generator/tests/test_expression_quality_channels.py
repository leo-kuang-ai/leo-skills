"""当前文件/收据/manifest 的质量状态；合成输入只证明失败门和状态机。"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from leo_ppt_generator.quality_metrics import deck_quality_for_run, _export_evidence
from leo_ppt_generator.content_projection import binding_impact, compute_expression_binding_digest, compute_materialization_binding_digest
from leo_ppt_generator.application.expression_pipeline import write_atomic_input_generation, _digest
from tests.test_expression_pipeline import transaction_inputs


class QualityChannelTests(unittest.TestCase):
    def test_files_and_tf_events_cannot_upgrade_any_evidence_channel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "input").mkdir()
            (root / "input/content-pack.json").write_text("{}")
            (root / "rendered").mkdir()
            (root / "rendered/pretend.png").write_bytes(b"not a PNG")
            quality = deck_quality_for_run(root, {"tf": {"status": "observed"}})
            self.assertFalse(any(value == "passed" for value in quality["channels"].values()))
            self.assertEqual(quality["overall_status"], "blocked")
            self.assertFalse(quality["publication_ready"])
            from jsonschema import Draft202012Validator
            schema = json.loads((Path(__file__).resolve().parents[1] / "runtime/src/leo_ppt_generator/schemas/deck-quality-v1.schema.json").read_text())
            self.assertFalse(list(Draft202012Validator(schema).iter_errors(quality)))

    def test_uncommitted_input_is_not_upgraded_and_committed_drift_is_stale(self):
        payload, resolver, _, _ = transaction_inputs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "run"
            def interrupt(phase):
                if phase == "before_pointer": raise InterruptedError()
            with self.assertRaises(InterruptedError):
                write_atomic_input_generation(root, payload, generation=_digest(payload), resolver=resolver, checkpoint=interrupt)
            quality = deck_quality_for_run(root)
            self.assertEqual(quality["channels"]["schema"], "not_run")
            target = write_atomic_input_generation(root, payload, generation=_digest(payload), resolver=resolver)
            (target / "bindings.json").write_text("{}")
            self.assertEqual(deck_quality_for_run(root)["channels"]["schema"], "stale")

    def test_export_manifest_absence_and_drift_are_lane_specific(self):
        payload, _, _, _ = transaction_inputs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            states = _export_evidence(root, payload, "a" * 64)
            self.assertEqual(states["render:html"]["status"], "blocked")
            self.assertEqual(states["image"]["status"], "not_run")
            (root / "pipeline-result.json").write_text(json.dumps({"input_generation": "b" * 64}))
            states = _export_evidence(root, payload, "a" * 64)
            self.assertEqual(states["render:html"]["status"], "stale")
            self.assertEqual(states["image"]["status"], "not_run")


class BindingImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, _, _, _ = transaction_inputs()

    def mutate(self, callback):
        before = self.payload["bindings"]
        after = deepcopy(before)
        pid = sorted(after["render:html"])[0]
        binding = after["render:html"][pid]
        callback(binding)
        binding["expression_binding_digest"] = compute_expression_binding_digest(binding)
        binding["materialization_binding_digest"] = compute_materialization_binding_digest(binding)
        return pid, binding_impact(before, after)

    def test_theme_asset_and_display_only_invalidate_one_materialization(self):
        cases = [("theme", lambda binding: binding["effective"]["theme"]["colors"].update(accent="#FF0000")),
                 ("asset", lambda binding: binding["execution_pairing_identity"].update(catalog_generation="new-generation")),
                 ("display_order", lambda binding: binding.update(number=9))]
        for expected, callback in cases:
            pid, impact = self.mutate(callback)
            with self.subTest(reason=expected):
                self.assertEqual(impact["pages"][pid]["reasons"], [expected])
                self.assertEqual(impact["pages"][pid]["expression_status"], "passed")
                self.assertTrue(all(row["status"] == "passed" for key, row in impact["pages"].items() if key != pid))

    def test_content_and_expression_invalidate_expression_only_for_changed_page(self):
        for expected, callback in (("content", lambda binding: binding.update(page_content_digest="b" * 64)),
                                  ("expression", lambda binding: binding["expression_choice_identity"].update(primary_expression="process"))):
            pid, impact = self.mutate(callback)
            with self.subTest(reason=expected):
                self.assertEqual(impact["pages"][pid]["reasons"], [expected])
                self.assertEqual(impact["pages"][pid]["expression_status"], "stale")
                self.assertTrue(all(row["status"] == "passed" for key, row in impact["pages"].items() if key != pid))

    def test_input_digests_and_impact_schema_are_derived_and_stable(self):
        before = self.payload["bindings"]
        unchanged = binding_impact(before, deepcopy(before))
        self.assertEqual(unchanged["input_digests"]["before"], unchanged["input_digests"]["after"])
        self.assertTrue(all(row["status"] == "passed" for row in unchanged["pages"].values()))
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).resolve().parents[1] / "runtime/src/leo_ppt_generator/schemas/impact-v2.schema.json").read_text())
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(unchanged)))
