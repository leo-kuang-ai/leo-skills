#!/usr/bin/env python3
"""record_run_step.py 单元测试（R-37 run 阶段账本）：追加与字段（artifact
sha256）/ tail 查看 / 中断后续点建议（最后未完成页与阶段）/ 全完成态 /
重试预算耗尽 exit 2 / 闭合状态矛盾 exit 2 / 页内阶段缺 page exit 4 /
未知 step 被拒绝。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_run_step.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


class RecordRunStepTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self._tmp.name) / "runs" / "imgdeck-v1"
        (self.run_dir / "reports").mkdir(parents=True)
        self.artifact = self.run_dir / "image-deck" / "origin_image" / "slide_01.png"
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_bytes(b"png-bytes")
        self.ledger = self.run_dir / "reports" / "run-ledger.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def rec(self, *args):
        return run("--run", str(self.run_dir), *args)

    def lines(self):
        return [json.loads(l) for l in
                self.ledger.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_mixed_numeric_and_string_page_rows_resume_without_mutation(self):
        rows = [{"page": 1, "step": "prompt", "status": "completed"},
                {"page": "1", "step": "backend", "status": "completed"},
                {"page": "2", "step": "prompt", "status": "completed"}]
        self.ledger.write_text("\n".join(map(json.dumps, rows)) + "\n")
        before = self.ledger.read_bytes()
        result = self.rec("--resume-suggestion")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("resume_from: 1/qa", result.stdout)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_append_step_records_fields_and_artifact_sha256(self):
        proc = self.rec("--step", "backend", "--page", "1", "--attempt", "2",
                        "--status", "completed",
                        "--problems-json", '["429 限流一次"]',
                        "--artifact", "image-deck/origin_image/slide_01.png")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = json.loads(proc.stdout)
        self.assertEqual(entry["step"], "backend")
        self.assertEqual(entry["page"], "1")
        self.assertEqual(entry["attempt"], 2)
        self.assertEqual(entry["problems"], ["429 限流一次"])
        self.assertEqual(entry["artifact"], "image-deck/origin_image/slide_01.png")
        self.assertEqual(entry["artifact_sha256"],
                         __import__("hashlib").sha256(b"png-bytes").hexdigest())
        self.assertIn("ts", entry)  # ts allowed: ledger is temporal by nature
        self.assertEqual(len(self.lines()), 1)

    def test_tail_shows_last_n_entries(self):
        for page in ("1", "2", "3"):
            self.rec("--step", "record", "--page", page, "--status", "completed")
        proc = self.rec("--tail", "2")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        shown = [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]
        self.assertEqual([e["page"] for e in shown], ["2", "3"])

    def test_resume_suggestion_points_to_last_open_page_and_step(self):
        for step in ("prompt", "backend", "qa", "record"):
            self.rec("--step", step, "--page", "1", "--status", "completed")
        self.rec("--step", "prompt", "--page", "2", "--status", "completed")
        self.rec("--step", "backend", "--page", "2", "--status", "started")
        proc = self.rec("--resume-suggestion")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("resume_from: 2/backend", proc.stdout)
        self.assertIn("不重做已 completed 阶段", proc.stdout)

    def test_resume_suggestion_all_recorded_points_to_receipt(self):
        for page in ("1", "2"):
            for step in ("prompt", "backend", "qa", "record"):
                self.rec("--step", step, "--page", page, "--status", "completed")
        proc = self.rec("--resume-suggestion")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("receipt", proc.stdout)

    def test_retry_budget_exhausted_needs_human_exit_two(self):
        self.rec("--step", "prompt", "--page", "1", "--status", "completed")
        for attempt in (1, 2, 3):
            self.rec("--step", "backend", "--page", "1",
                     "--attempt", str(attempt), "--status", "failed")
        proc = self.rec("--resume-suggestion")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("重复失败纪律", proc.stdout)
        self.assertIn("必须改变输入", proc.stdout)

    def test_contradictory_closed_states_detected(self):
        self.rec("--step", "qa", "--page", "1", "--status", "completed")
        self.rec("--step", "qa", "--page", "1", "--status", "failed")
        proc = self.rec("--resume-suggestion")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("矛盾", proc.stdout)

    def test_page_step_requires_page_flag(self):
        proc = self.rec("--step", "qa", "--status", "completed")
        self.assertEqual(proc.returncode, 4)

    def test_receipt_is_deck_level_without_page(self):
        proc = self.rec("--step", "receipt", "--status", "completed")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(json.loads(proc.stdout)["page"])

    def test_unknown_step_rejected(self):
        proc = self.rec("--step", "bogus", "--page", "1", "--status", "completed")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.ledger.exists(), False)

    def test_empty_ledger_suggestion_starts_from_scratch(self):
        proc = self.rec("--resume-suggestion")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("从首个页的 prompt 阶段开始", proc.stdout)

    def test_append_only_never_rewrites_history(self):
        self.rec("--step", "prompt", "--page", "1", "--status", "completed")
        first = self.ledger.read_text(encoding="utf-8")
        self.rec("--step", "prompt", "--page", "1", "--status", "completed")
        self.assertTrue(self.ledger.read_text(encoding="utf-8").startswith(first))


if __name__ == "__main__":
    unittest.main()
