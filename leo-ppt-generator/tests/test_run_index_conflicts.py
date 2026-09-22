#!/usr/bin/env python3
"""run_index 冲突类与 snapshot 缺失路径的聚焦回归。

覆盖两处 CLI 可观察行为：
- RevisionConflict/IdempotencyConflict 的 reason_code 透传 message 细码
  （空 message 回落类默认），不再被类属性统一掩盖；
- RunIndex.snapshot 对缺失 run.json 抛稳定 run_not_found 领域错误，
  不以裸 FileNotFoundError 冒出 CLI 边界。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.application.run_index import (  # noqa: E402
    IdempotencyConflict,
    RevisionConflict,
    RunIndex,
)
from leo_ppt_generator.contracts import ContractError  # noqa: E402


class ConflictReasonCodeTests(unittest.TestCase):
    def test_revision_conflict_forwards_message_as_reason_code(self):
        self.assertEqual(
            RevisionConflict("run_identity_conflict").reason_code,
            "run_identity_conflict")

    def test_revision_conflict_empty_message_falls_back_to_class_default(self):
        self.assertEqual(RevisionConflict("").reason_code, "revision_conflict")

    def test_idempotency_conflict_forwards_message_as_reason_code(self):
        self.assertEqual(
            IdempotencyConflict("cancel_state_conflict").reason_code,
            "cancel_state_conflict")


class SnapshotMissingRunTests(unittest.TestCase):
    def test_snapshot_missing_run_json_raises_contract_error_with_run_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "never-created-run"
            with self.assertRaises(ContractError) as ctx:
                RunIndex(missing).snapshot()
            self.assertIn("run_not_found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
