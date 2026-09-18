"""D1-T3 render page 的可观察行为测试（浏览器用例按 skip 纪律显式披露）。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.render.helpers import browser_test_case

from leo_ppt_generator.render.errors import RenderError
from leo_ppt_generator.render.page import render_page

SLIDE_DATA = {
    "title": "确定性渲染测试页",
    "bullets": ["模板合同六条", "ready 信号主门", "HTTP 字体禁 file://"],
    "page_no": 7,
}


class RenderPageOfflineContract(unittest.TestCase):
    def test_missing_template_reports_stable_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "slide.json"
            data.write_text(json.dumps(SLIDE_DATA), encoding="utf-8")
            with self.assertRaises(RenderError) as ctx:
                render_page("no-such-template", data, Path(tmp) / "out.png")
            self.assertEqual(ctx.exception.reason_code, "render_template_not_found")

    def test_invalid_template_id_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "slide.json"
            data.write_text(json.dumps(SLIDE_DATA), encoding="utf-8")
            with self.assertRaises(RenderError) as ctx:
                render_page("../escape", data, Path(tmp) / "out.png")
            self.assertEqual(ctx.exception.reason_code, "render_template_not_found")

    def test_canonical_template_asset_id_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "slide.json"
            data.write_text(json.dumps(SLIDE_DATA), encoding="utf-8")
            # Browser execution is covered elsewhere; this assertion reaches
            # template resolution before Playwright is required.
            from leo_ppt_generator.render.assets import template_path
            self.assertEqual(
                template_path("builtin:template:body-basic"),
                template_path("body-basic"),
            )

    def test_invalid_slide_data_reports_render_data_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "slide.json"
            data.write_text("not-json{", encoding="utf-8")
            with self.assertRaises(RenderError) as ctx:
                render_page("body-basic", data, Path(tmp) / "out.png")
            self.assertEqual(ctx.exception.reason_code, "render_data_invalid")

    def test_chart_svg_is_sanitized_before_browser_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "slide.json"
            data.write_text(
                json.dumps({
                    "title": "图表页",
                    "chart_svg": '<svg xmlns="http://www.w3.org/2000/svg"><rect onload="alert(1)"/></svg>',
                }),
                encoding="utf-8",
            )
            with self.assertRaises(RenderError) as ctx:
                render_page("body-basic", data, Path(tmp) / "out.png")
            self.assertEqual(ctx.exception.reason_code, "render_data_invalid")

    def test_duplicate_or_nonfinite_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "slide.json"
            for payload in ('{"title":"x","title":"y"}', '{"title":"x","page_no":1e999}',
                            '{"title":"x","page_no":NaN}', '{"title":"x","hidden":42}'):
                with self.subTest(payload=payload):
                    data.write_text(payload, encoding="utf-8")
                    with self.assertRaises(RenderError) as ctx:
                        render_page("body-basic", data, Path(tmp) / "out.png")
                    self.assertEqual(ctx.exception.reason_code, "render_data_invalid")


class RenderPageBrowser(browser_test_case()):
    """真浏览器用例：环境缺 chromium 时 skip 并披露（skip ≠ pass）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "slide.json"
        self.data.write_text(json.dumps(SLIDE_DATA), encoding="utf-8")

    def test_render_page_accepts_canonical_asset_id(self):
        out = Path(self._tmp.name) / "asset-id.png"
        result = render_page("builtin:template:body-basic", self.data, out)
        self.assertEqual(result["backend"], "render:html")
        self.assertTrue(out.is_file())

    def test_render_page_writes_provenance_sidecar_with_template_hash(self):
        out = Path(self._tmp.name) / "slide.png"
        result = render_page("body-basic", self.data, out)
        self.assertEqual(result["backend"], "render:html")
        self.assertEqual((result["width"], result["height"]), (2560, 1440))
        self.assertEqual(result["device_scale_factor"], 2)
        self.assertEqual(result["ready_signal"], "data-leo-ready")
        self.assertTrue(out.is_file())
        # PNG 头断言（不信 CLI 参数）
        from PIL import Image

        with Image.open(out) as image:
            self.assertEqual(image.size, (2560, 1440))
        # provenance sidecar：template_sha256 必须匹配磁盘模板
        sidecar = json.loads(
            Path(result["sidecar"]).read_text(encoding="utf-8")
        )
        self.assertEqual(sidecar["kind"], "render_provenance")
        self.assertEqual(sidecar["out_sha256"], result["out_sha256"])
        from leo_ppt_generator.render.assets import template_path
        from leo_ppt_generator.storage import sha256_file

        self.assertEqual(sidecar["template_sha256"], sha256_file(template_path("body-basic")))

    def test_same_input_twice_pixel_diff_within_tolerance(self):
        # HTML/playwright 链路只承诺像素 diff ≤ 0.1%（不承诺位级）。
        out_a = Path(self._tmp.name) / "a.png"
        out_b = Path(self._tmp.name) / "b.png"
        render_page("body-basic", self.data, out_a)
        render_page("body-basic", self.data, out_b)
        from PIL import Image, ImageChops

        a = Image.open(out_a).convert("RGB")
        b = Image.open(out_b).convert("RGB")
        diff = ImageChops.difference(a, b).convert("L")
        changed = sum(diff.histogram()[1:]) / (a.width * a.height)
        self.assertLessEqual(changed, 0.001, f"pixel diff {changed:.4%} > 0.1% tolerance")

    def test_size_tier_1280_matches_png_header(self):
        out = Path(self._tmp.name) / "web.png"
        result = render_page("body-basic", self.data, out, size=(1280, 720))
        self.assertEqual(result["device_scale_factor"], 1)
        from PIL import Image

        with Image.open(out) as image:
            self.assertEqual(image.size, (1280, 720))


if __name__ == "__main__":
    unittest.main()
