"""intake_codex_xiaobei 迁移器单元测试（风格进货批 S2b）。

覆盖：两源净增数与去重登记（22 卡 = 21 收 + 1 跳过；15 品牌 = 14 收 +
1 跳过）、生成文件的结构合同（08 轴 paste-ready 段落 + 来源许可节、
10 轴 verified_at 与字段可解析性）、在盘文件与内嵌数据零漂移（--check
语义）、load_brand 的主/强调色取序。
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "intake_codex_xiaobei.py"
RENDER_DIR = SKILL_DIR / "references" / "styles" / "08_图片渲染"
BRAND_DIR = SKILL_DIR / "references" / "styles" / "10_品牌身份"

spec = importlib.util.spec_from_file_location("intake_codex_xiaobei", SCRIPT)
intake = importlib.util.module_from_spec(spec)
sys.modules["intake_codex_xiaobei"] = intake
spec.loader.exec_module(intake)


class DecisionTableTests(unittest.TestCase):
    """两源配额与去重登记。"""

    def test_22_community_cards_yield_21_new_renders_1_dedup(self):
        self.assertEqual(len(intake.RENDER_CARDS), 21)
        self.assertEqual(len(intake.RENDER_SKIPPED), 1)
        self.assertEqual(intake.RENDER_SKIPPED[0][0], "nb-chalkboard-lesson")

    def test_14_net_new_brands_with_ibm_deduped(self):
        self.assertEqual(len(intake.BRANDS), 14)
        names = {b["file"] for b in intake.BRANDS}
        self.assertNotIn("ibm.md", names)
        self.assertEqual(
            names,
            {"airbnb.md", "apple.md", "bmw.md", "figma.md", "framer.md",
             "linear.md", "notion.md", "shopify.md", "spotify.md",
             "starbucks.md", "stripe.md", "supabase.md", "tesla.md",
             "vercel.md"},
        )

    def test_render_files_do_not_collide_with_preexisting_axis_entries(self):
        preexisting = {
            "矢量插画", "扁平几何", "瑞士极简", "玻璃拟态", "3D 等距",
            "数字仪表盘", "企业摄影", "工程蓝图", "杂志编辑", "手绘笔记",
            "水墨笔记", "黑板粉笔", "剪纸层叠", "水彩晕染", "暖光场景",
            "丝网印刷", "复古海报", "幻想动画", "像素复古", "自然有机",
        }
        stems = {Path(c["file"]).stem for c in intake.RENDER_CARDS}
        self.assertFalse(stems & preexisting)
        self.assertEqual(len(stems), 21)

    def test_render_groups_are_known_axis_buckets(self):
        buckets = {"现代商业", "手绘教育", "叙事氛围", "特色"}
        for card in intake.RENDER_CARDS:
            self.assertIn(card["group"], buckets)


class GeneratedContractTests(unittest.TestCase):
    """生成文件的结构合同（对在盘产物断言，防手改漂移）。"""

    def test_check_mode_reports_all_files_in_sync(self):
        self.assertEqual(intake.main(["--check"]), 0)

    def test_every_render_file_carries_guardrail_and_license(self):
        for card in intake.RENDER_CARDS:
            text = (RENDER_DIR / card["file"]).read_text(encoding="utf-8")
            self.assertIn(f"08_图片渲染 · {card['group']}", text)
            self.assertIn("## 1. 风格段落", text)
            self.assertIn("Rendering guardrails: no text", text)
            self.assertIn("16:9", text)
            self.assertIn("## 2. 线条 · 纹理 · 深度", text)
            self.assertIn("## 3. 来源与许可", text)
            self.assertIn(card["url"], text)
            self.assertIn("CC BY 4.0", text)
            for role, _ in card["ltd"]:
                self.assertIn(role, text)

    def test_render_style_paragraph_is_single_blockquote(self):
        for card in intake.RENDER_CARDS:
            text = (RENDER_DIR / card["file"]).read_text(encoding="utf-8")
            section = text.split("## 1. 风格段落", 1)[1].split("## 2.", 1)[0]
            quotes = [l for l in section.splitlines() if l.strip().startswith(">")]
            self.assertEqual(len(quotes), 1, card["file"])

    def test_every_brand_file_declares_verified_at_and_fields(self):
        for brand in intake.BRANDS:
            text = (BRAND_DIR / brand["file"]).read_text(encoding="utf-8")
            self.assertIn("**分类:** 10_品牌身份", text)
            self.assertIn("verified_at: 未核验", text)
            for field in ("语气：", "字体：", "氛围：", "暗场变体：", "使用边界："):
                self.assertIn(field, text, f"{brand['file']} missing {field}")
            # dark-deck preset vocabulary must be referenced for dark routing.
            self.assertIn("dark-deck", text)

    def test_brand_first_two_hexes_are_primary_then_accent(self):
        for brand in intake.BRANDS:
            text = (BRAND_DIR / brand["file"]).read_text(encoding="utf-8")
            hexes = re.findall(r"#[0-9A-Fa-f]{6}", text)
            self.assertEqual(hexes[0], brand["primary"], brand["file"])
            self.assertEqual(hexes[1], brand["accent"], brand["file"])

    def test_brand_files_load_via_runtime_contract(self):
        runtime_src = SKILL_DIR / "runtime" / "src"
        self.assertTrue((runtime_src / "leo_ppt_generator" / "templates.py").is_file())
        for brand in intake.BRANDS:
            path = BRAND_DIR / brand["file"]
            text = path.read_text(encoding="utf-8")
            # Mirror templates._field / _HEX_ANCHOR_RE expectations.
            m = re.search(r"- 字体：(.*)", text)
            self.assertTrue(m and m.group(1).strip(), brand["file"])
            m = re.search(r"- 语气：(.*)", text)
            self.assertTrue(m and m.group(1).strip(), brand["file"])


class DedupLedgerTests(unittest.TestCase):
    """去重台账与生态同源性说明。"""

    def test_skipped_card_maps_to_existing_axis_entry(self):
        _, target, reason = intake.RENDER_SKIPPED[0]
        self.assertTrue((RENDER_DIR / f"{target}.md").is_file())
        self.assertTrue(reason)

    def test_all_cards_share_nano_banana_license_ledger(self):
        self.assertEqual(intake.NANO_SOURCE["license"], "CC BY 4.0")
        self.assertIn("awesome-nano-banana-pro-prompts", intake.NANO_SOURCE["license_url"])


if __name__ == "__main__":
    unittest.main()
