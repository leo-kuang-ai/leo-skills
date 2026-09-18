"""真实文件事务边界；这些测试不签发 Provider、视觉或实际发布通过。"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from leo_ppt_generator.library_migration import (
    MigrationError, compare_and_swap_file, file_state, locked_publication,
    maintenance_path, require_available, scan_consumer_closure, verify_final_receipt,
    git_state, publish_targets, CURRENT,
    _recover_cleanup_rollback, _release_cleanup_maintenance, _restore_entries,
    _write_journal, _write_sealed, _staged_hashes, RECEIPT_KIND,
    _unlink_cas,
    _seal_publication_receipt, _verify_publication_confirmation, PUBLICATION_IDENTITY,
)
from leo_ppt_generator.qualification import file_reference, digest
from leo_ppt_generator.storage import atomic_write_json


class MigrationTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.relative = "leo-ppt-generator/a.json"
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"before")

    def test_cas_refuses_external_change_before_replace(self):
        expected = file_state(self.root, self.relative)
        def change(phase, relative):
            self.path.write_bytes(b"external")
        with self.assertRaisesRegex(MigrationError, "migration_cas_mismatch"):
            compare_and_swap_file(self.root, self.relative, expected=expected, body=b"after", checkpoint=change)
        self.assertEqual(self.path.read_bytes(), b"external")
        self.assertEqual(list(self.path.parent.glob(".migration-*")), [])

    def test_staging_convergence_rejects_unlisted_files_and_permission_drift(self):
        for command in (["git", "init", "-q"], ["git", "add", "."]):
            subprocess.run(command, cwd=self.root, check=True, capture_output=True)
        expected = file_state(self.root, self.relative)
        plan = {"target_hashes": {self.relative: expected["sha256"]},
                "mapping": {self.relative: {"mode": expected["mode"]}}, "delete_allowlist": []}
        self.assertEqual(_staged_hashes(plan, self.root), plan["target_hashes"])
        extra = self.path.with_name("not-in-plan.py")
        extra.write_text("external bytes")
        with self.assertRaisesRegex(MigrationError, "migration_convergence_file_set_mismatch"):
            _staged_hashes(plan, self.root)
        self.assertEqual(extra.read_text(), "external bytes")
        extra.unlink()
        self.path.chmod(0o755)
        with self.assertRaisesRegex(MigrationError, "migration_convergence_file_state_mismatch"):
            _staged_hashes(plan, self.root)

    def test_staging_inventory_checks_ignored_library_bytes_and_symlinks(self):
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True, capture_output=True)
        (self.root / ".gitignore").write_text("*.hidden\n")
        expected = file_state(self.root, self.relative)
        plan = {"target_hashes": {self.relative: expected["sha256"]},
                "mapping": {self.relative: {"mode": expected["mode"]}}, "delete_allowlist": []}
        library = self.path.parent / "template-library"
        library.mkdir()
        hidden = library / "extra.hidden"
        hidden.write_text("ignored but executable-library-owned")
        with self.assertRaisesRegex(MigrationError, "migration_convergence_file_set_mismatch"):
            _staged_hashes(plan, self.root)
        hidden.unlink()
        hidden.symlink_to(self.path)
        with self.assertRaisesRegex(MigrationError, "migration_symlink_rejected"):
            _staged_hashes(plan, self.root)

    def test_cas_replaces_only_the_bound_file_and_preserves_mode(self):
        other = self.path.with_name("unrelated")
        other.write_bytes(b"external")
        os.chmod(self.path, 0o755)
        result = compare_and_swap_file(self.root, self.relative, expected=file_state(self.root, self.relative), body=b"after", mode=0o755)
        self.assertEqual(result, {"type": "file", "sha256": hashlib.sha256(b"after").hexdigest(), "mode": 0o755})
        self.assertEqual(other.read_bytes(), b"external")

    def test_delete_cas_rechecks_external_bytes_and_symlink_before_unlink(self):
        expected = file_state(self.root, self.relative)
        def drift(phase, relative):
            self.path.write_bytes(b"external-before-delete")
        with self.assertRaisesRegex(MigrationError, "migration_cleanup_drift"):
            _unlink_cas(self.root, self.relative, expected, checkpoint=drift)
        self.assertEqual(self.path.read_bytes(), b"external-before-delete")
        _unlink_cas(self.root, self.relative, file_state(self.root, self.relative))
        self.assertFalse(self.path.exists())
        external = self.path.with_name("external")
        external.write_bytes(b"preserved")
        self.path.symlink_to(external)
        with self.assertRaisesRegex(MigrationError, "symlink"):
            _unlink_cas(self.root, self.relative, expected)
        self.assertEqual(external.read_bytes(), b"preserved")

    def test_file_and_parent_symlinks_are_rejected_without_following(self):
        original = self.path.with_name("original")
        self.path.rename(original)
        self.path.symlink_to(original)
        with self.assertRaisesRegex(MigrationError, "symlink"):
            file_state(self.root, self.relative)
        self.assertEqual(original.read_bytes(), b"before")
        alias = self.root / "alias"
        alias.symlink_to(self.path.parent, target_is_directory=True)
        with self.assertRaisesRegex(MigrationError, "symlink"):
            file_state(self.root, "alias/original")

    def test_maintenance_survives_interrupt_and_rejects_another_owner(self):
        library = self.root / "leo-ppt-generator/template-library"
        with self.assertRaises(InterruptedError):
            with locked_publication(self.root, plan_digest="a" * 64):
                with self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
                    require_available(library)
                with self.assertRaisesRegex(MigrationError, "lock_busy"):
                    with locked_publication(self.root, plan_digest="a" * 64):
                        pass
                raise InterruptedError()
        self.assertTrue(maintenance_path(self.root).exists())
        with self.assertRaisesRegex(MigrationError, "owner_conflict"):
            with locked_publication(self.root, plan_digest="b" * 64):
                pass
        with locked_publication(self.root, plan_digest="a" * 64):
            self.assertTrue(maintenance_path(self.root).exists())

    def test_handwritten_convergence_cannot_grant_delivery_visual_pass(self):
        atomic_write_json(self.root / "fake.json", {"status": "passed", "staging_hashes": {"a": "b"}, "delivery_hashes": {"a": "b"}})
        with self.assertRaises(MigrationError):
            verify_final_receipt(self.root, file_reference(self.root, "fake.json"), stage_receipt={})

    def test_shared_library_operation_blocks_publication_across_processes(self):
        from leo_ppt_generator.library_migration import library_operation
        library = self.root / "leo-ppt-generator/template-library"
        library.mkdir()
        before = list(library.iterdir())
        child = """
import sys
from pathlib import Path
from leo_ppt_generator.library_migration import MigrationError, locked_publication
try:
    with locked_publication(Path(sys.argv[1]), plan_digest='a' * 64):
        print('acquired')
except MigrationError as exc:
    print(str(exc))
    raise SystemExit(23)
"""
        with library_operation(library), library_operation(library):
            process = subprocess.run([sys.executable, "-c", child, str(self.root)], capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 23, process.stderr)
            self.assertEqual(process.stdout.strip(), "migration_maintenance_lock_busy")
            self.assertEqual(list(library.iterdir()), before)
        process = subprocess.run([sys.executable, "-c", child, str(self.root)], capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(maintenance_path(self.root).exists())
        with self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
            with library_operation(library):
                self.fail("持久 maintenance 未阻断消费者")

    def test_reader_hard_exit_releases_directory_lock_without_writing_installation(self):
        library = self.root / "leo-ppt-generator/template-library"
        library.mkdir(mode=0o555)
        child = """
import os,sys
from leo_ppt_generator.library_migration import library_operation
with library_operation(sys.argv[1]):
    os._exit(86)
"""
        result = subprocess.run([sys.executable, "-c", child, str(library)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 86, result.stderr)
        self.assertEqual(list(library.iterdir()), [])
        library.chmod(0o755)
        with locked_publication(self.root, plan_digest="a" * 64):
            self.assertTrue(maintenance_path(self.root).exists())

    def test_exclusive_lock_rejects_reader_even_before_marker_is_written(self):
        import fcntl
        from leo_ppt_generator.library_migration import library_operation
        library = self.root / "leo-ppt-generator/template-library"
        library.mkdir()
        fd = os.open(library, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertFalse(maintenance_path(self.root).exists())
            with self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
                with library_operation(library):
                    self.fail("独占锁未阻断消费者")
        finally:
            os.close(fd)
        with library_operation(library):
            self.assertEqual(list(library.iterdir()), [])

    def test_closure_includes_eval_hits_and_keeps_control_distinct(self):
        for relative in ("leo-ppt-generator/evals/case.yaml", "leo-ppt-generator/runtime/src/owner.py", "docs/plans/plan.md"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("references/styles/example.md\n")
        result = scan_consumer_closure(self.root)
        self.assertEqual(result["unclassified_hits"], 0)
        self.assertEqual(result["active_legacy_hits"], 2)
        self.assertEqual(len(result["roots"]), 11)
        self.assertEqual({row["classification"] for row in result["hits"]}, {"active-consumer", "plan-control"})

    def test_closure_gate_rejects_zero_hits_from_missing_or_wrong_type_roots(self):
        from leo_ppt_generator.library_migration import CLOSURE_ROOTS, CLOSURE_FILES, verify_consumer_closure
        with self.assertRaisesRegex(MigrationError, "migration_closure_roots_incomplete"):
            verify_consumer_closure(self.root)
        for relative in CLOSURE_ROOTS:
            path = self.root / relative
            if relative in CLOSURE_FILES:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# 当前消费者\n")
            else:
                path.mkdir(parents=True, exist_ok=True)
        self.assertEqual(verify_consumer_closure(self.root)["active_legacy_hits"], 0)
        with self.assertRaisesRegex(MigrationError, "migration_closure_roots_incomplete"):
            verify_consumer_closure(self.root / "leo-ppt-generator")
        wrong = self.root / "leo-ppt-generator/runtime/src"
        wrong.rmdir()
        wrong.write_text("这不是源码目录")
        with self.assertRaisesRegex(MigrationError, "migration_closure_roots_incomplete"):
            verify_consumer_closure(self.root)

    def test_historical_document_markers_do_not_hide_active_sources_or_guides(self):
        documents = {
            "docs/leo-ppt-generator/architecture/history.md": "---\nstatus: historical-reference\n---\n",
            "docs/leo-ppt-generator/evals/old.md": "# 多行业自主测试报告(2026-08-30)\n",
            "docs/leo-ppt-generator/tech-plans/old.md": "性质：技术方案（HOW）\n",
            "docs/leo-ppt-generator/current-guide.md": "# 当前指南（2026-08-01）\n",
            "leo-ppt-generator/runtime/src/history.py": "# status: historical-reference\n",
        }
        for name, heading in documents.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(heading + "references/styles/example.md\n")
        report = scan_consumer_closure(self.root)
        self.assertEqual(len(report["hits"]), 5)
        self.assertEqual(report["active_legacy_hits"], 2)
        self.assertEqual(report["unclassified_hits"], 0)
        history = self.root / "docs/leo-ppt-generator/architecture/history.md"
        history.write_text("# 当前指南\nreferences/styles/example.md\n")
        self.assertEqual(scan_consumer_closure(self.root)["active_legacy_hits"], 3)

    def publication_inputs(self):
        current = self.root / CURRENT
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_bytes(b"old-current")
        for command in (["git", "init", "-q"], ["git", "add", "."],
                        ["git", "-c", "user.name=Transaction test", "-c", "user.email=test@example.invalid", "commit", "-qm", "临时事务基线"]):
            subprocess.run(command, cwd=self.root, check=True, capture_output=True)
        work_temp = tempfile.TemporaryDirectory()
        self.addCleanup(work_temp.cleanup)
        work = Path(work_temp.name).resolve()
        staging = work / "staging"
        targets = {self.relative: b"after", CURRENT: b"new-current"}
        for path, body in targets.items():
            target = staging / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        state = git_state(self.root)
        plan = {"source_root": str(self.root), "base_revision": state["head"], "dirty_snapshot": state["dirty"],
            "plan_digest": "a" * 64, "source_snapshot": {path: file_state(self.root, path) for path in targets},
            "target_hashes": {path: hashlib.sha256(body).hexdigest() for path, body in targets.items()},
            "mapping": {path: {"mode": 0o644} for path in targets}}
        return work, staging, plan

    def test_publication_switches_current_last_and_records_original_byte_backups(self):
        work, staging, plan = self.publication_inputs()
        seen = []
        journal = publish_targets(work, plan, staging, checkpoint=lambda phase, path: seen.append((phase, path)))
        self.assertEqual(journal["status"], "passed")
        self.assertEqual([path for phase, path in seen if phase == "after_replace"], [self.relative, CURRENT])
        self.assertTrue(journal["current_switched"])
        self.assertTrue(all(row["backup"]["sha256"] == row["before"]["sha256"] for row in journal["files"]))
        self.assertEqual(journal["base_revision"], plan["base_revision"])
        self.assertEqual(len(journal["transaction_id"]), 64)
        marker = json.loads((work / "publication-marker.json").read_text())
        self.assertEqual(marker["state"], "current-switched")
        self.assertEqual(marker["journal_generation"], journal["journal_generation"])
        self.assertEqual(marker["journal_digest"], journal["journal_digest"])
        self.assertEqual(publish_targets(work, plan, staging), journal)

    def test_publication_interrupt_restores_owned_bytes_and_retry_succeeds(self):
        work, staging, plan = self.publication_inputs()
        def interrupt(phase, path):
            if phase == "after_replace" and path == self.relative:
                raise InterruptedError()
        with self.assertRaises(InterruptedError):
            publish_targets(work, plan, staging, checkpoint=interrupt)
        self.assertEqual(self.path.read_bytes(), b"before")
        self.assertEqual((self.root / CURRENT).read_bytes(), b"old-current")
        self.assertEqual(publish_targets(work, plan, staging)["status"], "passed")

    def test_external_postwrite_drift_is_not_overwritten_by_recovery(self):
        work, staging, plan = self.publication_inputs()
        def interrupt(phase, path):
            if phase == "after_replace" and path == self.relative:
                self.path.write_bytes(b"external-new-content")
                raise InterruptedError()
        with self.assertRaises(InterruptedError):
            publish_targets(work, plan, staging, checkpoint=interrupt)
        self.assertEqual(self.path.read_bytes(), b"external-new-content")
        with self.assertRaisesRegex(MigrationError, "migration_restore_external_drift"):
            publish_targets(work, plan, staging)
        self.assertEqual(self.path.read_bytes(), b"external-new-content")

    def _hard_interrupt_publication(self, work, staging, plan, boundary, phase="after_replace"):
        atomic_write_json(work / "process-plan.json", plan)
        script = """
import json, os, sys
from pathlib import Path
from leo_ppt_generator.library_migration import locked_publication, publish_targets
work, staging = Path(sys.argv[1]), Path(sys.argv[2])
plan = json.loads((work / 'process-plan.json').read_text())
def stop(phase, path):
    if phase == sys.argv[4] and path == sys.argv[3]:
        os._exit(86)
with locked_publication(plan['source_root'], plan_digest=plan['plan_digest']):
    publish_targets(work, plan, staging, checkpoint=stop)
"""
        result = subprocess.run([sys.executable, "-c", script, str(work), str(staging), boundary, phase],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 86, result.stderr)
        self.assertTrue(maintenance_path(self.root).is_file())
        with self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
            require_available(self.root / "leo-ppt-generator/template-library")

    def test_process_exit_after_page_and_current_recovers_from_durable_journal(self):
        for boundary in (self.relative, CURRENT):
            with self.subTest(boundary=boundary):
                work, staging, plan = self.publication_inputs()
                self._hard_interrupt_publication(work, staging, plan, boundary)
                progress = json.loads((work / "publication-progress.json").read_text())
                self.assertEqual(progress["status"], "running")
                self.assertEqual(progress["current_switched"], boundary == CURRENT)
                with locked_publication(self.root, plan_digest=plan["plan_digest"]):
                    recovered = publish_targets(work, plan, staging)
                self.assertEqual(recovered["status"], "passed")
                self.assertGreater(recovered["journal_generation"], progress["journal_generation"])
                self.assertEqual(recovered["transaction_id"], progress["transaction_id"])
                self.assertEqual(self.path.read_bytes(), b"after")
                self.assertEqual((self.root / CURRENT).read_bytes(), b"new-current")
                # 文件事务测试保留 maintenance，未伪造高层 cleanup 收据。
                self.assertTrue(maintenance_path(self.root).exists())
                self.path.write_bytes(b"before")

    def test_process_exit_then_external_drift_blocks_recovery_without_overwrite(self):
        work, staging, plan = self.publication_inputs()
        self._hard_interrupt_publication(work, staging, plan, self.relative)
        self.path.write_bytes(b"external-after-process-exit")
        with locked_publication(self.root, plan_digest=plan["plan_digest"]):
            with self.assertRaisesRegex(MigrationError, "migration_restore_external_drift"):
                publish_targets(work, plan, staging)
        self.assertEqual(self.path.read_bytes(), b"external-after-process-exit")
        self.assertEqual((self.root / CURRENT).read_bytes(), b"old-current")

    def test_process_exit_at_both_confirmation_boundaries_blocks_unconfirmed_receipts(self):
        for phase in ("after_prepared_marker", "before_current_confirmation"):
            with self.subTest(phase=phase):
                work, staging, plan = self.publication_inputs()
                self._hard_interrupt_publication(work, staging, plan, CURRENT, phase)
                before = json.loads((work / "publication-progress.json").read_text())
                self.assertEqual(json.loads((work / "publication-marker.json").read_text())["state"], "prepared")
                with self.assertRaisesRegex(MigrationError, "marker_unconfirmed"):
                    _seal_publication_receipt(work, plan, {"scope": "file-transaction-test"},
                        expected=file_state(work, "publication-receipt.json"))
                self.assertFalse((work / "publication-receipt.json").exists())
                with locked_publication(self.root, plan_digest=plan["plan_digest"]):
                    recovered = publish_targets(work, plan, staging)
                self.assertGreater(recovered["journal_generation"], before["journal_generation"])
                self.assertEqual(_verify_publication_confirmation(work, plan), recovered)
                self.path.write_bytes(b"before")

    def test_process_exit_after_confirmation_is_idempotent_without_inventing_a_receipt(self):
        work, staging, plan = self.publication_inputs()
        self._hard_interrupt_publication(work, staging, plan, CURRENT, "after_current_confirmation")
        confirmed = _verify_publication_confirmation(work, plan)
        self.assertFalse((work / "publication-receipt.json").exists())
        with locked_publication(self.root, plan_digest=plan["plan_digest"]):
            self.assertEqual(publish_targets(work, plan, staging), confirmed)

    def test_missing_confirmation_marker_blocks_recovery_without_modifying_delivery(self):
        work, staging, plan = self.publication_inputs()
        publish_targets(work, plan, staging)
        (work / "publication-marker.json").unlink()
        with self.assertRaisesRegex(MigrationError, "marker_unconfirmed"):
            publish_targets(work, plan, staging)
        self.assertEqual(self.path.read_bytes(), b"after")
        self.assertEqual((self.root / CURRENT).read_bytes(), b"new-current")

    def test_missing_progress_cannot_reset_generation_under_an_existing_marker(self):
        work, staging, plan = self.publication_inputs()
        publish_targets(work, plan, staging)
        before = (work / "publication-marker.json").read_bytes()
        (work / "publication-progress.json").unlink()
        with self.assertRaisesRegex(MigrationError, "publication_journal_missing"):
            publish_targets(work, plan, staging)
        self.assertEqual((work / "publication-marker.json").read_bytes(), before)
        self.assertEqual(self.path.read_bytes(), b"after")

    def test_resigned_cleanup_journal_cannot_restore_outside_the_allowlist(self):
        work, staging, plan = self.publication_inputs()
        journal = publish_targets(work, plan, staging)
        published = _seal_publication_receipt(work, plan, {"scope": "file-transaction-test"},
            expected=file_state(work, "publication-receipt.json"))
        _write_journal(work / "cleanup-progress.json", {"phase": "cleanup",
            **{key: published[key] for key in (*PUBLICATION_IDENTITY, "journal_generation")},
            "status": "restoring", "files": [journal["files"][0]]})
        with self.assertRaisesRegex(MigrationError, "cleanup_journal_scope_mismatch"):
            _recover_cleanup_rollback(work, plan, published)
        self.assertEqual(self.path.read_bytes(), b"after")

    def test_resigned_wrong_transaction_and_unlisted_journal_paths_cannot_restore(self):
        work, staging, plan = self.publication_inputs()
        original = publish_targets(work, plan, staging)
        outside = self.root / "other-skill/protected.txt"
        outside.parent.mkdir()
        outside.write_bytes(b"external-owner")
        for mutation in ("transaction", "base", "generation", "missing", "unlisted"):
            with self.subTest(mutation=mutation):
                journal = json.loads(json.dumps(original))
                if mutation == "transaction": journal["transaction_id"] = "b" * 64
                elif mutation == "base": journal["base_revision"] = "b" * 40
                elif mutation == "generation": journal["journal_generation"] = True
                elif mutation == "missing": journal.pop("journal_generation")
                else: journal["files"][0]["path"] = "other-skill/protected.txt"
                journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
                atomic_write_json(work / "publication-progress.json", journal)
                with self.assertRaisesRegex(MigrationError, "identity_mismatch|scope_mismatch"):
                    _verify_publication_confirmation(work, plan)
                self.assertEqual(outside.read_bytes(), b"external-owner")
                self.assertEqual(self.path.read_bytes(), b"after")

    def test_receipt_binding_rejects_missing_and_cross_generation_identity(self):
        work, staging, plan = self.publication_inputs()
        publish_targets(work, plan, staging)
        receipt = _seal_publication_receipt(work, plan, {"scope": "file-transaction-test"},
            expected=file_state(work, "publication-receipt.json"))
        for key in (*PUBLICATION_IDENTITY, "journal_generation"):
            with self.subTest(key=key):
                missing = {k: v for k, v in receipt.items() if k != key}
                with self.assertRaisesRegex(MigrationError, "receipt_stale"):
                    _verify_publication_confirmation(work, plan, missing)
        stale = {**receipt, "journal_generation": receipt["journal_generation"] + 1}
        with self.assertRaisesRegex(MigrationError, "receipt_stale"):
            _verify_publication_confirmation(work, plan, stale)

    def test_latest_receipt_cas_preserves_external_edit(self):
        work, staging, plan = self.publication_inputs()
        publish_targets(work, plan, staging)
        expected = file_state(work, "publication-receipt.json")
        (work / "publication-receipt.json").write_bytes(b"external-receipt")
        with self.assertRaisesRegex(MigrationError, "migration_cas_mismatch"):
            _seal_publication_receipt(work, plan, {"scope": "file-transaction-test"}, expected=expected)
        self.assertEqual((work / "publication-receipt.json").read_bytes(), b"external-receipt")

    def test_receipt_issuance_rechecks_delivery_bytes_after_current_confirmation(self):
        work, staging, plan = self.publication_inputs()
        publish_targets(work, plan, staging)
        self.path.write_bytes(b"external-between-publish-and-receipt")
        with self.assertRaisesRegex(MigrationError, "publication_delivery_drift"):
            _seal_publication_receipt(work, plan, {"scope": "file-transaction-test"},
                expected=file_state(work, "publication-receipt.json"))
        self.assertFalse((work / "publication-receipt.json").exists())
        self.assertEqual(self.path.read_bytes(), b"external-between-publish-and-receipt")

    def test_cleanup_rollback_advances_generation_and_invalidates_old_receipt(self):
        work, staging, plan = self.publication_inputs()
        journal = publish_targets(work, plan, staging)
        original = json.loads(json.dumps(journal))
        published = _seal_publication_receipt(work, plan, {"scope": "file-transaction-test"},
            expected=file_state(work, "publication-receipt.json"))
        archive_bytes = (work / published["journal"]["path"]).read_bytes()
        self.assertEqual(_restore_entries(work, self.root, journal["files"]), [])
        _write_journal(work / "cleanup-progress.json", {"phase": "cleanup",
            **{key: published[key] for key in (*PUBLICATION_IDENTITY, "journal_generation")},
            "status": "restored", "files": []})
        _recover_cleanup_rollback(work, plan, published)
        replayed = publish_targets(work, plan, staging)
        self.assertGreater(replayed["journal_generation"], original["journal_generation"])
        self.assertEqual(replayed["transaction_id"], original["transaction_id"])
        with self.assertRaisesRegex(MigrationError, "publication_receipt_stale"):
            _verify_publication_confirmation(work, plan, published)
        fresh = _seal_publication_receipt(work, plan, {"scope": "file-transaction-test"},
            expected=file_state(work, "publication-receipt.json"))
        self.assertEqual(_verify_publication_confirmation(work, plan, fresh), replayed)
        self.assertEqual((work / published["journal"]["path"]).read_bytes(), archive_bytes)
        self.assertNotEqual(fresh["journal"], published["journal"])
        self.assertEqual(self.path.read_bytes(), b"after")

    def test_cleanup_rollback_preserves_new_external_bytes(self):
        work, staging, plan = self.publication_inputs()
        journal = publish_targets(work, plan, staging)
        published = _seal_publication_receipt(work, plan, {"scope": "file-transaction-test"},
            expected=file_state(work, "publication-receipt.json"))
        _write_journal(work / "cleanup-progress.json", {"phase": "cleanup",
            **{key: published[key] for key in (*PUBLICATION_IDENTITY, "journal_generation")},
            "status": "restoring", "files": []})
        self.path.write_bytes(b"external-during-rollback")
        with self.assertRaisesRegex(MigrationError, "migration_restore_external_drift"):
            _recover_cleanup_rollback(work, plan, published)
        self.assertEqual(self.path.read_bytes(), b"external-during-rollback")
        self.assertEqual(json.loads((work / "cleanup-progress.json").read_text())["status"], "blocked")

    def test_release_requires_durable_matching_final_receipt(self):
        work, _, plan = self.publication_inputs()
        final = {"schema_version": 2, "kind": RECEIPT_KIND, "phase": "cleanup", "status": "passed",
                 "plan_digest": plan["plan_digest"]}
        final_path = work / "cleanup-receipt.json"
        # 只验证文件提交顺序；本例不签发可通过 verify_final_receipt 的完整发布收据。
        with locked_publication(self.root, plan_digest=plan["plan_digest"]) as marker:
            with self.assertRaises(ValueError):
                _release_cleanup_maintenance(work, final_path, marker, final)
            self.assertTrue(marker.exists())
            final = _write_sealed(final_path, final)
            with self.assertRaisesRegex(MigrationError, "final_receipt_conflict"):
                _release_cleanup_maintenance(work, final_path, marker, {**final, "different": True})
            self.assertTrue(marker.exists())
            _release_cleanup_maintenance(work, final_path, marker, final)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
