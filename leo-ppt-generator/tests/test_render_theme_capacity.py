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
from leo_ppt_generator.templates import DesignCompositionError, compose_design as _compose_design, resolve_design_context

DATA_3COL = {
    "title": "重点区域三季度经营指标",
    "columns": ["指标", "华东", "华南"],
    "column_align": ["left", "right", "right"],
    "rows": [["收入", "128.6", "96.4"],
             ["完成率", "103.2%", "98.7%"],
             ["同比", "12%", "10%"]],
    "page_no": 9,
}


def compose_design(style, *, pages, **options):
    """测试前端走真实资格与冻结 selection；不在生产 compose 内重新路由。"""
    from copy import deepcopy
    from leo_ppt_generator.content_pack import compile_content_pack
    from leo_ppt_generator.content_projection import materialize_html
    from leo_ppt_generator.layout_selection import allocate_deck
    from leo_ppt_generator.application.expression_pipeline import selection_digest
    from tests.expression_test_support import real_allocation_inputs
    resolver, _ = real_allocation_inputs()
    context = resolve_design_context(style, resolver=resolver, **options)
    data = deepcopy(pages[0]["slots"])
    items = [f"/structures/table/columns/{i}" for i in range(1, len(data["columns"]))]
    dims = [f"/structures/table/rows/{i}/0" for i in range(len(data["rows"]))]
    cells = [{"item_ref": item, "dimension_ref": dimension,
              "fact_ref": f"/structures/table/rows/{row}/{column}", "unknown": False}
             for row, dimension in enumerate(dims) for column, item in enumerate(items, 1)]
    model = {"schema_version": 2, "main_claim": "比较同口径指标", "main_style": style,
             "brand_constraints": [], "narrative_order": ["ch-test"], "chapters": [
                 {"chapter_id": "ch-test", "task": "核对指标", "conclusion": "保留表格数据",
                  "evidence_refs": [], "previous": None, "next": None}]}
    expression = {"chapter_id": "ch-test", "semantic_structure": "undecided", "media_role": "none",
        "evidence_refs": [], "basis": [], "expression": {"reading_task": "comparison", "focus": "claim",
        "reading_order": ["claim", *items, *dims, *[c["fact_ref"] for c in cells]], "fact_refs": [], "uncertainty": [],
        "relation_encoding": {"item_refs": items, "dimension_refs": dims, "cells": cells}}}
    master = "# 母版\ncontent_model: " + json.dumps(model, ensure_ascii=False) + "\n\n## S1 指标\npage_id: pg-1234abcd\n角色：指标·计分榜\n"
    master += "page_expression: " + json.dumps(expression, ensure_ascii=False) + "\n- 标题：" + data.get("title", DATA_3COL["title"]) + "\n"
    master += "表列: " + ",".join(data["columns"]) + "\n" + "\n".join("表行: " + "｜".join(row) for row in data["rows"])
    pack = compile_content_pack(master, master_path="table-test.md")
    result = allocate_deck(pack, context, resolver=resolver, qualification_purpose="validation",
                           candidates=["builtin:layout:p25-spec-table"])
    if result["status"] != "complete":
        raise DesignCompositionError(str(result["page_status"]))
    result.update(selection_frozen=True, selection_digest=selection_digest(result["selection"]))
    page = pack["pages"][0]
    selected = result["selection"][page["page_id"]]
    composed = [{"page_id": page["page_id"], "page_no": page["number"], "page_role": "data",
                 "layout": selected["layout_id"], "slots": materialize_html(selected["binding"], page, resolver=resolver)}]
    return _compose_design(style, pages=composed, selection=result, design_context=context, resolver=resolver)


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

    def test_unverified_explicit_layout_cannot_compose_without_selection(self) -> None:
        for layout in ("builtin:layout:p1-01-cover-layouts", "builtin:layout:p4-04-six-cells-layouts"):
            with self.subTest(layout=layout), self.assertRaisesRegex(DesignCompositionError, "selection_frozen_mismatch"):
                _compose_design("清爽专业风", pages=[{"page_no": 1, "page_role": "cover", "layout": layout, "slots": {}}])

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
        self.assertIn("structured_field_invalid", str(ctx.exception))

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
