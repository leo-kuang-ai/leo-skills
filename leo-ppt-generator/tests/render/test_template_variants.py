"""R-28 扩面模板的冒烟测试：lint 合同（离线恒跑）+ 渲染 lane 冒烟（真浏览器，
缺 chromium 时 skip 并披露）。覆盖 spec-table（P25）/ timeline（P11）/
compare（P8）/ pull-quote（P34）四模板的数据合同与 provenance；R-32 追加
frame-shot 证据截图框架（guizang screenshot-treatment 六参数移植）的 lint
合同、正交纪律静态断言与 device 包装渲染冒烟。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
SCRIPTS_DIR = SKILL_DIR / "scripts"
for _path in (str(RUNTIME_SRC), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from tests.render.helpers import browser_test_case  # noqa: E402

NEW_TEMPLATES = ("spec-table", "timeline", "compare", "pull-quote", "frame-shot")


def _shot_data_uri() -> str:
    """Deterministic 320x200 solid PNG as a data: URI.

    frame-shot only accepts data: URIs (offline deterministic lane), so the
    smoke fixture must be embedded rather than referenced by path.
    """
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (320, 200), (37, 99, 235)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


SLIDE_DATA = {
    "spec-table": {
        "title": "推理服务规格",
        "columns": ["参数", "值", "备注"],
        "column_align": ["left", "right", "left"],
        "rows": [
            ["上下文窗口", "128000", "输入+输出合计"],
            ["首 token 延迟", "220", "P50，单位 ms"],
            ["吞吐", "9800", "tokens/s，批大小 32"],
            ["可用性", "99.95", "月度 SLO"],
        ],
        "page_no": 3,
    },
    "timeline": {
        "title": "交付节奏",
        "steps": [
            {"no": "01", "name": "立项对齐"},
            {"no": "02", "name": "素材取证"},
            {"no": "03", "name": "初稿生成"},
            {"no": "04", "name": "机读验收"},
            {"no": "05", "name": "交付归档"},
        ],
        "page_no": 4,
    },
    "compare": {
        "sides": [
            {
                "label": "BEFORE",
                "title": "手工制图",
                "points": ["单页 40 分钟", "数值誊写易错", "风格逐页漂移"],
            },
            {
                "label": "AFTER",
                "title": "渲染 lane",
                "points": ["单页 40 秒", "逐字保真零誊写", "锚点注入防漂移"],
            },
        ],
        "page_no": 5,
    },
    "pull-quote": {
        "quote": "验证分报告前置，交付才算开始。",
        "source_name": "李工",
        "source_meta": "某平台架构负责人 · 2026",
        "page_no": 6,
    },
    # R-32 六参数缺省档（browser/phone/超宽变体在 FrameShotRenderSmoke
    # 里以 overrides 覆盖渲染）；image_src 由渲染侧惰性补 data: URI。
    "frame-shot": {
        "kicker": "EVIDENCE",
        "title": "线上控制台实况",
        "caption": "来源：产品后台截屏（已裁除状态栏），2026-08-31",
        "ratio": "16x10",
        "corners": "sq",
        "shadow": "none",
        "bg": "grey-1",
        "inset": "bal",
        "fit": "contain",
        "device": "none",
        "image_alt": "控制台截图",
        "page_no": 7,
    },
}


class NewTemplatesLintContract(unittest.TestCase):
    """离线恒跑：4 模板必须过 lint_render_templates 的全部 template.* 规则。"""

    def test_new_templates_pass_full_lint_contract(self):
        import lint_render_templates as lrt

        rules = lrt.load_rules()
        for template_id in NEW_TEMPLATES:
            path = lrt.TEMPLATES_DIR / template_id / "page.html"
            self.assertTrue(path.is_file(), f"missing template: {path}")
            result = lrt.lint_template(path, "render:html", rules)
            self.assertEqual(
                result["errors"], [], f"{template_id}: {result['errors']}"
            )
            # render:html 下五条规则全部适用（无 skip 披露）。
            self.assertEqual(result["skipped_rules"], [])

    def test_new_templates_declare_data_blocks(self):
        # E2 对账依赖 data-leo-block 锚点；每模板至少声明一个内容块。
        for template_id, block in (
            ("spec-table", "table"),
            ("timeline", "timeline"),
            ("compare", "compare"),
            ("pull-quote", "quote"),
            ("frame-shot", "frame-shot-stage"),
        ):
            text = (SKILL_DIR / "template-library" / "canonical" / "templates"
                    / template_id / "page.html").read_text(encoding="utf-8")
            self.assertIn(f'data-leo-block="{block}"', text)


class FrameShotContractTest(unittest.TestCase):
    """R-32 离线恒跑：frame-shot 六参数枚举面与正交纪律（guizang
    screenshot-treatment 移植合同的静态断言）。"""

    FRAME_SHOT = (SKILL_DIR / "template-library" / "canonical" / "templates"
                  / "frame-shot" / "page.html")

    @classmethod
    def setUpClass(cls):
        cls.text = cls.FRAME_SHOT.read_text(encoding="utf-8")

    def test_orthographic_no_tilt_primitives(self):
        # 正交纪律：代码（CSS/JS，剥离注释后）不得出现透视/倾斜/旋转/3D
        # 变换原语——注释里的纪律陈述本身不算违规。
        import re

        code = re.sub(r"/\*.*?\*/", "", self.text, flags=re.S)
        code = re.sub(r"<!--.*?-->", "", code, flags=re.S)
        code = re.sub(r"//[^\n]*", "", code)
        for primitive in ("perspective", "skew(", "rotate(", "rotateX",
                          "rotateY", "matrix3d"):
            self.assertNotIn(
                primitive, code,
                f"frame-shot must stay orthographic: {primitive} is forbidden",
            )

    def test_declares_seven_ratio_slots(self):
        for ratio in ("16x10", "16x9", "4x3", "3x2", "1x1", "3x4", "21x9"):
            self.assertIn(f".fs-r-{ratio}", self.text)

    def test_corner_radius_ceiling_is_14px(self):
        # guizang 纪律：圆角上限 14px（更大读作 iOS 营销）；三档 sq/sm/md。
        import re

        found = 0
        for name, body in re.findall(
            r"\.fs-corners-(\w+)\s*\{([^}]*)\}", self.text
        ):
            value = re.search(r"border-radius:\s*(\d+)(?:px)?", body)
            self.assertIsNotNone(value, f".fs-corners-{name} lacks radius")
            self.assertLessEqual(
                int(value.group(1)), 14,
                f".fs-corners-{name} breaks the 14px ceiling",
            )
            found += 1
        self.assertEqual(found, 3)
        self.assertIn(".fs-corners-md { border-radius: 14px; }", self.text)

    def test_stage_never_exposes_accent_background(self):
        # 舞台六档全是中性/纹理 token，不提供 accent 类背景入口。
        import re

        stages = re.findall(r"\.fs-bg-([\w-]+)\s*\{", self.text)
        self.assertEqual(
            sorted(stages),
            ["dot", "grey-1", "grid", "ink", "paper", "paper-2"],
        )

    def test_refuses_non_data_uri_sources(self):
        # 离线确定合同：image_src 仅接受 data: 前缀，远程/file 拒绝加载。
        self.assertIn('indexOf("data:")', self.text)
        self.assertIn("offline contract", self.text)

    def test_device_phone_forces_square_corners(self):
        # bezel 已圆角内图：phone 包装强制回到 sq，防双圆角。
        self.assertIn('device === "phone") { corners = "sq"; }', self.text)


def _render_template(template_id: str, **overrides) -> Path:
    """Render one slide through the real lane and assert the provenance
    contract (backend / template_id / ready signal / canvas pixels)."""

    from leo_ppt_generator.render.page import render_page

    payload = dict(SLIDE_DATA[template_id], **overrides)
    if template_id == "frame-shot":
        payload.setdefault("image_src", _shot_data_uri())
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "slide.json"
        data.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        out = Path(tmp) / "out.png"
        result = render_page(template_id, data, out, size=(1280, 720))
        assert result["backend"] == "render:html"
        assert result["template_id"] == template_id
        assert result["ready_signal"] == "data-leo-ready"
        assert (result["width"], result["height"]) == (1280, 720)
        from PIL import Image

        with Image.open(out) as image:
            assert image.size == (1280, 720)
        return out


class NewTemplatesRenderSmoke(browser_test_case()):
    """真浏览器冒烟：每模板渲染一次并断言 provenance 与画幅。"""

    def _render(self, template_id: str):
        return _render_template(template_id)

    def test_spec_table_renders(self):
        self._render("spec-table")

    def test_timeline_renders(self):
        self._render("timeline")

    def test_compare_renders(self):
        self._render("compare")

    def test_pull_quote_renders(self):
        self._render("pull-quote")


class FrameShotRenderSmoke(browser_test_case()):
    """R-32 真浏览器冒烟：六参数组合（含 device 包装与超宽档）逐项渲染。"""

    def _render_shot(self, **overrides):
        return _render_template("frame-shot", **overrides)

    def test_frame_shot_default_solid_stage_renders(self):
        # 缺省档：无包装 + grey-1 舞台 + inset-bal（guizang Swiss 配方）。
        self._render_shot()

    def test_frame_shot_device_browser_and_grid_stage_renders(self):
        # browser 包装（chrome 条）+ bg-grid 纹理舞台 + soft 阴影。
        self._render_shot(
            ratio="16x10", device="browser", bg="grid", corners="sm",
            shadow="soft", inset="sub",
        )

    def test_frame_shot_device_phone_portrait_ink_renders(self):
        # phone 包装（bezel）+ r-3x4 竖屏档 + ink 暗底（guizang 配对建议）。
        self._render_shot(
            ratio="3x4", device="phone", bg="ink", inset="none",
            shadow="none",
        )

    def test_frame_shot_ultrawide_hero_renders(self):
        # r-21x9 超宽档 + shadow-ed（hero 1px outline）+ dot 舞台。
        self._render_shot(
            ratio="21x9", bg="dot", shadow="ed", corners="md", inset="sub",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
