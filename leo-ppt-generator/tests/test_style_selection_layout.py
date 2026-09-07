"""实际候选分数不能代替独立容量检查，用户覆盖不继承内置路由。"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "runtime/src"))
import suggest_layout as suggest
import check_deck_geometry as geometry
from leo_ppt_generator import styles, templates


class SelectionLayoutTest(unittest.TestCase):
    def capacity(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capacity.json"
            path.write_text(json.dumps(data, ensure_ascii=False))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = geometry.capacity_check(path)
            return code, output.getvalue()

    def test_auto_high_score_does_not_override_hard_overflow(self):
        bank = suggest.load_bank()
        result = suggest.score_page({"page": 1, "page_role": "封面", "points": 1, "est_chars": 10000}, bank, 1.0, {})
        self.assertEqual(result["decision"], "auto")
        chosen = result["candidates"][0]["layout"]
        self.assertTrue(any("硬超" in reason for reason in result["candidates"][0]["reasons"]))
        code, output = self.capacity({"slides": [{"page": 1, "layout": chosen, "points": ["长" * 10000]}]})
        self.assertEqual(code, 1)
        self.assertIn("overflow", output)

    def test_user_override_neutral_layout_input_does_not_load_named_factor(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            name = "手绘白板风"
            source = styles.load_style(name, home=home)["content"]
            styles.save_style(name, source, home=home)
            summary = styles.style_summary(name, home=home)
            self.assertEqual(summary["scope"], "user")
            result = templates.compose_style(name, home=home, expected_selection=summary["selection_fingerprint"])
            self.assertNotIn("image_rendering", result)
            factor, adjustments = suggest.load_style_routing(None)
            self.assertEqual((factor, adjustments), (1.0, {}))
            code, output = self.capacity({"slides": [{"page": 1, "layout": "P6", "slots": {"item_label": "字" * 44}}]})
            self.assertEqual(code, 0)
            self.assertIn("[OK]", output)

    def test_unknown_layout_and_empty_bank_are_not_success(self):
        self.assertEqual(self.capacity({"slides": [{"page": 1, "layout": "P999"}]})[0], 2)
        with mock.patch.object(geometry, "_load_layout_sidecars", return_value={}):
            self.assertEqual(self.capacity({"slides": [{"page": 1, "layout": "P1"}]})[0], 2)

    def test_metadata_only_change_keeps_visual_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            name = "清爽专业风"
            raw = styles.load_style(name, home=home)["content"]
            brief = styles.parse_style_document(raw)["brief"]
            styles.save_style(name, "```json\n" + json.dumps(brief, ensure_ascii=False) + "\n```\n", home=home)
            first = styles.style_summary(name, home=home)
            before = templates.compose_style(name, home=home, expected_selection=first["selection_fingerprint"])
            brief["source"] = {"license": "unknown", "batch": "metadata-only"}
            styles.save_style(name, "```json\n" + json.dumps(brief, ensure_ascii=False) + "\n```\n", home=home, overwrite=True)
            second = styles.style_summary(name, home=home)
            after = templates.compose_style(name, home=home, expected_selection=second["selection_fingerprint"])
            self.assertNotEqual(first["style_content_digest"], second["style_content_digest"])
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
