"""真实 CLI 的摘要、角色和选择失效合同。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime/src"))
from leo_ppt_generator import styles


class StyleIndexWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = dict(os.environ, PYTHONPATH=str(SKILL / "runtime/src"), LEO_PPT_BUNDLE=str(SKILL))
        schema = json.loads((SKILL / "runtime/src/leo_ppt_generator/schemas/style-index-v1.schema.json").read_text())
        self.validator = Draft7Validator({"$ref": "#/definitions/summary", "definitions": schema["definitions"]})

    def cli(self, *args):
        result = subprocess.run([sys.executable, "-m", "leo_ppt_generator.cli", "style", *args,
                                 "--home", str(self.home)], env=self.env, capture_output=True, text=True)
        data = json.loads(result.stdout or result.stderr)
        return result.returncode, data.get("style", data)

    def test_actual_cli_summary_schema_and_override_invalidate_selection(self):
        code, summary = self.cli("load", "清爽专业风", "--summary")
        self.assertEqual(code, 0)
        self.validator.validate(summary)
        brief = styles.parse_style_document(styles.load_style("清爽专业风", home=self.home)["content"])["brief"]
        brief["visual_direction"] = "用户覆盖后的视觉"
        styles.save_style("清爽专业风", "```json\n" + json.dumps(brief, ensure_ascii=False) + "\n```\n", home=self.home)
        code, result = self.cli("render", "清爽专业风", "--expected-selection", summary["selection_fingerprint"])
        self.assertNotEqual(code, 0)
        self.assertIn("style_selection_changed", json.dumps(result))
        code, actual = self.cli("load", "清爽专业风", "--summary")
        self.validator.validate(actual)
        self.assertEqual(actual["scope"], "user")
        self.assertEqual(actual["display"]["visual_character"]["value"], brief["visual_direction"])

    def test_ordinary_browse_excludes_pool_but_exact_lookup_preserves_role(self):
        brief = styles.parse_style_document(styles.load_style("清爽专业风", home=self.home)["content"])["brief"]
        brief.update(style_name="合成参考池", asset_role="pool", aliases=["合成池别名"])
        styles.save_style("合成参考池", "```json\n" + json.dumps(brief, ensure_ascii=False) + "\n```\n", home=self.home)
        offset = 0
        while True:
            page = styles.list_style_summaries(home=self.home, limit=40, offset=offset)
            self.assertTrue(all(item["asset_role"] == "style" for item in page["items"]))
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        exact = styles.list_style_summaries(home=self.home, needle="合成池别名")
        self.assertEqual(exact["total"], 1)
        self.assertEqual(exact["items"][0]["asset_role"], "pool")
        self.assertTrue(exact["items"][0]["compatibility"]["legacy_callable"])

    def test_summary_schema_rejects_full_content_and_unproven_visual_pass(self):
        summary = styles.style_summary("清爽专业风", home=self.home)
        self.validator.validate(summary)
        summary["content"] = "不应回传正文"
        self.assertTrue(list(self.validator.iter_errors(summary)))
        del summary["content"]
        summary["verification"]["visual"]["status"] = "passed"
        self.assertTrue(list(self.validator.iter_errors(summary)))


if __name__ == "__main__":
    unittest.main()
