#!/usr/bin/env python3
"""estimate_run_cost.py 单测：历史均值×重试系数 / 无历史保守区间 / 混合 basis /
not-recorded 容错 / 价格换算 / 入参校验 exit 2 / 确定性输出。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "estimate_run_cost.py"


def _run(args, expect_ok=True):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )
    if expect_ok and result.returncode != 0:
        raise AssertionError(f"expected exit 0, got {result.returncode}: {result.stderr}")
    return result


def _stats_file(records):
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "backend_stats.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return tmp, path


HISTORY = [
    {"slide": 2, "page_type": "chart", "attempts": 1, "tokens": 5200},
    {"slide": 4, "page_type": "chart", "attempts": 2, "tokens": 5900},
    {"slide": 5, "page_type": "image", "attempts": 1, "tokens": 3000},
    {"slide": 6, "page_type": "image", "attempts": 1, "tokens": 3000},
]


class NoHistoryTest(unittest.TestCase):
    def test_assumed_band_for_untyped_deck(self):
        out = json.loads(_run(["--pages", 12, "--json"]).stdout)
        self.assertEqual(out["basis"], "assumed-default")
        self.assertEqual(out["tokens_low"], 72000)
        self.assertEqual(out["tokens_high"], 144000)
        self.assertEqual(len(out["lines"]), 1)
        self.assertEqual(out["lines"][0]["page_type"], "default")


class HistoryTest(unittest.TestCase):
    def test_history_band_multiplies_retry_factor(self):
        _, stats = _stats_file(HISTORY)
        out = json.loads(_run(["--pages", 5, "--chart", 2, "--image", 3,
                               "--stats", stats, "--json"]).stdout)
        chart = next(l for l in out["lines"] if l["page_type"] == "chart")
        image = next(l for l in out["lines"] if l["page_type"] == "image")
        # chart: mean(5200,5900)=5550 × mean_attempts(3/2)=1.5 → 8325/页
        self.assertEqual(chart["tokens_low"], 16650)
        self.assertEqual(chart["tokens_high"], 24975)
        self.assertEqual(image["tokens_low"], 9000)
        self.assertEqual(out["tokens_low"], 25650)
        self.assertEqual(out["tokens_high"], 38475)
        self.assertEqual(out["basis"], "history")

    def test_run_dir_resolves_observability_stats(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "observability").mkdir()
        (tmp / "observability" / "backend_stats.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in HISTORY) + "\n",
            encoding="utf-8",
        )
        out = json.loads(_run(["--pages", 5, "--chart", 2, "--image", 3,
                               "--stats", tmp, "--json"]).stdout)
        self.assertEqual(out["basis"], "history")

    def test_partial_history_reports_mixed_basis(self):
        _, stats = _stats_file(HISTORY)
        out = json.loads(_run(["--pages", 8, "--chart", 2, "--image", 3,
                               "--stats", stats, "--json"]).stdout)
        self.assertEqual(out["basis"], "mixed")
        self.assertEqual(sum(l["pages"] for l in out["lines"]), 8)

    def test_not_recorded_tokens_fall_back_to_assumed(self):
        _, stats = _stats_file([
            {"slide": 1, "page_type": "chart", "attempts": 3, "tokens": "not-recorded"},
        ])
        out = json.loads(_run(["--pages", 1, "--chart", 1,
                               "--stats", stats, "--json"]).stdout)
        self.assertEqual(out["basis"], "assumed-default")
        self.assertEqual(out["tokens_low"], 9000)


class PriceTest(unittest.TestCase):
    def test_cost_band_uses_price_per_1k(self):
        out = json.loads(_run(["--pages", 12, "--price-per-1k", "0.03", "--json"]).stdout)
        self.assertEqual(out["cost_low"], 2.16)
        self.assertEqual(out["cost_high"], 4.32)


class ValidationTest(unittest.TestCase):
    def test_zero_pages_exits_2(self):
        self.assertEqual(_run(["--pages", "0"], expect_ok=False).returncode, 2)

    def test_type_counts_exceeding_pages_exit_2(self):
        self.assertEqual(
            _run(["--pages", "2", "--chart", "2", "--image", "1"], expect_ok=False).returncode, 2
        )

    def test_missing_stats_file_exits_2(self):
        result = _run(["--pages", "3", "--stats", "/nonexistent/stats.jsonl"],
                      expect_ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)

    def test_negative_price_exits_2(self):
        self.assertEqual(
            _run(["--pages", "3", "--price-per-1k", "-1"], expect_ok=False).returncode, 2
        )


class DeterminismTest(unittest.TestCase):
    def test_same_input_same_output(self):
        args = ["--pages", 6, "--chart", 2, "--text-heavy", 1, "--price-per-1k", "0.03"]
        first = _run(args + ["--json"]).stdout
        second = _run(args + ["--json"]).stdout
        self.assertEqual(first, second)

    def test_text_output_mentions_band_and_basis(self):
        stdout = _run(["--pages", 3, "--chart", 1]).stdout
        self.assertIn("tokens:", stdout)
        self.assertIn("basis:", stdout)
        self.assertIn("chart", stdout)


if __name__ == "__main__":
    unittest.main()
