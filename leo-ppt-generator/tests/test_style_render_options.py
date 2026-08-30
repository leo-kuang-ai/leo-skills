"""style render 扩展选项的合同测试（风格系统优化计划 U6/U7）。

覆盖：deck 级 --color 覆盖的合并与四条失败路径（role 非法/非 HEX/role 缺失/
palette 缺失）、缺省调用与扩展参数的逐字节等价、--guardrail 护栏摘要块的
确定性（accent 有锚点行/无锚点整行省略）、CLI 侧 --color 参数解析失败。
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator import templates  # noqa: E402
from leo_ppt_generator.templates import (  # noqa: E402
    StyleColorOverrideError,
    TemplateError,
    _merge_palette_override,
    compose_style,
)

STYLE_WITH_ACCENT_HEX = "清爽专业风"
STYLE_WITH_PROSE_ACCENT = "麦肯锡咨询风"


class MergePaletteOverrideTest(unittest.TestCase):
    def test_merge_replaces_only_requested_role(self):
        base = {
            "primary": "white #FFFFFF",
            "secondary": "gray",
            "accent": "blue",
            "neutral": "ink #111111",
        }
        merged = _merge_palette_override(base, {"accent": "#C0FF00"})
        self.assertEqual(merged["accent"], "#C0FF00")
        self.assertEqual(merged["primary"], base["primary"])
        self.assertEqual(merged["neutral"], base["neutral"])
        # 原 dict 不被原地修改
        self.assertEqual(base["accent"], "blue")

    def test_rejects_unknown_role(self):
        with self.assertRaises(StyleColorOverrideError):
            _merge_palette_override({"primary": "x"}, {"brand": "#C0FF00"})

    def test_rejects_non_hex_value(self):
        with self.assertRaises(StyleColorOverrideError):
            _merge_palette_override({"accent": "x"}, {"accent": "blue"})

    def test_rejects_role_missing_from_brief(self):
        with self.assertRaises(StyleColorOverrideError):
            _merge_palette_override({"primary": "x"}, {"neutral": "#111111"})

    def test_rejects_override_without_palette(self):
        with self.assertRaises(StyleColorOverrideError):
            _merge_palette_override(None, {"accent": "#C0FF00"})
        with self.assertRaises(StyleColorOverrideError):
            _merge_palette_override({}, {"accent": "#C0FF00"})

    def test_reason_code_is_style_color_override_invalid(self):
        try:
            _merge_palette_override({"accent": "x"}, {"accent": "nope"})
        except StyleColorOverrideError as exc:
            self.assertEqual(type(exc).reason_code, "style_color_override_invalid")
        else:  # pragma: no cover - 防御：必须抛错
            self.fail("expected StyleColorOverrideError")


class ComposeStyleOptionsTest(unittest.TestCase):
    def test_color_override_visible_in_render_output(self):
        result = compose_style(STYLE_WITH_ACCENT_HEX, colors={"accent": "#0B1220"})
        self.assertEqual(result["color_palette"]["accent"], "#0B1220")

    def test_color_override_error_propagates(self):
        with self.assertRaises(StyleColorOverrideError):
            compose_style(STYLE_WITH_ACCENT_HEX, colors={"accent": "blue"})

    def test_default_call_equals_explicit_default_params(self):
        # 缺省路径必须与显式默认参数逐字节一致（快照消费者的合同）。
        self.assertEqual(
            compose_style(STYLE_WITH_PROSE_ACCENT),
            compose_style(
                STYLE_WITH_PROSE_ACCENT, colors=None, guardrail=False
            ),
        )

    def test_same_input_twice_is_identical(self):
        first = compose_style(STYLE_WITH_ACCENT_HEX, colors={"primary": "#1F2937"})
        second = compose_style(STYLE_WITH_ACCENT_HEX, colors={"primary": "#1F2937"})
        self.assertEqual(first, second)

    def test_guardrail_absent_by_default(self):
        self.assertNotIn("guardrail", compose_style(STYLE_WITH_ACCENT_HEX))

    def test_guardrail_block_contains_fixed_lines_and_accent_anchor(self):
        result = compose_style(STYLE_WITH_ACCENT_HEX, guardrail=True)
        lines = result["guardrail"]
        self.assertTrue(any("设计护栏摘要" in line for line in lines))
        self.assertTrue(any("≥4.5:1" in line for line in lines))
        self.assertTrue(any("accent 锚点：#F59E0B" in line for line in lines))

    def test_guardrail_omits_anchor_line_when_accent_has_no_hex(self):
        # prose accent（无 HEX 锚点）时锚点行整行省略：用合成 brief 断言降级
        # 行为本身，不依赖库中恰好存在 prose accent 的真实风格（lint 基线
        # 收敛后所有 brief 都可能带 HEX 锚点）。
        real = templates.load_style(STYLE_WITH_ACCENT_HEX)
        block = re.search(r"```json\n(.*?)\n```", real["content"], re.S)
        brief = json.loads(block.group(1))
        brief["color_palette"]["accent"] = "one restrained accent, sparingly"
        synthetic = dict(real)
        synthetic["content"] = real["content"].replace(
            block.group(0),
            "```json\n" + json.dumps(brief, ensure_ascii=False, indent=2) + "\n```",
            1,
        )
        with mock.patch.object(templates, "load_style", return_value=synthetic):
            result = compose_style(STYLE_WITH_ACCENT_HEX, guardrail=True)
        self.assertFalse(any("accent 锚点" in line for line in result["guardrail"]))
        self.assertTrue(len(result["guardrail"]) >= 5)

    def test_guardrail_anchor_reflects_override(self):
        # 护栏锚点描述的是生效（覆盖后）调色板，不是 brief 原值。
        result = compose_style(
            STYLE_WITH_ACCENT_HEX, colors={"accent": "#0B1220"}, guardrail=True
        )
        self.assertTrue(
            any("accent 锚点：#0B1220" in line for line in result["guardrail"])
        )
        self.assertFalse(
            any("#F59E0B" in line for line in result["guardrail"])
        )

    def test_guardrail_deterministic(self):
        a = compose_style(STYLE_WITH_ACCENT_HEX, guardrail=True)
        b = compose_style(STYLE_WITH_ACCENT_HEX, guardrail=True)
        self.assertEqual(a["guardrail"], b["guardrail"])


class CliColorParseTest(unittest.TestCase):
    def test_parse_valid_items(self):
        from leo_ppt_generator.cli import _parse_color_overrides

        self.assertIsNone(_parse_color_overrides(None))
        self.assertEqual(
            _parse_color_overrides(["accent=#C0FF00", "primary = #0B1220"]),
            {"accent": "#C0FF00", "primary": "#0B1220"},
        )

    def test_parse_rejects_item_without_separator(self):
        from leo_ppt_generator.cli import _parse_color_overrides

        with self.assertRaises(StyleColorOverrideError):
            _parse_color_overrides(["accent"])

    def test_repeated_role_last_wins(self):
        from leo_ppt_generator.cli import _parse_color_overrides

        self.assertEqual(
            _parse_color_overrides(["accent=#111111", "accent=#222222"]),
            {"accent": "#222222"},
        )

    def test_trailing_newline_hex_rejected(self):
        # $ 锚会被尾随换行穿透；\Z 不。
        with self.assertRaises(StyleColorOverrideError):
            _merge_palette_override({"accent": "x"}, {"accent": "#C0FF00\n"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
