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
    ReplayError, evaluate_quality_replay, freeze_legacy_baseline, validate_replay_dataset, verify_legacy_baseline,
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
