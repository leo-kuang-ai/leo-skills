"""runs_console（生成任务只读数据层）的单元测试。

覆盖方案 U1：发现与容错、页状态推断（timing pages）、事件尾窗与坏行计数、
交付卡（六门/失败回落）、backend_stats 聚合容错、页图沙箱拒绝矩阵。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from runs_fixture import make_run  # noqa: E402
from leo_ppt_generator.application.routes import ROUTES  # noqa: E402
from leo_ppt_generator.runs_console import (  # noqa: E402
    PreviewLookupError,
    ROUTE_STEP_SEQUENCES,
    RunLookupError,
    RunScanner,
)

RUN_A = "a3f2c1d4e5b64708901234567890abcd"
RUN_B = "b7c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5"


class RunScannerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.scanner = RunScanner(self.home)

    # ------------------------------------------------------------- 列表
    def test_list_runs_discovers_and_sorts_by_recency(self):
        make_run(self.home, project="p1", run_id=RUN_A)
        make_run(self.home, project="p2", run_id=RUN_B, route="upgrade-full", status="completed", final=True)
        data = self.scanner.list_runs()
        self.assertEqual(len(data["runs"]), 2)
        self.assertFalse(data["home_missing"])
        by_id = {item["run_id"]: item for item in data["runs"]}
        self.assertEqual(by_id[RUN_A]["project"], "p1")
        self.assertEqual(by_id[RUN_A]["progress"]["total_units"], 12)
        self.assertEqual(by_id[RUN_A]["progress"]["completed"], 7)
        self.assertEqual(by_id[RUN_B]["route"], "upgrade-full")

    def test_home_missing_is_flagged_not_raised(self):
        data = self.scanner.list_runs()
        self.assertTrue(data["home_missing"])
        self.assertEqual(data["runs"], [])

    # ------------------------------------------------- registry（workspace run）
    def _register(self, run_dir, run_id, *, project_root=None, home=None):
        import json as _json

        target = (home or self.home) / "runs-registry.jsonl"
        entry = {
            "schema_version": 1,
            "run_id": run_id,
            "route": "generate",
            "project_root": project_root,
            "run_dir": str(run_dir),
            "created_at": "2026-09-07T09:00:00Z",
        }
        with target.open("a", encoding="utf-8") as handle:
            handle.write(_json.dumps(entry, ensure_ascii=False) + "\n")

    def test_registry_makes_workspace_run_visible(self):
        ws = self.home / "ws-fixture"
        run_dir = make_run(self.home, run_id=RUN_B, workspace_root=ws, total=3, recorded=3, failed_pages=())
        self._register(run_dir, RUN_B, project_root=str(ws))
        data = self.scanner.list_runs()
        by_id = {item["run_id"]: item for item in data["runs"]}
        self.assertIn(RUN_B, by_id)
        self.assertEqual(by_id[RUN_B]["project"], "ws-fixture")
        detail = self.scanner.run_detail(RUN_B)
        self.assertEqual(len(detail["pages"]), 3)

    def test_registry_bad_lines_and_stale_dirs_degrade(self):
        ws = self.home / "ws-bad"
        run_dir = make_run(self.home, run_id=RUN_B, workspace_root=ws, total=2, recorded=2, failed_pages=())
        registry = self.home / "runs-registry.jsonl"
        registry.write_text(
            "{ broken-json\n"
            + "\n"
            + '{"schema_version":1,"run_id":"deadbeef","run_dir":"/nonexistent/run"}\n'
            + '{"schema_version":1,"run_id":"' + RUN_B + '","run_dir":"' + str(run_dir) + '"}\n',
            encoding="utf-8",
        )
        data = self.scanner.list_runs()
        self.assertEqual([item["run_id"] for item in data["runs"]], [RUN_B])
        # run_dir 存在但 run.json 的 run_id 对不上：零信任跳过。
        mismatch_dir = make_run(self.home, run_id=RUN_A, workspace_root=self.home / "ws-mis")
        with registry.open("a", encoding="utf-8") as handle:
            handle.write('{"schema_version":1,"run_id":"ffffffff","run_dir":"' + str(mismatch_dir) + '"}\n')
        self.scanner.invalidate_cache()
        data = self.scanner.list_runs()
        self.assertNotIn("ffffffff", {item["run_id"] for item in data["runs"]})

    def test_registry_duplicate_with_home_layout_prefers_home(self):
        make_run(self.home, run_id=RUN_A)
        ws = self.home / "ws-dup"
        dup_dir = make_run(self.home, run_id=RUN_A, workspace_root=ws, project="dup-proj")
        self._register(dup_dir, RUN_A)
        data = self.scanner.list_runs()
        by_id = {item["run_id"]: item for item in data["runs"]}
        self.assertEqual(by_id[RUN_A]["project"], "demo-proj")

    def test_corrupt_run_json_is_skipped_without_breaking_list(self):
        make_run(self.home, run_id=RUN_A)
        make_run(self.home, project="bad", run_id=RUN_B, corrupt_run_json=True)
        data = self.scanner.list_runs()
        self.assertEqual([item["run_id"] for item in data["runs"]], [RUN_A])

    def test_stale_minutes_only_for_non_terminal_runs(self):
        make_run(self.home, run_id=RUN_A, status="in_progress")
        make_run(self.home, project="p2", run_id=RUN_B, status="completed")
        data = self.scanner.list_runs()
        by_id = {item["run_id"]: item for item in data["runs"]}
        self.assertIsNotNone(by_id[RUN_A]["stale_minutes"])
        self.assertIsNone(by_id[RUN_B]["stale_minutes"])

    # ------------------------------------------------------------- 详情
    def test_detail_steps_and_current_stage(self):
        make_run(self.home, run_id=RUN_A, stage="image.dispatch")
        detail = self.scanner.run_detail(RUN_A)
        self.assertEqual([step["label"] for step in detail["steps"]], ["准备", "逐页生成", "交付"])
        states = {step["key"]: step["state"] for step in detail["steps"]}
        self.assertEqual(states["image.prepare"], "done")
        self.assertEqual(states["image.dispatch"], "current")
        self.assertEqual(states["image.finalize"], "pending")
        prepare = next(step for step in detail["steps"] if step["key"] == "image.prepare")
        self.assertAlmostEqual(prepare["duration_seconds"], 11.0, places=1)

    def test_detail_pages_infer_failure_from_timing(self):
        make_run(self.home, run_id=RUN_A, total=6, recorded=3, failed_pages=(3,), timeout_pages=(4,))
        detail = self.scanner.run_detail(RUN_A)
        by_number = {page["number"]: page for page in detail["pages"]}
        self.assertEqual(by_number[1]["state"], "recorded")
        self.assertEqual(by_number[3]["state"], "failed")
        self.assertEqual(by_number[3]["failure_reason"], "upstream_image_failed")
        self.assertEqual(by_number[4]["state"], "timeout")
        self.assertEqual(by_number[6]["state"], "pending")

    def test_detail_editable_active_reads_page_jobs(self):
        make_run(self.home, run_id=RUN_A, route="direct-editable", total=4, active_pages=(2,))
        detail = self.scanner.run_detail(RUN_A)
        by_number = {page["number"]: page for page in detail["pages"]}
        self.assertEqual(by_number[2]["state"], "active")

    def test_detail_pages_expose_render_lane_backends(self):
        # 混排牌组：render:* 页与 AI 渠道页并存，backend 逐页透传供 lane 徽标渲染；
        # render 页产物仍在 image-deck 域根内，走同一页图沙箱。
        make_run(
            self.home,
            run_id=RUN_A,
            total=6,
            recorded=6,
            failed_pages=(),
            render_pages={2: "render:html", 5: "render:mermaid"},
        )
        detail = self.scanner.run_detail(RUN_A)
        by_number = {page["number"]: page for page in detail["pages"]}
        self.assertEqual(by_number[1]["backend"], "zhipu")
        self.assertEqual(by_number[2]["backend"], "render:html")
        self.assertEqual(by_number[5]["backend"], "render:mermaid")
        self.assertTrue(by_number[2]["artifact"].startswith("render/html/"))
        content_type = self.scanner.page_image(RUN_A, 2)[1]
        self.assertEqual(content_type, "image/png")
        providers = detail["backend_stats"]["providers"]
        self.assertIn("render:html", providers)
        self.assertEqual(providers["render:html"]["tokens"], 0)

    def test_detail_events_tail_bad_lines_and_pagination(self):
        make_run(self.home, run_id=RUN_A, bad_event_lines=2)
        detail = self.scanner.run_detail(RUN_A)
        window = detail["events_window"]
        self.assertGreaterEqual(window["total_lines"], 10)
        self.assertEqual(window["bad_lines"], 2)
        seqs = [event["seq"] for event in window["events"]]
        self.assertEqual(seqs, sorted(seqs))
        earlier = self.scanner.run_detail(RUN_A, events_before=seqs[0])
        self.assertEqual(earlier["events_window"]["events"], [])

    def test_detail_delivery_gates_and_backend_stats(self):
        make_run(self.home, run_id=RUN_A, status="completed", final=True)
        detail = self.scanner.run_detail(RUN_A)
        self.assertEqual(len(detail["delivery"]["gates"]), 6)
        self.assertTrue(detail["delivery"]["deck_path"].endswith("final/deck.pptx"))
        providers = detail["backend_stats"]["providers"]
        self.assertEqual(providers["zhipu"]["calls"], 3)
        self.assertEqual(providers["zhipu"]["attempts"], 4)
        self.assertFalse(detail["backend_stats"]["tokens_recorded"])
        self.assertAlmostEqual(detail["duration_seconds"], 621.4, places=1)

    def test_detail_failure_fallback_without_reports(self):
        make_run(self.home, run_id=RUN_A, status="failed", stage="image.dispatch")
        detail = self.scanner.run_detail(RUN_A)
        self.assertIsNone(detail["delivery"]["gates"])
        self.assertEqual(detail["delivery"]["failure_summary"]["failed_stage"], "image.dispatch")

    def test_detail_unknown_pages_when_jobs_missing(self):
        run_dir = make_run(self.home, run_id=RUN_A)
        (run_dir / "image-deck" / "slide_jobs.json").unlink()
        detail = self.scanner.run_detail(RUN_A)
        self.assertEqual(len(detail["pages"]), 12)
        self.assertTrue(all(page["state"] == "unknown" for page in detail["pages"]))

    # ----------------------------------------------------- 契约与缓存防护
    def test_route_step_sequences_match_writer_routes(self):
        # 架构评审#4a：读侧步骤序列是写侧 ROUTES 的唯一副本，逐路线对齐。
        for route, definition in ROUTES.items():
            self.assertEqual(
                ROUTE_STEP_SEQUENCES.get(route),
                list(definition.steps),
                "route %s 步骤序列与写侧漂移" % route,
            )

    def test_index_cache_ttl_hides_new_runs_until_expiry(self):
        # 运维评审#1/架构#2：TTL 内命中缓存（新 run 下轮可见），invalidate 立即可见。
        frozen = {"now": 100.0}
        scanner = RunScanner(
            self.home, monotonic=lambda: frozen["now"], index_ttl=60.0
        )
        make_run(self.home, run_id=RUN_A)
        self.assertEqual([item["run_id"] for item in scanner.list_runs()["runs"]], [RUN_A])
        make_run(self.home, project="p2", run_id=RUN_B)
        self.assertEqual([item["run_id"] for item in scanner.list_runs()["runs"]], [RUN_A])
        scanner.invalidate_cache()
        self.assertEqual(
            sorted(item["run_id"] for item in scanner.list_runs()["runs"]),
            sorted([RUN_A, RUN_B]),
        )
        frozen["now"] += 61.0
        make_run(self.home, project="p3", run_id="c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6")
        self.assertEqual(len(scanner.list_runs()["runs"]), 3)

    def test_events_pagination_returns_window_adjacent_to_before(self):
        # 运维评审#3 附带 bug：before_seq 应取紧邻其前的 N 条而非全文件最旧 N 条。
        make_run(self.home, run_id=RUN_A)
        detail = self.scanner.run_detail(RUN_A, events_limit=3)
        all_events = detail["events_window"]["events"]
        self.assertLessEqual(len(all_events), 3)
        middle_seq = 4
        earlier = self.scanner.run_detail(RUN_A, events_before=middle_seq, events_limit=3)
        seqs = [event["seq"] for event in earlier["events_window"]["events"]]
        self.assertEqual(seqs, sorted(seqs))
        self.assertTrue(all(seq < middle_seq for seq in seqs))
        self.assertEqual(seqs[-1], middle_seq - 1)

    def test_run_not_found(self):
        with self.assertRaises(RunLookupError):
            self.scanner.run_detail("deadbeef" * 4)

    # ------------------------------------------------------------- 页图沙箱
    def test_page_image_serves_png(self):
        make_run(self.home, run_id=RUN_A)
        payload, content_type = self.scanner.page_image(RUN_A, 1)
        self.assertEqual(content_type, "image/png")
        self.assertGreater(len(payload), 100)

    def test_page_image_jpg_artifact(self):
        make_run(self.home, run_id=RUN_A, artifact_override={1: "origin_image/slide_01.jpg"})
        payload, content_type = self.scanner.page_image(RUN_A, 1)
        self.assertEqual(content_type, "image/jpeg")
        self.assertGreater(len(payload), 100)

    def test_page_image_missing_file(self):
        run_dir = make_run(self.home, run_id=RUN_A)
        (run_dir / "image-deck" / "origin_image" / "slide_01.png").unlink()
        with self.assertRaises(PreviewLookupError):
            self.scanner.page_image(RUN_A, 1)

    def test_page_image_rejects_traversal_artifact(self):
        make_run(self.home, run_id=RUN_A, artifact_override={1: "../../evil.png"})
        with self.assertRaises(PreviewLookupError):
            self.scanner.page_image(RUN_A, 1)

    def test_page_image_rejects_symlink_escape(self):
        outside = Path(self._tmp.name) / "outside.png"
        outside.write_bytes(b"PK-not-a-png")
        run_dir = make_run(self.home, run_id=RUN_A)
        escape = run_dir / "image-deck" / "origin_image" / "slide_01.png"
        escape.unlink()
        escape.symlink_to(outside)
        with self.assertRaises(PreviewLookupError):
            self.scanner.page_image(RUN_A, 1)

    def test_page_image_rejects_missing_page_or_run(self):
        make_run(self.home, run_id=RUN_A, total=4, recorded=2)
        with self.assertRaises(PreviewLookupError):
            self.scanner.page_image(RUN_A, 9)  # 页不存在
        with self.assertRaises(PreviewLookupError):
            self.scanner.page_image(RUN_A, 3)  # pending 无 artifact
        with self.assertRaises(RunLookupError):
            self.scanner.page_image("f" * 32, 1)  # run 不存在

    def test_page_image_rejects_bad_run_id_shape(self):
        with self.assertRaises(RunLookupError):
            self.scanner.page_image("../etc", 1)


if __name__ == "__main__":
    unittest.main()
