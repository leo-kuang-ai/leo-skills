"""旧回答 Judge 通过不能豁免真实咨询工具越界。"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_style_eval_traces.py"
SPEC = importlib.util.spec_from_file_location("style_eval_traces", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class StyleEvalTracesTest(unittest.TestCase):
    def test_report_requires_trace_and_rejects_shell_even_when_case_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "result.json"
            report.write_text(json.dumps({"case_results": [{"case_id": "sample", "status": "PASS", "response": "interaction_mode: advise"}]}))
            self.assertEqual(module.check(report)["failed"], 1)
            traces = root / "sample/with_skill/outputs/agent/run"
            traces.mkdir(parents=True)
            for tool, expected, arguments in (("Bash", 1, {"command": "python3 scripts/capability_manifest.py"}), ("Skill", 0, {})):
                payload = {"type": "tool_use", "name": tool, "input": arguments}
                (traces / "trace.jsonl").write_text(json.dumps(payload))
                result = module.check(report)
                self.assertEqual(result["checked"], 1)
                self.assertEqual(result["failed"], expected)

    def test_execute_does_not_inherit_advise_tool_restriction(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "result.json"
            report.write_text(json.dumps({"case_results": [{"case_id": "sample", "status": "PASS", "response": "status: ready", "prompt": "执行容量检查"}]}))
            self.assertEqual(module.check(report)["checked"], 0)


if __name__ == "__main__":
    unittest.main()
