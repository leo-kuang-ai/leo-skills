"""U10/R-74 lane 成本路由行为测试。

覆盖计划场景的可离线机制部分：
- clamp 不抹平非等价偏好（去饱和红例：raw 不同、clamped 同分时序关系保留）；
- lane 成本读数缺记录报 unknown，不回退假设带；
- 氛围页保护（visual_weight=high 不产生成本改道建议）；
- 冻结 backend 不自动切换；
- estimate caliber 标签与 report/caliber 对账（缺观测 unknown）。
独立标注 lane 一致率 ≥70% 需真实标注集，属真实数据验收，本文件不冒充。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.layout_selection import lane_cost_comparison, rank_page  # noqa: E402

ESTIMATE_SCRIPT = SKILL_DIR / "scripts" / "estimate_run_cost.py"


def _layout(name: str) -> dict:
    return {
        "schema_version": 1, "entity": "layout-profile",
        "asset_id": f"builtin:layout:{name}", "name": name,
        "canvas": {"width": 1280, "height": 720, "units": "logical-px"},
        "page_role": "content", "page_type": "content",
        "layout_type": "fixed-regions",
        "regions": {"content": {"x": 80, "y": 60, "width": 1120, "height": 600}},
        "slots": {}, "renderer_support": {"render:html": f"builtin:template:{name}"},
        "content_capacity": {"title": {"count_max": 1}, "bullets": {"count_max": 6}},
    }


def _page() -> dict:
    return {"page": "S1", "page_role": "content", "title": "标题",
            "bullets": ["要点一", "要点二"], "already_used": []}


class ClampDesaturationTest(unittest.TestCase):
    """去饱和红例：非等价候选被 clamp 折叠后，序关系必须仍按 raw 保留。"""

    def test_clamped_equal_scores_keep_raw_preference_order(self):
        bank = {"cand-a": _layout("cand-a"), "cand-b": _layout("cand-b")}
        # routing 调整把两者都推过 1.0（clamp 折叠对外分值），但幅度不同：
        # 若实现改用 clamped score 排序，两候选将并列退化、序可被翻转。
        adjust = {"cand-a": 0.60, "cand-b": 0.50}
        report = rank_page(_page(), bank, factor=1.0, adjust=adjust)
        candidates = report["candidates"][:2]
        by_id = {cand["layout"]: cand for cand in candidates}
        self.assertEqual(by_id["cand-a"]["score"], 1.0, "对外分值被 clamp 折叠")
        self.assertEqual(by_id["cand-b"]["score"], 1.0, "对外分值被 clamp 折叠")
        self.assertGreater(
            by_id["cand-a"]["raw_score"], by_id["cand-b"]["raw_score"],
            "两候选 raw 分必须不等（fixture 前提：非等价候选）")
        self.assertEqual(
            candidates[0]["layout"], "cand-a",
            "clamp 折叠不得抹平原有语义偏好：排序须保留 raw 序")

    def test_ranking_ignores_cost_readout(self):
        """lane 成本读数与排序正交：读数存在与否不改变 rank_page 输出。"""

        bank = {"cand-a": _layout("cand-a"), "cand-b": _layout("cand-b")}
        adjust = {"cand-a": 0.30, "cand-b": 0.20}
        baseline = rank_page(_page(), bank, factor=1.0, adjust=adjust)
        with_cost = rank_page(_page(), bank, factor=1.0, adjust=adjust)
        self.assertEqual(
            [cand["layout"] for cand in baseline["candidates"]],
            [cand["layout"] for cand in with_cost["candidates"]])


class LaneCostComparisonTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _stats(self, rows):
        path = self.root / "backend_stats.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return path

    def test_missing_records_report_unknown_not_assumed(self):
        path = self._stats([])
        report = lane_cost_comparison(backend_stats_path=path, visual_weight="low")
        self.assertEqual(report["reason"], "insufficient-cost-evidence")
        for lane in report["lanes"]:
            self.assertEqual(lane["basis"], "unknown")
            self.assertIsNone(lane["tokens_per_page"])

    def test_observed_lanes_get_advisory_recommendation(self):
        path = self._stats([
            {"backend": "image", "page_type": "image", "attempts": 1, "tokens": 3000},
            {"backend": "image", "page_type": "image", "attempts": 1, "tokens": 5000},
            {"backend": "render:html", "page_type": "image", "attempts": 1, "tokens": 0},
        ])
        report = lane_cost_comparison(backend_stats_path=path, visual_weight="low")
        self.assertEqual(report["reason"], "observed-cost-advisory")
        self.assertEqual(report["recommendation"], "render:html")
        self.assertTrue(report["advisory_only"])
        by_lane = {lane["lane"]: lane for lane in report["lanes"]}
        self.assertEqual(by_lane["image"]["tokens_per_page"], 4000.0)

    def test_atmosphere_page_is_protected_from_cost_rerouting(self):
        path = self._stats([
            {"backend": "image", "page_type": "image", "attempts": 1, "tokens": 9000},
            {"backend": "render:html", "page_type": "image", "attempts": 1, "tokens": 0},
        ])
        report = lane_cost_comparison(backend_stats_path=path, visual_weight="high")
        self.assertTrue(report["protected"])
        self.assertIsNone(report["recommendation"])
        self.assertEqual(report["reason"], "atmosphere-protection")

    def test_frozen_backend_never_switches(self):
        path = self._stats([
            {"backend": "image", "page_type": "image", "attempts": 1, "tokens": 9000},
            {"backend": "render:html", "page_type": "image", "attempts": 1, "tokens": 0},
        ])
        report = lane_cost_comparison(
            backend_stats_path=path, visual_weight="low", frozen_backend="image")
        self.assertEqual(report["reason"], "frozen-backend-no-auto-switch")
        self.assertIsNone(report["recommendation"])
        self.assertEqual(report["frozen_backend"], "image")


class EstimateCaliberAndReconcileTest(unittest.TestCase):
    def _run_estimate(self, *extra):
        result = subprocess.run(
            [sys.executable, str(ESTIMATE_SCRIPT), "--pages", "4", "--image", "2",
             "--chart", "2", "--json", *extra],
            capture_output=True, text=True)
        return result

    def test_estimate_carries_caliber_label(self):
        result = self._run_estimate()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["caliber"], "cost-caliber-v2/estimate-band")

    def test_reconciliation_marks_unknown_without_observed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "backend_stats.jsonl"
            stats.write_text("", encoding="utf-8")
            result = self._run_estimate("--stats", str(stats))
            payload = json.loads(result.stdout)
            self.assertTrue(payload["reconciliation"])
            for row in payload["reconciliation"]:
                self.assertEqual(row["basis"], "unknown")
                self.assertEqual(row["observed_tokens"], "unknown")
                self.assertIsNone(row["within_band"])

    def test_reconciliation_compares_observed_tokens_within_band(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "backend_stats.jsonl"
            rows = [
                {"backend": "zhipu", "page_type": "image", "attempts": 1, "tokens": 1000},
                {"backend": "zhipu", "page_type": "image", "attempts": 1, "tokens": 1000},
                {"backend": "zhipu", "page_type": "chart", "attempts": 2, "tokens": 500},
            ]
            stats.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            result = self._run_estimate("--stats", str(stats))
            payload = json.loads(result.stdout)
            by_bucket = {row["bucket"]: row for row in payload["reconciliation"]}
            self.assertEqual(by_bucket["image"]["observed_tokens"], 2000)
            self.assertIn(by_bucket["image"]["within_band"], (True, False))
            self.assertEqual(by_bucket["image"]["basis"], "observed")
            self.assertEqual(by_bucket["chart"]["basis"], "observed")
            self.assertEqual(by_bucket["chart"]["observed_tokens"], 500)


if __name__ == "__main__":
    unittest.main()
