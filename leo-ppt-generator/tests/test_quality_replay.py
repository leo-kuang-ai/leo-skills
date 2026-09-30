"""验证回放工具的真实文件边界；测试数据不构成 R-85 或旧链业务基线。"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from leo_ppt_generator.qualification import digest, environment_fingerprint, file_reference
from leo_ppt_generator.quality_replay import (
    ReplayError, evaluate_quality_replay, freeze_legacy_baseline, paired_environment_compatibility,
    validate_legacy_image_export, validate_paired_rebaseline_plan, validate_replay_dataset, verify_legacy_baseline,
)
from leo_ppt_generator.quality_metrics import _visual_evidence
from leo_ppt_generator.storage import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]


def dataset():
    cases = []
    for family in range(3):
        for copy in range(2):
            deck = f"deck-{family}-{copy}"
            for task in range(10):
                cases.append({"case_id": f"{deck}-{task}", "deck_id": deck, "page_id": f"pg-{task}",
                    "lane": "render:html", "theme_family": f"family-{family}", "task": f"task-{task}",
                    "expected": "solvable", "material": {"path": deck + ".md", "sha256": "a" * 64},
                    "request": {"path": deck + ".json", "sha256": "a" * 64}, "run": "runs/" + deck})
    body = {"schema_version": 1, "kind": "r85-heldout", "owner": "test-mechanism-only", "origin": "fixture",
            "families": [f"family-{i}" for i in range(3)], "tasks": [f"task-{i}" for i in range(10)], "cases": cases}
    body["dataset_digest"] = digest(body)
    return body


class ReplayDatasetTests(unittest.TestCase):
    def test_delivery_uses_explicit_representatives_and_a_separate_run_prefix(self):
        from leo_ppt_generator.quality_replay import replay_cases, replay_run_path
        data = dataset()
        image = {**data["cases"][0], "case_id": "image-representative", "lane": "image"}
        data["cases"].append(image)
        selected = [data["cases"][0]["case_id"], image["case_id"]]
        plan = {"phase": "U6-B", "representatives": selected, "run_prefix": "delivery"}
        self.assertEqual([case["case_id"] for case in replay_cases(plan, data)], selected)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.assertEqual(replay_run_path(root, plan, image), root / "delivery" / image["run"])
            self.assertNotEqual(replay_run_path(root, plan, image),
                                replay_run_path(root, {**plan, "run_prefix": "staging"}, image))

    def test_representative_duplicates_missing_lane_and_path_escape_fail_closed(self):
        from leo_ppt_generator.quality_replay import replay_cases, replay_run_path
        data = dataset()
        case_id = data["cases"][0]["case_id"]
        for representatives in ([case_id, case_id], [case_id], ["unknown"], []):
            with self.subTest(representatives=representatives), self.assertRaises(ReplayError):
                replay_cases({"phase": "U6-B", "representatives": representatives}, data)
        for prefix in ("../escape", "/absolute", ".", "a//b"):
            with self.subTest(prefix=prefix), self.assertRaises(ReplayError):
                replay_run_path(Path.cwd(), {"run_prefix": prefix}, data["cases"][0])

    def test_fixed_axes_and_independent_page_denominators(self):
        data = dataset()
        coverage = validate_replay_dataset(data)
        self.assertEqual((coverage["matrix_cells"], coverage["pages"], coverage["decks"]), (30, 60, 6))
        data["cases"] = [row for row in data["cases"] if row["deck_id"] != "deck-0-1"]
        data["cases"] += [{**row, "case_id": row["case_id"] + "-image", "lane": "image"} for row in data["cases"][:10]]
        data["dataset_digest"] = digest({k: v for k, v in data.items() if k != "dataset_digest"})
        with self.assertRaisesRegex(ReplayError, "r85_coverage_incomplete"):
            validate_replay_dataset(data)

    def test_relabelled_and_duplicate_cases_do_not_fill_coverage(self):
        for mutation in ("duplicate", "relabel", "digest"):
            data = dataset()
            if mutation == "duplicate":
                data["cases"].append(deepcopy(data["cases"][0]))
            elif mutation == "relabel":
                row = {**data["cases"][0], "case_id": "other", "lane": "image", "task": "task-1"}
                data["cases"].append(row)
            data["dataset_digest"] = digest({k: v for k, v in data.items() if k != "dataset_digest"}) if mutation != "digest" else "f" * 64
            with self.subTest(mutation=mutation), self.assertRaises(ReplayError):
                validate_replay_dataset(data)

    def test_old_handwritten_scores_cannot_grant_visual_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            atomic_write_json(root / "qa/visual-replay.json", {"status": "passed", "input_generation": "a" * 64,
                "scores": dict.fromkeys(("fidelity", "relation", "readability", "focus"), 5), "reviewer": "test"})
            self.assertEqual(_visual_evidence(root, "a" * 64, {})["status"], "error")

    def test_missing_baseline_is_blocked_with_persistable_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            atomic_write_json(root / "dataset.json", dataset())
            plan = {"schema_version": 1, "kind": "quality-replay-plan", "phase": "U6-A",
                "dataset": file_reference(root, "dataset.json"), "baseline": {"path": "absent.json", "sha256": "b" * 64},
                "reviews": None, "stage_receipt": None, "delivery_convergence": None, "user_defect": None,
                "run_prefix": "staging", "representatives": None, "observations": None}
            plan["plan_digest"] = digest(plan)
            atomic_write_json(root / "plan.json", plan)
            result = evaluate_quality_replay(root, file_reference(root, "plan.json"))
            self.assertEqual(result["status"], "blocked", result)
            self.assertFalse(result["publication_ready"])
            self.assertEqual(result["coverage"]["pages"], 60)
            self.assertEqual(result["receipt_digest"], digest({k: v for k, v in result.items() if k != "receipt_digest"}))


class PairedEnvironmentTests(unittest.TestCase):
    def setUp(self):
        from leo_ppt_generator.qualification import is_execution_source
        package = ROOT / "runtime/src/leo_ppt_generator"
        self.environment = environment_fingerprint()
        self.sources = {path.relative_to(package).as_posix(): file_reference(package, path.relative_to(package).as_posix())["sha256"]
                        for path in package.rglob("*") if path.is_file() and is_execution_source(path.relative_to(package).as_posix())}
        self.baseline = {"environment": deepcopy(self.environment),
                         "source_snapshot": {"archive/leo_ppt_generator/" + path: sha for path, sha in self.sources.items()}}

    def change_source(self, path):
        self.sources[path] = "f" * 64
        self.baseline["source_snapshot"]["archive/leo_ppt_generator/" + path] = "f" * 64
        self.baseline["environment"]["execution_source_digest"] = digest(self.sources)

    def test_oracle_only_change_preserves_renderer_but_records_distinct_execution_identity(self):
        self.change_source("relation_oracle.py")
        result = paired_environment_compatibility(self.baseline, self.environment)
        self.assertEqual(result["status"], "compatible")
        self.assertTrue(result["execution_source_changed"])
        self.assertNotEqual(result["baseline_execution_source_digest"], result["current_execution_source_digest"])
        self.assertEqual(result["baseline_renderer_source_digest"], result["current_renderer_source_digest"])

    def test_renderer_transition_requires_real_rebaseline_and_cannot_be_blessed_by_a_flag(self):
        self.change_source("render/page.py")
        self.baseline["transition"] = {"status": "passed"}
        with self.assertRaisesRegex(ReplayError, "paired_renderer_source_rebaseline_required"):
            paired_environment_compatibility(self.baseline, self.environment)

    def test_provider_adapter_transition_requires_real_rebaseline(self):
        self.change_source("_vendor/codex_ppt/image_providers/openai_compatible.py")
        with self.assertRaisesRegex(ReplayError, "paired_renderer_source_rebaseline_required"):
            paired_environment_compatibility(self.baseline, self.environment)

    def test_provider_sdk_version_drift_stays_blocked(self):
        for name in ("openai", "httpx"):
            current = deepcopy(self.environment)
            current["packages"][name] = "different-version"
            with self.subTest(name=name), self.assertRaisesRegex(ReplayError, "paired_environment_mismatch"):
                paired_environment_compatibility(self.baseline, current)

    def test_browser_font_package_vendor_and_platform_drift_stay_blocked(self):
        for key in ("browser_binaries", "font_files", "packages", "vendor_files", "release"):
            current = deepcopy(self.environment)
            current[key] = "changed"
            with self.subTest(key=key), self.assertRaisesRegex(ReplayError, "paired_environment_mismatch"):
                paired_environment_compatibility(self.baseline, current)

    def test_provider_sources_and_sdk_versions_are_pinned(self):
        from leo_ppt_generator.qualification import is_execution_source
        self.assertTrue(is_execution_source("_vendor/codex_ppt/image_providers/factory.py"))
        self.assertTrue(is_execution_source("_vendor/codex_ppt/image_providers/openai_compatible.py"))
        self.assertIn("openai", self.environment["packages"])
        self.assertIn("httpx", self.environment["packages"])
        self.assertTrue(any(path.startswith("_vendor/codex_ppt/image_providers/") for path in self.sources))

    def test_resigned_source_identity_and_duplicate_execution_owner_are_rejected(self):
        self.baseline["environment"]["execution_source_digest"] = "0" * 64
        with self.assertRaisesRegex(ReplayError, "baseline_execution_snapshot_incomplete"):
            paired_environment_compatibility(self.baseline, self.environment)
        self.baseline["environment"] = deepcopy(self.environment)
        self.baseline["source_snapshot"]["other/leo_ppt_generator/render/page.py"] = self.sources["render/page.py"]
        with self.assertRaisesRegex(ReplayError, "baseline_execution_source_ambiguous"):
            paired_environment_compatibility(self.baseline, self.environment)


class ReplayRejectionTests(unittest.TestCase):
    def test_self_contained_rejection_replays_after_evidence_freeze_without_original_root(self):
        from dataclasses import asdict, replace
        import shutil
        from tests.expression_test_support import real_validation_inputs
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest
        from leo_ppt_generator.quality_replay import execute_replay_request
        pack, original, context = real_validation_inputs()
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "evidence"
            shutil.copytree(original.builtin_root, root / "library")
            resolver = AssetResolver(library=root / "library")
            request = PipelineRequest(pack, context, resolver.generation,
                {page["page_id"]: ["render:html"] for page in pack["pages"]},
                str(root / "run"), "portable-rejection", str(root / "library"))
            atomic_write_json(root / "request.json", asdict(request))
            case = {"deck_id": "negative", "run": "run", "request": file_reference(root, "request.json")}
            first = execute_replay_request(root, case, request, execute=True, library_root=root / "library", self_contained=True)
            self.assertEqual(first["reason_code"], "no_candidates")
            receipt = json.loads((root / "run/qa/replay-execution.json").read_text())
            self.assertEqual(receipt["library_root"], "library")
            frozen = parent / "frozen"
            root.rename(frozen)
            request = replace(request, run_root=str(frozen / "run"))
            self.assertEqual(execute_replay_request(frozen, case, request, self_contained=True), first)

    def test_real_qualification_rejection_survives_read_only_replay_and_rejects_resigned_tampering(self):
        from dataclasses import asdict
        from tests.expression_test_support import real_validation_inputs
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest
        from leo_ppt_generator.quality_replay import execute_replay_request
        pack, resolver, context = real_validation_inputs()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            request = PipelineRequest(pack, context, resolver.generation,
                {page["page_id"]: ["render:html"] for page in pack["pages"]},
                str(root / "run"), "negative-replay", str(resolver.builtin_root))
            atomic_write_json(root / "request.json", asdict(request))
            case = {"deck_id": "negative", "run": "run", "request": file_reference(root, "request.json")}
            first = execute_replay_request(root, case, request, execute=True, library_root=resolver.builtin_root)
            self.assertEqual(first["reason_code"], "no_candidates")
            self.assertFalse((root / "run/input/current.json").exists())
            hashes_before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            replayed = execute_replay_request(root, case, request, execute=False)
            self.assertEqual(first, replayed)
            with self.assertRaisesRegex(ReplayError, "capability_u6a_external_execution_library"):
                execute_replay_request(root, case, request, execute=False, self_contained=True)
            self.assertEqual(hashes_before, {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()})
            receipt_path = root / "run/qa/replay-execution.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["failure"]["reason_code"] = "constraints_unsatisfied"
            receipt["receipt_digest"] = digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
            atomic_write_json(receipt_path, receipt)
            with self.assertRaisesRegex(ReplayError, "replay_rejection_not_reproducible"):
                execute_replay_request(root, case, request, execute=False)


class UserOutcomeMechanismTests(unittest.TestCase):
    def test_only_paired_recorded_observations_contribute_to_metrics(self):
        from leo_ppt_generator.quality_replay import evaluate_user_outcomes
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "before.png").write_bytes(b"mechanism-before-artifact")
            (root / "after.png").write_bytes(b"mechanism-after-artifact")
            (root / "interview.txt").write_text("仅用于验证观测消费机制，不登记为真实用户结果。")
            before, after = file_reference(root, "before.png"), file_reference(root, "after.png")
            refs = []
            for phase, artifact, correct, rework in (("before", before, False, 2), ("after", after, True, 0)):
                atomic_write_json(root / (phase + ".json"), {"case_id": "case", "participant_id": "pseudonym", "phase": phase,
                    "artifact": artifact, "conclusion_correct": correct, "task_success": correct, "rework_count": rework,
                    "recorded_at": "2026-09-15T00:00:00Z", "source": file_reference(root, "interview.txt"), "adjudicator": "test"})
                refs.append(file_reference(root, phase + ".json"))
            document = {"kind": "user-outcome-observations", "schema_version": 1, "origin": "recorded-user", "owner": "mechanism-test",
                        "observations": refs}
            atomic_write_json(root / "observations.json", document)
            cases, baseline = [{"case_id": "case", "status": "passed", "artifact": after}], [{"case_id": "case", "artifact": before}]
            result = evaluate_user_outcomes(root, file_reference(root, "observations.json"), cases=cases, baseline_pages=baseline)
            self.assertEqual(result["paired_denominator"], 1)
            self.assertEqual(result["delta"], {"conclusion_recognition_rate": 1, "task_success_rate": 1, "rework_rate": -1})
            document["observations"] = refs[:1]
            atomic_write_json(root / "observations.json", document)
            with self.assertRaisesRegex(ReplayError, "user_outcome_pair_incomplete"):
                evaluate_user_outcomes(root, file_reference(root, "observations.json"), cases=cases, baseline_pages=baseline)
            document["origin"] = "fixture"
            atomic_write_json(root / "observations.json", document)
            self.assertEqual(evaluate_user_outcomes(root, file_reference(root, "observations.json"), cases=cases, baseline_pages=baseline)["status"], "not_run")


class LegacyBaselineByteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.expression_test_support import copy_real_html_run
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name).resolve()
        run = cls.root / "render"
        result = copy_real_html_run(run)
        sources = {}
        package = ROOT / "runtime/src/leo_ppt_generator"
        from leo_ppt_generator.qualification import is_execution_source
        for path in package.rglob("*"):
            relative = path.relative_to(package).as_posix()
            if path.is_file() and is_execution_source(relative):
                target = cls.root / "baseline/source/leo_ppt_generator" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                reference = file_reference(cls.root, target.relative_to(cls.root).as_posix())
                sources[reference["path"]] = reference["sha256"]
        template = next((run / "input/generations").glob("*/asset-snapshot/builtin/canonical/templates/body-basic/page.html"))
        ref = file_reference(cls.root, template.relative_to(cls.root).as_posix())
        sources[ref["path"]] = ref["sha256"]
        material = cls.root / "material.md"
        material.write_bytes((ROOT / "evals/fixtures/expression-first-validation-master.md").read_bytes())
        pages = []
        for pid, row in result["receipt_refs"]["render:html"].items():
            artifact = run / row["artifact"]
            receipt = json.loads((run / row["receipt"]).read_text())
            selected = {"template_id": receipt["template_id"], "input": file_reference(cls.root, (artifact.parent / "data.json").relative_to(cls.root).as_posix())}
            selection = "selection-" + pid + ".json"
            atomic_write_json(cls.root / selection, selected)
            pages.append({"case_id": pid, "deck_id": "byte-test", "page_id": pid, "lane": "render:html", "theme_family": "test",
                "material": file_reference(cls.root, "material.md"), "selection": file_reference(cls.root, selection),
                "artifact": file_reference(cls.root, artifact.relative_to(cls.root).as_posix()),
                "receipt": file_reference(cls.root, (run / row["receipt"]).relative_to(cls.root).as_posix()), "provider_contract_digest": None})
        # 这里只测试现有导出字节的封存器，未将该临时描述登记为 U12 旧链证据。
        cls.body = {"schema_version": 1, "kind": "legacy-visual-baseline",
            "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_snapshot": sources, "dirty_hashes": {}, "capture_mode": "reconstructed-historical",
            "environment": environment_fingerprint(), "pages": pages}

    def descriptor(self, suffix, body=None):
        path = suffix + ".json"
        atomic_write_json(self.root / path, body or self.body)
        return file_reference(self.root, path)

    def test_real_png_receipt_and_complete_execution_source_freeze_idempotently(self):
        reference = freeze_legacy_baseline(self.root, self.descriptor("valid"), "qa/frozen-baseline.json")
        self.assertEqual(len(verify_legacy_baseline(self.root, reference)["pages"]), 2)
        self.assertEqual(reference, freeze_legacy_baseline(self.root, self.descriptor("valid"), "qa/frozen-baseline.json"))

    def test_missing_source_and_duplicate_artifact_are_rejected(self):
        for mutation in ("missing-source", "missing-raster-extractor", "reused-output", "wrong-receipt"):
            body = deepcopy(self.body)
            if mutation == "missing-source":
                body["source_snapshot"] = {p: sha for p, sha in body["source_snapshot"].items() if not p.endswith("render/page.py")}
            elif mutation == "missing-raster-extractor":
                body["source_snapshot"] = {p: sha for p, sha in body["source_snapshot"].items() if not p.endswith("raster_text.swift")}
            elif mutation == "reused-output":
                body["pages"][1]["artifact"] = body["pages"][0]["artifact"]
            else:
                body["pages"][1]["receipt"] = body["pages"][0]["receipt"]
            with self.subTest(mutation=mutation), self.assertRaises(ReplayError):
                freeze_legacy_baseline(self.root, self.descriptor(mutation, body), "qa/" + mutation + ".json")

    def test_changed_byte_hash_and_symlink_cannot_be_frozen(self):
        body = deepcopy(self.body)
        key = next(iter(body["source_snapshot"]))
        body["source_snapshot"][key] = "0" * 64
        with self.assertRaises(ValueError):
            freeze_legacy_baseline(self.root, self.descriptor("stale", body), "qa/stale.json")
        link = self.root / "link.json"
        link.symlink_to(self.root / "material.md")
        with self.assertRaises(ValueError):
            verify_legacy_baseline(self.root, {"path": "link.json", "sha256": "a" * 64})


class HistoricalBridgeTests(unittest.TestCase):
    def transport_fixture(self, root):
        """只测试归档协议的合成字节；不登记为真实 Provider 调用或业务证据。"""
        import base64
        import io
        from PIL import Image, ImageOps
        contract = {"provider": "mechanism-fixture", "model": "mechanism-fixture-model"}
        request = {"model": contract["model"], "prompt": "归档协议测试", "n": 1, "size": "auto"}
        raw = io.BytesIO()
        original = Image.new("RGB", (16, 9), "#765432")
        original.save(raw, "PNG")
        original.save(root / "provider-image.bin", "PNG")
        ImageOps.pad(original, (2560, 1440), method=Image.Resampling.LANCZOS, color="#FFFFFF").save(root / "page.png")
        atomic_write_json(root / "request.json", request)
        atomic_write_json(root / "response.json", {"data": [{"b64_json": base64.b64encode(raw.getvalue()).decode()}]})
        atomic_write_json(root / "contract.json", contract)
        (root / "material.md").write_text("测试材料")
        (root / "prompt.txt").write_text(request["prompt"])
        selection = {"page_id": "pg-old", "material": file_reference(root, "material.md"),
                     "request": file_reference(root, "request.json"), "provider_contract": file_reference(root, "contract.json"),
                     "prompt_source": file_reference(root, "prompt.txt"), "theme_family": "test-theme"}
        atomic_write_json(root / "selection.json", selection)
        receipt = {"schema_version": 1, "kind": "provider-export-receipt", "status": "succeeded", "lane": "image",
                   "evidence_source": "provider-http", "request_id": "mechanism-test", "http_status": 200,
                   "provider": contract["provider"], "model": contract["model"],
                   "contract_sha256": file_reference(root, "contract.json")["sha256"],
                   "page_id": "pg-old", "artifact": file_reference(root, "page.png"),
                   "provider_image": file_reference(root, "provider-image.bin"), "response": file_reference(root, "response.json"),
                   "request": file_reference(root, "request.json"), "out_sha256": file_reference(root, "page.png")["sha256"],
                   "width": 2560, "height": 1440,
                   "postprocess": {"operation": "contain", "background": "#FFFFFF", "source_size": [16, 9], "output_size": [2560, 1440]}}
        receipt["receipt_digest"] = digest(receipt)
        atomic_write_json(root / "receipt.json", receipt)
        source = root / "source/image_providers/openai_compatible.py"
        source.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "runtime/src/leo_ppt_generator/_vendor/codex_ppt/image_providers/openai_compatible.py", source)
        body = {"schema_version": 1, "kind": "legacy-image-export", "source_revision": "a" * 40,
                "capture_mode": "reconstructed-historical", "page_id": "pg-old", "selection": file_reference(root, "selection.json"),
                "material": file_reference(root, "material.md"), "provider_contract": file_reference(root, "contract.json"),
                "receipt": file_reference(root, "receipt.json"),
                "source_snapshot": {source.relative_to(root).as_posix(): file_reference(root, source.relative_to(root).as_posix())["sha256"]}}
        body["export_digest"] = digest(body)
        atomic_write_json(root / "legacy-image.json", body)
        return body

    def test_historical_transport_protocol_has_no_dependency_on_new_bindings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.transport_fixture(root)
            verified = validate_legacy_image_export(root, file_reference(root, "legacy-image.json"))
            self.assertEqual(verified["artifact"], file_reference(root, "page.png"))
            self.assertEqual(verified["capture_mode"], "reconstructed-historical")

    def test_historical_transport_rejects_resigned_new_bindings_page_contract_and_prompt(self):
        for mutation in ("binding", "page", "contract", "prompt", "missing-response"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                body = self.transport_fixture(root)
                receipt = json.loads((root / "receipt.json").read_text())
                if mutation == "binding": receipt["expression_binding_digest"] = "a" * 64
                elif mutation == "page": receipt["page_id"] = "pg-wrong"
                elif mutation == "contract": receipt["contract_sha256"] = "b" * 64
                elif mutation == "prompt": (root / "prompt.txt").write_text("changed")
                else: (root / "response.json").unlink()
                receipt["receipt_digest"] = digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
                atomic_write_json(root / "receipt.json", receipt)
                body["receipt"] = file_reference(root, "receipt.json")
                body["export_digest"] = digest({k: v for k, v in body.items() if k != "export_digest"})
                atomic_write_json(root / "legacy-image.json", body)
                with self.assertRaises(ValueError):
                    validate_legacy_image_export(root, file_reference(root, "legacy-image.json"))

    def test_legacy_image_protocol_test_is_blocked_without_new_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for name, body in (("selection.json", {"page_id": "pg-old"}),
                               ("material.json", {"body": "old"}),
                               ("contract.json", {"provider": "qianxing", "model": "gpt-image-1"}),
                               ("receipt.json", {"schema_version": 1, "kind": "provider-export-receipt",
                                                   "status": "succeeded", "lane": "image",
                                                   "evidence_source": "local-protocol-test", "page_id": "pg-old"})):
                atomic_write_json(root / name, body)
            source = root / "source/image_providers/openai_compatible.py"
            source.parent.mkdir(parents=True)
            source.write_text("# Historical source test only.\n")
            body = {"schema_version": 1, "kind": "legacy-image-export",
                    "source_revision": "a" * 40, "capture_mode": "reconstructed-historical", "page_id": "pg-old",
                    "selection": file_reference(root, "selection.json"), "material": file_reference(root, "material.json"),
                    "provider_contract": file_reference(root, "contract.json"), "receipt": file_reference(root, "receipt.json"),
                    "source_snapshot": {source.relative_to(root).as_posix(): file_reference(root, source.relative_to(root).as_posix())["sha256"]}}
            body["export_digest"] = digest(body)
            atomic_write_json(root / "legacy-image.json", body)
            with self.assertRaisesRegex(ReplayError, "legacy_image_provider_http_evidence_required"):
                validate_legacy_image_export(root, file_reference(root, "legacy-image.json"))

    def test_rebaseline_plan_requires_new_execution_fingerprint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for name, body in (("baseline.json", {"kind": "legacy-visual-baseline"}),
                               ("selection.json", {"template_id": "builtin:template:body-basic",
                                                    "input": {"path": "input.json", "sha256": "a" * 64}}),
                               ("request.json", {"kind": "PipelineRequest"}),
                               ("material.md", "old"), ("input.json", "{}")):
                if isinstance(body, str): (root / name).write_text(body)
                else: atomic_write_json(root / name, body)
            plan = {"schema_version": 1, "kind": "paired-rebaseline-plan",
                    "baseline": file_reference(root, "baseline.json"), "environment": environment_fingerprint(),
                    "cases": [{"case_id": "c1", "page_id": "pg-old", "lane": "render:html", "theme_family": "t",
                               "material": file_reference(root, "material.md"), "old_selection": file_reference(root, "selection.json"),
                               "old_snapshot": file_reference(root, "selection.json"), "new_request": file_reference(root, "request.json"),
                               "old_output": "old/page.png", "new_output": "../escape.png"}]}
            plan["plan_digest"] = digest(plan)
            atomic_write_json(root / "plan.json", plan)
            with self.assertRaisesRegex(ReplayError, "paired_rebaseline_schema_mismatch"):
                validate_paired_rebaseline_plan(root, file_reference(root, "plan.json"))


class PairedImageRebaselineTests(unittest.TestCase):
    """合成归档与本地 HTTP 只验证机制，不作为真实 Provider 或视觉证据。"""
    def setUp(self):
        from dataclasses import asdict
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest
        from leo_ppt_generator.config.backend_contract import BackendRegistry
        from leo_ppt_generator.content_pack import compile_content_pack
        from leo_ppt_generator.qualification import is_execution_source
        from leo_ppt_generator.quality_replay import prepare_paired_rebaseline_plan
        from leo_ppt_generator.templates import resolve_design_context
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = root = Path(self.temp.name).resolve()
        archive = HistoricalBridgeTests().transport_fixture(root)
        material = (ROOT / "evals/fixtures/expression-first-validation-master.md").read_text().split("## S2")[0]
        rows = material.splitlines()
        index = next(i for i, row in enumerate(rows) if row.startswith("content_model: "))
        model = json.loads(rows[index].split(": ", 1)[1])
        model["narrative_order"] = model["narrative_order"][:1]
        model["chapters"] = model["chapters"][:1]
        model["chapters"][0]["next"] = None
        rows[index] = "content_model: " + json.dumps(model, ensure_ascii=False)
        (root / "material.md").write_text("\n".join(rows))
        pack = compile_content_pack((root / "material.md").read_text(), master_path="material.md")
        pid = pack["pages"][0]["page_id"]
        resolver = AssetResolver(library=ROOT / "template-library")
        context = resolve_design_context("清爽专业风", resolver=resolver)
        self.contract = BackendRegistry.default().create_contract("openai-compatible", mode="generate",
            model="gpt-image-2", endpoint_origin="https://provider.invalid")
        atomic_write_json(root / "contract.json", self.contract)
        self.contract_sha = file_reference(root, "contract.json")["sha256"]
        atomic_write_json(root / "source/theme.json", context["effective"])
        self.request = {"model": self.contract["model"], "prompt": "归档协议测试", "n": 1, "size": "auto"}
        atomic_write_json(root / "request.json", self.request)
        selected = {"page_id": pid, "material": file_reference(root, "material.md"),
                    "request": file_reference(root, "request.json"), "provider_contract": file_reference(root, "contract.json"),
                    "prompt_source": file_reference(root, "prompt.txt"), "theme_family": "test-theme", "theme": context["effective"]}
        atomic_write_json(root / "selection.json", selected)
        receipt = json.loads((root / "receipt.json").read_text())
        receipt.update(page_id=pid, provider=self.contract["provider"], model=self.contract["model"],
                       contract_sha256=self.contract_sha, request=file_reference(root, "request.json"))
        receipt["receipt_digest"] = digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        atomic_write_json(root / "receipt.json", receipt)
        archive.update(page_id=pid, material=selected["material"], selection=file_reference(root, "selection.json"),
                       receipt=file_reference(root, "receipt.json"), provider_contract=selected["provider_contract"],
                       theme_source=file_reference(root, "source/theme.json"))
        archive["source_snapshot"]["source/theme.json"] = archive["theme_source"]["sha256"]
        archive["export_digest"] = digest({k: v for k, v in archive.items() if k != "export_digest"})
        atomic_write_json(root / "legacy-image.json", archive)
        sources = dict(archive["source_snapshot"])
        package = ROOT / "runtime/src/leo_ppt_generator"
        for source in package.rglob("*"):
            relative = source.relative_to(package).as_posix()
            if source.is_file() and is_execution_source(relative):
                target = root / "source/leo_ppt_generator" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                reference = file_reference(root, target.relative_to(root).as_posix())
                sources[reference["path"]] = reference["sha256"]
        page = {"case_id": "image-mechanism", "deck_id": "image-mechanism", "page_id": pid, "lane": "image",
                "theme_family": "test-theme", "material": selected["material"], "selection": archive["selection"],
                "artifact": file_reference(root, "page.png"), "receipt": file_reference(root, "legacy-image.json"),
                "provider_contract_digest": self.contract_sha}
        baseline = {"schema_version": 1, "kind": "legacy-visual-baseline", "source_revision": "a" * 40,
                    "source_snapshot": sources, "dirty_hashes": {}, "capture_mode": "reconstructed-historical",
                    "environment": environment_fingerprint(), "pages": [page]}
        baseline["baseline_digest"] = digest(baseline)
        atomic_write_json(root / "baseline.json", baseline)
        request = PipelineRequest(pack, context, resolver.generation, {pid: ["image"]},
            str(root / "new"), "image-mechanism", str(resolver.builtin_root), purpose="validation", provider_contract=self.contract)
        atomic_write_json(root / "new-request.json", asdict(request))
        case = {key: page[key] for key in ("case_id", "page_id", "lane", "theme_family", "material")}
        case.update(old_selection=page["selection"], old_snapshot=page["receipt"],
                    new_request=file_reference(root, "new-request.json"), old_output="old", new_output="new")
        descriptor = {"schema_version": 1, "kind": "paired-rebaseline-plan", "baseline": file_reference(root, "baseline.json"),
                      "cases": [case]}
        atomic_write_json(root / "descriptor.json", descriptor)
        self.plan_ref = prepare_paired_rebaseline_plan(root, file_reference(root, "descriptor.json"))
        self.plan = json.loads((root / self.plan_ref["path"]).read_text())
        self.case = self.plan["cases"][0]

    def old_side(self, *, execute=False):
        from leo_ppt_generator.quality_replay import _rebaseline_old_image_side
        return _rebaseline_old_image_side(self.root, self.plan_ref, self.plan, self.case,
                                          execute=execute, provider_contracts=[self.contract_sha])

    def test_explicit_execution_requires_exact_provider_scope_before_any_output(self):
        from leo_ppt_generator.quality_replay import execute_paired_rebaseline
        for allowed in ([], ["f" * 64], [self.contract_sha, "f" * 64], [self.contract_sha] * 2):
            with self.subTest(allowed=allowed), self.assertRaisesRegex(ReplayError, "provider_scope_mismatch"):
                execute_paired_rebaseline(self.root, self.plan_ref, execute=True, provider_contracts=allowed)
            self.assertFalse((self.root / "old").exists())
            self.assertFalse((self.root / "new").exists())
        with self.assertRaisesRegex(ReplayError, "provider_scope_requires_execute"):
            execute_paired_rebaseline(self.root, self.plan_ref, provider_contracts=[self.contract_sha])

    def test_new_image_side_uses_real_route_and_remains_blocked_without_qualification(self):
        from unittest.mock import patch
        from leo_ppt_generator.quality_replay import _rebaseline_new_side
        with patch("leo_ppt_generator.image_deck.expression_adapter.export_provider_image",
                   side_effect=AssertionError("unqualified route must not call provider")):
            with self.assertRaisesRegex(ReplayError, "paired_rebaseline_new_route_failed"):
                _rebaseline_new_side(self.root, self.case, execute=True, provider_contracts=[self.contract_sha])
        execution = json.loads((self.root / "new/qa/replay-execution.json").read_text())
        self.assertEqual(execution["failure"]["phase"], "qualification")
        self.assertFalse((self.root / "new/input/current.json").exists())

    def test_local_http_preserves_old_prompt_and_retry_never_upgrades_or_reissues(self):
        from dataclasses import replace
        from unittest.mock import patch
        from tests.test_image_expression_adapter import ProviderProtocolTests
        harness = ProviderProtocolTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        context = replace(harness.context, contract_sha256=self.contract_sha)
        with patch("leo_ppt_generator.backend_execution.build_execution_context", return_value=context):
            with self.assertRaisesRegex(ReplayError, "paired_rebaseline_real_provider_required"):
                self.old_side(execute=True)
        self.assertEqual(harness.requests, [self.request])
        with self.assertRaisesRegex(ReplayError, "paired_rebaseline_real_provider_required"):
            self.old_side(execute=True)
        self.assertEqual(harness.requests, [self.request])
        self.assertFalse((self.root / "old/execution.json").exists())

    def test_interrupted_provider_result_is_not_reissued(self):
        from dataclasses import replace
        from unittest.mock import patch
        from tests.test_image_expression_adapter import ProviderProtocolTests
        from leo_ppt_generator.image_deck.expression_adapter import export_provider_image
        harness = ProviderProtocolTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        context = replace(harness.context, contract_sha256=self.contract_sha)
        def interrupt(*args, **kwargs):
            def checkpoint(phase):
                if phase == "after_artifact":
                    raise InterruptedError("simulated-after-artifact")
            kwargs["checkpoint"] = checkpoint
            return export_provider_image(*args, **kwargs)
        with patch("leo_ppt_generator.backend_execution.build_execution_context", return_value=context):
            with patch("leo_ppt_generator.image_deck.expression_adapter.export_provider_image", side_effect=interrupt):
                with self.assertRaises(InterruptedError):
                    self.old_side(execute=True)
            with self.assertRaisesRegex(ValueError, "provider_outcome_unknown"):
                self.old_side(execute=True)
        self.assertEqual(harness.requests, [self.request])

    def test_context_contract_drift_is_rejected_before_transport(self):
        from unittest.mock import patch
        from leo_ppt_generator.backend_execution import BackendExecutionContext
        context = BackendExecutionContext(self.contract["provider"], self.contract["model"], "generate", {}, 1, 0, "f" * 64, {})
        with patch("leo_ppt_generator.backend_execution.build_execution_context", return_value=context):
            with self.assertRaisesRegex(ReplayError, "paired_rebaseline_execution_contract_changed"):
                self.old_side(execute=True)
        self.assertFalse((self.root / "old/provider-inflight.json").exists())

    def test_readonly_does_not_call_provider_or_create_outputs(self):
        with self.assertRaises(ValueError):
            self.old_side(execute=False)
        self.assertFalse((self.root / "old").exists())

    def test_resigned_request_cannot_change_original_provider_contract_or_theme(self):
        from leo_ppt_generator.quality_replay import _execution_fingerprint, _rebaseline_image_inputs
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest
        original = json.loads((self.root / "baseline.json").read_text())["pages"][0]
        for field in ("provider_contract", "design_context"):
            body = json.loads((self.root / "new-request.json").read_text())
            if field == "provider_contract": body[field]["model"] = "other-model"
            else: body[field]["effective"]["colors"]["background"] = "#123456"
            atomic_write_json(self.root / "changed-request.json", body)
            case = deepcopy(self.case)
            case["new_request"] = file_reference(self.root, "changed-request.json")
            case["new_fingerprint"] = _execution_fingerprint(PipelineRequest.from_dict(body))
            with self.subTest(field=field), self.assertRaisesRegex(ReplayError, "contract_or_theme_changed"):
                _rebaseline_image_inputs(self.root, case, original)

    def test_missing_historical_theme_blocks_even_when_archive_is_otherwise_valid(self):
        from leo_ppt_generator.quality_replay import _rebaseline_image_inputs
        archive = json.loads((self.root / "legacy-image.json").read_text())
        selected = json.loads((self.root / "selection.json").read_text())
        selected.pop("theme")
        atomic_write_json(self.root / "without-theme-selection.json", selected)
        archive.pop("theme_source")
        archive["selection"] = file_reference(self.root, "without-theme-selection.json")
        archive["export_digest"] = digest({k: v for k, v in archive.items() if k != "export_digest"})
        atomic_write_json(self.root / "without-theme.json", archive)
        reference = file_reference(self.root, "without-theme.json")
        case = {**self.case, "old_snapshot": reference, "old_selection": archive["selection"]}
        with self.assertRaisesRegex(ReplayError, "historical_image_theme_missing"):
            _rebaseline_image_inputs(self.root, case, {"receipt": reference})

    def test_undeclared_extra_lane_is_rejected_before_execution(self):
        from leo_ppt_generator.quality_replay import _execution_fingerprint
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest
        body = json.loads((self.root / "new-request.json").read_text())
        body["lane_matrix"][self.case["page_id"]].append("render:html")
        atomic_write_json(self.root / "extra-lane-request.json", body)
        plan = deepcopy(self.plan)
        plan["cases"][0]["new_request"] = file_reference(self.root, "extra-lane-request.json")
        plan["cases"][0]["new_fingerprint"] = _execution_fingerprint(PipelineRequest.from_dict(body))
        plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
        atomic_write_json(self.root / "extra-lane-plan.json", plan)
        with self.assertRaisesRegex(ReplayError, "paired_rebaseline_unplanned_execution"):
            validate_paired_rebaseline_plan(self.root, file_reference(self.root, "extra-lane-plan.json"))

    def test_archived_http_fixture_recovers_missing_execution_record_and_detects_drift(self):
        """仅测试合成字节的收据恢复；不登记外部 Provider 成功。"""
        from unittest.mock import patch
        from leo_ppt_generator.storage import canonical_json_bytes
        archive = json.loads((self.root / "legacy-image.json").read_text())
        selected = json.loads((self.root / "selection.json").read_text())
        expected = {"plan": self.plan_ref, "selection": self.case["old_selection"], "snapshot": self.case["old_snapshot"],
                    "environment": self.plan["environment"], "request": selected["request"],
                    "provider_contract": archive["provider_contract"], "theme_source": archive["theme_source"]}
        directory = self.root / "old"
        directory.mkdir()
        (directory / "execution-input.json").write_bytes(canonical_json_bytes(expected))
        for name in ("page.png", "provider-image.bin", "request.json", "response.json"):
            shutil.copyfile(self.root / name, directory / name)
        receipt = json.loads((self.root / "receipt.json").read_text())
        envelope = {"kind": "image-recipe-input", "canvas": {"width": 2560, "height": 1440},
                    "page_id": self.case["page_id"], "recipe_id": "historical-prompt:" + archive["export_digest"],
                    "prompt": self.request["prompt"]}
        receipt["recipe_id"] = envelope["recipe_id"]
        receipt["input_digest"] = digest({"request": self.request, "recipe_input": envelope, "contract": self.contract_sha,
            "materialization_binding_digest": None, "run_id": None, "input_generation": None})
        receipt["receipt_digest"] = digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        atomic_write_json(directory / "page.png.provider.json", receipt)
        with patch("leo_ppt_generator.backend_execution.build_execution_context", side_effect=AssertionError("no credentials needed")):
            recovered = self.old_side(execute=True)
            self.assertEqual(self.old_side(execute=False), recovered)
            self.assertEqual(self.old_side(execute=True), recovered)
        (directory / "provider-image.bin").write_bytes(b"drift")
        with self.assertRaises(ValueError):
            self.old_side(execute=False)

    def test_cli_provider_scope_without_execute_is_rejected(self):
        checked = subprocess.run([str(ROOT / "runtime/.venv/bin/python"), "scripts/run_quality_scorecard.py",
            str(self.root), "--paired-rebaseline-plan", self.plan_ref["path"],
            "--provider-contract-sha256", self.contract_sha], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(checked.returncode, 2, checked.stdout + checked.stderr)
        self.assertIn("provider scope requires", checked.stderr)
        self.assertFalse((self.root / "old").exists())


class HistoricalHtmlBindingTests(unittest.TestCase):
    """历史 schema=2 的单摘要合同；这些数据不作为业务基线。"""
    def setUp(self):
        self.binding = {"schema_version": 2, "page_id": "pg-old", "layout_id": "builtin:layout:body-basic",
            "template_id": "builtin:template:body-basic", "backend": "render:html", "slot_map": {},
            "item_ids": ["b", "a"], "context_digest": "a" * 64, "content_digest": "b" * 64,
            "compiler": "historical-contract-mechanism-test", "effective": {"theme": {"--bg": "#ffffff"}},
            "eligibility": {"qualified": True}}
        self.binding["binding_digest"] = self.historical_digest(self.binding)
        self.receipt = {key: self.binding[key] for key in ("binding_digest", "content_digest", "template_id", "backend")}
        self.page = {"page_id": "pg-old", "lane": "render:html"}
        self.selected = {"template_id": self.binding["template_id"], "theme": {"--bg": "#ffffff"}}

    @staticmethod
    def historical_digest(binding):
        body = {key: binding[key] for key in ("page_id", "layout_id", "template_id", "backend", "slot_map",
            "context_digest", "content_digest", "compiler", "effective", "eligibility")}
        body["item_ids"] = sorted(binding["item_ids"])
        return digest(body)

    def verify(self):
        from leo_ppt_generator.quality_replay import _verify_historical_html_binding
        return _verify_historical_html_binding(self.binding, self.receipt, page=self.page, selected=self.selected)

    def test_historical_single_digest_verifies_without_entering_production_verifier(self):
        self.assertIsNone(self.verify())
        from leo_ppt_generator.content_projection import verify_dual_binding_digests
        with self.assertRaisesRegex(ValueError, "binding_schema_mismatch"):
            verify_dual_binding_digests(self.binding)

    def test_resigned_theme_does_not_replace_original_receipt(self):
        self.binding["effective"]["theme"] = self.selected["theme"] = {"--bg": "#000000"}
        self.binding["binding_digest"] = self.historical_digest(self.binding)
        with self.assertRaisesRegex(ReplayError, "paired_rebaseline_historical_binding_receipt_mismatch"):
            self.verify()

    def test_missing_original_receipt_digest_is_blocked(self):
        self.receipt.pop("binding_digest")
        with self.assertRaisesRegex(ReplayError, "paired_rebaseline_historical_binding_missing") as caught:
            self.verify()
        self.assertEqual(caught.exception.status, "blocked")

    def test_missing_or_malformed_effective_theme_is_blocked(self):
        for effective in ({}, {"theme": {}}, None, []):
            self.binding["effective"] = effective
            with self.subTest(effective=effective), self.assertRaisesRegex(
                    ReplayError, "paired_rebaseline_historical_theme_missing") as caught:
                self.verify()
            self.assertEqual(caught.exception.status, "blocked")

    def test_old_and_new_digest_mixture_is_blocked(self):
        for target in (self.binding, self.receipt):
            target["expression_binding_digest"] = "f" * 64
            with self.subTest(target=target), self.assertRaisesRegex(
                    ReplayError, "paired_rebaseline_historical_binding_schema_mismatch") as caught:
                self.verify()
            self.assertEqual(caught.exception.status, "blocked")
            target.pop("expression_binding_digest")


class PairedRebaselineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from dataclasses import asdict
        from tests.expression_test_support import copy_real_html_run, real_validation_inputs
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest, load_committed_input
        from leo_ppt_generator.qualification import is_execution_source
        from leo_ppt_generator.quality_replay import prepare_paired_rebaseline_plan, execute_paired_rebaseline
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name).resolve()
        root = cls.root
        original = root / "original"
        result = copy_real_html_run(original)
        committed = load_committed_input(original)
        package = ROOT / "runtime/src/leo_ppt_generator"
        sources = {}
        for path in package.rglob("*"):
            relative = path.relative_to(package).as_posix()
            if path.is_file() and is_execution_source(relative):
                target = root / "source/leo_ppt_generator" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                ref = file_reference(root, target.relative_to(root).as_posix())
                sources[ref["path"]] = ref["sha256"]
        snapshot = committed["root"] / "asset-snapshot"
        files = []
        for path in snapshot.rglob("*"):
            if path.is_file():
                relative = path.relative_to(snapshot).as_posix()
                files.append(file_reference(snapshot, relative))
                if "/canonical/" in relative:
                    ref = file_reference(root, path.relative_to(root).as_posix())
                    sources[ref["path"]] = ref["sha256"]
        atomic_write_json(root / "snapshot.json", {"root": snapshot.relative_to(root).as_posix(), "files": files,
            "source_roots": {"builtin": (snapshot / "builtin").relative_to(root).as_posix()}})
        material = root / "material.md"
        material.write_bytes((ROOT / "evals/fixtures/expression-first-validation-master.md").read_bytes())
        pack, resolver, context = real_validation_inputs()
        request = PipelineRequest(pack, context, resolver.generation,
            {page["page_id"]: ["render:html"] for page in pack["pages"]},
            str(root / "new"), "paired-test", str(resolver.builtin_root), purpose="validation")
        atomic_write_json(root / "request.json", asdict(request))
        pages, cases = [], []
        for pid, row in result["receipt_refs"]["render:html"].items():
            binding = committed["payload"]["bindings"]["render:html"][pid]
            atomic_write_json(root / (pid + "-binding.json"), binding)
            artifact = original / row["artifact"]
            selected = {"template_id": binding["template_id"],
                        "input": file_reference(root, (artifact.parent / "data.json").relative_to(root).as_posix()),
                        "theme": binding["effective"]["theme"], "binding": file_reference(root, pid + "-binding.json")}
            atomic_write_json(root / (pid + "-selection.json"), selected)
            selection = file_reference(root, pid + "-selection.json")
            page = {"case_id": pid, "deck_id": "paired-test", "page_id": pid, "lane": "render:html",
                    "theme_family": "test", "material": file_reference(root, "material.md"), "selection": selection,
                    "artifact": file_reference(root, artifact.relative_to(root).as_posix()),
                    "receipt": file_reference(root, (original / row["receipt"]).relative_to(root).as_posix()),
                    "provider_contract_digest": None}
            pages.append(page)
            cases.append({key: page[key] for key in ("case_id", "page_id", "lane", "theme_family", "material")})
            cases[-1].update(old_selection=selection, old_snapshot=file_reference(root, "snapshot.json"),
                new_request=file_reference(root, "request.json"), old_output="old/" + pid, new_output="new")
        baseline = {"schema_version": 1, "kind": "legacy-visual-baseline", "source_revision": "a" * 40,
                    "source_snapshot": sources, "dirty_hashes": {}, "capture_mode": "reconstructed-historical",
                    "environment": environment_fingerprint(), "pages": pages}
        baseline["baseline_digest"] = digest(baseline)
        atomic_write_json(root / "baseline.json", baseline)
        cls.descriptor = {"schema_version": 1, "kind": "paired-rebaseline-plan",
                          "baseline": file_reference(root, "baseline.json"), "cases": cases}
        atomic_write_json(root / "descriptor.json", cls.descriptor)
        cls.plan_ref = prepare_paired_rebaseline_plan(root, file_reference(root, "descriptor.json"))
        cls.plan = json.loads((root / cls.plan_ref["path"]).read_text())
        cls.report = execute_paired_rebaseline(root, cls.plan_ref, execute=True)
        atomic_write_json(root / "paired.json", cls.report)

    def test_real_two_sided_html_exports_have_reverifiable_receipt_and_keep_historical_origin(self):
        from leo_ppt_generator.quality_replay import verify_paired_rebaseline
        self.assertEqual(self.report["status"], "passed", self.report)
        receipt = file_reference(self.root, "paired.json")
        self.assertEqual(verify_paired_rebaseline(self.root, receipt), self.report)
        baseline = verify_legacy_baseline(self.root, receipt)
        self.assertEqual(baseline["capture_mode"], "reconstructed-historical")
        self.assertEqual(baseline["source_snapshot"], json.loads((self.root / "baseline.json").read_text())["source_snapshot"])
        self.assertEqual(paired_environment_compatibility(baseline, environment_fingerprint())["status"], "compatible")

    def test_plan_cannot_override_old_material_theme_or_paths(self):
        for mutation in ("material", "path", "subset"):
            plan = deepcopy(self.plan)
            if mutation == "material":
                plan["cases"][0]["material"] = file_reference(self.root, "request.json")
            elif mutation == "path":
                plan["cases"][0]["old_output"] = "../escape"
            else:
                plan["cases"] = plan["cases"][:1]
            plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
            atomic_write_json(self.root / (mutation + "-plan.json"), plan)
            with self.subTest(mutation=mutation), self.assertRaises(ReplayError):
                validate_paired_rebaseline_plan(self.root, file_reference(self.root, mutation + "-plan.json"))

    def _changed_selection_plan(self, selected, label):
        baseline = json.loads((self.root / "baseline.json").read_text())
        atomic_write_json(self.root / (label + "-selection.json"), selected)
        reference = file_reference(self.root, label + "-selection.json")
        baseline["pages"][0]["selection"] = reference
        baseline["baseline_digest"] = digest({k: v for k, v in baseline.items() if k != "baseline_digest"})
        atomic_write_json(self.root / (label + "-baseline.json"), baseline)
        plan = deepcopy(self.plan)
        plan["baseline"] = file_reference(self.root, label + "-baseline.json")
        plan["cases"][0]["old_selection"] = reference
        return self._write_changed_plan(plan, label)

    def _write_changed_plan(self, plan, label):
        plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
        atomic_write_json(self.root / (label + "-plan.json"), plan)
        return file_reference(self.root, label + "-plan.json")

    def test_resigned_theme_binding_cannot_replace_original_receipt_identity(self):
        from leo_ppt_generator.content_projection import compute_materialization_binding_digest
        for resign in (False, True):
            selected = json.loads((self.root / self.plan["cases"][0]["old_selection"]["path"]).read_text())
            binding = json.loads((self.root / selected["binding"]["path"]).read_text())
            binding["effective"]["theme"]["--leo-color-bg"] = "#123456"
            selected["theme"] = deepcopy(binding["effective"]["theme"])
            if resign:
                binding["materialization_binding_digest"] = compute_materialization_binding_digest(binding)
            label = "resigned-theme-" + str(resign)
            atomic_write_json(self.root / (label + "-binding.json"), binding)
            selected["binding"] = file_reference(self.root, label + "-binding.json")
            reference = self._changed_selection_plan(selected, label)
            with self.subTest(resign=resign), self.assertRaisesRegex(
                    ReplayError, "paired_rebaseline_historical_binding_receipt_mismatch"):
                validate_paired_rebaseline_plan(self.root, reference)

    def test_missing_historical_binding_or_theme_blocks_rebaseline(self):
        for field in ("binding", "theme"):
            selected = json.loads((self.root / self.plan["cases"][0]["old_selection"]["path"]).read_text())
            selected.pop(field)
            reference = self._changed_selection_plan(selected, "missing-" + field)
            with self.subTest(field=field), self.assertRaisesRegex(
                    ReplayError, "paired_rebaseline_historical_binding_or_theme_missing") as caught:
                validate_paired_rebaseline_plan(self.root, reference)
            self.assertEqual(caught.exception.status, "blocked")

    def test_snapshot_rejects_historical_hash_bag_with_wrong_asset_path(self):
        from leo_ppt_generator.quality_replay import _rebaseline_snapshot
        baseline = json.loads((self.root / "baseline.json").read_text())
        descriptor = json.loads((self.root / "snapshot.json").read_text())
        selected = json.loads((self.root / self.plan["cases"][0]["old_selection"]["path"]).read_text())
        binding = json.loads((self.root / selected["binding"]["path"]).read_text())
        copied = self.root / "wrong-path-snapshot"
        shutil.copytree(self.root / descriptor["root"], copied)
        candidates = [row for row in descriptor["files"] if "/canonical/" in row["path"]]
        first = candidates[0]
        second = next(row for row in candidates if row["sha256"] != first["sha256"])
        (copied / first["path"]).write_bytes((copied / second["path"]).read_bytes())
        descriptor["root"] = copied.relative_to(self.root).as_posix()
        descriptor["files"] = [file_reference(copied, path.relative_to(copied).as_posix())
                               for path in copied.rglob("*") if path.is_file()]
        atomic_write_json(self.root / "wrong-path-snapshot.json", descriptor)
        with self.assertRaisesRegex(ReplayError, "paired_rebaseline_asset_path_not_historical"):
            _rebaseline_snapshot(self.root, file_reference(self.root, "wrong-path-snapshot.json"), baseline, binding)

    def test_snapshot_rejects_catalog_alias_for_another_manifest_identity(self):
        from leo_ppt_generator.quality_replay import _rebaseline_snapshot
        baseline = json.loads((self.root / "baseline.json").read_text())
        descriptor = json.loads((self.root / "snapshot.json").read_text())
        selected = json.loads((self.root / self.plan["cases"][0]["old_selection"]["path"]).read_text())
        binding = json.loads((self.root / selected["binding"]["path"]).read_text())
        copied = self.root / "alias-snapshot"
        shutil.copytree(self.root / descriptor["root"], copied)
        identity, spoof = binding["template_id"], "builtin:template:spoofed-identity"
        generation = json.loads((copied / "builtin/catalog/current.json").read_text())["generation"]
        registry_path = copied / "builtin/catalog/generations" / generation / "registry.json"
        registry = json.loads(registry_path.read_text())
        next(row for row in registry["entities"] if row["asset_id"] == identity)["asset_id"] = spoof
        atomic_write_json(registry_path, registry)
        binding["template_id"] = spoof
        next(pin for pin in binding["effective"]["assets"] if pin["asset_id"] == identity)["asset_id"] = spoof
        descriptor["root"] = copied.relative_to(self.root).as_posix()
        descriptor["files"] = [file_reference(copied, path.relative_to(copied).as_posix())
                               for path in copied.rglob("*") if path.is_file()]
        atomic_write_json(self.root / "alias-snapshot.json", descriptor)
        with self.assertRaisesRegex(ReplayError, "paired_rebaseline_asset_identity_mismatch"):
            _rebaseline_snapshot(self.root, file_reference(self.root, "alias-snapshot.json"), baseline, binding)

    def test_snapshot_malformed_pins_are_explicitly_blocked(self):
        from leo_ppt_generator.quality_replay import _rebaseline_snapshot
        baseline = json.loads((self.root / "baseline.json").read_text())
        selected = json.loads((self.root / self.plan["cases"][0]["old_selection"]["path"]).read_text())
        for pins in ([None], [{"asset_id": "fake", "origin_scope": "outside", "files": {"a": "b"}}], []):
            binding = json.loads((self.root / selected["binding"]["path"]).read_text())
            binding["effective"]["assets"] = pins
            with self.subTest(pins=pins), self.assertRaisesRegex(
                    ReplayError, "paired_rebaseline_historical_asset_pins_missing") as caught:
                _rebaseline_snapshot(self.root, file_reference(self.root, "snapshot.json"), baseline, binding)
            self.assertEqual(caught.exception.status, "blocked")

    def test_outputs_cannot_cover_inputs_or_enter_historical_snapshot(self):
        baseline = json.loads((self.root / "baseline.json").read_text())
        page = baseline["pages"][0]
        selected = json.loads((self.root / page["selection"]["path"]).read_text())
        snapshot = json.loads((self.root / "snapshot.json").read_text())
        targets = [page[field]["path"] for field in ("material", "selection", "artifact", "receipt")]
        targets.extend(selected[field]["path"] for field in ("input", "binding"))
        targets.extend(["snapshot.json", snapshot["root"], snapshot["root"] + "/nested-output",
                        snapshot["source_roots"]["builtin"] + "/nested-output"])
        for index, target in enumerate(targets):
            plan = deepcopy(self.plan)
            plan["cases"][0]["old_output"] = target
            reference = self._write_changed_plan(plan, "overlap-" + str(index))
            with self.subTest(target=target), self.assertRaisesRegex(
                    ReplayError, "paired_rebaseline_output_overlaps_input"):
                validate_paired_rebaseline_plan(self.root, reference)

    def test_one_side_missing_and_resigned_pass_flag_do_not_verify(self):
        from leo_ppt_generator.quality_replay import verify_paired_rebaseline
        report = deepcopy(self.report)
        report["status"] = "passed"
        report["cases"][0].pop("new", None)
        report["receipt_digest"] = digest({k: v for k, v in report.items() if k != "receipt_digest"})
        atomic_write_json(self.root / "forged.json", report)
        with self.assertRaises(ReplayError):
            verify_paired_rebaseline(self.root, file_reference(self.root, "forged.json"))

    def test_actual_old_artifact_drift_is_rejected(self):
        from leo_ppt_generator.quality_replay import verify_paired_rebaseline
        path = self.root / self.report["cases"][0]["old"]["artifact"]["path"]
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"changed")
            with self.assertRaises(ReplayError):
                verify_paired_rebaseline(self.root, file_reference(self.root, "paired.json"))
        finally:
            path.write_bytes(original)

    def test_prepare_is_immutable_and_does_not_rerender(self):
        from leo_ppt_generator.quality_replay import prepare_paired_rebaseline_plan
        before = (self.root / self.plan_ref["path"]).read_bytes()
        reference = prepare_paired_rebaseline_plan(self.root, file_reference(self.root, "descriptor.json"))
        self.assertEqual(reference, self.plan_ref)
        self.assertEqual((self.root / self.plan_ref["path"]).read_bytes(), before)

    def test_publication_bundle_cannot_borrow_an_external_rebaseline_library(self):
        from leo_ppt_generator.quality_replay import verify_paired_rebaseline
        with self.assertRaisesRegex(ReplayError, "capability_u6a_external_execution_library"):
            verify_paired_rebaseline(self.root, file_reference(self.root, "paired.json"), self_contained=True)

    def test_cli_prepares_and_reverifies_the_actual_pair_without_another_render(self):
        import os
        environment = {**os.environ, "PYTHONPATH": "runtime/src"}
        command = [str(ROOT / "runtime/.venv/bin/python"), "scripts/run_quality_scorecard.py", str(self.root)]
        prepared = subprocess.run(command + ["--prepare-paired-rebaseline", "descriptor.json"], cwd=ROOT,
                                  env=environment, text=True, capture_output=True)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(json.loads(prepared.stdout)["exports"], "not_run")
        checked = subprocess.run(command + ["--paired-rebaseline-plan", self.plan_ref["path"]], cwd=ROOT,
                                 env=environment, text=True, capture_output=True)
        self.assertEqual(checked.returncode, 0, checked.stderr + checked.stdout)
        self.assertEqual(json.loads(checked.stdout), self.report)
