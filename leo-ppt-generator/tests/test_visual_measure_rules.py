#!/usr/bin/env python3
"""validate_visual_measure.py 单元测试：测量式视觉质检规则子集。

覆盖（无需 playwright，纯标准库）：
- 每条规则（R1 溢出 / R4 最小字号 / R5 4 横带密度 / R8 视觉边界 / R9 标题间距）
  至少 1 个命中 + 1 个通过用例（合成几何 JSON）；
- R1 修正阶梯四档分档断言（30px→微调 / 200px→换版式 等）；
- 空白横带 whitespace_reason 豁免；
- R5 仅 3:4 画板生效；
- CLI 三态：--measurements exit 0/1、--html 无 playwright 降级 exit 3、
  无参打印用法。阈值真值见 references/social-card-specs.md。
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_visual_measure.py"

_spec = importlib.util.spec_from_file_location("validate_visual_measure", SCRIPT)
vvm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vvm)


def blk(bid, role, y_top, y_bottom, x_left=72, x_right=1008, font=None, **kw):
    d = {
        "id": bid,
        "role": role,
        "y_top": y_top,
        "y_bottom": y_bottom,
        "x_left": x_left,
        "x_right": x_right,
        "text": bid,
    }
    if font is not None:
        d["font_size"] = font
    d.update(kw)
    return d


def doc(blocks, page_id="xhs-01", width=1080, height=1440, board=None, reasons=None):
    canvas = {"width": width, "height": height}
    if board:
        canvas["board"] = board
    page = {"id": page_id, "blocks": blocks}
    if reasons is not None:
        page["whitespace_reasons"] = reasons
    return {"canvas": canvas, "pages": [page]}


def codes_of(data):
    return [v["code"] for v in vvm.run_rules(vvm.normalize_document(data))]


# 合规 fixture：覆盖 76%、安全区/字号/标题间距全部达标、无空白横带。
PASS_BLOCKS = [
    blk("meta-1", "meta", 88, 124, font=20),
    blk("title-1", "title", 190, 340, font=88),
    blk("lead-1", "lead", 380, 470, font=30),
    blk("body-1", "body", 510, 950, 72, 640, font=28),
    blk("image-1", "image", 510, 1250, 680, 1008),
    blk("strip-1", "meta", 1280, 1360, font=20),
]


def run_cli(argv):
    return subprocess.run([sys.executable, str(SCRIPT), *argv],
                          capture_output=True, text=True)


def write_json(payload):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                    encoding="utf-8")
    json.dump(payload, f, ensure_ascii=False)
    f.close()
    return f.name


class RuleSubsetTest(unittest.TestCase):
    def test_clean_page_has_no_violations(self):
        self.assertEqual(codes_of(doc(PASS_BLOCKS)), [])

    # ---- R1 溢出 ----
    def test_r1_overflow_below_canvas_hits_error_with_tweak_ladder(self):
        blocks = PASS_BLOCKS + [blk("foot-note", "body", 1400, 1470, 72, 400, font=28)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        r1 = [v for v in violations if v["code"] == "R1.overflow"]
        self.assertEqual(len(r1), 1)
        self.assertEqual(r1[0]["severity"], "error")
        self.assertIn("底边超出画布 30px", r1[0]["measured"])
        self.assertIn("微调档", r1[0]["fix"])

    def test_r1_passes_when_inside_canvas(self):
        self.assertNotIn("R1.overflow", codes_of(doc(PASS_BLOCKS)))

    def test_overflow_ladder_four_tiers(self):
        self.assertIn("微调档", vvm.overflow_fix_ladder(30))
        self.assertIn("不删内容", vvm.overflow_fix_ladder(40))
        self.assertIn("压缩档", vvm.overflow_fix_ladder(60))
        self.assertIn("删减档", vvm.overflow_fix_ladder(120))
        self.assertIn("换版式档", vvm.overflow_fix_ladder(200))
        self.assertIn("合并/删除内容模块", vvm.overflow_fix_ladder(999))

    # ---- R4 最小字号 ----
    def test_r4_caption_below_floor_hits_warn(self):
        blocks = PASS_BLOCKS + [blk("cap-1", "caption", 470, 500, 72, 640, font=16)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        r4 = [v for v in violations if v["code"] == "R4.min_font"]
        self.assertEqual(len(r4), 1)
        self.assertEqual(r4[0]["severity"], "warn")
        self.assertIn("16px", r4[0]["measured"])
        self.assertIn("≥18px", r4[0]["threshold"])

    def test_r4_passes_at_machine_floors(self):
        blocks = [
            blk("body-1", "body", 100, 400, font=22),
            blk("lead-1", "lead", 440, 700, font=26),
            blk("cap-1", "caption", 740, 900, font=18),
            blk("meta-1", "meta", 940, 1200, font=18),
            blk("cell-1", "cell_title", 1240, 1300, font=20),
        ]
        self.assertNotIn("R4.min_font", codes_of(doc(blocks, width=1080, height=1440)))

    # ---- R5 4 横带密度（仅 3:4） ----
    def test_r5_empty_band_without_reason_hits(self):
        blocks = [blk("title-1", "title", 96, 300, font=88),
                  blk("image-1", "image", 600, 1400)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        empty = [v for v in violations if v["code"] == "R5.empty_band"]
        self.assertEqual(len(empty), 1)
        self.assertIn("空白横带 300px", empty[0]["measured"])
        self.assertIn("whitespace_reason", empty[0]["threshold"])

    def test_r5_empty_band_exempted_with_whitespace_reason(self):
        blocks = [blk("title-1", "title", 96, 300, font=88),
                  blk("image-1", "image", 600, 1400)]
        reasons = [{"y_top": 300, "y_bottom": 600, "reason": "hero breathing"}]
        codes = codes_of(doc(blocks, reasons=reasons))
        self.assertNotIn("R5.empty_band", codes)

    def test_r5_adjacent_sparse_bands_hit_mid_poster_void(self):
        blocks = [blk("title-1", "title", 96, 300, font=88),
                  blk("strip-1", "meta", 1300, 1360, font=20)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        adjacent = [v for v in violations if v["code"] == "R5.adjacent"]
        self.assertEqual(len(adjacent), 1)
        self.assertIn("均稀", adjacent[0]["measured"])

    def test_r5_total_coverage_below_75pct_hits(self):
        blocks = [blk("title-1", "title", 96, 300, font=88),
                  blk("strip-1", "meta", 1300, 1360, font=20)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        total = [v for v in violations if v["code"] == "R5.total"]
        self.assertEqual(len(total), 1)
        self.assertIn("≥75%", total[0]["threshold"])

    def test_r5_not_applied_on_square_board(self):
        blocks = [blk("title-1", "title", 96, 300, font=88),
                  blk("strip-1", "meta", 1300, 1360, font=20)]
        codes = codes_of(doc(blocks, width=1080, height=1080, board="square"))
        self.assertFalse([c for c in codes if c.startswith("R5")])

    # ---- R8 视觉边界 ----
    def test_r8_content_too_close_to_edge_hits(self):
        blocks = [blk("body-1", "body", 100, 1300, 40, 1040, font=28)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        edge = [v for v in violations if v["code"] == "R8.edge"]
        self.assertTrue(edge)
        self.assertIn("距左", edge[0]["measured"])
        self.assertIn("≥72px", edge[0]["threshold"])

    def test_r8_bottom_whitespace_with_low_active_ratio_hits(self):
        blocks = [blk("title-1", "title", 96, 400, font=88),
                  blk("body-1", "body", 450, 1000, font=28)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        gap = [v for v in violations if v["code"] == "R8.bottom_gap"]
        self.assertEqual(len(gap), 1)
        self.assertIn("底部留白 440px", gap[0]["measured"])

    def test_r8_passes_inside_safe_area(self):
        self.assertNotIn("R8.edge", codes_of(doc(PASS_BLOCKS)))
        self.assertNotIn("R8.bottom_gap", codes_of(doc(PASS_BLOCKS)))

    # ---- R9 标题间距 ----
    def test_r9_title_touching_next_block_hits(self):
        blocks = [blk("title-1", "title", 190, 340, font=88),
                  blk("lead-1", "lead", 350, 470, font=30),
                  blk("body-1", "body", 510, 1360, font=28)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        r9 = [v for v in violations if v["code"] == "R9.title_gap"]
        self.assertEqual(len(r9), 1)
        self.assertIn("10px", r9[0]["measured"])
        self.assertIn("≥28px", r9[0]["threshold"])

    def test_r9_wide_board_uses_24px_floor(self):
        blocks = [blk("title-1", "title", 100, 220, 72, 2028, font=104),
                  blk("body-1", "body", 240, 820, 160, 1940, font=28)]
        violations = vvm.run_rules(vvm.normalize_document(
            doc(blocks, width=2100, height=900, board="wide")))
        r9 = [v for v in violations if v["code"] == "R9.title_gap"]
        self.assertEqual(len(r9), 1)
        self.assertIn("≥24px", r9[0]["threshold"])

    def test_r9_local_title_uses_16px_floor(self):
        blocks = [blk("local-1", "local_title", 190, 280, font=42),
                  blk("body-1", "body", 295, 1360, font=28)]
        violations = vvm.run_rules(vvm.normalize_document(doc(blocks)))
        r9 = [v for v in violations if v["code"] == "R9.title_gap"]
        self.assertEqual(len(r9), 1)
        self.assertIn("≥16px", r9[0]["threshold"])

    def test_r9_passes_with_40px_gap(self):
        self.assertNotIn("R9.title_gap", codes_of(doc(PASS_BLOCKS)))


class BoardDetectionTest(unittest.TestCase):
    def test_detects_boards_by_ratio_and_alias(self):
        self.assertEqual(vvm.detect_board(1080, 1440), "xhs")
        self.assertEqual(vvm.detect_board(1080, 1080), "square")
        self.assertEqual(vvm.detect_board(2100, 900), "wide")
        self.assertEqual(vvm.detect_board(1000, 500), "unknown")
        self.assertEqual(vvm.detect_board(999, 999, "3:4"), "xhs")
        self.assertEqual(vvm.detect_board(1000, 1000, "21:9"), "wide")


class CliContractTest(unittest.TestCase):
    def test_measurements_clean_doc_exits_zero(self):
        r = run_cli(["--measurements", write_json(doc(PASS_BLOCKS))])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[PASS] xhs-01", r.stdout)
        self.assertIn("统计:", r.stdout)

    def test_measurements_overflow_doc_exits_one(self):
        blocks = PASS_BLOCKS + [blk("foot-note", "body", 1400, 1640, 72, 400, font=28)]
        r = run_cli(["--measurements", write_json(doc(blocks))])
        self.assertEqual(r.returncode, 1)
        self.assertIn("R1 | error", r.stdout)
        self.assertIn("[FAIL]", r.stdout)
        self.assertIn("换版式档", r.stdout)  # 200px 溢出走换版式档

    def test_measurements_warn_only_exits_zero(self):
        blocks = [blk("cap-1", "caption", 100, 1300, font=16)]
        r = run_cli(["--measurements", write_json(doc(blocks))])
        self.assertEqual(r.returncode, 0)
        self.assertIn("R4 | warn", r.stdout)

    def test_html_without_playwright_degrades_exit_3(self):
        r = run_cli(["--html", "whatever.html"])
        self.assertEqual(r.returncode, 3)
        self.assertIn("pip install playwright", r.stdout)
        self.assertIn("playwright install chromium", r.stdout)
        self.assertIn("--measurements", r.stdout)
        self.assertNotIn("Traceback", r.stdout + r.stderr)

    def test_no_args_prints_usage_and_degrade_note(self):
        r = run_cli([])
        self.assertEqual(r.returncode, 2)
        self.assertIn("用法", r.stdout)
        self.assertIn("--measurements", r.stdout)
        self.assertNotIn("Traceback", r.stdout + r.stderr)

    def test_missing_measurements_file_exits_two(self):
        r = run_cli(["--measurements", "/nonexistent/deck.json"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("不存在", r.stderr)

    def test_mutually_exclusive_modes_exit_two(self):
        path = write_json(doc(PASS_BLOCKS))
        r = run_cli(["--measurements", path, "--html", "index.html"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("互斥", r.stderr)

    def test_schema_missing_field_exits_two_without_traceback(self):
        # 合法 JSON 但内容块缺 y_top：归一化失败按输入错误清晰退出，不抛 traceback
        path = write_json({
            "canvas": {"width": 1080, "height": 1440},
            "pages": [{"id": "xhs-01", "blocks": [{"id": "b1", "role": "body"}]}],
        })
        r = run_cli(["--measurements", path])
        self.assertEqual(r.returncode, 2)
        self.assertIn("缺少 y_top", r.stderr)
        self.assertNotIn("Traceback", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
