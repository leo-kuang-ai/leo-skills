"""确定性注入链(templates.py)的合同测试。

覆盖 2026-08-29 大师评审团 R13 决议的六项修复:字段解析双冒号形态、
分隔行跳过、空骨架/歧义/原则文档误命中的 fail-fast、双 json 块提取、
风格判定收紧,以及网格物化(materialize_composition)。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator import styles, templates  # noqa: E402


def _write_layout(root: Path, filename: str, title: str, skeleton: str = "2×3 网格") -> None:
    body = (
        f"# 版式：{title}\n\n"
        f"**用途:** 测试用途\n\n"
        f"**适用内容类型:** 测试内容\n\n"
        f"**骨架:** {skeleton}\n\n"
        f"**关键类:** .test-class\n\n"
        f"**动效 recipe:** fade\n"
    )
    (root / "12_版式库" / filename).write_text(body, encoding="utf-8")


class FieldParsingTests(unittest.TestCase):
    def test_field_accepts_colon_outside_asterisks(self):
        text = "**骨架**: 左右分栏 5/11"
        self.assertEqual(templates._field(text, "**骨架**"), "左右分栏 5/11")

    def test_field_accepts_colon_inside_asterisks(self):
        text = "**骨架:** 左右分栏 5/11"
        self.assertEqual(templates._field(text, "**骨架**"), "左右分栏 5/11")

    def test_field_fullwidth_colon(self):
        text = "**骨架**：左右分栏 5/11"
        self.assertEqual(templates._field(text, "**骨架**"), "左右分栏 5/11")

    def test_table_skips_separator_rows(self):
        text = "| 线条 | 直角 |\n| --- | --- |\n| 纹理 | 纸纹 |"
        self.assertEqual(templates._table(text), {"线条": "直角", "纹理": "纸纹"})


class LayoutResolutionTests(unittest.TestCase):
    def test_load_layout_rejects_rule_documents(self):
        with self.assertRaises(templates.TemplateError):
            templates.load_layout("P0")

    def test_p_code_matches_exactly_not_by_substring(self):
        result = templates.load_layout("P1")
        self.assertEqual(result["name"], "P1 · Cover · 封面页")

    def test_load_layout_rejects_ambiguous_substring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "12_版式库").mkdir()
            _write_layout(root, "51_Duo_A.md", "P51 A Alpha")
            _write_layout(root, "52_Duo_B.md", "P51 B Beta")
            with mock.patch.object(templates, "_styles_root", return_value=root):
                with self.assertRaises(templates.TemplateError) as ctx:
                    templates.load_layout("P51")
            msg = str(ctx.exception)
            self.assertIn("51_Duo_A", msg)
            self.assertIn("52_Duo_B", msg)

    def test_compose_layout_raises_on_empty_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "12_版式库").mkdir()
            _write_layout(root, "61_Empty.md", "P61 Empty", "")
            with mock.patch.object(templates, "_styles_root", return_value=root):
                with self.assertRaises(templates.TemplateError):
                    templates.compose_layout("61_Empty")

    def test_exact_stem_match_wins_over_title_substring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "12_版式库").mkdir()
            _write_layout(root, "71_Cover.md", "P71 Cover 唯一")
            with mock.patch.object(templates, "_styles_root", return_value=root):
                result = templates.load_layout("71_Cover")
        self.assertEqual(result["purpose"], "测试用途")


class StyleBriefExtractionTests(unittest.TestCase):
    def test_double_json_block_uses_first_block(self):
        content = (
            "# 风格\n\n```json\n{\"visual_direction\": \"first\"}\n```\n\n"
            "中间散文\n\n```json\n{\"visual_direction\": \"second\"}\n```\n"
        )
        fake = {"name": "x", "source": "builtin", "path": "/x", "content": content, "sha256": ""}
        with mock.patch.object(templates, "load_style", return_value=fake):
            composed = templates.compose_style("x")
        self.assertEqual(composed["visual_direction"], "first")

    def test_single_block_still_extracts_first_block(self):
        content = "# 风格\n\n```json\n{\"visual_direction\": \"v\", \"typography\": \"t\"}\n```\n"
        fake = {"name": "x", "source": "builtin", "path": "/x", "content": content, "sha256": ""}
        with mock.patch.object(templates, "load_style", return_value=fake):
            composed = templates.compose_style("x")
        self.assertEqual(composed["visual_direction"], "v")

    def test_is_style_md_requires_parseable_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.md"
            good.write_text("```json\n{\"ok\": 1}\n```\n", encoding="utf-8")
            bad = Path(tmp) / "bad.md"
            bad.write_text("```json\n{not json at all\n```\n", encoding="utf-8")
            prose = Path(tmp) / "prose.md"
            prose.write_text("只有散文,没有代码块。\n", encoding="utf-8")
            self.assertTrue(styles._is_style_md(good))
            self.assertFalse(styles._is_style_md(bad))
            self.assertFalse(styles._is_style_md(prose))


class MaterializeCompositionTests(unittest.TestCase):
    def test_materialize_strips_css_and_translates_units(self):
        layout = {
            "name": "P4 Six Cells",
            "skeleton": "kicker 上方 + 2×3 网格 .cell-6,字号 min(11.6vw,19vh)",
        }
        hint = templates.materialize_composition(layout)
        self.assertNotIn(".cell-6", hint)
        self.assertNotIn("min(11.6vw,19vh)", hint)
        self.assertIn("2×3", hint)

    def test_compose_layout_materialize_flag_adds_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "12_版式库").mkdir()
            _write_layout(root, "81_Grid.md", "P81 Grid", "2×3 网格 .cell-6")
            with mock.patch.object(templates, "_styles_root", return_value=root):
                plain = templates.compose_layout("81_Grid")
                with mock.patch.object(templates, "_styles_root", return_value=root):
                    materialized = templates.compose_layout("81_Grid", materialize=True)
        self.assertNotIn("composition_hint", plain)
        self.assertIn("composition_hint", materialized)
        self.assertNotIn(".cell-6", materialized["composition_hint"])


class DeterminismGuardTests(unittest.TestCase):
    """合法输入的输出必须与仓库内嵌 golden 逐字节一致(确定性保护)。

    golden 于 2026-08-29 内容升级(渲染守卫句/瑞士极简措辞/P30)后固化于
    tests/fixtures/render_golden.json;再次有意变更内容时随同更新 fixture。
    """

    GOLDEN = Path(__file__).resolve().parent / "fixtures" / "render_golden.json"

    def _assert_matches_golden(self, key: str, composed: dict) -> None:
        golden = json.loads(self.GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(
            json.dumps(composed, ensure_ascii=False, sort_keys=True, default=str),
            json.dumps(golden[key], ensure_ascii=False, sort_keys=True, default=str),
        )

    def test_builtin_style_output_matches_golden(self):
        self._assert_matches_golden(
            "style:minimal", templates.compose_style("极简风", mode="结论先行金字塔")
        )

    def test_builtin_mckinsey_style_matches_golden(self):
        self._assert_matches_golden(
            "style:mckinsey", templates.compose_style("麦肯锡咨询风", mode="故事弧")
        )

    def test_builtin_layout_output_matches_golden(self):
        self._assert_matches_golden(
            "layout:P6", templates.compose_layout("P6", image_type="漏斗图")
        )

    def test_new_layout_materialize_matches_golden(self):
        self._assert_matches_golden(
            "layout:P30", templates.compose_layout("P30", materialize=True)
        )

    def test_new_layout_p31_matches_golden(self):
        self._assert_matches_golden("layout:P31", templates.compose_layout("P31"))


if __name__ == "__main__":
    unittest.main()
