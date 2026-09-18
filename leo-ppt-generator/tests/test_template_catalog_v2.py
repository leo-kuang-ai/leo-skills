"""v2 shadow library 的真实扫描/派生/落盘；不把临时库当正式迁移发布。"""
from pathlib import Path
import json
import shutil
import tempfile
import unittest

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.library_migration import materialize_shadow_library
from leo_ppt_generator.template_catalog import (
    LibraryContext, CatalogError, build_catalog, publish_catalog, read_catalog, scan_records,
)

ROOT = Path(__file__).resolve().parents[1]


class TemplateCatalogV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        source = self.root / "source"
        shutil.copytree(ROOT / "tests/fixtures/minimal-template-library", source)
        shutil.copytree(ROOT / "template-library/governance", source / "governance", dirs_exist_ok=True)
        self.library = self.root / "shadow"
        materialize_shadow_library(source, self.library)

    def test_v2_build_publication_is_deterministic_and_resolves_assets(self):
        outputs = build_catalog(self.library)
        self.assertEqual(outputs, build_catalog(self.library))
        with self.assertRaisesRegex(CatalogError, "catalog_missing"):
            AssetResolver(context=LibraryContext(self.library)).entities
        published = publish_catalog(self.library, outputs)
        self.assertEqual(published, publish_catalog(self.library, outputs))
        resolver = AssetResolver(context=LibraryContext(self.library))
        self.assertEqual(resolver.generation, published["generation"])
        self.assertEqual(resolver.resolve("builtin:layout:minimal-table")["relative_path"],
                         "canonical/executable/layouts/minimal-table/layout.json")
        self.assertFalse(outputs["views/execution-pairings.json"]["candidates"])

    def test_explicit_relative_library_root_preserves_qualification_owner_paths(self):
        import os
        from leo_ppt_generator.qualification import layout_capability_contract
        source = self.root / "source"
        resolver = AssetResolver(library=Path(os.path.relpath(source)), home=self.root / "empty-user")
        layout = resolver.resolve("builtin:layout:minimal-table")
        self.assertTrue(Path(layout["trusted_root"]).is_absolute())
        contract, dependencies = layout_capability_contract(layout, resolver=resolver)
        self.assertEqual(contract["asset_id"], layout["asset_id"])
        self.assertIn(layout["relative_path"], dependencies)

    def test_diagnostic_cannot_freeze_or_run_and_old_protocol_is_rejected(self):
        from leo_ppt_generator.application.expression_pipeline import run_expression_pipeline, PipelineRequest
        diagnostic = AssetResolver(context=LibraryContext(self.library, mode="diagnostic"))
        self.assertTrue(diagnostic.entities)
        with self.assertRaisesRegex(ValueError, "diagnostic_resolver_not_executable"):
            diagnostic.freeze_assets(self.root / "frozen", [])
        with self.assertRaisesRegex(ValueError, "diagnostic_resolver_not_executable"):
            run_expression_pipeline(PipelineRequest({}, {}), resolver=diagnostic)
        with self.assertRaisesRegex(CatalogError, "unsupported_schema"):
            AssetResolver(context=LibraryContext(self.root / "source")).entities

    def test_evidence_and_source_drift_invalidate_current_and_produce_a_new_generation(self):
        outputs = build_catalog(self.library)
        publish_catalog(self.library, outputs)
        (self.library / "evidence").mkdir(exist_ok=True)
        (self.library / "evidence/new-observation.txt").write_text("not qualification evidence")
        with self.assertRaisesRegex(CatalogError, "stale_catalog"):
            read_catalog(LibraryContext(self.library))
        changed = build_catalog(self.library)
        self.assertEqual(outputs["registry.json"]["asset_generation"], changed["registry.json"]["asset_generation"])
        self.assertNotEqual(outputs["registry.json"]["catalog_generation"], changed["registry.json"]["catalog_generation"])
        self.assertFalse(changed["views/execution-pairings.json"]["candidates"])

    def test_warmed_resolver_rejects_maintenance_in_every_cached_consumer(self):
        from leo_ppt_generator.library_migration import MigrationError
        from leo_ppt_generator.storage import atomic_write_json
        publish_catalog(self.library, build_catalog(self.library))
        resolver = AssetResolver(context=LibraryContext(self.library))
        entity = resolver.entities[0]
        identity = entity["asset_id"]
        pin = resolver.fingerprint(identity)
        generation = resolver.generation
        self.assertTrue(resolver.lookup(identity))
        target = self.root / "must-not-freeze"
        marker = self.library / ".maintenance.json"
        atomic_write_json(marker, {"plan_digest": "a" * 64})
        checks = {
            "entities": lambda: resolver.entities,
            "generation": lambda: resolver.generation,
            "registry_source": lambda: resolver.registry_source,
            "lookup": lambda: resolver.lookup(identity),
            "resolve": lambda: resolver.resolve(identity),
            "fingerprint": lambda: resolver.fingerprint(identity),
            "freeze": lambda: resolver.freeze_assets(target, [pin]),
            "empty-freeze": lambda: resolver.freeze_assets(target, []),
        }
        for name, operation in checks.items():
            with self.subTest(consumer=name), self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
                operation()
        self.assertFalse(target.exists())
        marker.unlink()
        self.assertEqual(resolver.generation, generation)
        self.assertEqual(resolver.fingerprint(identity), pin)

    def test_user_library_maintenance_also_blocks_cached_combined_index(self):
        from leo_ppt_generator.library_migration import MigrationError
        from leo_ppt_generator.storage import atomic_write_json
        publish_catalog(self.library, build_catalog(self.library))
        resolver = AssetResolver(context=LibraryContext(self.library))
        self.assertTrue(resolver.entities)
        user = self.root / "user-library"
        user.mkdir()
        resolver.user_root = user
        atomic_write_json(user / ".maintenance.json", {"plan_digest": "a" * 64})
        with self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
            _ = resolver.entities

    def test_catalog_writer_excludes_migration_until_current_is_persisted(self):
        from leo_ppt_generator.library_migration import MigrationError, locked_publication, maintenance_path
        delivery = self.root / "delivery"
        library = delivery / "leo-ppt-generator/template-library"
        library.parent.mkdir(parents=True)
        self.library.rename(library)
        phases = []

        def concurrent_publish(phase):
            phases.append(phase)
            with self.assertRaisesRegex(MigrationError, "migration_maintenance_lock_busy"):
                with locked_publication(delivery, plan_digest="a" * 64):
                    pass
            self.assertFalse(maintenance_path(delivery).exists())

        published = publish_catalog(library, build_catalog(library), checkpoint=concurrent_publish)
        self.assertEqual(phases, ["before_generation", "before_pointer"])
        self.assertEqual(read_catalog(LibraryContext(library))["catalog_generation"], published["generation"])
        with locked_publication(delivery, plan_digest="a" * 64):
            self.assertTrue(maintenance_path(delivery).exists())

    def test_raw_catalog_consumers_reject_persistent_maintenance(self):
        from leo_ppt_generator.library_migration import MigrationError
        from leo_ppt_generator.storage import atomic_write_json
        atomic_write_json(self.library / ".maintenance.json", {"plan_digest": "a" * 64})
        for operation in (scan_records, build_catalog):
            with self.subTest(operation=operation.__name__), self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
                operation(self.library)

    def test_execution_entries_observe_exclusive_lock_before_maintenance_marker(self):
        import fcntl
        import os
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest
        from leo_ppt_generator.application.routes import generate
        from leo_ppt_generator.library_migration import MigrationError
        from leo_ppt_generator.render.page import render_page
        from leo_ppt_generator.capability_probes import run_probes
        from scripts.capability_manifest import build_template_registry, inventory_template_library, publish_template_registry
        publish_catalog(self.library, build_catalog(self.library))
        resolver = AssetResolver(context=LibraryContext(self.library))
        identity = resolver.entities[0]["asset_id"]
        fd = os.open(self.library, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertFalse((self.library / ".maintenance.json").exists())
            operations = {
                "scan": lambda: scan_records(self.library),
                "build": lambda: build_catalog(self.library),
                "read": lambda: read_catalog(LibraryContext(self.library)),
                "cached-resolve": lambda: resolver.resolve(identity),
                "generate": lambda: generate(PipelineRequest({}, {}, library_root=str(self.library)), resolver=resolver),
                "render": lambda: render_page("builtin:template:body-basic", self.root / "data.json", self.root / "out.png", resolver=resolver),
                "registry-build": lambda: build_template_registry(self.library),
                "registry-inventory": lambda: inventory_template_library(self.library),
                "registry-publish": lambda: publish_template_registry({}, self.library),
                "probe-writer": lambda: run_probes(library_root=self.library, cases={}, output="evidence/probes/blocked"),
            }
            for name, operation in operations.items():
                with self.subTest(entry=name), self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
                    operation()
        finally:
            os.close(fd)
        self.assertEqual(resolver.resolve(identity)["asset_id"], identity)
        self.assertFalse((self.root / "out.png").exists())
        self.assertFalse((self.library / "evidence/probes/blocked").exists())

    def test_interruption_before_pointer_keeps_generation_invisible_and_retry_recovers(self):
        outputs = build_catalog(self.library)
        def stop(phase):
            if phase == "before_pointer":
                raise InterruptedError()
        with self.assertRaises(InterruptedError):
            publish_catalog(self.library, outputs, checkpoint=stop)
        with self.assertRaisesRegex(CatalogError, "catalog_missing"):
            read_catalog(LibraryContext(self.library))
        publish_catalog(self.library, outputs)
        self.assertEqual(read_catalog(LibraryContext(self.library)), outputs["registry.json"])

    def test_same_generation_content_conflict_is_not_refreshed_in_place(self):
        outputs = build_catalog(self.library)
        result = publish_catalog(self.library, outputs)
        registry = self.library / "catalog/generations" / result["generation"] / "registry.json"
        registry.write_text("{}")
        with self.assertRaisesRegex(CatalogError, "catalog_invalid"):
            read_catalog(LibraryContext(self.library))
        with self.assertRaisesRegex(CatalogError, "catalog_generation_conflict"):
            publish_catalog(self.library, outputs)
        self.assertEqual(registry.read_text(), "{}")

    def test_v2_frozen_assets_preserve_catalog_identity_without_live_library(self):
        publish_catalog(self.library, build_catalog(self.library))
        resolver = AssetResolver(context=LibraryContext(self.library))
        pins = [resolver.fingerprint(row["asset_id"]) for row in resolver.entities]
        frozen = resolver.freeze_assets(self.root / "frozen", pins)
        self.assertEqual(frozen.generation, resolver.generation)
        shutil.rmtree(self.library)
        frozen = AssetResolver.from_snapshot(self.root / "frozen")
        self.assertEqual([frozen.fingerprint(pin["asset_id"]) for pin in pins], pins)

    def test_unowned_files_guides_and_symlinks_do_not_enter_execution_entities(self):
        target = self.library / "canonical/executable/layouts/guides/example"
        target.mkdir(parents=True)
        (target / "layout.json").write_text("{}")
        with self.assertRaisesRegex(CatalogError, "unclassified_canonical_file"):
            scan_records(self.library)
        (target / "layout.json").unlink()
        (target / "link").symlink_to(self.root / "source/library.json")
        with self.assertRaisesRegex(CatalogError, "scope_violation"):
            scan_records(self.library)


if __name__ == "__main__":
    unittest.main()
