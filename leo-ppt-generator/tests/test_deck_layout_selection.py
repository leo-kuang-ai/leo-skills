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


class _FakeResolver:
    """受控候选集合：三封面版式（hero 禁复用）+ 两内容版式。"""

    def __init__(self):
        def layout(name, page_role, *, reuse=None, max_per_deck=None,
                   structure=None, slots=None):
            profile = {
                "schema_version": 1, "entity": "layout-profile",
                "asset_id": f"builtin:layout:{name}", "name": name,
                "canvas": {"width": 1280, "height": 720, "units": "logical-px"},
                "page_role": page_role, "layout_type": "fixed-regions",
                "regions": {"content": {"x": 80, "y": 60, "width": 1120, "height": 600}},
                "slots": slots or {}, "renderer_support": {
                    "render:html": f"builtin:template:{name}"},
            }
            if reuse is False:
                profile["reuse_friendly"] = False
                profile["max_per_deck"] = max_per_deck or 1
            if structure:
                profile["structure"] = structure
            return profile

        def template(name, fields):
            return {"schema_version": 1, "entity": "render-template",
                    "asset_id": f"builtin:template:{name}", "name": name,
                    "input_fields": fields, "slot_bindings": [], "theme_roles": [],
                    "dependencies": []}

        text_slot = {"title": {"region": "content", "max_chars": 60,
                                "content_type": "text"}}
        bullets_slot = {"bullets": {"region": "content", "count_min": 2,
                                     "count_max": 6, "content_type": "points"},
                         "title": {"region": "content", "max_chars": 60,
                                    "content_type": "text"}}
        self.layouts = {
            "hero": layout("hero", "cover", reuse=False, max_per_deck=1,
                           slots=text_slot,
                           structure={"reading_order": ["title"]}),
            "cover-alt": layout("cover-alt", "cover", slots=text_slot,
                                 structure={"reading_order": ["title"]}),
            "cover-third": layout("cover-third", "cover", slots=text_slot,
                                   structure={"reading_order": ["title"]}),
            "bullets-a": layout("bullets-a", "content", slots=bullets_slot,
                                 structure={"reading_order": ["title", "bullets"]}),
            "bullets-b": layout("bullets-b", "content", slots=bullets_slot,
                                 structure={"reading_order": ["bullets", "title"]}),
        }
        self.templates = {
            "hero": template("hero", [
                {"name": "title", "required": True, "type": "string"},
                {"name": "subtitle", "required": False, "type": "string"}]),
            "cover-alt": template("cover-alt", [
                {"name": "title", "required": True, "type": "string"},
                {"name": "subtitle", "required": False, "type": "string"}]),
            "cover-third": template("cover-third", [
                {"name": "title", "required": True, "type": "string"},
                {"name": "subtitle", "required": False, "type": "string"}]),
            "bullets-a": template("bullets-a", [
                {"name": "title", "required": True, "type": "string"},
                {"name": "bullets", "required": True, "type": "array"}]),
            "bullets-b": template("bullets-b", [
                {"name": "title", "required": True, "type": "string"},
                {"name": "bullets", "required": True, "type": "array"}]),
        }

    def require(self, query, kind=None, scope="any"):
        return self._entity(f"builtin:layout:{query}", self.layouts[query])

    def resolve(self, asset_id, context=None):
        if asset_id.startswith("builtin:layout:"):
            name = asset_id.rsplit(":", 1)[-1]
            return self._entity(asset_id, self.layouts[name])
        if asset_id.startswith("builtin:template:"):
            name = asset_id.rsplit(":", 1)[-1]
            return self._entity(asset_id, self.templates[name])
        raise KeyError(asset_id)

    @staticmethod
    def _entity(asset_id, data):
        return {"asset_id": asset_id, "revision": "r1", "path": "/dev/null",
                "data": data}


def _pack_for(pages_spec: str) -> dict:
    """pages_spec: list of (page_id, 角色, 标题, [要点])。"""
    blocks = []
    ledger = []
    for pid, role, title, points in pages_spec:
        lines = [f"## S{pid[3:]} P", f"page_id: {pid}", f"角色：{role}",
                 "argument_role: 论据", f"- 标题：{title}"]
        lines += [f"- 要点 {i + 1}：{text}" for i, text in enumerate(points)]
        lines.append("视觉行：要点1→容器")
        lines.append("- 备注：口播")
        blocks.append("\n".join(lines))
    master = ("# 母版 v1\nconfirmation: confirmed\n\n"
              + "\n\n".join(blocks)
              + "\n\n## 数字登记表\n| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    return compile_content_pack(master, master_path="content/deck-master-v1.md")


def _context():
    return templates.resolve_design_context(STYLE)


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
        cls.resolver = _FakeResolver()
        cls.context = _context()
        cls.candidates = ["hero", "cover-alt", "cover-third", "bullets-a", "bullets-b"]

    def allocate(self, pages_spec, **kwargs):
        pack = _pack_for(pages_spec)
        return allocate_deck(pack, self.context, resolver=self.resolver,
                             candidates=self.candidates, **kwargs), pack

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
        # 普通内容版式可复用（不误套一次限制）；相邻重复被惩罚 → a/b 交替。
        self.assertEqual(first["selection"]["pg-22222222"]["layout_id"],
                         "builtin:layout:bullets-a")
        self.assertEqual(first["selection"]["pg-33333333"]["layout_id"],
                         "builtin:layout:bullets-b")

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
        resolver = _FakeResolver()
        resolver.layouts["cover-alt"]["reuse_friendly"] = False
        resolver.layouts["cover-alt"]["max_per_deck"] = 1
        context = _context()
        pages = [
            ("pg-11111111", "封面", "封面一", ["要点一"]),
            ("pg-22222222", "封面", "封面二", ["要点一"]),
        ]
        pack = _pack_for(pages)
        result = allocate_deck(pack, context, resolver=resolver,
                               candidates=["hero", "cover-alt", "cover-third"])
        self.assertEqual(result["status"], "complete", result["page_status"])
        chosen = {p: v["layout_id"] for p, v in result["selection"].items()}
        self.assertNotEqual(chosen["pg-11111111"], chosen["pg-22222222"])

    def test_max_per_deck_two_allows_reuse(self):
        resolver = _FakeResolver()
        resolver.layouts["hero"]["max_per_deck"] = 2
        context = _context()
        pages = [
            ("pg-11111111", "封面", "封面一", ["要点一"]),
            ("pg-22222222", "封面", "封面二", ["要点一"]),
        ]
        pack = _pack_for(pages)
        result = allocate_deck(pack, context, resolver=resolver,
                               candidates=["hero", "cover-alt", "cover-third"],
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
                              candidates=self.candidates, resolver=self.resolver)
        qualified_ids = {e["layout_id"] for e in pool["qualified"]}
        excluded_ids = {e["layout_id"] for e in pool["excluded"]}
        self.assertEqual(qualified_ids, {"builtin:layout:bullets-a",
                                          "builtin:layout:bullets-b"})
        self.assertIn("builtin:layout:hero", excluded_ids)  # 角色不符仍留在排除清单
        result = allocate_deck(pack, self.context, resolver=self.resolver,
                               candidates=self.candidates)
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
        self.assertEqual(declared, 7)

    def test_capability_manifest_derives_admission(self):
        script = PKG_ROOT / "scripts" / "capability_manifest.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--template-library"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        admission = json.loads(proc.stdout)["structure_admission"]
        self.assertEqual(admission["html_declared"], 7)
        self.assertEqual(admission["structure_unknown"], 35)
        self.assertEqual(admission["auto_pool"], admission["html_declared"]
                         + admission["image_declared"])


if __name__ == "__main__":
    unittest.main()
