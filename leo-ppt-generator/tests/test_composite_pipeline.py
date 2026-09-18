"""U8/R-70 composite 合成管线行为测试。

覆盖计划场景中可离线确定性验证的部分：逐字/单位保真、任一层手改拒绝、
溢出/缺字段/画布/对比度失败、三布局×两主题矩阵、透明文字层、双
provenance、旧 run freshness 消费（债4）、composite 与 TF-2 事件分开记录，
以及真浏览器链路的背景层→合成→校验。

不覆盖也不声称（阶段门证据，not_run 并在合同文档披露）：真实配对视觉
协议（判官-fixture＋人工-协议）、真实 TF/成本账单与相对收益声明。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.render.helpers import browser_test_case

from leo_ppt_generator.render.composite import (
    COMPOSITE_KIND,
    compose_page,
    verify_composite,
)
from leo_ppt_generator.render.errors import RenderError
from leo_ppt_generator.render.text_layer import TextLayerError
from leo_ppt_generator.storage import sha256_file

LIGHT_THEME = {"colors": {"title": "#111111", "body": "#333333"}, "fonts": {}}
DARK_THEME = {"colors": {"title": "#f5f2ea", "body": "#e8e4d8"}, "fonts": {}}
# 主题配套底色：浅色主题配浅底、深色主题配深底（对比度门按真实采样拦截）。
THEME_BACKGROUND = {
    "light": (240, 240, 236),
    "dark": (20, 24, 33),
}

# 三类版式 spec：标题横带 / 侧栏分栏 / 密集换行（max_width 强制换行）。
LAYOUT_TITLE_BAND = {
    "required_text": ["季度经营复盘", "增长与效率的再平衡"],
    "anchors": [
        {"text": "季度经营复盘", "x": 160, "y": 160, "size": 120, "color_role": "title"},
        {"text": "增长与效率的再平衡", "x": 160, "y": 420, "size": 72, "color_role": "body"},
    ],
}
LAYOUT_SIDE_COLUMN = {
    "required_text": ["收入结构", "订阅占比 62%", "毛利率 38.2%（估算）"],
    "anchors": [
        {"text": "收入结构", "x": 160, "y": 200, "size": 96, "color_role": "title"},
        {"text": "订阅占比 62%", "x": 160, "y": 480, "size": 64, "color_role": "body"},
        {"text": "毛利率 38.2%（估算）", "x": 1360, "y": 480, "size": 64, "color_role": "body"},
    ],
}


def _dense_wrap_spec():
    """密集换行版式：max_width 强制长文本多行换行（逐字不丢）。"""

    long_text = (
        "本页为密集文本：收入结构在下半年出现明显变化，订阅收入占比持续上升，"
        "一次性交付收入占比下降，整体毛利率因产品组合变化而承压，需要在下一"
        "季度重新校准定价与交付资源的配比。"
    )
    return {
        "required_text": [long_text, "标注：估算"],
        "anchors": [
            {"text": long_text, "x": 160, "y": 240, "size": 64, "color_role": "body", "max_width": 1500},
            {"text": "标注：估算", "x": 160, "y": 1100, "size": 48, "color_role": "body"},
        ],
    }


def make_background(path: Path, color=(240, 240, 236)) -> Path:
    from PIL import Image

    Image.new("RGB", (2560, 1440), color).save(path, format="PNG")
    return path


def make_receipt(background: Path) -> Path:
    """合成合同要求的背景 provenance fixture（结构同 render provenance sidecar）。"""

    receipt = {
        "schema_version": 1,
        "kind": "render_provenance",
        "backend": "render:html",
        "template_id": "body-basic",
        "template_sha256": "fixture",
        "data_sha256": "fixture",
        "dialect": None,
        "renderer": "fixture-renderer",
        "out": str(background),
        "out_sha256": sha256_file(background),
        "width": 2560,
        "height": 1440,
    }
    path = background.with_name(background.name + ".render.json")
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def write_spec(root: Path, name: str, spec: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return path


class CompositePipelineBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def themed(self, spec: dict, theme: dict) -> dict:
        return {**spec, "theme": theme}

    def compose(self, spec_path: Path, name="page.png", background_color=(240, 240, 236)):
        background = make_background(self.root / "bg.png", color=background_color)
        receipt = make_receipt(background)
        return compose_page(
            background, spec_path, self.root / name,
            render_receipt_path=receipt,
        )


class CompositeVerbatimTest(CompositePipelineBase):
    """逐字/单位正确 + 透明文字层 + 双 provenance。"""

    def test_units_and_text_render_verbatim_into_dual_provenance(self):
        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_SIDE_COLUMN, LIGHT_THEME))
        result = self.compose(spec)
        self.assertEqual(result["kind"], COMPOSITE_KIND)
        self.assertEqual(
            result["text_layer"]["rendered"],
            ["收入结构", "订阅占比 62%", "毛利率 38.2%（估算）"],
        )
        self.assertEqual(result["text_layer"]["source_class"], "deterministic-overlay")
        self.assertNotEqual(result["background"]["out_sha256"], result["out_sha256"])
        sidecar = json.loads(
            (self.root / "page.composite.json").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["out_sha256"], result["out_sha256"])
        self.assertEqual(sidecar["background"]["backend"], "render:html")
        # 产物三件套都在：终页、透明文字层、sidecar
        self.assertTrue((self.root / "page.png").is_file())
        self.assertTrue((self.root / "page.text-layer.png").is_file())

    def test_text_layer_is_transparent_and_paints_only_text(self):
        from PIL import Image

        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_SIDE_COLUMN, LIGHT_THEME))
        self.compose(spec)
        with Image.open(self.root / "page.text-layer.png") as layer:
            self.assertEqual(layer.mode, "RGBA")
            pixels = layer.load()
        corner = pixels[2500, 1400]
        self.assertEqual(corner[3], 0, "文字层空白区必须全透明")
        glyph = [pixels[x, 240] for x in range(160, 900, 8)]
        self.assertTrue(any(pixel[3] > 0 for pixel in glyph), "落位行应存在字形像素")
        with Image.open(self.root / "bg.png") as background, Image.open(self.root / "page.png") as page:
            self.assertEqual(page.getpixel((2500, 1400)), background.getpixel((2500, 1400)))

    def test_same_input_composes_byte_identical(self):
        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_TITLE_BAND, DARK_THEME))
        first = self.compose(spec, name="a.png", background_color=THEME_BACKGROUND["dark"])
        second = self.compose(spec, name="b.png", background_color=THEME_BACKGROUND["dark"])
        self.assertEqual(first["out_sha256"], second["out_sha256"])
        self.assertEqual(first["text_layer"]["sha256"], second["text_layer"]["sha256"])
        self.assertEqual(
            (self.root / "a.png").read_bytes(), (self.root / "b.png").read_bytes())

    def test_theme_change_invalidates_output(self):
        light = write_spec(self.root, "light.json", self.themed(LAYOUT_TITLE_BAND, LIGHT_THEME))
        dark = write_spec(self.root, "dark.json", self.themed(LAYOUT_TITLE_BAND, DARK_THEME))
        light_result = self.compose(light, name="light.png")
        dark_result = self.compose(dark, name="dark.png", background_color=THEME_BACKGROUND["dark"])
        self.assertNotEqual(light_result["out_sha256"], dark_result["out_sha256"])
        self.assertIsNotNone(light_result["text_layer"]["theme_sha256"])
        self.assertNotEqual(
            light_result["text_layer"]["theme_sha256"],
            dark_result["text_layer"]["theme_sha256"])


class CompositeLayoutThemeMatrixTest(CompositePipelineBase):
    """三布局×两主题：全部合成并可通过 verify（机制级矩阵）。"""

    def test_three_layouts_times_two_themes_compose_and_verify(self):
        layouts = {
            "title-band": LAYOUT_TITLE_BAND,
            "side-column": LAYOUT_SIDE_COLUMN,
            "dense-wrap": _dense_wrap_spec(),
        }
        themes = {"light": LIGHT_THEME, "dark": DARK_THEME}
        for layout_name, layout in layouts.items():
            for theme_name, theme in themes.items():
                with self.subTest(layout=layout_name, theme=theme_name):
                    spec = write_spec(
                        self.root, f"{layout_name}-{theme_name}.json", self.themed(layout, theme))
                    result = self.compose(spec, name=f"{layout_name}-{theme_name}.png",
                                          background_color=THEME_BACKGROUND[theme_name])
                    self.assertTrue((self.root / f"{layout_name}-{theme_name}.png").is_file())
                    report = verify_composite(
                        self.root / "bg.png", spec,
                        self.root / f"{layout_name}-{theme_name}.text-layer.png",
                        self.root / f"{layout_name}-{theme_name}.png",
                    )
                    self.assertEqual(report["status"], "verified")
                    self.assertEqual(report["rendered"], layout["required_text"])

    def test_dense_wrap_is_verbatim_across_lines(self):
        from leo_ppt_generator.render import text_layer as tl

        spec = _dense_wrap_spec()
        long_text = spec["required_text"][0]
        base = tl.new_canvas((2560, 1440))
        draw = tl.draw_of(base)
        font = tl.resolve_font(None, 64)
        lines = tl.wrap_lines(long_text, draw, font, 1500)
        self.assertGreater(len(lines), 1, "max_width 1500 下 64px 长文本必须换行")
        self.assertEqual("".join(lines), long_text, "换行逐字不丢不改")


class CompositeHandModificationTest(CompositePipelineBase):
    """任一层手改拒绝：文字层 / 整页 / 背景层。"""

    def setUp(self):
        super().setUp()
        self.spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_TITLE_BAND, LIGHT_THEME))
        make_background(self.root / "bg.png")
        self.receipt = make_receipt(self.root / "bg.png")
        compose_page(self.root / "bg.png", self.spec, self.root / "page.png",
                     render_receipt_path=self.receipt)

    def _tamper_pixel(self, path: Path):
        """翻转首个不透明像素的一个通道（透明层取首个字形，不透明页取左上角）。"""

        from PIL import Image

        with Image.open(path) as opened:
            image = opened.copy()
        pixels = image.load()
        if image.mode == "RGBA":
            x, y = next(
                (x, row)
                for x in range(0, image.width, 40)
                for row in range(image.height)
                if pixels[x, row][3] > 0
            )
            original = pixels[x, y]
            pixels[x, y] = (original[0] ^ 0xFF, original[1], original[2], original[3])
        else:
            original = pixels[100, 100]
            pixels[100, 100] = (original[0] ^ 0xFF, original[1], original[2])
        image.save(path, format="PNG")

    def test_modified_text_layer_rejected(self):
        self._tamper_pixel(self.root / "page.text-layer.png")
        with self.assertRaises(RenderError) as ctx:
            verify_composite(self.root / "bg.png", self.spec,
                             self.root / "page.text-layer.png", self.root / "page.png")
        self.assertEqual(ctx.exception.reason_code, "composite_text_layer_modified")

    def test_modified_final_page_rejected(self):
        self._tamper_pixel(self.root / "page.png")
        with self.assertRaises(RenderError) as ctx:
            verify_composite(self.root / "bg.png", self.spec,
                             self.root / "page.text-layer.png", self.root / "page.png")
        self.assertEqual(ctx.exception.reason_code, "composite_page_modified")

    def test_modified_background_rejected_by_receipt_binding(self):
        self._tamper_pixel(self.root / "bg.png")
        with self.assertRaises(RenderError) as ctx:
            compose_page(self.root / "bg.png", self.spec, self.root / "again.png",
                         render_receipt_path=self.receipt)
        self.assertEqual(ctx.exception.reason_code, "render_receipt_invalid")

    def test_untouched_artifacts_verify(self):
        report = verify_composite(self.root / "bg.png", self.spec,
                                  self.root / "page.text-layer.png", self.root / "page.png",
                                  render_receipt_path=self.receipt)
        self.assertEqual(report["status"], "verified")


class CompositeFailureContractsTest(CompositePipelineBase):
    """溢出 / 拉伸 / 缺字段 / 对比度 / 画布失败。"""

    def test_anchor_out_of_canvas_rejected(self):
        spec = self.themed({
            "required_text": ["越界标题"],
            "anchors": [{"text": "越界标题", "x": 2400, "y": 1400, "size": 96,
                         "color_role": "title"}],
        }, LIGHT_THEME)
        with self.assertRaises(RenderError) as ctx:
            self.compose(write_spec(self.root, "spec.json", spec))
        self.assertEqual(ctx.exception.reason_code, "overlay_out_of_canvas")

    def test_whitelist_entry_missing_anchor_rejected(self):
        spec = self.themed({
            "required_text": ["标题甲", "无锚点条目"],
            "anchors": [{"text": "标题甲", "x": 160, "y": 200}],
        }, LIGHT_THEME)
        with self.assertRaises(RenderError) as ctx:
            self.compose(write_spec(self.root, "spec.json", spec))
        self.assertEqual(ctx.exception.reason_code, "overlay_spec_invalid")
        self.assertIn("缺少锚点", ctx.exception.detail)

    def test_non_16_9_background_rejected(self):
        from PIL import Image

        background = self.root / "odd.png"
        Image.new("RGB", (1536, 1024), (240, 240, 236)).save(background, format="PNG")
        receipt = make_receipt(background)
        with Image.open(background) as img:
            pass
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        receipt_payload["width"] = 1536
        receipt_payload["height"] = 1024
        receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_TITLE_BAND, LIGHT_THEME))
        with self.assertRaises(RenderError) as ctx:
            compose_page(background, spec, self.root / "page.png",
                         render_receipt_path=receipt)
        self.assertEqual(ctx.exception.reason_code, "overlay_canvas_mismatch")

    def test_low_contrast_rejected(self):
        # 无主题 spec：默认 #111111 文字压深色底 → 对比度不足必须拒绝。
        spec = write_spec(self.root, "spec.json", {
            "required_text": ["深底深字"],
            "anchors": [{"text": "深底深字", "x": 160, "y": 200, "size": 96}],
        })
        with self.assertRaises(RenderError) as ctx:
            self.compose(spec, background_color=THEME_BACKGROUND["dark"])
        self.assertEqual(ctx.exception.reason_code, "text_contrast_insufficient")

    def test_missing_background_or_receipt_rejected(self):
        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_TITLE_BAND, LIGHT_THEME))
        with self.assertRaises(RenderError) as ctx:
            compose_page(self.root / "nope.png", spec, self.root / "page.png",
                         render_receipt_path=self.root / "nope.render.json")
        self.assertEqual(ctx.exception.reason_code, "composite_background_missing")
        make_background(self.root / "bg.png")
        with self.assertRaises(RenderError) as ctx:
            compose_page(self.root / "bg.png", spec, self.root / "page.png",
                         render_receipt_path=self.root / "nope.render.json")
        self.assertEqual(ctx.exception.reason_code, "render_receipt_invalid")


class _StubResolver:
    """verify_design_freshness 的最小 resolver seam（漂移循环是被测对象）。"""

    def __init__(self, files: dict[str, Path]):
        self.files = files

    def resolve(self, asset_id: str):
        return {"path": str(self.files[asset_id])}


class CompositeFreshnessTest(CompositePipelineBase):
    """旧 run 恢复：verify_design_freshness 消费（债4）。"""

    def setUp(self):
        super().setUp()
        self.asset = self.root / "asset.css"
        self.asset.write_text("body { color: red }", encoding="utf-8")
        self.resolved = {
            "entity": "resolved-design",
            "dependencies": [{"asset_id": "a", "sha256": sha256_file(self.asset)}],
        }

    def test_fresh_design_composes(self):
        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_TITLE_BAND, LIGHT_THEME))
        result = compose_page(
            make_background(self.root / "bg.png"), spec, self.root / "page.png",
            render_receipt_path=make_receipt(self.root / "bg.png"),
            resolved_design=self.resolved, resolver=_StubResolver({"a": self.asset}),
        )
        self.assertTrue((self.root / "page.png").is_file())
        self.assertEqual(result["kind"], COMPOSITE_KIND)

    def test_drifted_design_blocks_resume(self):
        self.asset.write_text("body { color: blue }", encoding="utf-8")
        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_TITLE_BAND, LIGHT_THEME))
        with self.assertRaises(RenderError) as ctx:
            compose_page(
                make_background(self.root / "bg.png"), spec, self.root / "page.png",
                render_receipt_path=make_receipt(self.root / "bg.png"),
                resolved_design=self.resolved, resolver=_StubResolver({"a": self.asset}),
            )
        self.assertEqual(ctx.exception.reason_code, "composite_design_stale")

    def test_non_design_input_rejected(self):
        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_TITLE_BAND, LIGHT_THEME))
        with self.assertRaises(RenderError):
            compose_page(
                make_background(self.root / "bg.png"), spec, self.root / "page.png",
                render_receipt_path=make_receipt(self.root / "bg.png"),
                resolved_design={"entity": "something-else"},
                resolver=_StubResolver({"a": self.asset}),
            )


class CompositeQualityEventTest(unittest.TestCase):
    """常规 composite 与 TF-2 事件分开记录：composite 观察不携带 TF 触发。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "run.json").write_text(json.dumps({"run_id": "r"}))

    def test_composite_observation_is_not_a_tf_trigger_event(self):
        from leo_ppt_generator import quality_metrics as metrics

        metrics.start_observation(self.root, window="production", target_pages=["1"],
                                  phase="after-authorization")
        metrics.record_runtime_tf(self.root, page="1", operation_id="op-comp-1",
                                  triggers=[], generation_method="composite", complete=True)
        metrics.record_runtime_tf(self.root, page="1", operation_id="op-tf2-1",
                                  triggers=["TF-2"], generation_method="image", complete=True)
        events = [json.loads(line) for line in
                  (self.root / "observability/quality-events.jsonl").read_text(encoding="utf-8").splitlines()]
        composite_rows = [e for e in events if e["payload"].get("generation_method") == "composite"]
        tf2_rows = [e for e in events if "TF-2" in (e["payload"].get("triggers") or [])]
        self.assertEqual(len(composite_rows), 1)
        self.assertEqual(composite_rows[0]["payload"]["triggers"], [])
        self.assertEqual(len(tf2_rows), 1)
        self.assertNotEqual(composite_rows[0]["event_id"], tf2_rows[0]["event_id"])


class CompositeRealRenderChainTest(CompositePipelineBase, browser_test_case()):
    """真浏览器链路：真实 render page sidecar → 合成 → 校验。

    这是机制与真实渲染 receipts 的接缝测试；不代表 R-70 阶段视觉验收。
    """

    def test_real_render_receipt_drives_composition(self):
        from leo_ppt_generator.render.page import render_page

        data = self.root / "slide.json"
        data.write_text(json.dumps({
            "title": "合成链路背景页",
            "bullets": ["背景层来自真实 render receipt"],
            "page_no": 1,
        }), encoding="utf-8")
        background = self.root / "bg.png"
        render_page("body-basic", data, background)
        receipt = background.with_name("bg.png.render.json")
        self.assertTrue(receipt.is_file(), "真实渲染必须落盘 provenance sidecar")
        spec = write_spec(self.root, "spec.json", self.themed(LAYOUT_SIDE_COLUMN, LIGHT_THEME))
        result = compose_page(background, spec, self.root / "page.png",
                              render_receipt_path=receipt)
        self.assertEqual(result["background"]["backend"], "render:html")
        report = verify_composite(background, spec,
                                  self.root / "page.text-layer.png", self.root / "page.png",
                                  render_receipt_path=receipt)
        self.assertEqual(report["status"], "verified")


if __name__ == "__main__":
    unittest.main()
