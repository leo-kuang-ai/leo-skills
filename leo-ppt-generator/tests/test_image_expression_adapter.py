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
