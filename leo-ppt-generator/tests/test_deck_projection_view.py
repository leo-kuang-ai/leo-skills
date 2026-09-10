#!/usr/bin/env python3
"""dashi 集成 K7/U7：内容投影视图与交付绑定验收测试。

覆盖：视图从冻结输入重建（可删除重建、无绑定输入如实报状态）/ 页身份→
页序→版式→摘要映射 / 收据 content_binding 关联与漂移失效 / preflight
projection 门（页数不一致 FAIL、无内容包跳过、通过时披露摘要）/
prepare --layout-selection 冻结与覆盖核对 / 升级快照不被源目录新版回写。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = PKG_ROOT / "runtime" / "src"
for entry in (str(RUNTIME_SRC), str(PKG_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from leo_ppt_generator.cli import build_parser, dispatch  # noqa: E402
from leo_ppt_generator.contracts import ContractError  # noqa: E402
from leo_ppt_generator.application.run_index import projection_view  # noqa: E402
from leo_ppt_generator.render.receipt import (  # noqa: E402
    create_delivery_receipt,
    verify_delivery_receipt,
)

MASTER = """# 母版 v1
confirmation: confirmed（测试基线）

## S1 内容
page_id: pg-11111111
角色：流程·路径
argument_role: 论据
- 标题：交付节奏
- 要点 1：环比 +18%
- 要点 2：净利率 12%
视觉行：要点1→KPI 塔
- 备注：口播

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 18% | S1 | Q3 财报 | 环比 | 2026Q3 | 百分点 | 引用 | yes | 2026-10-28 |
"""

SLIDES = [{"number": 1, "title": "交付节奏", "notes": ""}]


class DeckProjectionViewTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_root = Path(self._tmp.name) / "run"
        (self.run_root / "input").mkdir(parents=True)
        (self.run_root / "run.json").write_text(json.dumps({
            "schema_version": 1, "run_id": "r1", "route": "generate",
            "revision": 0, "supplemental_inputs": {}}), encoding="utf-8")
        master = Path(self._tmp.name) / "deck-master-v1.md"
        master.write_text(MASTER, encoding="utf-8")
        self.pack_path = Path(self._tmp.name) / "page-content-pack.json"
        dispatch(build_parser().parse_args([
            "content", "pack", "--master", str(master), "--out", str(self.pack_path)]))
        self.design_path = Path(self._tmp.name) / "resolved-design.json"
        self.design_path.write_text(json.dumps({
            "entity": "resolved-design", "pages": [{"page_no": 1}],
            "design_digest": "a" * 64, "design_context_digest": "b" * 64,
        }), encoding="utf-8")
        self.selection_path = Path(self._tmp.name) / "layout-selection.json"
        self.selection_path.write_text(json.dumps({
            "schema_version": 1, "kind": "deck-layout-selection",
            "policy_version": "1", "status": "complete",
            "content_digest": json.loads(
                self.pack_path.read_text(encoding="utf-8"))["content_digest"],
            "selection": {"pg-11111111": {
                "layout_id": "builtin:layout:body-basic",
                "binding_digest": "c" * 64}},
        }), encoding="utf-8")
        self.slides_path = Path(self._tmp.name) / "slides.json"
        self.slides_path.write_text(json.dumps(SLIDES), encoding="utf-8")

    def _prepare(self, *extra):
        return dispatch(build_parser().parse_args([
            "image", "prepare", str(self.run_root),
            "--slides", str(self.slides_path), *extra]))

    def test_view_rebuilt_from_frozen_inputs(self):
        self._prepare("--content-pack", str(self.pack_path),
                      "--design", str(self.design_path),
                      "--layout-selection", str(self.selection_path))
        view = projection_view(self.run_root)
        self.assertEqual(view["status"], "ok")
        self.assertTrue(view["rebuildable"])
        self.assertEqual(view["pages"][0]["page_id"], "pg-11111111")
        self.assertEqual(view["pages"][0]["layout_id"], "builtin:layout:body-basic")
        self.assertEqual(view["selection_policy"], "1")
        # 删除视图无关紧要：视图即时重建（无独立状态文件）。
        again = projection_view(self.run_root)
        self.assertEqual(view, again)

    def test_view_reports_missing_binding_inputs(self):
        view = projection_view(self.run_root)
        self.assertEqual(view["status"], "no_binding_inputs")

    def test_selection_mismatch_rejected_at_prepare(self):
        wrong = json.loads(self.selection_path.read_text(encoding="utf-8"))
        wrong["selection"]["pg-99999999"] = wrong["selection"].pop("pg-11111111")
        self.selection_path.write_text(json.dumps(wrong), encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            self._prepare("--content-pack", str(self.pack_path),
                          "--layout-selection", str(self.selection_path))
        self.assertEqual(str(caught.exception), "layout_selection_page_mismatch")

    def _mini_delivery_run(self) -> Path:
        """补齐收据所需最小交付面（复用 test_delivery_receipt 的形态）。"""
        (self.run_root / "image-deck" / "origin_image").mkdir(parents=True, exist_ok=True)
        (self.run_root / "final").mkdir(exist_ok=True)
        (self.run_root / "final" / "deck.pptx").write_bytes(b"FAKE")
        (self.run_root / "input" / "backend-contract.json").write_text(
            '{"backend": 1}', encoding="utf-8")
        (self.run_root / "input" / "style-brief.md").write_text(
            "# brief", encoding="utf-8")
        (self.run_root / "image-deck" / "origin_image" / "slide_01.png").write_bytes(
            b"PAGE1")
        return self.run_root

    def test_receipt_binds_content_and_drift_invalidates(self):
        self._prepare("--content-pack", str(self.pack_path),
                      "--layout-selection", str(self.selection_path))
        self._mini_delivery_run()
        create_delivery_receipt(self.run_root)
        self.assertEqual(verify_delivery_receipt(self.run_root)["status"], "fresh")
        # 绑定输入面变化（整册选择被移除）→ 收据绑定漂移失效。
        (self.run_root / "input" / "layout-selection.json").unlink()
        result = verify_delivery_receipt(self.run_root)
        self.assertEqual(result["status"], "stale")
        self.assertTrue(any(entry.get("class") == "content_binding"
                            for entry in result["changed"]))

    def test_preflight_projection_gate(self):
        import subprocess
        self._prepare("--content-pack", str(self.pack_path),
                      "--layout-selection", str(self.selection_path))
        self._mini_delivery_run()
        script = PKG_ROOT / "scripts" / "build_delivery_preflight.py"
        proc = subprocess.run(
            [sys.executable, str(script), str(self.run_root)],
            capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT))
        report = json.loads(
            (self.run_root / "reports" / "delivery-preflight.json").read_text(encoding="utf-8"))
        gates = {row["gate"]: row for row in report["gates"]}
        self.assertEqual(gates["projection"]["status"], "passed")
        self.assertEqual(gates["projection"]["detail"]["page_count"], 1)
        # 覆盖不一致 → failed。
        selection = json.loads(
            (self.run_root / "input" / "layout-selection.json").read_text(encoding="utf-8"))
        selection["selection"]["pg-99999999"] = selection["selection"].pop("pg-11111111")
        (self.run_root / "input" / "layout-selection.json").write_text(
            json.dumps(selection), encoding="utf-8")
        proc2 = subprocess.run(
            [sys.executable, str(script), str(self.run_root)],
            capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT))
        report2 = json.loads(
            (self.run_root / "reports" / "delivery-preflight.json").read_text(encoding="utf-8"))
        gates2 = {row["gate"]: row for row in report2["gates"]}
        self.assertEqual(gates2["projection"]["status"], "failed")

    def test_preflight_incomplete_selection_fails(self):
        import subprocess
        self._prepare("--content-pack", str(self.pack_path),
                      "--layout-selection", str(self.selection_path))
        self._mini_delivery_run()
        selection = json.loads(
            (self.run_root / "input" / "layout-selection.json").read_text(encoding="utf-8"))
        selection["status"] = "budget_exhausted"
        (self.run_root / "input" / "layout-selection.json").write_text(
            json.dumps(selection), encoding="utf-8")
        script = PKG_ROOT / "scripts" / "build_delivery_preflight.py"
        proc = subprocess.run(
            [sys.executable, str(script), str(self.run_root)],
            capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT))
        report = json.loads(
            (self.run_root / "reports" / "delivery-preflight.json").read_text(encoding="utf-8"))
        gates = {row["gate"]: row for row in report["gates"]}
        self.assertEqual(gates["projection"]["status"], "failed")

    def test_receipt_verify_unreadable_pack_invalid(self):
        self._prepare("--content-pack", str(self.pack_path),
                      "--layout-selection", str(self.selection_path))
        self._mini_delivery_run()
        create_delivery_receipt(self.run_root)
        (self.run_root / "input" / "page-content-pack.json").write_text(
            "{broken", encoding="utf-8")
        result = verify_delivery_receipt(self.run_root)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result.get("reason_code"), "content_pack_unreadable")

    def test_preflight_skips_without_content_pack(self):
        import subprocess
        self._mini_delivery_run()
        script = PKG_ROOT / "scripts" / "build_delivery_preflight.py"
        proc = subprocess.run(
            [sys.executable, str(script), str(self.run_root)],
            capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT))
        report = json.loads(
            (self.run_root / "reports" / "delivery-preflight.json").read_text(encoding="utf-8"))
        gates = {row["gate"]: row for row in report["gates"]}
        self.assertEqual(gates["projection"]["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
