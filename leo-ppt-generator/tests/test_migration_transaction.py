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

    def test_closure_does_not_hide_readers_next_to_negative_test_words(self):
        path = self.root / "leo-ppt-generator/tests/test_reader.py"
        path.parent.mkdir(parents=True)
        path.write_text("def test_legacy_reader():\n    value = 'references/styles/active.md'\n    assert value\n")
        self.assertEqual(scan_consumer_closure(self.root)["active_legacy_hits"], 1)
        path.write_text("def test_reader(self):\n    with self.assertRaises(ValueError):\n        load('references/styles/rejected.md')\n    load('references/styles/active.md')\n")
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 1)
        self.assertEqual([row["classification"] for row in report["hits"]], ["test-fixture", "active-consumer"])

    def test_closure_qa_profile_is_a_token_not_a_whole_line_exemption(self):
        path = self.root / "leo-ppt-generator/runtime/src/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text("schema = load('qa-profile')\ngovernance = load('qa-profile')\nload('render-qa-profiles.json')\nload('render-qa-profile-v1.schema.json')\n")
        self.assertEqual(scan_consumer_closure(self.root)["active_legacy_hits"], 2)

    def test_closure_canonical_variable_joins_require_proven_canonical_root(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text("from pathlib import Path\nLIBRARY = Path('template-library')\nCANONICAL_ROOT = LIBRARY / 'canonical'\nSTYLES = CANONICAL_ROOT / 'styles'\nBRANDS = CANONICAL_ROOT.joinpath('brands')\nOTHER_ROOT = Path('other')\nOTHER = OTHER_ROOT / 'styles'\n")
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 2)
        self.assertEqual({row["line"] for row in report["hits"]}, {4, 5})

    def test_closure_detects_joinpath_multi_arg_and_variable_folder_paths(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "from pathlib import Path\n"
            "ROOT = Path('template-library')\n"
            "kind = 'styles'\n"
            "def read():\n"
            "    return ROOT.joinpath('canonical', kind, 'example.json').read_text()\n"
        )
        report = scan_consumer_closure(self.root)
        self.assertGreaterEqual(report["active_legacy_hits"], 1)

    def test_closure_is_conservative_when_same_name_is_bound_in_multiple_functions(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "from pathlib import Path\n"
            "def builtin():\n"
            "    root = Path('template-library')\n"
            "    return root / 'canonical' / 'styles' / 'a.json'\n"
            "def user():\n"
            "    root = Path('other')\n"
            "    return root / 'styles' / 'b.json'\n"
        )
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 1)
        self.assertEqual(report["unclassified_hits"], 0)
        self.assertEqual({row["line"] for row in report["hits"]}, {4})

    def test_closure_resolves_complete_paths_across_join_variables_and_string_add(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        expressions = (
            "Path('template-library').joinpath('canonical', 'styles', 'demo.json')",
            "Path('template-library/' + 'canonical/' + 'styles/demo.json')",
            "root / kind / 'demo.json'",
            "Path('template-library', 'canonical', kind, 'demo.json')",
        )
        for expression in expressions:
            with self.subTest(expression=expression):
                path.write_text("from pathlib import Path\nroot = Path('template-library') / 'canonical'\nkind = 'styles'\nvalue = " + expression + "\n")
                report = scan_consumer_closure(self.root)
                self.assertEqual(report["active_legacy_hits"], 1)
                self.assertEqual(report["unclassified_hits"], 0)
                self.assertEqual({row["line"] for row in report["hits"]}, {4})

    def test_closure_requires_adjacent_canonical_and_legacy_folder_components(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text(
            "from pathlib import Path\n"
            "root = Path('template-library')\n"
            "kind = 'styles'\n"
            "a = root / kind\n"
            "b = root.joinpath('canonical', 'visual', kind)\n"
            "c = Path('other').joinpath(kind)\n"
            "d = Path('canonical-new') / kind\n"
            "e = Path('canonical') / 'styleguide'\n"
            "f = Path('canonical') / '/other' / kind\n"
        )
        self.assertEqual(scan_consumer_closure(self.root)["hits"], [])

    def test_closure_dynamic_file_names_and_log_words_are_not_legacy_directories(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text(
            "from pathlib import Path\n"
            "def report(folder, name, count):\n"
            "    file = folder / f'{name}.layouts.json'\n"
            "    label = f'TOTAL: {count} templates' + ' complete'\n"
            "    number = count + 1\n"
            "    dynamic = str(count) + name\n"
            "    return file, label, number, dynamic\n"
        )
        self.assertEqual(scan_consumer_closure(self.root)["hits"], [])

    def test_closure_literal_loop_destinations_are_resolved_without_directory_guessing(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text(
            "from pathlib import Path\n"
            "root = Path('canonical')\n"
            "def current():\n"
            "    for family, destination in [('a', 'visual/styles'), ('b', 'semantic/page-types')]:\n"
            "        item = root / destination\n"
            "def legacy():\n"
            "    for family, destination in [('a', 'styles'), ('b', 'themes')]:\n"
            "        item = root / destination\n"
        )
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 1)
        self.assertEqual(report["unclassified_hits"], 0)
        path.write_text(
            "from pathlib import Path\n"
            "root = Path('canonical')\n"
            "for family, destination in [('a', 'visual/styles'), ('b', 'semantic/page-types')]:\n"
            "    current = root / destination\n"
        )
        self.assertEqual(scan_consumer_closure(self.root)["hits"], [])

    def test_closure_defaults_are_candidates_but_do_not_prove_all_callers_safe(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text(
            "from pathlib import Path\n"
            "def legacy(root=Path('canonical')):\n"
            "    return root / 'styles'\n"
            "def dynamic(root=Path('other')):\n"
            "    return root / 'styles'\n"
        )
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 1)
        self.assertEqual(report["unclassified_hits"], 1)

    def test_closure_literal_dictionary_items_and_sorted_destructuring_are_resolved(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        for table, wrapper, legacy in (
            ("{'a': 'styles', 'b': 'visual/themes'}", "TABLE.items()", 1),
            ("{'a': 'styles'}", "sorted(TABLE.items())", 1),
            ("{'a': 'visual/styles', 'b': 'semantic/page-types'}", "sorted(TABLE.items())", 0),
            ("{'a': 'unused'}", "{'a': 'themes'}.items()", 1),
        ):
            with self.subTest(table=table, wrapper=wrapper):
                path.write_text("from pathlib import Path\nTABLE = " + table + "\n"
                    "root = Path('canonical')\nfor kind, destination in " + wrapper + ":\n"
                    "    current = root / destination\n")
                report = scan_consumer_closure(self.root)
                self.assertEqual(report["active_legacy_hits"], legacy)
                self.assertEqual(report["unclassified_hits"], 0)

    def test_closure_dictionary_mutation_escape_rebinding_and_shadowed_sorted_remain_unknown(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        for change in ("TABLE['a'] = dynamic\n", "TABLE.update(dynamic)\n", "alias = TABLE\n",
                       "TABLE = dynamic\n", "sorted = replacement\n"):
            with self.subTest(change=change):
                path.write_text("from pathlib import Path\nTABLE = {'a': 'visual/styles'}\n" + change
                    + "root = Path('canonical')\nfor kind, destination in sorted(TABLE.items()):\n"
                    "    current = root / destination\n")
                report = scan_consumer_closure(self.root)
                self.assertEqual(report["active_legacy_hits"], 0)
                self.assertEqual(report["unclassified_hits"], 1)
        path.write_text("from pathlib import Path\nTABLE = " + repr({str(i): 'visual/styles' for i in range(65)})
            + "\nfor kind, destination in TABLE.items():\n    current = Path('canonical') / destination\n")
        self.assertEqual(scan_consumer_closure(self.root)["unclassified_hits"], 1)

    def test_closure_imported_literal_uses_only_scanned_source_and_target_bytes(self):
        from leo_ppt_generator.library_migration import _scan_consumer_closure
        relative = "leo-ppt-generator/runtime/src/leo_ppt_generator/directory_contract.py"
        owner = self.root / relative
        owner.parent.mkdir(parents=True)
        owner.write_text("TABLE = {'a': 'styles', 'b': 'visual/themes'}\nraise RuntimeError('must not execute')\n")
        reader = self.root / "leo-ppt-generator/scripts/reader.py"
        reader.parent.mkdir(parents=True)
        reader.write_text("from pathlib import Path\n"
            "from leo_ppt_generator.directory_contract import TABLE as FOLDERS\n"
            "for kind, destination in sorted(FOLDERS.items()):\n    current = Path('canonical') / destination\n")
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 1)
        self.assertEqual(report["unclassified_hits"], 0)
        replacement = b"TABLE = {'a': 'visual/styles', 'b': 'semantic/page-types'}\n"
        self.assertEqual(_scan_consumer_closure(self.root, {relative: replacement})["hits"], [])
        self.assertEqual(scan_consumer_closure(self.root)["active_legacy_hits"], 1)
        reader.unlink()
        relative_reader = owner.with_name("reader.py")
        relative_reader.write_text("from pathlib import Path\nfrom .directory_contract import TABLE as FOLDERS\n"
            "for kind, destination in FOLDERS.items():\n    current = Path('canonical') / destination\n")
        self.assertEqual(scan_consumer_closure(self.root)["active_legacy_hits"], 1)

    def test_closure_imported_dictionary_rejects_dynamic_mutable_or_missing_owner(self):
        owner = self.root / "leo-ppt-generator/runtime/src/leo_ppt_generator/directory_contract.py"
        owner.parent.mkdir(parents=True)
        reader = self.root / "leo-ppt-generator/scripts/reader.py"
        reader.parent.mkdir(parents=True)
        reader.write_text("from pathlib import Path\nfrom leo_ppt_generator.directory_contract import TABLE\n"
            "for kind, destination in TABLE.items():\n    current = Path('canonical') / destination\n")
        for body in ("TABLE = dynamic\n", "TABLE = {'a': 'visual/styles'}\nTABLE = dynamic\n",
                     "TABLE = {'a': 'visual/styles'}\nTABLE.update(dynamic)\n",
                     "TABLE = {'a': 'visual/styles'}\nTABLE['a'] = dynamic\n",
                     "TABLE = {'a': 'visual/styles'}\nalias = TABLE\n"):
            with self.subTest(body=body):
                owner.write_text(body)
                report = scan_consumer_closure(self.root)
                self.assertEqual(report["active_legacy_hits"], 0)
                self.assertEqual(report["unclassified_hits"], 1)
        owner.unlink()
        reader.write_text("from pathlib import Path\nfrom leo_ppt_generator.asset_resolver import KIND_CANONICAL_DIR\n"
            "for kind, destination in KIND_CANONICAL_DIR.items():\n    current = Path('canonical') / destination\n")
        self.assertEqual(scan_consumer_closure(self.root)["unclassified_hits"], 1)

    def test_closure_recognizes_home_brand_protocol_without_assuming_dynamic_roots(self):
        path = self.root / "leo-ppt-generator/runtime/src/leo_ppt_generator/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text("from .config.runtime_config import default_home as configured_home\n"
            "def read(home, name):\n    return (home or configured_home()) / 'brands' / f'{name}.md'\n"
            "def dynamic(root, name):\n    return root / 'brands' / f'{name}.md'\n")
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 1)
        self.assertEqual(report["unclassified_hits"], 1)
        self.assertEqual([row["disposition"] for row in report["hits"]], ["migrate", "classify-dynamic-path"])
        path.write_text("from .config.runtime_config import default_home\ndefault_home = arbitrary\n"
            "def read(name):\n    return default_home() / 'brands' / f'{name}.md'\n")
        self.assertEqual(scan_consumer_closure(self.root)["unclassified_hits"], 1)

    def test_closure_lexical_locals_do_not_borrow_another_functions_binding(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text(
            "from pathlib import Path\n"
            "root = Path('template-library') / 'canonical'\n"
            "kind = 'styles'\n"
            "def legacy():\n"
            "    return root / kind\n"
            "def current():\n"
            "    root = Path('other')\n"
            "    return root / kind\n"
            "def nested():\n"
            "    root = Path('canonical') / 'visual'\n"
            "    def read():\n"
            "        return root / kind\n"
            "    return read()\n"
        )
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 1)
        self.assertEqual(report["unclassified_hits"], 0)
        self.assertEqual({row["line"] for row in report["hits"]}, {5})

    def test_closure_dynamic_canonical_child_is_unclassified_and_cannot_pass_gate(self):
        from leo_ppt_generator.library_migration import CLOSURE_ROOTS, CLOSURE_FILES, verify_consumer_closure
        for relative in CLOSURE_ROOTS:
            path = self.root / relative
            if relative in CLOSURE_FILES:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("")
            else:
                path.mkdir(parents=True, exist_ok=True)
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.write_text(
            "from pathlib import Path\n"
            "root = Path('template-library') / 'canonical'\n"
            "def read(kind):\n"
            "    return root / kind\n"
        )
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 0)
        self.assertEqual(report["unclassified_hits"], 1)
        self.assertEqual(report["hits"][0]["disposition"], "classify-dynamic-path")
        with self.assertRaisesRegex(MigrationError, "migration_consumer_closure_not_zero"):
            verify_consumer_closure(self.root)

    def test_closure_parameter_shadowing_does_not_borrow_safe_global_root(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text(
            "from pathlib import Path\n"
            "root = Path('other')\n"
            "def read(root):\n"
            "    return root / 'styles'\n"
        )
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 0)
        self.assertEqual(report["unclassified_hits"], 1)

    def test_closure_global_and_nonlocal_rebinding_do_not_keep_a_safe_root(self):
        path = self.root / "leo-ppt-generator/scripts/reader.py"
        path.parent.mkdir(parents=True)
        path.write_text(
            "from pathlib import Path\n"
            "root = Path('other')\n"
            "def configure():\n"
            "    global root\n"
            "    root = Path('canonical')\n"
            "def read():\n"
            "    return root / 'styles'\n"
            "def nested():\n"
            "    root = Path('other')\n"
            "    def configure():\n"
            "        nonlocal root\n"
            "        root = Path('canonical')\n"
            "    return root / 'styles'\n"
        )
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 2)
        self.assertEqual(report["unclassified_hits"], 0)
        self.assertEqual({row["line"] for row in report["hits"]}, {7, 13})

    def test_closure_resolved_paths_keep_exact_negative_scope_and_migration_ownership(self):
        source = (
            "from pathlib import Path\n"
            "root = Path('template-library') / 'canonical'\n"
            "kind = 'styles'\n"
            "def test_reader(self):\n"
            "    with self.assertRaises(ValueError):\n"
            "        load(root / kind)\n"
            "    load(root / kind)\n"
        )
        path = self.root / "leo-ppt-generator/tests/test_reader.py"
        path.parent.mkdir(parents=True)
        path.write_text(source)
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 1)
        self.assertEqual(report["unclassified_hits"], 0)
        self.assertEqual([row["classification"] for row in report["hits"]], ["test-fixture", "active-consumer"])
        path.unlink()
        owner = self.root / "leo-ppt-generator/scripts/migrate_template_library.py"
        owner.parent.mkdir(parents=True)
        owner.write_text(source)
        report = scan_consumer_closure(self.root)
        self.assertEqual(report["active_legacy_hits"], 0)
        self.assertEqual(report["unclassified_hits"], 0)
        self.assertTrue(all(row["classification"] == "migration-input" for row in report["hits"]))

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
