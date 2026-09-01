"""intake_ohmy 迁移器单元测试（风格进货批 S1a）。

覆盖：决策表完整性（74 = 49 保留 + 25 跳过）、纯函数推导（名称/palette
角色/负面提炼/typography 身份门）、去重门语义（同板指纹/同族判定/变体
豁免）、幂等重跑（--write 产物不计入既有库）。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "intake_ohmy.py"
SOURCE_ROOT = Path(
    "/Users/kuang/knowledge/ppt-github/oh-my-ppt/resources/styles"
)

spec = importlib.util.spec_from_file_location("intake_ohmy", SCRIPT)
intake = importlib.util.module_from_spec(spec)
sys.modules["intake_ohmy"] = intake
spec.loader.exec_module(intake)


def _pack(name: str) -> dict:
    return intake.parse_pack(SOURCE_ROOT / name)


@unittest.skipUnless(SOURCE_ROOT.is_dir(), "oh-my-ppt source not available")
class IntakeTableTests(unittest.TestCase):
    """Decision-table integrity against the real source tree."""

    def test_decisions_cover_every_source_pack_exactly_once(self):
        packs = {d.name for d in SOURCE_ROOT.iterdir() if d.is_dir()}
        decided = set(intake.KEEP) | set(intake.SKIP)
        self.assertEqual(decided, packs)
        self.assertFalse(set(intake.KEEP) & set(intake.SKIP))

    def test_quota_band_45_to_55_new_top_level_styles(self):
        variants = sum(1 for k in intake.KEEP.values() if k.get("variant_of"))
        self.assertGreaterEqual(len(intake.KEEP) - variants, 45)
        self.assertLessEqual(len(intake.KEEP) - variants, 55)

    def test_keep_entries_carry_name_subdir_vd_pairing(self):
        for src_id, keep in intake.KEEP.items():
            self.assertTrue(keep["name"].endswith("风"), f"{src_id}: name needs 风 suffix")
            self.assertTrue(keep["subdir"], f"{src_id}: subdir missing")
            self.assertGreater(len(keep["vd"].split()), 5, f"{src_id}: vd too thin")
            self.assertTrue(keep["pairing"], f"{src_id}: pairing missing")

    def test_variant_targets_are_kept_primaries(self):
        names = {k["name"] for k in intake.KEEP.values()}
        for keep in intake.KEEP.values():
            target = keep.get("variant_of")
            if target:
                self.assertIn(target, names)
        book = intake.variants_by_primary()
        self.assertEqual(set(book.get("凝脂杨妃风", [])), {"米白樱粉风"})
        self.assertIsNone(intake.variants_declaration("极光风"))


class DerivationTests(unittest.TestCase):
    """Pure derivation helpers."""

    def test_derive_name_appends_feng_and_strips_qualifier(self):
        self.assertEqual(intake.derive_name("水墨江南"), "水墨江南风")
        self.assertEqual(intake.derive_name("中国传统色·凝脂杨妃"), "中国传统色风")
        self.assertEqual(intake.derive_name("Y2K 铬"), "Y2K铬风")
        self.assertEqual(intake.derive_name("极简"), "极简风")

    def test_negative_items_keeps_source_prohibitions_verbatim(self):
        raw = "- 不要使用非等宽字体\n- 不要使用彩色（保持纯绿）\n- 不要丢掉暗色背景"
        items = intake.negative_items(raw)
        self.assertEqual(items[0], "不要使用非等宽字体")
        self.assertTrue(all(item.startswith("不要") for item in items))
        self.assertLessEqual(len(items), 5)

    def test_negative_items_pads_short_checklists(self):
        items = intake.negative_items("- 只有一条禁令")
        self.assertEqual(len(items), 3)

    def test_typography_identity_injected_when_source_has_none(self):
        pack = {"typography": "标题清晰但不刺眼。正文保持对比度。", "layout": "", "hexes": [], "bg": []}
        keep = {"subdir": "终端配色"}
        typo = intake.typography_pack(pack, keep)
        self.assertIn("等宽", "".join(typo.values()))
        self.assertNotEqual(typo["body"], typo["title"])

    def test_pick_palette_assigns_all_four_roles_with_hex(self):
        pack = _pack("dracula")
        palette = intake.pick_palette(pack)
        for role in ("primary", "secondary", "accent", "neutral"):
            self.assertRegex(palette[role], r"#[0-9A-Fa-f]{6}")

    def test_pick_palette_neutral_contrasts_against_primary(self):
        pack = _pack("terminal-green")
        palette = intake.pick_palette(pack)
        anchors = intake.palette_anchors(palette, pack["bg"])
        primary = intake.HEX_RE.search(palette["primary"]).group(0)
        self.assertTrue(intake.text_anchor_ok(anchors, primary))

    def test_parse_pack_reads_font_section_fallback(self):
        pack = _pack("palace-ink-red")  # uses ## 字体 instead of ## 排版
        self.assertIn("黑体", pack["typography"])
        self.assertTrue(pack["hexes"])

    def test_parse_pack_reads_dont_do_section_fallback(self):
        pack = _pack("hand-drawn-autumn")  # uses ## 不要做 instead of ## 不要
        self.assertTrue(pack["negative"].strip())


class GateTests(unittest.TestCase):
    """Dedupe-gate semantics on synthetic briefs."""

    def test_audit_family_pair_rules(self):
        fp_a = frozenset({"#111111", "#222222", "#333333"})
        fp_b = frozenset({"#111111", "#444444", "#555555"})
        fp_c = frozenset({"#666666", "#777777", "#888888"})
        # name_ratio >= 0.62 + one shared hex clusters (扁平 vs 半扁平 -> 0.8).
        self.assertTrue(intake.audit_family_pair("扁平风", fp_a, "半扁平风", fp_b))
        # Similar-but-soft names (ratio 0.5) without palette overlap stay apart.
        self.assertFalse(intake.audit_family_pair("水墨江南风", fp_a, "水墨禅意风", fp_c))
        # Unrelated name without palette overlap does not.
        self.assertFalse(intake.audit_family_pair("极光风", fp_a, "极简风", fp_c))
        # Jaccard >= 0.6 clusters regardless of name.
        fp_d = frozenset({"#111111", "#222222", "#333333", "#999999"})
        self.assertTrue(intake.audit_family_pair("甲风", fp_a, "乙风", fp_d))

    def test_fingerprint_covers_palette_and_canvas_bg(self):
        brief = {
            "color_palette": {"primary": "a #AABBCC", "accent": "b #DDEEFF"},
            "canvas": {"background": "#001122 gradient"},
        }
        self.assertEqual(intake.fingerprint(brief), frozenset({"#AABBCC", "#DDEEFF", "#001122"}))

    def test_normalize_name_strips_feng_suffixes(self):
        self.assertEqual(intake.normalize_name("商业计划书风"), "商业计划书")
        self.assertEqual(intake.normalize_name("党政红风格"), "党政红")


@unittest.skipUnless(SOURCE_ROOT.is_dir(), "oh-my-ppt source not available")
class PipelineTests(unittest.TestCase):
    """End-to-end gate run against the real source + library."""

    @classmethod
    def setUpClass(cls):
        packs = {d.name: intake.parse_pack(d) for d in sorted(SOURCE_ROOT.iterdir()) if d.is_dir()}
        cls.packs = packs
        cls.problems, cls.code = intake.run(packs, write=False)

    def test_gate_passes_on_current_library(self):
        self.assertEqual(self.code, 0, msg="; ".join(self.problems))

    def test_written_files_exist_and_parse(self):
        variant_names = {k["name"] for k in intake.KEEP.values() if k.get("variant_of")}
        for src_id, keep in sorted(intake.KEEP.items()):
            path = intake.target_path(keep)
            self.assertTrue(path.is_file(), f"{src_id}: {path} missing")
            brief, _ = intake.build_brief(self.packs[src_id], keep)
            self.assertEqual(brief["style_name"], keep["name"])
            if keep["name"] in variant_names:
                self.assertEqual(brief.get("variant_of"), keep["variant_of"])
            elif keep["name"] in intake.VARIANT_NOTES:
                declared = {item.split(":")[0] for item in brief.get("variants", [])}
                self.assertTrue(
                    declared & variant_names,
                    f"{src_id}: primary misses variant declaration",
                )

    def test_written_briefs_match_regenerated_content(self):
        # Idempotency: files on disk equal what a fresh run would write.
        for src_id, keep in sorted(intake.KEEP.items()):
            pack = self.packs[src_id]
            brief, _ = intake.build_brief(
                pack, keep, variants_declared=intake.variants_declaration(keep["name"])
            )
            expected = intake.render_markdown(brief, keep["subdir"], pack)
            self.assertEqual(
                intake.target_path(keep).read_text(encoding="utf-8"), expected,
                f"{src_id}: drift between script and committed file",
            )


if __name__ == "__main__":
    unittest.main()
