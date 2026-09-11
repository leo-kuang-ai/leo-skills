"""U13/R-81 残留观测与调度恢复回归。

覆盖：旧 operation 重放可解释失败（债2，image/editable 两链路，不再裸
KeyError）；sweep 复位的域隔离与 in-flight 保护（R-81 残留②）；WS6 调度
纪律观察哨聚合接入（R-81 残留④）。lease TTL/续期（债1）为登记残留，
不在本文件冒充已修。
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

from leo_ppt_generator.contracts import ContractError  # noqa: E402
from leo_ppt_generator.editable.adapter import EditableAdapter  # noqa: E402
from leo_ppt_generator.image_deck.adapter import ImageDeckAdapter  # noqa: E402
from leo_ppt_generator.lifecycle import Lifecycle  # noqa: E402
from leo_ppt_generator.quality_metrics import dispatch_discipline_warnings  # noqa: E402
from leo_ppt_generator.storage import sha256_file  # noqa: E402


class ImageReplayStateLostTest(unittest.TestCase):
    """债2 图像链路：reset 清掉 artifact 后同 operation 重放 → 可解释失败。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run = Path(self._tmp.name)
        self.adapter = ImageDeckAdapter(self.run / "image-deck")
        self.png = self.run / "page.png"
        from PIL import Image

        Image.new("RGB", (640, 360), "#ffffff").save(self.png)
        self.adapter.prepare([{"number": 1, "notes": ""}])
        jobs = self.adapter._jobs()
        self.adapter.record(1, self.png, backend="render:html",
                            expected_revision=jobs["revision"],
                            operation_id="op-1")

    def _reset_via_lifecycle(self):
        Lifecycle(self.run).reset_failed_pages(domain="image")

    def _vendor_overwrite_then_reset(self):
        """债2 真实链路：vendor 直写把 recorded 页状态覆盖为 failed，再复位。"""

        jobs_path = self.run / "image-deck/slide_jobs.json"
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
        jobs["slides"][0]["status"] = "failed"
        jobs["revision"] += 1
        jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
        self._reset_via_lifecycle()

    def test_replay_after_reset_raises_contract_error_not_keyerror(self):
        self._vendor_overwrite_then_reset()
        # 复位后页为 pending、artifact 字段已清、operations 仍含 op-1：
        # 同 operation 重放命中 replay 分支，必须可解释失败而非裸 KeyError。
        with self.assertRaises(ContractError) as ctx:
            self.adapter.record(
                1, self.png, backend="render:html",
                expected_revision=self.adapter._jobs()["revision"],
                operation_id="op-1")
        self.assertTrue(
            str(ctx.exception).startswith("operation_state_lost"),
            f"unexpected: {ctx.exception}")

    def test_fresh_operation_after_reset_succeeds(self):
        self._vendor_overwrite_then_reset()
        jobs = self.adapter._jobs()
        artifact = self.adapter.record(
            1, self.png, backend="render:html",
            expected_revision=jobs["revision"], operation_id="op-2")
        self.assertTrue(Path(artifact.artifact_path).is_file())


class EditableReplayStateLostTest(unittest.TestCase):
    """债2 editable 链路：reset --confirm-lost 后旧 operation 重放可解释。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run = Path(self._tmp.name)
        self.adapter = EditableAdapter(self.run / "editable")
        self.source = self.run / "src.png"
        from PIL import Image

        Image.new("RGB", (320, 180), "#eeeeee").save(self.source)
        result = self.adapter.prepare([self.source], worker_available=True)
        self.assertEqual(result["status"], "ready")

    def test_replay_after_confirm_lost_raises_contract_error(self):
        # 直接构造 recorded 页 + operation（不依赖 worker/pptx 构建链）。
        # record 的前置校验在 replay 分支之前消费 validation/pptx/manifest
        # 文件，因此三者须真实存在（reset 只清 jobs 条目字段，不动 worker
        # 目录文件——与真实链路一致）。
        jobs_path = self.run / "editable/page_jobs.json"
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
        page = jobs["pages"][0]
        pptx = self.run / "lost.pptx"
        validation = self.run / "v.json"
        manifest = self.run / "m.json"
        pptx.write_bytes(b"PK\x03\x04")
        validation.write_text(json.dumps({"passed": True}), encoding="utf-8")
        manifest.write_text(json.dumps({"source": {"width_px": 320, "height_px": 180}}),
                            encoding="utf-8")
        page.update({
            "status": "recorded", "artifact": str(pptx),
            "artifact_sha256": "a", "validation": str(validation),
            "validation_sha256": "b", "manifest": str(manifest),
            "manifest_sha256": "c", "width": 320, "height": 180,
        })
        jobs["operations"]["op-e1"] = {"fingerprint": "x", "status": "completed",
                                       "page_id": page["page_id"]}
        jobs["revision"] += 1
        jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
        # reset --confirm-lost 清掉 jobs 结果字段但保留 operations 账本。
        self.adapter.reset(page["page_id"], confirm_lost=True)
        with self.assertRaises(ContractError) as ctx:
            self.adapter.record(
                page["page_id"], pptx, validation, manifest,
                expected_revision=self.adapter._jobs()["revision"],
                operation_id="op-e1")
        self.assertTrue(
            str(ctx.exception).startswith("operation_state_lost"),
            f"unexpected: {ctx.exception}")


class ResetInflightAndDomainTest(unittest.TestCase):
    """R-81 残留②：in-flight 保护与域隔离。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run = Path(self._tmp.name)

    def _write_jobs(self, image_statuses, editable_statuses=None):
        (self.run / "image-deck").mkdir(parents=True, exist_ok=True)
        (self.run / "image-deck/slide_jobs.json").write_text(json.dumps({
            "schema_version": 1, "revision": 1, "run_status": "prepared",
            "operations": {},
            "slides": [{"number": i + 1, "slide_id": f"slide_{i + 1:02d}",
                        "status": s, "notes": None}
                       for i, s in enumerate(image_statuses)],
        }), encoding="utf-8")
        if editable_statuses is not None:
            (self.run / "editable").mkdir(parents=True, exist_ok=True)
            (self.run / "editable/page_jobs.json").write_text(json.dumps({
                "schema_version": 1, "revision": 1, "run_status": "prepared",
                "operations": {},
                "pages": [{"page_id": f"page_{i + 1:03d}", "number": i + 1,
                           "status": s, "source": "/tmp/x", "source_sha256": "y",
                           "notes": ""}
                          for i, s in enumerate(editable_statuses)],
            }), encoding="utf-8")

    def test_active_unit_blocks_reset_with_explainable_result(self):
        self._write_jobs(["failed", "active"])
        result = Lifecycle(self.run).reset_failed_pages(domain="image")
        self.assertEqual(result["reset_units"], [])
        self.assertEqual(result["blocked_by_inflight"], ["slide_02"])
        self.assertEqual(result["reason_code"], "reset_blocked_by_inflight_workers")
        # 状态未被改动。
        jobs = json.loads((self.run / "image-deck/slide_jobs.json").read_text(encoding="utf-8"))
        self.assertEqual(jobs["slides"][0]["status"], "failed")

    def test_domain_scoped_reset_leaves_other_domain_untouched(self):
        self._write_jobs(["failed"], editable_statuses=["failed"])
        result = Lifecycle(self.run).reset_failed_pages(domain="image")
        self.assertEqual(result["reset_units"], ["slide_01"])
        editable = json.loads(
            (self.run / "editable/page_jobs.json").read_text(encoding="utf-8"))
        self.assertEqual(editable["pages"][0]["status"], "failed",
                         "image 域清扫不得越界复位 editable 页")

    def test_unknown_domain_rejected(self):
        with self.assertRaises(ValueError):
            Lifecycle(self.run).reset_failed_pages(domain="console")


class DispatchWarningsAggregationTest(unittest.TestCase):
    """R-81 残留④：WS6 观察哨 → 调度纪律告警聚合计数。"""

    def test_aggregates_warnings_by_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "reports").mkdir(parents=True)
            rows = [
                {"step": "dispatch_discipline_warning", "agent_id": "w1",
                 "recorded_by_agent": 3},
                {"step": "dispatch_discipline_warning", "agent_id": "w1",
                 "recorded_by_agent": 4},
                {"step": "image.recorded", "agent_id": "w1"},
                {"step": "dispatch_discipline_warning", "agent_id": "w2",
                 "recorded_by_agent": 3},
            ]
            (run / "reports/run-ledger.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            report = dispatch_discipline_warnings(run)
            self.assertEqual(report["agents"]["w1"]["warnings"], 2)
            self.assertEqual(report["agents"]["w1"]["max_recorded_by_agent"], 4)
            self.assertEqual(report["agents"]["w2"]["warnings"], 1)

    def test_missing_ledger_reports_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = dispatch_discipline_warnings(Path(tmp))
            self.assertEqual(report["agents"], {})


if __name__ == "__main__":
    unittest.main()
