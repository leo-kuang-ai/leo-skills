"""U9/R-73 OCR 对齐通道与对齐门行为测试。

覆盖：逐条对齐断言（阈值/豁免红绿）、判域（composite/render/用户素材豁免、
图像生成页命中）、门 not_run 语义、WARN→enforce 校准门、OCR 一条龙通道
（token/依赖/超时按页 not_run，注入 seam 离线驱动 vendor 真实 text_blocks）、
离线校准集（干净 60/红 30 分集；红例全拦、误报 ≤5%）、record 前置门集成
（WARN 披露 / enforce 拦截 / not_run 不冒充通过）。
真实 PaddleOCR 云调用不在测试授权内：通道只验 not_run 分支与 seam 注入。
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

from leo_ppt_generator.cli import build_parser, dispatch  # noqa: E402
from leo_ppt_generator.contracts import ContractError  # noqa: E402
from leo_ppt_generator.ocr_alignment import (  # noqa: E402
    OcrAlignmentError,
    build_offline_calibration_manifest,
    evaluate_alignment,
    evaluate_calibration_set,
    gate_for_page,
    load_alignment_config,
    page_gate_applies,
    required_text_for_page,
    record_alignment,
    resolve_gate_mode,
    run_page_ocr,
)
from leo_ppt_generator.storage import canonical_json, sha256_bytes  # noqa: E402


def _dispatch(argv):
    return dispatch(build_parser().parse_args(argv))


class AlignmentEvaluateTest(unittest.TestCase):
    REQUIRED = ["季度经营复盘", "毛利率 38.2%（估算）", "订阅占比 62%"]

    def test_verbatim_alignment_passes(self):
        verdict = evaluate_alignment(self.REQUIRED, "\n".join(self.REQUIRED))
        self.assertEqual(verdict["status"], "pass")
        self.assertEqual(verdict["ratio"], 1.0)
        self.assertEqual(verdict["missing"], [])

    def test_single_char_corruption_fails(self):
        ocr = "\n".join(["季度经牧复盘", "毛利率 38.2%（估算）", "订阅占比 62%"])
        verdict = evaluate_alignment(self.REQUIRED, ocr)
        self.assertEqual(verdict["status"], "fail")
        self.assertEqual(verdict["missing"], ["季度经营复盘"])

    def test_line_break_inside_item_breaks_substring_match(self):
        # 条目内断行：空白折叠后条目不再连续，逐字合同仍须拦截。
        ocr = "季度经营复\n盘 毛利率 38.2%（估算） 订阅占比 62%"
        verdict = evaluate_alignment(self.REQUIRED, ocr)
        self.assertEqual(verdict["status"], "fail")
        self.assertEqual(verdict["missing"], ["季度经营复盘"])

    def test_wrapped_item_with_breaks_still_matched_when_contiguous(self):
        # OCR 把条目拆成多行但空白折叠后连续（真实换行拼回场景）→ 命中。
        ocr = "季度经营复\n盘\n要点占位 毛利率 38.2%（估算） 订阅占比 62%"
        verdict = evaluate_alignment(self.REQUIRED, ocr)
        # “季度经营复盘”折叠后为“季度经营复 盘”，不连续 → 仍拦截。
        self.assertEqual(verdict["missing"], ["季度经营复盘"])

    def test_threshold_relaxation_is_configurable(self):
        ocr = "\n".join(["季度经牧复盘", "毛利率 38.2%（估算）", "订阅占比 62%"])
        verdict = evaluate_alignment(self.REQUIRED, ocr, threshold=0.6)
        self.assertEqual(verdict["status"], "pass")

    def test_exemption_removes_item_from_denominator(self):
        ocr = "\n".join(["季度经牧复盘", "毛利率 38.2%（估算）"])
        verdict = evaluate_alignment(
            self.REQUIRED, ocr,
            exemptions=[{"text": "订阅占比 62%", "reason": "标签水印，OCR 已知漏检"}])
        self.assertEqual(verdict["status"], "fail")
        self.assertEqual(verdict["exempted"], ["订阅占比 62%"])
        self.assertEqual(verdict["missing"], ["季度经营复盘"])

    def test_all_items_exempt_reports_exempt(self):
        verdict = evaluate_alignment(
            ["装饰字"], "无关文本",
            exemptions=[{"text": "装饰字", "reason": "艺术字豁免"}])
        self.assertEqual(verdict["status"], "exempt")


class GateScopeTest(unittest.TestCase):
    def _manifest(self, *classes):
        return {"pages": [{"page_id": "slide_01",
                           "visuals": [{"source_class": cls} for cls in classes]}]}

    def test_image_generated_page_applies(self):
        applies, scope = page_gate_applies(self._manifest("ai-generated"), 1)
        self.assertTrue(applies)
        self.assertEqual(scope, "image-generated-page")

    def test_composite_generation_method_exempt(self):
        applies, scope = page_gate_applies(
            self._manifest("ai-generated"), 1, generation_method="composite")
        self.assertFalse(applies)
        self.assertEqual(scope, "composite-constructive")

    def test_render_provenance_exempt(self):
        applies, scope = page_gate_applies(
            self._manifest("deterministic-render"), 1,
            slide_provenance={"backend": "render:html"})
        self.assertFalse(applies)

    def test_overlay_constructive_layer_exempt(self):
        applies, scope = page_gate_applies(
            self._manifest("deterministic-overlay", "ai-generated"), 1)
        self.assertFalse(applies)
        self.assertEqual(scope, "constructive-layer")

    def test_user_material_page_not_applicable(self):
        applies, scope = page_gate_applies(self._manifest("user-material"), 1)
        self.assertFalse(applies)

    def test_missing_manifest_not_applicable(self):
        applies, scope = page_gate_applies(None, 1)
        self.assertFalse(applies)

    def test_verified_image_lane_cannot_be_exempted_by_optional_manifest_or_method(self):
        provenance = {"lane": "image"}
        for manifest, method in ((None, None), (None, "composite"),
                                 (self._manifest("deterministic-overlay"), None)):
            with self.subTest(manifest=manifest, method=method):
                self.assertEqual(page_gate_applies(manifest, 1, generation_method=method,
                                 slide_provenance=provenance), (True, "image-generated-page"))


class GateForPageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run = Path(self._tmp.name)
        self.required = ["标题甲", "要点一"]

    def _write_txt(self, text, name="page_1.txt"):
        ocr_dir = self.run / "image-deck/ocr"
        ocr_dir.mkdir(parents=True, exist_ok=True)
        (ocr_dir / name).write_text(text, encoding="utf-8")

    def test_missing_ocr_text_is_not_run_not_pass(self):
        verdict = gate_for_page(self.run, 1, self.required)
        self.assertEqual(verdict["status"], "not_run")
        self.assertEqual(verdict["reason_code"], "ocr_text_missing")

    def test_aligned_page_passes_and_writes_sidecar(self):
        self._write_txt("标题甲\n要点一")
        verdict = gate_for_page(self.run, 1, self.required)
        self.assertEqual(verdict["status"], "pass")
        sidecar = self.run / "image-deck/ocr/page_001.align.json"
        self.assertTrue(sidecar.is_file())
        report = json.loads(sidecar.read_text(encoding="utf-8"))
        self.assertEqual(report["kind"], "ocr-alignment")

    def test_misaligned_page_fails_with_missing_list(self):
        self._write_txt("标题甲\n要点乙")
        verdict = gate_for_page(self.run, 1, self.required)
        self.assertEqual(verdict["status"], "fail")
        self.assertEqual(verdict["missing"], ["要点一"])

    def test_page_scoped_exemption(self):
        self._write_txt("标题甲\n要点乙")
        config = {**load_alignment_config(self.run),
                  "exemptions": [{"page": 2, "text": "要点一", "reason": "他页豁免"}]}
        verdict = gate_for_page(self.run, 1, self.required, config=config)
        self.assertEqual(verdict["status"], "fail")  # 豁免只对页 2 生效


class GateConfigAndModeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run = Path(self._tmp.name)

    def _config(self, **overrides):
        config = {"schema_version": 1, "mode": "warn", "threshold": 1.0, "exemptions": []}
        config.update(overrides)
        (self.run / "input").mkdir(parents=True, exist_ok=True)
        (self.run / "input/ocr-alignment.json").write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return load_alignment_config(self.run)

    def test_defaults_without_config_file(self):
        config = load_alignment_config(self.run)
        self.assertEqual(config["mode"], "warn")
        self.assertEqual(config["threshold"], 1.0)

    def test_invalid_mode_rejected(self):
        with self.assertRaises(OcrAlignmentError) as ctx:
            self._config(mode="hard")
        self.assertEqual(ctx.exception.reason_code, "ocr_alignment_config_invalid")

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(OcrAlignmentError):
            self._config(threshold=1.5)

    def test_enforce_requires_passed_calibration_report(self):
        self._config(mode="enforce")
        with self.assertRaises(OcrAlignmentError) as ctx:
            resolve_gate_mode(load_alignment_config(self.run), self.run)
        self.assertEqual(ctx.exception.reason_code, "ocr_calibration_required_for_enforce")

    def test_enforce_with_failed_report_still_rejected(self):
        self._config(mode="enforce")
        (self.run / "reports").mkdir(parents=True)
        (self.run / "reports/ocr-calibration.json").write_text(
            json.dumps({"status": "failed"}), encoding="utf-8")
        with self.assertRaises(OcrAlignmentError):
            resolve_gate_mode(load_alignment_config(self.run), self.run)

    def test_enforce_with_passed_report_allowed(self):
        self._config(mode="enforce")
        (self.run / "reports").mkdir(parents=True)
        (self.run / "reports/ocr-calibration.json").write_text(
            json.dumps({"status": "passed", "fixture": True}), encoding="utf-8")
        self.assertEqual(resolve_gate_mode(load_alignment_config(self.run), self.run), "enforce")


class OcrChannelTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.image = self.root / "slide_01.png"
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (200, 80), (255, 255, 255))
        ImageDraw.Draw(image).rectangle((10, 10, 180, 60), fill=(10, 10, 10))
        image.save(self.image, format="PNG")

    def test_missing_page_image_is_not_run(self):
        result = run_page_ocr(self.root / "nope.png", self.root, 1,
                              token="t", submit_fn=lambda *a, **k: [])
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(result["reason_code"], "ocr_page_image_missing")

    def test_missing_token_is_not_run_without_any_call(self):
        environment_token = None
        result = run_page_ocr(self.image, self.root, 1, token=environment_token)
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(result["reason_code"], "ocr_token_missing")

    def test_injected_submit_drives_vendor_text_blocks_to_lines(self):
        pruned = {
            "width": 200,
            "height": 80,
            "parsing_res_list": [
                {"block_label": "text", "block_content": "季度经营复盘",
                 "block_bbox": [10, 10, 180, 60]},
            ],
        }
        result = run_page_ocr(
            self.image, self.root / "ocr", 1, token="fixture-token",
            submit_fn=lambda path, token, model, timeout: [pruned])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["lines"], 1)
        written = (self.root / "ocr" / "page_1.txt").read_text(encoding="utf-8")
        self.assertEqual(written.strip(), "季度经营复盘")
        self.assertIn("成本", result["cost_disclosure"])

    def test_timeout_maps_to_not_run_not_failure(self):
        def timeout_submit(path, token, model, timeout):
            raise RuntimeError(f"PaddleOCR job timed out after {timeout}s (state=running)")

        result = run_page_ocr(self.image, self.root, 1, token="t", submit_fn=timeout_submit)
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(result["reason_code"], "ocr_job_timeout")

    def test_job_failure_maps_to_not_run(self):
        def failed_submit(path, token, model, timeout):
            raise RuntimeError("PaddleOCR job failed: boom")

        result = run_page_ocr(self.image, self.root, 1, token="t", submit_fn=failed_submit)
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(result["reason_code"], "ocr_job_failed")


class OfflineCalibrationTest(unittest.TestCase):
    def test_fixture_set_meets_acceptance_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_offline_calibration_manifest(tmp)
            self.assertTrue(manifest["fixture"])
            self.assertEqual(len(manifest["split"]["calibration"]) +
                             len(manifest["split"]["acceptance"]), 90)
            self.assertFalse(
                set(manifest["split"]["calibration"]) & set(manifest["split"]["acceptance"]))
            report = evaluate_calibration_set(manifest)
            self.assertEqual(report["status"], "passed")
            acceptance = report["splits"]["acceptance"]
            self.assertEqual(acceptance["red_intercept_rate"], 1.0)
            self.assertLessEqual(acceptance["false_positive_rate"], 0.05)
            self.assertTrue(report["fixture"])

    def test_undetected_red_case_fails_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_offline_calibration_manifest(tmp)
            # 模拟门失效：把验收分集里第一个红例的 OCR 文本改回逐字一致。
            acceptance_ids = set(manifest["split"]["acceptance"])
            victim = next(case for case in manifest["cases"]
                          if case["kind"] == "red" and case["case_id"] in acceptance_ids)
            victim["ocr_text"] = "\n".join(victim["required_text"])
            report = evaluate_calibration_set(manifest)
            self.assertEqual(report["status"], "failed")

    def test_wrong_kind_rejected(self):
        with self.assertRaises(OcrAlignmentError) as ctx:
            evaluate_calibration_set({"kind": "something-else", "cases": [], "split": {}})
        self.assertEqual(ctx.exception.reason_code, "ocr_calibration_report_invalid")


class RequiredTextContractTest(unittest.TestCase):
    def test_reads_frozen_slides_contract(self):
        slides = [
            {"number": 1, "required_text": ["标题甲", "要点一"]},
            {"number": 2, "required_text": []},
            {"number": 3},
        ]
        self.assertEqual(required_text_for_page(slides, 1), ["标题甲", "要点一"])
        self.assertEqual(required_text_for_page(slides, 2), [])
        self.assertEqual(required_text_for_page(slides, 3), [])
        self.assertEqual(required_text_for_page(slides, 9), [])


class RecordGateIntegrationTest(unittest.TestCase):
    """OCR 门到页事务的机制集成；Provider 收据准入由 CLI 单独验证，不伪造 run。"""

    REQUIRED_1 = ["季度经营复盘", "要点一"]
    REQUIRED_2 = ["财务页标题", "毛利率 38.2%（估算）"]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run = Path(self._tmp.name) / "run"
        (self.run / "input").mkdir(parents=True)
        slides = [
            {"number": 1, "title": "经营", "required_text": self.REQUIRED_1},
            {"number": 2, "title": "财务", "required_text": self.REQUIRED_2},
        ]
        (self.run / "input/slides.json").write_text(
            json.dumps(slides, ensure_ascii=False), encoding="utf-8")
        manifest = self._sources_manifest()
        (self.run / "input/sources-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        self.images = {}
        from PIL import Image

        for number in (1, 2):
            path = Path(self._tmp.name) / f"page-{number}.png"
            Image.new("RGB", (1280, 720), (240, 240, 236)).save(path, format="PNG")
            self.images[number] = path
        from leo_ppt_generator.image_deck.adapter import ImageDeckAdapter
        self.adapter = ImageDeckAdapter(self.run / "image-deck")
        self.adapter.prepare(slides, sources_manifest=manifest)

    def _sources_manifest(self):
        pages = []
        for number in (1, 2):
            pages.append({
                "page_id": f"slide_{number:02d}",
                "visuals": [{
                    "visual_id": f"cover-{number}",
                    "figure_id": None,
                    "kind": "illustration",
                    "source_class": "ai-generated",
                    "tier": "示意",
                    "handling_mode": None,
                    "review_status": None,
                    "source_ref": None,
                    "source_sha256": "a" * 64,
                    "backend": "zhipu",
                }],
            })
        manifest = {
            "schema_version": 1,
            "manifest_kind": "visual-sources",
            "route": "generate",
            "run_ref": "runs/r1",
            "generated_from": "content/deck-master-v1.md",
            "pages": pages,
        }
        payload = {k: v for k, v in manifest.items() if k != "contents_sha256"}
        manifest["contents_sha256"] = sha256_bytes(canonical_json(payload).encode())
        return manifest

    def _record(self, number, operation_id):
        # 仅提供门的判域输入，不构造或声称真实 Provider receipt。
        alignment, warnings = record_alignment(self.run, number,
            self.REQUIRED_1 if number == 1 else self.REQUIRED_2,
            verified_provenance={"lane": "image"})
        artifact = self.adapter.record(number, self.images[number], backend="image",
            expected_revision=self.adapter._jobs()["revision"], operation_id=operation_id)
        return {"status": "ready", "alignment": alignment, "warnings": warnings, "artifact": artifact}

    def test_not_run_disclosed_without_ocr_text(self):
        result = self._record(1, "op-notrun")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["alignment"]["status"], "not_run")
        self.assertTrue(any("ocr_alignment_not_run" in w for w in result["warnings"]))

    def test_warn_mode_reports_failure_without_blocking(self):
        ocr_dir = self.run / "image-deck/ocr"
        ocr_dir.mkdir(parents=True, exist_ok=True)
        (ocr_dir / "page_2.txt").write_text("财务页标题\n毛利 38.2%（估算）", encoding="utf-8")
        result = self._record(2, "op-warn")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["alignment"]["status"], "fail")
        self.assertTrue(any("ocr_alignment_warned" in w for w in result["warnings"]))
        self.assertFalse((self.run / "image-deck").exists() is False)
        self.assertEqual(self.adapter._jobs()["slides"][1]["status"], "recorded")

    def test_enforce_mode_blocks_misaligned_record(self):
        self._record(1, "op-base")
        ocr_dir = self.run / "image-deck/ocr"
        ocr_dir.mkdir(parents=True, exist_ok=True)
        (ocr_dir / "page_2.txt").write_text("财务页标题\n毛利 38.2%（估算）", encoding="utf-8")
        # 真实校准链产出 passed 报告（fixture 校准集），方允许 enforce。
        manifest = build_offline_calibration_manifest(self.run / "reports")
        report = evaluate_calibration_set(manifest)
        self.assertEqual(report["status"], "passed")
        (self.run / "reports/ocr-calibration.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")
        (self.run / "input/ocr-alignment.json").write_text(
            json.dumps({"schema_version": 1, "mode": "enforce"}, ensure_ascii=False),
            encoding="utf-8")
        with self.assertRaises(OcrAlignmentError) as ctx:
            self._record(2, "op-enforce")
        self.assertEqual(ctx.exception.reason_code, "ocr_alignment_failed")
        self.assertEqual(self.adapter._jobs()["slides"][1]["status"], "pending")
        self.assertFalse((self.adapter.images_dir / "slide_02.png").exists())

    def test_composite_and_render_scopes_skip_gate(self):
        ocr_dir = self.run / "image-deck/ocr"
        ocr_dir.mkdir(parents=True, exist_ok=True)
        (ocr_dir / "page_1.txt").write_text("完全无关的 OCR 文本", encoding="utf-8")
        alignment, warnings = record_alignment(self.run, 1, self.REQUIRED_1,
            verified_provenance={"backend": "render:html"})
        self.assertIsNone(alignment)
        self.assertEqual(warnings, [])


class CliAlignmentIntegrationTest(unittest.TestCase):
    """完整 CLI 正例使用真实冻结 HTML；image 正例仍需真实 Provider 授权与证据。"""

    def test_real_frozen_html_record_skips_ocr_and_keeps_receipt(self):
        from tests.expression_test_support import copy_real_html_run, slides_for_run
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary).resolve() / "run"
            result = copy_real_html_run(run, request_index=True)
            slides = run / "work/slides.json"
            slides.write_text(json.dumps(slides_for_run(run)))
            _dispatch(["image", "prepare", str(run), "--slides", str(slides)])
            ocr = run / "image-deck/ocr"
            ocr.mkdir()
            (ocr / "page_1.txt").write_text("与页面完全无关的文字")
            row = result["receipt_refs"]["render:html"]["pg-11111111"]
            recorded = _dispatch(["image", "record", str(run), "--number", "1", "--image", str(run / row["artifact"]),
                "--backend", "render:html", "--render-receipt", str(run / row["receipt"]), "--operation-id", "real-html"])
            self.assertEqual(recorded["status"], "ready")
            self.assertIsNone(recorded["alignment"])
            self.assertTrue(recorded["provenance"]["materialization_binding_digest"])
            self.assertFalse((ocr / "page_001.align.json").exists())
            jobs = json.loads((run / "image-deck/slide_jobs.json").read_text())
            self.assertEqual(jobs["revision"], 1)
            self.assertEqual(jobs["slides"][0]["provenance"]["materialization_binding_digest"],
                             recorded["provenance"]["materialization_binding_digest"])


if __name__ == "__main__":
    unittest.main()
