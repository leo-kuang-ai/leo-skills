"""聚焦回归（评审 P2#1）：CLI image record --rework 显式返工通道。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from leo_ppt_generator.cli import build_parser, dispatch  # noqa: E402
from leo_ppt_generator.contracts import ContractError  # noqa: E402
from leo_ppt_generator.image_deck.adapter import ImageDeckAdapter  # noqa: E402

SLIDES = [
    {"number": 1, "notes": ""},
    {"number": 2, "notes": ""},
]


def _record_cli(run_root: Path, number: int, png: Path, rework: bool):
    argv = [
        "image", "record", str(run_root),
        "--number", str(number),
        "--image", str(png),
        "--backend", "render:html",
        "--page-type", "text-heavy",
        "--agent-id", "cli-rework-test",
    ]
    if rework:
        argv.append("--rework")
    return dispatch(build_parser().parse_args(argv))


class CliReworkFlagTest(unittest.TestCase):
    def setUp(self):
        from PIL import Image

        self._tmp = tempfile.TemporaryDirectory(prefix="leo-p2c1-")
        run_root = Path(self._tmp.name) / "run-001"
        # 无 run.json 时 CLI 的 domain 路径即 run 根本身——adapter 同址。
        self.adapter = ImageDeckAdapter(run_root)
        self.adapter.prepare([dict(s) for s in SLIDES])
        self.png = Path(self._tmp.name) / "page.png"
        Image.new("RGB", (1600, 900), "#ffffff").save(self.png)
        self.run_root = run_root
        # 初始录制第 1 页
        jobs = self.adapter._jobs()
        self.adapter.record(1, self.png, backend="render:html",
                            expected_revision=jobs["revision"],
                            operation_id="op-initial")

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
        replay = dispatch(build_parser().parse_args([
            "image", "record", str(self.run_root),
            "--number", "1", "--image", str(self.png),
            "--backend", "render:html",
            "--operation-id", "op-initial",
        ]))
        self.assertIn(replay.get("status"), ("ready", "completed"))


if __name__ == "__main__":
    unittest.main()
