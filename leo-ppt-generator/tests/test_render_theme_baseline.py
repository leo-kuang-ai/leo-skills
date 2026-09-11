"""U1 行业合并交付：七模板 21 页改前渲染基线的清单完整性。

基线用途：解释重构差异（改前基线）；不沿用旧方案 diff ≤0.001 作为新设计
等价门。本测试只做结构校验（21 页、hash 齐全、命令可复现），不做像素比较。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
BASELINE_DIR = SKILL_DIR / "tests" / "fixtures" / "render-theme-baseline"
MANIFEST = BASELINE_DIR / "manifest.json"

TEMPLATES = ("cover-basic", "body-basic", "compare", "timeline",
             "spec-table", "pull-quote", "frame-shot")
LEVELS = ("minimal", "typical", "near-capacity")


class RenderThemeBaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_covers_all_seven_templates_three_levels(self) -> None:
        pages = self.manifest["pages"]
        self.assertEqual(len(pages), 21)
        expected = {(t, l) for t in TEMPLATES for l in LEVELS}
        actual = {(page["template"], page["level"]) for page in pages}
        self.assertEqual(actual, expected, f"缺页: {expected - actual}")

    def test_every_page_has_input_output_hash_and_command(self) -> None:
        for page in self.manifest["pages"]:
            for field in ("page_id", "input_path", "input_sha256",
                          "output_path", "output_sha256", "output_size", "command"):
                self.assertIn(field, page, f"{page.get('page_id')} 缺 {field}")
            self.assertTrue((SKILL_DIR / page["input_path"]).is_file(),
                            f"输入文件缺失: {page['input_path']}")
            self.assertTrue((SKILL_DIR / page["output_path"]).is_file(),
                            f"输出 PNG 缺失: {page['output_path']}")
            self.assertEqual(page["output_size"], [2560, 1440],
                             f"{page['page_id']} 输出尺寸异常")

    def test_freeze_context_recorded(self) -> None:
        freeze = self.manifest["freeze"]
        self.assertTrue(freeze["head"])
        self.assertIsInstance(freeze["dirty_files"], list)
        facts = self.manifest["render_facts"]
        self.assertEqual(facts["status"], "render_backend_ready")
        self.assertTrue(facts["playwright_version"] and facts["chromium_version"])
        self.assertTrue(self.manifest["source_hashes"],
                        "源码 dirty hash 未记录")

    def test_plan_reference_and_purpose_declared(self) -> None:
        self.assertIn("template-quality-plan", self.manifest["plan"])
        self.assertIn("不作为新设计等价门", self.manifest["purpose"])


if __name__ == "__main__":
    unittest.main()
