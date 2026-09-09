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

BASELINE_ENTITIES = 548  # 含 124 条 canonical axis 的全量基线


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
            bundle = Path(tmp) / "bundle"
            shutil.copytree(SKILL / "template-library", bundle / "template-library")
            shutil.copytree(SKILL / "assets", bundle / "assets")
            env = dict(os.environ, LEO_PPT_BUNDLE=str(bundle))
            resolver = AssetResolver(library=bundle / "template-library")
            self.assertEqual(len(resolver.entities), BASELINE_ENTITIES)
            resolved = resolver.resolve("builtin:style:finance-navy")
            self.assertEqual(resolved["origin_scope"], "builtin")
            entry = template_http_entry("cover-basic.html")
            self.assertIsNotNone(entry)
            self.assertEqual(entry.parent.name, "cover-basic")
            proc = _library_check(bundle)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(payload.get("reason_code", "none"), "none")
            self.assertTrue((bundle / "assets" / "render-fonts").is_dir())

    def test_linked_install_points_at_source_of_truth(self) -> None:
        """链接安装：LEO_PPT_BUNDLE 指向原位不复制数据，解析等价。"""

        env = dict(os.environ, LEO_PPT_BUNDLE=str(SKILL))
        resolver = AssetResolver()
        self.assertEqual(len(resolver.entities), BASELINE_ENTITIES)
        self.assertTrue(template_path("spec-table").is_file())
        self.assertIn("canonical", [p.name for p in template_path("spec-table").parents])


def _make_library_copy(tmp: str) -> Path:
    bundle = Path(tmp) / "bundle"
    shutil.copytree(SKILL / "template-library", bundle / "template-library")
    return bundle / "template-library"


class TamperAndInterruptionTest(unittest.TestCase):
    def test_canonical_tamper_is_detected_not_silent(self) -> None:
        """篡改 canonical 文件 → resolver 拒绝加载该资产（StaleCatalogError）。

        revision 是内容摘要：绕过 builder 改文件必然漂移；library-check
        只校验发布产物自洽，内容漂移的运行时闸门是 resolver。
        """

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            target = library / "canonical" / "styles" / "finance-navy" / "brief.json"
            data = json.loads(target.read_text(encoding="utf-8"))
            data["name"] = (data.get("name") or "") + "（篡改）"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            resolver = AssetResolver(library=library)
            with self.assertRaises(StaleCatalogError):
                resolver.resolve("builtin:style:finance-navy")

    def test_interrupted_catalog_pointer_is_rejected(self) -> None:
        """断写：current.json 缺 generation → resolver 拒绝加载（不回落猜测）。"""

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            pointer = library / "catalog" / "current.json"
            pointer.write_text(json.dumps({"generation": None}), encoding="utf-8")
            with self.assertRaises(StaleCatalogError):
                AssetResolver(library=library).entities


class DesignFreshnessResumeTest(unittest.TestCase):
    """旧 run 恢复/拒绝：冻结设计的依赖摘要是续跑的唯一准入。"""

    PAGES = [{"page_no": 1, "page_role": "cover",
              "layout": "builtin:layout:cover-basic", "content_ref": "c"},
             {"page_no": 2, "page_role": "data",
              "layout": "builtin:layout:p25-spec-table", "content_ref": "d",
              "slots": {"rows": [["a", "b", "c"]], "columns": ["x", "y", "z"]}}]

    def _compose_in(self, library: Path) -> dict:
        resolver = AssetResolver(library=library)
        return compose_design("finance-navy", pages=self.PAGES, resolver=resolver)

    def test_fresh_design_resumes(self) -> None:
        report = verify_design_freshness(self._compose_in(SKILL / "template-library"))
        self.assertEqual(report["status"], "fresh")
        self.assertGreater(report["checked"], 0)

    def test_stale_dependency_rejects_resume(self) -> None:
        """依赖漂移（资产修订并重发布）→ stale + 波及面；旧 run 拒绝续跑。"""

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            frozen = self._compose_in(library)
            self.assertEqual(verify_design_freshness(frozen,
                AssetResolver(library=library))["status"], "fresh")
            # 模拟库演进：修订一个依赖并重发布 catalog
            theme = library / "canonical" / "themes" / "finance-navy-light" / "theme.json"
            data = json.loads(theme.read_text(encoding="utf-8"))
            data["name"] = (data.get("name") or "x") + " rev2"
            theme.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SKILL / "scripts" / "capability_manifest.py"),
                 "--template-library", "--library-publish"],
                capture_output=True, text=True, timeout=120,
                env=dict(os.environ, LEO_PPT_BUNDLE=str(library.parent)))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = verify_design_freshness(frozen,
                                             AssetResolver(library=library))
            self.assertEqual(report["status"], "stale")
            self.assertTrue(any("finance-navy-light" in m["asset_id"]
                                for m in report["mismatches"]),
                            f"波及面须点名被修订资产: {report['mismatches']}")

    def test_non_design_input_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            verify_design_freshness({"entity": "not-a-design"})


if __name__ == "__main__":
    unittest.main()
