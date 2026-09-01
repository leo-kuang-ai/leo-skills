#!/usr/bin/env python3
"""deck_template.py 单元测试（R-50 deck 模板化复用）：

save 后模板结构与业务数据剥离 / 登记表列结构保留但数据行剥离 /
无 confirmed 基线 exit 2 / instantiate 草案完备（骨架+指纹清单）/
实例指纹登记 / 无模板 exit 2 / diff-data 三分类正反 / 万亿单位归一
同键沿用 / 缺失项进材料确认清单 / 无实例登记 exit 2 / 非法模板名
exit 2 / save 与 diff 确定性 / 同材料重复 instantiate 幂等 /
确认语义红线恒在场 / --json 结构。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deck_template.py"

CONFIRMED_MASTER = """# 母版
confirmation: confirmed
风格合同: 深蓝商务

## S1 封面
argument_role: 开场
- 标题：增长质量是本季主叙事
- 要点 1：三大指标全面向好
视觉行：要点1→巨字卡（版式 P1）
- 备注：口播 30 秒

## S2 财务
argument_role: 支柱1
- 标题：营收 1.24 亿元创单季新高
- 要点 1：环比 +18%
视觉行：要点1→KPI 塔（版式 P12）
- 备注：引用财报

## S3 展望
argument_role: 支柱2
- 标题：下季度继续提速
视觉行：要点1→结论条（版式 P23）

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
"""

MATERIAL = "本期材料：营收 1.31 亿元，环比 +18%，新增签约客户 42 家，流失率 2.3%。\n"

# 本期母版：登记表含 12400 万元（与材料 1.31 亿不同值）、18%（沿用）、
# 55 家（新增）；42 / 2.3% 未进入母版（缺失）。
NEW_MASTER = """# 母版 v2
confirmation: pending

## S1 封面
argument_role: 开场
- 标题：本季营收再创新高
视觉行：要点1→巨字卡（版式 P1）

## S2 财务
argument_role: 支柱1
- 标题：营收 12400 万元创单季新高
- 要点 1：环比 +18%
视觉行：要点1→KPI 塔（版式 P12）

## S3 展望
argument_role: 支柱2
- 标题：下季度继续提速
视觉行：要点1→结论条（版式 P23）

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
| 18% | S2 | Q3 财报 | 环比 | 2026Q3 | - | 引用 | yes | 2026-10-28 |
| 55 家 | S3 | 经营会 | 新签 | 2026Q3 | 家 | 引用 | yes | 2026-10-28 |
"""


def run(*argv):
    return subprocess.run([sys.executable, str(SCRIPT), *argv],
                          capture_output=True, text=True)


class DeckTemplateFixture(unittest.TestCase):
    """tmp home + confirmed project + instantiated weekly template."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.home = base / "home"
        self.project = base / "proj"
        (self.project / "content").mkdir(parents=True)
        (self.project / "content" / "deck-master-v1.md").write_text(
            CONFIRMED_MASTER, encoding="utf-8")
        self.material = base / "material.md"
        self.material.write_text(MATERIAL, encoding="utf-8")
        r = run("save", str(self.project), "--name", "weekly",
                "--home", str(self.home))
        self.assertEqual(r.returncode, 0, r.stderr)

    def tearDown(self):
        self._tmp.cleanup()


class SaveTest(DeckTemplateFixture):
    def test_save_extracts_skeleton_structure(self):
        tpl = json.loads((self.home / "deck-templates/weekly/template.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(tpl["page_contract"],
                         {"page_count": 3, "page_ids": ["S1", "S2", "S3"]})
        self.assertEqual([p["page_id"] for p in tpl["pages"]],
                         ["S1", "S2", "S3"])
        self.assertEqual([p["argument_role"] for p in tpl["pages"]],
                         ["开场", "支柱1", "支柱2"])
        self.assertEqual([p["layout"] for p in tpl["pages"]],
                         ["P1", "P12", "P23"])
        self.assertEqual(tpl["style_ref"], "深蓝商务")

    def test_save_strips_business_data_from_template(self):
        raw = (self.home / "deck-templates/weekly/template.json") \
            .read_text(encoding="utf-8")
        # 登记表数值、页面标题/要点等业务文本一律不得进入模板
        for banned in ("1.24", "18%", "营收", "增长质量", "Q3 财报", "人民币元"):
            self.assertNotIn(banned, raw, f"业务数据泄漏进模板：{banned}")

    def test_save_keeps_ledger_column_structure_without_rows(self):
        tpl = json.loads((self.home / "deck-templates/weekly/template.json")
                         .read_text(encoding="utf-8"))
        # 列结构保留（v2 九列契约），数据行剥离
        self.assertEqual(tpl["ledger_columns"],
                         ["数值", "页", "来源", "口径", "期间", "单位",
                          "证据等级", "verified?", "as-of"])
        self.assertNotIn("rows", tpl)

    def test_save_without_confirmed_master_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            pending = Path(tmp) / "content"
            pending.mkdir()
            (pending / "deck-master-v1.md").write_text(
                CONFIRMED_MASTER.replace("confirmed", "pending"),
                encoding="utf-8")
            r = run("save", tmp, "--name", "weekly", "--home", str(self.home))
            self.assertEqual(r.returncode, 2)
            self.assertIn("confirmed", r.stderr)

    def test_save_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "home2"
            r = run("save", str(self.project), "--name", "weekly",
                    "--home", str(other))
            self.assertEqual(r.returncode, 0, r.stderr)
            a = (self.home / "deck-templates/weekly/template.json").read_bytes()
            b = (other / "deck-templates/weekly/template.json").read_bytes()
            self.assertEqual(a, b)

    def test_invalid_template_name_exits_2(self):
        r = run("save", str(self.project), "--name", "../escape",
                "--home", str(self.home))
        self.assertEqual(r.returncode, 2)


class InstantiateTest(DeckTemplateFixture):
    def setUp(self):
        super().setUp()
        self.out = Path(self._tmp.name) / "newproj"
        r = run("instantiate", "weekly", "--data", str(self.material),
                "--out", str(self.out), "--home", str(self.home))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_draft_is_complete_skeleton_prefill(self):
        draft = (self.out / "content" / "deck-master-v1.md") \
            .read_text(encoding="utf-8")
        self.assertIn("confirmation: pending", draft)
        for page_id, role, layout in (("S1", "开场", "P1"),
                                      ("S2", "支柱1", "P12"),
                                      ("S3", "支柱2", "P23")):
            self.assertIn(f"## {page_id}", draft)
            self.assertIn(f"argument_role: {role}", draft)
            self.assertIn(f"版式: {layout}", draft)
        # 四段占位齐全 + 页数合同 + 确认语义红线
        for stub in ("标题", "要点", "视觉行", "speaker_script"):
            self.assertIn(stub, draft)
        self.assertIn("page_contract: 3 页", draft)
        self.assertIn("确认语义红线", draft)
        self.assertIn("不减少确认门", draft)

    def test_draft_carries_fingerprint_list_and_ledger_columns_only(self):
        draft = (self.out / "content" / "deck-master-v1.md") \
            .read_text(encoding="utf-8")
        self.assertIn("模板数据点指纹清单", draft)
        for point in ("1.31亿", "num:131000000", "42", "pct:2.3"):
            self.assertIn(point, draft)
        # 登记表列结构保留、无数据行
        self.assertIn("| 数值 | 页 | 来源 |", draft)
        self.assertNotIn("| 1.24 亿元 | S2 |", draft)

    def test_instance_doc_and_registry_record_fingerprints(self):
        doc = json.loads((self.out / "content" / "template-instance.json")
                         .read_text(encoding="utf-8"))
        keys = {e["key"] for e in doc["registered_data_points"]}
        self.assertEqual(keys, {"num:131000000", "num:42",
                                "pct:18", "pct:2.3"})
        registry = (self.home / "deck-templates/weekly/instances.jsonl") \
            .read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(registry), 1)
        record = json.loads(registry[0])
        self.assertEqual(record["template"], "weekly")
        self.assertEqual({e["key"] for e in record["data_points"]}, keys)

    def test_reinstantiate_same_material_is_idempotent(self):
        before = (self.home / "deck-templates/weekly/instances.jsonl") \
            .read_text(encoding="utf-8")
        draft_before = (self.out / "content" / "deck-master-v1.md") \
            .read_text(encoding="utf-8")
        r = run("instantiate", "weekly", "--data", str(self.material),
                "--out", str(self.out), "--home", str(self.home))
        self.assertEqual(r.returncode, 0, r.stderr)
        after = (self.home / "deck-templates/weekly/instances.jsonl") \
            .read_text(encoding="utf-8")
        self.assertEqual(before, after)  # 不追加重复实例记录
        self.assertEqual(draft_before,
                         (self.out / "content" / "deck-master-v1.md")
                         .read_text(encoding="utf-8"))

    def test_instantiate_missing_template_exits_2(self):
        r = run("instantiate", "nope", "--data", str(self.material),
                "--out", str(Path(self._tmp.name) / "p2"),
                "--home", str(self.home))
        self.assertEqual(r.returncode, 2)
        self.assertIn("模板不存在", r.stderr)

    def test_instantiate_json_output_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("instantiate", "weekly", "--data", str(self.material),
                    "--out", tmp, "--home", str(self.home), "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["template"], "weekly")
            self.assertIn("confirm_semantics", payload)


class DiffDataTest(DeckTemplateFixture):
    def setUp(self):
        super().setUp()
        self.new_master = Path(self._tmp.name) / "new-master.md"
        self.new_master.write_text(NEW_MASTER, encoding="utf-8")

    def _diff(self, master=None):
        return run("diff-data", "weekly", str(master or self.new_master),
                   "--home", str(self.home))

    def _register(self, text):
        material = Path(self._tmp.name) / "m2.md"
        material.write_text(text, encoding="utf-8")
        out = Path(self._tmp.name) / "proj2"
        r = run("instantiate", "weekly", "--data", str(material),
                "--out", str(out), "--home", str(self.home))
        self.assertEqual(r.returncode, 0, r.stderr)
        return material

    def test_three_categories_positive(self):
        self._register(MATERIAL)
        r = self._diff()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("沿用 (1): 18%（pct:18）", r.stdout)
        self.assertIn("新增 (2): 55（num:55）、1.24亿（num:124000000）", r.stdout)
        self.assertIn("缺失 (3): 42（num:42）、1.31亿（num:131000000）、2.3%（pct:2.3）",
                      r.stdout)

    def test_missing_items_enter_material_checklist(self):
        self._register(MATERIAL)
        r = self._diff()
        self.assertIn("材料确认清单", r.stdout)
        self.assertIn("1.31亿（num:131000000）", r.stdout)
        self.assertIn("逐项与用户确认保留或放弃", r.stdout)

    def test_no_missing_when_all_material_points_carried(self):
        # 负向：材料数据点全部进入母版时无缺失、无确认清单
        self._register("材料只有一个数：环比 +18%。\n")
        master = Path(self._tmp.name) / "m-master.md"
        master.write_text(NEW_MASTER, encoding="utf-8")
        r = self._diff(master)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("缺失 (0): （无）", r.stdout)
        self.assertNotIn("材料确认清单", r.stdout)

    def test_unit_normalization_makes_wan_and_yi_same_key(self):
        # 1.24 亿（材料）与 12400 万元（母版登记表）归一同键 → 沿用
        # （沿用项显示串取基线侧首见显示）
        self._register("材料：营收 1.24 亿。\n")
        master = Path(self._tmp.name) / "u-master.md"
        master.write_text(
            NEW_MASTER.replace(
                "| 1.24 亿元 | S2 |", "| 12400 万元 | S2 |"), encoding="utf-8")
        r = self._diff(master)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("沿用 (1): 1.24亿（num:124000000）", r.stdout)
        self.assertIn("缺失 (0): （无）", r.stdout)

    def test_ledger_is_preferred_extraction_mode(self):
        self._register(MATERIAL)
        r = self._diff()
        self.assertIn("master 抽取模式 ledger", r.stdout)
        # 母版标题里的 12400 万元 不在登记表 → 不进入 master 侧数据点
        self.assertNotIn("12400万（num:124000000）\n新增", r.stdout)

    def test_diff_without_instances_exits_2(self):
        r = self._diff()
        self.assertEqual(r.returncode, 2)
        self.assertIn("尚无实例登记", r.stderr)

    def test_diff_missing_template_exits_2(self):
        r = run("diff-data", "nope", str(self.new_master),
                "--home", str(self.home))
        self.assertEqual(r.returncode, 2)
        self.assertIn("模板不存在", r.stderr)

    def test_diff_is_deterministic_and_confirms_semantics_always_present(self):
        self._register(MATERIAL)
        first, second = self._diff(), self._diff()
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn("确认语义：diff 式确认只减少呈现项，不减少确认门", first.stdout)

    def test_diff_json_output_shape(self):
        self._register(MATERIAL)
        r = run("diff-data", "weekly", str(self.new_master),
                "--home", str(self.home), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual([e["key"] for e in data["reused"]], ["pct:18"])
        self.assertEqual({e["key"] for e in data["added"]},
                         {"num:55", "num:124000000"})
        self.assertEqual({e["key"] for e in data["missing"]},
                         {"num:42", "num:131000000", "pct:2.3"})
        self.assertEqual(len(data["checklist"]), 3)
        self.assertIn("不减少确认门", data["confirm_semantics"])


if __name__ == "__main__":
    unittest.main()
