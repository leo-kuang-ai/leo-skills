#!/usr/bin/env python3
"""check_table_values.py 单测：全命中 / 值缺失 / 单位缺失降级 / 千分位归一。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_table_values.py"

EXPECTED = [
    {"value": "1.24", "unit": "亿元", "page": 2, "container": "KPI 塔"},
    {"value": "12,800", "unit": "万元", "page": 5, "container": "规格表 B3"},
    {"value": "37", "unit": "家", "page": 5, "container": "规格表 B2"},
]
OCR_P2 = "营收 1.24 亿元，创单季新高"
OCR_P5 = "投入 12800 万元；新签 37 家客户"


def _run(expected, ocr_texts):
    d = tempfile.mkdtemp()
    exp = Path(d) / "expected.json"
    exp.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
    ocr = Path(d) / "ocr"
    ocr.mkdir()
    for page, text in ocr_texts.items():
        (ocr / f"page_{page}.txt").write_text(text, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), str(exp), str(ocr)],
                       capture_output=True, text=True)
    return r.returncode, r.stderr, r.stdout


class TableValuesTest(unittest.TestCase):
    def test_all_hit_passes(self):
        code, err, out = _run(EXPECTED, {2: OCR_P2, 5: OCR_P5})
        self.assertEqual(code, 0, err)
        self.assertIn("missing_values=0", out)

    def test_missing_value_fails(self):
        code, err, _ = _run(EXPECTED, {2: OCR_P2, 5: "只有文字没有数字"})
        self.assertEqual(code, 1)
        self.assertIn("MISSING-VALUE", err)

    def test_missing_unit_degrades_not_fails(self):
        exp = [dict(EXPECTED[0], unit="亿元")]
        code, err, out = _run(exp, {2: "营收 1.24（单位漏了）"})
        self.assertEqual(code, 0)
        self.assertIn("missing_units=1", out)

    def test_thousand_separator_normalized(self):
        code, _, out = _run(EXPECTED, {2: OCR_P2, 5: OCR_P5.replace("12800", "12,800")})
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
