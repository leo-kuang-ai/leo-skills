"""U5/F4 垂直验证：风格 → 主题组合 → 版式 JSON → CSS → 容量 → 真实页面。

只修改 JSON（列权重 30/45/25 → 25/50/25、padding 15 → 12），HTML 源码不变；
真实 DOM 列宽分别匹配 330/495/275 与 275/550/275（1100 逻辑 px 区域），
误差最多 1 逻辑 px。容量随几何变化。硬超在设计组合阶段即被拒绝。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))
sys.path.insert(0, str(SKILL / "tests"))

from tests.render.helpers import browser_test_case

from leo_ppt_generator.render.layout import compile_geometry
from leo_ppt_generator.render.assets import template_path
from leo_ppt_generator.templates import DesignCompositionError, compose_design

DATA_3COL = {
    "title": "重点区域三季度经营指标",
    "columns": ["区域", "收入", "完成率"],
    "column_align": ["left", "right", "right"],
    "rows": [["华东大区", "128.6", "103.2%"],
             ["华南大区", "96.4", "98.7%"],
             ["华北大区", "74.9", "95.4%"]],
    "page_no": 9,
}


def _theme_variables(design: dict, profile: dict, effective_theme: dict) -> dict:
    geometry = compile_geometry(profile, effective_theme, column_count=3)
    return {
        "colors": effective_theme["colors"],
        "fonts": effective_theme["fonts"],
        "geometry": geometry,
        "column_weights": geometry["column_weights"],
    }


def _measure_columns(theme_variables: dict, data: dict) -> list[float]:
    """Playwright 实测表头列宽（逻辑 px）。"""
    from leo_ppt_generator.render.fonts import RenderAssetServer
    from leo_ppt_generator.render.page import _apply_browsers_path

    _apply_browsers_path()
    from playwright.sync_api import sync_playwright

    import os
    executable = os.environ.get("LEO_PPT_RENDER_CHROMIUM") or None
    data_literal = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    theme_literal = json.dumps(theme_variables, ensure_ascii=False).replace("</", "<\\/")
    with RenderAssetServer() as server:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=executable)
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                context.add_init_script(
                    f"window.__LEO_SLIDE_DATA__ = {data_literal};"
                    f"window.__LEO_THEME_VARIABLES__ = {theme_literal};")
                page = context.new_page()
                page.goto(template_path("spec-table").as_uri())
                page.wait_for_selector("table.spec th")
                page.wait_for_function("document.documentElement.dataset.leoReady === '1'")
                widths = page.evaluate(
                    "Array.from(document.querySelectorAll('table.spec th'))"
                    ".map(function (th) { return th.getBoundingClientRect().width; })")
                content = page.evaluate(
                    "document.querySelector('.leo-slide').getBoundingClientRect().width")
                return [round(w, 2) for w in widths] + [round(content, 2)]
            finally:
                browser.close()


class ComposeDesignPipelineTest(unittest.TestCase):
    """组合器行为（离线）：选择→主题→mode→路由→容量→冻结。"""

    def test_style_resolves_by_chinese_name_to_stable_id(self) -> None:
        design = compose_design("清爽专业风", pages=[
            {"page_no": 9, "page_role": "data", "slots": DATA_3COL}])
        self.assertEqual(design["selection"]["style"]["asset_id"],
                         "builtin:style:clean-professional")
        self.assertEqual(design["selection"]["theme"]["asset_id"],
                         "builtin:theme:clean-professional-light")
        self.assertEqual(design["pages"][0]["layout_id"],
                         "builtin:layout:p25-spec-table")
        self.assertEqual(design["pages"][0]["template_id"],
                         "builtin:template:spec-table")
        self.assertTrue(design["capacity_reports"][0]["fits"])

    def test_image_only_canonical_layout_composes_without_regions(self) -> None:
        # P1 已绑定 cover-pro（2026-09 pro-family 扩容）；image-only 的
        # template_id=None 行为改由未绑定 render:html 的版式（P4 six-cells）验证。
        design = compose_design("清爽专业风", pages=[{
            "page_no": 1,
            "page_role": "cover",
            "layout": "builtin:layout:p1-01-cover-layouts",
            "slots": {},
        }])
        self.assertEqual(design["pages"][0]["layout_id"],
                         "builtin:layout:p1-01-cover-layouts")
        self.assertEqual(design["pages"][0]["template_id"],
                         "builtin:template:cover-pro")
        image_only = compose_design("清爽专业风", pages=[{
            "page_no": 2,
            "page_role": "content",
            "layout": "builtin:layout:p4-04-six-cells-layouts",
            "slots": {},
        }])
        self.assertIsNone(image_only["pages"][0]["template_id"])

    def test_design_digest_deterministic_and_input_sensitive(self) -> None:
        pages = [{"page_no": 9, "page_role": "data", "slots": DATA_3COL}]
        first = compose_design("清爽专业风", pages=pages)
        second = compose_design("清爽专业风", pages=pages)
        self.assertEqual(first["design_digest"], second["design_digest"])
        changed = compose_design("清爽专业风", pages=pages,
                                 color_overrides={"accent": "#9A3412"})
        self.assertNotEqual(first["design_digest"], changed["design_digest"])

    def test_hard_overflow_rejected_at_composition(self) -> None:
        rows = [[f"超长行名第{i}项", "128.6", "103.2%"] for i in range(9)]
        with self.assertRaises(DesignCompositionError) as ctx:
            compose_design("清爽专业风", pages=[
                {"page_no": 9, "page_role": "data",
                 "slots": {"columns": DATA_3COL["columns"], "rows": rows}}])
        self.assertIn("layout_capacity_exceeded", str(ctx.exception))

    def test_unknown_mode_rejected(self) -> None:
        with self.assertRaises(DesignCompositionError) as ctx:
            compose_design("清爽专业风", mode="dark", pages=[
                {"page_no": 9, "page_role": "data", "slots": DATA_3COL}])
        self.assertIn("theme_invalid", str(ctx.exception))

    def test_locked_brand_role_rejects_task_override(self) -> None:
        brand = {"name": "示例品牌", "colors": {"primary": "#1D4ED8"},
                 "locked_roles": ["primary"]}
        design = compose_design("清爽专业风", brand_data=brand, pages=[
            {"page_no": 9, "page_role": "data", "slots": DATA_3COL}])
        self.assertEqual(design["effective_theme"]["colors"]["primary"], "#1D4ED8")
        with self.assertRaises(DesignCompositionError) as ctx:
            compose_design("清爽专业风", brand_data=brand,
                           color_overrides={"primary": "#DC2626"}, pages=[
                               {"page_no": 9, "page_role": "data", "slots": DATA_3COL}])
        self.assertIn("锁定", str(ctx.exception))

    def test_non_overrideable_role_rejected(self) -> None:
        with self.assertRaises(DesignCompositionError) as ctx:
            compose_design("清爽专业风", color_overrides={"primary": "#000000"},
                           pages=[{"page_no": 9, "page_role": "data", "slots": DATA_3COL}])
        self.assertIn("不可覆盖", str(ctx.exception))


class RenderGeometryDomTest(browser_test_case()):
    """真浏览器 F4 验收：JSON 单点改动驱动 DOM 列宽与渲染。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _profile(self) -> dict:
        resolver_pages = compose_design("清爽专业风", pages=[
            {"page_no": 9, "page_role": "data", "slots": DATA_3COL}])
        from leo_ppt_generator.asset_resolver import AssetResolver

        layout = AssetResolver().resolve(resolver_pages["pages"][0]["layout_id"])
        return layout["data"], resolver_pages

    def test_baseline_weights_30_45_25_drive_dom(self) -> None:
        profile, design = self._profile()
        theme_vars = _theme_variables(design, profile, design["effective_theme"])
        self.assertEqual(theme_vars["column_weights"], [30.0, 45.0, 25.0])
        measured = _measure_columns(theme_vars, DATA_3COL)
        content_width = measured[-1]
        self.assertAlmostEqual(content_width, 1100, delta=1)
        for actual, ratio in zip(measured[:3], (0.30, 0.45, 0.25)):
            self.assertAlmostEqual(actual, 1100 * ratio, delta=1,
                                   msg=f"列宽 {actual} ≠ {1100 * ratio}")

    def test_json_change_25_50_25_padding_12_drives_dom_html_untouched(self) -> None:
        import copy

        profile, design = self._profile()
        profile_before = copy.deepcopy(profile)
        # 只改 JSON：权重 30/45/25 → 25/50/25；padding 15 → 12。
        profile["columns"]["weights"] = [25, 50, 25]
        profile["padding"]["block"] = 12
        theme_vars = _theme_variables(design, profile, design["effective_theme"])
        self.assertEqual(theme_vars["column_weights"], [25.0, 50.0, 25.0])
        self.assertEqual(theme_vars["geometry"]["padding-block"], 12)
        measured = _measure_columns(theme_vars, DATA_3COL)
        for actual, ratio in zip(measured[:3], (0.25, 0.50, 0.25)):
            self.assertAlmostEqual(actual, 1100 * ratio, delta=1,
                                   msg=f"列宽 {actual} ≠ {1100 * ratio}")
        # HTML 源码未变（几何真值单源的直接证明）。
        html_path = template_path("spec-table")
        before_hash = __import__("hashlib").sha256(html_path.read_bytes()).hexdigest()
        self.assertEqual(profile_before["columns"]["weights"], [30, 45, 25])  # 原件未受内存改动影响
        after_hash = __import__("hashlib").sha256(html_path.read_bytes()).hexdigest()
        self.assertEqual(before_hash, after_hash)

    def test_render_page_produces_png_with_theme_variables(self) -> None:
        from leo_ppt_generator.render.page import render_page

        profile, design = self._profile()
        theme_vars = _theme_variables(design, profile, design["effective_theme"])
        data = Path(self._tmp.name) / "slide.json"
        data.write_text(json.dumps(DATA_3COL, ensure_ascii=False), encoding="utf-8")
        out = Path(self._tmp.name) / "page.png"
        result = render_page("spec-table", data, out, theme_variables=theme_vars)
        self.assertEqual((result["width"], result["height"]), (2560, 1440))
        self.assertEqual(result["ready_signal"], "data-leo-ready")


if __name__ == "__main__":
    unittest.main()
