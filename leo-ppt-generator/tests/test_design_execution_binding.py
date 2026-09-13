#!/usr/bin/env python3
"""dashi 集成 K2/K4、U4 设计-执行绑定一致性测试。

覆盖：候选绑定与冻结设计消费同一上下文快照（context_digest 相等）；
设计冻结前后绑定摘要一致（同输入重编译不漂移）；resolved-design 携带
design_context_digest；页面解析仍由既有组合器权威完成（不绕开 compose_design）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
for entry in (str(RUNTIME_SRC), str(SKILL_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from leo_ppt_generator import templates  # noqa: E402
from leo_ppt_generator.content_pack import compile_content_pack  # noqa: E402
from leo_ppt_generator.content_projection import precompile_binding  # noqa: E402

MASTER = """# 母版 v1
confirmation: confirmed（测试基线）

## S1 内容
page_id: pg-11111111
角色：流程·路径
argument_role: 论据
- 标题：交付节奏与指标
- 要点 1：环比 +18%
- 要点 2：净利率 12%
视觉行：要点1→KPI 塔 要点2→指标卡
- 备注：口播 20 秒

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 18% | S1 | Q3 财报 | 环比 | 2026Q3 | 百分点 | 引用 | yes | 2026-10-28 |
"""

STYLE = "finance-navy"


class DesignExecutionBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = compile_content_pack(MASTER, master_path="content/deck-master-v1.md")
        cls.page = cls.pack["pages"][0]
        cls.context = templates.resolve_design_context(STYLE)
        cls.binding = precompile_binding(
            cls.page, cls.context, "body-basic",
            content_digest=cls.pack["content_digest"],
            numbers=cls.pack["numbers"])
        assert cls.binding["eligibility"]["qualified"], cls.binding["eligibility"]

    def test_frozen_design_carries_context_digest(self):
        design = templates.compose_design(
            STYLE, pages=[{"page_no": 1, "page_role": "content",
                          "layout": "body-basic", "slots": {}}])
        self.assertEqual(design["design_context_digest"],
                         self.context["context_digest"])
        self.assertEqual(design["pages"][0]["template_id"],
                         "builtin:template:body-basic")

    def test_binding_and_design_share_context(self):
        design = templates.compose_design(
            STYLE, pages=[{"page_no": 1, "page_role": "content",
                          "layout": "body-basic", "slots": {}}])
        self.assertEqual(self.binding["context_digest"],
                         design["design_context_digest"])

    def test_binding_digest_stable_across_recompile(self):
        again = templates.resolve_design_context(STYLE)
        rebound = precompile_binding(
            self.page, again, "body-basic",
            content_digest=self.pack["content_digest"],
            numbers=self.pack["numbers"])
        self.assertEqual(self.binding["binding_digest"], rebound["binding_digest"])

    def test_design_digest_changes_only_with_real_inputs(self):
        kwargs = {"pages": [{"page_no": 1, "page_role": "content",
                             "layout": "body-basic", "slots": {}}]}
        design = templates.compose_design(STYLE, **kwargs)
        same = templates.compose_design(STYLE, **kwargs)
        self.assertEqual(design["design_digest"], same["design_digest"])
        variant = templates.compose_design(
            STYLE, font_overrides={"body.size": 20}, **kwargs)
        self.assertNotEqual(design["design_digest"], variant["design_digest"])

    def test_freshness_verification_still_owned_by_composer(self):
        design = templates.compose_design(
            STYLE, pages=[{"page_no": 1, "page_role": "content",
                          "layout": "body-basic", "slots": {}}])
        report = templates.verify_design_freshness(design)
        self.assertIn(report.get("status"), {"fresh", "stale"})


if __name__ == "__main__":
    unittest.main()

class DualBindingDigestTests(unittest.TestCase):
    def test_digest_helpers_are_lane_split(self):
        from leo_ppt_generator.content_projection import compute_expression_binding_digest, compute_materialization_binding_digest
        binding = {"page_id":"p", "item_ids":["i"], "content_digest":"c", "compiler":"x", "layout_id":"l", "template_id":"t", "backend":"render:html", "slot_map":{}, "context_digest":"ctx"}
        e = compute_expression_binding_digest(binding)
        binding["backend"] = "image"
        self.assertEqual(e, compute_expression_binding_digest(binding))
        self.assertNotEqual(compute_materialization_binding_digest({**binding, "backend":"image"}), compute_materialization_binding_digest({**binding, "backend":"render:html"}))

class DualBindingVerificationTests(unittest.TestCase):
    def test_missing_expression_digest_fails_closed(self):
        from leo_ppt_generator.content_projection import verify_dual_binding_digests, ProjectionError
        binding = {"page_id":"p", "item_ids":["i"], "content_digest":"c", "compiler":"x", "layout_id":"l", "template_id":"t", "backend":"render:html", "slot_map":{}, "context_digest":"ctx", "materialization_binding_digest":"x"}
        with self.assertRaises(ProjectionError): verify_dual_binding_digests(binding)
