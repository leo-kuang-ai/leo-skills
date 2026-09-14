"""确定性注入链(templates.py)的合同测试。

覆盖 2026-08-29 大师评审团 R13 决议的六项修复:字段解析双冒号形态、
分隔行跳过、空骨架/歧义/原则文档误命中的 fail-fast、双 json 块提取、
风格判定收紧,以及网格物化(materialize_composition)。

U10 切换后 load_layout 走新库协议（resolver + canonical/layouts notes.md），
fixture 用临时 template-library bundle 注入。
"""

from __future__ import annotations

import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator import templates  # noqa: E402
from leo_ppt_generator.asset_resolver import AssetNotFoundError, StaleCatalogError  # noqa: E402


def _write_notes(bundle: Path, slug: str, title: str, skeleton: str = "2×3 网格") -> Path:
    layout_dir = bundle / "template-library" / "canonical" / "layouts" / slug
    layout_dir.mkdir(parents=True, exist_ok=True)
    body = (
        f"# 版式：{title}\n\n"
        f"**用途:** 测试用途\n\n"
        f"**适用内容类型:** 测试内容\n\n"
        f"**骨架:** {skeleton}\n\n"
        f"**关键类:** .test-class\n\n"
        f"**动效 recipe:** fade\n"
    )
    notes = layout_dir / "notes.md"
    notes.write_text(body, encoding="utf-8")
    return notes


@contextlib.contextmanager
def _temp_library(*slugs_need_entity: str):
    """临时 template-library bundle（LEO_PPT_BUNDLE 注入，resolver 优先命中）。"""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp)
        library = bundle / "template-library"
        (library / "canonical" / "layouts").mkdir(parents=True)
        (library / "library.json").write_text(json.dumps({
            "schema_version": 1, "kind": "template-library", "library_id": "builtin",
            "zones": {"canonical": "c", "reference": "r", "governance": "g",
                      "catalog": "k", "evidence": "e"},
            "reserved_directory_names": [],
        }), encoding="utf-8")
        with mock.patch.dict("os.environ", {"LEO_PPT_BUNDLE": str(bundle)}):
            yield bundle


class FieldParsingTests(unittest.TestCase):
    def test_field_accepts_colon_outside_asterisks(self):
        text = "**骨架**: 左右分栏 5/11"
        self.assertEqual(templates._field(text, "**骨架**"), "左右分栏 5/11")

    def test_field_accepts_colon_inside_asterisks(self):
        text = "**骨架:** 左右分栏 5/11"
        self.assertEqual(templates._field(text, "**骨架**"), "左右分栏 5/11")

    def test_field_fullwidth_colon(self):
        text = "**骨架**：左右分栏 5/11"
        self.assertEqual(templates._field(text, "**骨架**"), "左右分栏 5/11")

    def test_table_skips_separator_rows(self):
        text = "| 线条 | 直角 |\n| --- | --- |\n| 纹理 | 纸纹 |"
        self.assertEqual(templates._table(text), {"线条": "直角", "纹理": "纸纹"})


class BrandResolutionTests(unittest.TestCase):
    def test_brand_stale_catalog_does_not_fallback_to_legacy_file(self):
        with mock.patch.object(templates.AssetResolver, "require",
                               side_effect=StaleCatalogError("stale_catalog")):
            with self.assertRaises(StaleCatalogError):
                templates._brand_candidates("anthropic")

    def test_brand_missing_asset_keeps_compatibility_fallback(self):
        with mock.patch.object(templates.AssetResolver, "require",
                               side_effect=AssetNotFoundError("asset_not_found")):
            with mock.patch.object(templates, "_styles_root", return_value=Path("/legacy")):
                candidates = templates._brand_candidates("anthropic", home=Path("/home"))
        self.assertEqual(candidates, [Path("/home/brands/anthropic.md"),
                                      Path("/legacy/10_品牌身份/anthropic.md")])


class TemplateIndexTests(unittest.TestCase):
    def test_list_templates_derives_axis_names_from_resolver_entities(self):
        entities = [
            {"kind": "axis", "path":
             "canonical/axes/rendering/rendering-demo/manifest.json"},
            {"kind": "axis", "path":
             "canonical/axes/argument/argument-学术五拍/manifest.json"},
            {"kind": "axis", "path":
             "canonical/axes/infographic/infographic-漏斗图/manifest.json"},
            {"kind": "layout", "name": "测试版式"},
        ]
        resolver = SimpleNamespace(entities=entities)
        with mock.patch.object(templates, "AssetResolver", return_value=resolver):
            result = templates.list_templates()
        self.assertEqual(result["renderings"], ["demo"])
        self.assertEqual(result["modes"], ["学术五拍"])
        self.assertEqual(result["image_types"], ["漏斗图"])
        self.assertEqual(result["layouts"], ["测试版式"])


class LayoutResolutionTests(unittest.TestCase):
    def test_load_layout_rejects_rule_documents(self):
        # P0 是选版式原则文档，不是版式实体：负例保持（layout_not_found）。
        with self.assertRaises(templates.TemplateError) as ctx:
            templates.load_layout("P0")
        self.assertIn("layout_not_found", str(ctx.exception))

    def test_p_code_matches_exactly_not_by_substring(self):
        result = templates.load_layout("P1")
        self.assertEqual(result["name"], "P1 · cover-pro")
        self.assertEqual(result["purpose"], "cover")

    def test_load_layout_rejects_ambiguous_substring(self):
        with _temp_library() as bundle:
            _write_notes(bundle, "p51-a", "P51 A Alpha")
            _write_notes(bundle, "p51-b", "P51 B Beta")
            # 两个标题都含「P51」子串且均无 resolver 实体 → 歧义列出候选。
            with self.assertRaises(templates.TemplateError) as ctx:
                templates.load_layout("P51")
            msg = str(ctx.exception)
            self.assertIn("P51 A Alpha", msg)
            self.assertIn("P51 B Beta", msg)

    def test_compose_layout_raises_on_empty_skeleton(self):
        with _temp_library() as bundle:
            _write_notes(bundle, "p61-empty", "P61 Empty", "")
            with self.assertRaises(templates.TemplateError) as ctx:
                templates.compose_layout("P61")
        self.assertIn("layout_field_empty", str(ctx.exception))

    def test_resolver_name_hit_wins_over_title_substring(self):
        # 新库等价断言：resolver 名称命中优先于 notes 标题子串匹配。
        result = templates.load_layout("Cover")
        self.assertEqual(result["name"], "P1 · cover-pro")
        self.assertEqual(result["purpose"], "cover")

    def test_layout_alias_can_be_loaded_when_template_shares_the_slug(self):
        # body-basic 同时存在 template 与 layout；kind 过滤必须在名称优先前生效。
        result = templates.load_layout("body-basic")
        self.assertEqual(result["name"], "body-basic · 要点正文")
        self.assertIn("problem-process-result-next steps", result["skeleton"])
        composed = templates.compose_layout("body-basic")
        self.assertEqual(composed["purpose"], "content")
        self.assertEqual(composed["skeleton"], result["skeleton"])

    def test_layout_and_brand_use_explicit_custom_home(self):
        with _temp_library() as bundle:
            home = bundle / "user-home"
            user_library = home / "template-library"
            (user_library / "canonical" / "layouts" / "custom-layout").mkdir(parents=True)
            (user_library / "canonical" / "brands" / "acme").mkdir(parents=True)
            (user_library / "library.json").write_text(json.dumps({
                "schema_version": 1, "kind": "template-library", "library_id": "user",
                "zones": {"canonical": "c", "reference": "r", "governance": "g",
                          "catalog": "k", "evidence": "e"},
                "reserved_directory_names": [],
            }), encoding="utf-8")
            (user_library / "canonical" / "layouts" / "custom-layout" / "layout.json").write_text(
                json.dumps({
                    "schema_version": 1, "entity": "layout-profile",
                    "asset_id": "user:layout:custom-layout", "name": "Custom Layout",
                    "aliases": ["custom-layout"],
                    "canvas": {"width": 1280, "height": 720, "units": "logical-px"},
                    "page_role": "content", "layout_type": "fixed-regions",
                    "slots": {"body": {"region": "content", "max_chars": 40}},
                    "renderer_support": {"render:html": None, "image": "custom skeleton"},
                }, ensure_ascii=False), encoding="utf-8")
            (user_library / "canonical" / "brands" / "acme" / "brand.json").write_text(
                json.dumps({
                    "schema_version": 1, "entity": "brand-identity",
                    "asset_id": "user:brand:acme", "name": "acme",
                    "colors": {"primary": "#123456", "accent": "#654321"},
                    "typography": "Inter", "tone": "precise",
                    "verification": {"verified_at": "2026-09-09"},
                }, ensure_ascii=False), encoding="utf-8")
            layout = templates.load_layout("custom-layout", home=home)
            brand = templates.load_brand("acme", home=home)
        self.assertEqual(layout["name"], "Custom Layout")
        self.assertEqual(brand["primary"], "#123456")


class StyleBriefExtractionTests(unittest.TestCase):
    def test_double_json_block_uses_first_block(self):
        content = (
            "# 风格\n\n```json\n{\"visual_direction\": \"first\"}\n```\n\n"
            "中间散文\n\n```json\n{\"visual_direction\": \"second\"}\n```\n"
        )
        fake = {"name": "x", "source": "builtin", "path": "/x", "content": content, "sha256": ""}
        with mock.patch.object(templates, "load_style", return_value=fake):
            composed = templates.compose_style("x")
        self.assertEqual(composed["visual_direction"], "first")

    def test_single_block_still_extracts_first_block(self):
        content = "# 风格\n\n```json\n{\"visual_direction\": \"v\", \"typography\": \"t\"}\n```\n"
        fake = {"name": "x", "source": "builtin", "path": "/x", "content": content, "sha256": ""}
        with mock.patch.object(templates, "load_style", return_value=fake):
            composed = templates.compose_style("x")
        self.assertEqual(composed["visual_direction"], "v")


class MaterializeCompositionTests(unittest.TestCase):
    def test_materialize_strips_css_and_translates_units(self):
        layout = {
            "name": "P4 Six Cells",
            "skeleton": "kicker 上方 + 2×3 网格 .cell-6,字号 min(11.6vw,19vh)",
        }
        hint = templates.materialize_composition(layout)
        self.assertNotIn(".cell-6", hint)
        self.assertNotIn("min(11.6vw,19vh)", hint)
        self.assertIn("2×3", hint)

    def test_compose_layout_materialize_flag_adds_hint(self):
        with _temp_library() as bundle:
            _write_notes(bundle, "p81-grid", "P81 Grid", "2×3 网格 .cell-6")
            plain = templates.compose_layout("P81")
            materialized = templates.compose_layout("P81", materialize=True)
        self.assertNotIn("composition_hint", plain)
        self.assertIn("composition_hint", materialized)
        self.assertNotIn(".cell-6", materialized["composition_hint"])


class DeterminismGuardTests(unittest.TestCase):
    """合法输入的输出必须与仓库内嵌 golden 逐字节一致(确定性保护)。

    golden 于 2026-08-29 内容升级(渲染守卫句/瑞士极简措辞/P30)后固化于
    tests/fixtures/render_golden.json;再次有意变更内容时随同更新 fixture。
    """

    GOLDEN = Path(__file__).resolve().parent / "fixtures" / "render_golden.json"

    def _assert_matches_golden(self, key: str, composed: dict) -> None:
        golden = json.loads(self.GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(
            json.dumps(composed, ensure_ascii=False, sort_keys=True, default=str),
            json.dumps(golden[key], ensure_ascii=False, sort_keys=True, default=str),
        )

    def test_builtin_style_output_matches_golden(self):
        self._assert_matches_golden(
            "style:minimal", templates.compose_style("极简风", mode="结论先行金字塔")
        )

    def test_builtin_mckinsey_style_matches_golden(self):
        self._assert_matches_golden(
            "style:mckinsey", templates.compose_style("麦肯锡咨询风", mode="故事弧")
        )

    def test_builtin_layout_output_matches_golden(self):
        self._assert_matches_golden(
            "layout:P6", templates.compose_layout("P6", image_type="漏斗图")
        )

    def test_new_layout_materialize_matches_golden(self):
        self._assert_matches_golden(
            "layout:P30", templates.compose_layout("P30", materialize=True)
        )

    def test_new_layout_p31_matches_golden(self):
        self._assert_matches_golden("layout:P31", templates.compose_layout("P31"))


if __name__ == "__main__":
    unittest.main()
