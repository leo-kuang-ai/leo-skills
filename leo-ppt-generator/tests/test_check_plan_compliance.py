#!/usr/bin/env python3
"""check_plan_compliance.py 单元测试（R-43 计划履约报告）：四档 status /
偏差条目结构（point/evidence/suggestion）/ 丢一条要点→partial_deviation /
OCR 目录优先于 ledger 摘要 / 偏差上限截断 / 线索级非门禁（exit 0）/ 用法
错误 exit 2 / 确定性输出。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_plan_compliance.py"

MASTER = """# 母版

## S1 市场概览
- 页面角色：章节
- 标题：智能客服市场进入放量期
- 视觉行：要点1→结论条

## S2 核心指标
- 标题：智能解决率翻倍
- 要点1：智能解决率从 41% 提升到 68%（引用）
- 要点2：转接率由 17% 降至 4.1%
- 要点3：坐席响应时间从 86 秒缩短至 31 秒
- 视觉行：要点1→大数字卡；要点2→对比条；要点3→对比条

## S3 客户证言
- 标题：头部客户实证
- 要点1：某零售集团年节约 1200 万元服务成本【引用|src:案例页】
- 视觉行：要点1→证言卡
"""


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8")


def make_ledger(pages: list[dict]) -> dict:
    return {
        "schema_version": 1, "kind": "rendered-ledger", "run": "r",
        "pages_total": len(pages), "pages_missing_ocr": 0, "pages": pages,
    }


class PlanComplianceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.run_dir = self.root / "runs" / "imgdeck-v1"
        (self.run_dir / "reports").mkdir(parents=True)
        self.master = self.root / "deck-master-v1.md"
        self.master.write_text(MASTER, encoding="utf-8")
        self.out = self.run_dir / "reports" / "plan-compliance.json"

    def tearDown(self):
        self._tmp.cleanup()

    def write_ledger(self, pages: list[dict]):
        (self.run_dir / "reports" / "rendered-ledger.json").write_text(
            json.dumps(make_ledger(pages), ensure_ascii=False), encoding="utf-8")

    def report(self):
        return json.loads(self.out.read_text(encoding="utf-8"))

    def test_full_match_and_na_functional_page(self):
        self.write_ledger([
            {"page_id": "page_001", "slide_no": 1, "ocr_status": "ok",
             "ocr_text_head": "智能客服市场", "notes_head": None},
            {"page_id": "page_002", "slide_no": 2, "ocr_status": "ok",
             "ocr_text_head": "智能解决率 41%→68% 转接率 17%→4.1% 坐席响应时间 86 秒→31 秒",
             "notes_head": None},
            {"page_id": "page_003", "slide_no": 3, "ocr_status": "ok",
             "ocr_text_head": "某零售集团 年节约 1200 万元 服务成本",
             "notes_head": None},
        ])
        proc = run("--master", str(self.master), "--run", str(self.run_dir))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = self.report()
        by_page = {p["page_no"]: p for p in data["pages"]}
        self.assertEqual(by_page[1]["status"], "na")  # 章节 page role
        self.assertEqual(by_page[1]["reason"], "functional_page")
        self.assertEqual(by_page[2]["status"], "full")
        self.assertEqual(by_page[3]["status"], "full")
        self.assertEqual(data["summary"]["status_counts"]["full"], 2)
        self.assertEqual(data["deviations"], [])

    def test_dropped_point_yields_partial_deviation_with_entry(self):
        # 31 秒 / 86 秒 never rendered: bullet 3 dropped from the page.
        self.write_ledger([
            {"page_id": "page_002", "slide_no": 2, "ocr_status": "ok",
             "ocr_text_head": "智能解决率 41% 68% 转接率 17% 4.1%",
             "notes_head": None},
        ])
        proc = run("--master", str(self.master), "--run", str(self.run_dir))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = self.report()
        page2 = next(p for p in data["pages"] if p["page_no"] == 2)
        self.assertEqual(page2["status"], "partial_deviation")
        dev = data["deviations"][0]
        self.assertEqual(dev["page"], 2)
        self.assertIn("坐席响应时间", dev["point"])
        self.assertIn("86 秒", dev["evidence"])
        self.assertIn("31 秒", dev["evidence"])
        self.assertIn("rendered-ledger", dev["evidence"])
        for key in ("point", "evidence", "suggestion"):
            self.assertTrue(dev[key], f"deviation entry missing {key}")

    def test_missing_ocr_page_reported_as_missing_not_fabricated(self):
        self.write_ledger([
            {"page_id": "page_002", "slide_no": 2, "ocr_status": "missing",
             "ocr_text_head": None, "notes_head": None},
        ])
        proc = run("--master", str(self.master), "--run", str(self.run_dir))
        self.assertEqual(proc.returncode, 0)
        data = self.report()
        page2 = next(p for p in data["pages"] if p["page_no"] == 2)
        self.assertEqual(page2["status"], "missing")
        self.assertEqual(page2["reason"], "ocr_text_missing")
        # S3 is absent from the ledger entirely → also missing (honest report).
        self.assertEqual(data["summary"]["status_counts"]["missing"], 2)
        self.assertTrue(any(d["page"] == 2 for d in data["deviations"]))

    def test_page_absent_from_ledger_is_missing(self):
        self.write_ledger([])  # ledger exists but covers nothing
        (self.run_dir / "reports" / "rendered-ledger.json").unlink()
        proc = run("--master", str(self.master), "--ledger",
                   str(self.run_dir / "reports" / "rendered-ledger.json"))
        self.assertEqual(proc.returncode, 2, "missing ledger file is a usage error")
        # empty ledger: all content pages missing
        self.write_ledger([])
        proc = run("--master", str(self.master), "--run", str(self.run_dir))
        self.assertEqual(proc.returncode, 0)
        counts = self.report()["summary"]["status_counts"]
        self.assertEqual(counts["missing"], 2)  # S2 + S3 (S1 is functional)
        self.assertEqual(counts["na"], 1)

    def test_ocr_dir_full_text_wins_over_ledger_head(self):
        # Ledger head truncated so the number fell off; full OCR file saves it.
        self.write_ledger([
            {"page_id": "page_002", "slide_no": 2, "ocr_status": "ok",
             "ocr_text_head": "智能解决率 41% 68% 转接率 17% 4.1%", "notes_head": None},
        ])
        ocr = self.run_dir / "reports" / "ocr"
        ocr.mkdir()
        (ocr / "page_2.txt").write_text(
            "智能解决率 41% 68%\n转接率 17% 4.1%\n坐席响应时间 86 秒→31 秒",
            encoding="utf-8")
        proc = run("--master", str(self.master), "--run", str(self.run_dir))
        self.assertEqual(proc.returncode, 0)
        data = self.report()
        page2 = next(p for p in data["pages"] if p["page_no"] == 2)
        self.assertEqual(page2["status"], "full")
        self.assertTrue(page2["text_source"].startswith("ocr:"))

    def test_deviation_cap_truncates_and_flags(self):
        # S2 has 3 bullets; page rendered text matches none of them.
        self.write_ledger([
            {"page_id": "page_002", "slide_no": 2, "ocr_status": "ok",
             "ocr_text_head": "完全无关的文本", "notes_head": None},
        ])
        proc = run("--master", str(self.master), "--run", str(self.run_dir),
                   "--max-deviations", "1")
        self.assertEqual(proc.returncode, 0)
        data = self.report()
        self.assertEqual(len(data["deviations"]), 2)  # 1 real + 1 truncation note
        self.assertIsNone(data["deviations"][-1]["page"])
        self.assertTrue(data["summary"]["deviations_truncated"])

    def test_deviations_are_leads_not_gate_exit_zero(self):
        self.write_ledger([
            {"page_id": "page_002", "slide_no": 2, "ocr_status": "ok",
             "ocr_text_head": "毫不相干", "notes_head": None},
        ])
        proc = run("--master", str(self.master), "--run", str(self.run_dir))
        self.assertEqual(proc.returncode, 0, "线索级非门禁：偏差不改变退出码")
        self.assertIn("非门禁", self.report()["note"])

    def test_usage_errors_exit_two(self):
        proc = run("--master", str(self.root / "nope.md"), "--run",
                   str(self.run_dir))
        self.assertEqual(proc.returncode, 2)
        proc = run("--master", str(self.master))
        self.assertEqual(proc.returncode, 2)  # no rendered-text source
        proc = run("--master", str(self.master), "--ledger",
                   str(self.run_dir / "reports" / "rendered-ledger.json"))
        self.assertEqual(proc.returncode, 2)  # no --out without --run
        (self.root / "empty-master.md").write_text("# 无页母版\n", encoding="utf-8")
        self.write_ledger([])
        proc = run("--master", str(self.root / "empty-master.md"), "--run",
                   str(self.run_dir))
        self.assertEqual(proc.returncode, 2)

    def test_deterministic_byte_identical_output(self):
        self.write_ledger([
            {"page_id": "page_002", "slide_no": 2, "ocr_status": "ok",
             "ocr_text_head": "智能解决率 41% 68% 转接率 17% 4.1%", "notes_head": None},
        ])
        first = run("--master", str(self.master), "--run", str(self.run_dir),
                    "--out", str(self.root / "a.json"))
        second = run("--master", str(self.master), "--run", str(self.run_dir),
                     "--out", str(self.root / "b.json"))
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual((self.root / "a.json").read_bytes(),
                         (self.root / "b.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
