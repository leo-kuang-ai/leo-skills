"""风格推荐反馈闭环测试（R-64）。

覆盖：record 只存归类标签不存原话（genre 原文不落盘）、--note 拒收（用户
原话/业务数据边界）、record 缺 --candidates 用法错误、brief JSON 不可解析
用法错误、suggest-weights 空库零建议、boost/decay 聚合（简易 bandit 口径）、
确定性双跑一致、家族映射正确（风格名→FAMILIES 反查）、seq 递增、clear
清理入口清空后归零。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import recommend_feedback as rfb  # noqa: E402

SCRIPT_PATH = SCRIPTS_DIR / "recommend_feedback.py"


def run_cli(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True, text=True, env=env,
    )


class RecordBehavior(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Path(self._tmp.name) / "records.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def _record(self, *extra: str) -> subprocess.CompletedProcess:
        return run_cli(
            "record",
            "--brief-json", '{"genre":"融资路演","domain":["AI","大模型"]}',
            "--candidates", "暗黑科技风,麦肯锡咨询风,极简风",
            "--store", str(self.store),
            *extra,
        )

    def test_record_stores_family_labels_not_raw_wording(self):
        result = self._record("--chosen", "暗黑科技风",
                              "--rejected-ids", "麦肯锡咨询风")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        raw = self.store.read_text(encoding="utf-8")
        # Raw contract wording must never hit the disk.
        self.assertNotIn("融资路演", raw)
        self.assertNotIn("大模型", raw)
        rec = json.loads(raw.strip().splitlines()[-1])
        self.assertEqual(rec["schema_version"], 1)
        self.assertEqual(rec["signal_family"]["prefer"],
                         {"商务专业": 1, "科技暗色": 1, "金融审计": 1})
        self.assertIn("科技暗色", rec["chosen"]["families"])
        self.assertEqual(rec["rejected"][0]["style"], "麦肯锡咨询风")
        self.assertIn("商务专业", rec["rejected"][0]["families"])

    def test_record_refuses_note_and_writes_nothing(self):
        # Boundary: user wording may carry business data; never persisted.
        result = self._record("--note", "用户说太严肃了")
        self.assertEqual(result.returncode, 1)
        self.assertIn("note_refused", result.stderr)
        self.assertIn("不落盘", result.stderr)
        self.assertFalse(self.store.exists())

    def test_record_without_candidates_is_usage_error(self):
        result = run_cli(
            "record",
            "--brief-json", '{"genre":"团队周会"}',
            "--candidates", "",
            "--store", str(self.store),
        )
        self.assertEqual(result.returncode, 2)

    def test_record_with_invalid_brief_json_is_usage_error(self):
        result = run_cli(
            "record",
            "--brief-json", "{not json",
            "--candidates", "极简风",
            "--store", str(self.store),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("brief_json_invalid", result.stderr)

    def test_seq_increments_across_records(self):
        self._record("--chosen", "极简风")
        self._record("--chosen", "暗黑科技风")
        lines = self.store.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual([json.loads(x)["seq"] for x in lines], [1, 2])

    def test_named_style_bypass_records_empty_family_verdict(self):
        result = run_cli(
            "record",
            "--brief-json", '{"genre":"论文答辩","named_style":"蒸汽波风"}',
            "--candidates", "蒸汽波风",
            "--chosen", "蒸汽波风",
            "--store", str(self.store),
        )
        self.assertEqual(result.returncode, 0)
        rec = json.loads(self.store.read_text(encoding="utf-8").strip())
        self.assertEqual(rec["signal_family"]["triggered_rules"], [])
        self.assertIn("复古潮流", rec["chosen"]["families"])


class SuggestWeightsBehavior(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Path(self._tmp.name) / "records.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def _seed(self, n: int) -> None:
        for _ in range(n):
            run_cli(
                "record",
                "--brief-json", '{"genre":"融资路演","domain":["AI"]}',
                "--candidates", "暗黑科技风,麦肯锡咨询风,极简风",
                "--chosen", "暗黑科技风",
                "--rejected-ids", "麦肯锡咨询风",
                "--store", str(self.store),
            )

    def test_empty_store_yields_zero_suggestions(self):
        result = run_cli("suggest-weights", "--store", str(self.store))
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout)
        self.assertEqual(out["records"], 0)
        self.assertEqual(out["suggestions"]["boost"], [])

    def test_bandit_tally_emits_boost_and_decay(self):
        self._seed(2)
        out = json.loads(run_cli("suggest-weights",
                                 "--store", str(self.store)).stdout)
        self.assertEqual(out["records"], 2)
        # Chosen twice -> net +2 reaches the boost threshold.
        self.assertIn("科技暗色", out["suggestions"]["boost"])
        # Rejected twice -> net -2 reaches the decay threshold.
        self.assertIn("商务专业", out["suggestions"]["decay"])
        self.assertEqual(out["families"]["科技暗色"]["net"], 2)
        self.assertEqual(out["families"]["商务专业"]["net"], -2)

    def test_below_threshold_lands_in_hold(self):
        self._seed(1)
        out = json.loads(run_cli("suggest-weights",
                                 "--store", str(self.store)).stdout)
        self.assertIn("科技暗色", out["suggestions"]["hold"])
        self.assertNotIn("科技暗色", out["suggestions"]["boost"])

    def test_output_is_deterministic(self):
        self._seed(3)
        first = run_cli("suggest-weights", "--store", str(self.store)).stdout
        second = run_cli("suggest-weights", "--store", str(self.store)).stdout
        self.assertEqual(first, second)

    def test_clear_empties_store_and_resets_tally(self):
        self._seed(2)
        result = run_cli("clear", "--store", str(self.store))
        self.assertEqual(result.returncode, 0)
        self.assertIn("cleared: 删除 2 条", result.stdout)
        self.assertFalse(self.store.exists())
        out = json.loads(run_cli("suggest-weights",
                                 "--store", str(self.store)).stdout)
        self.assertEqual(out["records"], 0)

    def test_clear_on_missing_store_is_idempotent(self):
        result = run_cli("clear", "--store", str(self.store))
        self.assertEqual(result.returncode, 0)
        self.assertIn("已是空库", result.stdout)


class FamilyMapping(unittest.TestCase):
    def test_families_of_reverse_lookup(self):
        self.assertIn("商务专业", rfb._families_of("麦肯锡咨询风"))
        self.assertIn("数据图表", rfb._families_of("麦肯锡咨询风"))
        self.assertIn("科技暗色", rfb._families_of("暗黑科技风"))
        self.assertEqual(rfb._families_of("完全不存在的风格"), [])

    def test_parse_names_accepts_json_and_csv(self):
        self.assertEqual(rfb._parse_names('["极简风","瑞士网格风"]'),
                         ["极简风", "瑞士网格风"])
        self.assertEqual(rfb._parse_names("极简风, 瑞士网格风"),
                         ["极简风", "瑞士网格风"])
        self.assertEqual(rfb._parse_names(""), [])


if __name__ == "__main__":
    unittest.main()
