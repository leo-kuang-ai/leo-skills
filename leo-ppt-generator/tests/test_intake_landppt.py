"""intake_landppt 迁移器单元测试（风格进货批 S2a）。

覆盖：决策表完整性（25 = 6 保留 + 19 跳过）、价值精选配额带（净 6-8）、
锚点来源纪律（HEX 必须能在源 CSS 找到出处，含 %23/rgba 解码）、
场景/别名推导不重复、去重门语义复用（S1a 同构）、幂等重跑
（--write 产物不计入既有库）与盘上文件与脚本再生成一致。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "intake_landppt.py"
SOURCE_ROOT = Path("/Users/kuang/knowledge/ppt-github/LandPPT/template_examples")

spec = importlib.util.spec_from_file_location("intake_landppt", SCRIPT)
intake = importlib.util.module_from_spec(spec)
sys.modules["intake_landppt"] = intake
spec.loader.exec_module(intake)


def _pack(name: str) -> dict:
    return intake.parse_pack(SOURCE_ROOT / name)


@unittest.skipUnless(SOURCE_ROOT.is_dir(), "LandPPT source not available")
class IntakeTableTests(unittest.TestCase):
    """Decision-table integrity against the real source tree."""

    def test_decisions_cover_every_source_template_exactly_once(self):
        files = {p.name for p in SOURCE_ROOT.glob("*.json")}
        decided = set(intake.KEEP) | set(intake.SKIP)
        self.assertEqual(decided, files)
        self.assertFalse(set(intake.KEEP) & set(intake.SKIP))

    def test_quota_band_6_to_8_curated_new_styles(self):
        self.assertGreaterEqual(len(intake.KEEP), 6)
        self.assertLessEqual(len(intake.KEEP), 8)

    def test_two_new_subfamilies_declared(self):
        subdirs = {k["subdir"] for k in intake.KEEP.values()}
        self.assertIn("中式载体", subdirs)
        self.assertIn("印象派油画", subdirs)
        carriers = [k["name"] for k in intake.KEEP.values() if k["subdir"] == "中式载体"]
        impressionists = [k["name"] for k in intake.KEEP.values() if k["subdir"] == "印象派油画"]
        self.assertEqual(sorted(carriers), ["中式书卷风", "宣纸风", "竹简风"])
        self.assertEqual(sorted(impressionists), ["星月夜风", "莫奈风"])

    def test_keep_entries_carry_name_subdir_vd_pairing(self):
        for src_id, keep in intake.KEEP.items():
            self.assertTrue(keep["name"].endswith("风"), f"{src_id}: name needs 风 suffix")
            self.assertTrue(keep["subdir"], f"{src_id}: subdir missing")
            self.assertGreater(len(keep["vd"].split()), 5, f"{src_id}: vd too thin")
            self.assertTrue(keep["pairing"], f"{src_id}: pairing missing")
            self.assertEqual(set(keep["anchors"]), {"primary", "secondary", "accent", "neutral"})

    def test_skip_entries_map_to_real_leo_concepts(self):
        # Spot anchors of the concept dedupe (S1a 同纪律): terminal/cyberpunk/
        # sunset are the highest-risk duplicate families in this source.
        self.assertEqual(intake.SKIP["终端风.json"]["leo"], "终端命令行风")
        self.assertEqual(intake.SKIP["赛博朋克风.json"]["leo"], "荧光高对比科技风")
        self.assertEqual(intake.SKIP["日落大道.json"]["leo"], "日落暖风")
        self.assertEqual(intake.SKIP["星月蓝.json"]["leo"], "星月夜风")


class AnchorProvenanceTests(unittest.TestCase):
    """Source-fidelity: curated anchors must trace back to the CSS tokens."""

    def test_rgba_and_encoded_hex_decoded_into_anchor_pool(self):
        # 宣纸风 accent #C8A064 exists only as rgba(200,160,100,.15).
        pack = _pack("宣纸风.json")
        self.assertIn("#C8A064", pack["anchors"])
        # 吉卜力风 secondary #A3B8A1 exists only as %23a3b8a1 in an SVG URI.
        pack = _pack("吉卜力风.json")
        self.assertIn("#A3B8A1", pack["anchors"])

    def test_transparent_rgba_not_promoted_to_anchor(self):
        anchors = intake.source_anchors("rgba(255, 255, 255, 0.02)")
        self.assertNotIn("#FFFFFF", anchors)
        anchors = intake.source_anchors("rgba(10, 20, 30, 0.5)")
        self.assertIn("#0A141E", anchors)

    def test_every_brief_anchor_provable_against_source(self):
        for src_id, keep in intake.KEEP.items():
            pack = _pack(src_id)
            brief, bg_hexes = intake.build_brief(keep, pack)
            provenance = pack["anchors"]
            for role in ("primary", "secondary", "accent", "neutral"):
                hexm = intake.HEX_RE.search(brief["color_palette"][role]).group(0)
                self.assertIn(hexm.upper(), provenance, f"{src_id}.{role} {hexm}")
            for hexm in bg_hexes:
                self.assertIn(hexm.upper(), provenance, f"{src_id} bg {hexm}")


class DerivationTests(unittest.TestCase):
    """Pure derivation helpers."""

    def test_aliases_deduped_and_keep_source_stem(self):
        brief, _ = intake.build_brief(intake.KEEP["竹简风.json"], _pack("竹简风.json"))
        self.assertEqual(brief["aliases"][0], "竹简风")
        self.assertEqual(len(brief["aliases"]), len(set(brief["aliases"])))
        self.assertIn("bamboo slip", brief["aliases"])

    def test_best_for_carries_single_scene_suffix(self):
        brief, _ = intake.build_brief(intake.KEEP["莫奈风.json"], _pack("莫奈风.json"))
        self.assertEqual(brief["best_for"].count("适合"), 1)
        self.assertTrue(brief["best_for"].endswith("艺术赏析/文化活动/品牌美学"))

    def test_dark_and_light_decks_both_have_wcag_anchor(self):
        for src_id, keep in intake.KEEP.items():
            brief, bg_hexes = intake.build_brief(keep, _pack(src_id))
            anchors = intake.ohmy.palette_anchors(brief["color_palette"], bg_hexes)
            primary = intake.HEX_RE.search(brief["color_palette"]["primary"]).group(0)
            self.assertTrue(
                intake.ohmy.text_anchor_ok(anchors, primary), f"{src_id}: no WCAG text anchor"
            )

    def test_typography_identity_font_declared(self):
        for keep in intake.KEEP.values():
            joined = " ".join(str(v) for v in keep["typo"].values())
            self.assertTrue(
                intake.ohmy.FONT_IDENTITY_RE.search(joined),
                f"{keep['name']}: typography lacks identity font",
            )


@unittest.skipUnless(SOURCE_ROOT.is_dir(), "LandPPT source not available")
class PipelineTests(unittest.TestCase):
    """End-to-end gate run against the real source + library."""

    @classmethod
    def setUpClass(cls):
        packs = {p.name: intake.parse_pack(p) for p in sorted(SOURCE_ROOT.glob("*.json"))}
        cls.packs = packs
        cls.problems, cls.code = intake.run(packs, write=False)

    def test_gate_passes_on_current_library(self):
        self.assertEqual(self.code, 0, msg="; ".join(self.problems))

    def test_written_files_exist_and_parse(self):
        for src_id, keep in sorted(intake.KEEP.items()):
            path = intake.target_path(keep)
            self.assertTrue(path.is_file(), f"{src_id}: {path} missing")
            brief, _ = intake.build_brief(keep, self.packs[src_id])
            self.assertEqual(brief["style_name"], keep["name"])

    def test_written_briefs_match_regenerated_content(self):
        # Idempotency: files on disk equal what a fresh run would write.
        for src_id, keep in sorted(intake.KEEP.items()):
            brief, _ = intake.build_brief(keep, self.packs[src_id])
            expected = intake.render_markdown(brief, keep["subdir"], self.packs[src_id])
            self.assertEqual(
                intake.target_path(keep).read_text(encoding="utf-8"), expected,
                f"{src_id}: drift between script and committed file",
            )


if __name__ == "__main__":
    unittest.main()
