"""质量口径：缺失不算零，真实身份去重，复合页不等于 TF。"""
import unittest

from leo_ppt_generator.quality_metrics import aggregate_metrics, MetricEventError


def event(identity, kind, **payload):
    return {"schema_version": 1, "event_id": identity, "run_id": "run-1",
            "kind": kind, "window": "production-1", "phase": "after-authorization",
            "source": "runtime", "payload": payload}


class QualityMetricsTests(unittest.TestCase):
    def report(self, events, pages=("1", "2")):
        return aggregate_metrics(events, run_id="run-1", window="production-1",
                                 target_pages=pages)

    def test_no_observation_is_unknown_not_zero(self):
        tf = self.report([])["tf"]
        self.assertEqual((tf["K"], tf["N"], tf["U"]), (0, 0, 2))
        self.assertIsNone(tf["rate"])
        self.assertEqual(tf["status"], "blocked")

    def test_complete_composite_observations_are_not_tf_events(self):
        rows = [event(str(i), "tf", page=str(i), triggers=[], complete=True,
                      generation_method="composite") for i in range(1, 11)]
        tf = self.report(rows, [str(i) for i in range(1, 11)])["tf"]
        self.assertEqual((tf["K"], tf["N"], tf["U"], tf["rate"]), (0, 10, 0, 0))

    def test_trigger_survives_later_success_and_duplicate_events(self):
        first = event("a", "tf", page="1", triggers=["TF-1"], complete=False,
                      generation_method="image")
        later = event("b", "tf", page="1", triggers=[], complete=True,
                      generation_method="image")
        tf = self.report([first, first, later])["tf"]
        self.assertEqual((tf["K"], tf["N"], tf["U"]), (1, 0, 1))
        self.assertEqual(tf["event_count"], 1)
        self.assertEqual(tf["target_interval"], [0.5, 1.0])

    def test_empty_target_is_not_applicable(self):
        self.assertEqual(self.report([], [])["tf"]["status"], "not_applicable")

    def test_conflicting_event_identity_is_rejected(self):
        a = event("a", "tf", page="1", triggers=[], complete=True,
                  generation_method="image")
        b = event("a", "tf", page="1", triggers=["TF-2"], complete=True,
                  generation_method="image")
        with self.assertRaises(MetricEventError):
            self.report([a, b])

    def test_paid_retry_and_duplicate_call_reconcile(self):
        a = event("e1", "call", call_id="c1", pages=["1", "2"], amount="0.03",
                  currency="CNY", price_version="p1", outcome="failed", tokens=100,
                  attempts=3)
        b = event("e2", "call", **a["payload"])
        c = event("e3", "call", call_id="c2", pages=["1"], amount="0.02",
                  currency="CNY", price_version="p1", outcome="succeeded")
        cost = self.report([a, b, c])["cost"]
        self.assertEqual(cost["known_totals"], {"CNY": "0.05"})
        self.assertEqual(cost["calls"], 2)
        self.assertEqual(cost["per_page"]["CNY"], {"1": "0.035", "2": "0.015"})

    def test_cost_buckets_do_not_mix_currencies(self):
        rows = [event(currency, "call", call_id=currency, pages=["1"],
                      amount="1.00", currency=currency, price_version="v1",
                      outcome="succeeded") for currency in ["CNY", "USD"]]
        self.assertEqual(self.report(rows)["cost"]["known_totals"],
                         {"CNY": "1.00", "USD": "1.00"})

    def test_development_cost_is_separate_from_production(self):
        row = event("e", "call", call_id="c", pages=["1"], amount="5",
                    currency="CNY", price_version="v1", outcome="succeeded")
        row["phase"] = "development"
        report = self.report([row])
        self.assertEqual(report["cost"]["known_totals"], {})
        self.assertEqual(report["cost_by_phase"]["development"]["known_totals"], {"CNY": "5"})

    def test_same_call_cannot_be_reclassified_across_authorization_boundary(self):
        a = event("e1", "call", call_id="c", pages=["1"], amount="1",
                  currency="CNY", price_version="v1", outcome="succeeded")
        b = {**a, "event_id": "e2", "phase": "development"}
        with self.assertRaises(MetricEventError):
            self.report([a, b])

    def test_missing_price_or_usage_is_unknown_not_free(self):
        row = event("e", "call", call_id="c", pages=["1"], amount=None,
                    currency="CNY", price_version=None, outcome="failed")
        cost = self.report([row])["cost"]
        self.assertEqual(cost["unknown_calls"], ["c"])
        self.assertEqual(cost["known_totals"], {})
        self.assertEqual(cost["status"], "blocked")

    def test_conflicting_call_identity_is_not_arbitrarily_chosen(self):
        a = event("e1", "call", call_id="c", pages=["1"], amount="1",
                  currency="CNY", price_version="v1", outcome="succeeded")
        b = event("e2", "call", **{**a["payload"], "amount": "2"})
        with self.assertRaises(MetricEventError):
            self.report([a, b])

    def test_rework_counts_feedback_cycles_not_pages_or_internal_retries(self):
        a = event("e1", "rework", feedback_id="f1", pages=["1", "2"],
                  reason="layout", actor="user", state="presented")
        b = event("e2", "rework", feedback_id="f1", pages=["1", "2"],
                  reason="layout", actor="user", state="revised")
        c = event("e3", "rework", feedback_id="qa", pages=["1"],
                  reason="text", actor="automatic", state="presented")
        d = event("e4", "rework", feedback_id="f1", pages=["1", "2"],
                  reason="layout", actor="user", state="received")
        self.assertEqual(self.report([a, b, c, d])["rework"]["completed_rounds"], 1)

    def test_presented_without_feedback_cycle_is_incomplete(self):
        row = event("e", "rework", feedback_id="f", pages=["1"],
                    reason="text", actor="user", state="presented")
        result = self.report([row])["rework"]
        self.assertEqual(result["completed_rounds"], 0)
        self.assertEqual(result["status"], "partial")

    def test_synthetic_observation_cannot_complete_real_window(self):
        row = event("e", "tf", page="1", triggers=[], complete=True,
                    generation_method="render")
        row["source"] = "synthetic"
        result = self.report([row])
        self.assertEqual(result["tf"]["U"], 2)
        self.assertEqual(result["excluded_synthetic_events"], ["e"])

    def test_cost_preserves_large_decimal_and_three_page_remainder(self):
        from decimal import Decimal, localcontext
        amount = "123456789012345678901234567890.01"
        row = event("e", "call", call_id="c", pages=["1", "2", "3"],
                    amount=amount, currency="CNY", price_version="v1", outcome="succeeded")
        result = self.report([row], ["1", "2", "3"])["cost"]
        self.assertEqual(result["known_totals"]["CNY"], amount)
        with localcontext() as ctx:
            ctx.prec = 100
            self.assertEqual(sum(map(Decimal, result["per_page"]["CNY"].values())), Decimal(amount))

    def test_no_feedback_does_not_mean_zero_observed_rework(self):
        r = self.report([])["rework"]
        self.assertIsNone(r["completed_rounds"])
        self.assertEqual(r["status"], "not_yet_observed")

    def test_metrics_registry_has_all_eight_required_fields(self):
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "references" / "metrics-registry.md"
        rows = [line for line in path.read_text().splitlines() if line.startswith("| ")]
        expected = ["metric_id", "formula", "source", "caliber_version", "consumer",
                    "missing_policy", "observation_window", "evidence_level"]
        self.assertEqual([cell.strip() for cell in rows[0].split("|")[1:-1]], expected)
        self.assertEqual(len(rows[2:]), 3)
        for row in rows[2:]:
            fields = [cell.strip() for cell in row.split("|")[1:-1]]
            self.assertEqual(len(fields), 8)
            self.assertTrue(all(fields))

    def test_invalid_amount_and_boolean_completion_rejected(self):
        for amount in ["NaN", "Infinity", "-1", True]:
            with self.subTest(amount=amount), self.assertRaises(MetricEventError):
                self.report([event("e", "call", call_id="c", pages=["1"],
                                   amount=amount, currency="CNY", price_version="v1",
                                   outcome="succeeded")])

    def test_foreign_window_is_excluded_and_target_outside_is_rejected(self):
        row = event("e", "tf", page="3", triggers=[], complete=True,
                    generation_method="image")
        with self.assertRaises(MetricEventError):
            self.report([row])
        row["window"] = "earlier"
        self.assertEqual(self.report([row])["tf"]["U"], 2)


if __name__ == "__main__":
    unittest.main()
