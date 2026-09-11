"""模板入口必须受 catalog 与可信根约束。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from leo_ppt_generator.render.assets import template_path, template_http_entry


class TemplateResolutionTests(unittest.TestCase):
    def test_http_rejects_direct_unregistered_html_paths(self):
        from leo_ppt_generator.render.fonts import RenderAssetServer
        from urllib.request import urlopen
        from urllib.error import HTTPError
        with RenderAssetServer() as server:
            with self.assertRaises(HTTPError) as ctx:
                urlopen(server.url("body-basic/page.html"))
            self.assertEqual(ctx.exception.code, 404)
            with urlopen(server.url("body-basic.html")) as response:
                self.assertEqual(response.status, 200)

    def test_canonical_prefix_does_not_bypass_slug_validation(self):
        for value in ("builtin:template:..", "builtin:template:.hidden", "builtin:template:"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                template_path(value)

    def test_missing_http_entry_returns_none(self):
        self.assertIsNone(template_http_entry("not-a-known-template.html"))

    def test_partial_bundle_cannot_shadow_registered_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "template-library/canonical/templates/body-basic"
            fake.mkdir(parents=True)
            (fake / "page.html").write_text("<script>throw new Error('shadow')</script>")
            with patch.dict("os.environ", {"LEO_PPT_BUNDLE": tmp}):
                self.assertNotEqual(template_path("body-basic"), fake / "page.html")

    def test_template_symlink_must_stay_in_trusted_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library"
            directory = library / "canonical/templates/test"
            directory.mkdir(parents=True)
            external = root / "external.html"
            external.write_text("<html>external</html>")
            (directory / "page.html").symlink_to(external)
            resolved = {"path": str(directory / "template.json"),
                        "trusted_root": str(library), "data": {"lane": "render:html"}}
            with patch("leo_ppt_generator.asset_resolver.AssetResolver") as resolver, \
                 patch("leo_ppt_generator.render.assets._canonical_template_dirs", return_value=[directory.parent]):
                resolver.return_value.resolve.return_value = resolved
                with self.assertRaises(ValueError):
                    template_path("test")


if __name__ == "__main__":
    unittest.main()
