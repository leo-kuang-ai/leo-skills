#!/usr/bin/env python3
"""dashi 集成 K6/U6：四类高价值任务结构的真实承载验证。

指标及基准差异（spec-table 表列/表行）/ 趋势及事件注释（timeline steps）/
决策矩阵（compare 对照侧）/ 流程及责任分工（body-basic bullets）——每类：
母版 fixture → 内容包 → 硬资格 → 物化真实模板 data；负例：缺结构标记回
母版、表行列数不对齐编译拒绝、换主题不改业务内容与结构身份。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = PKG_ROOT / "runtime" / "src"
for entry in (str(RUNTIME_SRC), str(PKG_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from leo_ppt_generator import templates  # noqa: E402
from leo_ppt_generator.content_pack import (  # noqa: E402
    ContentPackError,
    compile_content_pack,
)
from leo_ppt_generator.content_projection import (  # noqa: E402
    materialize_html,
    precompile_binding,
)
from leo_ppt_generator.layout_selection import structure_fingerprint  # noqa: E402

FIXTURES = PKG_ROOT / "tests" / "fixtures" / "dashi-integration"
STYLE = "finance-navy"


def _compile(name: str) -> dict:
    return compile_content_pack(
        (FIXTURES / name).read_text(encoding="utf-8"),
        master_path=f"content/{name}", master_revision="v1")


def _bind(pack: dict, page_id: str, layout: str, context=None):
    context = context or templates.resolve_design_context(STYLE)
    page = next(p for p in pack["pages"] if p["page_id"] == page_id)
    return precompile_binding(page, context, layout,
                              content_digest=pack["content_digest"],
                              numbers=pack["numbers"]), page


class MetricBaselineTests(unittest.TestCase):
    def test_spec_table_carries_columns_rows(self):
        pack = _compile("metrics-baseline-master.md")
        binding, page = _bind(pack, "pg-a1b2c3d4", "p25-spec-table")
        self.assertTrue(binding["eligibility"]["qualified"],
                        binding["eligibility"]["hard_failures"])
        data = materialize_html(binding, page)
        self.assertEqual(data["columns"],
                         ["指标", "本季 2026Q3", "上季 2026Q2", "年度基准"])
        self.assertEqual(len(data["rows"]), 3)
        self.assertEqual(data["rows"][0], ["营收", "1.24 亿元", "1.10 亿元", "4.8 亿元"])
        # 基准期间显式可见（不同期间不合并）。
        self.assertTrue(any("2026Q3" in c for c in data["columns"])
                        or any("2026Q3" in c for row in data["rows"] for c in row))

    def test_mismatched_table_rows_rejected_at_compile(self):
        text = (FIXTURES / "metrics-baseline-master.md").read_text(encoding="utf-8")
        broken = text.replace("表行: 留存率｜90%｜84%｜85%", "表行: 留存率｜90%｜84%")
        with self.assertRaisesRegex(ContentPackError, "单元格数"):
            compile_content_pack(broken, master_path="content/x.md")

    def test_table_without_markers_rejected_at_binding(self):
        text = (FIXTURES / "metrics-baseline-master.md").read_text(encoding="utf-8")
        stripped = "\n".join(
            ln for ln in text.splitlines()
            if not ln.startswith(("表列:", "表行:")))
        pack = compile_content_pack(stripped, master_path="content/x.md")
        binding, _page = _bind(pack, "pg-a1b2c3d4", "p25-spec-table")
        self.assertFalse(binding["eligibility"]["qualified"])


class TrendEventsTests(unittest.TestCase):
    def test_timeline_carries_steps_from_points(self):
        pack = _compile("trend-events-master.md")
        binding, page = _bind(pack, "pg-b1b2c3d4", "timeline")
        self.assertTrue(binding["eligibility"]["qualified"],
                        binding["eligibility"]["hard_failures"])
        data = materialize_html(binding, page)
        self.assertEqual(data["steps"][:2], ["2026Q1 六周", "2026Q2 四周"])
        self.assertEqual(data["title"], "交付周期连续三季缩短")


class DecisionMatrixTests(unittest.TestCase):
    def test_compare_carries_two_sides(self):
        pack = _compile("decision-matrix-master.md")
        binding, page = _bind(pack, "pg-c1b2c3d4", "compare")
        self.assertTrue(binding["eligibility"]["qualified"],
                        binding["eligibility"]["hard_failures"])
        data = materialize_html(binding, page)
        self.assertEqual([s["label"] for s in data["sides"]],
                         ["自建路线", "采购路线"])

    def test_matrix_without_sides_rejected_not_guessed(self):
        text = (FIXTURES / "decision-matrix-master.md").read_text(encoding="utf-8")
        stripped = "\n".join(
            ln for ln in text.splitlines() if not ln.startswith("对照侧:"))
        pack = compile_content_pack(stripped, master_path="content/x.md")
        binding, _page = _bind(pack, "pg-c1b2c3d4", "compare")
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertTrue(any("对照侧" in f
                            for f in binding["eligibility"]["hard_failures"]))


class ProcessOwnershipTests(unittest.TestCase):
    def test_body_basic_carries_stage_points(self):
        pack = _compile("process-ownership-master.md")
        binding, page = _bind(pack, "pg-d1b2c3d4", "body-basic")
        self.assertTrue(binding["eligibility"]["qualified"],
                        binding["eligibility"]["hard_failures"])
        data = materialize_html(binding, page)
        self.assertEqual(len(data["bullets"]), 3)
        self.assertIn("平台组", data["bullets"][0])


class ThemeIndependenceTests(unittest.TestCase):
    def test_reskin_keeps_business_content_and_structure(self):
        pack = _compile("decision-matrix-master.md")
        dark = templates.resolve_design_context("tech-dark")
        light = templates.resolve_design_context(STYLE)
        page = next(p for p in pack["pages"] if p["page_id"] == "pg-c1b2c3d4")
        b1 = precompile_binding(page, light, "compare",
                                content_digest=pack["content_digest"],
                                numbers=pack["numbers"])
        b2 = precompile_binding(page, dark, "compare",
                                content_digest=pack["content_digest"],
                                numbers=pack["numbers"])
        self.assertEqual(b1["slot_map"], b2["slot_map"])
        self.assertEqual(b1["item_ids"], b2["item_ids"])
        d1 = materialize_html(b1, page)
        d2 = materialize_html(b2, page)
        self.assertEqual(d1, d2)  # 业务内容与结构不随主题漂移
        # 结构指纹与主题无关（声明级，来自 canonical layout profile）。
        from leo_ppt_generator.asset_resolver import AssetResolver
        profile = AssetResolver().resolve("builtin:layout:compare")["data"]
        self.assertTrue(structure_fingerprint(profile).startswith("fp-"))


class TemplateContractNoRegressionTests(unittest.TestCase):
    def test_all_templates_lint_clean(self):
        """模板合同 lint 全绿守恒（2026-09 扩容 8 个 pro-family 模板后
        由固定数量断言改为全量 ERROR=0 守恒；新模板走 README 八步流程接入）。"""
        import subprocess
        script = PKG_ROOT / "scripts" / "lint_template_contract.py"
        proc = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True,
            encoding="utf-8", cwd=str(PKG_ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ERROR=0", proc.stdout)

    def test_pro_family_pcode_bindings(self):
        """pro-family 模板与 P 码版式双向绑定守恒。"""
        import json
        bindings = {
            "cover-pro": "p1-01-cover-layouts",
            "chain-flow": "p2-02-vertical-timeline-layouts",
            "compare-pro": "p8-08-duo-compare-layouts",
            "quote-pro": "p9-09-closing-manifesto-layouts",
            "timeline-pro": "p11-11-horizontal-timeline-layouts",
            "cards-stat": "p16-16-multi-card-brief-layouts",
            "kpi-stat": "p20-20-stacked-kpi-ledger-layouts",
            "table-pro": "p21-21-tech-spec-sheet-layouts",
        }
        for tpl, layout_slug in bindings.items():
            tj = json.loads((PKG_ROOT / "template-library/canonical/templates" / tpl / "template.json").read_text(encoding="utf-8"))
            self.assertIn(f"builtin:layout:{layout_slug}", tj.get("layout_profiles", []), tpl)
            lj = json.loads((PKG_ROOT / "template-library/canonical/layouts" / layout_slug / "layout.json").read_text(encoding="utf-8"))
            self.assertEqual(lj["renderer_support"]["render:html"], f"builtin:template:{tpl}", layout_slug)


if __name__ == "__main__":
    unittest.main()
