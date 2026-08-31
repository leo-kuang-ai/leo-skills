"""D3 SVG→PNG 栅格化的可观察行为测试：位级确定性 / 双路径探测 / 离线字体。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from leo_ppt_generator.render import raster
from leo_ppt_generator.render.errors import RenderError

SAMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200" '
    'viewBox="0 0 400 200"><rect width="400" height="200" fill="#ffffff"/>'
    '<text x="20" y="60" font-size="24" fill="#111111">resvg 2560 档</text>'
    '<rect x="20" y="90" width="360" height="20" fill="#1a9850"/></svg>'
)


class RasterizeDeterminism(unittest.TestCase):
    def test_rasterize_svg_is_bitwise_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            svg = Path(tmp) / "chart.svg"
            svg.write_text(SAMPLE_SVG, encoding="utf-8")
            first = raster.rasterize_svg(svg_path=svg, out_path=Path(tmp) / "a.png")
            second = raster.rasterize_svg(svg_path=svg, out_path=Path(tmp) / "b.png")
            self.assertEqual(first["out_sha256"], second["out_sha256"])
            self.assertEqual(first["width"], 2560)
            self.assertGreater(first["height"], 0)
            self.assertTrue(first["rasterizer"].startswith("resvg"))

    def test_svg_string_and_path_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RenderError) as ctx:
                raster.rasterize_svg(
                    svg_string=SAMPLE_SVG,
                    svg_path=Path(tmp) / "x.svg",
                    out_path=Path(tmp) / "out.png",
                )
            self.assertEqual(ctx.exception.reason_code, "render_data_invalid")

    def test_missing_svg_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RenderError) as ctx:
                raster.rasterize_svg(
                    svg_path=Path(tmp) / "missing.svg", out_path=Path(tmp) / "out.png"
                )
            self.assertEqual(ctx.exception.reason_code, "render_data_invalid")

    def test_offline_font_files_are_passed_not_system_fonts(self):
        # 离线确定性：font_dirs 存在时 font_files 显式计数（不静默用系统字体）。
        from leo_ppt_generator.render.assets import fonts_dir

        if not (fonts_dir().is_dir() and any(fonts_dir().iterdir())):
            self.skipTest("render-fonts 未铺设（离线字体目录为空）")
        with tempfile.TemporaryDirectory() as tmp:
            svg = Path(tmp) / "c.svg"
            svg.write_text(SAMPLE_SVG, encoding="utf-8")
            result = raster.rasterize_svg(svg_path=svg, out_path=Path(tmp) / "c.png")
            self.assertGreater(result["font_files"], 0)


class RasterizerAvailability(unittest.TestCase):
    def test_rasterize_reports_unavailable_when_both_paths_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            svg = Path(tmp) / "c.svg"
            svg.write_text(SAMPLE_SVG, encoding="utf-8")
            with mock.patch.object(raster, "_python_bindings_available", return_value=False), \
                 mock.patch.object(raster, "_rasterize_node", side_effect=raster.RasterizerUnavailable("node unavailable")):
                with self.assertRaises(RenderError) as ctx:
                    raster.rasterize_svg(svg_path=svg, out_path=Path(tmp) / "out.png")
            self.assertEqual(ctx.exception.reason_code, "rasterizer_unavailable")

    def test_status_reports_both_paths(self):
        status = raster.rasterizer_status()
        self.assertIn("python_bindings", status)
        self.assertIn("node_subprocess", status)


if __name__ == "__main__":
    unittest.main()
