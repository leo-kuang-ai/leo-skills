"""E1 DELIVERY-GATE 指纹收据的行为测试（gamma M0）。

用 tmp 目录构造 mini run fixture（不依赖真实图像）覆盖可观察行为：

- 五类指纹落盘（churn 文件 timing.json 与收据自身不进指纹）；
- 篡改单页 → verify stale + 波及页＝该页；
- 本地资产漂移 → 全册波及；QA 报告漂移 → 仅 QA 重跑建议；
- 收据缺失 → readiness 收据门按 not_run 披露且不得 accepted；
- 同输入两次 create 指纹一致；
- CLI envelope 语义（fresh=completed/exit0 通道，stale=blocked）。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.cli import (  # noqa: E402
    _delivery_readiness,
    _status_next_action,
    build_parser,
    dispatch,
)
from leo_ppt_generator.render.receipt import (  # noqa: E402
    FINGERPRINT_CLASSES,
    RECEIPT_RELATIVE_PATH,
    ReceiptError,
    create_delivery_receipt,
    verify_delivery_receipt,
)
from leo_ppt_generator.storage import sha256_file  # noqa: E402


def _make_mini_run(root: Path) -> None:
    """复用真实生成链的冻结输入与两页 HTML 导出；视觉验收保持未运行。"""
    from tests.expression_test_support import copy_real_html_run
    copy_real_html_run(root)
    (root / "final").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "final/validation-summary.json").write_text(json.dumps({
        "passed": True, "quality_gates": {
            "visual_render": {"status": "passed", "source": "real-chromium"},
            "manual_visual_acceptance": {"status": "not_run"}}}), encoding="utf-8")
    (root / "reports/visual-qa.json").write_text('{"status": "not_run"}', encoding="utf-8")
    (root / "reports/timing.json").write_text('{"stages": []}', encoding="utf-8")


def _input_root(root):
    from leo_ppt_generator.application.expression_pipeline import committed_input_root
    return committed_input_root(root)


def _page_artifact(root, number):
    from leo_ppt_generator.application.expression_pipeline import load_committed_input, materialization_paths
    page = load_committed_input(root)["payload"]["pack"]["pages"][number - 1]
    return materialization_paths(root, "render:html", page["page_id"])[0]


class MiniRunTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_root = Path(self._tmp.name).resolve() / "run"
        _make_mini_run(self.run_root)


class CreateCollectsFiveFingerprintClasses(MiniRunTestCase):
    def test_create_collects_five_fingerprint_classes_and_excludes_churn(self):
        result = create_delivery_receipt(self.run_root)
        receipt = result["receipt"]
        self.assertEqual(receipt["schema_version"], 1)
        self.assertEqual(receipt["kind"], "delivery_receipt")
        self.assertEqual(set(receipt["fingerprints"]), set(FINGERPRINT_CLASSES))
        fingerprints = receipt["fingerprints"]
        self.assertEqual(len(fingerprints["page_artifacts"]), 4)
        self.assertIn("input/current.json", fingerprints["local_assets"])
        self.assertTrue(fingerprints["template_style_sources"])
        self.assertEqual(set(fingerprints["qa_reports"]),
                         {"reports/visual-qa.json", "final/validation-summary.json"})
        self.assertTrue(any(p.startswith("previews/") for p in fingerprints["render_previews"]))
        # churn 与收据自身不得进入任何指纹类。
        for items in fingerprints.values():
            self.assertNotIn("reports/timing.json", items)
            self.assertNotIn(RECEIPT_RELATIVE_PATH.as_posix(), items)
        # 指纹值即流式 sha256；R-3 裁决字段在场。
        self.assertEqual(
            fingerprints["page_artifacts"][_page_artifact(self.run_root, 2).relative_to(self.run_root).as_posix()],
            sha256_file(_page_artifact(self.run_root, 2)),
        )
        self.assertEqual(
            receipt["linked_assets"],
            {"sources_manifest": None, "beta_sidecars": None},
        )
        self.assertIsNone(receipt["builder_id"])


class TamperedPageIsStaleWithPageImpact(MiniRunTestCase):
    def test_tampered_single_page_reports_stale_and_infers_that_page(self):
        create_delivery_receipt(self.run_root)
        _page_artifact(self.run_root, 2).write_bytes(
            b"PAGE2-TAMPERED"
        )
        outcome = verify_delivery_receipt(self.run_root)
        self.assertEqual(outcome["status"], "stale")
        self.assertFalse(outcome["fresh"])
        self.assertEqual(len(outcome["changed"]), 1)
        entry = outcome["changed"][0]
        self.assertEqual(entry["class"], "page_artifacts")
        self.assertEqual(entry["path"], _page_artifact(self.run_root, 2).relative_to(self.run_root).as_posix())
        self.assertEqual(entry["change"], "modified")
        self.assertEqual(outcome["impact"]["scope"], "page")
        self.assertEqual(outcome["impact"]["impacted_pages"], [2])

    def test_deleted_page_artifact_is_also_drift(self):
        create_delivery_receipt(self.run_root)
        _page_artifact(self.run_root, 1).unlink()
        outcome = verify_delivery_receipt(self.run_root)
        self.assertEqual(outcome["status"], "stale")
        self.assertEqual(outcome["changed"][0]["change"], "missing")
        self.assertEqual(outcome["impact"]["impacted_pages"], [1])


class AssetDriftImpactsWholeDeck(MiniRunTestCase):
    def _template(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        resolver = AssetResolver.from_snapshot(_input_root(self.run_root) / "asset-snapshot")
        return Path(resolver.resolve("builtin:template:body-basic")["path"]).with_name("page.html")

    def test_frozen_template_drift_invalidates_receipt(self):
        create_delivery_receipt(self.run_root)
        self._template().write_text("changed")
        result = verify_delivery_receipt(self.run_root)
        self.assertFalse(result["fresh"])
        self.assertEqual(result["reason_code"], "input_generation_invalid")

    def test_frozen_template_removal_blocks_creation(self):
        self._template().unlink()
        with self.assertRaisesRegex(ReceiptError, "input_generation_invalid"):
            create_delivery_receipt(self.run_root)

    def test_unused_run_local_templates_are_not_a_fallback(self):
        create_delivery_receipt(self.run_root)
        unused = self.run_root / "template-library/canonical/templates/unused/page.html"
        unused.parent.mkdir(parents=True)
        unused.write_text("unselected")
        self.assertTrue(verify_delivery_receipt(self.run_root)["fresh"])

    def test_missing_pointer_rejects_loose_design_and_templates(self):
        (self.run_root / "input/current.json").unlink()
        (self.run_root / "input/resolved-design.json").write_text('{"pages": []}')
        with self.assertRaisesRegex(ReceiptError, "input_pointer_missing"):
            create_delivery_receipt(self.run_root)

    def test_frozen_template_symlink_blocks_creation(self):
        template = self._template()
        template.unlink()
        template.symlink_to(self.run_root / "final/validation-summary.json")
        with self.assertRaisesRegex(ReceiptError, "input_generation_invalid"):
            create_delivery_receipt(self.run_root)

    def test_local_asset_drift_impacts_whole_deck(self):
        create_delivery_receipt(self.run_root)
        (_input_root(self.run_root) / "page-content-pack.json").write_text(
            '{"slides": ["changed"]}', encoding="utf-8"
        )
        outcome = verify_delivery_receipt(self.run_root)
        self.assertFalse(outcome["fresh"])
        self.assertEqual(outcome["impact"]["scope"], "deck")
        self.assertEqual(outcome["impact"]["impacted_pages"], [])
        self.assertTrue(outcome["impact"]["recommended_actions"])

    def test_style_source_drift_impacts_whole_deck(self):
        create_delivery_receipt(self.run_root)
        (_input_root(self.run_root) / "resolved-design.json").write_text(
            "# style brief v2", encoding="utf-8"
        )
        outcome = verify_delivery_receipt(self.run_root)
        self.assertEqual(outcome["impact"]["scope"], "deck")

    def test_qa_report_drift_recommends_qa_rerun_only(self):
        create_delivery_receipt(self.run_root)
        (self.run_root / "reports" / "visual-qa.json").write_text(
            '{"qa": "rerun"}', encoding="utf-8"
        )
        outcome = verify_delivery_receipt(self.run_root)
        self.assertEqual(outcome["status"], "stale")
        self.assertEqual(outcome["impact"]["scope"], "qa_only")
        self.assertEqual(outcome["impact"]["impacted_pages"], [])
        self.assertTrue(
            any("重跑 QA" in action for action in outcome["impact"]["recommended_actions"])
        )
        self.assertFalse(
            any("artifact revision" in action for action in outcome["impact"]["recommended_actions"])
        )


class MissingReceiptGateDisclosure(MiniRunTestCase):
    def test_missing_receipt_disclosed_as_not_run_and_blocks_accepted(self):
        run = {"output_dir": str(self.run_root), "status": "completed"}
        readiness = _delivery_readiness(run)
        self.assertEqual(readiness["status"], "acceptance_pending")
        self.assertIn("delivery_receipt", readiness["missing_gates"])
        self.assertEqual(readiness["receipt_gate"]["status"], "not_run")
        self.assertEqual(
            readiness["receipt_gate"]["reason_code"], "delivery_receipt_missing"
        )
        next_action = _status_next_action(run)
        self.assertNotEqual(next_action["kind"], "none")

    def test_stale_receipt_blocks_accepted_and_is_disclosed(self):
        create_delivery_receipt(self.run_root)
        (_input_root(self.run_root) / "page-content-pack.json").write_text(
            '{"slides": ["changed"]}', encoding="utf-8"
        )
        run = {"output_dir": str(self.run_root), "status": "completed"}
        readiness = _delivery_readiness(run)
        self.assertEqual(readiness["status"], "acceptance_pending")
        self.assertIn("delivery_receipt", readiness["unverified_gates"])
        self.assertEqual(readiness["receipt_gate"]["status"], "blocked")
        self.assertEqual(readiness["receipt_gate"]["impact"]["scope"], "deck")

    def test_fresh_receipt_does_not_replace_visual_acceptance(self):
        create_delivery_receipt(self.run_root)
        run = {"output_dir": str(self.run_root), "status": "completed"}
        readiness = _delivery_readiness(run)
        self.assertEqual(readiness["status"], "acceptance_pending")
        self.assertEqual(readiness["receipt_gate"]["status"], "passed")
        self.assertNotEqual(_status_next_action(run)["kind"], "none")


class DeterministicFingerprints(MiniRunTestCase):
    def test_two_creates_over_same_input_yield_identical_fingerprints(self):
        first = create_delivery_receipt(self.run_root)["receipt"]
        second = create_delivery_receipt(self.run_root)["receipt"]
        self.assertEqual(first["fingerprints"], second["fingerprints"])

    def test_receipt_rejects_old_missing_and_mixed_binding_summary(self):
        from copy import deepcopy
        created = create_delivery_receipt(self.run_root)
        for mutation in ("missing", "old", "mixed"):
            receipt = deepcopy(created["receipt"])
            if mutation == "missing":
                receipt.pop("content_binding")
            elif mutation == "old":
                receipt["content_binding"] = {"binding_digest": "a" * 64}
            else:
                receipt["content_binding"]["binding_digests"] = {"one": "a" * 64}
            Path(created["path"]).write_text(json.dumps(receipt))
            with self.subTest(mutation=mutation):
                result = verify_delivery_receipt(self.run_root)
                self.assertEqual(result["status"], "invalid")
                self.assertEqual(result["reason_code"], "binding_schema_mismatch")


class CliEnvelopeSemantics(MiniRunTestCase):
    def _dispatch(self, *argv):
        args = build_parser().parse_args(argv)
        return dispatch(args)

    def test_create_and_verify_via_cli(self):
        created = self._dispatch(
            "delivery", "receipt", "create", str(self.run_root)
        )
        self.assertEqual(created["status"], "completed")
        self.assertEqual(created["reason_code"], "delivery_receipt_created")
        self.assertTrue(created["artifact_refs"])
        verified = self._dispatch(
            "delivery", "receipt", "verify", str(self.run_root)
        )
        self.assertEqual(verified["status"], "completed")
        self.assertEqual(verified["reason_code"], "delivery_receipt_fresh")
        self.assertEqual(verified["delivery_receipt"]["fresh"], True)
        self.assertEqual(verified["protocol"], "leo-ppt-machine/v1")

    def test_tampered_verify_is_blocked_envelope(self):
        self._dispatch("delivery", "receipt", "create", str(self.run_root))
        _page_artifact(self.run_root, 2).write_bytes(
            b"EVIL"
        )
        verified = self._dispatch(
            "delivery", "receipt", "verify", str(self.run_root)
        )
        self.assertEqual(verified["status"], "blocked")
        self.assertEqual(verified["reason_code"], "delivery_receipt_stale")
        self.assertEqual(verified["delivery_receipt"]["impact"]["impacted_pages"], [2])

    def test_verify_without_receipt_reports_missing(self):
        verified = self._dispatch(
            "delivery", "receipt", "verify", str(self.run_root)
        )
        self.assertEqual(verified["status"], "blocked")
        self.assertEqual(verified["reason_code"], "delivery_receipt_missing")

    def test_churn_from_command_logging_keeps_receipt_fresh(self):
        """create/verify 自身会重写 reports/timing.json——收据必须保持 fresh。"""

        self._dispatch("delivery", "receipt", "create", str(self.run_root))
        for _ in range(2):
            verified = self._dispatch(
                "delivery", "receipt", "verify", str(self.run_root)
            )
            self.assertEqual(verified["reason_code"], "delivery_receipt_fresh")


if __name__ == "__main__":
    unittest.main()
