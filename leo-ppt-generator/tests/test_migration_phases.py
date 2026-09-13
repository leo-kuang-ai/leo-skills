"""迁移五阶段的真实临时目录合同。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_template_library.py"
spec = importlib.util.spec_from_file_location("migration_phases", SCRIPT)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationPhaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.library = self.root / "template-library"
        (self.library / "governance/migration").mkdir(parents=True)
        self.shadow = self.root / "shadow"
        self.shadow.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _manifest(self, delivery_text="old", staged_text="new"):
        staged = self.shadow / "canonical" / "x.json"
        delivery = self.root / "delivery" / "canonical" / "x.json"
        staged.parent.mkdir(parents=True)
        delivery.parent.mkdir(parents=True)
        staged.write_text(staged_text, encoding="utf-8")
        delivery.write_text(delivery_text, encoding="utf-8")
        plan = {"schema_version": 2, "phase": "preview", "entry_count": 1}
        plan["plan_digest"] = migration._plan_digest(plan)
        payload = {
            "schema_version": 2, "plan_digest": plan["plan_digest"],
            "shadow_root": str(self.shadow),
            "entries": [{"path": str(staged), "delivery_path": str(delivery),
                         "sha256": hashlib.sha256(staged.read_bytes()).hexdigest(),
                         "delivery_sha256": hashlib.sha256(delivery.read_bytes()).hexdigest()}],
        }
        (self.library / "governance/migration/staging-manifest.json").write_text(
            json.dumps(payload), encoding="utf-8")
        return plan, delivery

    def test_publish_rejects_digest_mismatch(self):
        plan, _ = self._manifest()
        with self.assertRaisesRegex(ValueError, "staging_manifest_plan_mismatch"):
            migration.publish_staged_manifest(self.library, plan_digest="wrong",
                                              delivery_root=self.root)

    def test_publish_is_cas_and_records_journal(self):
        plan, delivery = self._manifest()
        journal = migration.publish_staged_manifest(self.library,
                                                    plan_digest=plan["plan_digest"],
                                                    delivery_root=self.root)
        self.assertEqual(journal["status"], "published")
        self.assertEqual(delivery.read_text(encoding="utf-8"), "new")
        stored = json.loads((self.library / "governance/migration/publication-journal.json").read_text())
        self.assertEqual(stored["status"], "published")

    def test_publish_rejects_delivery_drift_and_marks_journal_failed(self):
        plan, delivery = self._manifest()
        delivery.write_text("external", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "delivery_drift"):
            migration.publish_staged_manifest(self.library, plan_digest=plan["plan_digest"],
                                              delivery_root=self.root)
        journal = json.loads((self.library / "governance/migration/publication-journal.json").read_text())
        self.assertEqual(journal["status"], "failed")

    def test_cleanup_deletes_only_hash_bound_allowlist(self):
        legacy = self.root / "legacy" / "a.txt"
        legacy.parent.mkdir()
        legacy.write_text("legacy", encoding="utf-8")
        plan = {"schema_version": 2, "delete_allowlist": ["legacy/a.txt"],
                "source_snapshot": {"files": {
                    "legacy/a.txt": hashlib.sha256(legacy.read_bytes()).hexdigest()}}}
        plan["plan_digest"] = migration._plan_digest(plan)
        receipt = {"phase": "published", "plan_digest": plan["plan_digest"]}
        result = migration.cleanup_published(self.library, plan, receipt,
                                             delivery_root=self.root)
        self.assertEqual(result["deleted"], ["legacy/a.txt"])
        self.assertFalse(legacy.exists())

    def test_cleanup_rejects_external_drift(self):
        legacy = self.root / "legacy" / "a.txt"
        legacy.parent.mkdir()
        legacy.write_text("changed", encoding="utf-8")
        plan = {"schema_version": 2, "delete_allowlist": ["legacy/a.txt"],
                "source_snapshot": {"files": {"legacy/a.txt": "old-hash"}}}
        plan["plan_digest"] = migration._plan_digest(plan)
        receipt = {"phase": "published", "plan_digest": plan["plan_digest"]}
        with self.assertRaisesRegex(ValueError, "cleanup_drift"):
            migration.cleanup_published(self.library, plan, receipt,
                                        delivery_root=self.root)
        self.assertTrue(legacy.exists())


if __name__ == "__main__":
    unittest.main()
