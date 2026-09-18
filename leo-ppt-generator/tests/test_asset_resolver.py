"""U9：asset_resolver 统一身份/路径/scope/依赖解析（方案 §5–§6）。

用最小新库 fixture 驱动；覆盖 AE1/AE3/AE4：
改名/移动不改 ID、重号拒绝、歧义拒绝、坏引用拒绝、循环拒绝、scope 伪装拒绝、
陈旧 catalog 拒绝、缺库拒绝、canonical 只读重建、发布后 catalog 读取。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator import asset_resolver as ar

FIXTURE = SKILL / "tests" / "fixtures" / "minimal-template-library"


def _copy_fixture() -> Path:
    tmp = tempfile.TemporaryDirectory(prefix="leo-resolver-")
    root = Path(tmp.name) / "template-library"
    shutil.copytree(FIXTURE, root)
    return root


class FixtureCleanupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-resolver-")
        self.addCleanup(self._tmp.cleanup)
        self._tmp_path = Path(self._tmp.name)
        self.library = self._tmp_path / "template-library"
        shutil.copytree(FIXTURE, self.library)


class AssetResolverCoreTest(FixtureCleanupTestCase):
    def _resolver(self) -> ar.AssetResolver:
        return ar.AssetResolver(library=self.library)

    def test_resolve_by_full_id_and_name_and_alias(self) -> None:
        resolver = self._resolver()
        for query in ("builtin:style:minimal-clean", "最小清爽风", "清爽最小", "minimal-clean"):
            hits = resolver.lookup(query)
            self.assertEqual(len(hits), 1, query)
            resolved = resolver.resolve(hits[0]["asset_id"])
            self.assertEqual(resolved["kind"], "style")
            self.assertEqual(resolved["name"], "最小清爽风")
        self.assertEqual(resolver.registry_source, "canonical-rebuild")

    def test_kind_filter_precedes_name_precedence(self) -> None:
        """A template name must not shadow a layout alias for kind=layout."""
        resolver = self._resolver()
        layout = resolver.lookup("minimal-table", kind="layout")
        self.assertEqual(len(layout), 1)
        self.assertEqual(layout[0]["asset_id"], "builtin:layout:minimal-table")

    def test_rename_and_move_do_not_change_identity(self) -> None:
        # 实体目录改名（display 属性），ID 与解析结果不变（KTD4/AE1）。
        style_dir = self.library / "canonical" / "styles" / "minimal-clean"
        renamed = self.library / "canonical" / "styles" / "renamed-dir"
        style_dir.rename(renamed)
        (renamed / "brief.json").write_text(
            (renamed / "brief.json").read_text(encoding="utf-8"), encoding="utf-8")
        resolved = self._resolver().resolve("builtin:style:minimal-clean")
        self.assertEqual(resolved["asset_id"], "builtin:style:minimal-clean")
        self.assertEqual(resolved["relative_path"],
                         "canonical/styles/renamed-dir/brief.json")

    def test_ambiguous_name_rejected_with_all_hits(self) -> None:
        theme = json.loads(
            (self.library / "canonical/themes/minimal-light/theme.json").read_text())
        theme["asset_id"] = "builtin:theme:minimal-second"
        theme["name"] = "最小浅色主题"  # 与既有同名
        second = self.library / "canonical/themes/minimal-second"
        second.mkdir()
        (second / "theme.json").write_text(json.dumps(theme, ensure_ascii=False))
        resolver = self._resolver()
        hits = resolver.lookup("最小浅色主题")
        self.assertEqual(len(hits), 2)
        with self.assertRaises(ar.AmbiguousNameError):
            resolver.require("最小浅色主题")

    def test_duplicate_id_rejected(self) -> None:
        duplicate = self.library / "canonical/themes/minimal-clone"
        duplicate.mkdir()
        source = (self.library / "canonical/themes/minimal-light/theme.json").read_text()
        (duplicate / "theme.json").write_text(source)  # 同 asset_id
        with self.assertRaises(ar.DuplicateIdError):
            self._resolver().entities

    def test_missing_dependency_rejected(self) -> None:
        brief = json.loads(
            (self.library / "canonical/styles/minimal-clean/brief.json").read_text())
        brief["bindings"]["theme_default"] = "builtin:theme:ghost"
        (self.library / "canonical/styles/minimal-clean/brief.json").write_text(
            json.dumps(brief, ensure_ascii=False))
        resolver = self._resolver()
        with self.assertRaises(ar.DependencyMissingError):
            resolver.resolve_dependencies("builtin:style:minimal-clean")

    def test_dependency_cycle_rejected(self) -> None:
        layout = json.loads(
            (self.library / "canonical/layouts/minimal-table/layout.json").read_text())
        # 显式资源依赖指向 template；template.dependencies 已反向引用 layout。
        layout["dependencies"] = ["builtin:template:minimal-table"]
        (self.library / "canonical/layouts/minimal-table/layout.json").write_text(
            json.dumps(layout, ensure_ascii=False))
        resolver = self._resolver()
        with self.assertRaises((ar.ResolverError,)) as ctx:
            resolver.resolve_dependencies("builtin:layout:minimal-table")
        self.assertIn("循环依赖", str(ctx.exception))

    def test_dependency_closure_includes_transitive_deps(self) -> None:
        resolver = self._resolver()
        closure = resolver.resolve_dependencies("builtin:style:minimal-clean")
        ids = [entity["asset_id"] for entity in closure]
        self.assertIn("builtin:style:minimal-clean", ids)
        self.assertIn("builtin:theme:minimal-light", ids)      # brief → theme
        self.assertIn("builtin:layout:minimal-table", ids)     # brief → route → layout

    def test_user_manifest_cannot_impersonate_builtin(self) -> None:
        user_root = self.library.parent / "user-library"
        user_root.mkdir()
        (user_root / "library.json").write_text(
            json.dumps({"schema_version": 1, "kind": "template-library",
                        "library_id": "user", "zones": {
                            "canonical": "c", "reference": "r", "governance": "g",
                            "catalog": "k", "evidence": "e"},
                        "reserved_directory_names": []}))
        style_dir = user_root / "canonical/styles/minimal-clean"
        style_dir.mkdir(parents=True)
        (style_dir / "brief.json").write_text(
            json.dumps({"schema_version": 2, "entity": "style-brief",
                        "asset_id": "builtin:style:minimal-clean",
                        "name": "冒充内置", "lifecycle": "active",
                        "taxonomy": {"families": ["x"]},
                        "recommendation_features": {
                            "audience_conservatism": "balanced", "formality": 0.5,
                            "density": "balanced", "environments": ["desktop-review"]},
                        "visual_language": {"direction": "x" * 8, "features": ["a" * 4, "b" * 4]},
                        "bindings": {"theme_default": "builtin:theme:minimal-light"}},
                       ensure_ascii=False))
        home = user_root.parent  # user library.json 已就位
        with self.assertRaises(ar.ScopeViolationError):
            ar.AssetResolver(library=self.library, home=home).entities

    def test_library_missing_when_no_declaration(self) -> None:
        empty = self._tmp_path / "empty-library"
        empty.mkdir()
        with self.assertRaises(ar.LibraryMissingError):
            ar.AssetResolver(library=empty)

    def test_entity_file_escape_rejected(self) -> None:
        # registry/实体路径越出可信根 → scope_violation（traversal/symlink 防护）。
        import os
        secret = self._tmp_path / "secret.json"
        secret.write_text(
            (self.library / "canonical/themes/minimal-light/theme.json").read_text()
            .replace("builtin:theme:minimal-light", "builtin:style:minimal-clean"))
        link = self.library / "canonical/styles/minimal-clean/brief.json"
        link.unlink()
        link.symlink_to(secret)
        resolver = self._resolver()
        with self.assertRaises(ar.ScopeViolationError):
            resolver.resolve("builtin:style:minimal-clean")


class AssetResolverCatalogTest(FixtureCleanupTestCase):
    def _publish(self) -> str:
        sys.path.insert(0, str(SKILL / "scripts"))
        import capability_manifest as cm
        registry = cm.build_template_registry(self.library)
        cm.publish_template_registry(registry, self.library)
        return registry["generation"]

    def test_resolver_reads_published_catalog(self) -> None:
        generation = self._publish()
        resolver = ar.AssetResolver(library=self.library)
        self.assertEqual(resolver.registry_source, "catalog")
        resolved = resolver.resolve("builtin:style:minimal-clean")
        self.assertEqual(resolved["asset_id"], "builtin:style:minimal-clean")

    def test_axis_entities_are_indexed_from_nested_canonical_paths(self) -> None:
        axis_dir = self.library / "canonical/axes/argument/argument-demo"
        axis_dir.mkdir(parents=True)
        (axis_dir / "manifest.json").write_text(json.dumps({
            "schema_version": 1,
            "entity": "axis-manifest",
            "asset_id": "builtin:axis:argument-demo",
            "name": "论证模式：演示",
            "kind": "argument",
            "body_ref": "body.md",
            "applicability_limits": [],
        }, ensure_ascii=False))
        (axis_dir / "body.md").write_text("演示轴\n", encoding="utf-8")

        sys.path.insert(0, str(SKILL / "scripts"))
        import capability_manifest as cm
        registry = cm.build_template_registry(self.library)
        axis_entities = [e for e in registry["entities"] if e["kind"] == "axis"]
        self.assertEqual(len(axis_entities), 1)
        self.assertEqual(axis_entities[0]["path"],
                         "canonical/axes/argument/argument-demo/manifest.json")

        cm.publish_template_registry(registry, self.library)
        resolver = ar.AssetResolver(library=self.library)
        resolved = resolver.resolve("builtin:axis:argument-demo")
        self.assertEqual(resolved["kind"], "axis")
        self.assertEqual(resolved["relative_path"], axis_entities[0]["path"])

    def test_content_drift_after_publish_is_stale(self) -> None:
        self._publish()
        brief_path = self.library / "canonical/styles/minimal-clean/brief.json"
        brief = json.loads(brief_path.read_text())
        brief["name"] = "改名后的风格"
        brief_path.write_text(json.dumps(brief, ensure_ascii=False))
        resolver = ar.AssetResolver(library=self.library)
        with self.assertRaises(ar.StaleCatalogError):
            resolver.resolve("builtin:style:minimal-clean")

    def test_builder_rejects_unknown_dependency(self) -> None:
        sys.path.insert(0, str(SKILL / "scripts"))
        import capability_manifest as cm
        brief_path = self.library / "canonical/styles/minimal-clean/brief.json"
        brief = json.loads(brief_path.read_text())
        brief["bindings"]["theme_default"] = "builtin:theme:missing"
        brief_path.write_text(json.dumps(brief, ensure_ascii=False))
        with self.assertRaises(ValueError) as ctx:
            cm.build_template_registry(self.library)
        self.assertIn("dependency_missing", str(ctx.exception))

    def test_publish_is_deterministic_and_idempotent(self) -> None:
        sys.path.insert(0, str(SKILL / "scripts"))
        import capability_manifest as cm
        first = cm.build_template_registry(self.library)
        second = cm.build_template_registry(self.library)
        self.assertEqual(first["generation"], second["generation"])
        self.assertEqual(_json_bytes(first), _json_bytes(second))
        cm.publish_template_registry(first, self.library)
        cm.publish_template_registry(second, self.library)  # 幂等
        pointer = json.loads((self.library / "catalog/current.json").read_text())
        self.assertEqual(pointer["generation"], first["generation"])

    def test_publish_refreshes_same_generation_when_registry_algorithm_changes(self) -> None:
        import capability_manifest as cm
        first = cm.build_template_registry(self.library)
        cm.publish_template_registry(first, self.library)
        registry_path = (self.library / "catalog" / "generations" /
                         first["generation"] / "registry.json")
        stale = json.loads(registry_path.read_text(encoding="utf-8"))
        stale["entities"] = []
        registry_path.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")

        result = cm.publish_template_registry(first, self.library)
        self.assertTrue(result["updated"])
        self.assertEqual(json.loads(registry_path.read_text(encoding="utf-8")), first)
        checked, code = cm.check_template_registry(self.library)
        self.assertEqual(code, 0)
        self.assertEqual(checked["reason_code"], "none")


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
