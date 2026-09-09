import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evals/fixtures/scripts/judge_content_execution_boundary.py"
spec = importlib.util.spec_from_file_location("content_boundary", SCRIPT)
judge = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(judge)


class ContentExecutionBoundaryTest(unittest.TestCase):
    def test_requires_project_path(self):
        self.assertTrue(judge.check("已完成 outline", ""))

    def test_accepts_declared_stop_boundary(self):
        transcript = json.dumps({
            "type": "tool_use", "name": "Bash",
            "input": {"command": "leo-ppt style render --summary"},
        }, ensure_ascii=False)
        self.assertEqual(judge.check("产物：./project/content/outline-v1.md", transcript), [])

    def test_rejects_worker_provider_and_image_generation(self):
        transcript = json.dumps([
            {"type": "tool_use", "name": "dispatch_worker", "input": {}},
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "image generate --provider foo"}},
        ], ensure_ascii=False)
        errors = judge.check("产物：project/content/outline-v1.md", transcript)
        self.assertGreaterEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
