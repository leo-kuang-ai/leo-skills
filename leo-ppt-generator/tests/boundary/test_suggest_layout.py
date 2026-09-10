#!/usr/bin/env python3
"""suggest_layout.py（B2 调度师打分器）边界测试：确定性、强视觉硬排除、
undecided 兜底、禁编造 id、容量硬超排除、输入 schema 错误 exit 2。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "suggest_layout.py"
SKILL_DIR = Path(__file__).resolve().parents[2]


def run(payload: dict, *extra: str) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        return subprocess.run(
            [sys.executable, str(SCRIPT), fh.name, *extra],
            capture_output=True, text=True,
        )


class SuggestLayoutTests(unittest.TestCase):
    def test_same_input_byte_identical_output(self):
        payload = {"pages": [
            {"page": 3, "page_role": "对比·多维", "points": 2, "est_chars": 60},
        ]}
        first = run(payload)
        second = run(payload)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn("candidates", first.stdout)

    def test_excludes_used_non_reuse_friendly_layout(self):
        # P9（reuse_friendly=false）已用 → 结尾页候选中被硬排除。
        payload = {"pages": [
            {"page": 9, "page_role": "结尾", "points": 3, "est_chars": 40,
             "already_used": ["P9"]},
        ]}
        proc = run(payload)
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        ids = [c["layout"] for c in data["pages"][0]["candidates"]]
        self.assertNotIn("P9", ids)
        # reuse_friendly=true 的已用版式仅降权，不排除。

    def test_undecided_when_top_score_below_half(self):
        payload = {"pages": [
            {"page": 5, "page_role": "未知角色", "points": 9, "est_chars": 400},
        ]}
        proc = run(payload)
        self.assertEqual(proc.returncode, 0)  # undecided 是合法结果，不打 1
        data = json.loads(proc.stdout)
        page = data["pages"][0]
        self.assertEqual(page["decision"], "undecided")
        self.assertLess(page["confidence"], 0.5)
        # undecided 页仍按母版合同给候选（top 2）。
        self.assertLessEqual(len(page["candidates"]), 2)

    def test_never_emits_unenumerated_layout_id(self):
        payload = {"pages": [
            {"page": i, "page_role": role, "points": 3, "est_chars": 30}
            for i, role in enumerate(
                ["封面", "拆解·目录", "指标·计分榜", "对比·多维", "结尾",
                 "未知角色X"], start=1,
            )
        ]}
        proc = run(payload)
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        bank_ids = {
            alias
            for p in (SKILL_DIR / "template-library" / "canonical" / "layouts").glob("*/layout.json")
            for alias in (json.loads(p.read_text(encoding="utf-8")).get("aliases") or [])[:1]
        }
        for page in data["pages"]:
            for cand in page["candidates"]:
                self.assertIn(cand["layout"], bank_ids)

    def test_capacity_overflow_excludes_candidate(self):
        tight = {"pages": [
            {"page": 1, "page_role": "指标·计分榜", "points": 4, "est_chars": 30},
        ]}
        overflow = {"pages": [
            {"page": 1, "page_role": "指标·计分榜", "points": 4,
             "est_chars": 3000},
        ]}
        ok_tight = json.loads(run(tight).stdout)["pages"][0]
        ok_over = json.loads(run(overflow).stdout)["pages"][0]
        self.assertTrue(ok_tight["candidates"])
        self.assertEqual(ok_over["candidates"], [])
        self.assertEqual(ok_over["decision"], "undecided")

    def test_cover_hard_overflow_cannot_be_offset_by_role_score(self):
        page = json.loads(run({"pages": [{
            "page": 1, "page_role": "封面", "est_chars": 99999,
        }]}).stdout)["pages"][0]
        self.assertEqual(page["candidates"], [])
        self.assertEqual(page["decision"], "undecided")

    def test_style_routing_adjusts_score(self):
        payload = {"pages": [
            {"page": 2, "page_role": "指标·计分榜", "points": 5, "est_chars": 20},
        ]}
        plain = json.loads(run(payload).stdout)["pages"][0]
        routed = json.loads(
            run(payload, "--style", "数据仪表盘风").stdout
        )["pages"][0]
        routed_reasons = [
            r for c in routed["candidates"] for r in c["reasons"]
            if "风格路由" in r
        ]
        self.assertTrue(routed_reasons, routed)  # preferred +0.1 生效
        self.assertIn("风格路由 +0.1", routed_reasons[0])

    def test_input_schema_error_exits_two(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input='{"not_pages": []}', capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        proc = run({"pages": [{"page": 1}]})  # 缺 page_role
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
