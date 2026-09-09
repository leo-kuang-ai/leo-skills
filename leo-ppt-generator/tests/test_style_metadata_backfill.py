"""L0 可选元数据实际校验与 11 个内置回填的兼容证明。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))
sys.path.insert(0, str(SKILL / "scripts"))
from leo_ppt_generator import styles
import lint_style_briefs as lint
import style_hard_rules as rules

BUILTINS = (
    "党政红风格", "创意杂志风", "复古扁平插画风", "手绘技术解释风", "手绘白板风",
    "教学课件风", "数据仪表盘风", "清爽专业风", "温暖手工风", "电子墨水杂志风", "科研答辩风",
)


class StyleMetadataBackfillTest(unittest.TestCase):
    def test_old_brief_without_metadata_stays_valid(self):
        self.assertEqual(styles.validate_style_metadata({}), [])

    def test_unknown_license_does_not_require_origin(self):
        self.assertEqual(styles.validate_style_metadata({"source": {"license": "unknown"}}), [])

    def test_wrong_types_and_unknown_licenses_fail(self):
        for value in (None, [], "MIT"):
            with self.subTest(value=value):
                self.assertIn("source:type", styles.validate_style_metadata({"source": value}))
        self.assertIn("source.license:enum", styles.validate_style_metadata({"source": {"license": "verified"}}))

    def test_origin_is_not_guessed_and_unknown_keys_fail(self):
        errors = styles.validate_style_metadata({"source": {"origin": "unknown", "license": "unknown", "approved": True}})
        self.assertIn("source.origin:enum", errors)
        self.assertIn("source.approved:unknown", errors)

    def test_families_are_namespaced_unique_and_main_is_a_member(self):
        errors = styles.validate_style_metadata({"taxonomy": {"families": ["business", "business"], "visual_family": "family:other"}})
        self.assertIn("taxonomy.families[0]:pattern", errors)
        self.assertIn("taxonomy.families:duplicate", errors)
        self.assertIn("taxonomy.visual_family:not_in_families", errors)

    def test_unknown_main_family_may_be_absent(self):
        self.assertEqual(styles.validate_style_metadata({"taxonomy": {"families": ["family:teaching"]}}), [])

    def test_lint_checks_new_metadata_instead_of_only_declaring_schema(self):
        sample = styles.parse_style_document((SKILL / "template-library/reference/sources/retired-styles-tree/styles/清爽专业风.md").read_text())["brief"]
        sample["source"] = {"license": "made-up-license"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "bad.md"
            path.write_text("```json\n" + json.dumps(sample, ensure_ascii=False) + "\n```\n")
            errors, _ = lint._lint_one(path, lint._load_schema(), rel_to=root)
        self.assertTrue(any("metadata_invalid" in value and "source.license:enum" in value for value in errors))

    def test_eleven_builtins_have_only_evidenced_metadata(self):
        for name in BUILTINS:
            with self.subTest(name=name):
                brief = styles.parse_style_document((SKILL / "template-library/reference/sources/retired-styles-tree/styles" / f"{name}.md").read_text())["brief"]
                self.assertEqual(brief["source"], {"license": "unknown"})
                self.assertNotIn("visual_family", brief["taxonomy"])
                self.assertEqual(styles.validate_style_metadata(brief), [])

    def test_current_family_membership_driven_by_authored_taxonomy(self):
        # U10 后成员真值源是 template-library brief 的 taxonomy.families：
        # 兼容表成员必须都存在于库中（防失明，池代表在 reference/pools）。
        members = rules.current_family_members()
        library_names = rules._library_style_names()
        for label, names in members.items():
            for name in names:
                self.assertIn(name, library_names,
                              f"家族 {label} 引用库中不存在的风格 {name}")
        self.assertIn("手绘白板风", members["艺术手绘"])
        self.assertIn("清爽专业风", members["商务专业"])
        self.assertIn("朋克深底撞色池", members["参考池代表"])
        # 垂直切片行业皮肤声明自己的方向家族（开放词表，不并入语义家族）。
        self.assertIn("品牌创意风", members["品牌方向"])

    def test_bad_family_mapping_does_not_silently_change_candidates(self):
        # v2 词表开放：未知家族标签不得静默并入已知家族——自成可见桶，
        # 已知家族成员不变（静默改判=候选池漂移，才是要拦的回归）。
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_dir = root / "synthetic-style"
            style_dir.mkdir()
            (style_dir / "brief.json").write_text(json.dumps({
                "schema_version": 2, "entity": "style-brief",
                "asset_id": "builtin:style:synthetic-style", "name": "合成风",
                "lifecycle": "active",
                "taxonomy": {"families": ["family:unmapped"]},
                "visual_language": {"direction": "synthetic direction"},
                "bindings": {},
            }, ensure_ascii=False), encoding="utf-8")
            members = rules.current_family_members(root)
        self.assertIn("合成风", members["family:unmapped"])
        for label in ("商务专业", "学术答辩", "党政红"):
            self.assertNotIn("合成风", members[label])


if __name__ == "__main__":
    unittest.main()
