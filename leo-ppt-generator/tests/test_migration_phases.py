"""正式五阶段入口的拒绝门；临时测试不会伪造真实视觉 prerequisite。"""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from leo_ppt_generator.library_migration import (
    MigrationError, preview_migration, stage_migration, publish_migration, cleanup_migration,
    validate_plan_contract,
    file_state, _target_bytes, compare_and_swap_file,
    _verify_target_closure,
)
from leo_ppt_generator.qualification import digest, file_reference
from leo_ppt_generator.storage import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]


class MigrationPhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.delivery = self.root / "delivery"
        library = self.delivery / "leo-ppt-generator/template-library"
        shutil.copytree(ROOT / "tests/fixtures/minimal-template-library", library)
        shutil.copytree(ROOT / "template-library/governance", library / "governance", dirs_exist_ok=True)
        for command in (["git", "init", "-q"], ["git", "add", "."],
                        ["git", "-c", "user.name=Migration test", "-c", "user.email=test@example.invalid", "commit", "-qm", "临时测试基线"]):
            subprocess.run(command, cwd=self.delivery, check=True, capture_output=True)
        self.work = self.root / "evidence"
        self.plan_path = self.work / "migration-plan.json"

    def test_preview_records_current_source_mapping_and_only_writes_one_plan(self):
        before = {p.relative_to(self.delivery).as_posix(): p.read_bytes() for p in self.delivery.rglob("*") if p.is_file() and ".git" not in p.parts}
        plan = preview_migration(self.delivery, self.plan_path)
        self.assertEqual(plan["gate"], "U7-A")
        self.assertEqual(plan["gaps"], ["migration_pre_value_gate_missing"])
        self.assertEqual(plan["closure"]["unclassified_hits"], 0)
        self.assertIn("leo-ppt-generator/template-library/canonical/visual/styles/minimal-clean/brief.json", plan["target_hashes"])
        self.assertEqual(list(self.work.iterdir()), [self.plan_path])
        self.assertEqual(before, {p.relative_to(self.delivery).as_posix(): p.read_bytes() for p in self.delivery.rglob("*") if p.is_file() and ".git" not in p.parts})
        self.assertEqual(preview_migration(self.delivery, self.plan_path), plan)

    def test_target_evidence_manifest_is_validated_before_plan_creation(self):
        self.work.mkdir(exist_ok=True)
        evidence = self.work / "target-evidence.json"
        atomic_write_json(evidence, {"schema_version": 1, "kind": "migration-target-evidence",
                                     "asset_generation": "0" * 64, "required_assets": [], "files": []})
        with self.assertRaisesRegex(MigrationError, "migration_target_evidence_manifest_invalid"):
            preview_migration(self.delivery, self.plan_path,
                              target_evidence=file_reference(self.work, evidence.name))
        self.assertFalse(self.plan_path.exists())

    def test_target_evidence_cli_argument_is_forwarded_and_rejects_invalid_manifest(self):
        self.work.mkdir(exist_ok=True)
        evidence = self.work / "target-evidence.json"
        atomic_write_json(evidence, {"schema_version": 1, "kind": "wrong", "files": []})
        result = subprocess.run([
            str(ROOT / "runtime/.venv/bin/python"), str(ROOT / "scripts/migrate_template_library.py"),
            "preview", "--source-root", str(self.delivery), "--out-plan", str(self.plan_path),
            "--target-evidence", str(evidence)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("migration_target_evidence_manifest_invalid", result.stderr)

    def evidence_input(self, body=b"\x89PNG\r\n\x1a\n\xff\x00", required_assets=None):
        path = "leo-ppt-generator/template-library/evidence/probes/new-output.png"
        document = {"schema_version": 1, "kind": "migration-target-evidence", "asset_generation": "0" * 64,
                    "required_assets": ["builtin:layout:body-basic"] if required_assets is None else required_assets,
                    "files": [{"path": path, "expected": file_state(self.delivery, path),
                        "target": {"payload": base64.b64encode(body).decode(),
                                   "sha256": hashlib.sha256(body).hexdigest(), "mode": 0o644}}]}
        self.work.mkdir(exist_ok=True)
        output = self.work / "target-evidence.json"
        atomic_write_json(output, document)
        return file_reference(self.work, output.name), document

    def test_target_evidence_decodes_binary_outputs_and_requires_nonempty_asset_scope(self):
        from leo_ppt_generator.library_migration import _replacement_bytes, _target_evidence_manifest
        reference, document = self.evidence_input()
        self.assertEqual(_replacement_bytes(document["files"][0]["target"], require_text=False), b"\x89PNG\r\n\x1a\n\xff\x00")
        reference, _ = self.evidence_input(body=b"{}", required_assets=[])
        with self.assertRaisesRegex(MigrationError, "migration_target_evidence_manifest_invalid"):
            _target_evidence_manifest(self.delivery, self.work, reference)

    def test_real_target_evidence_freezes_new_png_and_revalidates_in_target_runtime(self):
        from tests.expression_test_support import real_validation_inputs_v2
        from leo_ppt_generator.library_migration import _verify_target_evidence, _uses_target_runtime
        from leo_ppt_generator.qualification import asset_generation, RECEIPTS_PATH
        _, resolver, _ = real_validation_inputs_v2()
        package = self.delivery / "leo-ppt-generator"
        library = package / "template-library"
        shutil.rmtree(library)
        shutil.copytree(resolver.builtin_root, library)
        shutil.copytree(ROOT / "runtime/src", package / "runtime/src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "assets", package / "assets")
        receipts = json.loads((library / RECEIPTS_PATH).read_text())["receipts"]
        self.assertTrue(receipts)
        document = {"schema_version": 1, "kind": "migration-target-evidence",
            "asset_generation": asset_generation(library),
            "required_assets": sorted({row["asset_id"] for row in receipts}), "files": []}
        for source in sorted((resolver.builtin_root / "evidence").rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(resolver.builtin_root).as_posix()
            path = "leo-ppt-generator/template-library/" + relative
            body = source.read_bytes()
            # 证据目标必须能新增，不能要求它已存在于 delivery 快照。
            (self.delivery / path).unlink()
            document["files"].append({"path": path, "expected": file_state(self.delivery, path),
                "target": {"payload": base64.b64encode(body).decode(),
                    "sha256": hashlib.sha256(body).hexdigest(), "mode": 0o644}})
        self.work.mkdir(exist_ok=True)
        manifest_path = self.work / "target-evidence.json"
        atomic_write_json(manifest_path, document)
        plan = preview_migration(self.delivery, self.plan_path,
                                 target_evidence=file_reference(self.work, manifest_path.name))
        self.assertTrue(_uses_target_runtime(plan))
        self.assertFalse(any(row["operation"] == "replace" for row in plan["mapping"].values()))
        png = next(row["path"] for row in document["files"] if row["path"].endswith(".png"))
        self.assertEqual(_target_bytes(plan, png)[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(plan["source_snapshot"][png]["type"], "absent")
        self.assertEqual(plan["gate"], "U7-A")
        shadow = self.root / "evidence-bytes-only-shadow"
        for relative, row in plan["mapping"].items():
            destination = shadow / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(_target_bytes(plan, relative))
            destination.chmod(row["mode"])
        verified = _verify_target_evidence(plan, shadow)
        self.assertTrue(verified["result"]["verified_receipts"])
        self.assertEqual(verified["result"]["asset_generation"], document["asset_generation"])
        self.assertEqual(verified["owners"]["qualification.py"],
                         file_reference(package / "runtime/src/leo_ppt_generator", "qualification.py")["sha256"])
        for mutation in ("digest", "mapping", "manifest", "generation", "scope"):
            candidate = deepcopy(plan)
            if mutation == "digest":
                candidate["target_evidence_digest"] = "0" * 64
            elif mutation == "mapping":
                candidate["mapping"][png]["operation"] = "replace"
            elif mutation == "manifest":
                candidate["target_evidence"]["files"].pop()
                candidate["target_evidence_digest"] = digest(candidate["target_evidence"])
            elif mutation == "generation":
                candidate["target_evidence"]["asset_generation"] = "0" * 64
                candidate["target_evidence_digest"] = digest(candidate["target_evidence"])
            else:
                candidate["target_evidence"]["required_assets"] = []
                candidate["target_evidence_digest"] = digest(candidate["target_evidence"])
            candidate["plan_digest"] = digest({key: value for key, value in candidate.items() if key != "plan_digest"})
            with self.subTest(mutation=mutation), self.assertRaises(MigrationError):
                validate_plan_contract(candidate)
        (shadow / png).write_bytes(b"external drift")
        # v2 reader 先复核 evidence-set 与 catalog 代，附件漂移在进入 probe 前拒绝。
        with self.assertRaisesRegex(MigrationError, "stale_catalog"):
            _verify_target_evidence(plan, shadow)
        with self.assertRaisesRegex(MigrationError, "migration_execution_plan_required"):
            stage_migration(self.plan_path, self.root / "formal-shadow")

    def test_stage_rejects_contract_baseline_without_creating_worktree(self):
        preview_migration(self.delivery, self.plan_path)
        shadow = self.root / "shadow"
        with self.assertRaisesRegex(MigrationError, "migration_execution_plan_required"):
            stage_migration(self.plan_path, shadow)
        self.assertFalse(shadow.exists())

    def test_preview_binds_required_root_changelog_without_expanding_sibling_scope(self):
        changelog = self.delivery / "CHANGELOG.md"
        changelog.write_text("# Changelog\n本任务与既有记录均须保留。\n")
        sibling = self.delivery / "other-skill/owner.py"
        sibling.parent.mkdir()
        sibling.write_text("user_owned = True\n")
        plan = preview_migration(self.delivery, self.plan_path)
        self.assertIn("CHANGELOG.md", plan["source_snapshot"])
        self.assertEqual(plan["mapping"]["CHANGELOG.md"]["source"], "CHANGELOG.md")
        self.assertIn("CHANGELOG.md", plan["target_hashes"])
        self.assertIn({"path": "CHANGELOG.md", "exists": True}, plan["closure"]["roots"])
        self.assertNotIn("other-skill/owner.py", plan["source_snapshot"])
        self.assertEqual(sibling.read_text(), "user_owned = True\n")

    def test_editing_gate_and_resigning_cannot_forge_runtime_prerequisite(self):
        plan = preview_migration(self.delivery, self.plan_path)
        plan["gate"] = "U7-B"
        plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
        atomic_write_json(self.plan_path, plan)
        with self.assertRaisesRegex(MigrationError, "migration_reference_invalid"):
            stage_migration(self.plan_path, self.root / "shadow")
        self.assertFalse((self.root / "shadow").exists())

    def test_old_cli_aliases_are_rejected(self):
        for option in ("--execute", "--verify", "--retire-old-tree", "--phase"):
            result = subprocess.run([str(ROOT / "runtime/.venv/bin/python"), str(ROOT / "scripts/migrate_template_library.py"), option], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)

    def test_publish_and_cleanup_reject_unverified_or_mismatched_receipt_before_writes(self):
        plan = preview_migration(self.delivery, self.plan_path)
        plan["gate"] = "U7-B"
        plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
        atomic_write_json(self.plan_path, plan)
        bad = self.work / "receipt.json"
        atomic_write_json(bad, {"status": "passed", "phase": "verify", "plan_digest": plan["plan_digest"]})
        for operation in (publish_migration, cleanup_migration):
            with self.subTest(operation=operation.__name__), self.assertRaises(MigrationError):
                operation(self.plan_path, bad, self.delivery)
        self.assertFalse((self.delivery / "leo-ppt-generator/template-library/.maintenance.json").exists())

    def test_existing_plan_is_not_overwritten_after_source_drift(self):
        preview_migration(self.delivery, self.plan_path)
        before = self.plan_path.read_bytes()
        (self.delivery / "leo-ppt-generator/external.txt").write_text("external")
        with self.assertRaisesRegex(MigrationError, "migration_immutable_artifact_conflict"):
            preview_migration(self.delivery, self.plan_path)
        self.assertEqual(self.plan_path.read_bytes(), before)

    def test_plan_schema_rejects_unknown_operations_fields_and_cross_scope_mapping(self):
        plan = preview_migration(self.delivery, self.plan_path)
        path = next(path for path, row in plan["mapping"].items() if row["operation"] == "copy")
        for mutation in ("unknown-op", "unknown-field", "setuid-mode", "foreign-source", "wrong-target", "missing-root"):
            candidate = deepcopy(plan)
            row = candidate["mapping"][path]
            if mutation == "unknown-op":
                row["operation"] = "shell"
            elif mutation == "unknown-field":
                row["command"] = "untrusted"
            elif mutation == "setuid-mode":
                row["mode"] = 0o4755
            elif mutation == "foreign-source":
                row["source"] = "../outside"
            elif mutation == "wrong-target":
                candidate["mapping"]["leo-ppt-generator/unrelated.py"] = candidate["mapping"].pop(path)
            else:
                candidate["closure"]["roots"][0]["path"] = "elsewhere"
            candidate["plan_digest"] = digest({k: v for k, v in candidate.items() if k != "plan_digest"})
            with self.subTest(mutation=mutation), self.assertRaises(MigrationError):
                validate_plan_contract(candidate)

    def replacement_input(self, path="leo-ppt-generator/runtime/src/consumer.py", target=b"VALUE = 'v2'\n"):
        source = self.delivery / path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"VALUE = 'references/styles/legacy.md'\n")
        entry = {"path": path, "expected": file_state(self.delivery, path),
                 "target": {"payload": base64.b64encode(target).decode(),
                            "sha256": hashlib.sha256(target).hexdigest(), "mode": 0o644}}
        manifest = {"schema_version": 1, "kind": "migration-consumer-replacements", "replacements": [entry]}
        self.work.mkdir(exist_ok=True)
        path = self.work / "consumer-replacements.json"
        atomic_write_json(path, manifest)
        return file_reference(self.work, path.name), manifest

    def test_preview_freezes_consumer_replacement_and_target_closure_without_writing_delivery(self):
        reference, manifest = self.replacement_input()
        path = manifest["replacements"][0]["path"]
        before = file_state(self.delivery, path)
        plan = preview_migration(self.delivery, self.plan_path, consumer_replacements=reference)
        self.assertEqual(plan["mapping"][path]["operation"], "replace")
        self.assertEqual(plan["mapping"][path]["expected"], before)
        self.assertEqual(plan["closure"]["active_legacy_hits"], 1)
        self.assertEqual(plan["target_closure"]["active_legacy_hits"], 0)
        self.assertEqual(plan["target_closure_digest"], digest(plan["target_closure"]))
        self.assertEqual(file_state(self.delivery, path), before)
        self.assertEqual(_target_bytes(plan, path), b"VALUE = 'v2'\n")
        self.assertEqual(preview_migration(self.delivery, self.plan_path, consumer_replacements=reference), plan)
        atomic_write_json(self.work / reference["path"], {"changed": True})
        self.assertEqual(_target_bytes(plan, path), b"VALUE = 'v2'\n")
        target = self.root / "cas-target"
        (target / path).parent.mkdir(parents=True)
        (target / path).write_bytes((self.delivery / path).read_bytes())
        result = compare_and_swap_file(target, path, expected=before, body=_target_bytes(plan, path), mode=0o644)
        self.assertEqual(result["sha256"], plan["target_hashes"][path])
        self.assertEqual(plan["gate"], "U7-A")
        with self.assertRaisesRegex(MigrationError, "migration_execution_plan_required"):
            stage_migration(self.plan_path, self.root / "shadow")
        self.assertFalse((self.root / "shadow").exists())

    def test_consumer_replacements_reject_drift_tamper_duplicates_and_scope_escape(self):
        reference, manifest = self.replacement_input()
        for mutation in ("source-drift", "target-hash", "invalid-base64", "duplicate", "new-file",
                         "traversal", "library", "outside", "unknown-field", "setuid", "policy-owner"):
            candidate = deepcopy(manifest)
            entry = candidate["replacements"][0]
            if mutation == "source-drift":
                entry["expected"]["sha256"] = "0" * 64
            elif mutation == "target-hash":
                entry["target"]["sha256"] = "0" * 64
            elif mutation == "invalid-base64":
                entry["target"]["payload"] = "not base64!!!"
            elif mutation == "duplicate":
                candidate["replacements"].append(deepcopy(entry))
            elif mutation == "unknown-field":
                entry["command"] = "untrusted"
            elif mutation == "setuid":
                entry["target"]["mode"] = 0o4755
            else:
                entry["path"] = {"new-file": "leo-ppt-generator/runtime/src/new.py",
                    "traversal": "leo-ppt-generator/runtime/src/../escape.py",
                    "library": "leo-ppt-generator/template-library/library.json",
                    "outside": "docs/plans/outside.md",
                    "policy-owner": "leo-ppt-generator/runtime/src/leo_ppt_generator/asset_resolver.py"}[mutation]
            atomic_write_json(self.work / reference["path"], candidate)
            with self.subTest(mutation=mutation), self.assertRaises(MigrationError):
                preview_migration(self.delivery, self.plan_path,
                                  consumer_replacements=file_reference(self.work, reference["path"]))
            self.assertFalse(self.plan_path.exists())

    def test_plan_rejects_replacement_payload_expected_state_and_closure_tampering(self):
        reference, manifest = self.replacement_input()
        plan = preview_migration(self.delivery, self.plan_path, consumer_replacements=reference)
        path = manifest["replacements"][0]["path"]
        for mutation in ("payload", "expected", "target-hash", "closure", "source", "mode"):
            candidate = deepcopy(plan)
            row = candidate["mapping"][path]
            if mutation == "payload":
                row["payload"] = base64.b64encode(b"tampered").decode()
            elif mutation == "expected":
                row["expected"]["sha256"] = "0" * 64
            elif mutation == "target-hash":
                candidate["target_hashes"][path] = "0" * 64
            elif mutation == "closure":
                candidate["target_closure"]["active_legacy_hits"] = 42
            elif mutation == "source":
                row["source"] = "leo-ppt-generator/runtime/src/another.py"
            else:
                row["mode"] = 0o4755
            candidate["plan_digest"] = digest({k: v for k, v in candidate.items() if k != "plan_digest"})
            with self.subTest(mutation=mutation), self.assertRaises(MigrationError):
                validate_plan_contract(candidate)

    def test_preview_replacement_cli_and_target_closure_match_real_copied_bytes(self):
        reference, manifest = self.replacement_input()
        command = [str(ROOT / "runtime/.venv/bin/python"), str(ROOT / "scripts/migrate_template_library.py"),
                   "preview", "--source-root", str(self.delivery), "--out-plan", str(self.plan_path),
                   "--consumer-replacements", str(self.work / reference["path"])]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["gate"], "U7-A")
        plan = json.loads(self.plan_path.read_text())
        path = manifest["replacements"][0]["path"]
        shadow = self.root / "bytes-only-shadow"
        shutil.copytree(self.delivery, shadow, ignore=shutil.ignore_patterns(".git"))
        with self.assertRaisesRegex(MigrationError, "migration_target_closure_mismatch"):
            _verify_target_closure(plan, shadow)
        compare_and_swap_file(shadow, path, expected=plan["source_snapshot"][path], body=_target_bytes(plan, path))
        self.assertEqual(_verify_target_closure(plan, shadow)["active_legacy_hits"], 0)
        (shadow / path).write_bytes(b"references/styles/external.md\n")
        with self.assertRaisesRegex(MigrationError, "migration_target_closure_mismatch"):
            _verify_target_closure(plan, shadow)

    def test_replacements_reject_transaction_owner_changes_before_plan_creation(self):
        for owner in ("library_migration.py", "storage.py", "schemas/migration-plan-v2.schema.json"):
            reference, _ = self.replacement_input("leo-ppt-generator/runtime/src/leo_ppt_generator/" + owner)
            with self.subTest(owner=owner), self.assertRaisesRegex(MigrationError, "migration_transaction_owner_replacement_forbidden"):
                preview_migration(self.delivery, self.plan_path, consumer_replacements=reference)
            self.assertFalse(self.plan_path.exists())

    def test_catalog_owner_replacement_builds_and_verifies_with_real_target_runtime(self):
        from leo_ppt_generator.library_migration import _catalog_subprocess, _migration_catalog_details, _migration_catalog_files
        from leo_ppt_generator.template_catalog import CatalogError, LibraryContext, read_catalog
        package = self.delivery / "leo-ppt-generator"
        shutil.copytree(ROOT / "runtime/src", package / "runtime/src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "assets", package / "assets")
        path = "leo-ppt-generator/runtime/src/leo_ppt_generator/asset_resolver.py"
        before = file_state(self.delivery, path)
        target = (self.delivery / path).read_bytes() + "\n# 目标 catalog 策略字节回归。\n".encode()
        renderer = "leo-ppt-generator/runtime/src/leo_ppt_generator/render/page.py"
        renderer_before = file_state(self.delivery, renderer)
        renderer_target = (self.delivery / renderer).read_bytes() + "\n# 目标执行环境字节回归。\n".encode()
        self.work.mkdir(exist_ok=True)
        manifest = self.work / "consumer-replacements.json"
        atomic_write_json(manifest, {"schema_version": 1, "kind": "migration-consumer-replacements", "replacements": [
            {"path": path, "expected": before, "target": {"payload": base64.b64encode(target).decode(),
                "sha256": hashlib.sha256(target).hexdigest(), "mode": before["mode"]}},
            {"path": renderer, "expected": renderer_before, "target": {"payload": base64.b64encode(renderer_target).decode(),
                "sha256": hashlib.sha256(renderer_target).hexdigest(), "mode": renderer_before["mode"]}}]})
        plan = preview_migration(self.delivery, self.plan_path, consumer_replacements=file_reference(self.work, manifest.name))
        shadow = self.root / "target-owner-bytes"
        for relative, row in plan["mapping"].items():
            destination = shadow / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(_target_bytes(plan, relative))
            destination.chmod(row["mode"])
        result = _catalog_subprocess(shadow / "leo-ppt-generator", "inspect")
        self.assertEqual(result["owners"]["asset_resolver.py"], hashlib.sha256(target).hexdigest())
        self.assertEqual(file_state(self.delivery, path), before)
        self.assertEqual(result["result"]["registry"]["schema_version"], 2)
        from leo_ppt_generator.qualification import environment_fingerprint
        current_environment = environment_fingerprint()
        self.assertNotEqual(result["environment"]["execution_source_digest"], current_environment["execution_source_digest"])
        for field in ("font_files", "vendor_files", "browser_binaries", "packages"):
            self.assertEqual(result["environment"][field], current_environment[field])
        self.assertEqual(_migration_catalog_details(plan, shadow), result["result"])
        self.assertEqual(_migration_catalog_files(plan, shadow), result["result"]["catalog"])
        with self.assertRaisesRegex(CatalogError, "stale_catalog"):
            read_catalog(LibraryContext(shadow / "leo-ppt-generator/template-library"))
        self.assertEqual(plan["gate"], "U7-A")
        with self.assertRaisesRegex(MigrationError, "migration_execution_plan_required"):
            stage_migration(self.plan_path, self.root / "formal-shadow")

    def test_replacement_symlink_and_post_preview_source_drift_cannot_be_applied(self):
        from leo_ppt_generator.library_migration import _check_source
        reference, manifest = self.replacement_input()
        path = manifest["replacements"][0]["path"]
        plan = preview_migration(self.delivery, self.plan_path, consumer_replacements=reference)
        (self.delivery / path).write_bytes(b"external new content\n")
        with self.assertRaisesRegex(MigrationError, "migration_delivery_head_or_dirty_drift"):
            _check_source(plan)
        (self.delivery / path).unlink()
        (self.delivery / path).symlink_to(self.delivery / "leo-ppt-generator/template-library/library.json")
        with self.assertRaisesRegex(MigrationError, "migration_symlink_rejected"):
            preview_migration(self.delivery, self.work / "another" / "migration-plan.json")


if __name__ == "__main__":
    unittest.main()
