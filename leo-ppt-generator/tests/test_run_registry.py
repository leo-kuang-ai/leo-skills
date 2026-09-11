"""写侧登记（cli._register_run_in_home_registry）的单元测试。

覆盖：追加行内容、同 run_id 幂等、坏 registry 行不阻断、OSError 容错
（登记失败绝不阻断 run create）、非法 run_id 拒写。
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

from leo_ppt_generator.cli import _register_run_in_home_registry  # noqa: E402

RUN_ID = "d4c3b2a1f0e1938472560af1b2c3d4e5"


class RunRegistryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = self.home / "ws-demo" / "runs" / ("run-" + RUN_ID[:8])
        self.run_dir.mkdir(parents=True)
        self.snapshot = {
            "run_id": RUN_ID,
            "route": "generate",
            "created_at": "2026-09-07T09:00:00Z",
        }

    def _lines(self):
        path = self.home / "runs-registry.jsonl"
        if not path.is_file():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue  # 坏行保留原样（读侧负责跳过），不计入
        return entries

    def test_appends_registry_entry(self):
        written = _register_run_in_home_registry(
            self.run_dir, self.snapshot, project_root=str(self.home / "ws-demo"), home=self.home
        )
        self.assertTrue(written)
        entries = self._lines()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["run_id"], RUN_ID)
        self.assertEqual(entries[0]["run_dir"], str(self.run_dir.resolve()))
        self.assertEqual(entries[0]["project_root"], str(self.home / "ws-demo"))
        self.assertEqual(entries[0]["route"], "generate")

    def test_same_run_id_is_idempotent(self):
        self.assertTrue(
            _register_run_in_home_registry(self.run_dir, self.snapshot, project_root=None, home=self.home)
        )
        self.assertFalse(
            _register_run_in_home_registry(self.run_dir, self.snapshot, project_root=None, home=self.home)
        )
        self.assertEqual(len(self._lines()), 1)

    def test_bad_existing_lines_do_not_block_append(self):
        registry = self.home / "runs-registry.jsonl"
        registry.write_text("{ broken\n\n", encoding="utf-8")
        self.assertTrue(
            _register_run_in_home_registry(self.run_dir, self.snapshot, project_root=None, home=self.home)
        )
        # 坏行保留原样（读侧负责跳过），新行追加在尾部。
        self.assertEqual(len(self._lines()), 1)

    def test_invalid_run_id_is_rejected(self):
        written = _register_run_in_home_registry(
            self.run_dir, {"run_id": "not-hex", "route": "generate"}, project_root=None, home=self.home
        )
        self.assertFalse(written)
        self.assertEqual(self._lines(), [])

    def test_os_error_is_swallowed_not_raised(self):
        # /dev/null 下不可能创建目录：mkdir 必然 OSError，登记静默降级。
        broken_home = Path("/dev/null/leo-registry-test")
        written = _register_run_in_home_registry(
            self.run_dir, self.snapshot, project_root=None, home=broken_home
        )
        self.assertFalse(written)


if __name__ == "__main__":
    unittest.main()
