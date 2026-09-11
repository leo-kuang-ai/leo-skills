#!/usr/bin/env python3
"""content_projection.py 单元测试（dashi 集成 K2/K3、U3）：角色规范化唯一入口 /
候选硬资格（角色、backend、容量、媒体、必需覆盖、数值覆盖）/ compare 边数
拒绝与两组合法（AE3）/ 品牌字体改变上下文摘要（K2 同源）/ 绑定摘要确定性 /
隐藏必需项不可过关 / image 预检不冒充成品保真 / 物化复用同一绑定。"""
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
    compile_content_pack,
)
from leo_ppt_generator.content_projection import (  # noqa: E402
    ProjectionError,
    materialize_html,
    materialize_image_prompt,
    materialize_page,
    normalize_page_role,
    precompile_binding,
)

MASTER = """# 母版 v1
confirmation: confirmed（测试基线）

## S1 封面
page_id: pg-11111111
角色：封面
argument_role: 开场
- 标题：增长质量是本季主叙事
- 要点 1：三大指标全面向好
视觉行：要点1→巨字卡
- 备注：speaker_script: 开场 30 秒

## S2 对比
page_id: pg-22222222
角色：对比·多维
argument_role: 论据
- 标题：两条路线的交付差异
- 要点 1：甲路线部署 6 周
- 要点 2：乙路线部署 1 周
对照侧: 甲路线｜部署 6 周｜甲路线部署 6 周
对照侧: 乙路线｜部署 1 周｜乙路线部署 1 周
视觉行：要点1→左栏 要点2→右栏
- 备注：speaker_script: 强调对比口径

## S3 台账
page_id: pg-33333333
角色：流程·路径
argument_role: 数据
- 标题：核心指标 1.24 亿元
- 要点 1：营收 1.24 亿元，环比 +18%
- 要点 2：净利率 12%
- 要点 3：留存率 90%
视觉行：要点1→KPI 塔 要点2→指标卡 要点3→指标卡
- 备注：speaker_script: 数据页

## S4 图页
page_id: pg-44444444
角色：证据·实拍
argument_role: 证据
- 标题：现场部署实拍
- 要点 1：交付现场实拍
视觉行：图[F1] 模式:preserve 状态:vision-reviewed 焦点:部署环境 | 承载:全幅图 | 服务:实拍证据 | 避免误读:非摆拍
- 备注：speaker_script: 实拍说明

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S3 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
"""

STYLE_QUERY = "finance-navy"


def build_pack():
    return compile_content_pack(MASTER, master_path="content/deck-master-v1.md",
                                master_revision="v1")


def page_of(pack, page_id):
    return next(p for p in pack["pages"] if p["page_id"] == page_id)


class RoleNormalizationTests(unittest.TestCase):
    def test_known_role_maps_to_page_types(self):
        self.assertEqual(normalize_page_role("封面"), ["cover"])
        self.assertIn("content", normalize_page_role("对比·多维"))

    def test_unknown_role_returns_none(self):
        self.assertIsNone(normalize_page_role("不存在的角色"))
        self.assertIsNone(normalize_page_role(None))

    def test_suggest_layout_consumes_same_mapping(self):
        sys.path.insert(0, str(PKG_ROOT / "scripts"))
        import suggest_layout
        self.assertIs(suggest_layout.ROLE_PAGE_TYPES,
                      sys.modules["leo_ppt_generator.content_projection"].ROLE_PAGE_TYPES)


class PrecompileEligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = build_pack()
        cls.context = templates.resolve_design_context(STYLE_QUERY)

    def precompile(self, page_id, layout, **kwargs):
        return precompile_binding(page_of(self.pack, page_id), self.context, layout,
                                  content_digest=self.pack["content_digest"],
                                  numbers=self.pack["numbers"], **kwargs)

    def test_body_basic_bullets_qualified_and_deterministic(self):
        first = self.precompile("pg-33333333", "body-basic")
        second = self.precompile("pg-33333333", "body-basic")
        self.assertTrue(first["eligibility"]["qualified"],
                        first["eligibility"]["hard_failures"])
        self.assertEqual(first["binding_digest"], second["binding_digest"])
        self.assertEqual(first["context_digest"], self.context["context_digest"])
        self.assertEqual(first["layout_id"], "builtin:layout:body-basic")
        self.assertEqual(first["template_id"], "builtin:template:body-basic")
        self.assertEqual(len(first["item_ids"]), 3)  # 3 要点；claim 非内容项

    def test_points_over_max_hard_excluded(self):
        text = MASTER.replace("- 要点 3：留存率 90%\n", (
            "- 要点 3：留存率 90%\n- 要点 4：A\n- 要点 5：B\n"
            "- 要点 6：C\n- 要点 7：D\n"))
        pack = compile_content_pack(text, master_path="content/deck-master-v1.md")
        binding = precompile_binding(
            page_of(pack, "pg-33333333"), self.context, "body-basic",
            content_digest=pack["content_digest"], numbers=pack["numbers"])
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertTrue(any("points_over_max" in f
                            for f in binding["eligibility"]["hard_failures"]))

    def test_cover_text_overflow_hard_excluded(self):
        text = MASTER.replace("- 标题：增长质量是本季主叙事",
                              "- 标题：" + "长" * 99999)
        pack = compile_content_pack(text, master_path="content/deck-master-v1.md")
        binding = precompile_binding(
            page_of(pack, "pg-11111111"), self.context, "cover-basic",
            content_digest=pack["content_digest"], numbers=pack["numbers"])
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertTrue(any("text_overflow" in f
                            for f in binding["eligibility"]["hard_failures"]))

    def test_role_mismatch_and_unknown_role_excluded(self):
        binding = self.precompile("pg-11111111", "body-basic")  # cover 页配 content 版式
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertTrue(any("role_mismatch" in f
                            for f in binding["eligibility"]["hard_failures"]))
        pack = build_pack()
        page = dict(page_of(pack, "pg-33333333"), narrative_role="神秘角色")
        binding = precompile_binding(page, self.context, "body-basic",
                                     content_digest=pack["content_digest"],
                                     numbers=pack["numbers"])
        self.assertTrue(any("role_unknown" in f
                            for f in binding["eligibility"]["hard_failures"]))

    def test_compare_sides_two_qualified_one_and_three_rejected(self):
        two = self.precompile("pg-22222222", "compare")
        self.assertTrue(two["eligibility"]["qualified"],
                        two["eligibility"]["hard_failures"])
        for count in (1, 3):
            with self.subTest(sides=count):
                markers = {
                    1: "对照侧: 甲路线｜部署 6 周｜甲路线部署 6 周\n",
                    3: ("对照侧: 甲路线｜部署 6 周｜甲路线部署 6 周\n"
                        "对照侧: 乙路线｜部署 1 周｜乙路线部署 1 周\n"
                        "对照侧: 丙路线｜部署 3 周｜丙路线部署 3 周\n"),
                }[count]
                text = MASTER.replace(
                    "对照侧: 甲路线｜部署 6 周｜甲路线部署 6 周\n"
                    "对照侧: 乙路线｜部署 1 周｜乙路线部署 1 周\n", markers)
                pack = compile_content_pack(text, master_path="content/deck-master-v1.md")
                binding = precompile_binding(
                    page_of(pack, "pg-22222222"), self.context, "compare",
                    content_digest=pack["content_digest"], numbers=pack["numbers"])
                self.assertFalse(binding["eligibility"]["qualified"])
                self.assertTrue(
                    any("sides_count" in f for f in binding["eligibility"]["hard_failures"]),
                    binding["eligibility"]["hard_failures"])

    def test_compare_without_master_marker_rejected_not_guessed(self):
        text = MASTER.replace("对照侧: 甲路线｜部署 6 周｜甲路线部署 6 周\n", "").replace(
            "对照侧: 乙路线｜部署 1 周｜乙路线部署 1 周\n", "")
        pack = compile_content_pack(text, master_path="content/deck-master-v1.md")
        binding = precompile_binding(
            page_of(pack, "pg-22222222"), self.context, "compare",
            content_digest=pack["content_digest"], numbers=pack["numbers"])
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertTrue(any("required_item_unmapped" in f and "对照侧" in f
                            for f in binding["eligibility"]["hard_failures"]))

    def test_figure_without_media_capability_rejected(self):
        # body-basic 无媒体槽：图行必需项无落点 → 硬失败。
        binding = self.precompile("pg-44444444", "body-basic")
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertTrue(any("required_item_unmapped" in f
                            for f in binding["eligibility"]["hard_failures"]))

    def test_number_coverage_missing_rejected(self):
        # 数值只存在于 JSON（登记表）而不在任何绑定显示文本 → 拒绝。
        text = MASTER.replace("- 要点 1：营收 1.24 亿元，环比 +18%",
                              "- 要点 1：营收创新高，环比 +18%").replace(
            "- 标题：核心指标 1.24 亿元", "- 标题：核心指标创新高")
        pack = compile_content_pack(text, master_path="content/deck-master-v1.md")
        binding = precompile_binding(
            page_of(pack, "pg-33333333"), self.context, "body-basic",
            content_digest=pack["content_digest"], numbers=pack["numbers"])
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertTrue(any("number_coverage_missing" in f
                            for f in binding["eligibility"]["hard_failures"]))

    def test_font_override_changes_context_and_binding_digest(self):
        # K2：品牌/字体覆盖改变 → 上下文摘要与绑定摘要一致变化（同一快照）。
        branded = templates.resolve_design_context(
            STYLE_QUERY, font_overrides={"body.size": 20})
        self.assertNotEqual(branded["context_digest"], self.context["context_digest"])
        base = self.precompile("pg-33333333", "body-basic")
        variant = precompile_binding(page_of(self.pack, "pg-33333333"), branded,
                                     "body-basic",
                                     content_digest=self.pack["content_digest"],
                                     numbers=self.pack["numbers"])
        self.assertNotEqual(base["binding_digest"], variant["binding_digest"])
        self.assertEqual(variant["context_digest"], branded["context_digest"])

    def test_page_reorder_keeps_item_binding_stable(self):
        # 物理换序（S3 块移到 S1 前）：未修改页 item_ids 与绑定一致，
        # 展示 number 跟随新顺序。
        s1_start, s1_end = MASTER.index("## S1 封面"), MASTER.index("## S2 对比")
        s3_start, s3_end = MASTER.index("## S3 台账"), MASTER.index("## S4 图页")
        s1_block = MASTER[s1_start:s1_end]
        s3_block = MASTER[s3_start:s3_end]
        reordered = MASTER.replace(s3_block, "").replace(s1_block, s3_block + s1_block)
        pack2 = compile_content_pack(reordered, master_path="content/deck-master-v1.md")
        binding2 = precompile_binding(
            page_of(pack2, "pg-33333333"), self.context, "body-basic",
            content_digest=pack2["content_digest"], numbers=pack2["numbers"])
        base = self.precompile("pg-33333333", "body-basic")
        self.assertTrue(binding2["eligibility"]["qualified"],
                        binding2["eligibility"]["hard_failures"])
        self.assertEqual(base["item_ids"], binding2["item_ids"])
        self.assertEqual(binding2["number"], 1)  # 展示顺序随换序更新


class MaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = build_pack()
        cls.context = templates.resolve_design_context(STYLE_QUERY)

    def test_html_materialization_uses_bound_values(self):
        binding = precompile_binding(page_of(self.pack, "pg-33333333"),
                                     self.context, "body-basic",
                                     content_digest=self.pack["content_digest"],
                                     numbers=self.pack["numbers"])
        data = materialize_html(binding, page_of(self.pack, "pg-33333333"))
        self.assertEqual(data["title"], "核心指标 1.24 亿元")
        self.assertEqual(data["bullets"], ["营收 1.24 亿元，环比 +18%",
                                           "净利率 12%",
                                           "留存率 90%"])
        self.assertEqual(data["page_no"], 3)

    def test_compare_materialization_carries_sides(self):
        binding = precompile_binding(page_of(self.pack, "pg-22222222"),
                                     self.context, "compare",
                                     content_digest=self.pack["content_digest"],
                                     numbers=self.pack["numbers"])
        data = materialize_html(binding, page_of(self.pack, "pg-22222222"))
        self.assertEqual(len(data["sides"]), 2)
        self.assertEqual(data["sides"][0]["label"], "甲路线")
        self.assertEqual(data["sides"][1]["title"], "部署 1 周")

    def test_unqualified_binding_cannot_materialize(self):
        text = MASTER.replace("- 标题：增长质量是本季主叙事",
                              "- 标题：" + "长" * 99999)
        pack = compile_content_pack(text, master_path="content/deck-master-v1.md")
        binding = precompile_binding(page_of(pack, "pg-11111111"), self.context,
                                     "cover-basic",
                                     content_digest=pack["content_digest"],
                                     numbers=pack["numbers"])
        with self.assertRaises(ProjectionError):
            materialize_html(binding, page_of(pack, "pg-11111111"))

    def test_media_value_required_at_execution(self):
        binding = precompile_binding(page_of(self.pack, "pg-44444444"),
                                     self.context, "frame-shot",
                                     content_digest=self.pack["content_digest"],
                                     numbers=self.pack["numbers"])
        self.assertTrue(binding["eligibility"]["qualified"],
                        binding["eligibility"]["hard_failures"])
        with self.assertRaisesRegex(ProjectionError, "媒体内容缺失"):
            materialize_html(binding, page_of(self.pack, "pg-44444444"))
        data = materialize_html(binding, page_of(self.pack, "pg-44444444"),
                                media={"F1": "data:image/png;base64,QUJD"})
        self.assertEqual(data["image_src"], "data:image/png;base64,QUJD")

    def test_image_prompt_is_precheck_not_fidelity(self):
        design = templates.compose_design(
            STYLE_QUERY, pages=[{"page_no": 3, "page_role": "data",
                                 "layout": "body-basic", "slots": {}}])
        binding = precompile_binding(page_of(self.pack, "pg-33333333"),
                                     self.context, "body-basic", backend="image",
                                     content_digest=self.pack["content_digest"],
                                     numbers=self.pack["numbers"])
        self.assertTrue(binding["eligibility"]["qualified"],
                        binding["eligibility"]["hard_failures"])
        result = materialize_image_prompt(binding, page_of(self.pack, "pg-33333333"),
                                          design)
        self.assertIn("营收 1.24 亿元，环比 +18%", result["required_text"])
        # required_text 是生成合同输入，报告口径不宣称最终图片文字保真。
        self.assertNotIn("verified", result)

    def test_materialize_page_dispatches_by_backend(self):
        binding = precompile_binding(page_of(self.pack, "pg-33333333"),
                                     self.context, "body-basic",
                                     content_digest=self.pack["content_digest"],
                                     numbers=self.pack["numbers"])
        out = materialize_page(binding, page_of(self.pack, "pg-33333333"))
        self.assertEqual(out["backend"], "render:html")
        self.assertIn("bullets", out["data"])


if __name__ == "__main__":
    unittest.main()


class ReviewFixRegressionTests(unittest.TestCase):
    """独立审查修复回归（lfg-dashi-1788979338）：表格数值覆盖与媒体多槽。"""

    MASTER_TABLE = """# 母版 v1
confirmation: confirmed（测试基线）

## S1 台账
page_id: pg-aaaa1111
角色：指标·计分榜
argument_role: 数据
- 标题：指标对照表
- 要点 1：三行指标对基准
表列: 指标,本季,基准
表行: 营收｜1.24 亿元｜1.10 亿元
表行: 净利率｜12%｜10%
视觉行：要点1→表格
- 备注：口播

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S1 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
| 12% | S1 | Q3 财报 | 净利率 | 2026Q3 | 百分点 | 引用 | yes | 2026-10-28 |
"""

    def test_numbers_only_in_table_cells_keep_spec_table_qualified(self):
        from leo_ppt_generator.layout_selection import qualified_pool
        pack = compile_content_pack(self.MASTER_TABLE,
                                    master_path="content/deck-master-v1.md")
        context = templates.resolve_design_context(STYLE_QUERY)
        binding = precompile_binding(page_of(pack, "pg-aaaa1111"), context,
                                     "p25-spec-table",
                                     content_digest=pack["content_digest"],
                                     numbers=pack["numbers"])
        self.assertTrue(binding["eligibility"]["qualified"],
                        binding["eligibility"]["hard_failures"])
        data = materialize_html(binding, page_of(pack, "pg-aaaa1111"))
        self.assertEqual(data["rows"][0], ["营收", "1.24 亿元", "1.10 亿元"])

    def test_multi_figure_media_materializes_by_index(self):
        # 双图页：媒体字段 count_max≥2 时按索引填充不越界（frame-shot 单图
        # 之外的场景用伪造双图绑定的 slot_map 直接验证物化路径）。
        from leo_ppt_generator.content_projection import compute_binding_digest
        pack = compile_content_pack(
            self.MASTER_TABLE.replace(
                "- 要点 1：三行指标对基准",
                "- 要点 1：三行指标对基准\n图[F1] 模式:preserve 状态:vision-reviewed"
                " 焦点:现场 | 承载:全幅 | 服务:证据 | 避免误读:非摆拍\n"
                "图[F2] 模式:preserve 状态:metadata-reviewed 焦点:细节"
                " | 承载:特写 | 服务:证据 | 避免误读:非摆拍"),
            master_path="content/deck-master-v1.md")
        page = page_of(pack, "pg-aaaa1111")
        context = templates.resolve_design_context(STYLE_QUERY)
        binding = precompile_binding(page, context, "p25-spec-table",
                                     content_digest=pack["content_digest"],
                                     numbers=pack["numbers"])
        binding = dict(binding)
        binding["slot_map"] = {**binding["slot_map"],
                               "images[0]": {"source": "figure", "item_id": "F1"},
                               "images[1]": {"source": "figure", "item_id": "F2"}}
        # 回归目标仅物化路径：媒体槽为伪造注入，资格按已覆盖论通过。
        binding["eligibility"] = {**binding["eligibility"],
                                  "qualified": True, "hard_failures": []}
        data = materialize_html(binding, page,
                                media={"F1": "data:image/png;base64,QQ==",
                                       "F2": "data:image/png;base64,Qg=="})
        self.assertEqual(data["images"], ["data:image/png;base64,QQ==",
                                          "data:image/png;base64,Qg=="])


class EligibilityBranchTests(unittest.TestCase):
    """硬资格三分支覆盖（独立审查 testing finding）。"""

    @classmethod
    def setUpClass(cls):
        cls.pack = build_pack()
        cls.context = templates.resolve_design_context(STYLE_QUERY)

    def test_backend_unsupported_excludes(self):
        binding = precompile_binding(
            page_of(self.pack, "pg-33333333"), self.context, "body-basic",
            backend="vector",
            content_digest=self.pack["content_digest"], numbers=self.pack["numbers"])
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertTrue(any("backend_unsupported" in f
                            for f in binding["eligibility"]["hard_failures"]))

    def test_points_below_min_excludes(self):
        text = MASTER.replace("- 要点 2：净利率 12%\n- 要点 3：留存率 90%\n", "")
        pack = compile_content_pack(text, master_path="content/deck-master-v1.md")
        binding = precompile_binding(
            page_of(pack, "pg-33333333"), self.context, "body-basic",
            content_digest=pack["content_digest"], numbers=pack["numbers"])
        self.assertTrue(any("points_below_min" in f
                            for f in binding["eligibility"]["hard_failures"]))

    def test_media_over_capacity_excludes(self):
        text = MASTER.replace(
            "- 备注：speaker_script: 实拍说明",
            "图[F2] 模式:preserve 状态:vision-reviewed 焦点:备图 | 承载:特写 | 服务:证据 | 避免误读:非摆拍\n"
            "- 备注：实拍说明")
        pack = compile_content_pack(text, master_path="content/deck-master-v1.md")
        binding = precompile_binding(
            page_of(pack, "pg-44444444"), self.context, "frame-shot",
            content_digest=pack["content_digest"], numbers=pack["numbers"])
        self.assertTrue(any("media_over_capacity" in f
                            for f in binding["eligibility"]["hard_failures"]))
