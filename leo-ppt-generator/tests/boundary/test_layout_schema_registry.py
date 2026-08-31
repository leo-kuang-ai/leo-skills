#!/usr/bin/env python3
"""版式 Schema 登记核对：12_版式库 P 系文件与 版式内容Schema.md 双向一致。"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "references/styles"
SCHEMA = ROOT / "00_索引/版式内容Schema.md"
LAYOUT_DIR = ROOT / "12_版式库"


def p_files():
    return sorted(p.stem.split("_", 1)[0] for p in LAYOUT_DIR.glob("P*_*.md"))


def schema_rows():
    text = SCHEMA.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"^\|\s*(P\d+)\s", text, re.M)))


class LayoutSchemaRegistryTest(unittest.TestCase):
    def test_every_p_layout_has_schema_row(self):
        missing = [p for p in p_files() if p not in schema_rows()]
        self.assertEqual(missing, [], f"版式文件未登记 Schema: {missing}")

    def test_every_schema_p_row_has_file(self):
        files = set(p_files())
        dangling = [p for p in schema_rows() if p not in files]
        self.assertEqual(dangling, [], f"Schema 行无对应版式文件: {dangling}")

    def test_new_batch_layouts_registered(self):
        rows = set(schema_rows())
        for p in ("P23", "P24", "P25", "P26", "P27", "P28", "P29"):
            self.assertIn(p, rows, f"{p} 未登记")


if __name__ == "__main__":
    unittest.main()
