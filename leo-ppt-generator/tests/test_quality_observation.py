"""观测写方：固定分母、幂等追加、关闭后不可篡改与消费者对账。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from leo_ppt_generator import quality_metrics as metrics


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "run.json").write_text(json.dumps({"run_id": "r"}))

    def start(self):
        return metrics.start_observation(self.root, window="production", target_pages=["1", "2"],
                                         phase="after-authorization")

    def row(self, identity="tf1", page="1"):
        return {"schema_version": 1, "event_id": identity, "run_id": "r",
                "window": "production", "phase": "after-authorization", "kind": "tf",
                "source": "runtime", "payload": {"page": page, "triggers": ["TF-1"],
                "complete": False, "generation_method": "image"}}

    def test_window_and_event_replay_are_idempotent(self):
        self.start()
        first = (self.root / "observability/quality-window.json").read_bytes()
        self.start()
        self.assertEqual(first, (self.root / "observability/quality-window.json").read_bytes())
        metrics.record_quality_event(self.root, self.row())
        metrics.record_quality_event(self.root, self.row())
        result = metrics.scorecard_for_run(self.root)
        self.assertEqual(result["tf"]["event_count"], 1)
        self.assertEqual(result["tf"]["K"], 1)

    def test_changed_target_set_rejected(self):
        self.start()
        with self.assertRaises(metrics.MetricEventError):
            metrics.start_observation(self.root, window="production", target_pages=["1"],
                                      phase="after-authorization")

    def test_new_window_after_preparation_cannot_claim_early_freeze(self):
        (self.root / "image-deck").mkdir()
        (self.root / "image-deck/slide_jobs.json").write_text("{}")
        with self.assertRaises(metrics.MetricEventError):
            self.start()

    def test_event_before_start_and_foreign_run_rejected(self):
        with self.assertRaises(metrics.MetricEventError):
            metrics.record_quality_event(self.root, self.row())
        self.start()
        with self.assertRaises(metrics.MetricEventError):
            metrics.record_quality_event(self.root, {**self.row(), "run_id": "other"})

    def test_conflicting_identity_does_not_change_file(self):
        self.start()
        metrics.record_quality_event(self.root, self.row())
        path = self.root / "observability/quality-events.jsonl"
        before = path.read_bytes()
        with self.assertRaises(metrics.MetricEventError):
            metrics.record_quality_event(self.root, self.row(page="2"))
        self.assertEqual(before, path.read_bytes())

    def test_concurrent_writers_do_not_lose_events(self):
        self.start()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: metrics.record_quality_event(self.root, self.row(str(i))), range(12)))
        self.assertEqual(metrics.scorecard_for_run(self.root)["tf"]["event_count"], 12)

    def test_user_feedback_requires_real_transition_order(self):
        self.start()
        def feedback(state):
            return {**self.row(), "event_id": "feedback:" + state, "kind": "rework",
                    "source": "user-feedback", "payload": {"feedback_id": "f1", "pages": ["1", "2"],
                    "reason": "layout", "actor": "user", "state": state}}
        with self.assertRaises(metrics.MetricEventError):
            metrics.record_quality_event(self.root, feedback("presented"))
        for state in ("received", "revised", "presented"):
            metrics.record_quality_event(self.root, feedback(state))
        self.assertEqual(metrics.scorecard_for_run(self.root)["rework"]["completed_rounds"], 1)
        with self.assertRaises(metrics.MetricEventError):
            metrics.record_quality_event(self.root, feedback("cancelled"))

    def test_runtime_tf_writer_deduplicates_and_preserves_missing_coverage(self):
        self.start()
        for _ in range(2):
            metrics.record_runtime_tf(self.root, page=1, operation_id="op", triggers=["TF-1"],
                                      generation_method="image")
        result = metrics.scorecard_for_run(self.root)["tf"]
        self.assertEqual((result["K"], result["U"], result["event_count"]), (1, 1, 1))

    def test_close_seals_bytes_but_does_not_invent_billing_completeness(self):
        self.start()
        metrics.record_quality_event(self.root, self.row())
        metrics.close_observation(self.root)
        metrics.record_quality_event(self.root, self.row())
        with self.assertRaises(metrics.MetricEventError):
            metrics.record_quality_event(self.root, self.row("new"))
        result = metrics.scorecard_for_run(self.root)
        self.assertTrue(result["observation_closed"])
        self.assertFalse(result["cost"]["window_complete"])
        self.assertEqual(result["tf"]["U"], 1)

    def test_closed_stream_tampering_is_rejected(self):
        self.start()
        metrics.record_quality_event(self.root, self.row())
        metrics.close_observation(self.root)
        path = self.root / "observability/quality-events.jsonl"
        path.write_text(path.read_text()+json.dumps(self.row("injected"))+"\n")
        with self.assertRaises(metrics.MetricEventError):
            metrics.scorecard_for_run(self.root)

    def test_cli_records_through_same_owner(self):
        targets = self.root / "targets.json"
        targets.write_text('["1","2"]')
        event = self.root / "event.json"
        event.write_text(json.dumps(self.row()))
        def cli(*args):
            return subprocess.run([sys.executable, "-m", "leo_ppt_generator", "quality", *args],
                                  capture_output=True, text=True)
        result = cli("start", str(self.root), "--window", "production", "--target-pages", str(targets),
                     "--phase", "after-authorization")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = cli("record", str(self.root), "--event", str(event))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(metrics.scorecard_for_run(self.root)["tf"]["K"], 1)

    def test_frozen_local_render_replay_hashes_and_results(self):
        import hashlib
        fixture = Path(__file__).resolve().parents[1] / "evals/fixtures/quality-replay-v1"
        manifest_bytes = (fixture / "manifest.json").read_bytes()
        self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), "649df6882db59076c120c111bc557ce43252c8c1f599f85b839aff6d05febfd6")
        manifest = json.loads(manifest_bytes)
        for path, digest in manifest["sha256"].items():
            self.assertEqual(hashlib.sha256((fixture / path).read_bytes()).hexdigest(), digest, path)
        actual = metrics.scorecard_for_run(fixture)
        expected = json.loads((fixture / "expected-scorecard.json").read_text())
        self.assertEqual(actual, expected)
        self.assertEqual(actual["tf"]["N"], 2)
        self.assertEqual(actual["cost"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
