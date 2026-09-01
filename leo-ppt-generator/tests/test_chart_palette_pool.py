#!/usr/bin/env python3
"""chart_palette_pool.py 弹药库测试（机制线 M1）：双源解析器纯函数、
聚合确定性/命名空间、CLI 查询语义、提交快照合同（53 条全 hex）。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import chart_palette_pool as cpp  # noqa: E402

SNAPSHOT = SCRIPTS_DIR / "chart-palette-pool.json"

ECHARTS_SAMPLE = """
var colorPalette = [
    '#2ec7c9', '#b6a2de', '#0F0F2D'
];
var theme = {
    color: colorPalette,
    backgroundColor: '#fef8ef',
    tooltip: {
        backgroundColor: 'rgba(0,0,0,0.5)',
        axisPointer: { lineStyle: { color: ['#eee', '#ddd'] } }
    }
};
"""

PRESET_PY_SAMPLE = """
from typing import dict
PRESET_PALETTES: dict[str, dict[str, str]] = {
    "corporate_blue": {
        "dark1": "#1B2A4A", "light1": "#FFFFFF", "dark2": "#44546A", "light2": "#F2F2F2",
        "accent1": "#2B579A", "accent2": "#BF4B28", "accent3": "#2E7D32",
        "accent4": "#7B3FA0", "accent5": "#C4652A", "accent6": "#1A7A8A",
    },
}
OTHER = {"unrelated": True}
"""


class ParseEchartsJsTest(unittest.TestCase):
    def test_extracts_series_colors_in_source_order(self):
        colors, _bg = cpp.parse_echarts_js(ECHARTS_SAMPLE)
        self.assertEqual(colors, ["#2ec7c9", "#b6a2de", "#0F0F2D"])

    def test_drops_short_hex_and_dedupes(self):
        text = """
        var colorPalette = ['#abc', '#2ec7c9', '#2ec7c9', 'red'];
        """
        colors, _bg = cpp.parse_echarts_js(text)
        self.assertEqual(colors, ["#2ec7c9"])

    def test_indented_theme_background_wins_over_tooltip_rgba(self):
        colors, bg = cpp.parse_echarts_js(ECHARTS_SAMPLE)
        self.assertEqual(bg, "#fef8ef")

    def test_var_background_declaration_preferred(self):
        text = """
        var backgroundColor = '#100C2A';
        var theme = { backgroundColor: backgroundColor };
        """
        _colors, bg = cpp.parse_echarts_js(text)
        self.assertEqual(bg, "#100C2A")

    def test_color_all_alias_supported(self):
        text = "var colorAll = ['#F2385A', '#F5A503'];\nvar theme = { color: colorAll };"
        colors, _bg = cpp.parse_echarts_js(text)
        self.assertEqual(colors, ["#F2385A", "#F5A503"])


class ParsePresetPalettesTest(unittest.TestCase):
    def test_extracts_dict_literal_via_ast(self):
        presets = cpp.parse_preset_palettes_py(PRESET_PY_SAMPLE)
        self.assertEqual(
            presets["corporate_blue"]["accent1"],
            "#2B579A",
        )

    def test_missing_symbol_returns_empty(self):
        self.assertEqual(cpp.parse_preset_palettes_py("OTHER = 1\n"), {})


class BuildPoolTest(unittest.TestCase):
    def test_namespaced_sorted_and_accent_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            (tmpdir / "zeta.js").write_text(
                "var colorPalette = ['#111111'];", encoding="utf-8"
            )
            (tmpdir / "alpha.js").write_text(
                "var colorPalette = ['#222222'];", encoding="utf-8"
            )
            themes_py = tmpdir / "themes.py"
            themes_py.write_text(PRESET_PY_SAMPLE, encoding="utf-8")
            pool = cpp.build_pool(tmpdir, themes_py)
        self.assertEqual(
            list(pool),
            ["echarts/alpha", "echarts/zeta", "ppt_mcp/corporate_blue"],
        )
        # PPT chart series cycle over accent1..6 only; dark/light stay out.
        self.assertEqual(pool["ppt_mcp/corporate_blue"]["colors"][0], "#2B579A")
        self.assertEqual(len(pool["ppt_mcp/corporate_blue"]["colors"]), 6)


class CliTest(unittest.TestCase):
    def test_query_substring_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool_path = Path(tmp) / "pool.json"
            pool_path.write_text(
                json.dumps({"echarts/macarons": {"colors": ["#2ec7c9"]}}),
                encoding="utf-8",
            )
            code = cpp.main(["--pool", str(pool_path), "--query", "MACARON"])
        self.assertEqual(code, 0)

    def test_query_no_match_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool_path = Path(tmp) / "pool.json"
            pool_path.write_text("{}", encoding="utf-8")
            code = cpp.main(["--pool", str(pool_path), "--query", "nope"])
        self.assertEqual(code, 1)

    def test_missing_pool_file_fails_loudly(self):
        with self.assertRaises(SystemExit):
            cpp.main(["--pool", "/nonexistent/pool.json"])

    def test_aggregate_without_source_errors(self):
        with self.assertRaises(SystemExit):
            cpp.main(["--aggregate"])


class CommittedSnapshotTest(unittest.TestCase):
    def test_snapshot_loads_with_expected_sources(self):
        pool = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        echarts = [k for k in pool if k.startswith("echarts/")]
        ppt = [k for k in pool if k.startswith("ppt_mcp/")]
        self.assertEqual(len(echarts), 36)  # incl. v5.js theme (has colorPalette)
        self.assertEqual(len(ppt), 17)
        self.assertEqual(list(pool), sorted(pool))

    def test_snapshot_colors_all_pure_hex(self):
        pool = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        for name, entry in pool.items():
            for color in entry["colors"]:
                self.assertRegex(color, r"^#[0-9A-Fa-f]{6}$", msg=name)
            self.assertGreaterEqual(len(entry["colors"]), 6, msg=name)
            self.assertIn("source", entry)


if __name__ == "__main__":
    unittest.main()
