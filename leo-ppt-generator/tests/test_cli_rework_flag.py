"""聚焦回归（评审 P2#1）：CLI image record --rework 显式返工通道。"""
from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from leo_ppt_generator.cli import build_parser, dispatch  # noqa: E402
from leo_ppt_generator.contracts import ContractError  # noqa: E402
from leo_ppt_generator.image_deck.adapter import ImageDeckAdapter  # noqa: E402

SLIDES = [
    {"number": 1, "notes": ""},
    {"number": 2, "notes": ""},
]


def _record_cli(run_root: Path, number: int, png: Path, rework: bool, operation_id=None):
    argv = [
        "image", "record", str(run_root),
        "--number", str(number),
        "--image", str(png),
        "--backend", "render:html",
        "--render-receipt", str(png.with_name(png.name + ".render.json")),
        "--page-type", "text-heavy",
        "--agent-id", "cli-rework-test",
    ]
    if rework:
        argv.append("--rework")
    if operation_id:
        argv.extend(["--operation-id", operation_id])
    return dispatch(build_parser().parse_args(argv))


class CliReworkFlagTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-p2c1-")
        run_root = Path(self._tmp.name).resolve() / "run-001"
        from tests.expression_test_support import copy_real_html_run, slides_for_run
        result = copy_real_html_run(run_root, request_index=True)
        slides = run_root / "work/slides.json"
        slides.write_text(json.dumps(slides_for_run(run_root)))
        dispatch(build_parser().parse_args(["image", "prepare", str(run_root), "--slides", str(slides)]))
        self.adapter = ImageDeckAdapter(run_root / "image-deck")
        self.png = run_root / result["receipt_refs"]["render:html"]["pg-11111111"]["artifact"]
        self.run_root = run_root
        _record_cli(run_root, 1, self.png, rework=False, operation_id="op-initial")

    def tearDown(self):
        self._tmp.cleanup()

    def test_without_flag_late_record_rejected(self):
        with self.assertRaises(ContractError) as caught:
            _record_cli(self.run_root, 1, self.png, rework=False)
        self.assertEqual(str(caught.exception), "page_already_recorded")

    def test_with_flag_rework_replaces_recorded_page(self):
        result = _record_cli(self.run_root, 1, self.png, rework=True)
        self.assertIn(result.get("status"), ("ready", "completed"))
        # 幂等重放不需要 rework 旗标
        replay = _record_cli(self.run_root, 1, self.png, rework=False, operation_id="op-initial")
        self.assertIn(replay.get("status"), ("ready", "completed"))

    def test_html_lane_rejects_provider_receipt_without_changing_page_jobs(self):
        before = self.adapter.jobs_path.read_bytes()
        with self.assertRaisesRegex(ContractError, "effective_binding_receipt_lane_mismatch"):
            dispatch(build_parser().parse_args(["image", "record", str(self.run_root),
                "--number", "1", "--image", str(self.png), "--backend", "render:html",
                "--provider-receipt", str(self.png) + ".provider.json", "--operation-id", "wrong-lane"]))
        self.assertEqual(self.adapter.jobs_path.read_bytes(), before)

    def test_page_and_provenance_are_recorded_together_and_bound_on_retry(self):
        # 使用实际HTML导出验证通用文件事务，不冒充Provider正向集成。
        receipt = json.loads(self.png.with_name(self.png.name + ".render.json").read_text())
        self.adapter.record(1, self.png, backend="render:html", expected_revision=self.adapter._jobs()["revision"],
                            operation_id="with-provenance", rework=True, provenance=receipt)
        jobs = self.adapter._jobs()
        self.assertEqual(jobs["slides"][0]["provenance"], receipt)
        self.assertEqual(jobs["slides"][0]["sha256"], receipt["out_sha256"])
        before = self.adapter.jobs_path.read_bytes()
        with self.assertRaisesRegex(ContractError, "idempotency_conflict"):
            self.adapter.record(1, self.png, backend="render:html", expected_revision=jobs["revision"],
                                operation_id="with-provenance", provenance={**receipt, "revision": "changed"})
        with self.assertRaisesRegex(ContractError, "page_provenance_artifact_mismatch"):
            self.adapter.record(1, self.png, backend="render:html", expected_revision=jobs["revision"],
                                operation_id="bad-provenance", rework=True, provenance={**receipt, "out_sha256": "f" * 64})
        self.assertEqual(self.adapter.jobs_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
