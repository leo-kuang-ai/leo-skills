"""D2 render chart 的可观察行为测试：抽块/映射纯函数离线；渲染用例按 skip 披露。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.render.helpers import browser_test_case

from leo_ppt_generator.render.chart import (
    DEFAULT_THEME_WARNING,
    build_theme_variables,
    extract_mermaid_example,
    load_chart_code,
    render_chart,
)
from leo_ppt_generator.render.errors import RenderError

SKILL_ROOT = Path(__file__).resolve().parents[2]
LINE_CHART_MD = SKILL_ROOT / "template-library/reference/sources/retired-styles-tree/styles/11_图表语法/折线图.md"


class ExtractMermaidExampleBlock(unittest.TestCase):
    """从 11_图表语法 方言文件抽取 ```mermaid-example 块（零改写升级）。"""

    def test_extracts_first_block_from_real_dialect_file(self):
        code, count = extract_mermaid_example(LINE_CHART_MD.read_text(encoding="utf-8"))
        self.assertEqual(count, 1)
        self.assertTrue(code.startswith("xychart-beta"))
        self.assertIn('"月度活跃用户(万)"', code)
        self.assertIn("line [120, 138, 171, 164, 205, 248]", code)

    def test_multiple_blocks_take_first_and_report_count(self):
        text = (
            "```mermaid-example\nxychart-beta\n  line [1]\n```\n"
            "```mermaid-example\nxychart-beta\n  line [2]\n```\n"
        )
        code, count = extract_mermaid_example(text)
        self.assertEqual(count, 2)
        self.assertIn("line [1]", code)

    def test_missing_block_reports_render_data_invalid(self):
        with self.assertRaises(RenderError) as ctx:
            extract_mermaid_example("# no blocks here\n\nplain text\n")
        self.assertEqual(ctx.exception.reason_code, "render_data_invalid")

    def test_load_chart_code_requires_exactly_one_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RenderError) as ctx:
                load_chart_code()
            self.assertEqual(ctx.exception.reason_code, "render_data_invalid")


class ThemeVariableMapping(unittest.TestCase):
    """deck colors 锚 → mermaid 键（含 xyChart 域补充）。"""

    def test_no_theme_warns_and_uses_defaults(self):
        variables, warnings = build_theme_variables(None)
        self.assertEqual(variables, {})
        self.assertIn(DEFAULT_THEME_WARNING, warnings)

    def test_primary_maps_to_primary_color_and_xychart_palette(self):
        variables, warnings = build_theme_variables(
            {"primary": "#1a9850", "background": "#f0f4f8"}
        )
        self.assertEqual(variables["primaryColor"], "#1a9850")
        self.assertEqual(variables["mainBkg"], "#f0f4f8")
        self.assertEqual(variables["xyChart"]["plotColorPalette"], "#1a9850")
        self.assertEqual(variables["xyChart"]["backgroundColor"], "#f0f4f8")
        self.assertEqual(warnings, [])

    def test_unmatched_anchors_block_not_default(self):
        """§8.2 治理合同：给了主题但映射键全落空 → 阻断，不回落 mermaid 默认。"""
        from leo_ppt_generator.render.errors import RenderError

        with self.assertRaises(RenderError) as ctx:
            build_theme_variables({"nothing": "matches"})
        self.assertEqual(ctx.exception.reason_code, "chart_theme_mapping_missing")


class RenderChartBrowser(browser_test_case()):
    def test_renders_line_chart_svg_with_verbatim_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "chart.svg"
            result = render_chart(dialect="mermaid", source=LINE_CHART_MD, out=out)
            svg = out.read_text(encoding="utf-8")
            self.assertIn("<svg", svg)
            # 数值/标签逐字保真：标题与 x 轴类目原文在 SVG 文本中
            self.assertIn("月度活跃用户(万)", svg)
            for month in ("1月", "2月", "3月", "4月", "5月", "6月"):
                self.assertIn(month, svg)
            self.assertIn("MAU", svg)
            self.assertEqual(result["backend"], "render:mermaid")
            self.assertEqual(result["out_sha256"], result["out_sha256"])

    def test_invalid_syntax_reports_render_data_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = Path(tmp) / "bad.mmd"
            code.write_text("this is not valid mermaid at all %%\n", encoding="utf-8")
            with self.assertRaises(RenderError) as ctx:
                render_chart(dialect="mermaid", code_file=code, out=Path(tmp) / "bad.svg")
            self.assertEqual(ctx.exception.reason_code, "render_data_invalid")

    def test_theme_primary_color_greppable_in_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "theme.json"
            theme.write_text('{"primary": "#1a9850", "background": "#f0f4f8"}', encoding="utf-8")
            out = Path(tmp) / "chart.svg"
            render_chart(dialect="mermaid", source=LINE_CHART_MD, out=out, theme_file=theme)
            svg = out.read_text(encoding="utf-8")
            self.assertIn("#1a9850", svg)


if __name__ == "__main__":
    unittest.main()
