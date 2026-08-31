"""E4-T2 image sweep：非 rendered 页复位计划/执行（假 slide_jobs state）。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from leo_ppt_generator.cli import build_parser, dispatch


def _make_run(root: Path, statuses: dict[int, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "run.json").write_text(
        json.dumps({"run_id": "sweep-test", "route": "generate", "status": "in_progress"}),
        encoding="utf-8",
    )
    deck = root / "image-deck"
    (deck / "origin_image").mkdir(parents=True, exist_ok=True)
    slides = []
    for number, status in sorted(statuses.items()):
        slide = {"number": number, "slide_id": f"slide_{number:02d}", "status": status, "notes": ""}
        if status == "recorded":
            artifact = deck / "origin_image" / f"slide_{number:02d}.png"
            artifact.write_bytes(f"png-{number}".encode())
            slide.update({"artifact": f"origin_image/slide_{number:02d}.png", "backend": "render:html"})
        slides.append(slide)
    (deck / "slide_jobs.json").write_text(
        json.dumps({"schema_version": 1, "revision": 1, "slides": slides}), encoding="utf-8"
    )
    stats = root / "observability" / "backend_stats.jsonl"
    stats.parent.mkdir(exist_ok=True)
    stats.write_text(
        json.dumps({"ts": "t", "slide": 2, "backend": "openai", "page_type": "chart",
                    "attempts": 3, "tokens": 5000}) + "\n",
        encoding="utf-8",
    )
    return root


def _sweep(run_root: Path, *extra):
    args = build_parser().parse_args(["image", "sweep", str(run_root), *extra])
    return dispatch(args)


class ImageSweepResetsOnlyUnrenderedPages(unittest.TestCase):
    def test_dry_run_plans_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_run(Path(tmp) / "run", {1: "recorded", 2: "failed", 3: "pending"})
            result = _sweep(root, "--dry-run")
            self.assertEqual(result["reason_code"], "render_sweep_planned")
            plan = result["sweep"]["plan"]
            self.assertEqual({p["slide_id"] for p in plan}, {"slide_02", "slide_03"})
            self.assertEqual(result["sweep"]["rendered_pages_skipped"], 1)
            by_id = {p["slide_id"]: p for p in plan}
            self.assertEqual(by_id["slide_02"]["action"], "reset_and_redispatch")
            self.assertEqual(by_id["slide_02"]["attempts"], 3)
            self.assertEqual(by_id["slide_03"]["action"], "redispatch")
            # dry-run 不改状态
            jobs = json.loads((root / "image-deck" / "slide_jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(jobs["slides"][1]["status"], "failed")

    def test_apply_resets_failed_but_never_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_run(Path(tmp) / "run", {1: "recorded", 2: "failed", 3: "timeout"})
            result = _sweep(root)
            self.assertEqual(result["reason_code"], "render_sweep_applied")
            self.assertEqual(result["sweep"]["round"], 1)
            self.assertIn("slide_02", result["sweep"]["recovery"]["reset_units"])
            self.assertIn("slide_03", result["sweep"]["recovery"]["reset_units"])
            jobs = json.loads((root / "image-deck" / "slide_jobs.json").read_text(encoding="utf-8"))
            statuses = {s["slide_id"]: s["status"] for s in jobs["slides"]}
            # 已 rendered 页无条件跳过；失败/超时页复位 pending
            self.assertEqual(statuses, {"slide_01": "recorded", "slide_02": "pending", "slide_03": "pending"})
            # recorded 页产物与 backend 不被清扫触碰
            recorded = jobs["slides"][0]
            self.assertEqual(recorded["backend"], "render:html")
            self.assertTrue((root / "image-deck" / recorded["artifact"]).is_file())

    def test_rounds_capped_at_max_rounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_run(Path(tmp) / "run", {1: "recorded", 2: "failed"})
            first = _sweep(root)
            self.assertEqual(first["reason_code"], "render_sweep_applied")
            # 再次制造失败页，第二次 apply 后达到上限
            jobs = json.loads((root / "image-deck" / "slide_jobs.json").read_text(encoding="utf-8"))
            jobs["slides"][1]["status"] = "failed"
            (root / "image-deck" / "slide_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
            second = _sweep(root)
            self.assertEqual(second["reason_code"], "render_sweep_applied")
            jobs["slides"][1]["status"] = "failed"
            (root / "image-deck" / "slide_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
            third = _sweep(root)
            self.assertEqual(third["status"], "blocked")
            self.assertEqual(third["reason_code"], "render_sweep_rounds_exhausted")

    def test_all_recorded_deck_has_empty_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_run(Path(tmp) / "run", {1: "recorded", 2: "recorded"})
            result = _sweep(root, "--dry-run")
            self.assertEqual(result["reason_code"], "render_sweep_planned")
            self.assertEqual(result["sweep"]["plan"], [])
            self.assertEqual(result["sweep"]["rendered_pages_skipped"], 2)


if __name__ == "__main__":
    unittest.main()
