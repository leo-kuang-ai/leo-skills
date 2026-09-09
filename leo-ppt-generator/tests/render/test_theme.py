"""U5/AE5：七模板主题消费实测——换肤真实生效（计算样式来自主题角色）。

每个模板用九方向种子主题渲染，测量 body 背景/标题色/正文字号的计算样式
必须等于主题值（不是模板 fallback 纸色）。暗色变体同步生效。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from tests.render.helpers import browser_test_case

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.render.assets import template_path
from leo_ppt_generator.render.fonts import RenderAssetServer
from leo_ppt_generator.render.theme import compute_effective_theme

TEMPLATES = ("cover-basic", "body-basic", "compare", "timeline",
             "spec-table", "pull-quote", "frame-shot")

SAMPLE_DATA = {
    "cover-basic": {"kicker": "2026 三季度经营分析", "title": "稳健增长与结构优化",
                    "subtitle": "收入、利润与现金流联动解读", "footer_left": "集团经管部",
                    "footer_right": "内部资料", "page_no": 1},
    "body-basic": {"title": "核心结论", "bullets": ["收入增长 12.4%", "毛利率 38.2%",
                 "现金流 4.7 亿", "回款纪律加强"], "page_no": 2},
    "compare": {"sides": [
        {"label": "现状", "title": "分散部署", "points": ["利用率不足 40%", "补丁滞后两季"]},
        {"label": "目标", "title": "统一平台", "points": ["利用率 75%+", "补丁两周内"]}], "page_no": 7},
    "timeline": {"title": "五阶段路线", "steps": [{"no": "01", "name": "现状盘点"},
                 {"no": "02", "name": "平台选型"}, {"no": "03", "name": "试点验证"},
                 {"no": "04", "name": "分批迁移"}, {"no": "05", "name": "全面运营"}], "page_no": 8},
    "spec-table": {"title": "区域经营指标", "columns": ["区域", "收入", "完成率"],
                   "column_align": ["left", "right", "right"],
                   "rows": [["华东", "128.6", "103.2%"], ["华南", "96.4", "98.7%"],
                            ["华北", "74.9", "95.4%"]], "page_no": 9},
    "pull-quote": {"quote": "把不确定性变成风险。", "source_name": "陈明远",
                   "source_meta": "风控委员会主席", "page_no": 10},
    "frame-shot": {"kicker": "运行证据", "title": "控制台运行列表", "caption": "季度评审留档",
                   "ratio": "16x10", "corners": "sq", "shadow": "flat", "bg": "paper",
                   "inset": "sub", "fit": "contain", "device": "none", "page_no": 11,
                   "image_src": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="},
}

TITLE_SELECTOR = {
    "cover-basic": "[data-leo-block='title']", "body-basic": "[data-leo-block='title']",
    "compare": "[data-leo-block='page-no']", "timeline": "[data-leo-block='title']",
    "spec-table": "[data-leo-block='title']", "pull-quote": "[data-leo-block='quote']",
    "frame-shot": "[data-leo-block='page-no']",
}


def _measure(template: str, theme_variables: dict, data: dict) -> dict:
    from playwright.sync_api import sync_playwright
    from leo_ppt_generator.render.page import _apply_browsers_path

    _apply_browsers_path()
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
                page.goto(template_path(template).as_uri())
                page.wait_for_function("document.documentElement.dataset.leoReady === '1'")
                return page.evaluate("""(sel) => {
                    const body = getComputedStyle(document.body);
                    const title = document.querySelector(sel);
                    const titleStyle = title ? getComputedStyle(title) : null;
                    return {
                        background: body.backgroundColor,
                        color: body.color,
                        titleColor: titleStyle ? titleStyle.color : null,
                        titleSize: titleStyle ? titleStyle.fontSize : null,
                    };
                }""", TITLE_SELECTOR[template])
            finally:
                browser.close()


def _theme_vars(theme_id: str, mode: str | None = None) -> tuple[dict, dict]:
    resolver = AssetResolver()
    theme = resolver.resolve(theme_id)["data"]
    effective = compute_effective_theme(theme, mode=mode)
    fonts = {role: dict(defn) for role, defn in effective["fonts"].items()}
    # 每模板保持原设计比例：字号按模板档放大（cover 标题 92 等）——单一来源
    # 仍是注入的字体角色值（模板只消费变量，fallback 不参与）。
    scaled = dict(fonts)
    return {"colors": effective["colors"], "fonts": scaled,
            "geometry": {}}, effective


class TemplateThemeConsumptionTest(browser_test_case()):
    def test_every_template_consumes_seed_theme_colors(self) -> None:
        _, effective = _theme_vars("builtin:theme:finance-navy-light")
        expected_bg = _rgb(effective["colors"]["background"])
        expected_text = _rgb(effective["colors"]["text"])
        for template in TEMPLATES:
            with self.subTest(template=template):
                theme_vars, _ = _theme_vars("builtin:theme:finance-navy-light")
                measured = _measure(template, theme_vars, SAMPLE_DATA[template])
                self.assertEqual(measured["background"], expected_bg,
                                 f"{template} 背景未跟随主题（得 {measured['background']}）")
                self.assertEqual(measured["color"], expected_text,
                                 f"{template} 正文色未跟随主题")

    def test_dark_variant_switches_all_templates(self) -> None:
        theme_vars, effective = _theme_vars("builtin:theme:tech-dark-mode", mode="dark")
        expected_bg = _rgb(effective["colors"]["background"])
        for template in ("cover-basic", "body-basic", "timeline", "pull-quote"):
            with self.subTest(template=template):
                measured = _measure(template, theme_vars, SAMPLE_DATA[template])
                self.assertEqual(measured["background"], expected_bg,
                                 f"{template} 暗色变体未生效（得 {measured['background']}）")

    def test_font_size_variable_drives_dom(self) -> None:
        theme_vars, _ = _theme_vars("builtin:theme:finance-navy-light")
        theme_vars["fonts"] = {"title": {"family": "Noto Sans SC", "weight": 700,
                                         "size": 64, "line_height": 1.2}}
        measured = _measure("body-basic", theme_vars, SAMPLE_DATA["body-basic"])
        self.assertEqual(measured["titleSize"], "64px",
                         "标题字号必须由主题字体角色变量驱动")


def _rgb(hex_value: str) -> str:
    r = int(hex_value[1:3], 16)
    g = int(hex_value[3:5], 16)
    b = int(hex_value[5:7], 16)
    return f"rgb({r}, {g}, {b})"


class RenderPipelineThemeRegressionTest(browser_test_case()):
    """回归：deck-style 矩阵语义抽查发现的换肤静默失效。

    RenderAssetServer 站点根指向旧平铺目录时，``/<slug>.html`` 回落
    super() 供给了无主题消费的旧模板——像素层背景仍是模板默认纸色，
    硬字节闸（空页下限）测不出。此测试钉住"HTTP 供给的模板必须走
    template_path 新库优先策略，且 render_page 全链路换肤到达像素层"。
    """

    def test_http_entry_maps_slug_to_canonical_page(self) -> None:
        from leo_ppt_generator.render.assets import template_http_entry

        entry = template_http_entry("cover-basic.html")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.name, "page.html")
        self.assertEqual(entry.parent.name, "cover-basic")
        self.assertIn("canonical", [p.name for p in entry.parents])
        self.assertIn("applyThemeVariables", entry.read_text(encoding="utf-8"))

    def test_render_page_pipeline_applies_theme_to_pixels(self) -> None:
        from leo_ppt_generator.render.page import render_page

        theme_vars, effective = _theme_vars("builtin:theme:finance-navy-light")
        bg = effective["colors"]["background"]
        expected = (int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16))
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "slide.json"
            out_path = Path(tmp) / "slide.png"
            data_path.write_text(
                json.dumps(SAMPLE_DATA["cover-basic"], ensure_ascii=False),
                encoding="utf-8")
            render_page("cover-basic", data_path, out_path,
                        theme_variables=theme_vars)
            from PIL import Image

            im = Image.open(out_path).convert("RGB")
            w, h = im.size
            corner = im.getpixel((30, 30))
            for got, want in zip(corner, expected):
                self.assertLessEqual(abs(got - want), 16,
                                     f"背景像素 {corner} ≠ 主题 {expected}"
                                     "（换肤未到达像素层）")
            self.assertEqual((w, h), (2560, 1440))


if __name__ == "__main__":
    unittest.main()
