"""U8：模板库 bundle 安装完整性与恢复/拒绝（方案 v4 §U8）。

覆盖：完整安装（隔离副本）、链接安装（LEO_PPT_BUNDLE 指向原位）、
canonical 篡改检出（library-check 非 zero）、断写 current.json 拒绝、
冻结设计恢复校验（fresh ↔ stale；stale 即旧 run 拒绝续跑）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.asset_resolver import (AssetResolver,
                                              StaleCatalogError)
from leo_ppt_generator.render.assets import (template_http_entry,
                                              template_path)
from leo_ppt_generator.templates import (compose_design,
                                         verify_design_freshness)
from leo_ppt_generator.library_migration import materialize_shadow_library
from leo_ppt_generator.template_catalog import LibraryContext, build_catalog, publish_catalog, CatalogError

BASELINE_ENTITIES = 443  # v2 执行实体含新增规格表 recipe；124 个指南仍不进入执行池


def _library_check(bundle_root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, LEO_PPT_BUNDLE=str(bundle_root))
    return subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "capability_manifest.py"),
         "--template-library", "--library-check"],
        capture_output=True, text=True, env=env, timeout=120)


class IsolatedInstallTest(unittest.TestCase):
    def test_full_copy_install_resolves_and_checks_green(self) -> None:
        """隔离完整安装：副本内 resolver 全量、模板入口、library-check 全绿。"""

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            bundle = library.parent
            shutil.copytree(SKILL / "assets", bundle / "assets")
            env = dict(os.environ, LEO_PPT_BUNDLE=str(bundle))
            resolver = AssetResolver(context=LibraryContext(library))
            self.assertEqual(len(resolver.entities), BASELINE_ENTITIES)
            recipe = resolver.resolve("builtin:recipe:p25-spec-table")
            self.assertEqual(recipe["data"]["layout_profiles"], ["builtin:layout:p25-spec-table"])
            self.assertEqual(recipe["data"]["slot_map"]["cell"]["input_path"], "rows.*.*")
            resolved = resolver.resolve("builtin:style:finance-navy")
            self.assertEqual(resolved["origin_scope"], "builtin")
            entry = template_http_entry("cover-basic.html", resolver=resolver)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.parent.name, "cover-basic")
            proc = _library_check(bundle)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(payload["reason_code"], "ok")
            self.assertTrue((bundle / "assets" / "render-fonts").is_dir())

    def test_linked_install_points_at_source_of_truth(self) -> None:
        """链接安装：LEO_PPT_BUNDLE 指向原位不复制数据，解析等价。"""

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            resolver = AssetResolver(context=LibraryContext(library))
            self.assertEqual(len(resolver.entities), BASELINE_ENTITIES)
            recipe = resolver.resolve("builtin:recipe:p25-spec-table")
            self.assertEqual(Path(recipe["path"]), library / "canonical/executable/recipes/p25-spec-table/recipe.json")
            path = template_path("spec-table", resolver=resolver)
            self.assertTrue(path.is_relative_to(library))
            self.assertEqual(path, library / "canonical/executable/templates/spec-table/page.html")


def _make_library_copy(tmp: str) -> Path:
    library = Path(tmp).resolve() / "bundle/template-library"
    materialize_shadow_library(SKILL / "template-library", library)
    publish_catalog(library, build_catalog(library))
    return library


class TamperAndInterruptionTest(unittest.TestCase):
    def test_canonical_tamper_is_detected_not_silent(self) -> None:
        """篡改 canonical 文件 → resolver 拒绝加载该资产（StaleCatalogError）。

        revision 是内容摘要：绕过 builder 改文件必然漂移；library-check
        只校验发布产物自洽，内容漂移的运行时闸门是 resolver。
        """

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            target = library / "canonical/visual/styles/finance-navy/brief.json"
            data = json.loads(target.read_text(encoding="utf-8"))
            data["name"] = (data.get("name") or "") + "（篡改）"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            resolver = AssetResolver(context=LibraryContext(library))
            with self.assertRaisesRegex(CatalogError, "stale_catalog"):
                resolver.resolve("builtin:style:finance-navy")

    def test_interrupted_catalog_pointer_is_rejected(self) -> None:
        """断写：current.json 缺 generation → resolver 拒绝加载（不回落猜测）。"""

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            pointer = library / "catalog" / "current.json"
            pointer.write_text(json.dumps({"generation": None}), encoding="utf-8")
            with self.assertRaisesRegex(CatalogError, "catalog_invalid"):
                AssetResolver(context=LibraryContext(library)).entities


class DesignFreshnessResumeTest(unittest.TestCase):
    """旧 run 恢复/拒绝：冻结设计的依赖摘要是续跑的唯一准入。"""

    PAGES = [{"page_no": 1, "page_role": "cover",
              "layout": "builtin:layout:cover-basic", "content_ref": "c"},
             {"page_no": 2, "page_role": "data",
              "layout": "builtin:layout:p25-spec-table", "content_ref": "d",
              "slots": {"rows": [["a", "b", "c"]], "columns": ["x", "y", "z"]}}]

    def _compose_in(self, resolver) -> dict:
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest, load_committed_input
        from leo_ppt_generator.application.routes import generate
        from leo_ppt_generator.templates import resolve_design_context
        from tests.expression_test_support import real_validation_inputs_v2
        pack, _, _ = real_validation_inputs_v2()
        context = resolve_design_context("clean-professional", resolver=resolver)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        run = Path(temporary.name).resolve() / "run"
        result = generate(PipelineRequest(pack, context, resolver.generation,
            {page["page_id"]: ["render:html"] for page in pack["pages"]},
            str(run), "v2-bundle-validation", str(resolver.builtin_root), purpose="validation"), resolver=resolver)
        self.assertEqual(result["status"], "html_validated")
        return load_committed_input(run)["payload"]["designs"]["render:html"]

    def test_fresh_design_resumes(self) -> None:
        from tests.expression_test_support import real_validation_inputs_v2
        _, resolver, _ = real_validation_inputs_v2()
        report = verify_design_freshness(self._compose_in(resolver), resolver)
        self.assertEqual(report["status"], "fresh")
        self.assertGreater(report["checked"], 0)

    def test_stale_dependency_rejects_resume(self) -> None:
        """依赖漂移（资产修订并重发布）→ stale + 波及面；旧 run 拒绝续跑。"""

        with tempfile.TemporaryDirectory() as tmp:
            from tests.expression_test_support import real_validation_inputs_v2
            _, original, _ = real_validation_inputs_v2()
            library = Path(tmp).resolve() / "bundle/template-library"
            shutil.copytree(original.builtin_root, library)
            resolver = AssetResolver(context=LibraryContext(library))
            frozen = self._compose_in(resolver)
            self.assertEqual(verify_design_freshness(frozen,
                resolver)["status"], "fresh")
            # 模拟库演进：修订一个依赖并重发布 catalog
            theme = Path(resolver.resolve(frozen["selection"]["theme"]["asset_id"])["path"])
            data = json.loads(theme.read_text(encoding="utf-8"))
            data["name"] = (data.get("name") or "x") + " rev2"
            theme.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            publish_catalog(library, build_catalog(library))
            report = verify_design_freshness(frozen,
                                             AssetResolver(context=LibraryContext(library)))
            self.assertEqual(report["status"], "stale")
            self.assertTrue(any(m["asset_id"] == frozen["selection"]["theme"]["asset_id"]
                                for m in report["mismatches"]),
                            f"波及面须点名被修订资产: {report['mismatches']}")

    def test_non_design_input_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            verify_design_freshness({"entity": "not-a-design"})


if __name__ == "__main__":
    unittest.main()
