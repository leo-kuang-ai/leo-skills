"""负面语料参考池合同测试（UB1，方案 2026-09-02-002）。

覆盖：池文档存在性与结构契约、_load_pool/_pool_candidates 解析与匹配、
缺省行为（不传 --pool）不读池。
"""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import shutil
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / "scripts" / "draft_negative_prompts.py"
POOL_DOC = SKILL_DIR / "template-library/governance/authoring/index/负面语料参考池.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("draft_negative_prompts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class NegativePromptPoolDocContract(unittest.TestCase):
    def test_pool_doc_exists_with_source_and_license_line(self):
        """池文档存在，且含来源登记（思想级改写口径）与快照日期。"""
        text = POOL_DOC.read_text(encoding="utf-8")
        self.assertIn("huashu-design", text)
        self.assertIn("思想级改写", text)
        self.assertIn("2026-09-02", text)

    def test_pool_doc_first_stage_groups_present(self):
        """首期覆盖组在场：通用 + 三派辐射家族组；每组 ≥3 条。"""
        mod = _load_module()
        groups = mod._load_pool(POOL_DOC)
        for name in ("通用", "东方意蕴", "中式载体", "质感专业"):
            self.assertIn(name, groups, f"缺首期组：{name}")
            self.assertGreaterEqual(
                len(groups[name]), 3, f"组 {name} 词条不足 3 条"
            )

    def test_pool_doc_groups_match_current_taxonomy(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        resolver = AssetResolver(home=SKILL_DIR / ".negative-test-no-user")
        families = {family for row in resolver.entities if row["kind"] == "style"
                    for family in resolver.resolve(row["asset_id"])["data"]["taxonomy"]["families"]}
        for name in _load_module()._load_pool(POOL_DOC):
            if name != "通用":
                self.assertIn(name, families)


class PoolParsingAndMatching(unittest.TestCase):
    def test_load_pool_skips_usage_guide_section(self):
        """## 选用指引 段不参与解析。"""
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pool.md"
            p.write_text(
                "# 池\n\n## 组A\n- 不要使用高饱和撞色破坏基调\n\n"
                "## 选用指引\n- 这是一条说明不是词条\n",
                encoding="utf-8",
            )
            groups = mod._load_pool(p)
        self.assertEqual(groups, {"组A": ["不要使用高饱和撞色破坏基调"]})

    def test_pool_candidates_universal_group_always_applies(self):
        """通用组对所有 brief 适用；家族组仅 taxonomy 命中时适用。"""
        mod = _load_module()
        groups = {
            "通用": ["通用负面词条一"],
            "东方意蕴": ["水墨负面词条一"],
        }
        hit = mod._pool_candidates(groups, {"东方意蕴"})
        miss = mod._pool_candidates(groups, {"科技数字"})
        self.assertIn("通用负面词条一", hit)
        self.assertIn("水墨负面词条一", hit)
        self.assertIn("通用负面词条一", miss)
        self.assertNotIn("水墨负面词条一", miss)

    def test_cli_without_pool_flag_leaves_default_untouched(self):
        """不传 --pool 时运行 dry-run 正常退出（缺省行为不变）。"""
        mod = _load_module()
        rc = mod.main(["--limit", "1"])
        self.assertEqual(rc, 0)


class CurrentLibraryDraftTests(unittest.TestCase):
    def setUp(self):
        from leo_ppt_generator.styles import save_style
        from leo_ppt_generator.template_catalog import build_catalog, publish_catalog
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.library = self.home / "template-library"
        self.mod = _load_module()
        for name in ("style-a", "style-b"):
            brief = {"schema_version": 2, "entity": "style-brief", "asset_id": "user:style:" + name,
                     "name": name, "lifecycle": "draft", "taxonomy": {"families": ["东方意蕴"]},
                     "visual_language": {"direction": "克制排印与留白，禁止混用三种以上字体",
                                         "features": ["不要用霓虹高饱和色破坏水墨基调", "大幅留白"]},
                     "constraints": {"negative": ["禁止遮挡事实文字"]}, "bindings": {}}
            save_style(name, json.dumps(brief, ensure_ascii=False), home=self.home)
        self.pool = self.library / "governance/authoring/index/负面语料参考池.md"
        self.pool.parent.mkdir(parents=True)
        shutil.copyfile(POOL_DOC, self.pool)
        publish_catalog(self.library, build_catalog(self.library))

    def snapshot(self):
        return {p.relative_to(self.library).as_posix(): p.read_bytes()
                for p in self.library.rglob("*") if p.is_file() and not p.name.endswith(".lock")}

    def test_dry_run_uses_current_briefs_and_limit_without_writing(self):
        before = self.snapshot()
        rows = self.mod.run(self.library, limit=1, pool=self.pool)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asset_id"], "user:style:style-a")
        self.assertEqual(len(rows[0]["added"]), 2)
        self.assertEqual(self.snapshot(), before)

    def test_apply_preserves_content_identity_and_publishes_catalog(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        before = AssetResolver(library=self.library, home=self.root / "empty").resolve("user:style:style-a")["data"]
        old_pointer = (self.library / "catalog/current.json").read_bytes()
        rows = self.mod.run(self.library, apply=True, pool=self.pool, limit=1)
        self.assertEqual(len(rows), 1)
        resolved = AssetResolver(library=self.library, home=self.root / "empty").resolve("user:style:style-a")
        expected = json.loads(json.dumps(before))
        expected["constraints"]["negative"] += rows[0]["added"]
        self.assertEqual(resolved["data"], expected)
        self.assertNotEqual((self.library / "catalog/current.json").read_bytes(), old_pointer)
        self.mod.run(self.library, apply=True, pool=self.pool)
        after = self.snapshot()
        self.assertEqual(self.mod.run(self.library, apply=True, pool=self.pool), [])
        self.assertEqual(self.snapshot(), after)

    def test_missing_catalog_and_pool_and_cross_root_are_rejected(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.mod.run(self.library, pool=POOL_DOC)
        with self.assertRaises(ValueError):
            self.mod.run(self.library, pool=self.pool.parent / "missing.md")
        self.assertEqual(self.snapshot(), before)
        (self.library / "catalog/current.json").unlink()
        with self.assertRaises(ValueError):
            self.mod.run(self.library)

    def test_pool_symlink_is_rejected_without_writing(self):
        self.pool.unlink()
        self.pool.symlink_to(POOL_DOC)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.mod.run(self.library, pool=self.pool, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_archived_pool_inside_library_is_not_an_authoring_source(self):
        archive = self.library / "reference/sources/retired-styles-tree/styles/00_索引/负面语料参考池.md"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(self.pool.read_bytes())
        with self.assertRaisesRegex(ValueError, "negative_pool_owner_invalid"):
            self.mod.run(self.library, pool=archive)

    def test_apply_requires_explicit_v2_library(self):
        with self.assertRaisesRegex(ValueError, "explicit_library"):
            self.mod.run(apply=True)
        with self.assertRaisesRegex(ValueError, "migration_required"):
            self.mod.run(SKILL_DIR / "template-library", apply=True)

    def test_catalog_failure_restores_original_bytes_and_pointer(self):
        before = self.snapshot()
        with patch("leo_ppt_generator.template_catalog.build_catalog", side_effect=OSError("catalog failure")):
            with self.assertRaisesRegex(OSError, "catalog failure"):
                self.mod.run(self.library, pool=self.pool, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_drift_before_first_cas_preserves_external_bytes(self):
        from leo_ppt_generator.user_library import publish_user_library
        path = self.library / "canonical/visual/styles/style-a/brief.json"
        pointer = (self.library / "catalog/current.json").read_bytes()
        def external_write(*args, **kwargs):
            path.write_text("external bytes")
            return publish_user_library(*args, **kwargs)
        with patch.object(self.mod, "publish_user_library", side_effect=external_write):
            with self.assertRaisesRegex(ValueError, "drift"):
                self.mod.run(self.library, pool=self.pool, apply=True)
        self.assertEqual(path.read_text(), "external bytes")
        self.assertEqual((self.library / "catalog/current.json").read_bytes(), pointer)

    def test_cli_zero_candidates_in_current_delivery(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.mod.main(["--pool"]), 0)
        self.assertIn("候选 0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
