"""资产发现、角色、摘要和兼容引用的行为测试。"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))
from leo_ppt_generator import styles

BRIEF = {
    "type": "16:9 full-slide PowerPoint image", "style_name": "测试风格",
    "best_for": "项目复盘", "visual_direction": "清晰网格",
    "canvas": {"aspect_ratio": "16:9", "background": "#FFFFFF", "composition": "grid", "density": "medium"},
    "color_palette": {"primary": "#111111"}, "typography": {"title": "Noto Sans SC"},
    "layout_patterns": ["左文右图"], "aliases": ["同名别名"],
}


class StyleAssetInventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name="测试风格.md", brief=None, prefix="# 风格\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prefix + "\n```json\n" + json.dumps(brief or BRIEF, ensure_ascii=False) + "\n```\n", encoding="utf-8")
        return path

    def test_complete_style_in_new_directory_is_discovered(self):
        self.write("new-source/测试风格.md")
        entry = styles.style_asset_inventory(self.root)[0]
        self.assertEqual(entry["asset_role"], "style")
        self.assertEqual(entry["coverage"], "full")
        self.assertIsNone(entry["taxonomy"])
        self.assertEqual(entry["verification"]["visual"]["status"], "not-run")

    def test_pool_stays_pool_and_legacy_callable(self):
        path = self.write(prefix="# 测试池\n\n**分类:** 参考池代表\n")
        entry = styles.describe_style_asset(path, self.root)
        self.assertEqual(entry["asset_role"], "pool")
        self.assertTrue(entry["compatibility"]["legacy_callable"])
        self.assertTrue(styles._is_style_md(path))

    def test_conflicting_role_does_not_become_style(self):
        path = self.write(brief={**BRIEF, "asset_role": "style"}, prefix="**分类:** 参考池代表\n")
        entry = styles.describe_style_asset(path, self.root)
        self.assertEqual(entry["asset_role"], "unknown")
        self.assertIn("asset_role_conflict", entry["diagnostics"])

    def test_json_example_is_reference_and_legacy_predicate_unchanged(self):
        path = self.write(brief={"ok": 1})
        self.assertTrue(styles._is_style_md(path))
        entry = styles.describe_style_asset(path, self.root)
        self.assertEqual(entry["asset_role"], "reference")
        self.assertFalse(entry["compatibility"]["legacy_callable"])

    def test_malformed_json_and_generated_files(self):
        path = self.root / "bad.md"
        path.write_text("```json\n{not-json\n```\n")
        self.write("generated/fake.md")
        entries = styles.style_asset_inventory(self.root)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["asset_role"], "unknown")
        self.assertIn("invalid_json", entries[0]["diagnostics"])

    def test_alias_collisions_are_not_missing_members(self):
        self.write()
        self.write("second.md", {**BRIEF, "style_name": "另一个风格"})
        entries = styles.style_asset_inventory(self.root)
        self.assertEqual([e["aliases"] for e in entries], [["同名别名"], ["同名别名"]])
        self.assertEqual(styles.style_reference_problems(entries), [])

    def test_duplicate_names_and_missing_members_are_reported(self):
        self.write()
        self.write("other/same.md")
        errors = styles.style_reference_problems(styles.style_asset_inventory(self.root), members={"family": ["不存在"]})
        self.assertEqual({e["code"] for e in errors}, {"duplicate_style_name", "style_member_missing"})

    def test_variant_cycle_and_bidirectional_relation(self):
        self.write(brief={**BRIEF, "variants": ["变体: 不同场景"]})
        self.write("变体.md", {**BRIEF, "style_name": "变体", "variant_of": "测试风格"})
        self.assertEqual(styles.style_reference_problems(styles.style_asset_inventory(self.root)), [])
        self.write(brief={**BRIEF, "variant_of": "变体"})
        codes = {e["code"] for e in styles.style_reference_problems(styles.style_asset_inventory(self.root))}
        self.assertIn("variant_cycle_or_chain", codes)

    def test_summary_is_bounded_and_provenance_is_not_invented(self):
        brief = copy.deepcopy(BRIEF)
        brief["best_for"] = "中" * 121
        brief["visual_direction"] = " ".join(["v"] * 161)
        brief["canvas"].pop("density")
        entry = styles.describe_style_asset(self.write(brief=brief), self.root)
        self.assertEqual(len(entry["display"]["suitable_for"]["value"]), 120)
        self.assertTrue(entry["display"]["suitable_for"]["truncated"])
        self.assertFalse(entry["display"]["density"]["present"])
        self.assertEqual(entry["coverage"], "partial")
        self.assertIsNone(entry["authored_source"])

    def test_outside_symlink_is_not_read(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "private.md"
            target.write_text("不能泄漏的私人正文")
            link = self.root / "link.md"
            link.symlink_to(target)
            entry = styles.describe_style_asset(link, self.root)
            self.assertEqual(entry["diagnostics"], ["asset_outside_root"])
            self.assertNotIn("私人", json.dumps(entry, ensure_ascii=False))

    def test_all_roles_have_separate_coverage_and_verification(self):
        (self.root / "rule.md").write_text("# 规则\n")
        (self.root / "P1.layouts.json").write_text('{"entity":"layout","layout_id":"P1"}')
        (self.root / "asset.bin").write_bytes(b"binary")
        for entry in styles.style_asset_inventory(self.root):
            self.assertEqual(entry["coverage"], "name-only")
            self.assertEqual(entry["verification"]["visual"]["status"], "not-run")

    def test_malformed_role_and_variants_do_not_crash(self):
        entry = styles.describe_style_asset(self.write(brief={**BRIEF, "asset_role": [], "variants": None}), self.root)
        self.assertIn("asset_role_invalid", entry["diagnostics"])
        self.assertIn("variants_invalid", entry["diagnostics"])


if __name__ == "__main__":
    unittest.main()
