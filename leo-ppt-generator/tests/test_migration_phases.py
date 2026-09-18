"""正式五阶段入口的拒绝门；临时测试不会伪造真实视觉 prerequisite。"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from leo_ppt_generator.library_migration import (
    MigrationError, preview_migration, stage_migration, publish_migration, cleanup_migration,
    validate_plan_contract,
)
from leo_ppt_generator.qualification import digest
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


if __name__ == "__main__":
    unittest.main()
