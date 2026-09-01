#!/usr/bin/env python3
"""build_rendered_ledger.py 单元测试（R-41 渲染事实账本）：slide_jobs 聚合 /
OCR 摘要与数值抽取 top5 / 图表计数 / 无 OCR 页如实 missing（notes 兜底标注
source）/ 确定性（逐字节一致）/ 无页记录 exit 2 / fallback 扫描
origin_image+events。"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_rendered_ledger.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def make_run(tmp: Path) -> Path:
    run_dir = tmp / "runs" / "imgdeck-v1"
    (run_dir / "image-deck" / "origin_image").mkdir(parents=True)
    (run_dir / "reports").mkdir(parents=True)
    return run_dir


def make_jobs(run_dir: Path, pages: list[dict]) -> None:
    (run_dir / "image-deck" / "slide_jobs.json").write_text(
        json.dumps({"delivery": {"pages": pages}}, ensure_ascii=False), encoding="utf-8")


PAGE_1 = {
    "page_id": "page_001",
    "artifact_ref": "x/origin_image/slide_01.png",
    "artifact_sha256": "a" * 64,
    "notes": "营收 1.24 亿元，环比 +18%；无图。",
}
PAGE_2 = {
    "page_id": "page_002",
    "artifact_ref": "x/origin_image/slide_02.png",
    "artifact_sha256": "b" * 64,
    "notes": None,
}


class BuildRenderedLedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = make_run(Path(self._tmp.name))
        self.out = self.run_dir / "reports" / "rendered-ledger.json"

    def tearDown(self):
        self._tmp.cleanup()

    def ledger(self):
        return json.loads(self.out.read_text(encoding="utf-8"))

    def test_aggregates_pages_from_slide_jobs(self):
        make_jobs(self.run_dir, [PAGE_1, PAGE_2])
        proc = run(str(self.run_dir))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = self.ledger()
        self.assertEqual(data["pages_total"], 2)
        self.assertEqual([p["page_id"] for p in data["pages"]], ["page_001", "page_002"])
        self.assertEqual(data["pages"][0]["artifact_sha256"], "a" * 64)
        self.assertEqual(data["pages"][0]["notes_head"][:6], "营收 1.2")

    def test_ocr_page_summary_numbers_and_head(self):
        make_jobs(self.run_dir, [PAGE_1])
        ocr = self.run_dir / "reports" / "ocr"
        ocr.mkdir()
        (ocr / "page_1.txt").write_text(
            "智能解决率 41%→68%\n转接率 17%→4.1%\n响应 86 秒→31 秒\n"
            "规则 2→22 条/日\n节约 ~1200 万元/年\n图表 1：对比小表 图[F1]", encoding="utf-8")
        run(str(self.run_dir))
        page = self.ledger()["pages"][0]
        self.assertEqual(page["ocr_status"], "ok")
        self.assertIn("41%→68%", page["ocr_text_head"])
        numbers = page["key_numbers"]
        self.assertEqual(len(numbers), 5)  # top-k dedup, insertion order
        self.assertEqual(numbers[0], "41%")
        self.assertEqual(page["chart_count"], 2)  # 图表 + 图[F1] both counted

    def test_missing_ocr_page_marked_with_notes_fallback(self):
        make_jobs(self.run_dir, [PAGE_1, PAGE_2])
        run(str(self.run_dir))
        data = self.ledger()
        self.assertEqual(data["pages_missing_ocr"], 2)
        p1 = data["pages"][0]
        self.assertEqual(p1["ocr_status"], "missing")
        self.assertIsNone(p1["ocr_text_head"])
        self.assertEqual(p1["key_numbers"][0]["value"], "1.24 亿元")
        self.assertEqual(p1["key_numbers"][0]["source"], "notes")
        p2 = data["pages"][1]
        self.assertEqual(p2["key_numbers"], [])
        self.assertIsNone(p2["notes_head"])

    def test_deterministic_byte_identical_output(self):
        make_jobs(self.run_dir, [PAGE_1, PAGE_2])
        (self.run_dir / "reports" / "ocr").mkdir()
        (self.run_dir / "reports" / "ocr" / "page_1.txt").write_text(
            "文本 100%\n图表", encoding="utf-8")
        run(str(self.run_dir))
        first = self.out.read_bytes()
        run(str(self.run_dir))
        self.assertEqual(first, self.out.read_bytes())

    def test_no_page_records_exits_two(self):
        proc = run(str(self.run_dir))
        self.assertEqual(proc.returncode, 2)

    def test_fallback_scan_origin_image_and_events(self):
        png = self.run_dir / "image-deck" / "origin_image" / "slide_01.png"
        png.write_bytes(b"png")
        self.run_dir.joinpath("events.ndjson").write_text(
            json.dumps({"kind": "image.recorded", "data": {
                "slide_id": "slide_02", "artifact_ref": str(png)}},
                ensure_ascii=False) + "\n", encoding="utf-8")
        proc = run(str(self.run_dir))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = self.ledger()
        self.assertEqual(data["source"]["slide_jobs"], "origin_image+events")
        self.assertEqual(data["pages_total"], 2)
        self.assertEqual(data["pages"][0]["artifact_sha256"],
                         hashlib.sha256(b"png").hexdigest())

    def test_custom_out_path_and_head_chars(self):
        make_jobs(self.run_dir, [PAGE_1])
        out = self.run_dir / "rendered.json"
        proc = run(str(self.run_dir), "--out", str(out), "--head-chars", "5")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = json.loads(out.read_text(encoding="utf-8"))["pages"][0]
        self.assertEqual(page["notes_head"], "营收 1.2"[:5])

    def test_missing_run_dir_is_usage_error(self):
        self.assertEqual(run(str(self.run_dir / "nope")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
