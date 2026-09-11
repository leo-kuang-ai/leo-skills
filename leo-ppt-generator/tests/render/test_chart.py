"""D2 render chart 的可观察行为测试：抽块/映射纯函数离线；渲染用例按 skip 披露。"""

from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
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
    def test_effective_theme_maps_dark_chart_text_from_governed_roles(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.render.theme import compute_effective_theme
        theme = compute_effective_theme(AssetResolver().resolve(
            "builtin:theme:tech-dark-mode")["data"])
        variables, _ = build_theme_variables(theme)
        xy = variables["xyChart"]
        self.assertEqual(xy["titleColor"], theme["colors"]["text"])
        for role in ("xAxisLabelColor", "yAxisLabelColor", "xAxisLineColor", "yAxisLineColor"):
            self.assertEqual(xy[role], theme["colors"]["muted"])

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

    def test_dark_xychart_maps_data_labels_and_legend_text(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.render.theme import compute_effective_theme
        theme = compute_effective_theme(AssetResolver().resolve(
            "builtin:theme:tech-dark-mode")["data"])
        variables, _ = build_theme_variables(theme)
        self.assertEqual(variables["xyChart"]["dataLabelColor"], theme["colors"]["text"])
        self.assertEqual(variables["xyChart"]["legendTextColor"], theme["colors"]["text"])

    def test_xy_options_are_bounded(self):
        from leo_ppt_generator.render.chart import render_mermaid_svg
        for options in ({"height": 100}, {"width": True}, {"label_size": 97},
                        {"unknown": 5}, {"data_labels": "yes"}):
            with self.subTest(options=options), self.assertRaises(RenderError) as ctx:
                render_mermaid_svg("xychart-beta\n bar [1]", chart_options=options)
            self.assertEqual(ctx.exception.reason_code, "render_data_invalid")


class RenderChartBrowser(browser_test_case()):
    def test_cli_xy_options_reach_artifact_and_invalid_height_is_blocked(self):
        import json
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp) / "chart.mmd", Path(tmp) / "chart.svg"
            source.write_text('xychart-beta\n x-axis [A, B]\n bar [30, 40]', encoding="utf-8")
            args = [sys.executable, "-m", "leo_ppt_generator", "render", "chart",
                    "--code-file", str(source), "--out", str(out), "--chart-width", "660",
                    "--chart-height", "228", "--label-size", "22", "--data-labels"]
            result = subprocess.run(args, cwd=SKILL_ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            receipt = json.loads(out.with_name("chart.svg.render.json").read_text())
            self.assertEqual(receipt["chart_options"], {
                "width": 660, "height": 228, "label_size": 22, "data_labels": True})
            self.assertEqual(ET.fromstring(out.read_text()).get("viewBox"), "0 0 660 228")
            args[args.index("228")] = "100"
            result = subprocess.run(args, cwd=SKILL_ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            self.assertIn("render_data_invalid", result.stdout + result.stderr)

    def test_compact_multiseries_chart_preserves_values_sizes_and_theme(self):
        from leo_ppt_generator.render.chart import render_mermaid_svg
        code = 'xychart-beta\n x-axis [A, B, C]\n y-axis "降幅 %" 0 --> 100\n bar [0, 40, 60]\n bar [20, 50, 70]'
        svg = render_mermaid_svg(code, theme_variables={"xyChart": {
            "backgroundColor": "#111111", "dataLabelColor": "#EEEEEE"}},
            chart_options={"width": 660, "height": 228, "label_size": 22, "data_labels": True})
        root = ET.fromstring(svg)
        self.assertEqual(root.get("viewBox"), "0 0 660 228")
        ns = {"s": "http://www.w3.org/2000/svg"}
        for i, expected in enumerate((["0", "40", "60"], ["20", "50", "70"])):
            labels = root.findall(f'.//s:g[@class="bar-plot-{i}"]/s:text', ns)
            self.assertEqual([node.text for node in labels], expected)
            self.assertTrue(all(node.get("font-size") == "22" for node in labels))
            self.assertTrue(all(node.get("fill") == "#EEEEEE" for node in labels))
        ticks = root.findall('.//s:g[@class="left-axis"]/s:g[@class="label"]/s:text', ns)
        self.assertGreaterEqual(len(ticks), 2)
        self.assertLess(len(ticks), 11)
        self.assertIn("0", [node.text for node in ticks])
        self.assertIn("100", [node.text for node in ticks])

    def test_xy_options_reject_non_xy_diagrams(self):
        from leo_ppt_generator.render.chart import render_mermaid_svg
        with self.assertRaises(RenderError) as error:
            render_mermaid_svg("flowchart LR\n A-->B", chart_options={"width": 660})
        self.assertIn("require xychart", str(error.exception))

    def test_main_diagrams_preserve_chinese_labels_without_html(self):
        cases = {
            "flowchart": ('flowchart LR\n A["中文标题<br/>第二行"] -->|"责任人确认"| B["验收 80%+"]',
                          ("中文标题", "第二行", "责任人确认", "验收 80%+")),
            "graph": ("graph TD\n A[htmlLabels] --> B[完成]", ("htmlLabels", "完成")),
            "mindmap": ("mindmap\n  root((系统))\n    接入\n    交付", ("系统", "接入", "交付")),
            "sequence": ("sequenceDiagram\n participant A as 用户\n participant B as 系统\n A->>B: 请求\n B-->>A: 完成",
                         ("用户", "系统", "请求", "完成")),
            "state": ("stateDiagram-v2\n [*] --> 待办\n 待办 --> 完成", ("待办", "完成")),
            "class": ("classDiagram\n class Order {\n +submit()\n }\n Order --> Receipt", ("Order", "Receipt", "submit")),
            "er": ("erDiagram\n ORDER ||--|{ ITEM : contains", ("ORDER", "ITEM", "contains")),
            "pie": ('pie title 收益\n "直接节省" : 80\n "其他" : 20', ("收益", "直接节省", "其他")),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, (code, labels) in cases.items():
                with self.subTest(dialect=name):
                    source, out = Path(tmp) / f"{name}.mmd", Path(tmp) / f"{name}.svg"
                    source.write_text(code, encoding="utf-8")
                    render_chart(dialect="mermaid", code_file=source, out=out)
                    svg = out.read_text(encoding="utf-8")
                    self.assertNotIn("<foreignObject", svg)
                    text = "".join(ET.fromstring(svg).itertext())
                    for label in labels:
                        self.assertIn(label, text)

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
