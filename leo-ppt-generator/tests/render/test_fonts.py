"""主题字体必须实际可加载，文件存在与 fonts.ready 不代替加载验证。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.render.helpers import browser_test_case
from leo_ppt_generator.render.errors import RenderError
from leo_ppt_generator.render.fonts import theme_font_assets
from leo_ppt_generator.render.page import render_page


class FontContractTests(unittest.TestCase):
    def test_unknown_theme_family_fails(self):
        with self.assertRaises(RenderError) as error:
            theme_font_assets({"fonts": {"body": {"family": "Unregistered Leo Font"}}})
        self.assertEqual(error.exception.reason_code, "render_font_missing")


class FontLoadingTests(browser_test_case()):
    def test_serif_theme_fonts_load_in_chromium(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.render.theme import compute_effective_theme
        theme = compute_effective_theme(AssetResolver().require("editorial-serif-light", kind="theme")["data"])
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data.json"
            data.write_text(json.dumps({"title": "中文衬线字体加载", "subtitle": "离线字体证据"}), encoding="utf-8")
            result = render_page("cover-pro", data, Path(tmp) / "out.png", theme_variables=theme)
            self.assertIn(("Noto Serif SC", 700), result["fonts_checked"])

    def test_corrupt_font_does_not_silently_fall_back(self):
        theme = {"fonts": {"title": {"family": "Broken Test Font", "weight": 700}}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "broken.otf").write_bytes(b"not a font")
            data = root / "data.json"
            data.write_text('{"title":"加载失败"}', encoding="utf-8")
            css = '@font-face { font-family:"Broken Test Font"; font-weight:700; src:url("/leo-fonts/broken.otf"); }'
            with patch("leo_ppt_generator.render.page.theme_font_assets", return_value=([root], css)):
                with self.assertRaises(RenderError) as error:
                    render_page("cover-pro", data, root / "out.png", theme_variables=theme)
            self.assertEqual(error.exception.reason_code, "render_font_missing")
            self.assertFalse((root / "out.png").exists())
