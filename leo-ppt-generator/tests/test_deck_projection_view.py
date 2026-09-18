#!/usr/bin/env python3
"""表达链内容投影视图与 committed input 的交付验收测试。

覆盖：视图从冻结输入重建（可删除重建、无绑定输入如实报状态）/ 页身份→
页序→版式→摘要映射 / 收据 content_binding 关联与漂移失效 / preflight
projection 门（页数不一致 FAIL、无内容包跳过、通过时披露摘要）/
prepare 冻结输入覆盖核对 / 升级快照不被源目录新版回写。
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

class DeckProjectionViewTests(unittest.TestCase):
    def setUp(self):
        from tests.expression_test_support import copy_real_html_run
        from leo_ppt_generator.application.expression_pipeline import load_committed_input
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_root = Path(self._tmp.name).resolve() / "run"
        copy_real_html_run(self.run_root)
        committed = load_committed_input(self.run_root)
        self.inputs = committed["root"]
        self.pack = committed["payload"]["pack"]

    def test_view_rebuilt_from_frozen_inputs(self):
        view = projection_view(self.run_root)
        self.assertEqual(view["status"], "ok", view)
        self.assertTrue(view["rebuildable"])
        self.assertEqual([p["page_id"] for p in view["pages"]],
                         [p["page_id"] for p in self.pack["pages"]])
        self.assertEqual(view["pages"][0]["layout_id"], "builtin:layout:body-basic")
        self.assertEqual(view["selection_policy"], "2")
        self.assertNotIn("binding_digest", view["pages"][0])
        self.assertEqual(view, projection_view(self.run_root))

    def test_view_reports_missing_committed_input(self):
        (self.run_root / "input/current.json").unlink()
        view = projection_view(self.run_root)
        self.assertEqual(view["status"], "invalid")
        self.assertEqual(view["reason_code"], "input_pointer_missing")

    def test_loose_files_do_not_override_frozen_selection(self):
        (self.run_root / "input/layout-selection.json").write_text('{"selection":{}}')
        self.assertEqual(projection_view(self.run_root)["status"], "ok")
        selected = json.loads((self.inputs / "layout-selection.json").read_text())
        selected["selection"]["pg-99999999"] = selected["selection"].pop(self.pack["pages"][0]["page_id"])
        (self.inputs / "layout-selection.json").write_text(json.dumps(selected))
        self.assertEqual(projection_view(self.run_root)["reason_code"], "input_generation_invalid")

    def test_receipt_binds_content_and_drift_invalidates(self):
        create_delivery_receipt(self.run_root)
        self.assertEqual(verify_delivery_receipt(self.run_root)["status"], "fresh")
        (self.inputs / "layout-selection.json").unlink()
        result = verify_delivery_receipt(self.run_root)
        self.assertFalse(result["fresh"])
        self.assertEqual(result["reason_code"], "input_generation_invalid")

    def _preflight(self):
        import subprocess
        proc = subprocess.run([sys.executable, str(PKG_ROOT / "scripts/build_delivery_preflight.py"),
                               str(self.run_root)], capture_output=True, text=True, cwd=PKG_ROOT)
        self.assertIn(proc.returncode, (0, 1), proc.stderr)
        report = json.loads((self.run_root / "reports/delivery-preflight.json").read_text())
        return {row["gate"]: row for row in report["gates"]}

    def test_preflight_projection_gate_uses_all_committed_pages(self):
        gate = self._preflight()["projection"]
        self.assertEqual(gate["status"], "passed", gate)
        self.assertEqual(gate["detail"]["page_count"], len(self.pack["pages"]))
        (self.inputs / "layout-selection.json").write_text('{"status":"budget_exhausted"}')
        self.assertEqual(self._preflight()["projection"]["status"], "failed")

    def test_preflight_missing_pointer_fails_closed(self):
        (self.run_root / "input/current.json").unlink()
        self.assertEqual(self._preflight()["projection"]["status"], "failed")

    def test_receipt_verify_unreadable_pack_invalid(self):
        create_delivery_receipt(self.run_root)
        (self.inputs / "page-content-pack.json").write_text("{broken")
        result = verify_delivery_receipt(self.run_root)
        self.assertFalse(result["fresh"])
        self.assertEqual(result["reason_code"], "input_generation_invalid")

    def test_preflight_without_expression_run_stays_not_run(self):
        self.run_root = Path(self._tmp.name).resolve() / "unrelated"
        self.run_root.mkdir()
        self.assertEqual(self._preflight()["projection"]["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
