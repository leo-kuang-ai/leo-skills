"""容量查询面合同测试（UB2，方案 2026-09-02-002）。

覆盖：条件解析的非法输入拒绝、真实库过滤行为（计数槽 count_max / 文本槽
max_chars 判定）、槽缺失如实报 missing、AND 语义、缺省枚举路径不受影响。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.layout_bank import (  # noqa: E402
    LayoutBankError,
    _parse_capacity_conditions,
    _slot_upper_bound,
    filter_layout_bank_by_capacity,
    list_layout_bank,
)


class CapacityConditionParsing(unittest.TestCase):
    def test_rejects_condition_without_operator(self):
        with self.assertRaises(LayoutBankError):
            _parse_capacity_conditions("title8")

    def test_rejects_non_integer_bound(self):
        with self.assertRaises(LayoutBankError):
            _parse_capacity_conditions("title<=abc")

    def test_rejects_empty_condition_string(self):
        with self.assertRaises(LayoutBankError):
            _parse_capacity_conditions("  ")

    def test_parses_multiple_conditions(self):
        self.assertEqual(
            _parse_capacity_conditions("title<=8, items<=6"),
            [("title", 8), ("items", 6)],
        )


class SlotUpperBound(unittest.TestCase):
    def test_count_slot_prefers_count_max(self):
        self.assertEqual(_slot_upper_bound({"count_min": 4, "count_max": 6}), 6)

    def test_text_slot_uses_max_chars(self):
        self.assertEqual(_slot_upper_bound({"chars_per_line": 7, "max_chars": 8}), 8)

    def test_slot_without_bound_keys_reports_none(self):
        """槽存在但无判定键 → None（missing 路径，不静默通过）。"""
        self.assertIsNone(_slot_upper_bound({"desc": "只有描述"}))


class RealLibraryFiltering(unittest.TestCase):
    def test_title_filter_matches_cover_by_max_chars(self):
        """当前 P1/cover-pro 标题上限 40；39 必须排除该资产。"""
        hit = filter_layout_bank_by_capacity("title<=40")["matched"]
        miss = filter_layout_bank_by_capacity("title<=39")["matched"]
        self.assertIn("P1", [item["layout_id"] for item in hit])
        self.assertNotIn("P1", [item["layout_id"] for item in miss])

    def test_items_filter_uses_count_max(self):
        """P6 items.count_max=4：items<=4 命中并带 capacity_bounds；items<=3 排除。"""
        hit = filter_layout_bank_by_capacity("items<=4")["matched"]
        miss = filter_layout_bank_by_capacity("items<=3")["matched"]
        hit_ids = [item["layout_id"] for item in hit]
        self.assertIn("P6", hit_ids)
        self.assertNotIn("P6", [item["layout_id"] for item in miss])
        p6 = next(item for item in hit if item["layout_id"] == "P6")
        self.assertEqual(p6["capacity_bounds"], {"items": 4})

    def test_absent_slot_is_normal_non_match_not_missing(self):
        """无 title 槽的版式是正常不匹配，不进 missing。"""
        result = filter_layout_bank_by_capacity("title<=8")
        matched_ids = {item["layout_id"] for item in result["matched"]}
        for layout_id, miss_slots in result["missing"].items():
            self.assertNotEqual(
                layout_id, "P6", "P6 无 title 槽，不应因缺槽进 missing"
            )
            self.assertTrue(miss_slots)
        self.assertNotIn("P6", matched_ids)

    def test_conditions_combine_with_and(self):
        """title<=8 且 items<=4 同时要求：交集语义。"""
        only_title = {item["layout_id"] for item in filter_layout_bank_by_capacity("title<=8")["matched"]}
        only_items = {item["layout_id"] for item in filter_layout_bank_by_capacity("items<=4")["matched"]}
        both = {item["layout_id"] for item in filter_layout_bank_by_capacity("title<=8,items<=4")["matched"]}
        self.assertEqual(both, only_title & only_items)

    def test_default_listing_unchanged_by_filter_addition(self):
        """缺省枚举（不带过滤）保持 42 份确定性输出（36 P 码 + 6 html-lane）。"""
        items = list_layout_bank()
        self.assertEqual(len(items), 42)
        self.assertEqual(
            [item["layout_id"] for item in items],
            sorted(item["layout_id"] for item in items),
        )

    def test_missing_registration_is_condition_order_insensitive(self):
        """前序槽不存在时，后续缺键槽仍如实进 missing（break→continue 回归锁）。"""
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td)
            library = bundle / "template-library"
            layout_dir = library / "canonical" / "layouts" / "px-x"
            layout_dir.mkdir(parents=True)
            (layout_dir / "layout.json").write_text(json.dumps({
                "schema_version": 1, "entity": "layout-profile",
                "asset_id": "builtin:layout:px-x", "name": "X",
                "aliases": ["PX"],
                "canvas": {"width": 1280, "height": 720, "units": "logical-px"},
                "page_role": "content", "layout_type": "fixed-regions",
                "slots": {"stub": {"region": "content",
                                   "desc": "槽存在但无 count_max/max_chars"}},
                "renderer_support": {"render:html": None, "image": None},
            }), encoding="utf-8")
            (library / "library.json").write_text(json.dumps({
                "schema_version": 1, "kind": "template-library",
                "library_id": "builtin",
                "zones": {"canonical": "c", "reference": "r", "governance": "g",
                          "catalog": "k", "evidence": "e"},
                "reserved_directory_names": [],
            }), encoding="utf-8")
            from leo_ppt_generator import layout_bank
            with mock.patch.dict("os.environ", {"LEO_PPT_BUNDLE": str(bundle)}):
                forward = layout_bank.filter_layout_bank_by_capacity(
                    "title<=8,stub<=4"
                )
                backward = layout_bank.filter_layout_bank_by_capacity(
                    "stub<=4,title<=8"
                )
        self.assertEqual(forward["missing"], {"PX": ["stub"]})
        self.assertEqual(forward["missing"], backward["missing"])
        self.assertEqual(forward["matched"], [])


class CliDispatchContract(unittest.TestCase):
    """--capacity 的 CLI 接线层合同：信封 reason_code、缺省行为、互斥、空串。"""

    def _run(self, *argv: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "PYTHONPATH": str(RUNTIME_SRC)}
        return subprocess.run(
            [sys.executable, "-m", "leo_ppt_generator", *argv],
            cwd=SKILL_DIR, capture_output=True, text=True, env=env,
        )

    def test_capacity_success_envelope_shape(self):
        proc = self._run("style", "layouts", "--capacity", "items<=4")
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["reason_code"], "layout_bank_capacity_filtered")
        self.assertIn("P6", [m["layout_id"] for m in payload["matched"]])
        self.assertEqual(payload["missing"], {})

    def test_capacity_syntax_error_keeps_stable_reason_code(self):
        """语法错误的信封 reason_code 必须是 capacity_filter_invalid，
        不得坍缩为泛化 layout_bank_error（审查 P1 回归锁）。"""
        proc = self._run("style", "layouts", "--capacity", "title=8")
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stderr)
        self.assertEqual(payload["reason_code"], "capacity_filter_invalid")

    def test_capacity_empty_string_errors_not_full_list(self):
        """空串条件必须报错，不得被 falsy 守卫吞掉回落全量列表。"""
        proc = self._run("style", "layouts", "--capacity", "")
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stderr)
        self.assertEqual(payload["reason_code"], "capacity_filter_invalid")

    def test_capacity_conflicts_with_layout_flag(self):
        """互斥冲突走 blocked 信封（envelope 合同：detail 不进输出字段，
        冲突行为由 returncode 2 + capacity_filter_invalid 族锁定）。"""
        proc = self._run(
            "style", "layouts", "--capacity", "items<=4", "--layout", "P6"
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stderr)
        self.assertEqual(payload["reason_code"], "capacity_filter_invalid")

    def test_default_listing_reason_code_unchanged(self):
        """缺省调用信封与 reason_code 不受新旗标影响（缺省字节红线）。"""
        proc = self._run("style", "layouts")
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["reason_code"], "layout_bank_listed")
        self.assertEqual(len(payload["layouts"]), 42)
        self.assertNotIn("matched", payload)
        self.assertNotIn("capacity_filter", payload)


if __name__ == "__main__":
    unittest.main()
