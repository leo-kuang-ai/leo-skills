"""用户风格保存必须发布可读取的 v2 库，失败恢复与导入共享同一事务。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from leo_ppt_generator import styles
from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.template_catalog import LibraryContext, read_catalog


class UserStyleV2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name).resolve() / "home"
        self.library = self.home / "template-library"

    def save(self, name="用户风格", **kwargs):
        return styles.save_style(name, json.dumps({"style_name": "内容旧名", "visual_direction": "网格排印与克制留白"}), home=self.home, **kwargs)

    def test_save_publishes_v2_and_reloads_through_real_resolver(self):
        result = self.save()
        self.assertEqual(result["name"], "用户风格")
        self.assertEqual(result["asset_id"], "user:style:用户风格")
        self.assertEqual(Path(result["path"]), self.library / "canonical/visual/styles/用户风格/brief.json")
        registry = read_catalog(LibraryContext(self.library))
        self.assertEqual(registry["entities"][0]["asset_id"], result["asset_id"])
        loaded = AssetResolver(home=self.home).resolve(result["asset_id"])
        self.assertEqual(loaded["data"]["name"], "用户风格")

    def test_save_rename_controls_name_identity_path_and_preserves_original(self):
        original = self.save()
        renamed = self.save(rename="另存风格")
        self.assertEqual(renamed["name"], "另存风格")
        self.assertEqual(renamed["asset_id"], "user:style:另存风格")
        self.assertEqual(Path(renamed["path"]).parent.name, "另存风格")
        self.assertTrue(Path(original["path"]).is_file())

    def test_save_refuses_v1_library_without_migrating_material(self):
        self.library.mkdir(parents=True)
        path = self.library / "library.json"
        path.write_text(json.dumps({"kind": "template-library", "schema_version": 1, "library_id": "user", "protocol": {"resolver": "asset_resolver/v1"}}))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "migration_required"):
            self.save()
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.library / "canonical").exists())

    def snapshot(self):
        return {p.relative_to(self.library).as_posix(): p.read_bytes()
                for p in self.library.rglob("*") if p.is_file()}

    def test_incremental_save_and_overwrite_republish_all_assets(self):
        first = self.save()
        with self.assertRaisesRegex(styles.StyleStoreError, "style_name_conflict"):
            self.save()
        self.save("第二个风格")
        updated = styles.save_style("用户风格", json.dumps({"visual_direction": "大幅留白与醒目红色标题"}), home=self.home, overwrite=True)
        self.assertEqual(updated["path"], first["path"])
        resolver = AssetResolver(home=self.home)
        self.assertEqual(resolver.resolve(updated["asset_id"])["data"]["visual_language"]["direction"], "大幅留白与醒目红色标题")
        self.assertEqual(resolver.resolve("user:style:第二个风格")["data"]["name"], "第二个风格")

    def test_overwrite_pointer_postreplace_failure_restores_original_bytes(self):
        from leo_ppt_generator.library_migration import compare_and_swap_file
        self.save()
        before = self.snapshot()
        failed = False
        def fail_after_pointer(root, relative, **kwargs):
            nonlocal failed
            result = compare_and_swap_file(root, relative, **kwargs)
            if relative == "catalog/current.json" and not failed:
                failed = True
                raise OSError("pointer postreplace failure")
            return result
        with patch("leo_ppt_generator.library_migration.compare_and_swap_file", side_effect=fail_after_pointer):
            with self.assertRaisesRegex(OSError, "pointer postreplace"):
                styles.save_style("用户风格", json.dumps({"visual_direction": "大幅留白与醒目红色标题"}), home=self.home, overwrite=True)
        self.assertTrue(failed)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(styles.load_style("用户风格", home=self.home)["brief"]["visual_language"]["direction"], "网格排印与克制留白")

    def test_fresh_catalog_failure_rolls_back_and_retry_succeeds(self):
        with patch("leo_ppt_generator.template_catalog.build_catalog", side_effect=OSError("catalog write failed")):
            with self.assertRaisesRegex(OSError, "catalog write failed"):
                self.save()
        self.assertFalse((self.library / "library.json").exists())
        self.assertFalse(list((self.library / "canonical").rglob("brief.json")))
        self.save()
        self.assertEqual(len(read_catalog(LibraryContext(self.library))["entities"]), 1)

    def test_external_edit_during_overwrite_is_not_overwritten_by_rollback(self):
        self.save()
        original_pointer = (self.library / "catalog/current.json").read_bytes()
        target = self.library / "canonical/visual/styles/用户风格/brief.json"
        def external_edit(root):
            target.write_text("external change")
            raise OSError("catalog failed")
        from leo_ppt_generator.template_catalog import build_catalog
        calls = 0
        def fail_second_build(root):
            nonlocal calls
            calls += 1
            if calls > 1:
                return external_edit(root)
            return build_catalog(root)
        with patch("leo_ppt_generator.template_catalog.build_catalog", side_effect=fail_second_build):
            with self.assertRaisesRegex(ValueError, "rollback_external_drift"):
                styles.save_style("用户风格", json.dumps({"visual_direction": "大幅留白与醒目红色标题"}), home=self.home, overwrite=True)
        self.assertEqual(target.read_text(), "external change")
        self.assertEqual((self.library / "catalog/current.json").read_bytes(), original_pointer)

    def test_saved_v2_document_retains_its_visual_fields(self):
        brief = {"schema_version": 2, "entity": "style-brief", "asset_id": "user:style:old", "name": "内容旧名",
                 "lifecycle": "draft", "taxonomy": {"families": ["视觉族"]},
                 "visual_language": {"direction": "网格排印与克制留白", "features": ["留白", "大字"]}, "bindings": {}}
        result = styles.save_style("用户风格", json.dumps(brief), home=self.home)
        loaded = styles.load_style(result["asset_id"], home=self.home)
        self.assertEqual(loaded["brief"]["visual_language"], brief["visual_language"])
        self.assertEqual(loaded["brief"]["taxonomy"], brief["taxonomy"])

    def test_save_rejects_invalid_dependency_and_preserves_published_catalog(self):
        original = self.save()
        before = self.snapshot()
        brief = styles.load_style(original["asset_id"], home=self.home)["brief"]
        for dependency in (original["asset_id"], "user:theme:missing"):
            with self.subTest(dependency=dependency):
                brief["bindings"] = {"theme_default": dependency}
                with self.assertRaises(ValueError):
                    styles.save_style("用户风格", json.dumps(brief), home=self.home, overwrite=True)
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
