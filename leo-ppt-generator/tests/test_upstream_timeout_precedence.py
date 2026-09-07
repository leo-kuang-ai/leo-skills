"""聚焦回归（D-DEF-05）：upstream 显式 --timeout 优先于合同默认超时。

此前带 backend 合同时 CLI 旗标被静默丢弃（合同 timeout 恒胜），注入与
诊断调用无法收紧超时。语义：显式旗标 > 合同 > 无。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "runtime" / "src"))

from leo_ppt_generator import upstream_bridge  # noqa: E402


def _contract(path: Path, timeout_seconds: int = 60) -> Path:
    payload = {
        "schema_version": 1, "backend_kind": "openai-compatible",
        "provider": "openai-compatible", "mode": "generate",
        "model": "gpt-image-2",
        "credential_source": "environment-reference", "credential_ref": "env:OPENAI_API_KEY",
        "endpoint_origin": "https://example.invalid", "capabilities": {
            "generate": True, "edit": False, "mask": False,
            "execution_owner": "runtime", "max_reference_images": 0},
        "timeouts": {"backend_api_seconds": timeout_seconds, "backend_api_retries": 0},
        "selection_source": "user-confirmed",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class UpstreamTimeoutPrecedenceTest(unittest.TestCase):
    def setUp(self):
        import os
        self._previous = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "sk-test"
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-def05-")

    def tearDown(self):
        import os
        if self._previous is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = self._previous
        self._tmp.cleanup()

    def _captured_timeouts(self):
        captured = []

        def fake_run(command, *, env=None, timeout_seconds=None):
            captured.append(timeout_seconds)
            return {"returncode": 0, "stdout": "", "stderr": None, "timed_out": False}

        return captured, fake_run

    def test_explicit_flag_beats_contract_timeout(self):
        captured, fake_run = self._captured_timeouts()
        contract = _contract(Path(self._tmp.name) / "backend.json", timeout_seconds=60)
        with mock.patch.object(upstream_bridge, "_run", side_effect=fake_run):
            upstream_bridge.run_upstream(
                "codex-ppt", ["status"], backend_contract=contract, timeout_seconds=5)
        self.assertEqual(captured, [5])

    def test_contract_timeout_used_without_flag(self):
        captured, fake_run = self._captured_timeouts()
        contract = _contract(Path(self._tmp.name) / "backend.json", timeout_seconds=60)
        with mock.patch.object(upstream_bridge, "_run", side_effect=fake_run):
            upstream_bridge.run_upstream(
                "codex-ppt", ["status"], backend_contract=contract, timeout_seconds=None)
        self.assertEqual(captured, [60])


if __name__ == "__main__":
    unittest.main()
