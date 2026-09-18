#!/usr/bin/env python3
"""layout_selection.py 单元测试（dashi 集成 K5/U5）：结构指纹规范化（重命名
不变、顺序/分组/编码变化、缺声明 unknown）/ 完整合格池与排除原因 /
整册分配确定性（换序、平分裁决）/ 禁复用仅对 reuse_friendly=false 生效 /
AE5 全局约束由池内候选解决 / 搜索预算耗尽与无候选分别报告 / 显式选择过
资格门 / capability_manifest 准入派生。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = PKG_ROOT / "runtime" / "src"
for entry in (str(RUNTIME_SRC), str(PKG_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from leo_ppt_generator import templates  # noqa: E402
from leo_ppt_generator.content_pack import compile_content_pack  # noqa: E402
from leo_ppt_generator.layout_selection import (  # noqa: E402
    UNKNOWN_FINGERPRINT,
    allocate_deck,
    qualified_pool,
    structure_fingerprint,
)

STYLE = "finance-navy"


def allocation_inputs(*, hero_limit=1, alt_limit=0, prefer_b=False):
    """真实资产变体经正反浏览器探针后供算法测试使用，不授予发布资格。"""
    from tests.expression_test_support import real_allocation_inputs
    return real_allocation_inputs(hero_limit, alt_limit, prefer_b)


def _pack_for(pages_spec: list, *, decided=False) -> dict:
    """pages_spec: list of (page_id, 角色, 标题, [要点])。"""
    blocks = []
    model = {"schema_version": 2, "main_claim": "验证选型约束", "main_style": "清爽专业风",
             "brand_constraints": [], "narrative_order": ["ch-test"], "chapters": [
                 {"chapter_id": "ch-test", "task": "比较候选", "conclusion": "保留所有事实",
                  "evidence_refs": [], "previous": None, "next": None}]}
    for pid, role, title, points in pages_spec:
        lines = [f"## S{pid[3:]} P", f"page_id: {pid}", f"角色：{role}",
                 "argument_role: 论据", f"- 标题：{title}"]
        lines += [f"- 要点 {i + 1}：{text}" + ("【引用|src:测试材料】" if decided else "")
                  for i, text in enumerate(points)]
        refs = [f"point:{i + 1}" for i in range(len(points))]
        expression = {"chapter_id": "ch-test", "semantic_structure": "independent" if decided else "undecided", "media_role": "none",
                      "evidence_refs": ["测试材料"] if decided else [], "basis": ["材料列明相互独立的事项"] if decided else [], "expression": {"reading_task": "independent",
                      "focus": "claim", "reading_order": ["claim", *refs], "fact_refs": [], "uncertainty": [],
                      "relation_encoding": {"item_refs": refs, "edges": []}}}
        lines.append("page_expression: " + json.dumps(expression, ensure_ascii=False))
        lines.append("视觉行：要点1→容器")
        lines.append("- 备注：口播")
        blocks.append("\n".join(lines))
    master = ("# 母版 v2\ndecision_source: user-delegated\ncontent_model: " + json.dumps(model, ensure_ascii=False) + "\n\n"
              + "\n\n".join(blocks)
              + "\n\n## 数字登记表\n| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    return compile_content_pack(master, master_path="content/deck-master-v1.md")


def _context():
    return allocation_inputs()[1]


class StructureFingerprintTests(unittest.TestCase):
    def test_rename_and_style_changes_keep_fingerprint(self):
        base = {"reading_order": ["title", "bullets"],
                "groups": [{"name": "对照", "members": ["a", "b"],
                             "relation": "contrast"}]}
        renamed = {"reading_order": ["title", "bullets"],
                   "groups": [{"name": "改名", "members": ["b", "a"],
                                "relation": "contrast"}]}
        self.assertEqual(structure_fingerprint({"structure": base}),
                         structure_fingerprint({"structure": renamed}))

    def test_order_group_encoding_changes_flip_fingerprint(self):
        base = {"reading_order": ["title", "bullets"]}
        self.assertNotEqual(
            structure_fingerprint({"structure": base}),
            structure_fingerprint({"structure": {"reading_order": ["bullets", "title"]}}))
        grouped = {"reading_order": ["title", "bullets"],
                   "groups": [{"name": "g", "members": ["x"], "relation": "r"}]}
        self.assertNotEqual(structure_fingerprint({"structure": base}),
                            structure_fingerprint({"structure": grouped}))
        encoded = {"reading_order": ["title"],
                   "encodings": [{"slot": "chart", "kind": "bar"}]}
        self.assertNotEqual(structure_fingerprint({"structure": base}),
                            structure_fingerprint({"structure": encoded}))

    def test_missing_declaration_is_unknown(self):
        self.assertEqual(structure_fingerprint({}), UNKNOWN_FINGERPRINT)
        self.assertEqual(structure_fingerprint({"structure": {}}), UNKNOWN_FINGERPRINT)


class DeckAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolver, cls.context = allocation_inputs()
        cls.candidates = ["hero", "cover-alt", "cover-third", "bullets-a", "bullets-b"]

    def allocate(self, pages_spec, **kwargs):
        pack = _pack_for(pages_spec)
        return allocate_deck(pack, self.context, resolver=self.resolver,
                             candidates=self.candidates, qualification_purpose="validation", **kwargs), pack

    def test_allocation_deterministic_and_ordered(self):
        pages = [
            ("pg-11111111", "封面", "封面结论", ["要点一"]),
            ("pg-22222222", "流程·路径", "内容结论", ["甲", "乙", "丙"]),
            ("pg-33333333", "流程·路径", "内容结论二", ["丁", "戊", "己"]),
        ]
        first, _ = self.allocate(pages)
        second, _ = self.allocate(pages)
        self.assertEqual(first["status"], "complete", first["page_status"])
        self.assertEqual(first["selection"], second["selection"])
        # 普通内容版式可复用；二者是真实同结构变体，不能伪造不同结构强迫交替。
        for page_id in ("pg-22222222", "pg-33333333"):
            self.assertIn(first["selection"][page_id]["layout_id"],
                          {"builtin:layout:bullets-a", "builtin:layout:bullets-b"})

    def test_reuse_limited_layout_respected_and_third_candidate_solves(self):
        # AE5：hero（reuse_friendly=false, max_per_deck=1）显式用于第一页后，
        # 第二页必须由完整池内其它候选解决——Top-2 截断会误报无解。
        pages = [
            ("pg-11111111", "封面", "封面一", ["要点一"]),
            ("pg-22222222", "封面", "封面二", ["要点一"]),
        ]
        result, _ = self.allocate(pages, explicit={"pg-11111111": "hero"})
        self.assertEqual(result["status"], "complete", result["page_status"])
        chosen = {p: v["layout_id"] for p, v in result["selection"].items()}
        self.assertEqual(chosen["pg-11111111"], "builtin:layout:hero")
        self.assertIn(chosen["pg-22222222"],
                      {"builtin:layout:cover-alt", "builtin:layout:cover-third"})

    def test_budget_exhausted_distinct_from_no_candidates(self):
        pages = [
            ("pg-11111111", "封面", "封面一", ["要点一"]),
            ("pg-22222222", "封面", "封面二", ["要点一"]),
        ]
        # 极小预算：候选存在但搜索预算耗尽 → budget_exhausted，不放宽硬约束。
        result, _ = self.allocate(pages, search_budget=0)
        self.assertEqual(result["status"], "budget_exhausted")
        # 无候选：未知角色页 → no_candidates 且带原因。
        result, _ = self.allocate([("pg-99999999", "神秘角色", "标题", ["a", "b"])])
        self.assertEqual(result["status"], "no_candidates")
        reasons = result["page_status"]["pg-99999999"]["reasons"]
        self.assertTrue(reasons)

    def test_explicit_choice_still_goes_through_qualification(self):
        pages = [("pg-11111111", "流程·路径", "内容结论", ["甲", "乙", "丙"])]
        result, _ = self.allocate(pages, explicit={"pg-11111111": "hero"})
        self.assertEqual(result["status"], "explicit_unqualified")
        # 合法显式选择被尊重。
        result_ok, _ = self.allocate(pages, explicit={"pg-11111111": "bullets-b"})
        self.assertEqual(result_ok["status"], "complete")
        self.assertEqual(result_ok["selection"]["pg-11111111"]["layout_id"],
                         "builtin:layout:bullets-b")

    def test_backtracking_reassigns_when_second_page_loses_top_choice(self):
        # 两个禁复用封面版式各限一次：回溯撤销重选，两页均得解（AE5 深化）。
        resolver, context = allocation_inputs(alt_limit=1)
        pages = [
            ("pg-11111111", "封面", "封面一", ["要点一"]),
            ("pg-22222222", "封面", "封面二", ["要点一"]),
        ]
        pack = _pack_for(pages)
        result = allocate_deck(pack, context, resolver=resolver,
                               qualification_purpose="validation", candidates=["hero", "cover-alt", "cover-third"])
        self.assertEqual(result["status"], "complete", result["page_status"])
        chosen = {p: v["layout_id"] for p, v in result["selection"].items()}
        self.assertNotEqual(chosen["pg-11111111"], chosen["pg-22222222"])

    def test_max_per_deck_two_allows_reuse(self):
        resolver, context = allocation_inputs(hero_limit=2)
        pages = [
            ("pg-11111111", "封面", "封面一", ["要点一"]),
            ("pg-22222222", "封面", "封面二", ["要点一"]),
        ]
        pack = _pack_for(pages)
        result = allocate_deck(pack, context, resolver=resolver,
                               qualification_purpose="validation", candidates=["hero", "cover-alt", "cover-third"],
                               explicit={"pg-11111111": "hero", "pg-22222222": "hero"})
        self.assertEqual(result["status"], "complete", result["page_status"])
        chosen = {p: v["layout_id"] for p, v in result["selection"].items()}
        self.assertEqual(chosen["pg-11111111"], chosen["pg-22222222"],
                         "max_per_deck=2 允许复用两次")


    def test_top2_is_human_summary_full_pool_lives_behind(self):
        pages = [("pg-11111111", "流程·路径", "内容结论", ["甲", "乙", "丙"])]
        pack = _pack_for(pages)
        pool = qualified_pool(pack["pages"][0], self.context,
                              content_digest=pack["content_digest"],
                              numbers=pack["numbers"],
                              candidates=self.candidates, resolver=self.resolver, qualification_purpose="validation")
        qualified_ids = {e["layout_id"] for e in pool["qualified"]}
        excluded_ids = {e["layout_id"] for e in pool["excluded"]}
        self.assertEqual(qualified_ids, {"builtin:layout:bullets-a",
                                          "builtin:layout:bullets-b"})
        self.assertIn("builtin:layout:hero", excluded_ids)  # 角色不符仍留在排除清单
        result = allocate_deck(pack, self.context, resolver=self.resolver,
                               candidates=self.candidates, qualification_purpose="validation")
        self.assertLessEqual(len(result["top2"]["pg-11111111"]), 2)


class CanonicalAdmissionTests(unittest.TestCase):
    def test_canonical_structure_declarations_validate_and_admit(self):
        import jsonschema
        schema = json.loads((PKG_ROOT / "template-library/governance/schemas"
                             / "layout-profile-v1.schema.json").read_text(encoding="utf-8"))
        from referencing import Registry, Resource
        resources = []
        schema_dir = PKG_ROOT / "template-library/governance/schemas"
        for path in schema_dir.glob("*.schema.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if "$id" in doc:
                resources.append((doc["$id"], Resource.from_contents(doc)))
        validator = jsonschema.Draft7Validator(
            schema, registry=Registry().with_resources(resources))
        declared = 0
        for path in sorted((PKG_ROOT / "template-library/canonical/layouts").glob(
                "*/layout.json")):
            profile = json.loads(path.read_text(encoding="utf-8"))
            errors = list(validator.iter_errors(profile))
            self.assertFalse(errors, [e.message for e in errors])
            if profile.get("structure"):
                declared += 1
                self.assertNotEqual(structure_fingerprint(profile), UNKNOWN_FINGERPRINT)
        self.assertEqual(declared, 15)

    def test_capability_manifest_derives_admission(self):
        script = PKG_ROOT / "scripts" / "capability_manifest.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--template-library"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        admission = json.loads(proc.stdout)["structure_admission"]
        self.assertEqual(admission["html_declared"], 15)
        self.assertEqual(admission["structure_unknown"], 27)
        # 声明数量不是资格；生产库没有当前正反例与视觉 receipt 时必须关门。
        self.assertEqual(admission["auto_pool"], 0)


if __name__ == "__main__":
    unittest.main()
