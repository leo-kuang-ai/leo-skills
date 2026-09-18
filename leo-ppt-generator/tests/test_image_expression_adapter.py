"""本地真实 HTTP 协议验证；明确不能作为真实 Provider、关系或视觉通过证据。"""
from copy import deepcopy
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from PIL import Image

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.backend_execution import BackendExecutionContext
from leo_ppt_generator.content_pack import compile_content_pack
from leo_ppt_generator.image_deck.recipe import validate_recipe, project_recipe, ImageRecipeError
from leo_ppt_generator.image_deck.expression_adapter import export_provider_image, verify_provider_export, ImageExportError
from leo_ppt_generator.qualification import digest, file_reference

ROOT = Path(__file__).resolve().parents[1]


class ImageRecipeTests(unittest.TestCase):
    def setUp(self):
        resolver = AssetResolver(library=ROOT / "template-library")
        self.recipe = resolver.resolve("builtin:recipe:body-basic")["data"]
        self.layout = resolver.resolve("builtin:layout:body-basic")["data"]

    def test_complete_projection_preserves_content_and_never_claims_output_quality(self):
        pack = compile_content_pack((ROOT / "evals/fixtures/expression-first-validation-master.md").read_text(), master_path="validation.md")
        page = deepcopy(pack["pages"][0])
        before = deepcopy(page)
        projected = project_recipe(self.recipe, page=page, layout=self.layout, theme={"background": "#fff"}, numbers=pack["numbers"])
        self.assertEqual(projected["expression"], page["expression"])
        self.assertEqual(projected["content"]["items"], page["items"])
        self.assertEqual(projected["semantic_output_status"], "not_run")
        self.assertEqual(before, page)

    def test_unknown_placeholders_missing_slots_and_type_mismatch_fail_closed(self):
        for mutation in ("placeholder", "missing", "type", "unknown"):
            recipe = deepcopy(self.recipe)
            if mutation == "placeholder": recipe["prompt_skeleton"] = "{content.__class__}"
            elif mutation == "missing": recipe["slot_map"].pop("chart")
            elif mutation == "type": recipe["slot_map"]["chart"]["content_type"] = "media"
            else: recipe["css"] = "display:none"
            with self.subTest(mutation=mutation), self.assertRaises(ImageRecipeError):
                validate_recipe(recipe, self.layout)
        layout = deepcopy(self.layout)
        del layout["slots"]["chart"]["content_type"]
        with self.assertRaisesRegex(ImageRecipeError, "image_recipe_slot_type_mismatch"):
            validate_recipe(self.recipe, layout)

    def test_all_five_relations_prepare_both_image_probes_without_provider_calls(self):
        from leo_ppt_generator.capability_probes import image_probe_inputs
        cases = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())
        before = deepcopy(cases)
        inputs = image_probe_inputs(library_root=ROOT / "template-library", cases=cases)
        self.assertEqual(len(inputs), 10, inputs)
        self.assertTrue(all(row["status"] == "not_run" for row in inputs))
        for case in cases["cases"]:
            for probe in ("positive", "negative"):
                row = next(row for row in inputs if row["case_id"] == case["case_id"] and row["probe"] == probe)
                content = row["input"]["prompt"].split("正文与事实：", 1)[1].split("\n表达合同：", 1)[0]
                self.assertEqual(json.loads(content), case[probe])
        self.assertEqual(cases, before)


class TableImageRecipeTests(unittest.TestCase):
    def setUp(self):
        from tests.test_page_expression_contract import content, declaration
        from leo_ppt_generator.content_pack import compile_page_expression
        from leo_ppt_generator.config.backend_contract import BackendRegistry
        from leo_ppt_generator.templates import resolve_design_context
        self.resolver = AssetResolver(library=ROOT / "template-library")
        self.layout = self.resolver.resolve("builtin:layout:p25-spec-table")["data"]
        self.recipe = self.resolver.resolve("builtin:recipe:p25-spec-table")["data"]
        self.pack = content()
        self.page = self.pack["pages"][0]
        self.page.update(number=1, narrative_role="data", required_text=["逐项核对", "6小时", "2小时"])
        self.page["structures"]["table"] = {"columns": ["维度", "甲", "乙"],
            "rows": [["时长", "6小时", "2小时"], ["期间", "7月", "8月"], ["样本", "12项", "待核对"]]}
        self.page["expression"] = compile_page_expression(self.pack, self.page["page_id"], **declaration("comparison"))
        self.context = resolve_design_context("清爽专业风", resolver=self.resolver)
        self.contract = BackendRegistry.default().create_contract("qianxing", mode="generate")

    def project(self, page=None, recipe=None):
        return project_recipe(recipe or self.recipe, page=page or self.page, layout=self.layout,
            theme={}, numbers=self.pack["numbers"])

    def binding(self, page):
        from leo_ppt_generator.content_projection import precompile_binding
        return precompile_binding(page, self.context, self.layout["asset_id"], backend="image",
            content_digest="a" * 64, numbers=self.pack["numbers"], resolver=self.resolver,
            provider_contract=self.contract)

    def test_table_projection_keeps_facts_unknowns_and_long_title_without_granting_qualification(self):
        before = deepcopy(self.page)
        projected = self.project()
        self.assertEqual(projected["content"]["structures"], self.page["structures"])
        self.assertEqual(projected["content"]["numbers"], self.pack["numbers"])
        self.assertEqual(projected["expression"], self.page["expression"])
        self.assertEqual(projected["semantic_output_status"], "not_run")
        self.assertEqual(self.page, before)
        page = deepcopy(self.page)
        page["claim"] = "这是表格标题" * 12
        binding = self.binding(page)
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertEqual(binding["eligibility"]["checks"]["qualification"]["status"], "unverified")
        self.assertFalse(any("overflow" in gap or "image_recipe_" in gap for gap in binding["eligibility"]["hard_failures"]))

    def test_table_capacity_rejected_in_projection_and_real_candidate_precompile(self):
        for mutation, reason in (("rows-max", "image_recipe_count_over_max:rows"),
                                 ("rows-min", "image_recipe_count_below_min:rows"),
                                 ("columns-max", "image_recipe_count_over_max:columns"),
                                 ("cell-text", "image_recipe_text_overflow:cell"),
                                 ("cell-lines", "image_recipe_lines_over_max:cell")):
            page = deepcopy(self.page)
            table = page["structures"]["table"]
            if mutation == "rows-max": table["rows"] *= 3
            elif mutation == "rows-min": table["rows"].pop()
            elif mutation == "columns-max":
                table["columns"].append("额外列")
                for row in table["rows"]: row.append("额外值")
            elif mutation == "cell-text": table["rows"][0][0] = "长" * 49
            else: table["rows"][0][0] = "第一行\n第二行"
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ImageRecipeError, reason): self.project(page)
                binding = self.binding(page)
                self.assertFalse(binding["eligibility"]["qualified"])
                self.assertTrue(any(reason in gap for gap in binding["eligibility"]["hard_failures"]), binding)

    def test_mapping_paths_shapes_and_conflicting_sources_fail_closed(self):
        for mutation in ("missing", "ragged", "type", "conflict"):
            page = deepcopy(self.page)
            table = page["structures"]["table"]
            if mutation == "missing": del table["columns"]
            elif mutation == "ragged": table["rows"][0].pop()
            elif mutation == "type": table["rows"][0][0] = {"text": "绕过"}
            else: page["structures"]["fields"] = {"rows": [["不同来源"]]}
            with self.subTest(mutation=mutation), self.assertRaises(ImageRecipeError): self.project(page)
        page = deepcopy(self.page)
        page["structures"]["fields"] = page["structures"].pop("table")
        self.assertEqual(self.project(page)["content"]["structures"], page["structures"])
        for mutation in ("path", "missing-path", "projection"):
            recipe = deepcopy(self.recipe)
            if mutation == "path": recipe["slot_map"]["cell"]["input_path"] = "../../secret"
            elif mutation == "missing-path": del recipe["slot_map"]["cell"]["input_path"]
            else: recipe["slot_map"]["cell"]["projection"] = "claim"
            with self.subTest(mutation=mutation), self.assertRaises(ImageRecipeError): self.project(recipe=recipe)

    def test_capacity_changes_follow_layout_owner_and_cannot_be_hidden_by_recipe(self):
        from leo_ppt_generator.image_deck.recipe import validate_recipe_content
        layout = deepcopy(self.layout)
        layout["slots"]["rows"]["count_max"] = 2
        with self.assertRaisesRegex(ImageRecipeError, "image_recipe_count_over_max:rows"):
            validate_recipe_content(self.recipe, page=self.page, layout=layout)
        layout = deepcopy(self.layout)
        layout["slots"]["cell"]["max_chars"] = 2
        with self.assertRaisesRegex(ImageRecipeError, "image_recipe_text_overflow:cell"):
            validate_recipe_content(self.recipe, page=self.page, layout=layout)
        recipe = deepcopy(self.recipe)
        recipe["slot_map"]["cell"]["max_chars"] = 10000
        with self.assertRaisesRegex(ImageRecipeError, "image_recipe_schema_mismatch"):
            validate_recipe_content(recipe, page=self.page, layout=self.layout)


class ProviderProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        buffer = io.BytesIO()
        Image.new("RGB", (128, 96), "#765432").save(buffer, "PNG")
        body = json.dumps({"created": 12345, "data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]}).encode()
        self.requests = []
        requests = self.requests
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("x-request-id", "local-protocol-only")
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.context = BackendExecutionContext("openai-compatible", "gpt-image-2", "generate",
            {"OPENAI_API_KEY": "local-protocol-only", "OPENAI_BASE_URL": f"http://127.0.0.1:{self.server.server_port}/v1"}, 10, 0, "a" * 64, {})
        self.recipe_input = {"kind": "image-recipe-input", "canvas": {"width": 2560, "height": 1440},
            "prompt": "本地协议测试，不是真实任务", "recipe_id": "builtin:recipe:body-basic", "page_id": "test-only"}

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def export(self, **kwargs):
        return export_provider_image(self.recipe_input, context=self.context, output_root=self.root, **kwargs)

    def test_real_http_preserves_response_id_and_bytes_and_retry_is_idempotent(self):
        receipt = self.export()
        self.assertEqual(receipt["request_id"], "local-protocol-only")
        self.assertEqual(receipt["evidence_source"], "local-protocol-test")
        self.assertEqual(receipt["purpose"], "capability-probe")
        self.assertEqual(receipt["semantic_status"], "not_run")
        self.assertEqual(receipt, self.export())
        self.assertEqual(len(self.requests), 1)
        (self.root / "page.png").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            verify_provider_export(receipt, root=self.root)

    def test_interrupted_request_is_not_automatically_reissued(self):
        def stop(phase):
            if phase == "after_artifact": raise InterruptedError(phase)
        with self.assertRaises(InterruptedError): self.export(checkpoint=stop)
        with self.assertRaisesRegex(ImageExportError, "provider_outcome_unknown"):
            self.export()
        self.assertEqual(len(self.requests), 1)

    def test_resealed_unrelated_artifact_is_not_the_provider_response(self):
        receipt = self.export()
        Image.new("RGB", (2560, 1440), "#abcdef").save(self.root / "page.png")
        receipt["artifact"] = file_reference(self.root, "page.png")
        receipt["out_sha256"] = receipt["artifact"]["sha256"]
        receipt["receipt_digest"] = digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        with self.assertRaisesRegex(ImageExportError, "provider_export_pixels_mismatch"):
            verify_provider_export(receipt, root=self.root)

    def test_resealed_response_or_identity_cannot_borrow_other_image_bytes(self):
        receipt = self.export()
        for mutation in ("response", "request_id", "http_status", "model", "postprocess"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(receipt)
                if mutation == "response":
                    wrong = io.BytesIO()
                    Image.new("RGB", (128, 96), "#ffffff").save(wrong, "PNG")
                    path = self.root / "changed-response.json"
                    path.write_text(json.dumps({"data": [{"b64_json": base64.b64encode(wrong.getvalue()).decode()}]}))
                    changed["response"] = file_reference(self.root, path.name)
                elif mutation == "request_id": changed["request_id"] = None
                elif mutation == "http_status": changed["http_status"] = 503
                elif mutation == "model": changed["model"] = "another-model"
                else: changed["postprocess"]["operation"] = "crop"
                changed["receipt_digest"] = digest({k: v for k, v in changed.items() if k != "receipt_digest"})
                with self.assertRaises(ImageExportError):
                    verify_provider_export(changed, root=self.root)

    def test_local_protocol_receipt_cannot_enter_image_capability_pool(self):
        from leo_ppt_generator.qualification import file_reference
        from leo_ppt_generator.raster_oracle import verify_image_probe_source, RasterOracleError
        self.export()
        with self.assertRaisesRegex(RasterOracleError, "image_real_provider_evidence_required"):
            verify_image_probe_source(root=self.root, fixture={}, relation="independent", artifact={},
                render_input={}, provider_reference=file_reference(self.root, "page.png.provider.json"), dependencies={})

    def test_requested_contract_cannot_borrow_other_provider_evidence(self):
        from leo_ppt_generator.qualification import verify_provider_qualification
        self.export()
        reference = file_reference(self.root, "page.png.provider.json")
        qualification = {"receipt_payloads": [{"lane": "image", "probes": {
            name: {"provider_receipt": reference} for name in ("positive", "negative")}}]}
        for contract, reason in ((None, "evidence_provider_contract_missing"),
                                 ("b" * 64, "evidence_provider_contract_mismatch"),
                                 ("a" * 64, "image_real_provider_evidence_required")):
            with self.subTest(contract=contract), self.assertRaisesRegex(ValueError, reason):
                verify_provider_qualification(qualification, library_root=self.root, contract_sha256=contract)

    def test_missing_contract_digest_is_rejected_after_receipt_resealing(self):
        receipt = self.export()
        del receipt["contract_sha256"]
        receipt["receipt_digest"] = digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        with self.assertRaisesRegex(ImageExportError, "provider_contract_digest_invalid"):
            verify_provider_export(receipt, root=self.root)

    def test_changed_input_and_symlink_output_fail_before_new_request(self):
        self.export()
        self.recipe_input["prompt"] += " changed"
        with self.assertRaisesRegex(ImageExportError, "provider_input_conflict"):
            self.export()
        self.assertEqual(len(self.requests), 1)
        linked = self.root / "linked"
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ImageExportError, "provider_output_path_invalid"):
            export_provider_image(self.recipe_input, context=self.context, output_root=linked)
