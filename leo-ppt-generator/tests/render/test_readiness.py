"""D1-T1 readiness 三态探测的可观察行为测试（离线，不需要浏览器）。"""

from __future__ import annotations

import importlib.metadata
import unittest
from unittest import mock

from leo_ppt_generator.render import readiness
from leo_ppt_generator.render.page import parse_size
from leo_ppt_generator.render.errors import RenderError


class RenderReadyReportsMissingBackendWithoutNetwork(unittest.TestCase):
    """缺 playwright 包时必须如实报 missing + 安装指引，而不是抛异常。"""

    def test_missing_playwright_package_reports_missing_with_guide(self):
        with mock.patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError("playwright"),
        ):
            report = readiness.probe(launch=False)
        self.assertEqual(report.status, "render_backend_missing")
        self.assertIn("playwright", report.details["missing"])
        self.assertIsNotNone(report.install_guide)
        self.assertIn("playwright install chromium", report.install_guide)

    def test_missing_chromium_binary_reports_missing(self):
        with mock.patch.object(
            readiness, "_probe_chromium", return_value=(None, None, "chromium executable missing")
        ):
            report = readiness.probe(launch=False)
        self.assertEqual(report.status, "render_backend_missing")
        self.assertEqual(report.details["missing"], ["chromium"])
        self.assertIsNotNone(report.install_guide)

    def test_launch_failure_with_executable_present_reports_unknown(self):
        # 组件在场但启动探测不可判 → unknown（按 missing 抑制路由，但披露差异）。
        with mock.patch.object(
            readiness,
            "_probe_chromium",
            return_value=("/some/chromium", None, "chromium probe failed: crashed"),
        ):
            report = readiness.probe(launch=True)
        self.assertEqual(report.status, "render_backend_unknown")
        self.assertNotIn("missing", report.details)
        self.assertIn("probe_error", report.details)


class ParseSizeContract(unittest.TestCase):
    """--size 合同：缺省交付档；非 16:9 / 非 1x|2x 档拒绝。"""

    def test_default_size_is_delivery_tier(self):
        self.assertEqual(parse_size(None), (2560, 1440))
        self.assertEqual(parse_size("2560x1440"), (2560, 1440))
        self.assertEqual(parse_size("1280x720"), (1280, 720))

    def test_non_16_9_rejected_with_stable_reason(self):
        with self.assertRaises(RenderError) as ctx:
            parse_size("1920x1200")
        self.assertEqual(ctx.exception.reason_code, "render_size_mismatch")

    def test_unsupported_scale_rejected(self):
        from leo_ppt_generator.render.page import _device_scale_factor, RenderSizeError

        with self.assertRaises(RenderSizeError):
            _device_scale_factor((3840, 2160))  # dsf 3 不在合同档
        with self.assertRaises(RenderSizeError):
            _device_scale_factor((1000, 563))


if __name__ == "__main__":
    unittest.main()
