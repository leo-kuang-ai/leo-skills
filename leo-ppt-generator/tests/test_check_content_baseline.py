#!/usr/bin/env python3
"""check_content_baseline.py 单元测试（R-36 CAS 写锁 + R-39 手改保护）：
记录建锁 / 复核一致 / 篡改检测（有限选项+不自动覆盖）/ 重锁采纳 /
锁缺失与文件缺失 / sidecar 损坏 / 并发场景双会话语义。"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_content_baseline.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


class CheckContentBaselineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.master = self.dir / "deck-master-v1.md"
        self.master.write_text("# 母版\n## S1\n- 要点 1\n", encoding="utf-8")
        self.lock = self.dir / (self.master.name + ".base-lock.json")

    def tearDown(self):
        self._tmp.cleanup()

    def _sha(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def record(self):
        return run("--record", str(self.master))

    def verify(self):
        return run("--verify", str(self.master))

    def test_record_creates_sidecar_with_sha256(self):
        proc = self.record()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.lock.is_file())
        payload = json.loads(self.lock.read_text(encoding="utf-8"))
        self.assertEqual(payload["sha256"], self._sha(self.master))
        self.assertEqual(payload["file"], "deck-master-v1.md")
        self.assertIn("recorded_at", payload)

    def test_verify_matches_baseline_exit_zero(self):
        self.record()
        proc = self.verify()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["sha256"], self._sha(self.master))

    def test_tampered_file_fails_with_finite_options_and_no_overwrite(self):
        self.record()
        locked_sha = self._sha(self.master)
        self.master.write_text("# 母版（会话外手改）\n## S1\n- 要点 1 改\n", encoding="utf-8")
        proc = self.verify()
        self.assertEqual(proc.returncode, 3)
        # Finite options wording (adopt-as-new-version / discard / view-only).
        self.assertIn("采纳为新版本", proc.stdout)
        self.assertIn("丢弃", proc.stdout)
        self.assertIn("只查看", proc.stdout)
        self.assertIn("不自动覆盖", proc.stdout)
        payload = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual(payload["status"], "baseline_drift")
        self.assertEqual(payload["locked_sha256"], locked_sha)
        # R-39: neither the file nor the lock is rewritten on drift.
        self.assertNotEqual(payload["current_sha256"], locked_sha)
        self.assertEqual(json.loads(self.lock.read_text(encoding="utf-8"))["sha256"], locked_sha)
        self.assertIn("会话外手改", self.master.read_text(encoding="utf-8"))

    def test_relock_after_adopting_new_version(self):
        self.record()
        self.master.write_text("# 母版 v2\n## S1\n- 新要点\n", encoding="utf-8")
        self.assertEqual(self.verify().returncode, 3)
        proc = self.record()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.verify().returncode, 0)

    def test_verify_without_lock_reports_usage_error(self):
        proc = self.verify()
        self.assertEqual(proc.returncode, 4)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "no_lock")

    def test_missing_file_is_usage_error_for_both_modes(self):
        gone = self.dir / "outline-v9.md"
        self.assertEqual(run("--record", str(gone)).returncode, 4)
        self.assertEqual(run("--verify", str(gone)).returncode, 4)

    def test_corrupted_sidecar_is_rejected_not_trusted(self):
        self.record()
        self.lock.write_text("{ not json", encoding="utf-8")
        proc = self.verify()
        self.assertEqual(proc.returncode, 4)
        self.assertEqual(json.loads(proc.stdout)["status"], "no_lock")

    def test_concurrent_sessions_second_writer_stops(self):
        # Session A locks, session B edits outside the flow, then a writer
        # session must stop before post-confirm writeback (contract sentence).
        self.record()
        self.master.write_text("手改内容", encoding="utf-8")
        proc = self.verify()
        self.assertEqual(proc.returncode, 3)
        self.assertIn("并发", proc.stdout)

    def test_mutually_exclusive_flags_rejected(self):
        proc = run("--record", str(self.master), "--verify", str(self.master))
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(run("--verify", str(self.master)).returncode, 4)

    def test_commit_replaces_content_and_updates_baseline(self):
        self.record()
        expected = self._sha(self.master)
        candidate = self.dir / "candidate.md"
        candidate.write_text("## S1\n停止投资\n", encoding="utf-8")
        proc = run("--commit", str(self.master), "--candidate", str(candidate),
                   "--expected-sha256", expected)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.master.read_bytes(), candidate.read_bytes())
        self.assertEqual(self.verify().returncode, 0)

    def test_two_concurrent_commits_have_one_winner(self):
        self.record()
        expected = self._sha(self.master)
        candidates = [self.dir / f"candidate-{i}.md" for i in range(2)]
        for i, candidate in enumerate(candidates):
            candidate.write_text(f"## S1\n独立候选 {i}\n", encoding="utf-8")
        processes = [subprocess.Popen(
            [sys.executable, str(SCRIPT), "--commit", str(self.master),
             "--candidate", str(candidate), "--expected-sha256", expected],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) for candidate in candidates]
        results = [process.communicate(timeout=15) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 3], results)
        winner = next(i for i, process in enumerate(processes) if process.returncode == 0)
        self.assertEqual(self.master.read_bytes(), candidates[winner].read_bytes())
        self.assertEqual(self.verify().returncode, 0)

    def test_re_record_cannot_authorize_stale_candidate(self):
        self.record()
        expected = self._sha(self.master)
        candidate = self.dir / "candidate.md"
        candidate.write_text("旧编辑", encoding="utf-8")
        self.master.write_text("已采纳的新内容", encoding="utf-8")
        self.record()
        proc = run("--commit", str(self.master), "--candidate", str(candidate),
                   "--expected-sha256", expected)
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(self.master.read_text(encoding="utf-8"), "已采纳的新内容")

    def test_commit_without_baseline_does_not_write(self):
        candidate = self.dir / "candidate.md"
        candidate.write_text("未建立基线的编辑", encoding="utf-8")
        expected = self._sha(self.master)
        proc = run("--commit", str(self.master), "--candidate", str(candidate),
                   "--expected-sha256", expected)
        self.assertEqual(proc.returncode, 4, proc.stderr)
        self.assertEqual(self._sha(self.master), expected)


if __name__ == "__main__":
    unittest.main()
