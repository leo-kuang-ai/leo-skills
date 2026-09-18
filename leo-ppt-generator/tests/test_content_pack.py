#!/usr/bin/env python3
"""content_pack.py 单元测试（dashi 集成 K1/U2）：稳定页身份与确定性编译 /
插删换序不改变未修改页身份 / 同数不同单位期间不合并 / legacy 母版拒绝编译 /
部分身份与重复身份报错 / 手改内容包被拒 / engineering 不进 notes /
缺字段的登记表行与图行回母版补齐 / 一次性身份写入幂等 / schema 校验。"""
import json
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = PKG_ROOT / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.content_pack import (  # noqa: E402
    ContentPackError,
    compile_content_pack,
    content_digest,
    parse_master,
    propose_page_id_stamping,
    verify_content_pack,
)

try:
    import jsonschema
except ImportError:  # pragma: no cover — 依赖缺失时跳过 schema 断言
    jsonschema = None

SCHEMA_PATH = RUNTIME_SRC / "leo_ppt_generator" / "schemas" / "page-content-pack-v1.schema.json"

MASTER_V3 = """# 母版 v3
confirmation: confirmed（测试基线）
decision_source: user-delegated
goal: 向管理层汇报季度增长质量
audience: 管理层
delivery_tier: standard

## S1 封面
page_id: pg-11111111
argument_role: 开场
- 标题：增长质量是本季主叙事
- 要点 1：三大指标全面向好
视觉行：要点1→巨字卡
- 备注：speaker_script: 开场 30 秒，先给结论

## S2 财务
page_id: pg-22222222
argument_role: 支柱1
- 标题：营收 1.24 亿元创单季新高
- 要点 1：环比 +18%【引用|src:Q3 财报#rev】
- 要点 2：净利率 12%
视觉行：图[F1] 模式:preserve 状态:vision-reviewed 焦点:核心指标趋势 | 承载:全幅图 | 服务:环比断言 | 避免误读:不含一次性损益
- 备注：speaker_script: 强调环比口径
engineering: 失败路径——素材缺失时降级为文字卡

## S3 结论
page_id: pg-33333333
argument_role: 回报
- 标题：增长质量可延续
- 要点 1：现金流同步改善
视觉行：要点1→结论条
- 备注：口播 10 秒

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
| 1.24 亿元 | S2 | Q3 财报 | 母公司 | 2025Q3 | 人民币元 | 引用 | yes | 2025-10-28 |
| 18% | S2 | Q3 财报 | 环比 | 2026Q3 | 百分点 | 引用 | yes | 2026-10-28 |

## 术语表
| 术语 | 缩写 | 首现页 |
| --- | --- | --- |
| 智能客服 | — | S2 |
"""


def compile_master(text=MASTER_V3, **kwargs):
    return compile_content_pack(text, master_path="content/deck-master-v3.md",
                                master_revision="v3", **kwargs)


class ContentPackCompileTests(unittest.TestCase):
    def test_compiles_with_stable_identity_and_deck_meta(self):
        pack = compile_master()
        self.assertEqual([p["page_id"] for p in pack["pages"]],
                         ["pg-11111111", "pg-22222222", "pg-33333333"])
        self.assertEqual([p["number"] for p in pack["pages"]], [1, 2, 3])
        self.assertEqual(pack["deck"]["goal"], "向管理层汇报季度增长质量")
        self.assertEqual(pack["deck"]["audience"], "管理层")
        self.assertEqual(pack["source"]["decision_source"], "user-delegated")
        s2 = pack["pages"][1]
        self.assertEqual(s2["claim"], "营收 1.24 亿元创单季新高")
        kinds = [i["kind"] for i in s2["items"]]
        self.assertIn("point", kinds)
        self.assertIn("figure", kinds)
        self.assertIn("number-ref", kinds)

    def test_point_annotations_parsed(self):
        pack = compile_master()
        s2 = pack["pages"][1]
        cited = next(i for i in s2["items"] if "环比" in i.get("text", ""))
        self.assertEqual(cited["evidence_tier"], "引用")
        self.assertEqual(cited["source_ref"], "Q3 财报#rev")

    def test_engineering_isolated_from_speaker_notes(self):
        pack = compile_master()
        s2 = pack["pages"][1]
        self.assertIn("素材缺失", s2["notes"]["engineering"])
        self.assertNotIn("素材缺失", s2["notes"]["speaker_script"] or "")
        # 无 speaker_script 标注的页回退到备注行文本（进 notes 通道）。
        self.assertIn("口播 10 秒", pack["pages"][2]["notes"]["speaker_script"])

    def test_same_value_different_unit_or_period_not_merged(self):
        pack = compile_master()
        values = {(n["value"], n["unit"], n["period"]) for n in pack["numbers"]}
        self.assertEqual(len(pack["numbers"]), 3)
        self.assertIn(("1.24 亿元", "人民币元", "2026Q3"), values)
        self.assertIn(("1.24 亿元", "人民币元", "2025Q3"), values)
        ids = [n["item_id"] for n in pack["numbers"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_deterministic_digest_and_tamper_rejection(self):
        first = compile_master()
        second = compile_master()
        self.assertEqual(first["content_digest"], second["content_digest"])
        verify_content_pack(first)
        tampered = json.loads(json.dumps(first))
        tampered["pages"][0]["claim"] = "被手改的标题"
        with self.assertRaises(ContentPackError):
            verify_content_pack(tampered)

    def test_insert_and_reorder_keep_unchanged_page_identity(self):
        # v4：删除 S2，插入新页 S4，S1/S3 内容不变——未修改页身份不变。
        v4 = MASTER_V3.replace(
            "## S2 财务\npage_id: pg-22222222\n", "## S4 新增页\npage_id: pg-44444444\n"
        ).replace("argument_role: 支柱1", "argument_role: 新增")
        v4 = v4.replace("| 1.24 亿元 | S2 |", "| 1.24 亿元 | S4 |")
        v4 = v4.replace("| 18% | S2 |", "| 18% | S4 |")
        pack4 = compile_master(v4)
        self.assertEqual([p["page_id"] for p in pack4["pages"]],
                         ["pg-11111111", "pg-44444444", "pg-33333333"])
        self.assertEqual([p["number"] for p in pack4["pages"]], [1, 2, 3])
        # v5：整体换序（S3 提前），身份集合不变、number 跟随展示顺序。
        v5 = MASTER_V3.replace("pg-11111111", "pg-tmpswap").replace(
            "pg-33333333", "pg-11111111").replace("pg-tmpswap", "pg-33333333")
        pack5 = compile_master(v5)
        self.assertEqual([p["page_id"] for p in pack5["pages"]],
                         ["pg-33333333", "pg-22222222", "pg-11111111"])

    def test_legacy_master_without_identity_refuses_compile(self):
        legacy = "\n".join(ln for ln in MASTER_V3.splitlines()
                           if not ln.startswith("page_id:"))
        with self.assertRaisesRegex(ContentPackError, "page_id"):
            compile_master(legacy)

    def test_partial_identity_rejected(self):
        partial = MASTER_V3.replace("page_id: pg-22222222\n", "", 1)
        with self.assertRaisesRegex(ContentPackError, "部分页缺 page_id"):
            compile_master(partial)

    def test_duplicate_page_id_rejected(self):
        dup = MASTER_V3.replace("pg-33333333", "pg-11111111")
        with self.assertRaisesRegex(ContentPackError, "重复"):
            compile_master(dup)

    def test_invalid_page_id_format_rejected(self):
        bad = MASTER_V3.replace("pg-11111111", "page-one")
        with self.assertRaisesRegex(ContentPackError, "格式非法"):
            compile_master(bad)

    def test_incomplete_ledger_row_reports_master_location(self):
        broken = MASTER_V3.replace(
            "| 18% | S2 | Q3 财报 | 环比 | 2026Q3 | 百分点 | 引用 | yes | 2026-10-28 |",
            "| 18% | S9 | Q3 财报 | | | | | | |")
        with self.assertRaisesRegex(ContentPackError, "数字登记表行"):
            compile_master(broken)
        unresolvable = MASTER_V3.replace("| 18% | S2 |", "| 18% | S9 |")
        with self.assertRaisesRegex(ContentPackError, "无法解析到母版页块"):
            compile_master(unresolvable)

    def test_incomplete_figure_row_reports_master_location(self):
        broken = MASTER_V3.replace(" | 承载:全幅图 | 服务:环比断言 | 避免误读:不含一次性损益", "")
        with self.assertRaisesRegex(ContentPackError, "图行缺"):
            compile_master(broken)

    def test_missing_title_reports_master_location(self):
        broken = MASTER_V3.replace("- 标题：增长质量可延续\n", "")
        with self.assertRaisesRegex(ContentPackError, "标题"):
            compile_master(broken)

    @unittest.skipIf(jsonschema is None, "jsonschema 未安装")
    def test_compiled_pack_validates_against_schema(self):
        validator = jsonschema.Draft202012Validator(
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        pack = compile_master()
        errors = list(validator.iter_errors(pack))
        self.assertEqual(errors, [e.message for e in errors])


class PageIdStampingTests(unittest.TestCase):
    def test_stamping_is_idempotent_and_enables_compile(self):
        legacy = "\n".join(ln for ln in MASTER_V3.splitlines()
                           if not ln.startswith("page_id:"))
        once = propose_page_id_stamping(legacy)
        twice = propose_page_id_stamping(once)
        self.assertEqual(once, twice)
        parsed = parse_master(once)
        ids = [p["page_id"] for p in parsed["pages"]]
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))
        for pid in ids:
            self.assertRegex(pid, r"^pg-[0-9a-f]{10}$")
        pack = compile_master(once)
        self.assertEqual([p["page_id"] for p in pack["pages"]], ids)

    def test_stamping_preserves_untouched_content(self):
        legacy = "\n".join(ln for ln in MASTER_V3.splitlines()
                           if not ln.startswith("page_id:"))
        stamped = propose_page_id_stamping(legacy)
        for line in legacy.splitlines():
            self.assertIn(line, stamped)
        self.assertEqual(
            len(legacy.splitlines()) + 3, len(stamped.splitlines()))


class DigestHelperTests(unittest.TestCase):
    def test_content_digest_ignores_only_digest_field(self):
        pack = compile_master()
        self.assertEqual(content_digest(pack), pack["content_digest"])
        body = {k: v for k, v in pack.items() if k != "content_digest"}
        self.assertEqual(content_digest(body), pack["content_digest"])


if __name__ == "__main__":
    unittest.main()


class ReviewFixRegressionTests(unittest.TestCase):
    """独立审查修复回归（lfg-dashi-1788979338）。"""

    def test_stamp_survives_interleaved_partial_identity(self):
        # 部分页已带身份且与未带身份页交错：每页恰获一个 id，既有 id 保留。
        legacy = MASTER_V3.replace("page_id: pg-22222222\n", "")
        stamped = propose_page_id_stamping(legacy)
        parsed = parse_master(stamped)
        ids = [p["page_id"] for p in parsed["pages"]]
        self.assertEqual(ids, ["pg-11111111", ids[1], "pg-33333333"])
        self.assertNotEqual(ids[1], "pg-11111111")
        self.assertRegex(ids[1], r"^pg-[0-9a-f]{10}$")
        self.assertEqual(propose_page_id_stamping(stamped), stamped)

    def test_duplicate_page_labels_rejected(self):
        dup = MASTER_V3 + MASTER_V3[MASTER_V3.index("## S3 结论"):MASTER_V3.index("## 数字登记表")]
        with self.assertRaisesRegex(ContentPackError, "重复"):
            compile_master(dup)

    def test_duplicate_appendix_labels_rejected(self):
        text = MASTER_V3.replace(
            "## 数字登记表",
            "## 附 录A\n- 标题：附录\n视觉行：附录条\n- 备注：附录\n\n## 附 录B\n"
            "- 标题：附录二\n视觉行：附录条\n- 备注：附录二\n\n## 数字登记表")
        with self.assertRaisesRegex(ContentPackError, "重复"):
            compile_master(text)

class PageExpressionContractTests(unittest.TestCase):
    def test_expression_rejects_unknown_order_reference(self):
        from leo_ppt_generator.content_pack import compile_page_expression, ContentPackError
        pack = {"pages": [{"page_id": "pg-abc", "items": [{"item_id": "i1"}]}]}
        with self.assertRaises(ContentPackError):
            compile_page_expression(pack, "pg-abc", reading_task="comparison", focus="f", reading_order=["missing"], relation_encoding={"dimensions": ["x"]})
