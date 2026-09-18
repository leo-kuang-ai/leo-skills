"""原子输入机制与真实拒绝路径；真实浏览器资格只用于非发布验证。"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from leo_ppt_generator.application.expression_pipeline import (
    ExpressionPipelineError, PipelineRequest, _digest, load_committed_input,
    run_expression_pipeline, selection_digest, write_atomic_input_generation,
)
from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.content_pack import compile_content_pack
from leo_ppt_generator.content_projection import precompile_binding, compute_materialization_binding_digest, binding_impact
from leo_ppt_generator.execution_pairing import pairing_identity
from leo_ppt_generator.templates import compose_design, DesignCompositionError, resolve_design_context

ROOT = Path(__file__).resolve().parents[1]


def transaction_inputs():
    from tests.expression_test_support import real_validation_inputs
    pack, resolver, context = real_validation_inputs()
    selection, pins, pages = {}, {}, []
    for page in pack["pages"]:
        layout = "builtin:layout:body-basic"
        binding = precompile_binding(page, context, layout, content_digest=pack["content_digest"],
            numbers=pack["numbers"], resolver=resolver, qualification_purpose="validation")
        if not binding["eligibility"]["qualified"]:
            raise AssertionError(binding["eligibility"])
        selection[page["page_id"]] = {"layout_id": layout, "binding": binding,
            "expression_binding_digest": binding["expression_binding_digest"],
            "materialization_binding_digest": binding["materialization_binding_digest"]}
        for pin in binding["effective"]["assets"]:
            pins[pin["asset_id"]] = pin
        pages.append({"page_id": page["page_id"], "page_no": page["number"], "page_role": page["narrative_role"], "slots": {}})
    selected = {"schema_version": 1, "kind": "deck-layout-selection", "status": "complete", "policy_version": "2",
        "content_digest": pack["content_digest"], "selection": selection,
        "selection_frozen": True, "selection_digest": selection_digest(selection)}
    design = compose_design(context["style"]["asset_id"], pages=pages, selection=selected, design_context=context, resolver=resolver)
    payload = {"request": {"run_id": "transaction-mechanism-test", "input_digest": "a" * 64,
        "catalog_generation": resolver.generation, "policy_revision": "expression-policy-v1",
        "purpose": "validation", "lane_matrix": {page["page_id"]: ["render:html"] for page in pack["pages"]}},
        "pack": pack, "lane_selections": {"render:html": selected}, "designs": {"render:html": design},
        "bindings": {"render:html": {pid: entry["binding"] for pid, entry in selection.items()}},
        "asset_pins": sorted(pins.values(), key=lambda pin: pin["asset_id"])}
    payload["impact"] = binding_impact({}, payload["bindings"])
    return payload, resolver, context, pages


class ExpressionPipelineTests(unittest.TestCase):
    def test_empty_or_partial_request_fails_closed(self):
        with self.assertRaises(ExpressionPipelineError):
            run_expression_pipeline(PipelineRequest({}, {}))
        with self.assertRaisesRegex(ExpressionPipelineError, "pipeline_request_schema_mismatch"):
            PipelineRequest.from_dict({"pack": {}, "design_context": {}, "backend": "image"})

    def test_route_runs_real_qualification_and_leaves_no_partial_run(self):
        from leo_ppt_generator.application.routes import generate
        payload, resolver, context, _ = transaction_inputs()
        with tempfile.TemporaryDirectory() as root:
            target = Path(root).resolve() / "run"
            request = PipelineRequest(payload["pack"], context, resolver.generation,
                payload["request"]["lane_matrix"], str(target), "real-rejection", str(resolver.builtin_root))
            with self.assertRaises(ExpressionPipelineError) as caught:
                generate(request, resolver=resolver)
            self.assertEqual(caught.exception.phase, "qualification")
            self.assertEqual(caught.exception.reason_code, "no_candidates")
            self.assertFalse(target.exists())

    def test_route_rejects_non_request_without_constructing_defaults(self):
        from leo_ppt_generator.application.routes import generate, RouteContractError
        with self.assertRaises(RouteContractError):
            generate({})

    def test_cli_only_forwards_request_and_has_one_pipeline_caller(self):
        import ast
        from leo_ppt_generator.cli import build_parser
        args = build_parser().parse_args(["generate", "--request", "request.json", "--json"])
        self.assertEqual(args.request, "request.json")
        callers = []
        for path in (ROOT / "runtime/src/leo_ppt_generator").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "run_expression_pipeline":
                    callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, ["runtime/src/leo_ppt_generator/application/routes.py"])


class InputGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.resolver, cls.context, cls.pages = transaction_inputs()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "run"
        self.value = deepcopy(self.payload)

    def write(self, checkpoint=None):
        return write_atomic_input_generation(self.root, self.value, generation=_digest(self.value), resolver=self.resolver, checkpoint=checkpoint)

    def test_real_pipeline_holds_source_lease_through_freeze_and_materialization(self):
        import shutil
        from leo_ppt_generator.library_migration import MigrationError, locked_publication, maintenance_path
        delivery = self.root.parent / "delivery"
        library = delivery / "leo-ppt-generator/template-library"
        shutil.copytree(self.resolver.builtin_root, library)
        resolver = AssetResolver(library=library, home=self.root.parent / "empty-user")
        request = PipelineRequest(self.value["pack"], self.context, resolver.generation,
            self.value["request"]["lane_matrix"], str(self.root), "maintenance-pipeline", str(library), purpose="validation")
        visited = []

        def attempt_publication(phase):
            visited.append(phase)
            with self.assertRaisesRegex(MigrationError, "migration_maintenance_lock_busy"):
                with locked_publication(delivery, plan_digest="a" * 64):
                    pass
            self.assertFalse(maintenance_path(delivery).exists())

        result = run_expression_pipeline(request, resolver=resolver, checkpoint=attempt_publication)
        self.assertEqual(result["status"], "html_validated")
        for phase in ("before_generation", "after_pointer", "after_run_index"):
            self.assertIn(phase, visited)
        for page in result["receipt_refs"]["render:html"].values():
            self.assertTrue(Path(page["artifact"]).is_file())
        with locked_publication(delivery, plan_digest="a" * 64):
            self.assertTrue(maintenance_path(delivery).exists())

    def test_staging_is_invisible_and_retry_is_idempotent_at_every_boundary(self):
        for phase in ("after_documents", "after_evidence", "before_generation", "before_pointer", "after_pointer"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory).resolve() / "run"
                def stop(actual):
                    if actual == phase: raise InterruptedError(phase)
                with self.assertRaises(InterruptedError): self.write(stop)
                if phase != "after_pointer":
                    with self.assertRaisesRegex(ExpressionPipelineError, "input_pointer_missing"):
                        load_committed_input(self.root)
                target = self.write()
                before = (target / "input-manifest.json").read_bytes()
                self.assertEqual(self.write(), target)
                self.assertEqual((target / "input-manifest.json").read_bytes(), before)
                self.assertEqual(load_committed_input(self.root)["payload"], self.value)

    def test_pointer_then_run_index_can_be_recovered_without_reselection(self):
        from leo_ppt_generator.application.run_index import RunIndex
        self.write()
        index = RunIndex.create(self.root, route="generate", runtime_identity="expression-policy-v1", run_id=self.value["request"]["run_id"])
        index.register_input_generation(_digest(self.value))
        before = index.snapshot()
        index.register_input_generation(_digest(self.value))
        self.assertEqual(before, index.snapshot())
        self.assertEqual(before["input_generation"], _digest(self.value))

    def test_evidence_closure_is_frozen_and_consumed_without_shared_library(self):
        from leo_ppt_generator.content_projection import verify_effective_binding
        target = self.write()
        frozen = AssetResolver.from_snapshot(target / "asset-snapshot")
        binding = next(iter(self.value["bindings"]["render:html"].values()))
        qualification = binding["eligibility"]["checks"]["qualification"]
        for reference in qualification["evidence_files"]:
            self.assertTrue((frozen.builtin_root / reference["path"]).is_file(), reference)
        page = self.value["pack"]["pages"][0]
        verify_effective_binding(binding, page, resolver=frozen)
        reference = qualification["evidence_files"][0]
        (frozen.builtin_root / reference["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "evidence_stale"):
            verify_effective_binding(binding, page, resolver=frozen)

    def test_claimed_qualification_without_frozen_evidence_is_rejected(self):
        from leo_ppt_generator.content_projection import verify_effective_binding
        binding = deepcopy(next(iter(self.value["bindings"]["render:html"].values())))
        del binding["eligibility"]["checks"]["qualification"]["receipt_payloads"]
        binding["materialization_binding_digest"] = compute_materialization_binding_digest(binding)
        with self.assertRaisesRegex(ValueError, "binding_qualification_evidence_missing"):
            verify_effective_binding(binding, self.value["pack"]["pages"][0], resolver=self.resolver)

    def test_real_html_outputs_are_receipted_and_single_page_drift_is_detected(self):
        from leo_ppt_generator.application.routes import generate
        from leo_ppt_generator.render.receipt import create_delivery_receipt, verify_delivery_receipt
        request = PipelineRequest(self.value["pack"], self.context, self.resolver.generation,
            self.value["request"]["lane_matrix"], str(self.root), "real-html-receipt",
            str(self.resolver.builtin_root), purpose="validation")
        result = generate(request, resolver=self.resolver)
        self.assertEqual(result["status"], "html_validated")
        created = create_delivery_receipt(self.root)
        artifacts = created["receipt"]["fingerprints"]["page_artifacts"]
        rows = result["receipt_refs"]["render:html"]
        for row in rows.values():
            for key in ("artifact", "receipt"):
                self.assertIn(Path(row[key]).relative_to(self.root).as_posix(), artifacts)
        self.assertTrue(verify_delivery_receipt(self.root)["fresh"])
        row = next(iter(rows.values()))
        Path(row["artifact"]).write_bytes(b"changed")
        changed = verify_delivery_receipt(self.root)
        self.assertEqual(changed["status"], "stale")
        self.assertEqual(changed["impact"]["scope"], "page")
        self.assertEqual(changed["impact"]["impacted_pages"], [1])

    def test_different_input_digest_and_missing_partial_data_fail_closed(self):
        self.write()
        self.value["request"]["input_digest"] = "b" * 64
        with self.assertRaisesRegex(ExpressionPipelineError, "input_generation_conflict"):
            self.write()
        for key in ("asset_pins", "lane_selections", "bindings", "designs"):
            incomplete = deepcopy(self.payload)
            incomplete.pop(key)
            with self.subTest(key=key), self.assertRaises(ExpressionPipelineError):
                write_atomic_input_generation(self.root, incomplete, generation=_digest(incomplete), resolver=self.resolver)

    def test_html_page_publication_recovers_at_render_and_publish_boundaries(self):
        from leo_ppt_generator.application.routes import generate
        from leo_ppt_generator.application.expression_pipeline import materialization_paths
        from leo_ppt_generator.render.receipt import create_delivery_receipt, verify_delivery_receipt
        for boundary in ("after_page_render", "after_page_publish"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve() / "run"
                request = PipelineRequest(self.value["pack"], self.context, self.resolver.generation,
                    self.value["request"]["lane_matrix"], str(root), "page-recovery",
                    str(self.resolver.builtin_root), purpose="validation")
                def stop(phase):
                    if phase == boundary:
                        raise InterruptedError(phase)
                with self.assertRaises(InterruptedError):
                    run_expression_pipeline(request, resolver=self.resolver, checkpoint=stop)
                artifact, sidecar = materialization_paths(root, "render:html", self.value["pack"]["pages"][0]["page_id"])
                self.assertEqual(artifact.exists(), boundary == "after_page_publish")
                self.assertEqual(sidecar.exists(), artifact.exists())
                before = artifact.stat().st_mtime_ns if artifact.exists() else None
                result = generate(request, resolver=self.resolver)
                self.assertEqual(result["status"], "html_validated")
                if before is not None:
                    self.assertEqual(artifact.stat().st_mtime_ns, before)
                create_delivery_receipt(root)
                self.assertTrue(verify_delivery_receipt(root)["fresh"])

    def test_committed_page_input_tamper_is_not_hidden_by_valid_pixels(self):
        from leo_ppt_generator.application.routes import generate
        from leo_ppt_generator.application.expression_pipeline import materialization_paths
        request = PipelineRequest(self.value["pack"], self.context, self.resolver.generation,
            self.value["request"]["lane_matrix"], str(self.root), "data-integrity",
            str(self.resolver.builtin_root), purpose="validation")
        generate(request, resolver=self.resolver)
        artifact, _ = materialization_paths(self.root, "render:html", self.value["pack"]["pages"][0]["page_id"])
        data = artifact.with_name("data.json")
        data.write_text('{"title":"altered"}')
        with self.assertRaisesRegex(ExpressionPipelineError, "materialization_input_mismatch"):
            generate(request, resolver=self.resolver)

    def test_pointer_missing_or_manifest_byte_drift_never_uses_loose_input_files(self):
        target = self.write()
        pointer = self.root / "input/current.json"
        pointer.unlink()
        with self.assertRaisesRegex(ExpressionPipelineError, "input_pointer_missing"):
            load_committed_input(self.root)
        self.write()
        (target / "asset-pins.json").write_text("[]")
        with self.assertRaisesRegex(ExpressionPipelineError, "input_generation_invalid"):
            load_committed_input(self.root)

    def test_generation_traversal_and_symlink_roots_rejected(self):
        with self.assertRaisesRegex(ExpressionPipelineError, "input_generation_digest_mismatch"):
            write_atomic_input_generation(self.root, self.value, generation="../../escape", resolver=self.resolver)
        self.root.parent.joinpath("outside").mkdir()
        self.root.symlink_to(self.root.parent / "outside", target_is_directory=True)
        with self.assertRaisesRegex(ExpressionPipelineError, "input_root_invalid"):
            self.write()


class ComposeFrozenSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.resolver, cls.context, cls.pages = transaction_inputs()

    def test_missing_selection_empty_pages_and_reselection_are_rejected(self):
        selected = self.payload["lane_selections"]["render:html"]
        for selection, pages in ((None, self.pages), (selected, []), (selected, [{**self.pages[0], "layout": "builtin:layout:other"}, self.pages[1]])):
            with self.assertRaisesRegex(DesignCompositionError, "selection_frozen_mismatch"):
                compose_design(self.context["style"]["asset_id"], selection=selection, pages=pages, design_context=self.context, resolver=self.resolver)

    def test_selection_digest_is_order_independent_and_rejects_legacy_fields(self):
        entries = self.payload["lane_selections"]["render:html"]["selection"]
        self.assertEqual(selection_digest(entries), selection_digest(dict(reversed(list(entries.items())))))
        legacy = deepcopy(entries)
        next(iter(legacy.values()))["binding_digest"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "binding_schema_mismatch"):
            selection_digest(legacy)
