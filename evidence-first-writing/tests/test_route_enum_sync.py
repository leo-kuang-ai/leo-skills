"""路由枚举同步测试：SKILL.md 意图识别/operation 节 ↔ intent-routing.md canonical 枚举。

防漂移锁（对照审查 2026-09-04 第 3 条落地）：intent-routing.md 的 yaml 块是
lifecycle_intent / article_family / operation 三轴枚举的唯一事实源；SKILL.md
「入口意图识别」与「选择 operation」两节以中文概述 + 英文锚复述同一枚举。
任一侧增删值——包括 intent-routing.md 新增 lifecycle 后 SKILL.md 概述漏列
（2026-09 修复前 tool-select / personal-context 即处此态）——本文件即红。
本锁只约束枚举成员的覆盖与一致，不锁中文措辞本身。
"""

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
INTENT_ROUTING = SKILL_DIR / "references" / "intent-routing.md"
SKILL_MD = SKILL_DIR / "SKILL.md"

AXES = ("lifecycle_intent", "article_family", "operation")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _enum_from_routing(axis: str) -> list[str]:
    matches = re.findall(rf"^{axis}:\s*([^\n]+)$", _read(INTENT_ROUTING), re.MULTILINE)
    enum_lines = [m for m in matches if "|" in m]
    if not enum_lines:
        raise AssertionError(f"intent-routing.md 缺少 {axis} canonical 枚举行")
    values = [v.strip() for v in enum_lines[0].split("|")]
    if not all(values):
        raise AssertionError(f"{axis} 枚举行存在空值")
    return values


def _skill_axis_line(axis: str) -> str:
    match = re.search(rf"^\d+\.\s*`{axis}`：(.*)$", _read(SKILL_MD), re.MULTILINE)
    if not match:
        raise AssertionError(f"SKILL.md 入口意图识别节缺少 {axis} 概述行")
    return match.group(1)


def _operation_section() -> str:
    match = re.search(
        r"^## 选择 operation\n(.*?)(?=^## )", _read(SKILL_MD), re.DOTALL | re.MULTILINE
    )
    if not match:
        raise AssertionError("SKILL.md 缺少「选择 operation」节")
    return match.group(1)


class RouteEnumSyncTest(unittest.TestCase):
    def test_intent_routing_defines_all_axes(self):
        for axis in AXES:
            with self.subTest(axis=axis):
                self.assertGreaterEqual(len(_enum_from_routing(axis)), 3)

    def test_lifecycle_overview_covers_every_canonical_value(self):
        line = _skill_axis_line("lifecycle_intent")
        for value in _enum_from_routing("lifecycle_intent"):
            with self.subTest(value=value):
                self.assertIn(f"`{value}`", line)

    def test_family_overview_covers_every_canonical_value(self):
        line = _skill_axis_line("article_family")
        for value in _enum_from_routing("article_family"):
            with self.subTest(value=value):
                self.assertIn(f"`{value}`", line)

    def test_overview_lines_invent_no_values(self):
        for axis in ("lifecycle_intent", "article_family"):
            canonical = set(_enum_from_routing(axis))
            tokens = set(re.findall(r"`([^`]+)`", _skill_axis_line(axis)))
            invented = tokens - canonical - {axis}
            self.assertEqual(invented, set(), f"SKILL.md {axis} 概述行私造枚举值: {invented}")

    def test_operation_section_matches_canonical_enum(self):
        canonical = set(_enum_from_routing("operation"))
        defined = set(re.findall(r"`([^`]+)`：", _operation_section()))
        self.assertEqual(defined - canonical, set(), "SKILL.md operation 节存在私造值")
        self.assertEqual(canonical - defined, set(), "SKILL.md operation 节漏列 canonical operation")


if __name__ == "__main__":
    unittest.main()
