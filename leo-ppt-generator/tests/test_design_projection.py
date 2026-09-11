"""U4/F3：设计投影——两路线共享冻结设计，治理值不入内容。

硬验收：双适配器输入同 design_digest；适配器不再读活动设计资产；同输入
确定性；治理值（分数/许可/路径/来源标记）不泄漏进投影。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.templates import (
    DesignProjectionError,
    compose_design,
    project_design_to_prompt,
)
from leo_ppt_generator.render.layout import compile_geometry

PAGES = [{"page_no": 9, "page_role": "data", "layout": "P25",
          "slots": {"columns": ["指标", "数值", "同比"],
                    "rows": [["营收", "12.4亿", "+9.8%"],
                             ["利润", "3.1亿", "+14.2%"],
                             ["现金流", "4.7亿", "+41.0%"]]}}]


def _design():
    return compose_design("金融藏青风", pages=PAGES)


class DesignProjectionTest(unittest.TestCase):
    def test_two_lanes_consume_same_frozen_design_digest(self) -> None:
        design = _design()
        # HTML 路线：layout 编译几何；image 路线：prompt 投影。
        geometry = compile_geometry(
            {"regions": {"content": {"x": 90, "y": 170, "width": 1100, "height": 470}},
             "layout_type": "table", "columns": {"count": 3, "weights": [30, 45, 25]},
             "canvas": {"width": 1280, "height": 720, "units": "logical-px"},
             "renderer_support": {"render:html": "builtin:template:spec-table"},
             "entity": "layout-profile", "asset_id": "builtin:layout:p25-spec-table",
             "name": "规格参数表", "page_role": "data",
             "slots": {}, "font_size_refs": {}, "padding": {"block": 15, "inline": 18}},
            design["effective_theme"], column_count=3)
        prompt = project_design_to_prompt(design, {"page_no": 9})
        self.assertEqual(prompt["design_digest"], design["design_digest"])
        self.assertEqual(geometry["column_weights"], [30.0, 45.0, 25.0])
        # 两条路线的有效值同源：prompt 颜色来自 effective_theme。
        self.assertIn("primary=#1E3A8A", prompt["colors"])

    def test_projection_is_deterministic(self) -> None:
        design = _design()
        first = project_design_to_prompt(design, {"page_no": 9})
        second = project_design_to_prompt(
            compose_design("金融藏青风", pages=PAGES), {"page_no": 9})
        self.assertEqual(
            json.dumps(first, sort_keys=True, ensure_ascii=False),
            json.dumps(second, sort_keys=True, ensure_ascii=False))

    def test_projection_carries_only_effective_values_not_prose(self) -> None:
        prompt = project_design_to_prompt(_design(), {"page_no": 9})
        encoded = json.dumps(prompt, ensure_ascii=False)
        # 有效值是编译后的 HEX 指令，不是 brief 里的散文色板。
        self.assertIn("=#", encoded)
        self.assertNotIn("professional blue", encoded)
        # 负面约束完整传递（关键约束不丢）。
        self.assertTrue(any("来源" in c for c in prompt["negative_constraints"]))

    def test_governance_values_do_not_leak_into_projection(self) -> None:
        design = _design()
        design["selection"]["source_map"] = {"primary": "theme"}
        design["authored_digest"] = "deadbeef" * 8
        prompt = project_design_to_prompt(design, {"page_no": 9})
        encoded = json.dumps(prompt, ensure_ascii=False)
        for forbidden in ("source_map", "authored_digest", "curation",
                          "evidence", "verified", "license", "reviewer"):
            self.assertNotIn(forbidden, encoded)

    def test_projection_rejects_non_frozen_input(self) -> None:
        with self.assertRaises(DesignProjectionError):
            project_design_to_prompt({"entity": "something-else"}, {"page_no": 1})

    def test_page_outside_design_rejected(self) -> None:
        with self.assertRaises(DesignProjectionError):
            project_design_to_prompt(_design(), {"page_no": 99})

    def test_snapshot_reusable_offline(self) -> None:
        """移机后快照可恢复：冻结记录序列化→反序列化仍可投影（不访问库）。"""
        import copy

        design = _design()
        frozen = json.loads(json.dumps(design, ensure_ascii=False))
        prompt = project_design_to_prompt(frozen, {"page_no": 9})
        self.assertTrue(prompt["design_digest"])


if __name__ == "__main__":
    unittest.main()
