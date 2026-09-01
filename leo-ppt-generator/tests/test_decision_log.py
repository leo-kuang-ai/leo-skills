#!/usr/bin/env python3
"""decision_log.py 单元测试（R-44 决策账本）：add 追加+ID 自增+风险必填 /
list 过滤 / cite 引用句 / supersede 留痕不删行 / 幂等 / 不存在 ID exit 1 /
确定性（无时钟）。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "decision_log.py"


def run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8", cwd=cwd)


class DecisionLogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.log = self.root / "content" / "decision-log.md"

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, decision, reason="", risk="密度不足", alt="", *extra):
        return run("--file", str(self.log), "add", decision,
                   "--reason", reason, "--risk", risk, "--alt", alt, *extra)

    def test_add_creates_table_and_increments_ids(self):
        proc = self.add("风格选定清爽专业风", reason="用户偏好轻量叙事",
                        alt="深色科技风")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("recorded D-001", proc.stdout)
        proc = self.add("版式走 P5 台账", reason="证据多", risk="页数膨胀")
        self.assertIn("recorded D-002", proc.stdout)
        text = self.log.read_text(encoding="utf-8")
        self.assertIn("| ID | 决策 | 理由 | 风险 | 替代 | 状态 |", text)
        self.assertIn("| D-001 | 风格选定清爽专业风 |", text)
        self.assertIn("| D-002 |", text)
        self.assertIn("active", text)

    def test_add_requires_risk(self):
        proc = run("--file", str(self.log), "add", "无风险决策", "--reason", "x")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("风险", proc.stderr)
        self.assertFalse(self.log.exists(), "被拒绝的决策不得落盘")

    def test_list_filters_by_status_and_topic(self):
        self.add("风格选定清爽专业风", reason="轻量", risk="r1")
        self.add("版式走 P5 台账", reason="财务场景", risk="r2")
        proc = run("--file", str(self.log), "list", "--topic", "财务")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("P5 台账", proc.stdout)
        self.assertNotIn("清爽专业风", proc.stdout)
        run("--file", str(self.log), "supersede", "D-001")
        proc = run("--file", str(self.log), "list", "--status", "active")
        self.assertNotIn("D-001", proc.stdout)
        self.assertIn("D-002", proc.stdout)

    def test_cite_outputs_one_line_reference(self):
        self.add("风格选定清爽专业风", reason="用户偏好轻量叙事",
                 risk="密集页密度不足", alt="深色科技风")
        proc = run("--file", str(self.log), "cite", "D-001")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("[D-001] 风格选定清爽专业风", proc.stdout)
        self.assertIn("理由：用户偏好轻量叙事", proc.stdout)
        self.assertIn("风险：密集页密度不足", proc.stdout)
        self.assertIn("替代：深色科技风", proc.stdout)
        self.assertIn("引用而非重新论证", proc.stdout)

    def test_cite_unknown_id_exits_one(self):
        self.add("风格选定清爽专业风", reason="r", risk="k")
        proc = run("--file", str(self.log), "cite", "D-099")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("D-099", proc.stderr)

    def test_supersede_keeps_row_and_is_idempotent(self):
        self.add("风格选定清爽专业风", reason="r1", risk="k1")
        self.add("改用科研答辩风", reason="r2", risk="k2")
        proc = run("--file", str(self.log), "supersede", "D-001", "--by", "D-002")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = self.log.read_text(encoding="utf-8")
        self.assertIn("superseded <- D-002", text)
        self.assertIn("风格选定清爽专业风", text, "推翻留痕：旧行不删除")
        again = run("--file", str(self.log), "supersede", "D-001", "--by", "D-002")
        self.assertEqual(again.returncode, 0)
        self.assertIn("幂等", again.stderr)

    def test_supersede_by_must_exist(self):
        self.add("风格选定清爽专业风", reason="r", risk="k")
        proc = run("--file", str(self.log), "supersede", "D-001", "--by", "D-009")
        self.assertEqual(proc.returncode, 1)

    def test_default_location_and_determinism(self):
        project = self.root / "proj"
        (project / "content").mkdir(parents=True)
        # No timestamps invented: same inputs -> byte-identical log.
        run("add", "结构决策：三幕式", "--reason", "x", "--risk", "y",
            cwd=project)
        first = (project / "content" / "decision-log.md").read_bytes()
        (project / "content" / "decision-log.md").unlink()
        run("add", "结构决策：三幕式", "--reason", "x", "--risk", "y",
            cwd=project)
        second = (project / "content" / "decision-log.md").read_bytes()
        self.assertEqual(first, second)
        self.assertNotIn("202", first.decode("utf-8"),
                         "不得自动编造日期（时钟禁用）")

    def test_operator_supplied_date_is_recorded(self):
        proc = self.add("结构决策：三幕式", "", "k", "", "--date", "2026-08-31")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("active（2026-08-31）",
                      self.log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
