#!/usr/bin/env python3
"""check_deck_geometry.py --capacity 模式（B3）边界测试：vw 权重、互斥用法、
硬超 exit 1 带替代候选、软超降档建议（否定感知：绝不建议缩字号）、
无旗标时既有几何行为逐项不变。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
GEOMETRY = SCRIPTS / "check_deck_geometry.py"

sys.path.insert(0, str(SCRIPTS))
from check_deck_geometry import leo_capacity_for, vw_of  # noqa: E402


def run_capacity(spec: dict) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(spec, fh, ensure_ascii=False)
        fh.flush()
        return subprocess.run(
            [sys.executable, str(GEOMETRY), "--capacity", fh.name],
            capture_output=True, text=True,
        )


class VwOfTests(unittest.TestCase):
    def test_vw_of_cjk_ascii_space_weights(self):
        self.assertEqual(vw_of("中"), 1.0)
        self.assertEqual(vw_of("，"), 1.0)  # 全角标点（U+3000-303F）
        self.assertEqual(vw_of("Ａ"), 1.0)  # 全角拉丁（U+FF00-FFEF）
        self.assertEqual(vw_of("A"), 0.5)
        self.assertEqual(vw_of("1"), 0.5)
        self.assertEqual(vw_of(" "), 0.35)
        self.assertEqual(vw_of("×"), 0.8)  # 其他（非 ASCII 非 CJK）
        self.assertAlmostEqual(vw_of("中文 abc"), 2.0 + 1.5 + 0.35)

    def test_leo_capacity_for_formula(self):
        # 版心 token 公式：cols=12 → 88vw×25.6×0.95 = 2142.72px。
        cpl, lines, mx = leo_capacity_for(12, 19, 297)
        self.assertEqual((cpl, lines, mx), (7, 1, 8))
        # 恒等式 max_chars == floor(cpl × lines × 1.2)。
        for cols, h, f in ((4, 6, 28), (8, 40, 102), (5, 30, 48)):
            c, l, m = leo_capacity_for(cols, h, f)
            self.assertEqual(m, int(c * l * 1.2))


class CapacityModeTests(unittest.TestCase):
    def test_fixed_cover_cannot_repeat_short_points_without_total_limit(self):
        for points in (["长"] * 10000, ["长" * 10000]):
            proc = run_capacity({"slides": [{"page": 1, "layout": "P1", "points": points}]})
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("overflow:total_text", proc.stdout)
        proc = run_capacity({"slides": [{"page": 1, "layout": "P1", "points": ["标题", "副标题"]}]})
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_capacity_mode_rejects_pptx_and_capacity_together(self):
        proc = subprocess.run(
            [sys.executable, str(GEOMETRY), "foo.pptx", "--capacity",
             "bar.json"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("互斥", proc.stderr)

    def test_ok_when_within_capacity(self):
        proc = run_capacity({"slides": [
            {"page": 1, "layout": "P6", "slots": {
                "item_label": "月活跃用户",
                "big_number": "1.2亿",
            }},
        ]})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[OK]", proc.stdout)

    def test_soft_over_suggests_downgrade_never_smaller_font(self):
        # P6 item_label max_chars=45；软超带 = (45, 54]，48 个 CJK 字 = 48 vw。
        proc = run_capacity({"slides": [
            {"page": 2, "layout": "P6", "slots": {"item_label": "标" * 48}},
        ]})
        self.assertEqual(proc.returncode, 0)  # 软超不占退出码
        self.assertIn("[WARN]", proc.stdout)
        self.assertIn("降档", proc.stdout)
        self.assertIn("不缩字号", proc.stdout)  # 健康建议：明示不缩字号
        # 否定感知：不得出现肯定式的缩小字号/省略号话术
        # （"不缩字号" 是否定形态，属健康输出）。
        for phrase in ("缩小字号", "减小字号", "降低字号", "省略号截断"):
            self.assertNotIn(phrase, proc.stdout)

    def test_hard_overflow_exits_one_with_alternatives(self):
        proc = run_capacity({"slides": [
            {"page": 3, "layout": "P19", "slots": {
                "card_desc": "长" * 120,
            }},
        ]})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[FAIL]", proc.stdout)
        self.assertIn("overflow:card_desc", proc.stdout)
        self.assertIn("换版式候选", proc.stdout)
        self.assertIn("不缩字号", proc.stdout)

    def test_count_range_violation_suggests_alternative_layouts(self):
        # P5 cards 数量 = 3；给 6 条要点 → 数量硬超建议换版式（X-3 联动）。
        proc = run_capacity({"slides": [
            {"page": 4, "layout": "P5", "points": [
                "要点一", "要点二", "要点三", "要点四",
                "要点五", "要点六",
            ]},
        ]})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("count:cards", proc.stdout)
        self.assertIn("降档删要点至 ≤3", proc.stdout)

    def test_style_capacity_factor_applied(self):
        # 手绘白板风 factor 0.85：44 vw 在 1.0 下过（≤45）、0.85 下软超
        # （>38.25 且 ≤45.9）→ WARN。
        spec = {"style": "手绘白板风", "slides": [
            {"page": 1, "layout": "P6", "slots": {"item_label": "字" * 44}},
        ]}
        neutral = run_capacity({"slides": [
            {"page": 1, "layout": "P6", "slots": {"item_label": "字" * 44}},
        ]})
        self.assertIn("[OK]", neutral.stdout)
        with_factor = run_capacity(spec)
        self.assertEqual(with_factor.returncode, 0)
        self.assertIn("[WARN]", with_factor.stdout)

    def test_committed_over_spec_fixture_flows(self):
        # 仓库 fixture（tests/fixtures/capacity/over-spec.json）：P5 六条要点
        # 硬超 → exit 1 且建议为降档/换版式（X-3 断言链）。
        fixture = (Path(__file__).resolve().parents[1]
                   / "fixtures" / "capacity" / "over-spec.json")
        proc = subprocess.run(
            [sys.executable, str(GEOMETRY), "--capacity", str(fixture)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("降档删要点至 ≤3", proc.stdout)
        self.assertIn("换版式候选", proc.stdout)
        self.assertIn("[OK] 第 1 页 P1", proc.stdout.splitlines()[0])

    def test_unknown_layout_or_slot_exits_two(self):
        proc = run_capacity({"slides": [{"page": 1, "layout": "P99"}]})
        self.assertEqual(proc.returncode, 2)
        proc = run_capacity({"slides": [
            {"page": 1, "layout": "P6", "slots": {"no_such_slot": "x"}},
        ]})
        self.assertEqual(proc.returncode, 2)


class ExistingGeometryModeTests(unittest.TestCase):
    def test_existing_geometry_mode_unchanged(self):
        # 无 --capacity 时既有用法/退出码逐项不变：无参数仍为用法错误 2。
        proc = subprocess.run(
            [sys.executable, str(GEOMETRY)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        # --self-test 仍三例全过。
        proc = subprocess.run(
            [sys.executable, str(GEOMETRY), "--self-test"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("[PASS]", proc.stdout)
        # 缺文件仍 exit 2 且报错路径。
        proc = subprocess.run(
            [sys.executable, str(GEOMETRY), "definitely-missing.pptx"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("definitely-missing.pptx", proc.stdout)


if __name__ == "__main__":
    unittest.main()
