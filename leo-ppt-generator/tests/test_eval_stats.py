#!/usr/bin/env python3
"""eval_stats.py unit tests: Wilson CI verdicts, Mann-Whitney U (tie-corrected),
Fisher exact, input format probing (exit 2), determinism.

Expected statistics below were computed independently from the closed-form
formulas and hardcoded as literals (tolerance 1e-6).
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "eval_stats.py"

_spec = importlib.util.spec_from_file_location("eval_stats", SCRIPT)
eval_stats = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_stats)


def _run(args, expect_ok=True):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )
    if expect_ok and result.returncode != 0:
        raise AssertionError(f"expected exit 0, got {result.returncode}: {result.stderr}")
    return result


def _ndjson_file(lines):
    tmp = Path(tempfile.mkdtemp()) / "rounds.ndjson"
    tmp.write_text(
        "\n".join(json.dumps(l, ensure_ascii=False) for l in lines) + "\n",
        encoding="utf-8",
    )
    return tmp


def _skill_up_round(statuses):
    """One skill-up result.json round: statuses maps case_id -> PASS/FAIL/ERROR."""
    return {
        "skill_name": "demo",
        "schema_version": "v1alpha1",
        "case_results": [
            {"case_id": cid, "title": cid, "status": st}
            for cid, st in statuses.items()
        ],
    }


def _skill_up_files(rounds):
    tmp = Path(tempfile.mkdtemp())
    paths = []
    for i, statuses in enumerate(rounds, start=1):
        p = tmp / f"iteration-{i}" / "result.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_skill_up_round(statuses)), encoding="utf-8")
        paths.append(p)
    return paths


class WilsonCiTest(unittest.TestCase):
    def test_nine_of_ten_passes_bounds(self):
        low, high = eval_stats.wilson_ci(9, 10)
        self.assertAlmostEqual(low, 0.5958436145024278, delta=1e-6)
        self.assertAlmostEqual(high, 0.9821242504842788, delta=1e-6)

    def test_zero_samples_returns_none_interval(self):
        self.assertIsNone(eval_stats.wilson_ci(0, 0))

    def test_single_sample_interval_spans_half(self):
        low, high = eval_stats.wilson_ci(1, 1)
        self.assertAlmostEqual(low, 0.2065432914738929, delta=1e-6)
        self.assertAlmostEqual(high, 1.0, delta=1e-6)

    def test_all_fail_interval_clamped_to_zero(self):
        low, high = eval_stats.wilson_ci(0, 10)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, 0.2775401687666166, delta=1e-6)


class VerdictTest(unittest.TestCase):
    def test_stable_pass_when_lower_bound_above_half(self):
        low, high = eval_stats.wilson_ci(9, 10)
        self.assertEqual(
            eval_stats.classify_verdict(low, high, 10, min_samples=3), "stable_pass"
        )

    def test_stable_fail_when_upper_bound_below_half(self):
        low, high = eval_stats.wilson_ci(0, 10)
        self.assertEqual(
            eval_stats.classify_verdict(low, high, 10, min_samples=3), "stable_fail"
        )

    def test_trending_when_interval_spans_half(self):
        # 2/10: high = 0.5098... stays above 0.5 -> trending (PRD AE-10 scenario).
        low, high = eval_stats.wilson_ci(2, 10)
        self.assertEqual(
            eval_stats.classify_verdict(low, high, 10, min_samples=3), "trending"
        )

    def test_trending_when_samples_below_min_samples(self):
        low, high = eval_stats.wilson_ci(2, 2)
        self.assertEqual(
            eval_stats.classify_verdict(low, high, 2, min_samples=3), "trending"
        )


class MannWhitneyTest(unittest.TestCase):
    def test_u_and_p_with_tie_correction(self):
        res = eval_stats.mann_whitney_u([1, 1, 0, 0], [1, 1, 1, 1])
        self.assertEqual(res["u"], 4.0)
        self.assertEqual(res["mu"], 8.0)
        self.assertAlmostEqual(res["sigma2"], 48.0 / 7.0, delta=1e-6)
        self.assertAlmostEqual(res["z"], 1.3365845776954535, delta=1e-6)
        self.assertAlmostEqual(res["p"], 0.18135827590431342, delta=1e-6)
        self.assertFalse(res["significant"])

    def test_u_without_ties_uses_plain_variance(self):
        # All-distinct values: sigma^2 = m*n*(N+1)/12 = 12.
        res = eval_stats.mann_whitney_u([1, 2, 3, 4], [5, 6, 7, 8])
        self.assertEqual(res["u"], 0.0)
        self.assertAlmostEqual(res["sigma2"], 12.0, delta=1e-9)
        self.assertAlmostEqual(res["p"], 0.03038282197657749, delta=1e-6)

    def test_significant_shift_flagged_at_alpha(self):
        res = eval_stats.mann_whitney_u([1, 2, 3, 4], [5, 6, 7, 8], alpha=0.05)
        self.assertTrue(res["significant"])


class FisherExactTest(unittest.TestCase):
    def test_classic_table_two_sided_p(self):
        res = eval_stats.fisher_exact(3, 1, 1, 3)
        self.assertAlmostEqual(res["p"], 34.0 / 70.0, delta=1e-9)

    def test_extreme_table_significant(self):
        res = eval_stats.fisher_exact(8, 0, 0, 8)
        self.assertAlmostEqual(res["p"], 2.0 / 12870.0, delta=1e-12)
        self.assertTrue(res["significant"])

    def test_symmetric_table_not_significant(self):
        res = eval_stats.fisher_exact(4, 4, 4, 4)
        self.assertEqual(res["p"], 1.0)
        self.assertFalse(res["significant"])


class SkillUpFormatTest(unittest.TestCase):
    def test_reads_skill_up_result_json_rounds(self):
        paths = _skill_up_files(
            [
                {"case-a": "PASS", "case-b": "FAIL"},
                {"case-a": "PASS", "case-b": "PASS"},
            ]
        )
        out = json.loads(_run(paths + ["--json"]).stdout)
        self.assertEqual(out["formats"], ["skill-up-result-v1alpha1"])
        self.assertEqual(len(out["rounds"]), 2)
        by_case = {c["case"]: c for c in out["cases"]}
        self.assertEqual(by_case["case-a"]["pass"], 2)
        self.assertEqual(by_case["case-a"]["total"], 2)
        self.assertEqual(by_case["case-a"]["verdict"], "trending")
        self.assertEqual(by_case["case-b"]["pass"], 1)
        # ERROR rounds count toward the denominator but never toward pass.
        paths2 = _skill_up_files(
            [{"case-a": "ERROR"}, {"case-a": "PASS"}, {"case-a": "PASS"}]
        )
        out2 = json.loads(_run(paths2 + ["--json"]).stdout)
        self.assertEqual(out2["cases"][0]["total"], 3)
        self.assertEqual(out2["cases"][0]["pass"], 2)

    def test_rejects_unsupported_schema_version_exits_2(self):
        tmp = Path(tempfile.mkdtemp()) / "result.json"
        tmp.write_text(
            json.dumps({"schema_version": "v9", "case_results": []}), encoding="utf-8"
        )
        result = _run([tmp, "--json"], expect_ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("schema_version", result.stderr)

    def test_rejects_unknown_status_value_exits_2(self):
        tmp = Path(tempfile.mkdtemp()) / "result.json"
        tmp.write_text(
            json.dumps(_skill_up_round({"case-a": "MAYBE"})), encoding="utf-8"
        )
        result = _run([tmp, "--json"], expect_ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MAYBE", result.stderr)


class NdjsonFormatTest(unittest.TestCase):
    def test_reads_ndjson_multi_round_verdicts(self):
        lines = []
        for r in range(1, 11):
            lines.append({"case": "case-a", "status": "PASS" if r <= 9 else "FAIL",
                          "round": r})
        for r in range(1, 11):
            lines.append({"case": "case-b", "status": "PASS" if r <= 2 else "FAIL",
                          "round": r})
        for r in range(1, 3):
            lines.append({"case": "case-c", "status": "PASS", "round": r})
        out = json.loads(_run([_ndjson_file(lines), "--json"]).stdout)
        self.assertEqual(out["formats"], ["ndjson-v1"])
        by_case = {c["case"]: c for c in out["cases"]}
        self.assertEqual([c["case"] for c in out["cases"]],
                         ["case-a", "case-b", "case-c"])
        self.assertEqual(by_case["case-a"]["verdict"], "stable_pass")
        self.assertAlmostEqual(by_case["case-a"]["wilson_low"], 0.5958436145,
                               delta=1e-6)
        self.assertEqual(by_case["case-b"]["verdict"], "trending")
        self.assertEqual(by_case["case-c"]["verdict"], "trending")

    def test_rejects_unknown_format_exits_2(self):
        tmp = Path(tempfile.mkdtemp()) / "input.txt"
        tmp.write_text("neither json nor ndjson\n", encoding="utf-8")
        result = _run([tmp], expect_ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized", result.stderr.lower())

    def test_rejects_ndjson_line_missing_case_exits_2(self):
        tmp = Path(tempfile.mkdtemp()) / "rounds.ndjson"
        tmp.write_text(
            '{"case": "x", "status": "PASS"}\n{"status": "FAIL"}\n',
            encoding="utf-8",
        )
        result = _run([tmp], expect_ok=False)
        self.assertEqual(result.returncode, 2)

    def test_rejects_non_json_object_document_exits_2(self):
        tmp = Path(tempfile.mkdtemp()) / "result.json"
        tmp.write_text(json.dumps([{"case": "x", "status": "PASS"}]),
                       encoding="utf-8")
        self.assertEqual(_run([tmp], expect_ok=False).returncode, 2)


class ReplayCliTest(unittest.TestCase):
    def test_replay_outputs_mann_whitney_and_derived_fisher(self):
        out = json.loads(
            _run(["--replay-before", "1,1,0,0", "--replay-after", "1,1,1,1",
                  "--json"]).stdout
        )
        mw = out["replay"]["mann_whitney"]
        self.assertEqual(mw["u"], 4.0)
        self.assertAlmostEqual(mw["p"], 0.18135827590431342, delta=1e-6)
        self.assertFalse(mw["significant"])
        fisher = out["replay"]["fisher"]
        self.assertEqual(fisher["table"], [[2, 2], [4, 0]])
        self.assertAlmostEqual(fisher["p"], 12.0 / 28.0, delta=1e-9)

    def test_fisher_table_flag_overrides_derivation(self):
        out = json.loads(
            _run(["--replay-before", "1,1,0,0", "--replay-after", "1,1,1,1",
                  "--fisher-table", "3,1,1,3", "--json"]).stdout
        )
        self.assertEqual(out["replay"]["fisher"]["table"], [[3, 1], [1, 3]])
        self.assertAlmostEqual(out["replay"]["fisher"]["p"], 34.0 / 70.0, delta=1e-9)

    def test_fisher_null_for_non_binary_sequences_without_table(self):
        out = json.loads(
            _run(["--replay-before", "1,2,3,4", "--replay-after", "5,6,7,8",
                  "--json"]).stdout
        )
        self.assertIsNone(out["replay"]["fisher"])

    def test_replay_requires_both_sides_exits_2(self):
        result = _run(["--replay-before", "1,0", "--json"], expect_ok=False)
        self.assertEqual(result.returncode, 2)

    def test_replay_rejects_negative_value_exits_2(self):
        result = _run(["--replay-before", "1,-2", "--replay-after", "1,1",
                       "--json"], expect_ok=False)
        self.assertEqual(result.returncode, 2)


class CliContractTest(unittest.TestCase):
    def test_no_input_exits_2(self):
        self.assertEqual(_run(["--json"], expect_ok=False).returncode, 2)

    def test_missing_file_exits_2(self):
        result = _run(["/nonexistent/rounds.ndjson"], expect_ok=False)
        self.assertEqual(result.returncode, 2)

    def test_deterministic_json_stdout_byte_identical(self):
        path = _ndjson_file([{"case": "x", "status": "PASS", "round": 1},
                             {"case": "x", "status": "FAIL", "round": 2}])
        first = _run([path, "--json"]).stdout
        second = _run([path, "--json"]).stdout
        self.assertEqual(first, second)

    def test_deterministic_text_stdout_byte_identical(self):
        path = _ndjson_file([{"case": "x", "status": "PASS", "round": 1},
                             {"case": "y", "status": "FAIL", "round": 1}])
        self.assertEqual(_run([path]).stdout, _run([path]).stdout)

    def test_text_summary_mentions_verdicts_and_interval(self):
        path = _ndjson_file([{"case": "x", "status": "PASS", "round": 1}])
        stdout = _run([path]).stdout
        self.assertIn("trending", stdout)
        self.assertIn("wilson", stdout.lower())
        self.assertIn("min_samples", stdout)


if __name__ == "__main__":
    unittest.main()
