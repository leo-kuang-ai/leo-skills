"""U5/F4：layout-profile 合同与几何编译（离线，无浏览器）。

JSON 是几何唯一真值：列权重/padding/区域 → CSS 变量；容量随主题字号联动；
输入列数不匹配声明报不支持，不硬套比例。
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.render.layout import (
    CapacityOverflowError,
    LayoutProfileError,
    compile_geometry,
    estimate_table_capacity,
    require_capacity,
    validate_profile,
)
from leo_ppt_generator.render.theme import compute_effective_theme

PROFILE_PATH = (SKILL / "template-library/canonical/layouts/p25-spec-table/layout.json")
THEME_PATH = (SKILL / "template-library/canonical/themes/clean-professional-light/theme.json")


def load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def load_effective_theme() -> dict:
    theme = json.loads(THEME_PATH.read_text(encoding="utf-8"))
    return compute_effective_theme(theme)


class LayoutProfileContractTest(unittest.TestCase):
    def test_real_profile_valid(self) -> None:
        validate_profile(load_profile())

    def test_image_only_profile_may_omit_regions(self) -> None:
        profile = load_profile()
        profile["renderer_support"] = {"render:html": None, "image": "指导性构图"}
        profile.pop("regions")
        validate_profile(profile)

    def test_html_profile_requires_regions(self) -> None:
        profile = load_profile()
        profile.pop("regions")
        with self.assertRaises(LayoutProfileError):
            validate_profile(profile)

    def test_canvas_units_are_part_of_the_contract(self) -> None:
        profile = load_profile()
        profile["canvas"]["units"] = "px"
        with self.assertRaises(LayoutProfileError):
            validate_profile(profile)

    def test_canvas_must_be_logical_1280x720(self) -> None:
        profile = load_profile()
        profile["canvas"] = {"width": 1920, "height": 1080, "units": "logical-px"}
        with self.assertRaises(LayoutProfileError):
            validate_profile(profile)

    def test_region_outside_canvas_rejected(self) -> None:
        profile = load_profile()
        profile["regions"]["content"]["width"] = 1300
        with self.assertRaises(LayoutProfileError):
            validate_profile(profile)

    def test_free_css_layout_type_rejected(self) -> None:
        profile = load_profile()
        profile["layout_type"] = "free-css"
        with self.assertRaises(LayoutProfileError):
            validate_profile(profile)

    def test_column_count_mismatch_rejected_not_rescaled(self) -> None:
        profile = load_profile()
        theme = load_effective_theme()
        with self.assertRaises(LayoutProfileError) as ctx:
            compile_geometry(profile, theme, column_count=2)
        self.assertIn("不支持", str(ctx.exception))  # 2/4/5/6 列需各自声明 profile

    def test_geometry_compiles_weights_and_padding(self) -> None:
        profile = load_profile()
        theme = load_effective_theme()
        geometry = compile_geometry(profile, theme)
        self.assertEqual(geometry["content-x"], 90)
        self.assertEqual(geometry["content-y"], 170)
        self.assertEqual(geometry["content-w"], 1100)
        self.assertEqual(geometry["content-h"], 470)
        self.assertEqual(geometry["padding-block"], 15)
        self.assertEqual(geometry["padding-inline"], 18)
        self.assertEqual(geometry["column_weights"], [30.0, 45.0, 25.0])
        # 字号/行高来自 effective_theme 引用，不在 profile 写数值。
        self.assertEqual(geometry["font-size-table_header"], 26)
        self.assertEqual(geometry["font-size-table_body"], 25)

    def test_json_weight_change_propagates_without_html(self) -> None:
        profile = load_profile()
        theme = load_effective_theme()
        profile["columns"]["weights"] = [25, 50, 25]
        profile["padding"]["block"] = 12
        geometry = compile_geometry(profile, theme)
        self.assertEqual(geometry["column_weights"], [25.0, 50.0, 25.0])
        self.assertEqual(geometry["padding-block"], 12)


class LayoutCapacityTest(unittest.TestCase):
    ROWS_3 = [["华东大区", "128.6", "103.2%"],
              ["华南大区", "96.4", "98.7%"],
              ["华北大区", "74.9", "95.4%"]]

    def test_three_short_rows_fit(self) -> None:
        result = estimate_table_capacity(load_profile(), load_effective_theme(),
                                         rows=self.ROWS_3, columns=3)
        self.assertTrue(result["fits"])
        self.assertEqual(result["slot"], "rows")

    def test_overflow_reports_slot_and_space(self) -> None:
        rows = [[f"行{i}", "值", "备注"] for i in range(20)]
        with self.assertRaises(CapacityOverflowError) as ctx:
            require_capacity(load_profile(), load_effective_theme(), rows=rows, columns=3)
        message = str(ctx.exception)
        self.assertIn("layout_capacity_exceeded", message)
        self.assertIn("slot=rows", message)
        self.assertIn("可用", message)

    def test_bigger_font_reduces_capacity(self) -> None:
        profile = load_profile()
        theme = json.loads(THEME_PATH.read_text(encoding="utf-8"))
        normal = compute_effective_theme(theme)
        bigger = compute_effective_theme(
            theme, font_overrides={"table_body.size": 48})
        rows = [[f"行{i}", "值", "备注"] for i in range(5)]
        normal_result = estimate_table_capacity(profile, normal, rows=rows, columns=3)
        bigger_result = estimate_table_capacity(profile, bigger, rows=rows, columns=3)
        self.assertGreater(bigger_result["needed_height"], normal_result["needed_height"])
        self.assertLess(bigger_result["max_rows_estimate"],
                        normal_result["max_rows_estimate"],
                        "字号增大 25→48 后单行估算上限应减少")


if __name__ == "__main__":
    unittest.main()
