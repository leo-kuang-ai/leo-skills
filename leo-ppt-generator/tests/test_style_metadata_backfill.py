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
        sample = styles.parse_style_document((SKILL / "references/styles/清爽专业风.md").read_text())["brief"]
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
                brief = styles.parse_style_document((SKILL / "references/styles" / f"{name}.md").read_text())["brief"]
                self.assertEqual(brief["source"], {"license": "unknown"})
                self.assertNotIn("visual_family", brief["taxonomy"])
                self.assertEqual(styles.validate_style_metadata(brief), [])

    def test_current_family_membership_equals_legacy_fixture(self):
        self.assertEqual(rules.current_family_members(), {key: sorted(set(values)) for key, values in rules.FAMILIES.items()})

    def test_bad_family_mapping_does_not_silently_change_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "synthetic.md").write_text('```json\n{"style_name":"x","taxonomy":{"families":["family:unmapped"]}}\n```\n')
            with self.assertRaisesRegex(ValueError, "style_family_mapping_unknown"):
                rules.current_family_members(root)


if __name__ == "__main__":
    unittest.main()
