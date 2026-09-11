"""章节/单页表达合同与旧内容包兼容，不把设计元数据塞进正文。"""
import copy
import json
import unittest

from leo_ppt_generator.content_pack import compile_content_pack, content_digest, verify_content_pack, ContentPackError


MODEL = {"schema_version": 2, "main_claim": "效率提升须按同口径比较", "main_style": "清爽专业风",
         "brand_constraints": ["内部资料"], "narrative_order": ["ch-context", "ch-evidence"],
         "chapters": [
             {"chapter_id": "ch-context", "task": "界定口径", "conclusion": "先统一计量边界",
              "evidence_refs": [], "previous": None, "next": "ch-evidence"},
             {"chapter_id": "ch-evidence", "task": "证明效率", "conclusion": "时长下降",
              "evidence_refs": ["试点台账"], "previous": "ch-context", "next": None}]}


def master(model=None, expression=None):
    expression = expression or {"chapter_id": "ch-evidence", "semantic_structure": "comparison",
                                "media_role": "support", "evidence_refs": ["试点台账"],
                                "basis": ["同期间同单位对照"], "budget_seconds": 75}
    return """# 母版
decision_source: user-delegated
goal: 汇报效率
audience: 管理层
content_model: %s

## S1 口径
page_id: pg-11111111
page_expression: {"chapter_id":"ch-context","semantic_structure":"undecided","media_role":"none","evidence_refs":[],"basis":[]}
- 标题：先统一口径
- 要点 1：两组必须同期间

## S2 对照
page_id: pg-22222222
page_expression: %s
- 标题：试点处理时长下降
- 要点 1：从 6 小时降到 2 小时【引用|src:试点台账】
对照侧: 旧流程｜6 小时｜同期间
对照侧: 新流程｜2 小时｜同期间
- 备注：speaker_script: 说明两组相同边界

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | S2 | 试点台账 | 旧流程 | 2026Q3 | 小时 | 引用 | yes | 2026-09-01 |
| 2 | S2 | 试点台账 | 新流程 | 2026Q3 | 小时 | 引用 | yes | 2026-09-01 |
""" % (json.dumps(model or MODEL, ensure_ascii=False), json.dumps(expression, ensure_ascii=False))


def compile_text(text=None):
    return compile_content_pack(text or master(), master_path="content/deck-master-v1.md")


class ChapterContentTests(unittest.TestCase):
    def test_v2_records_chapters_required_text_sources_and_budget(self):
        pack = compile_text()
        self.assertEqual(pack["schema_version"], 2)
        self.assertEqual(pack["deck"]["main_style"], "清爽专业风")
        page = pack["pages"][1]
        self.assertEqual(page["chapter_id"], "ch-evidence")
        self.assertEqual(page["budget_seconds"], 75)
        self.assertIn("从 6 小时降到 2 小时【引用|src:试点台账】", page["required_text"])
        self.assertEqual(set(page["data_refs"]), {n["item_id"] for n in pack["numbers"]})
        self.assertNotIn("budget_seconds", str(page["items"]))
        verify_content_pack(pack)

    def test_absent_evidence_is_undecided(self):
        pack = compile_text()
        self.assertEqual(pack["pages"][0]["confidence"], "undecided")
        self.assertTrue(pack["pages"][0]["basis"])

    def test_reordered_chapters_keep_page_identity(self):
        changed = copy.deepcopy(MODEL)
        changed["narrative_order"].reverse()
        changed["chapters"][0].update(previous="ch-evidence", next=None)
        changed["chapters"][1].update(previous=None, next="ch-context")
        text = master(changed)
        prefix, rest = text.split("## S1", 1)
        first_page, rest = rest.split("## S2", 1)
        second_page, ledger = rest.split("## 数字登记表", 1)
        reordered = prefix + "## S2" + second_page + "## S1" + first_page + "## 数字登记表" + ledger
        first, second = compile_text(), compile_text(reordered)
        self.assertEqual({p["page_id"]: p["claim"] for p in first["pages"]},
                         {p["page_id"]: p["claim"] for p in second["pages"]})
        self.assertEqual(second["pages"][0]["page_id"], "pg-22222222")

    def test_duplicate_chapter_and_unknown_page_chapter_rejected(self):
        changed = copy.deepcopy(MODEL)
        changed["chapters"].append(changed["chapters"][0])
        with self.assertRaises(ContentPackError):
            compile_text(master(changed))
        with self.assertRaises(ContentPackError):
            compile_text(master().replace('"chapter_id": "ch-evidence"', '"chapter_id": "missing"', 1))

    def test_missing_reference_and_recomputed_digest_do_not_bypass_validation(self):
        pack = compile_text()
        pack["pages"][1]["data_refs"] = []
        pack["content_digest"] = content_digest(pack)
        with self.assertRaises(ContentPackError):
            verify_content_pack(pack)

    def test_fabricated_evidence_reference_rejected(self):
        with self.assertRaises(ContentPackError):
            compile_text(master(expression={"chapter_id": "ch-evidence", "semantic_structure": "comparison",
                                           "media_role": "support", "evidence_refs": ["不存在的来源"],
                                           "basis": ["假证据"]}))

    def test_v1_legacy_and_invalid_version(self):
        text = "\n".join(line for line in master().splitlines()
                         if not line.startswith(("content_model:", "page_expression:")))
        pack = compile_text(text)
        self.assertEqual(pack["schema_version"], 1)
        verify_content_pack(pack)
        pack["schema_version"] = 99
        pack["content_digest"] = content_digest(pack)
        with self.assertRaises(ContentPackError):
            verify_content_pack(pack)


if __name__ == "__main__":
    unittest.main()
