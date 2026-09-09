"""SVG 静态子集策略的拒绝边界测试。"""

from __future__ import annotations

import unittest

from leo_ppt_generator.render.svg_policy import SvgPolicyError, sanitize_chart_output, sanitize_svg


class SvgPolicyTest(unittest.TestCase):
    def test_static_svg_is_preserved(self):
        source = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#fff"/></svg>'
        output = sanitize_svg(source)
        self.assertIn("<rect", output)
        self.assertIn('fill="#fff"', output)

    def test_static_style_attribute_is_allowed(self):
        source = '<svg xmlns="http://www.w3.org/2000/svg" style="max-width: 100%;"><rect width="10" height="10"/></svg>'
        self.assertIn('style="max-width: 100%;"', sanitize_svg(source))

    def test_script_and_event_attributes_are_rejected(self):
        cases = (
            '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><rect onload="alert(1)"/></svg>',
        )
        for source in cases:
            with self.subTest(source=source), self.assertRaises(SvgPolicyError):
                sanitize_svg(source)

    def test_external_references_and_css_urls_are_rejected(self):
        cases = (
            '<svg xmlns="http://www.w3.org/2000/svg"><use href="https://evil.example/x.svg#x"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><use href="javascript:alert(1)"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><use href="file:///etc/passwd"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><style>@import url(https://evil.example/a.css);</style></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(data:image/svg+xml;base64,abc)"/></svg>',
        )
        for source in cases:
            with self.subTest(source=source), self.assertRaises(SvgPolicyError):
                sanitize_svg(source)

    def test_fragment_href_is_allowed(self):
        source = '<svg xmlns="http://www.w3.org/2000/svg"><use href="#local"/></svg>'
        self.assertIn('href="#local"', sanitize_svg(source))

    def test_entity_and_foreign_object_are_rejected(self):
        entity = '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg">&xxe;</svg>'
        with self.assertRaises(SvgPolicyError):
            sanitize_svg(entity)
        with self.assertRaises(SvgPolicyError):
            sanitize_chart_output(
                '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><div>bad</div></foreignObject></svg>',
                dialect="mermaid",
            )

    def test_mermaid_html_labels_marker_is_rejected(self):
        source = '<svg xmlns="http://www.w3.org/2000/svg"><text>htmlLabels</text></svg>'
        with self.assertRaises(SvgPolicyError):
            sanitize_chart_output(source, dialect="mermaid")


if __name__ == "__main__":
    unittest.main()
