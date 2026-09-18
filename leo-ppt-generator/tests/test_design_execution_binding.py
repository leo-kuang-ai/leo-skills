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
        from tests.test_expression_pipeline import transaction_inputs
        cls.payload, cls.resolver, cls.context, cls.pages = transaction_inputs()
        cls.pack = cls.payload["pack"]
        cls.page = cls.pack["pages"][0]
        cls.binding = cls.payload["bindings"]["render:html"][cls.page["page_id"]]

    def design(self):
        return templates.compose_design(self.context["style"]["asset_id"], pages=self.pages,
            selection=self.payload["lane_selections"]["render:html"], design_context=self.context, resolver=self.resolver)

    def test_frozen_design_carries_context_and_template(self):
        design = self.design()
        self.assertEqual(design["design_context_digest"], self.binding["context_digest"])
        self.assertEqual(design["pages"][0]["template_id"], self.binding["template_id"])

    def test_binding_digests_stable_across_recompile(self):
        rebound = precompile_binding(self.page, self.context, self.binding["layout_id"],
            content_digest=self.pack["content_digest"], numbers=self.pack["numbers"], resolver=self.resolver, qualification_purpose="validation")
        for key in ("expression_binding_digest", "materialization_binding_digest"):
            self.assertEqual(self.binding[key], rebound[key])

    def test_compose_is_deterministic_and_refuses_missing_selection(self):
        self.assertEqual(self.design(), self.design())
        with self.assertRaises(ValueError):
            templates.compose_design(self.context["style"]["asset_id"], pages=self.pages, resolver=self.resolver)

    def test_freshness_verification_is_exact_for_frozen_inputs(self):
        self.assertEqual(templates.verify_design_freshness(self.design(), self.resolver)["status"], "fresh")


if __name__ == "__main__":
    unittest.main()

class DualBindingDigestTests(unittest.TestCase):
    def test_digest_helpers_are_lane_split(self):
        from leo_ppt_generator.content_projection import compute_expression_binding_digest, compute_materialization_binding_digest
        from copy import deepcopy
        from tests.test_expression_pipeline import transaction_inputs
        payload, _, _, _ = transaction_inputs()
        binding = deepcopy(next(iter(payload["bindings"]["render:html"].values())))
        e = compute_expression_binding_digest(binding)
        binding["backend"] = "image"
        self.assertEqual(e, compute_expression_binding_digest(binding))
        self.assertNotEqual(compute_materialization_binding_digest({**binding, "backend":"image"}), compute_materialization_binding_digest({**binding, "backend":"render:html"}))

class DualBindingVerificationTests(unittest.TestCase):
    def test_missing_expression_digest_fails_closed(self):
        from leo_ppt_generator.content_projection import verify_dual_binding_digests, ProjectionError
        binding = {"page_id":"p", "item_ids":["i"], "content_digest":"c", "compiler":"x", "layout_id":"l", "template_id":"t", "backend":"render:html", "slot_map":{}, "context_digest":"ctx", "materialization_binding_digest":"x"}
        with self.assertRaises(ProjectionError): verify_dual_binding_digests(binding)
