"""八个增强模板：冻结内容、主题、几何到浏览器的端到端回归。"""
import copy
import json
import os
import tempfile
from pathlib import Path

from tests.test_pro_template_contracts import KPI_DATA, master
from tests.render.helpers import browser_test_case
from leo_ppt_generator import templates
from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.content_pack import compile_content_pack
from leo_ppt_generator.content_projection import precompile_binding, materialize_html
from leo_ppt_generator.render.fonts import RenderAssetServer
from leo_ppt_generator.render.layout import compile_geometry
from leo_ppt_generator.render.page import render_page, _OVERFLOW_CHECK_JS
from leo_ppt_generator.render.theme import compute_effective_theme
from leo_ppt_generator.render.errors import RenderError

CASES = {
    "cover-pro": ("P1", "封面", {"kicker": "季度评审", "subtitle": "规模、成本与质量的共同改善",
                                         "arch_hint": "盘点投入 → 验证成效", "footer_left": "平台团队", "footer_right": "内部资料"}),
    "chain-flow": ("P2", "流程·路径", {
        "nodes": [{"name": s, "tag": "责任人", "desc": "核对输入与验收结果"} for s in ("范围确认", "方案评审", "试点验证", "正式交付", "持续复盘")],
        "side_cards": [{"key": "边界", "value": "按统一业务口径验收"}, {"key": "证据", "value": "记录数据来源与期间"}],
        "stats": [{"label": "覆盖团队", "value": "12"}, {"label": "交付阶段", "value": "5"}]}),
    "compare-pro": ("P8", "对比·多维", {"sides": [
        {"label": "原方案", "title": "分散管理", "points": ["资源独立分配", "指标分别统计", "人工逐项验证"]},
        {"label": "新方案", "title": "统一治理", "points": ["资源集中调度", "口径统一对齐", "证据自动归档"]}],
        "bottom": "在一致边界内比较成本与收益"}),
    "quote-pro": ("P9", "结尾", {"quote_em": "成效", "source": "季度复盘结论",
        "route": [{"name": "统一口径", "desc": "明确来源与期间"}, {"name": "复核成果", "desc": "保留原始证据"}, {"name": "推广实践", "desc": "持续跟踪效果"}],
        "bound": "后续结果以实际验收为准"}),
    "timeline-pro": ("P11", "趋势·时间线", {
        "steps": [{"no": str(i + 1), "name": s, "desc": "产出经确认的交付记录", "note": "阶段验收"} for i, s in enumerate(("盘点", "设计", "试点", "迁移", "运营"))],
        "bottom": [{"strong": "检查点", "text": "保留验证证据"}, {"strong": "完成条件"}]}),
    "cards-stat": ("P16", "小结·回顾", {
        "cards": [{"label": s, "claim": "以业务结果衡量", "stat": {"value": str(i + 10), "unit": "项", "note": "同一统计期间"}} for i, s in enumerate(("效率", "质量", "成本", "交付", "稳定", "协作"))],
        "bottom": "六项指标分别验证，不混用统计口径"}),
    "kpi-stat": ("P20", "指标·计分榜", KPI_DATA),
    "table-pro": ("P21", "指标·计分榜", {
        "columns": ["指标", "原值", "当前", "变化", "单位"],
        "rows": [["应用", "334", "75", "259", "个"], ["CPU", "1268", "554.5", "713.5", "核"],
                 ["内存", "1893.11", "934.63", "958.48", "GB"], ["团队", "8", "12", "4", "个"],
                 ["用例", "20", "30", "10", "项"], ["任务", "30", "40", "10", "项"]],
        "footnote": "示例输入，业务数值与财务推导需单独验收"}),
}


class ProTemplateRenderingTests(browser_test_case()):
    def test_eight_templates_preserve_content_and_consume_theme_geometry(self):
        from playwright.sync_api import sync_playwright
        from leo_ppt_generator.render.chart import render_mermaid_svg, build_theme_variables

        resolver = AssetResolver()
        context = templates.resolve_design_context("finance-navy")
        with tempfile.TemporaryDirectory(prefix="leo-pro-") as tmp:
            output = Path(os.environ.get("LEO_PPT_TEST_RENDER_OUTPUT") or tmp)
            output.mkdir(parents=True, exist_ok=True)
            for theme_id in ("finance-navy-light", "tech-dark-mode"):
                theme = compute_effective_theme(resolver.require(theme_id, kind="theme")["data"])
                chart_theme, _ = build_theme_variables(theme)
                chart = render_mermaid_svg('xychart-beta\n x-axis ["应用", "CPU", "内存"]\n y-axis "降幅 %" 0 --> 100\n bar [77.5, 56.3, 50.6]', theme_variables=chart_theme,
                                          chart_options={"width": 660, "height": 228, "label_size": 22, "data_labels": True})
                for name, (layout, role, fields) in CASES.items():
                    with self.subTest(template=name, theme=theme_id):
                        fields = copy.deepcopy(fields)
                        if name == "kpi-stat":
                            fields.update(chart_svg=chart, chart_title="各指标相对原值降幅（示例）")
                        pack = compile_content_pack(master(fields, role), master_path="fixture.md")
                        page_data = pack["pages"][0]
                        binding = precompile_binding(page_data, context, layout, content_digest=pack["content_digest"])
                        self.assertTrue(binding["eligibility"]["qualified"], binding["eligibility"])
                        data = materialize_html(binding, page_data)
                        profile = resolver.require(layout, kind="layout")["data"]
                        variables = {**theme, "geometry": compile_geometry(profile, theme)}
                        first_region = next(iter(profile["regions"]))
                        variables["geometry"][first_region + "-x"] += 3
                        stem = output / f"{name}-{theme_id}"
                        source = stem.with_suffix(".json")
                        source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                        result = render_page(name, source, stem.with_suffix(".png"), size=(1280, 720), theme_variables=variables)
                        self.assertEqual(result["ready_signal"], "data-leo-ready")
                        self.assertEqual(result["overflow_check"], "pass")
                        with RenderAssetServer() as server, sync_playwright() as pw:
                            browser = pw.chromium.launch(headless=True, executable_path=os.environ.get("LEO_PPT_RENDER_CHROMIUM") or None)
                            try:
                                page = browser.new_page(viewport={"width": 1280, "height": 720})
                                page.add_init_script("window.__LEO_SLIDE_DATA__=" + json.dumps(data) + ";window.__LEO_THEME_VARIABLES__=" + json.dumps(variables))
                                page.goto(server.url(name + ".html?leo_render=1"))
                                page.wait_for_selector("html[data-leo-ready='1']", state="attached")
                                measured = page.evaluate("""() => ({
                                    text:document.body.innerText,
                                    title:getComputedStyle(document.querySelector('.title, .quote')).fontSize,
                                    regions:Array.from(document.querySelectorAll('[data-leo-region]')).filter(e=>e.getClientRects().length).map(e=>({name:e.dataset.leoRegion,x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})),
                                    bg:getComputedStyle(document.body).backgroundColor
                                })""")
                                self.assertEqual(measured["title"], str(theme["fonts"]["title"]["size"]) + "px")
                                bg = theme["colors"]["background"]
                                self.assertEqual(measured["bg"], f"rgb({int(bg[1:3],16)}, {int(bg[3:5],16)}, {int(bg[5:7],16)})")
                                for region in measured["regions"]:
                                    self.assertEqual(region["x"], variables["geometry"][region["name"] + "-x"])
                                    self.assertEqual(region["y"], variables["geometry"][region["name"] + "-y"])
                                self.assertNotIn("undefined", measured["text"])
                                self.assertNotIn("独立应用集群", measured["text"])
                                for text in _visible_strings(data):
                                    self.assertIn(text, measured["text"])
                                self.assertEqual(page.evaluate(_OVERFLOW_CHECK_JS), [])
                            finally:
                                browser.close()

    def test_direct_render_rejects_malformed_objects_and_invented_quote(self):
        for name, data in (("kpi-stat", {"title": "指标", "kpis": ["75"]}),
                           ("quote-pro", {"quote": "原文", "quote_em": "编造文本"})):
            with self.subTest(template=name), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "data.json"
                source.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(RenderError) as error:
                    render_page(name, source, Path(tmp) / "out.png")
                self.assertEqual(error.exception.reason_code, "render_data_invalid")


def _visible_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _visible_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in ("chart_svg", "kind", "quote_em"):
                yield from _visible_strings(item)
