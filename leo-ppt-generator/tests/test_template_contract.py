"""canonical 模板目录级合同回归。"""
from __future__ import annotations
import json
import shutil
import sys
import tempfile
import unittest
import contextlib
import io
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import lint_template_contract as contract  # noqa: E402
import lint_render_templates as render_contract
from leo_ppt_generator.asset_resolver import AssetResolver


class TemplateContractTest(unittest.TestCase):
    def setUp(self):
        self.resolver = AssetResolver(home=SKILL / ".template-lint-no-user")
        self.layouts = {row["asset_id"]: self.resolver.resolve(row["asset_id"])["data"]
                        for row in self.resolver.entities if row["kind"] == "layout"}
        self.template = Path(self.resolver.require("body-basic", kind="template")["path"]).parent

    def test_canonical_templates_pass(self):
        errors = []
        for row in self.resolver.entities:
            if row["kind"] == "template":
                path = Path(self.resolver.resolve(row["asset_id"])["path"]).parent
                errors.extend(contract.lint_one(path, self.layouts))
        self.assertEqual(errors, [])

    def test_missing_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / "new-template"
            path.mkdir()
            shutil.copy(self.template / "page.html", path / "page.html")
            self.assertTrue(any("missing template.json" in e for e in contract.lint_one(path, self.layouts)))

    def test_selector_drift_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / "body-basic"
            shutil.copytree(self.template, path)
            manifest = json.loads((path / "template.json").read_text())
            manifest["slot_bindings"][0]["selector"] = "[data-leo-block='missing']"
            (path / "template.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertTrue(any("missing DOM anchor" in e for e in contract.lint_one(path, self.layouts)))


class TemplateLintLibraryTests(unittest.TestCase):
    def invoke(self, module, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return module.main(args)

    def test_malformed_manifests_fail_without_crashing(self):
        resolver = AssetResolver(home=SKILL / ".template-lint-no-user")
        source = Path(resolver.require("body-basic", kind="template")["path"]).parent
        original = json.loads((source / "template.json").read_text())
        malformed = [[], {"entity": "render-template", "lane": "render:html"},
                     dict(original, asset_id=42), dict(original, slot_bindings=[None])]
        for data in malformed:
            with self.subTest(data=data), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                shutil.copytree(source, root / "body-basic")
                (root / "body-basic/template.json").write_text(json.dumps(data))
                for module in (contract, render_contract):
                    with self.subTest(module=module.__name__):
                        self.assertEqual(self.invoke(module, ["--templates-dir", str(root)]), 1)

    def test_dangling_directory_symlink_cannot_be_ignored(self):
        resolver = AssetResolver(home=SKILL / ".template-lint-no-user")
        source = Path(resolver.require("body-basic", kind="template")["path"]).parent
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            shutil.copytree(source, root / "body-basic")
            (root / "broken").symlink_to(root / "missing", target_is_directory=True)
            for module in (contract, render_contract):
                with self.subTest(module=module.__name__):
                    self.assertEqual(self.invoke(module, ["--templates-dir", str(root)]), 1)

    def test_v1_schema_symlink_cannot_escape_library(self):
        from tests.expression_test_support import real_validation_inputs
        _, resolver, _ = real_validation_inputs()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "library"
            shutil.copytree(resolver.builtin_root, root)
            shutil.copytree(SKILL / "template-library/governance", root / "governance", dirs_exist_ok=True)
            schema = root / "governance/schemas/template-v1.schema.json"
            target = root.parent / "outside-schema.json"
            schema.rename(target)
            schema.symlink_to(target)
            for module in (contract, render_contract):
                with self.subTest(module=module.__name__):
                    self.assertEqual(self.invoke(module, ["--library-root", str(root)]), 1)

    def test_explicit_directory_allows_readme_but_not_unknown_files(self):
        resolver = AssetResolver(home=SKILL / ".template-lint-no-user")
        source = Path(resolver.require("body-basic", kind="template")["path"]).parent
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            shutil.copytree(source, root / "body-basic")
            (root / "README.md").write_text("# 模板作者说明\n")
            for module in (contract, render_contract):
                self.assertEqual(self.invoke(module, ["--templates-dir", str(root)]), 0)
            (root / "unknown.txt").write_text("unclassified")
            for module in (contract, render_contract):
                self.assertEqual(self.invoke(module, ["--templates-dir", str(root)]), 1)

    def test_nonempty_directory_without_templates_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "unrelated").mkdir()
            for module in (contract, render_contract):
                with self.subTest(module=module.__name__):
                    self.assertEqual(self.invoke(module, ["--templates-dir", str(root)]), 1)

    def test_each_manifest_and_html_must_have_its_pair(self):
        resolver = AssetResolver(home=SKILL / ".template-lint-no-user")
        source = Path(resolver.require("body-basic", kind="template")["path"]).parent
        for missing in ("template.json", "page.html"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                shutil.copytree(source, root / "body-basic")
                shutil.copytree(source, root / "broken")
                (root / "broken" / missing).unlink()
                for module in (contract, render_contract):
                    self.assertEqual(self.invoke(module, ["--templates-dir", str(root)]), 1)

    def test_real_v2_library_and_renamed_template_directory(self):
        from tests.expression_test_support import real_validation_inputs_v2
        from leo_ppt_generator.template_catalog import build_catalog, publish_catalog
        _, resolver, _ = real_validation_inputs_v2()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "library"
            shutil.copytree(resolver.builtin_root, root)
            current = AssetResolver(library=root, home=root / "empty")
            owner = Path(current.require("body-basic", kind="template")["path"]).parent
            owner.rename(owner.with_name("relocated-body"))
            publish_catalog(root, build_catalog(root))
            for module in (contract, render_contract):
                self.assertEqual(self.invoke(module, ["--library-root", str(root)]), 0)
            (owner.with_name("relocated-body") / "page.html").unlink()
            for module in (contract, render_contract):
                self.assertEqual(self.invoke(module, ["--library-root", str(root)]), 1)

    def test_missing_current_cannot_fallback_to_directory_scan(self):
        from tests.expression_test_support import real_validation_inputs_v2
        _, resolver, _ = real_validation_inputs_v2()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "library"
            shutil.copytree(resolver.builtin_root, root)
            (root / "catalog/current.json").unlink()
            for module in (contract, render_contract):
                self.assertEqual(self.invoke(module, ["--library-root", str(root)]), 1)


if __name__ == "__main__":
    unittest.main()
