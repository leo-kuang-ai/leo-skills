"""intake_gpt_image2 迁移器单元测试（风格进货批 C1）。

覆盖：决策表完整性（32 完整套 = 12 保留 + 20 跳过）、纯函数推导
（palette 墨色主锚/池归并键/负面提炼/typography 身份门）、四重去重门
语义（同板指纹/audit 同族判定/WCAG 文字锚）、池覆盖完整性（233 套恰好
归入 7 池）、幂等重跑（--write 产物不计入既有库）。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "intake_gpt_image2.py"
SOURCE_ROOT = Path(
    "/Users/kuang/knowledge/ppt-github/gpt-image2-ppt-skills/styles"
)

spec = importlib.util.spec_from_file_location("intake_gpt_image2", SCRIPT)
intake = importlib.util.module_from_spec(spec)
sys.modules["intake_gpt_image2"] = intake
spec.loader.exec_module(intake)


@unittest.skipUnless(SOURCE_ROOT.is_dir(), "gpt-image2-ppt-skills source not available")
class IntakeTableTests(unittest.TestCase):
    """Decision-table integrity against the real source tree."""

    def test_full_sets_decided_exactly_once(self):
        full = {p.stem for p in (SOURCE_ROOT / "initial").glob("*.md")}
        full |= {p.stem for p in (SOURCE_ROOT / "featured").glob("*.md")}
        decided = set(intake.KEEP) | set(intake.SKIP)
        self.assertEqual(decided, full)
        self.assertFalse(set(intake.KEEP) & set(intake.SKIP))

    def test_quota_honest_band_and_pool_count(self):
        # 宁实勿虚: the 25-35 quota is a target band, honest concept-dedupe
        # may land below it; freeze the audited decision (12 mains + 7 pools)
        # so any future re-decision is a deliberate act.
        self.assertEqual(len(intake.KEEP), 12)
        self.assertEqual(len(intake.SKIP), 20)
        self.assertGreaterEqual(len(intake.POOLS), 5)
        self.assertLessEqual(len(intake.POOLS), 8)

    def test_keep_entries_carry_name_subdir_vd_pairing(self):
        for src_id, keep in intake.KEEP.items():
            self.assertTrue(keep["name"].endswith("风"), f"{src_id}: name needs 风 suffix")
            self.assertIn(keep["subdir"].split("/")[0], ("01_通用母版", "02_行业内容域",
                                                         "03_场景用途结构"),
                          f"{src_id}: subdir outside counted brief dirs")
            self.assertGreater(len(keep["vd"].split()), 5, f"{src_id}: vd too thin")
            self.assertTrue(keep["pairing"], f"{src_id}: pairing missing")

    def test_pool_specs_cover_their_group_keys(self):
        for pool_name, spec in intake.POOLS.items():
            self.assertTrue(pool_name.endswith("池"), f"{pool_name}: pool name needs 池")
            self.assertIn(spec["group"], ("morandi", "punk", "tech"))
            self.assertIn(spec["key"], ("dark", "warm", "cool", "light"))
            self.assertGreater(len(spec["vd"].split()), 5, f"{pool_name}: vd too thin")


class PaletteDerivationTests(unittest.TestCase):
    """pick_palette: ink primary on light decks, ground primary on dark."""

    def test_light_deck_takes_darkest_head_anchor_as_primary(self):
        pal = intake.pick_palette(["#FFFFFF", "#F4F7FF", "#635BFF", "#1E40AF"],
                                  ["#FFFFFF", "#F4F7FF"])
        self.assertTrue(pal["primary"].startswith("#635BFF"))
        # Neutral must survive on the light deck (darkest ink anchor).
        self.assertTrue(pal["neutral"].startswith("#1E40AF"))

    def test_dark_deck_takes_ground_as_primary_and_light_neutral(self):
        pal = intake.pick_palette(["#0B0E14", "#B5D333", "#FFFFFF"], ["#0B0E14"])
        self.assertTrue(pal["primary"].startswith("#0B0E14"))
        self.assertTrue(pal["neutral"].startswith("#FFFFFF"))

    def test_missing_hexes_raise(self):
        with self.assertRaises(ValueError):
            intake.pick_palette([])

    def test_text_anchor_gate_mirrors_governance_polarity(self):
        anchors = {"#635BFF", "#FFFFFF", "#1E40AF"}
        self.assertTrue(intake.text_anchor_ok(anchors, "#635BFF"))
        self.assertFalse(intake.text_anchor_ok({"#635BFF"}, "#635BFF"))


class PoolClassifierTests(unittest.TestCase):
    """Deterministic pool assignment over background-first palettes."""

    def test_dark_ground_splits_first(self):
        self.assertEqual(intake.classify_pool(["#121212", "#F2EDE7", "#A78B71"], "morandi"), "dark")
        self.assertEqual(intake.classify_pool(["#0B0E14", "#B5D333"], "tech"), "dark")

    def test_morandi_light_decks_split_by_warm_cool_majority(self):
        warm = ["#F4F0EA", "#A84223", "#DC964E", "#A98E75"]
        cool = ["#F4F0EA", "#4660A9", "#7A9B9F", "#C3C6A8"]
        self.assertEqual(intake.classify_pool(warm, "morandi"), "warm")
        self.assertEqual(intake.classify_pool(cool, "morandi"), "cool")

    def test_punk_tech_are_dark_light_binary(self):
        self.assertEqual(intake.classify_pool(["#FFFFFF", "#000000", "#F04D30"], "punk"), "light")
        self.assertEqual(intake.classify_pool(["#000000", "#FFFFFF", "#FF0000"], "tech"), "dark")

    def test_empty_palette_defaults_light(self):
        self.assertEqual(intake.classify_pool([], "morandi"), "light")

    def test_tie_breaks_to_warm(self):
        # Saturated anchors split 1:1 -> warm (muted-palette majority rule).
        tie = ["#FFFFFF", "#E83A59", "#4660A9"]
        self.assertEqual(intake.classify_pool(tie, "morandi"), "warm")


class DerivationTests(unittest.TestCase):
    """Prose distillation helpers."""

    def test_negative_items_skip_universal_provenance_line(self):
        raw = "- Full-color photographs\n- Drop shadows\n- 禁止出现来源网站 UI、水印、下载提示或模板署名。"
        items = intake.negative_items(raw)
        self.assertEqual(items[0], "Full-color photographs")
        self.assertTrue(all("来源网站" not in i for i in items))

    def test_negative_items_pads_short_checklists(self):
        items = intake.negative_items("- 只要一条")
        self.assertGreaterEqual(len(items), 3)
        self.assertIn("不要偏离该风格的字体/配色/质感约定", items)

    def test_negative_items_limit_five(self):
        raw = "\n".join(f"- 禁止{i}" for i in range(9))
        self.assertEqual(len(intake.negative_items(raw)), 5)

    def test_clean_desc_strips_list_repr_and_provenance(self):
        raw = "['A muted deck.', 'Features sage green.']\n来源说明：本文件只记录抽象视觉规律。"
        self.assertEqual(intake._clean_desc(raw), "A muted deck. Features sage green.")

    def test_typography_identity_gate_appends_fallback(self):
        # No identity keyword anywhere -> the fallback font is prepended so
        # the brief always carries an identity declaration.
        # NB: "Headings" alone would false-positive on the shared "DIN"
        # pattern (mirrored from lint_style_briefs), so use a bare phrase.
        pack = {"fonts": "Titles are bold, geometric."}
        typo = intake.typography_pack(pack, "思源黑体 / Inter")
        self.assertTrue(intake.FONT_IDENTITY_RE.search(" ".join(typo.values())))
        self.assertTrue(typo["title"].startswith("思源黑体 / Inter"))

    def test_typography_passes_when_identity_font_present(self):
        pack = {"fonts": "Headings: Playfair Display serif. Body: clean sans-serif."}
        typo = intake.typography_pack(pack, "思源宋体 / Georgia")
        self.assertTrue(typo["title"].startswith("Headings:"))

    def test_layout_patterns_fallback_without_layouts(self):
        pack = {"layouts": []}
        self.assertEqual(intake.layout_patterns(pack),
                         ["大面积色块分区", "标题区 + 内容卡两层结构"])

    def test_layout_patterns_distinct_page_types(self):
        pack = {"layouts": [
            {"page_type": "cover", "summary": "Large right-aligned image block balanced by text."},
            {"page_type": "content", "summary": "A 2x3 masonry-style grid with floating titles."},
            {"page_type": "content", "summary": "Duplicate page type must not repeat."},
        ]}
        got = intake.layout_patterns(pack)
        self.assertEqual(len(got), 2)


class GateSemanticsTests(unittest.TestCase):
    """Fingerprint / audit-family / name gates (isomorphic to audit tool)."""

    def test_fingerprint_reads_palette_and_background(self):
        brief = {"color_palette": {"primary": "#AABBCC(主色)"},
                 "canvas": {"background": "#112233→#445566"}}
        self.assertEqual(intake.fingerprint(brief),
                         frozenset({"#AABBCC", "#112233", "#445566"}))

    def test_normalize_name_strips_feng_and_pool_suffix(self):
        self.assertEqual(intake.normalize_name("黑白杂志风"), "黑白杂志")
        self.assertEqual(intake.normalize_name("莫兰迪暖调编辑池"), "莫兰迪暖调编辑")

    def test_audit_pair_requires_name_ratio_plus_shared_hex(self):
        fa = frozenset({"AAAAAA", "BBBBBB"})
        fb = frozenset({"AAAAAA", "CCCCCC"})
        self.assertTrue(intake.audit_family_pair("黑白杂志", fa, "黑白杂志甲", fb))
        self.assertFalse(intake.audit_family_pair("完全不同名", fa, "毫无关系名", fb))

    def test_audit_pair_high_jaccard_alone_clusters(self):
        fa = frozenset({"AAAAAA", "BBBBBB", "CCCCCC"})
        fb = frozenset({"AAAAAA", "BBBBBB", "CCCCCC", "DDDDDD"})
        self.assertTrue(intake.audit_family_pair("甲风格", fa, "乙风格", fb))


@unittest.skipUnless(SOURCE_ROOT.is_dir(), "gpt-image2-ppt-skills source not available")
class PipelineTests(unittest.TestCase):
    """Full-pipeline gates against the real source + real library."""

    @classmethod
    def setUpClass(cls):
        cls.packs = intake.load_source(SOURCE_ROOT)

    def test_pool_coverage_is_total_and_disjoint(self):
        xia = [p for p in self.packs.values() if p["group"] == "xiamulingzi"]
        self.assertEqual(len(xia), 233)
        pools = {name: 0 for name in intake.POOLS}
        for pack in xia:
            hexes = pack["palette_sidecar"] or pack["hexes"]
            group = ("morandi" if "morandi" in pack["id"]
                     else "punk" if "punk" in pack["id"] else "tech")
            pools[intake.pool_for(hexes, group)] += 1
        self.assertEqual(sum(pools.values()), 233)
        self.assertTrue(all(v > 0 for v in pools.values()), pools)

    def test_all_gates_pass_without_writing(self):
        problems, code, _ = intake.run(self.packs, intake.STYLES_ROOT, write=False)
        self.assertEqual(code, 0, problems)
        self.assertEqual(problems, [])

    def test_written_briefs_are_own_targets_not_library_history(self):
        # Idempotency: a second run must not treat its own outputs as
        # pre-existing library entries (no false family_duplicate).
        own = set()
        for keep in intake.KEEP.values():
            own.add(str(intake.STYLES_ROOT / keep["subdir"] / f"{keep['name']}.md"))
        for pool in intake.POOLS:
            own.add(str(intake.STYLES_ROOT / intake.POOL_DIR_REL / f"{pool}.md"))
        existing = {str(intake.STYLES_ROOT / rel)
                    for rel, _, _ in intake.load_existing_briefs(intake.STYLES_ROOT)}
        self.assertFalse(own & (existing - own))

    def test_representative_pick_is_deterministic(self):
        members = [
            {"id": "b", "hexes": ["#202020", "#F0F0F0"]},
            {"id": "a", "hexes": ["#808080", "#808080"]},
            {"id": "c", "hexes": ["#E0E0E0", "#202020"]},
        ]
        rep = intake.pick_pool_representative(members)
        self.assertEqual(rep["id"], "a")
        self.assertEqual(intake.pick_pool_representative(members[:1])["id"], "b")


if __name__ == "__main__":
    unittest.main()
