"""样张决策在真实文件与 image prepare 边界的回归。"""

import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import shutil

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))

from leo_ppt_generator.application.run_index import RunIndex
from leo_ppt_generator.application.sample_decisions import (
    RECEIPT_PATH, record_sample_decision, verify_sample_decision,
)
from leo_ppt_generator.cli import build_parser, dispatch
from leo_ppt_generator import cli
from leo_ppt_generator.config.backend_contract import BackendRegistry
from leo_ppt_generator.contracts import ContractError
from leo_ppt_generator.storage import sha256_file


class SampleDecisions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.run = self.root / "run"
        from tests.expression_test_support import copy_real_html_run, slides_for_run
        result = copy_real_html_run(self.run, request_index=True)
        page = result["receipt_refs"]["render:html"]["pg-11111111"]
        self.sample = self.root / "sample.png"
        shutil.copyfile(self.run / page["artifact"], self.sample)
        self.original_sample = self.sample.read_bytes()
        self.slides = self.root / "slides.json"
        self.slides.write_text(json.dumps(slides_for_run(self.run), ensure_ascii=False), encoding="utf-8")
        self.style = self.root / "visual.md"
        self.style.write_text("白底黑字", encoding="utf-8")
        self.binding = self.root / "binding.json"
        self.binding_data = {"backend": "render:html", "width": 2560, "height": 1440,
                             "generation_method": "full-image", "style_visual_path": str(self.style),
                             "layout_binding_path": None}
        self.write_binding()
        self.authorization = self.root / "request.md"
        self.authorization.write_text("样张选择委托你决定。", encoding="utf-8")

    def change_slides(self, title):
        slides = json.loads(self.slides.read_text())
        slides[0]["title"] = title
        self.slides.write_text(json.dumps(slides))

    def write_binding(self):
        self.binding.write_text(json.dumps(self.binding_data), encoding="utf-8")

    def record(self, source="user-delegated"):
        return record_sample_decision(self.run, sample=self.sample, slides=self.slides,
                                      binding=self.binding, decision_source=source,
                                      authorization_ref=self.authorization, authorization_quote="样张选择委托你决定。")

    def prepare(self, with_binding=False):
        args = ["image", "prepare", str(self.run), "--slides", str(self.slides)]
        if with_binding:
            args += ["--sample-binding", str(self.binding)]
        return dispatch(build_parser().parse_args(args))

    def test_same_binding_restores_and_json_formatting_does_not_invalidate(self):
        self.assertEqual(self.record()["idempotency_status"], "created")
        self.assertEqual(self.record()["idempotency_status"], "replayed")
        content = json.loads(self.slides.read_text(encoding="utf-8"))
        self.slides.write_text(json.dumps(content, indent=4), encoding="utf-8")
        self.assertEqual(verify_sample_decision(self.run)["status"], "verified")
        self.assertEqual(self.prepare()["sample_decision"]["decision_source"], "user-delegated")

    def test_image_and_content_changes_block_prepare_without_flag(self):
        self.record()
        Image.new("RGB", (2560, 1440), "black").save(self.sample)
        with self.assertRaisesRegex(ContractError, "sample_decision_stale"):
            self.prepare()
        self.sample.write_bytes(self.original_sample)
        self.change_slides("changed")
        with self.assertRaisesRegex(ContractError, "sample_decision_stale"):
            self.prepare()
        self.assertFalse((self.run / "input/slides.json").exists())

    def test_backend_dimensions_method_and_visual_changes_block(self):
        self.record()
        for key, changed, reason in (("backend", "other", "sample_backend_mismatch"),
                                     ("width", 2561, "sample_dimensions_mismatch"),
                                     ("generation_method", "overlay", "sample_decision_stale")):
            with self.subTest(key=key):
                old = self.binding_data[key]
                self.binding_data[key] = changed
                self.write_binding()
                with self.assertRaisesRegex(ContractError, reason):
                    self.prepare()
                self.binding_data[key] = old
                self.write_binding()
        self.style.write_text("黑底白字", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "sample_decision_stale"):
            self.prepare()

    def test_missing_corrupt_receipt_and_legacy_are_distinct(self):
        with self.assertRaisesRegex(ContractError, "sample_decision_required"):
            self.prepare(with_binding=True)
        self.assertEqual(self.prepare()["sample_decision"], {
            "status": "not_run", "mode": "legacy", "reason_code": "sample_decision_not_recorded"})
        (self.run / RECEIPT_PATH).write_text("broken", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "sample_decision_invalid"):
            self.prepare()

    def test_authorization_quote_required_and_delegation_not_relabelled(self):
        with self.assertRaisesRegex(ContractError, "sample_authorization_quote_missing"):
            record_sample_decision(self.run, sample=self.sample, slides=self.slides, binding=self.binding,
                                   decision_source="user-confirmed", authorization_ref=self.authorization,
                                   authorization_quote="我已人工逐项确认")
        self.record()
        receipt = json.loads((self.run / RECEIPT_PATH).read_text())
        self.assertEqual(receipt["decision"]["source"], "user-delegated")
        self.assertNotIn("approved", receipt)
        receipt["decision"]["source"] = "user-confirmed"
        (self.run / RECEIPT_PATH).write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ContractError, "sample_decision_invalid"):
            verify_sample_decision(self.run)

    def test_cli_record_and_verify(self):
        args = ["image", "sample-record", str(self.run), "--sample", str(self.sample),
                "--slides", str(self.slides), "--binding", str(self.binding),
                "--decision-source", "user-delegated", "--authorization-ref", str(self.authorization),
                "--authorization-quote", "样张选择委托你决定。"]
        self.assertEqual(dispatch(build_parser().parse_args(args))["reason_code"], "sample_decision_recorded")
        result = dispatch(build_parser().parse_args(["image", "sample-verify", str(self.run)]))
        self.assertEqual(result["sample_decision"]["status"], "verified")

    def test_explicit_redecision_preserves_previous_receipt(self):
        self.record()
        receipt = self.run / RECEIPT_PATH
        receipt.write_text(json.dumps(json.loads(receipt.read_text()), indent=4), encoding="utf-8")
        old_bytes = receipt.read_bytes()
        old_digest = sha256_file(self.run / RECEIPT_PATH)
        self.change_slides("revised")
        with self.assertRaisesRegex(ContractError, "sample_decision_conflict"):
            self.record()
        record_sample_decision(self.run, sample=self.sample, slides=self.slides, binding=self.binding,
                               decision_source="user-delegated", authorization_ref=self.authorization,
                               authorization_quote="样张选择委托你决定。", supersedes=old_digest)
        self.assertTrue((self.run / "reports/sample-decisions" / f"{old_digest}.json").is_file())
        self.assertEqual((self.run / "reports/sample-decisions" / f"{old_digest}.json").read_bytes(), old_bytes)
        self.assertEqual(self.prepare()["sample_decision"]["status"], "verified")

    def test_non_widescreen_sample_cannot_be_accepted_by_matching_binding(self):
        Image.new("RGB", (160, 120), "white").save(self.sample)
        self.binding_data["height"] = 120
        self.write_binding()
        with self.assertRaisesRegex(ContractError, "sample_dimensions_mismatch"):
            self.record()

    def test_corrupt_receipt_requires_explicit_redecision_and_preserves_bytes(self):
        self.record()
        receipt = self.run / RECEIPT_PATH
        receipt.write_bytes(b"interrupted receipt")
        previous = sha256_file(receipt)
        with self.assertRaisesRegex(ContractError, "sample_decision_invalid"):
            self.record()
        record_sample_decision(self.run, sample=self.sample, slides=self.slides, binding=self.binding,
                               decision_source="user-delegated", authorization_ref=self.authorization,
                               authorization_quote="样张选择委托你决定。", supersedes=previous)
        self.assertEqual((self.run / "reports/sample-decisions" / f"{previous}.json").read_bytes(),
                         b"interrupted receipt")
        self.assertEqual(verify_sample_decision(self.run)["status"], "verified")

    def test_enabled_run_missing_receipt_never_falls_back_to_legacy(self):
        self.record()
        self.prepare()
        (self.run / RECEIPT_PATH).unlink()
        with self.assertRaisesRegex(ContractError, "sample_decision_required"):
            self.prepare()
        with self.assertRaisesRegex(ContractError, "sample_decision_required"):
            dispatch(build_parser().parse_args(["image", "assemble", str(self.run)]))

    def test_concurrent_redecision_cannot_mix_snapshot_and_returned_digest(self):
        from leo_ppt_generator.application import sample_decisions as module
        self.record()
        original = module._binding

        def replace_during_check(*args, **kwargs):
            result = original(*args, **kwargs)
            receipt = self.run / RECEIPT_PATH
            receipt.write_bytes(receipt.read_bytes() + b"\n")
            return result

        with patch.object(module, "_binding", side_effect=replace_during_check):
            with self.assertRaisesRegex(ContractError, "sample_decision_conflict"):
                verify_sample_decision(self.run)

    def test_frozen_backend_contract_drift_is_detected(self):
        self.record()
        run = json.loads((self.run / "run.json").read_text())
        backend_path = self.run / run["backend_contract"]["path"]
        backend = json.loads(backend_path.read_text())
        backend["model"] = "different-model"
        backend_path.write_text(json.dumps(backend))
        with self.assertRaisesRegex(ContractError, "sample_decision_stale"):
            self.prepare()

    def test_input_changed_during_freeze_cannot_reach_jobs(self):
        self.record()
        freeze = cli._freeze_slides_contract

        def change_then_freeze(run_path, source_path):
            self.change_slides("concurrent change")
            return freeze(run_path, source_path)

        with patch.object(cli, "_freeze_slides_contract", side_effect=change_then_freeze):
            with self.assertRaisesRegex(ContractError, "sample_decision_stale"):
                self.prepare()
        self.assertFalse((self.run / "image-deck/slide_jobs.json").exists())

    def test_assemble_rechecks_sample_after_prepare(self):
        self.record()
        self.prepare()
        self.style.write_text("changed after prepare", encoding="utf-8")
        for command in ("assemble", "finalize"):
            with self.subTest(command=command):
                with patch.object(cli.ImageDeckAdapter, "finalize") as finalize:
                    with self.assertRaisesRegex(ContractError, "sample_decision_stale"):
                        dispatch(build_parser().parse_args(["image", command, str(self.run)]))
                    finalize.assert_not_called()

    def test_assemble_rechecks_frozen_slides_even_if_original_is_unchanged(self):
        self.record()
        self.prepare()
        (self.run / "input/slides.json").write_text('[{"number":1,"title":"tampered"}]')
        with patch.object(cli.ImageDeckAdapter, "finalize") as finalize:
            with self.assertRaisesRegex(ContractError, "sample_decision_stale"):
                dispatch(build_parser().parse_args(["image", "assemble", str(self.run)]))
            finalize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
