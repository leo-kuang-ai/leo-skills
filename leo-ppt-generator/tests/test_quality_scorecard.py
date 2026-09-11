"""记分卡必须只读，并拒绝污染交付指纹的输出路径。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_quality_scorecard.py"


class ScorecardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "observability").mkdir()

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.root), *map(str, args)],
                              capture_output=True, text=True)

    def hashes(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()}

    def configure(self):
        (self.root / "observability" / "quality-window.json").write_text(json.dumps({
            "schema_version": 1, "run_id": "r", "window": "w", "target_pages": ["1"]}))

    def test_empty_run_reports_unknown_without_writing(self):
        before = self.hashes()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "blocked")
        self.assertEqual(self.hashes(), before)

    def test_real_file_stream_is_aggregated_without_touching_inputs(self):
        self.configure()
        row = {"schema_version": 1, "event_id": "e", "kind": "tf", "run_id": "r",
               "window": "w", "phase": "after-authorization", "source": "runtime",
               "payload": {"page": "1", "triggers": ["TF-1"], "complete": True,
                           "generation_method": "image"}}
        (self.root / "observability" / "quality-events.jsonl").write_text(json.dumps(row)+"\n")
        before = self.hashes()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["tf"]["K"], 1)
        self.assertEqual(self.hashes(), before)

    def test_explicit_output_only_adds_scorecard(self):
        self.configure()
        before = self.hashes()
        result = self.invoke("--out", self.root / "scorecard" / "quality-scorecard.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.hashes()
        self.assertEqual(set(after) - set(before), {"scorecard/quality-scorecard.json"})
        self.assertTrue(all(after[p] == digest for p, digest in before.items()))

    def test_reports_and_symlink_outputs_are_rejected(self):
        self.configure()
        with tempfile.TemporaryDirectory() as external:
            (self.root / "scorecard").symlink_to(external, target_is_directory=True)
            for output in [self.root / "reports" / "x.json",
                           self.root / "scorecard" / "quality-scorecard.json"]:
                result = self.invoke("--out", output)
                self.assertEqual(result.returncode, 2)
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_truncated_event_stream_is_not_silently_ignored(self):
        self.configure()
        (self.root / "observability" / "quality-events.jsonl").write_text('{"event_id":')
        self.assertEqual(self.invoke().returncode, 2)

    def test_backend_report_consumes_same_aggregation(self):
        self.configure()
        expected = json.loads(self.invoke().stdout)
        result = subprocess.run([sys.executable, "-m", "leo_ppt_generator", "backend",
                                 "report", str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["quality"], expected)

    def test_explicit_scorecard_preserves_all_five_receipt_fingerprints(self):
        from leo_ppt_generator.render.receipt import collect_fingerprints, create_delivery_receipt, verify_delivery_receipt
        from test_delivery_receipt import _make_mini_run
        self.configure()
        _make_mini_run(self.root)
        create_delivery_receipt(self.root)
        before = collect_fingerprints(self.root)
        self.assertEqual(len(before), 5)
        self.assertTrue(all(before.values()))
        result = self.invoke("--out", self.root / "scorecard/quality-scorecard.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(collect_fingerprints(self.root), before)
        self.assertEqual(verify_delivery_receipt(self.root)["status"], "fresh")


if __name__ == "__main__":
    unittest.main()
