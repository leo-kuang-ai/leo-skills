#!/usr/bin/env python3
"""聚焦回归（加固方案 WS2）：deck 尺寸预算确定性校验。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "check_size_budget.py"


def _make_run(root: Path, pages: list[tuple[str, str, tuple[int, int]]]) -> Path:
    run = root / "proj" / "runs" / "run-001"
    origin = run / "image-deck" / "origin_image"
    origin.mkdir(parents=True, exist_ok=True)
    slides = []
    for i, (backend, _note, size) in enumerate(pages, 1):
        png = origin / f"slide_{i:02d}.png"
        Image.new("RGB", size, "#ffffff").save(png)
        slides.append({
            "number": i, "slide_id": f"slide_{i:02d}", "status": "recorded",
            "artifact": f"image-deck/origin_image/slide_{i:02d}.png",
            "backend": backend,
        })
    (run / "image-deck" / "slide_jobs.json").write_text(
        json.dumps({"slides": slides}), encoding="utf-8")
    return run


def _check(run: Path, budget: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), str(run)]
    if budget is not None:
        p = run.parent.parent / "content" / "size-budget.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(budget), encoding="utf-8")
        cmd += ["--budget", str(p)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


class SizeBudgetTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-ws2-")
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_consistent_mixed_lanes_pass_with_disclosure_warn(self):
        run = _make_run(self.root, [
            ("ark", "image", (2560, 1440)),
            ("render:html", "chart", (2560, 1440)),
            ("zhipu", "image", (1792, 1008)),  # 渠道档受限 → WARN 不是 FAIL
        ])
        result = _check(run, {"canvas_ratio": "16 / 9", "image_lane_px": "2560x1440"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("image_below_budget", result.stdout)

    def test_ratio_and_ladder_violations_fail(self):
        run = _make_run(self.root, [
            ("ark", "image", (2000, 1440)),        # 非 16:9
            ("render:html", "text", (1792, 1008)), # 渲染档非整数 dsf
        ])
        result = _check(run)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ratio_mismatch", result.stdout)
        self.assertIn("render_size_off_ladder", result.stdout)

    def test_image_exceeding_budget_fails(self):
        run = _make_run(self.root, [("ark", "image", (2560, 1440))])
        result = _check(run, {"canvas_ratio": "16 / 9", "image_lane_px": "1792x1008"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("image_exceeds_budget", result.stdout)


if __name__ == "__main__":
    unittest.main()
