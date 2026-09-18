"""语料参考资产合同测试（UB3/UB4，方案 2026-09-02-002）。

覆盖：构图词汇参考文档存在性与边界声明、OfficeMCP 色板池增量（静态源
幂等 + 查询通道）、手绘系 brief 素材语汇词条。
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
COMPOSITION_DOC = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles") / "00_索引" / "构图词汇参考.md"
POOL_JSON = SKILL_DIR / "scripts" / "chart-palette-pool.json"
POOL_SCRIPT = SKILL_DIR / "scripts" / "chart_palette_pool.py"


def _load_pool_module():
    spec = importlib.util.spec_from_file_location("chart_palette_pool", POOL_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CompositionVocabularyDoc(unittest.TestCase):
    def test_doc_exists_with_six_categories(self):
        """六类视觉词汇（布局/视角/光照/色调/材质/主体状态）全部在场。"""
        text = COMPOSITION_DOC.read_text(encoding="utf-8")
        for heading in ("布局结构", "视角镜头", "光照", "色调氛围", "材质质感", "主体状态"):
            self.assertIn(heading, text, f"缺六类词汇之：{heading}")

    def test_doc_declares_density_boundary_and_source(self):
        """含"不学富提示词密度"边界声明与 MIT 来源登记。"""
        text = COMPOSITION_DOC.read_text(encoding="utf-8")
        self.assertIn("富提示词密度", text)
        self.assertIn("MIT", text)
        self.assertIn("nano-banana", text)


class OfficeMcpPalettePool(unittest.TestCase):
    def test_pool_json_contains_four_office_mcp_entries(self):
        """池 JSON 含 4 组 office_mcp/ 条目，来源登记指向上游定义。"""
        pool = json.loads(POOL_JSON.read_text(encoding="utf-8"))
        entries = {k: v for k, v in pool.items() if k.startswith("office_mcp/")}
        self.assertEqual(
            sorted(entries),
            [
                "office_mcp/corporate_gray",
                "office_mcp/elegant_green",
                "office_mcp/modern_blue",
                "office_mcp/warm_red",
            ],
        )
        for entry in entries.values():
            self.assertIn("PROFESSIONAL_COLOR_SCHEMES", entry["source"])

    def test_modern_blue_series_starts_with_microsoft_blue(self):
        """系列色序首色 = primary（Microsoft Blue #0078D7），background=light。"""
        pool = json.loads(POOL_JSON.read_text(encoding="utf-8"))
        entry = pool["office_mcp/modern_blue"]
        self.assertEqual(entry["colors"][0], "#0078D7")
        self.assertEqual(entry["background"], "#F7F7F7")

    def test_static_source_is_deterministic_and_idempotent(self):
        """build_pool(None, None) 只产静态源，两次调用逐字节一致（--aggregate 幂等前提）。"""
        mod = _load_pool_module()
        first = mod.build_pool(None, None)
        second = mod.build_pool(None, None)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)

    def test_committed_json_office_mcp_equals_static_source(self):
        """提交态池的 office_mcp 条目 == 生成器静态源（常量与 JSON 不漂移）。"""
        mod = _load_pool_module()
        pool = json.loads(POOL_JSON.read_text(encoding="utf-8"))
        committed = {k: v for k, v in pool.items() if k.startswith("office_mcp/")}
        self.assertEqual(committed, mod.build_pool(None, None))


class HanddrawnVocabularyIncrement(unittest.TestCase):
    def test_whiteboard_brief_gains_torn_tape_sticky_note(self):
        raw = (SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles") / "手绘白板风.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("torn-tape", raw)

    def test_tech_explainer_brief_gains_callout_bubble(self):
        raw = (SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles") / "手绘技术解释风.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("callout bubbles", raw)


if __name__ == "__main__":
    unittest.main()
