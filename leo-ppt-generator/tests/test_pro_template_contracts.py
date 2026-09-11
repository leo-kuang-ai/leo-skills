"""增强模板的内容合同与真实渲染回归。"""
import copy
import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator import templates
from leo_ppt_generator.content_pack import ContentPackError, compile_content_pack
from leo_ppt_generator.content_projection import materialize_html, precompile_binding


def master(fields, role="指标·计分榜"):
    return ("# 母版 v1\nconfirmation: confirmed（测试基线）\n\n"
            "## S1 数据\npage_id: pg-1234abcd\n角色：" + role + "\n"
            "argument_role: 论据\n- 标题：资源投入与成效\n"
            "结构数据: " + json.dumps(fields, ensure_ascii=False) + "\n")


KPI_DATA = {"kpis": [
    {"label": "应用", "value": "75", "unit": "个", "before": "原值 334"},
    {"label": "CPU", "value": "554.5", "unit": "核", "before": "原值 1268"},
    {"label": "内存", "value": "934.63", "unit": "GB", "before": "原值 1893.11"},
    {"label": "效率", "value": "80%+", "before": "独立统计口径"}],
    "dual": [{"kind": "direct", "tag": "直接节省", "hkd": "107.7 万 HKD/年",
              "usd": "示例输入，未经业务验收"},
             {"kind": "net", "tag": "净节省", "hkd": "20.2 万 HKD/年",
              "usd": "示例输入，未经业务验收"}],
    "footnote": "两口径不相加、不互替"}


class StructuredTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = templates.resolve_design_context("finance-navy")

    def binding(self, fields, layout="P20", role="指标·计分榜", text=None):
        pack = compile_content_pack(text or master(fields, role), master_path="master.md")
        page = pack["pages"][0]
        binding = precompile_binding(page, self.context, layout,
                                     content_digest=pack["content_digest"], numbers=pack["numbers"])
        return page, binding

    def test_kpi_fields_preserve_objects_and_display_values(self):
        page, binding = self.binding(KPI_DATA)
        self.assertTrue(binding["eligibility"]["qualified"], binding["eligibility"])
        data = materialize_html(binding, page)
        for key, value in KPI_DATA.items():
            self.assertEqual(data[key], value)
        data["kpis"][0]["value"] = "changed"
        self.assertEqual(page["structures"]["fields"]["kpis"][0]["value"], "75")

    def test_bad_shape_missing_value_and_excess_cards_are_rejected(self):
        cases = [{"kpis": ["75", "554.5"]},
                 {"kpis": [{"label": "缺数值"}]},
                 {"kpis": KPI_DATA["kpis"] * 2},
                 {**KPI_DATA, "unrendered_fact": "隐藏数字 999"}]
        for fields in cases:
            with self.subTest(fields=fields):
                _, binding = self.binding(fields)
                self.assertFalse(binding["eligibility"]["qualified"])

    def test_explicit_title_cannot_replace_claim(self):
        _, binding = self.binding({**KPI_DATA, "title": "替换论点"})
        self.assertFalse(binding["eligibility"]["qualified"])

    def test_duplicate_or_malformed_structure_is_not_silently_dropped(self):
        for text in (master(KPI_DATA) + "结构数据: {}\n",
                     master(KPI_DATA).replace('"kpis":', '"kpis": [], "kpis":'),
                     master(KPI_DATA).replace('"kpis":', '"kpis": NaN, "extra":'),
                     master(KPI_DATA).replace('"kpis":', '"kpis": 1e999, "extra":')):
            with self.subTest(text=text):
                with self.assertRaises(ContentPackError):
                    compile_content_pack(text, master_path="master.md")

    def test_svg_attributes_and_style_values_are_not_display_evidence(self):
        from leo_ppt_generator.template_inputs import display_texts
        value = {"chart_svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 999 500"><style>.a {fill:#334455}</style><text>金额 <tspan>42 万元</tspan></text></svg>',
                 "deco_filled": 777, "dual": [{"kind": "888", "hkd": "20.2 万"}]}
        self.assertEqual(list(display_texts(value)), ["金额 42 万元", "20.2 万"])

    def test_quote_type_errors_and_unknown_fields_are_validation_failures(self):
        from leo_ppt_generator.template_inputs import validate_template_data
        manifest = {"input_fields": [{"name": "quote", "type": "string"},
                                      {"name": "quote_em", "type": "string"}]}
        self.assertTrue(validate_template_data(manifest, {"quote": "原文", "quote_em": 42}))
        self.assertTrue(validate_template_data(manifest, {"quote": "原文", "hidden": "42"}))

    def test_unbound_table_does_not_satisfy_number_coverage(self):
        text = (master({}, "流程·路径").replace("结构数据: {}", "- 要点 1：投入下降\n- 要点 2：统一口径")
                + "表列: 指标,数值\n表行: 隐藏金额｜999 万元\n\n"
                "## 数字登记表\n| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| 999 万元 | S1 | 财报 | 合并 | 2026 | 元 | 引用 | yes | 2026-09-11 |\n")
        _, binding = self.binding({}, "body-basic", text=text)
        self.assertTrue(any("number_coverage_missing" in f
                            for f in binding["eligibility"]["hard_failures"]))
