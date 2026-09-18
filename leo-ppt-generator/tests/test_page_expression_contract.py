"""表达编译必须保留真实引用与关系；不能只验证字段存在。"""
from copy import deepcopy
import unittest

from leo_ppt_generator.content_pack import ContentPackError, compile_page_expression


def content():
    return {"pages": [{"page_id": "pg-11111111", "claim": "逐项核对",
                       "items": [{"item_id": "i1", "kind": "point", "text": "甲", "required": True,
                                  "source_ref": "记录"},
                                 {"item_id": "i2", "kind": "point", "text": "乙", "required": True},
                                 {"item_id": "n1", "kind": "number-ref", "number_item_id": "n1", "required": True},
                                 {"item_id": "n2", "kind": "number-ref", "number_item_id": "n2", "required": True}],
                       "structures": {"dimension": "耗时", "times": ["2026-01", "2026-02"],
                                      "meaning": "使处理速度提高"}}],
            "numbers": [{"item_id": "n1", "value": "6", "unit": "小时", "period": "2026Q1", "source": "记录", "page_ids": ["pg-11111111"]},
                        {"item_id": "n2", "value": "2", "unit": "小时", "period": "2026Q1", "source": "记录", "page_ids": ["pg-11111111"]}]}


def declaration(kind="independent"):
    encodings = {
        "independent": {"item_refs": ["i1", "i2"], "edges": []},
        "comparison": {"item_refs": ["i1", "i2"], "dimension_refs": ["/structures/dimension"],
                       "cells": [{"item_ref": "i1", "dimension_ref": "/structures/dimension", "fact_ref": "n1", "unknown": False},
                                 {"item_ref": "i2", "dimension_ref": "/structures/dimension", "fact_ref": "n2", "unknown": False}]},
        "trend": {"samples": [{"time_ref": "/structures/times/0", "value_ref": "n1"},
                              {"time_ref": "/structures/times/1", "value_ref": "n2"}],
                  "unit_ref": "/facts/n1/unit", "period_ref": "/facts/n1/period", "baseline_ref": None},
        "process": {"nodes": ["i1", "i2"], "edges": [{"from": "i1", "to": "i2"}], "parallel_branches": []},
        "causal": {"nodes": ["i1", "i2"], "edges": [{"from": "i1", "to": "i2", "meaning_ref": "/structures/meaning", "support_refs": ["i1"]}]},
    }
    return {"reading_task": kind, "focus": "claim", "reading_order": ["claim", "i1", "i2", "n1", "n2"],
            "relation_encoding": deepcopy(encodings[kind]), "fact_refs": ["n1", "n2"], "uncertainty": []}


class PageExpressionContractTests(unittest.TestCase):
    def test_formal_schema_is_referenced_and_copies_agree(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "runtime/src/leo_ppt_generator/schemas/page-expression-v1.schema.json").read_text())
        governed = json.loads((root / "template-library/governance/schemas/page-expression-v1.schema.json").read_text())
        pack_schema = json.loads((root / "runtime/src/leo_ppt_generator/schemas/page-content-pack-v2.schema.json").read_text())
        self.assertEqual(schema, governed)
        self.assertEqual(pack_schema["properties"]["pages"]["items"]["properties"]["expression"], {"$ref": schema["$id"]})
        from leo_ppt_generator.page_intent import load_page_type_regime
        for kind, relation in load_page_type_regime()["relations"].items():
            self.assertEqual(schema["$defs"][kind]["required"], relation["required_encoding_fields"])

    def compile(self, kind="independent", *, pack=None, **updates):
        args = declaration(kind)
        args.update(updates)
        return compile_page_expression(pack or content(), "pg-11111111", **args)

    def test_each_relation_keeps_distinct_minimum_encoding(self):
        for kind in ("comparison", "trend", "process", "causal", "independent"):
            with self.subTest(kind=kind):
                self.assertEqual(self.compile(kind)["relation"]["encoding"], declaration(kind)["relation_encoding"])

    def test_focus_must_be_a_positioned_reference(self):
        for focus in ("未知焦点", "i-missing", ""):
            with self.subTest(focus=focus), self.assertRaisesRegex(ContentPackError, "expression_incomplete"):
                self.compile(focus=focus)

    def test_required_point_claim_and_fact_cannot_disappear(self):
        for missing in declaration()["reading_order"]:
            order = [r for r in declaration()["reading_order"] if r != missing]
            with self.subTest(missing=missing), self.assertRaisesRegex(ContentPackError, "expression_incomplete"):
                self.compile(reading_order=order)
        with self.assertRaisesRegex(ContentPackError, "expression_incomplete"):
            self.compile(fact_refs=[])

    def test_each_missing_relation_field_fails(self):
        for kind in ("comparison", "trend", "process", "causal", "independent"):
            encoding = declaration(kind)["relation_encoding"]
            for key in encoding:
                incomplete = {k: v for k, v in encoding.items() if k != key}
                with self.subTest(kind=kind, key=key), self.assertRaisesRegex(ContentPackError, "expression_incomplete"):
                    self.compile(kind, relation_encoding=incomplete)

    def test_comparison_missing_cell_and_dangling_fact_rejected(self):
        base = declaration("comparison")["relation_encoding"]
        for field, value in (("cells", base["cells"][:1]), ("dimension_refs", ["/structures/missing"])):
            with self.subTest(field=field), self.assertRaises(ContentPackError):
                self.compile("comparison", relation_encoding={**base, field: value})

    def test_unknown_comparison_cell_requires_uncertainty(self):
        enc = declaration("comparison")["relation_encoding"]
        enc["cells"][0].update(fact_ref=None, unknown=True)
        with self.assertRaises(ContentPackError):
            self.compile("comparison", relation_encoding=enc)
        self.compile("comparison", relation_encoding=enc, uncertainty=["甲耗时待核对"])

    def test_trend_mixed_units_reversed_time_and_non_numeric_rejected(self):
        for mutation in ("unit", "time", "value"):
            pack = content()
            if mutation == "unit": pack["numbers"][1]["unit"] = "元"
            if mutation == "time": pack["pages"][0]["structures"]["times"].reverse()
            if mutation == "value": pack["numbers"][0]["value"] = "没有记录"
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ContentPackError, "expression_declaration_conflict"):
                self.compile("trend", pack=pack)

    def test_process_reverse_edge_and_unknown_node_rejected(self):
        for edge in ({"from": "i2", "to": "i1"}, {"from": "missing", "to": "i2"}):
            enc = declaration("process")["relation_encoding"]
            enc["edges"] = [edge]
            with self.assertRaises(ContentPackError): self.compile("process", relation_encoding=enc)

    def test_independent_forbids_invented_edges(self):
        enc = declaration()["relation_encoding"]
        enc["edges"] = [{"from": "i1", "to": "i2"}]
        with self.assertRaises(ContentPackError): self.compile(relation_encoding=enc)

    def test_causal_requires_source_support_and_preserves_correlation(self):
        pack = content()
        del pack["pages"][0]["items"][0]["source_ref"]
        with self.assertRaises(ContentPackError): self.compile("causal", pack=pack)
        pack = content()
        pack["pages"][0]["structures"]["relation_type"] = "correlation"
        with self.assertRaisesRegex(ContentPackError, "expression_declaration_conflict"):
            self.compile("causal", pack=pack)

    def test_empty_fact_list_wrong_types_and_long_reference_fail_cleanly(self):
        for updates in ({"reading_order": [["claim"]]}, {"fact_refs": "n1"}, {"uncertainty": "unknown"},
                        {"focus": "长" * 10000}, {"reading_order": ["claim", "i1", "i1"]}):
            with self.subTest(updates=list(updates)), self.assertRaises(ContentPackError): self.compile(**updates)

    def test_authoring_fields_cannot_hide_structural_conflicts(self):
        for relation, fields in (("causal", {"relation_type": "correlation"}),
                                 ("independent", {"steps": ["甲", "乙"]}),
                                 ("independent", {"sides": ["甲", "乙"]}),
                                 ("independent", {"edges": [{"from": "甲", "to": "乙"}]})):
            pack = content()
            pack["pages"][0]["structures"]["fields"] = fields
            with self.subTest(relation=relation, fields=fields), self.assertRaisesRegex(ContentPackError, "expression_declaration_conflict"):
                self.compile(relation, pack=pack)

    def test_structure_subjects_need_positions_and_process_order_must_agree(self):
        encoding = {"item_refs": ["/structures/dimension"], "edges": []}
        with self.assertRaisesRegex(ContentPackError, "subject not positioned"):
            self.compile(relation_encoding=encoding)
        self.compile(relation_encoding=encoding, reading_order=declaration()["reading_order"] + ["/structures/dimension"])
        with self.assertRaisesRegex(ContentPackError, "reading order contradicts dependency"):
            self.compile("process", reading_order=["claim", "i2", "i1", "n1", "n2"])

    def test_statement_needs_no_fabricated_item(self):
        pack = {"pages": [{"page_id": "pg-11111111", "claim": "证据不足时保留未知", "items": [], "structures": {}}], "numbers": []}
        result = self.compile(pack=pack, reading_task="statement", reading_order=["claim"], fact_refs=[],
                              relation_encoding={"item_refs": ["claim"], "edges": []})
        self.assertEqual(result["focus"], "claim")
