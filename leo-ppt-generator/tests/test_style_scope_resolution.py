"""摘要和 guarded render 的实际来源必须一致（U10 新协议：用户 overlay 为
${LEO_PPT_HOME}/template-library，选择指纹覆盖 scope/asset_id/revision）。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime/src"))
from leo_ppt_generator import styles, templates


class StyleScopeResolutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.name = "清爽专业风"
        builtin = styles.load_style(self.name)
        legacy = dict(builtin["brief"].get("legacy_payload") or {})
        self.brief = {"style_name": self.name, **legacy}
        self.brief["visual_direction"] = "用户红色极简风，网格排印与克制留白"
        self.save()

    def user_brief_path(self) -> Path:
        return (self.home / "template-library" / "canonical" / "styles"
                / self.name / "brief.json")

    def save(self):
        return styles.save_style(
            self.name, json.dumps(self.brief, ensure_ascii=False),
            home=self.home, overwrite=True)

    def test_summary_is_user_scoped_and_does_not_return_full_content(self):
        summary = styles.style_summary(self.name, home=self.home)
        self.assertEqual(summary["source"], "user")
        self.assertEqual(summary["display"]["visual_character"]["value"],
                         "用户红色极简风，网格排印与克制留白")
        self.assertNotIn("content", summary)
        self.assertTrue(Path(summary["path"]).is_relative_to(self.home))

    def test_guarded_composition_uses_same_home_and_no_builtin_pairing(self):
        summary = styles.style_summary(self.name, home=self.home)
        result = templates.compose_style(
            self.name, home=self.home,
            expected_selection=summary["selection_fingerprint"])
        self.assertEqual(result["visual_direction"],
                         "用户红色极简风，网格排印与克制留白")
        self.assertNotIn("image_rendering", result)
        self.assertNotIn("selection_fingerprint", result)

    def test_changed_content_and_deleted_override_fail_guard(self):
        original = styles.style_summary(
            self.name, home=self.home)["selection_fingerprint"]
        self.brief["visual_direction"] = "已发生变化的视觉方向描述"
        self.save()
        with self.assertRaisesRegex(styles.StyleStoreError, "style_selection_changed"):
            templates.compose_style(self.name, home=self.home,
                                    expected_selection=original)
        self.user_brief_path().unlink()
        with self.assertRaisesRegex(styles.StyleStoreError, "style_selection_changed"):
            templates.compose_style(self.name, home=self.home,
                                    expected_selection=original)

    def test_alias_query_works_without_generated_catalog(self):
        self.brief["aliases"] = ["共有测试别名"]
        self.save()
        second = dict(self.brief, style_name="用户第二风格")
        styles.save_style("用户第二风格",
                          json.dumps(second, ensure_ascii=False), home=self.home)
        result = styles.list_style_summaries(home=self.home,
                                             needle="共有测试别名", limit=1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["next_offset"], 1)
        self.assertEqual(len(result["items"]), 1)

    def test_plain_style_list_filter_matches_alias(self):
        """普通列表与摘要列表必须共享 catalog 的 aliases 过滤语义。"""
        self.brief["aliases"] = ["共有测试别名"]
        self.save()
        entries = [item for item in styles.list_styles(home=self.home)
                   if "共有测试别名" in item.get("aliases", [])]
        self.assertEqual([item["name"] for item in entries], [self.name])
        self.assertEqual(entries[0]["aliases"], ["共有测试别名"])

    def test_guard_reuses_single_loaded_content(self):
        summary = styles.style_summary(self.name, home=self.home)
        with mock.patch.object(templates, "load_style",
                               wraps=styles.load_style) as loader:
            templates.compose_style(
                self.name, home=self.home,
                expected_selection=summary["selection_fingerprint"])
        self.assertEqual(loader.call_count, 1)

    def test_empty_cli_lists_preserve_rebuilt_registry_source(self):
        """筛选无匹配和库内无风格两种空列表均须披露重建来源。"""
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            library = bundle / "template-library"
            shutil.copytree(SKILL / "tests/fixtures/minimal-template-library", library)
            env = dict(os.environ, PYTHONPATH=str(SKILL / "runtime/src"),
                       LEO_PPT_BUNDLE=str(bundle),
                       LEO_PPT_HOME=str(Path(directory) / "home"))
            for empty_library in (False, True):
                if empty_library:
                    shutil.rmtree(library / "canonical/styles")
                for summary in (False, True):
                    args = ["--summary"] if summary else []
                    if not empty_library:
                        args += ["--filter", "no-such-style-audit"]
                    with self.subTest(empty_library=empty_library, summary=summary):
                        proc = subprocess.run(
                            [sys.executable, "-m", "leo_ppt_generator.cli",
                             "style", "list", *args],
                            env=env, capture_output=True, text=True)
                        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                        payload = json.loads(proc.stdout)
                        self.assertEqual(payload["styles" if not summary else "items"], [])
                        self.assertEqual(payload["registry_source"], "canonical-rebuild")

    def test_non_style_entities_cannot_be_composed_as_styles(self):
        # 新协议负例：非 style 实体（版式 P6）在类型层即被 resolver 拒绝，
        # 不得作为风格加载/组合（旧 asset_role 嗅探的等价拒绝路径）。
        with self.assertRaises(styles.StyleStoreError) as ctx:
            templates.compose_style("P6")
        self.assertIn("style_not_found", str(ctx.exception))

    def test_cli_render_forwards_explicit_home(self):
        env = dict(os.environ, PYTHONPATH=str(SKILL / "runtime/src"),
                   LEO_PPT_BUNDLE=str(SKILL))
        summary = styles.style_summary(self.name, home=self.home)
        result = subprocess.run(
            [sys.executable, "-m", "leo_ppt_generator.cli", "style", "render",
             self.name, "--home", str(self.home),
             "--expected-selection", summary["selection_fingerprint"]],
            env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("用户红色极简风", result.stdout)

    def test_cli_summary_blocks_on_single_catalog_revision_drift(self):
        """单个 brief 漂移时摘要 CLI 必须 fail closed，而不是返回部分 ready 列表。"""
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            shutil.copytree(SKILL / "template-library", bundle / "template-library")
            target = bundle / "template-library" / "canonical" / "styles" / "finance-navy" / "brief.json"
            data = json.loads(target.read_text(encoding="utf-8"))
            data["name"] = f"{data.get('name', 'finance-navy')} 漂移"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            env = dict(
                os.environ,
                PYTHONPATH=str(SKILL / "runtime/src"),
                LEO_PPT_BUNDLE=str(bundle),
                LEO_PPT_HOME=str(Path(directory) / "home"),
            )
            result = subprocess.run(
                [sys.executable, "-m", "leo_ppt_generator.cli", "style", "list", "--summary"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stderr.strip())
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["reason_code"], "stale_catalog")

    def test_load_summary_preserves_catalog_stale_reason(self):
        """直接加载路径也必须保留 registry 漂移的稳定 reason code。"""
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            shutil.copytree(SKILL / "template-library", bundle / "template-library")
            target = bundle / "template-library" / "canonical" / "styles" / "clean-professional" / "brief.json"
            data = json.loads(target.read_text(encoding="utf-8"))
            data["name"] = f"{data.get('name', 'clean-professional')} 漂移"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            env = dict(os.environ, LEO_PPT_BUNDLE=str(bundle))
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(styles.StyleCatalogStale):
                    styles.style_summary("清爽专业风")

    def test_cli_summary_blocks_on_unreadable_catalog_entity(self):
        """坏的 canonical brief 不得降级成带 problems 的 ready 列表。"""
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            shutil.copytree(SKILL / "template-library", bundle / "template-library")
            target = (bundle / "template-library" / "canonical" / "styles"
                      / "finance-navy" / "brief.json")
            target.write_text("{bad", encoding="utf-8")
            env = dict(
                os.environ,
                PYTHONPATH=str(SKILL / "runtime/src"),
                LEO_PPT_BUNDLE=str(bundle),
                LEO_PPT_HOME=str(Path(directory) / "home"),
            )
            result = subprocess.run(
                [sys.executable, "-m", "leo_ppt_generator.cli",
                 "style", "list", "--summary"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stderr.strip())
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["reason_code"], "style_catalog_incomplete")

    def test_style_lists_disclose_canonical_rebuild_source(self):
        """缺 catalog 时，列表必须披露 resolver 的降级来源。"""
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            shutil.copytree(
                SKILL / "tests" / "fixtures" / "minimal-template-library",
                bundle / "template-library",
            )
            env = {
                "LEO_PPT_BUNDLE": str(bundle),
                "LEO_PPT_HOME": str(Path(directory) / "home"),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                entries = styles.list_styles()
                self.assertTrue(entries)
                self.assertEqual({entry["registry_source"] for entry in entries},
                                 {"canonical-rebuild"})
                result = styles.list_style_summaries(limit=1)
                self.assertEqual(result["registry_source"], "canonical-rebuild")


if __name__ == "__main__":
    unittest.main()
