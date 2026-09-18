"""聚焦回归（WS3 渲染溢出哨兵，加固方案 2026-09-07-002）：

模板合同第七条——全部 ``data-leo-block`` 渲染后必须完整落在逻辑画幅内且
块内容不超出其盒。越界 → ``render_overflow`` 拒产；观察模式（
``LEO_PPT_RENDER_OVERFLOW=warn``）降级为 sidecar 警告。D-CHART-01 类缺陷
从视觉 QA 前移到渲染期拦截。
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from leo_ppt_generator.render.errors import RenderError  # noqa: E402
from leo_ppt_generator.render.page import render_page  # noqa: E402

from tests.render.helpers import browser_test_case  # noqa: E402


def _write_data(root: Path, name: str, payload: dict) -> Path:
    target = root / name
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target


class OverflowSentinelTest(browser_test_case()):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-ws3-")
        self.root = Path(self._tmp.name)
        self._prev_mode = os.environ.get("LEO_PPT_RENDER_OVERFLOW")
        os.environ.pop("LEO_PPT_RENDER_OVERFLOW", None)

    def tearDown(self):
        if self._prev_mode is not None:
            os.environ["LEO_PPT_RENDER_OVERFLOW"] = self._prev_mode
        else:
            os.environ.pop("LEO_PPT_RENDER_OVERFLOW", None)
        self._tmp.cleanup()

    def test_overflowing_page_is_rejected_without_artifact(self):
        # D-CHART-01 形态复现：要点足够多 + 图表，内容总高超出 720 逻辑画幅。
        data = _write_data(self.root, "overflow.json", {
            "title": "溢出哨兵回归：要点超容组合",
            "bullets": [f"第 {i} 条要点：内容足够长以触达画幅底部边界场景" for i in range(1, 9)],
            "chart_svg": "<svg viewBox='0 0 700 500' style='max-width: 700px;'>"
                         "<rect width='700' height='500'/></svg>",
            "page_no": "02",
        })
        out = self.root / "overflow.png"
        with self.assertRaises(RenderError) as caught:
            render_page("body-basic", data, out)
        self.assertEqual(caught.exception.reason_code, "render_overflow")
        self.assertFalse(out.exists(), "越界页不得留下产物")
        self.assertFalse(out.with_name(out.name + ".render.json").exists())

    def test_warn_mode_records_sidecar_warning_and_produces(self):
        data = _write_data(self.root, "overflow-warn.json", {
            "title": "观察模式：越界只记不拦",
            "bullets": [f"观察模式第 {i} 条要点，用于验证降级通道完整性" for i in range(1, 9)],
            "page_no": "03",
        })
        out = self.root / "overflow-warn.png"
        os.environ["LEO_PPT_RENDER_OVERFLOW"] = "warn"
        result = render_page("body-basic", data, out)
        self.assertTrue(out.exists())
        self.assertEqual(result["overflow_check"], "warn")
        self.assertTrue(any(w.startswith("overflow_observed:") for w in result["warnings"]))

    def test_normal_pages_pass_sentinel(self):
        for template, payload in (
            ("cover-basic", {"kicker": "k", "title": "正常封面", "subtitle": "副题"}),
            ("body-basic", {"title": "正常正文页",
                            "bullets": ["要点一：短句", "要点二：短句"], "page_no": "01"}),
            ("pull-quote", {"quote": "一句引语。", "source_name": "来源", "source_meta": "2026"}),
            ("spec-table", {"title": "规格表", "columns": ["列A", "列B", "列C"],
                            "column_align": ["left", "right", "left"], "rows": [["a", "1", "x"], ["b", "2", "y"], ["c", "3", "z"]],
                            "page_no": "04"}),
            ("timeline", {"title": "时间线", "steps": ["一", "二", "三", "四"], "page_no": "05"}),
            ("compare", {"sides": [{"label": "左", "title": "A", "points": ["x"]},
                                   {"label": "右", "title": "B", "points": ["y"]}]}),
        ):
            with self.subTest(template=template):
                data = _write_data(self.root, f"{template}.json", payload)
                out = self.root / f"{template}.png"
                result = render_page(template, data, out)
                self.assertEqual(result["overflow_check"], "pass")
                self.assertTrue(out.exists())

    def test_spec_table_two_columns_are_rejected_before_render(self):
        data = _write_data(self.root, "bad-columns.json", {
            "title": "规格表", "columns": ["列A", "列B"],
            "column_align": ["left", "right"], "rows": [["a", "1"]], "page_no": "04"})
        with self.assertRaises(RenderError) as ctx:
            render_page("spec-table", data, self.root / "bad-columns.png")
        self.assertEqual(ctx.exception.reason_code, "render_data_invalid")
        self.assertFalse((self.root / "bad-columns.png").exists())


if __name__ == "__main__":
    unittest.main()
