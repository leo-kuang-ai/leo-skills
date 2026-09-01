"""intake_yixue_kimi 迁移器单元测试（风格进货批 S3 终批）。

覆盖：决策表完整性（yixue 19 = 13 保留 + 6 跳过；open-kimi 30 = 3 保留
+ 27 跳过）、价值精选配额带（本批净增 14-18，实测 16）、医疗域加密落位
（新条目全部 02_行业内容域/医疗健康）、锚点来源纪律（HEX 必须能在源文件
原文找到出处）、场景/别名推导不重复、去重门语义复用（S1a/S2a 同构）、
continuity/asset_embedding 不迁契约、幂等重跑（--write 产物不计入既有库）
与盘上文件与脚本再生成一致。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "intake_yixue_kimi.py"
YIXUE_ROOT = Path("/Users/kuang/knowledge/ppt-github/yixueAIganhuo-PPT/references")
KIMI_ROOT = Path(
    "/Users/kuang/knowledge/ppt-github/open-kimi-ppt-skill/skills/"
    "open-kimi-ppt/reference/design_system"
)

spec = importlib.util.spec_from_file_location("intake_yixue_kimi", SCRIPT)
intake = importlib.util.module_from_spec(spec)
sys.modules["intake_yixue_kimi"] = intake
spec.loader.exec_module(intake)

MEDICAL_CATEGORY = SKILL_DIR / "references" / "styles" / "02_行业内容域" / "医疗健康"


def _yixue_pack(name: str) -> dict:
    return intake.parse_yixue(YIXUE_ROOT / name)


def _kimi_pack(rel: str) -> dict:
    parts = rel.split("/")
    return intake.parse_kimi(KIMI_ROOT.joinpath(*parts))


class IntakeTableTests(unittest.TestCase):
    """Decision-table integrity (source availability checked per class)."""

    @unittest.skipUnless(YIXUE_ROOT.is_dir(), "yixue source not available")
    def test_yixue_decisions_cover_every_source_exactly_once(self):
        files = {p.name for p in YIXUE_ROOT.glob("[0-9]*.json")}
        decided = set(intake.MEDICAL_KEEP) | set(intake.MEDICAL_SKIP)
        self.assertEqual(decided, files)
        self.assertFalse(set(intake.MEDICAL_KEEP) & set(intake.MEDICAL_SKIP))

    @unittest.skipUnless(KIMI_ROOT.is_dir(), "open-kimi source not available")
    def test_kimi_decisions_cover_every_signature_system_exactly_once(self):
        sources = {
            f"{group.name}/{d.name}"
            for group in KIMI_ROOT.iterdir() if group.is_dir()
            for d in group.iterdir() if d.is_dir() and (d / "design.md").is_file()
        }
        decided = set(intake.KIMI_KEEP) | set(intake.KIMI_SKIP)
        self.assertEqual(decided, sources)
        self.assertFalse(set(intake.KIMI_KEEP) & set(intake.KIMI_SKIP))

    def test_quota_band_net_14_to_18_curated_new_styles(self):
        net = len(intake.MEDICAL_KEEP) + len(intake.KIMI_KEEP)
        self.assertGreaterEqual(net, 14)
        self.assertLessEqual(net, 18)

    def test_medical_band_12_to_14_and_all_under_medical_category(self):
        self.assertGreaterEqual(len(intake.MEDICAL_KEEP), 12)
        self.assertLessEqual(len(intake.MEDICAL_KEEP), 14)
        for keep in intake.MEDICAL_KEEP.values():
            self.assertTrue(intake.yixue_target(keep).parent == MEDICAL_CATEGORY)

    def test_survey_directions_present(self):
        # 勘察指认的净新方向（青蓝水墨/暖陶土/秋叶麦田水彩/书卷/手稿答辩/
        # 医养同源水墨/雾感鼠尾草/深海军蓝）必须全部在保留表中。
        names = {k["name"] for k in intake.MEDICAL_KEEP.values()}
        for required in (
            "青蓝水墨医学风", "暖陶土医学风", "秋叶麦田水彩医学风", "医学书卷风",
            "医学手稿答辩风", "医养同源水墨风", "雾感鼠尾草风", "深海军蓝医学风",
        ):
            self.assertIn(required, names)

    def test_keep_entries_carry_name_subdir_vd_pairing(self):
        for src_id, keep in {**intake.MEDICAL_KEEP, **intake.KIMI_KEEP}.items():
            self.assertTrue(keep["name"].endswith("风"), f"{src_id}: name needs 风 suffix")
            self.assertGreater(len(keep["vd"].split()), 5, f"{src_id}: vd too thin")
            self.assertTrue(keep["pairing"], f"{src_id}: pairing missing")
            self.assertEqual(set(keep["anchors"]), {"primary", "secondary", "accent", "neutral"})
            self.assertGreaterEqual(len(keep["negatives"]), 3, f"{src_id}: negatives too thin")

    def test_skip_entries_map_to_real_leo_concepts(self):
        lib = {n for _, n, _ in intake.ohmy.load_existing_briefs()}
        incoming = {k["name"] for k in intake.MEDICAL_KEEP.values()} | {
            k["name"] for k in intake.KIMI_KEEP.values()
        }
        for table in (intake.MEDICAL_SKIP, intake.KIMI_SKIP):
            for src, info in table.items():
                self.assertIn(info["leo"], lib | incoming,
                              f"{src} -> {info['leo']} 不是现库或本批风格")


class AnchorProvenanceTests(unittest.TestCase):
    """Source-fidelity: curated anchors must trace back to source tokens."""

    @unittest.skipUnless(YIXUE_ROOT.is_dir(), "yixue source not available")
    def test_every_yixue_brief_anchor_provable_against_source(self):
        for src_id, keep in intake.MEDICAL_KEEP.items():
            pack = _yixue_pack(src_id)
            brief, bg_hexes = intake.build_brief(
                keep, pack, reference="test"
            )
            provenance = pack["anchors"]
            for role in ("primary", "secondary", "accent", "neutral"):
                hexm = intake.HEX_RE.search(brief["color_palette"][role]).group(0)
                self.assertIn(hexm.upper(), provenance, f"{src_id}.{role} {hexm}")
            for hexm in bg_hexes:
                self.assertIn(hexm.upper(), provenance, f"{src_id} bg {hexm}")

    @unittest.skipUnless(KIMI_ROOT.is_dir(), "open-kimi source not available")
    def test_every_kimi_brief_anchor_provable_against_design_doc(self):
        for src_id, keep in intake.KIMI_KEEP.items():
            pack = _kimi_pack(src_id)
            brief, bg_hexes = intake.build_brief(
                keep, pack, reference="test"
            )
            provenance = pack["anchors"]
            for role in ("primary", "secondary", "accent", "neutral"):
                hexm = intake.HEX_RE.search(brief["color_palette"][role]).group(0)
                self.assertIn(hexm.upper(), provenance, f"{src_id}.{role} {hexm}")
            for hexm in bg_hexes:
                self.assertIn(hexm.upper(), provenance, f"{src_id} bg {hexm}")

    def test_source_without_hex_has_no_keep_entry(self):
        # 001 通用医学汇报：源文件零 HEX 锚点，必须走 SKIP（无法过来源纪律）。
        self.assertNotIn(
            "001_通用医学汇报PPT风格提示词.json", intake.MEDICAL_KEEP
        )


class DerivationTests(unittest.TestCase):
    """Pure derivation helpers."""

    @unittest.skipUnless(YIXUE_ROOT.is_dir(), "yixue source not available")
    def test_aliases_deduped_and_lead_with_style_name(self):
        keep = intake.MEDICAL_KEEP["013_青蓝水墨医学汇报PPT风格提示词.json"]
        brief, _ = intake.build_brief(keep, _yixue_pack(
            "013_青蓝水墨医学汇报PPT风格提示词.json"), reference="test")
        self.assertEqual(brief["aliases"][0], keep["name"])
        self.assertEqual(len(brief["aliases"]), len(set(brief["aliases"])))

    @unittest.skipUnless(YIXUE_ROOT.is_dir(), "yixue source not available")
    def test_continuity_and_asset_embedding_never_migrated(self):
        # 契约：continuity/asset_embedding 由 M1 通用机制承载，不进 brief。
        keep = next(iter(intake.MEDICAL_KEEP.values()))
        brief, _ = intake.build_brief(keep, _yixue_pack(
            next(iter(intake.MEDICAL_KEEP))), reference="test")
        self.assertNotIn("continuity", brief)
        self.assertNotIn("asset_embedding", brief)

    def test_dark_and_light_decks_both_have_wcag_anchor(self):
        packs = {}
        if YIXUE_ROOT.is_dir():
            for src_id, keep in intake.MEDICAL_KEEP.items():
                packs[src_id] = (keep, _yixue_pack(src_id))
        if KIMI_ROOT.is_dir():
            for src_id, keep in intake.KIMI_KEEP.items():
                packs[src_id] = (keep, _kimi_pack(src_id))
        self.assertGreaterEqual(len(packs), 1, "no source available for WCAG gate")
        for src_id, (keep, pack) in packs.items():
            brief, _ = intake.build_brief(keep, pack, reference="test")
            # Roles only, mirroring lint_style_governance._check_text_anchor.
            anchors = intake.ohmy.palette_anchors(brief["color_palette"], [])
            primary = intake.HEX_RE.search(brief["color_palette"]["primary"]).group(0)
            self.assertTrue(
                intake.ohmy.text_anchor_ok(anchors, primary),
                f"{src_id}: no WCAG text anchor",
            )

    def test_typography_identity_font_declared(self):
        for keep in {**intake.MEDICAL_KEEP, **intake.KIMI_KEEP}.values():
            joined = " ".join(str(v) for v in keep["typo"].values())
            self.assertTrue(
                intake.ohmy.FONT_IDENTITY_RE.search(joined),
                f"{keep['name']}: typography lacks identity font",
            )


@unittest.skipUnless(
    YIXUE_ROOT.is_dir() and KIMI_ROOT.is_dir(), "sources not available"
)
class PipelineTests(unittest.TestCase):
    """End-to-end gate run against the real sources + library."""

    @classmethod
    def setUpClass(cls):
        yixue_packs = {}
        for p in sorted(YIXUE_ROOT.glob("[0-9]*.json")):
            pack = intake.parse_yixue(p)
            yixue_packs[pack["file"]] = pack
        kimi_packs = {}
        for group in sorted(KIMI_ROOT.iterdir()):
            if not group.is_dir():
                continue
            for d in sorted(group.iterdir()):
                if d.is_dir() and (d / "design.md").is_file():
                    kimi_packs[f"{group.name}/{d.name}"] = intake.parse_kimi(d)
        cls.yixue_packs = yixue_packs
        cls.kimi_packs = kimi_packs
        cls.problems, cls.code = intake.run(yixue_packs, kimi_packs, write=False)

    def test_gate_passes_on_current_library(self):
        self.assertEqual(self.code, 0, msg="; ".join(self.problems))

    def test_written_files_exist_and_parse(self):
        for src_id, keep in sorted(intake.MEDICAL_KEEP.items()):
            path = intake.yixue_target(keep)
            self.assertTrue(path.is_file(), f"{src_id}: {path} missing")
        for src_id, keep in sorted(intake.KIMI_KEEP.items()):
            path = intake.kimi_target(keep)
            self.assertTrue(path.is_file(), f"{src_id}: {path} missing")

    def test_written_briefs_match_regenerated_content(self):
        # Idempotency: files on disk equal what a fresh run would write.
        for src_id, keep in sorted(intake.MEDICAL_KEEP.items()):
            brief, _ = intake.build_brief(
                keep, {**self.yixue_packs[src_id], "scenes": keep["scenes"]},
                reference=f"GitHub: yixueAIganhuo-PPT · references/{src_id}",
            )
            expected = intake.render_markdown(
                brief, "02_行业内容域 · 医疗健康", keep["scenes"]
            )
            self.assertEqual(
                intake.yixue_target(keep).read_text(encoding="utf-8"), expected,
                f"{src_id}: drift between script and committed file",
            )
        for src_id, keep in sorted(intake.KIMI_KEEP.items()):
            brief, _ = intake.build_brief(
                keep, {**self.kimi_packs[src_id], "scenes": keep["scenes"]},
                reference=f"GitHub: open-kimi-ppt-skill · reference/design_system/{src_id}/design.md",
            )
            expected = intake.render_markdown(
                brief, f"01_通用母版 · {keep['subdir']}", keep["scenes"]
            )
            self.assertEqual(
                intake.kimi_target(keep).read_text(encoding="utf-8"), expected,
                f"{src_id}: drift between script and committed file",
            )


if __name__ == "__main__":
    unittest.main()
