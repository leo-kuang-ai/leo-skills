"""style render 扩展选项的合同测试（风格系统优化计划 U6/U7 + R-27 --var）。

覆盖：deck 级 --color 覆盖的合并与四条失败路径（role 非法/非 HEX/role 缺失/
palette 缺失）、缺省调用与扩展参数的逐字节等价、--guardrail 护栏摘要块的
确定性（accent 有锚点行/无锚点整行省略）、CLI 侧 --color 参数解析失败；
R-27 token sidecar：--var 覆盖生效、对比度硬校验（覆盖键门控 + background
全量重查 + accent 3:1 大字口径）、无 --var 字节红线、无 sidecar/未知键/
非 HEX 值的失败路径、CLI 侧 --var 参数解析；R-31 --layout-lock：版式锚
注入（sidecar 优先 / brief 顶层降级）、五字段齐备校验、无键/缺字段
layout_lock_unavailable 失败路径、字节红线、CLI 旗标接线与 main exit 2。
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
    StyleLayoutLockError,
    StyleVarOverrideError,
    TemplateError,
    _merge_palette_override,
    compose_style,
)

STYLE_WITH_ACCENT_HEX = "清爽专业风"
STYLE_WITH_PROSE_ACCENT = "麦肯锡咨询风"

# R-27 fixture sidecar: keys aligned with the H-line theme.json render
# anchors; accent #F59E0B is sub-4.5 vs white on purpose (decorative
# accent is only owed the 3:1 large-token floor, see render-contract.md).
SIDECAR = {
    "palette": {
        "primary": "#2563EB",
        "accent": "#F59E0B",
        "background": "#FFFFFF",
        "surface": "#F1F5F9",
        "text": "#1F2430",
    },
    "typography": {"title": "思源黑体 Bold", "body": "Noto Sans SC Regular"},
    "density": "comfortable",
}


def _synthetic_style_with_sidecar():
    """Real 清爽专业风 brief with a token_sidecar injected (mock pattern
    from the guardrail prose-accent test above; library files untouched —
    styles/ is owned by the R-66 family-merge batch)."""
    real = templates.load_style(STYLE_WITH_ACCENT_HEX)
    block = re.search(r"```json\n(.*?)\n```", real["content"], re.S)
    brief = json.loads(block.group(1))
    brief["token_sidecar"] = SIDECAR
    synthetic = dict(real)
    synthetic["content"] = real["content"].replace(
        block.group(0),
        "```json\n" + json.dumps(brief, ensure_ascii=False, indent=2) + "\n```",
        1,
    )
    return synthetic


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


class TokenSidecarVarOverrideTest(unittest.TestCase):
    """R-27：--var 覆盖、对比度硬校验与字节红线。"""

    def _compose_with_sidecar(self, **overrides):
        with mock.patch.object(
            templates, "load_style", return_value=_synthetic_style_with_sidecar()
        ):
            return compose_style(STYLE_WITH_ACCENT_HEX, **overrides)

    def test_var_override_visible_in_sidecar_output(self):
        result = self._compose_with_sidecar(
            var_overrides={"palette.primary": "#0B1220"}
        )
        self.assertEqual(result["token_sidecar"]["palette"]["primary"], "#0B1220")
        # 未覆盖键与散文 color_palette 均不被改写（分离的面）。
        self.assertEqual(result["token_sidecar"]["palette"]["accent"], "#F59E0B")
        self.assertIn("#2563EB", result["color_palette"]["primary"])

    def test_var_typography_and_density_pass_through(self):
        result = self._compose_with_sidecar(var_overrides={
            "typography.title": "思源宋体 Heavy",
            "density": "compact",
        })
        self.assertEqual(result["token_sidecar"]["typography"]["title"], "思源宋体 Heavy")
        self.assertEqual(result["token_sidecar"]["density"], "compact")

    def test_sidecar_passthrough_without_var(self):
        # brief 带 sidecar 且不带 --var：sidecar 原样进入输出。
        result = self._compose_with_sidecar()
        self.assertEqual(result["token_sidecar"], SIDECAR)

    def test_byte_red_line_without_var(self):
        # 字节红线：不带 --var 时 compose_style 输出与显式 var_overrides=None
        # 逐字节一致；真实库 brief（无 sidecar）输出不含 token_sidecar 键。
        baseline = compose_style(STYLE_WITH_ACCENT_HEX)
        self.assertEqual(
            json.dumps(baseline, ensure_ascii=False, sort_keys=True),
            json.dumps(
                compose_style(STYLE_WITH_ACCENT_HEX, var_overrides=None),
                ensure_ascii=False, sort_keys=True,
            ),
        )
        self.assertNotIn("token_sidecar", baseline)

    def test_var_rejects_brief_without_sidecar(self):
        with self.assertRaises(StyleVarOverrideError) as ctx:
            compose_style(STYLE_WITH_ACCENT_HEX, var_overrides={"density": "compact"})
        self.assertIn("no token_sidecar", str(ctx.exception))

    def test_var_rejects_unknown_key(self):
        with self.assertRaises(StyleVarOverrideError):
            self._compose_with_sidecar(var_overrides={"palette.brand": "#C0FF00"})
        with self.assertRaises(StyleVarOverrideError):
            self._compose_with_sidecar(var_overrides={"spacing": "tight"})

    def test_var_rejects_non_hex_palette_value(self):
        with self.assertRaises(StyleVarOverrideError) as ctx:
            self._compose_with_sidecar(var_overrides={"palette.accent": "blue"})
        self.assertIn("is not #RRGGBB", str(ctx.exception))

    def test_var_contrast_blocks_low_ratio_primary(self):
        # #F59E0B vs #FFFFFF = 2.15:1，低于 primary 的 4.5 正文下限。
        with self.assertRaises(StyleVarOverrideError) as ctx:
            self._compose_with_sidecar(var_overrides={"palette.primary": "#F59E0B"})
        self.assertIn("style_var_contrast_insufficient", str(ctx.exception))
        self.assertIn("palette.primary", str(ctx.exception))
        self.assertIn("最近合规建议", str(ctx.exception))

    def test_var_contrast_accent_uses_large_token_floor(self):
        # accent 只欠 3:1 大字/非文本口径：2.15 拦截、3.0+ 放行。
        with self.assertRaises(StyleVarOverrideError):
            self._compose_with_sidecar(var_overrides={"palette.accent": "#F59E0B"})
        result = self._compose_with_sidecar(var_overrides={"palette.accent": "#B55E00"})
        self.assertEqual(result["token_sidecar"]["palette"]["accent"], "#B55E00")

    def test_var_contrast_rechecks_all_ink_keys_on_background_override(self):
        # 覆盖 background → 对 primary(#2563EB, 5.17 vs 白)全量重查：
        # 换暗底后原 primary 对比坍塌，必须拦截（双向漂移）。
        with self.assertRaises(StyleVarOverrideError) as ctx:
            self._compose_with_sidecar(var_overrides={"palette.background": "#0B1220"})
        self.assertIn("palette.primary", str(ctx.exception))

    def test_var_contrast_uses_sidecar_background_not_white(self):
        # sidecar background=#FFFFFF、覆盖 text=#FFFF00（1.07:1）拦截；
        # 覆盖 text 为合规深色放行。
        with self.assertRaises(StyleVarOverrideError):
            self._compose_with_sidecar(var_overrides={"palette.text": "#FFFF00"})
        result = self._compose_with_sidecar(var_overrides={"palette.text": "#111827"})
        self.assertEqual(result["token_sidecar"]["palette"]["text"], "#111827")

    def test_var_does_not_gate_untouched_preexisting_tokens(self):
        # 只覆盖 typography 时不过对比度门；sidecar 原有 accent #F59E0B
        # （对白 2.15）不阻塞非 palette 覆盖。
        result = self._compose_with_sidecar(var_overrides={"typography.body": "MiSans"})
        self.assertEqual(result["token_sidecar"]["palette"]["accent"], "#F59E0B")

    def test_var_reason_code_is_style_var_override_invalid(self):
        try:
            self._compose_with_sidecar(var_overrides={"palette.accent": "nope"})
        except StyleVarOverrideError as exc:
            self.assertEqual(type(exc).reason_code, "style_var_override_invalid")
        else:  # pragma: no cover - 防御：必须抛错
            self.fail("expected StyleVarOverrideError")

    def test_var_same_input_twice_is_identical(self):
        first = self._compose_with_sidecar(var_overrides={"palette.primary": "#0B1220"})
        second = self._compose_with_sidecar(var_overrides={"palette.primary": "#0B1220"})
        self.assertEqual(first, second)


class CliVarParseTest(unittest.TestCase):
    def test_parse_valid_items(self):
        from leo_ppt_generator.cli import _parse_var_overrides

        self.assertIsNone(_parse_var_overrides(None))
        self.assertEqual(
            _parse_var_overrides(
                ["palette.accent = #C0FF00", "typography.title=思源宋体", "density=compact"]
            ),
            {"palette.accent": "#C0FF00", "typography.title": "思源宋体", "density": "compact"},
        )

    def test_parse_rejects_item_without_separator(self):
        from leo_ppt_generator.cli import _parse_var_overrides

        with self.assertRaises(StyleVarOverrideError):
            _parse_var_overrides(["palette.accent"])

    def test_repeated_key_last_wins(self):
        from leo_ppt_generator.cli import _parse_var_overrides

        self.assertEqual(
            _parse_var_overrides(["palette.primary=#111111", "palette.primary=#222222"]),
            {"palette.primary": "#222222"},
        )


# R-31 fixture: layout-system lock fields (xhs-visual-director master-lock
# prefix shape — grid / safe margin / page-number slot / corner / line
# weight). No builtin brief carries a `layout` key yet (styles/ is owned by
# the R-66 family-merge batch), so tests inject it synthetically.
LAYOUT_LOCK = {
    "grid": "12 列 × 24px 槽",
    "safe_margin": "80px 100px 72px",
    "page_no": "右下 right:44px bottom:30px",
    "corner_radius": "0px（直角）",
    "line_weight": "1px 分隔线",
}


def _synthetic_style_brief(brief_mutator):
    """Real 清爽专业风 brief with a JSON-block mutation applied (mock
    pattern shared with ``_synthetic_style_with_sidecar``; library files
    untouched)."""
    real = templates.load_style(STYLE_WITH_ACCENT_HEX)
    block = re.search(r"```json\n(.*?)\n```", real["content"], re.S)
    brief = json.loads(block.group(1))
    brief_mutator(brief)
    synthetic = dict(real)
    synthetic["content"] = real["content"].replace(
        block.group(0),
        "```json\n" + json.dumps(brief, ensure_ascii=False, indent=2) + "\n```",
        1,
    )
    return synthetic


class LayoutLockTest(unittest.TestCase):
    """R-31：--layout-lock 版式锚注入、失败路径与字节红线。"""

    def _compose_with_layout(self, brief_mutator, **overrides):
        synthetic = _synthetic_style_brief(brief_mutator)
        with mock.patch.object(templates, "load_style", return_value=synthetic):
            return compose_style(STYLE_WITH_ACCENT_HEX, **overrides)

    def test_layout_lock_absent_by_default(self):
        # 真实库 brief（无 layout 键）：缺省输出不含 layout_lock 键。
        self.assertNotIn("layout_lock", compose_style(STYLE_WITH_ACCENT_HEX))

    def test_layout_lock_byte_red_line(self):
        # 字节红线：不带旗标与显式 layout_lock=False 逐字节一致。
        self.assertEqual(
            json.dumps(compose_style(STYLE_WITH_ACCENT_HEX), ensure_ascii=False,
                       sort_keys=True),
            json.dumps(
                compose_style(STYLE_WITH_ACCENT_HEX, layout_lock=False),
                ensure_ascii=False, sort_keys=True,
            ),
        )

    def test_layout_lock_injects_five_anchor_lines_from_sidecar(self):
        result = self._compose_with_layout(
            lambda b: b.update(
                token_sidecar={**SIDECAR, "layout": LAYOUT_LOCK}
            ),
            layout_lock=True,
        )
        lines = result["layout_lock"]
        self.assertEqual(lines[0], "【版式锚（逐页逐字节相同注入，防网格/页码/边距漂移）】")
        self.assertTrue(any("网格锚：12 列 × 24px 槽" in x for x in lines))
        self.assertTrue(any("安全边距锚：80px 100px 72px" in x for x in lines))
        self.assertTrue(any("页码位锚：右下 right:44px bottom:30px" in x for x in lines))
        self.assertTrue(any("圆角锚：0px（直角）" in x for x in lines))
        self.assertTrue(any("线重锚：1px 分隔线" in x for x in lines))
        self.assertEqual(len(lines), 6)

    def test_layout_lock_reads_brief_top_level_layout(self):
        # brief 顶层 layout 键是合法降级源（无需 sidecar）。
        result = self._compose_with_layout(
            lambda b: b.update(layout=LAYOUT_LOCK), layout_lock=True
        )
        self.assertTrue(any("网格锚" in x for x in result["layout_lock"]))

    def test_layout_lock_sidecar_wins_over_brief(self):
        # sidecar.layout 优先于 brief 顶层 layout（生效 token 面）。
        result = self._compose_with_layout(
            lambda b: b.update(
                layout={**LAYOUT_LOCK, "grid": "brief 侧 6 列"},
                token_sidecar={**SIDECAR, "layout": LAYOUT_LOCK},
            ),
            layout_lock=True,
        )
        self.assertTrue(any("网格锚：12 列 × 24px 槽" in x for x in result["layout_lock"]))
        self.assertFalse(any("brief 侧 6 列" in x for x in result["layout_lock"]))

    def test_layout_lock_fails_loud_without_any_layout_key(self):
        # 无 layout 键：报 layout_lock_unavailable，不静默降级。
        with self.assertRaises(StyleLayoutLockError) as ctx:
            self._compose_with_layout(
                lambda b: b.update(token_sidecar=SIDECAR), layout_lock=True
            )
        self.assertIn("layout_lock_unavailable", str(ctx.exception))
        self.assertEqual(
            type(ctx.exception).reason_code, "layout_lock_unavailable"
        )

    def test_layout_lock_fails_loud_on_partial_fields(self):
        # layout 键存在但缺 page_no：报错并指明缺的字段（防半锁漂移）。
        partial = {k: v for k, v in LAYOUT_LOCK.items() if k != "page_no"}
        with self.assertRaises(StyleLayoutLockError) as ctx:
            self._compose_with_layout(
                lambda b: b.update(layout=partial), layout_lock=True
            )
        self.assertIn("layout.page_no", str(ctx.exception))

    def test_layout_lock_rejects_blank_field_value(self):
        # 空白字符串字段视同缺失（静默空锚 = 漂移回归）。
        blank = {**LAYOUT_LOCK, "line_weight": "  "}
        with self.assertRaises(StyleLayoutLockError) as ctx:
            self._compose_with_layout(
                lambda b: b.update(layout=blank), layout_lock=True
            )
        self.assertIn("layout.line_weight", str(ctx.exception))

    def test_layout_lock_deterministic(self):
        mutate = lambda b: b.update(layout=LAYOUT_LOCK)  # noqa: E731
        first = self._compose_with_layout(mutate, layout_lock=True)
        second = self._compose_with_layout(mutate, layout_lock=True)
        self.assertEqual(first["layout_lock"], second["layout_lock"])

    def test_layout_lock_composes_with_var_overrides(self):
        # --var（palette 面）与 --layout-lock（版式面）是分离的面，可组合。
        result = self._compose_with_layout(
            lambda b: b.update(
                token_sidecar={**SIDECAR, "layout": LAYOUT_LOCK}
            ),
            var_overrides={"palette.primary": "#0B1220"},
            layout_lock=True,
        )
        self.assertEqual(result["token_sidecar"]["palette"]["primary"], "#0B1220")
        self.assertTrue(any("网格锚" in x for x in result["layout_lock"]))

    def test_layout_lock_does_not_touch_other_faces(self):
        # 开启版式锚不改写 color_palette / token_sidecar 原值。
        result = self._compose_with_layout(
            lambda b: b.update(layout=LAYOUT_LOCK), layout_lock=True
        )
        self.assertNotIn("token_sidecar", result)
        self.assertIn("#2563EB", result["color_palette"]["primary"])


class CliLayoutLockFlagTest(unittest.TestCase):
    def test_flag_default_off_and_explicit_on(self):
        from leo_ppt_generator.cli import build_parser

        base = build_parser().parse_args(["style", "render", "x"])
        self.assertIs(getattr(base, "layout_lock", None), False)
        on = build_parser().parse_args(["style", "render", "x", "--layout-lock"])
        self.assertIs(on.layout_lock, True)

    def test_main_exits_2_with_layout_lock_unavailable(self):
        # 端到端：真实库风格无 layout 键 → blocked envelope + exit 2 不静默。
        import contextlib
        import io

        from leo_ppt_generator.cli import main

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = main(
                ["style", "render", STYLE_WITH_ACCENT_HEX, "--layout-lock"]
            )
        self.assertEqual(rc, 2)
        self.assertIn("layout_lock_unavailable", stderr.getvalue())

    def test_main_default_flag_output_matches_baseline(self):
        # 端到端字节红线：不带旗标的 main 输出不含 layout_lock。
        import contextlib
        import io

        from leo_ppt_generator.cli import main

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
            io.StringIO()
        ):
            rc = main(["style", "render", STYLE_WITH_ACCENT_HEX])
        self.assertEqual(rc, 0)
        self.assertNotIn("layout_lock", stdout.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
