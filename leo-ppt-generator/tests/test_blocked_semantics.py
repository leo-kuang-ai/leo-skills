"""U9/债8 blocked 三口径统一回归：editable status 计数、next 建议、
runs_console 页态投影、dispatch 拒绝与 lifecycle 复位口径一致。

统一语义：blocked 是独立终态——不并入 pending、不被建议派发；恢复只有
reset_failed_pages 一条通道（与 lifecycle.reset_failed_pages 的复位集合
{failed, blocked, timeout} 一致）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.editable.adapter import EditableAdapter  # noqa: E402
from leo_ppt_generator.runs_console import RunScanner  # noqa: E402


def write_page_jobs(run: Path, statuses: list[str]) -> None:
    (run / "editable").mkdir(parents=True, exist_ok=True)
    pages = [
        {"page_id": f"page_{number:03d}", "number": number, "status": status,
         "source": f"/tmp/src-{number}.png", "source_sha256": "x" * 64, "notes": ""}
        for number, status in enumerate(statuses, 1)
    ]
    (run / "editable/page_jobs.json").write_text(
        json.dumps({"schema_version": 1, "revision": 3, "run_status": "prepared",
                    "pages": pages, "operations": {}}, ensure_ascii=False),
        encoding="utf-8")


class EditableStatusBlockedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run = Path(self._tmp.name)
        self.adapter = EditableAdapter(self.run / "editable")

    def test_blocked_pages_counted_as_blocked_not_pending(self):
        write_page_jobs(self.run, ["recorded", "blocked", "blocked"])
        report = self.adapter.status()
        self.assertEqual(report["progress"]["blocked"], 2)
        self.assertEqual(report["progress"]["pending"], 0)
        self.assertEqual(report["progress"]["completed"], 1)

    def test_blocked_only_next_action_is_reset_not_dispatch(self):
        write_page_jobs(self.run, ["blocked", "blocked"])
        report = self.adapter.status()
        self.assertEqual(report["next_action"]["kind"], "reset_failed_pages")
        self.assertEqual(report["next_action"]["payload"]["page_count"], 2)
        self.assertEqual(report["reason_code"], "page_recovery_required")

    def test_mixed_pending_and_blocked_dispatch_suggests_pending_only(self):
        write_page_jobs(self.run, ["pending", "blocked"])
        report = self.adapter.status()
        self.assertEqual(report["next_action"]["kind"], "request_worker_dispatch")
        self.assertEqual(report["next_action"]["payload"]["page_count"], 1,
                         "派发建议只数 pending，blocked 页不得入列")

    def test_failed_and_blocked_share_recovery_channel(self):
        write_page_jobs(self.run, ["failed", "blocked", "timeout"])
        report = self.adapter.status()
        self.assertEqual(report["next_action"]["kind"], "reset_failed_pages")
        self.assertEqual(report["next_action"]["payload"]["page_count"], 3)

    def test_dispatch_still_rejects_blocked_page(self):
        write_page_jobs(self.run, ["blocked"])
        prompt = self.run / "prompt.md"
        prompt.write_text("worker prompt", encoding="utf-8")
        with self.assertRaises(Exception) as ctx:
            self.adapter.dispatch("page_001", "agent-1", prompt)
        self.assertEqual(str(ctx.exception), "editable_dispatch_state_conflict")

    def test_lifecycle_reset_restores_blocked_to_pending(self):
        from leo_ppt_generator.lifecycle import Lifecycle

        write_page_jobs(self.run, ["blocked"])
        result = Lifecycle(self.run).reset_failed_pages()
        self.assertEqual(result["reset_units"], ["page_001"])
        jobs = json.loads((self.run / "editable/page_jobs.json").read_text(encoding="utf-8"))
        self.assertEqual(jobs["pages"][0]["status"], "pending")


class ConsoleProjectionBlockedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.run = self.home / "projects" / "p" / "runs" / "run-blocked1"
        (self.run / "image-deck").mkdir(parents=True)
        (self.run / "run.json").write_text(json.dumps({
            "schema_version": 1, "run_id": "blocked1", "route": "generate",
            "runtime_identity": "fixture", "revision": 1, "status": "in_progress",
            "stage": "image.dispatch", "page_order": [1, 2],
            "domains": {"image": {"path": "image-deck",
                                  "progress": {"total_units": 2, "completed": 1,
                                               "failed": 0, "active": 0, "pending": 0,
                                               "estimated_remaining_seconds": None}},
                        "editable": {"path": "editable"}},
        }), encoding="utf-8")
        (self.run / "image-deck/slide_jobs.json").write_text(json.dumps({
            "schema_version": 1, "revision": 2, "run_status": "prepared",
            "operations": {},
            "slides": [
                {"number": 1, "slide_id": "slide_01", "status": "recorded",
                 "artifact": "origin_image/slide_01.png", "notes": None},
                {"number": 2, "slide_id": "slide_02", "status": "blocked", "notes": None},
            ],
        }), encoding="utf-8")
        self.scanner = RunScanner(self.home)

    def test_console_shows_blocked_state_not_pending(self):
        info = {"dir": self.run, "run_json": json.loads(
            (self.run / "run.json").read_text(encoding="utf-8"))}
        pages = self.scanner._pages_of(info, None)
        by_id = {page["unit_id"]: page["state"] for page in pages}
        self.assertEqual(by_id["slide_01"], "recorded")
        self.assertEqual(by_id["slide_02"], "blocked",
                         "控制台页态必须把 blocked 显示为独立状态，不得并入 pending")


if __name__ == "__main__":
    unittest.main()
