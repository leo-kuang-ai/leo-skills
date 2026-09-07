"""摘要和 guarded render 的实际来源必须一致。"""
import json
import os
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
        raw = (SKILL / "references/styles" / f"{self.name}.md").read_text()
        self.brief = styles.parse_style_document(raw)["brief"]
        self.brief["visual_direction"] = "用户红色极简风"
        self.save()

    def save(self):
        return styles.save_style(self.name, "# 用户风格\n\n```json\n" + json.dumps(self.brief, ensure_ascii=False) + "\n```\n", home=self.home, overwrite=True)

    def test_summary_is_user_scoped_and_does_not_return_full_content(self):
        summary = styles.style_summary(self.name, home=self.home)
        self.assertEqual(summary["scope"], "user")
        self.assertEqual(summary["display"]["visual_character"]["value"], "用户红色极简风")
        self.assertNotIn("content", summary)
        self.assertFalse(Path(summary["path"]).is_absolute())

    def test_guarded_composition_uses_same_home_and_no_builtin_pairing(self):
        summary = styles.style_summary(self.name, home=self.home)
        result = templates.compose_style(self.name, home=self.home, expected_selection=summary["selection_fingerprint"])
        self.assertEqual(result["visual_direction"], "用户红色极简风")
        self.assertNotIn("image_rendering", result)
        self.assertNotIn("selection_fingerprint", result)

    def test_changed_content_and_deleted_override_fail_guard(self):
        original = styles.style_summary(self.name, home=self.home)["selection_fingerprint"]
        self.brief["visual_direction"] = "已发生变化"
        self.save()
        with self.assertRaisesRegex(styles.StyleStoreError, "style_selection_changed"):
            templates.compose_style(self.name, home=self.home, expected_selection=original)
        (self.home / "styles" / f"{self.name}.md").unlink()
        with self.assertRaisesRegex(styles.StyleStoreError, "style_selection_changed"):
            templates.compose_style(self.name, home=self.home, expected_selection=original)

    def test_alias_query_works_without_generated_catalog(self):
        self.brief["aliases"] = ["共有测试别名"]
        self.save()
        second = dict(self.brief, style_name="用户第二风格")
        styles.save_style("用户第二风格", "```json\n" + json.dumps(second, ensure_ascii=False) + "\n```\n", home=self.home)
        result = styles.list_style_summaries(home=self.home, needle="共有测试别名", limit=1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["next_offset"], 1)
        self.assertEqual(len(result["items"]), 1)

    def test_crlf_content_and_raw_file_hash_have_distinct_scopes(self):
        path = self.home / "styles" / f"{self.name}.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        summary = styles.style_summary(self.name, home=self.home)
        self.assertNotEqual(summary["file_sha256"], summary["style_content_digest"])
        self.assertEqual(summary["style_content_digest"], styles.load_style(self.name, home=self.home)["sha256"])

    def test_guard_reuses_single_loaded_content(self):
        summary = styles.style_summary(self.name, home=self.home)
        with mock.patch.object(templates, "load_style", wraps=styles.load_style) as loader:
            templates.compose_style(self.name, home=self.home, expected_selection=summary["selection_fingerprint"])
        self.assertEqual(loader.call_count, 1)

    def test_guard_rejects_summary_and_first_json_disagreement(self):
        path = self.home / "styles" / f"{self.name}.md"
        path.write_text('```json\n{"example":true}\n```\n' + path.read_text())
        summary = styles.style_summary(self.name, home=self.home)
        self.assertIn("style_brief_not_first_block", summary["diagnostics"])
        with self.assertRaisesRegex(styles.StyleStoreError, "style_selection_invalid"):
            templates.compose_style(self.name, home=self.home, expected_selection=summary["selection_fingerprint"])

    def test_guard_rejects_non_style_roles_even_with_complete_brief(self):
        for role in ("layout", "axis", "rule", "reference", "unknown"):
            with self.subTest(role=role):
                self.brief["asset_role"] = role
                self.save()
                summary = styles.style_summary(self.name, home=self.home)
                with self.assertRaisesRegex(styles.StyleStoreError, "style_selection_invalid"):
                    templates.compose_style(self.name, home=self.home, expected_selection=summary["selection_fingerprint"])
        self.brief["asset_role"] = "pool"
        self.save()
        summary = styles.style_summary(self.name, home=self.home)
        self.assertEqual(templates.compose_style(self.name, home=self.home, expected_selection=summary["selection_fingerprint"])["visual_direction"], self.brief["visual_direction"])

    def test_cli_render_forwards_explicit_home(self):
        env = dict(os.environ, PYTHONPATH=str(SKILL / "runtime/src"), LEO_PPT_BUNDLE=str(SKILL))
        summary = styles.style_summary(self.name, home=self.home)
        result = subprocess.run([sys.executable, "-m", "leo_ppt_generator.cli", "style", "render", self.name,
                                 "--home", str(self.home), "--expected-selection", summary["selection_fingerprint"]],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("用户红色极简风", result.stdout)


if __name__ == "__main__":
    unittest.main()
