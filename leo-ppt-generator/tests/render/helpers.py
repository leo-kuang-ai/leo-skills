"""tests/render 共享助手：浏览器可用性探测（skip 纪律：skip ≠ pass）。"""

from __future__ import annotations

import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]


def browser_available() -> tuple[bool, str]:
    """探测 playwright + chromium；返回 (available, 原因)。"""

    try:
        from leo_ppt_generator.render.readiness import probe
    except Exception as exc:  # pragma: no cover
        return False, f"render module import failed: {exc}"
    report = probe(launch=True)
    return report.status == "render_backend_ready", (
        f"render backend missing/unknown: {report.status} "
        f"({report.details.get('probe_error') or report.details.get('missing')})"
    )


def browser_test_case() -> type:
    """需要真浏览器的测试基类：探测失败 → skip 并显式披露原因。"""

    available, reason = browser_available()

    class _BrowserTestCase(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            if not available:
                raise unittest.SkipTest(
                    f"render backend missing（skip ≠ pass，环境装好后必须全跑）: {reason}"
                )

    return _BrowserTestCase
