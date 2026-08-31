#!/usr/bin/env python3
"""extract_pptx_theme.py（B4）边界测试：rels 链解析、clrMap 非默认变体、
schemeClr+lumMod 修饰、Office 字体映射 16 条、中文未映射字体标注、
键排序确定性无时间戳、缺 theme 清晰失败 exit 1。fixture 为
tests/fixtures/theme/mixed.pptx（clrMap 反转 + sysClr/srgbClr 混合 +
中文字体 + 多巨标色）。"""
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
EXTRACTOR = SCRIPTS / "extract_pptx_theme.py"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "theme" / "mixed.pptx"

sys.path.insert(0, str(SCRIPTS))
from extract_pptx_theme import (  # noqa: E402
    OFFICE_FONT_MAP, apply_color_modifiers,
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(EXTRACTOR), *args],
        capture_output=True, text=True,
    )


class ExtractPptxThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = run(str(FIXTURE))
        cls.result = json.loads(cls.proc.stdout)

    def test_resolves_theme_via_relationship_chain(self):
        self.assertEqual(self.proc.returncode, 0)
        # rels 链解析成功：12 slot 中 accent1 走 srgbClr、dk1 走 sysClr。
        self.assertEqual(self.result["roles"]["primary"]["hex"], "#173B5B")
        # 背景：slide bg schemeClr bg1 → clrMap bg1→dk1 → sysClr lastClr。
        self.assertEqual(self.result["background"]["hex"], "#1F2A44")
        self.assertEqual(self.result["background"]["derived_from"],
                         "slide bg top(1 处)")

    def test_clrmap_non_default_variant(self):
        # clrMap bg1→dk1 / tx1→lt1（反转）：neutral 回退取 clrMap tx1 = lt1 白。
        self.assertEqual(self.result["roles"]["neutral"]["hex"], "#FFFFFF")

    def test_scheme_color_with_lum_mod_applied(self):
        # shape fill schemeClr accent1(#1F4E79) + lumMod 75000 → HSL 亮度 ×0.75。
        self.assertEqual(
            apply_color_modifiers("#1F4E79", [("lumMod", 75000)]),
            self.result["roles"]["primary"]["hex"],
        )

    def test_office_font_map_sixteen_entries(self):
        self.assertEqual(len(OFFICE_FONT_MAP), 16)
        self.assertEqual(OFFICE_FONT_MAP["Calibri"], "Inter")
        self.assertEqual(OFFICE_FONT_MAP["Calibri Light"], "Inter")
        # fixture 的 heading 字体 Calibri Light 命中映射并登记 applied。
        self.assertEqual(
            self.result["fonts"]["heading"],
            {"raw": "Calibri Light", "mapped": "Inter", "source": "slide scan"},
        )
        self.assertIn("Calibri Light→Inter",
                      self.result["office_font_map_applied"])

    def test_chinese_font_unmapped_flagged(self):
        body = self.result["fonts"]["body"]
        self.assertEqual(body["raw"], "思源黑体")
        self.assertIsNone(body["mapped"])
        self.assertEqual(body["note"], "生图后端可用性需样张验证")

    def test_deterministic_sorted_keys_no_timestamp(self):
        second = run(str(FIXTURE))
        self.assertEqual(second.returncode, 0)
        self.assertEqual(self.proc.stdout, second.stdout)
        self.assertNotIn("timestamp", self.proc.stdout.lower())
        self.assertNotIn("generated_at", self.proc.stdout.lower())
        # 源指纹在场（CI-2 可哈希锚点）。
        self.assertRegex(self.result["source_pptx_sha256"], r"^[0-9a-f]{64}$")

    def test_role_overrides_only_use_color_channel(self):
        # HEX 只走 --color 覆盖通道：suggested_overrides 全部是 --color 形态。
        for line in self.result["suggested_overrides"]:
            self.assertRegex(
                line,
                r"^--color (primary|secondary|accent|neutral)=#[0-9A-F]{6}$",
            )

    def test_missing_theme_fails_loud_exit_one(self):
        # 构造去 theme 的包（rels 链指向的 theme 目标缺失）。
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            broken = Path(td) / "no-theme.pptx"
            with zipfile.ZipFile(FIXTURE) as src, \
                    zipfile.ZipFile(broken, "w") as dst:
                for name in src.namelist():
                    if name == "ppt/theme/theme1.xml":
                        continue
                    dst.writestr(name, src.read(name))
            proc = run(str(broken))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("theme_missing", proc.stderr)
            self.assertIn("清晰失败", proc.stderr)  # 不静默降级

    def test_not_a_zipfile_exits_two(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            junk = Path(td) / "junk.pptx"
            junk.write_bytes(b"not a zip")
            proc = run(str(junk))
            self.assertEqual(proc.returncode, 2)

    def test_missing_file_exits_two(self):
        proc = run("/nonexistent.pptx")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
