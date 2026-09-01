"""intake_beautiful_html 迁移器单元测试（风格进货批 C3）。

覆盖：决策表完整性（34 = 14 保留 + 20 跳过）、配额带（12-15）、KEEP
字段完备、纯函数行为（粗俗 occasion 过滤 / 同族判定 / 四角色 HEX 映射）、
brief 构建合同（身份字体门 / 负面提示词含 avoid_for 首条）。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "intake_beautiful_html.py"
SOURCE_ROOT = Path("/Users/kuang/knowledge/ppt-github/beautiful-html-templates")

spec = importlib.util.spec_from_file_location("intake_beautiful_html", SCRIPT)
intake = importlib.util.module_from_spec(spec)
sys.modules["intake_beautiful_html"] = intake
spec.loader.exec_module(intake)


def _pack(name: str) -> dict:
    packs = intake.load_source()
    return packs[name]


@unittest.skipUnless((SOURCE_ROOT / "index.json").is_file(),
                     "beautiful-html-templates source not available")
class IntakeTableTests(unittest.TestCase):
    """Decision-table integrity against the real source tree."""

    def test_decisions_cover_every_source_slug_exactly_once(self):
        slugs = set(intake.load_source())
        decided = set(intake.KEEP) | set(intake.SKIP)
        self.assertEqual(decided, slugs)
        self.assertFalse(set(intake.KEEP) & set(intake.SKIP))

    def test_quota_band_12_to_15_new_styles(self):
        self.assertGreaterEqual(len(intake.KEEP), 12)
        self.assertLessEqual(len(intake.KEEP), 15)

    def test_keep_entries_carry_required_fields(self):
        for slug, keep in intake.KEEP.items():
            self.assertTrue(keep["name"].endswith("风"), f"{slug}: name needs 风 suffix")
            self.assertTrue(keep["subdir"], f"{slug}: subdir missing")
            self.assertGreater(len(keep["vd"].split()), 5, f"{slug}: vd too thin")
            self.assertTrue(keep["pairing"], f"{slug}: pairing missing")
            self.assertEqual(set(keep["roles"]), {"primary", "secondary", "accent", "neutral"},
                             f"{slug}: roles must cover 4 palette roles")
            self.assertGreaterEqual(len(keep["patterns"]), 3, f"{slug}: >=3 layout patterns")
            illu_families = {"flat", "glass", "hand-drawn", "dashboard",
                             "photographic", "editorial", "collage", "diagram"}
            self.assertIn(keep["illu"][0], illu_families, f"{slug}: illu family")
            self.assertIn(keep["illu"][1], ("core", "supportive", "sparse"),
                          f"{slug}: illu density")

    def test_skip_reasons_registered_nonempty(self):
        for slug, reason in intake.SKIP.items():
            self.assertGreater(len(reason), 4, f"{slug}: skip reason too thin")

    def test_target_names_unique_across_keep(self):
        names = [k["name"] for k in intake.KEEP.values()]
        self.assertEqual(len(names), len(set(names)))


@unittest.skipUnless((SOURCE_ROOT / "index.json").is_file(),
                     "beautiful-html-templates source not available")
class BriefBuildTests(unittest.TestCase):
    """Brief construction contract against real source data."""

    def test_roles_palette_has_four_hex_anchors(self):
        keep = intake.KEEP["biennale-yellow"]
        palette = intake.roles_palette(_pack("biennale-yellow"), keep)
        for role in ("primary", "secondary", "accent", "neutral"):
            self.assertRegex(palette[role], r"#[0-9A-Fa-f]{6}", f"{role} anchor")

    def test_roles_palette_raises_on_missing_key(self):
        pack = _pack("monochrome")
        bad = dict(intake.KEEP["monochrome"])
        bad["roles"] = {**bad["roles"], "primary": "no_such_key"}
        with self.assertRaises(ValueError):
            intake.roles_palette(pack, bad)

    def test_negative_prompt_leads_with_source_avoid_for(self):
        pack = _pack("emerald-editorial")
        keep = intake.KEEP["emerald-editorial"]
        neg = intake.negative_pack(pack, keep)
        self.assertEqual(neg[0], pack["avoid_for"])
        self.assertGreaterEqual(len(neg), 3)

    def test_clean_occasions_drops_vulgar_tags(self):
        pack = _pack("retro-windows")
        cleaned = intake.clean_occasions(pack)
        self.assertFalse(any("shitpost" in s.lower() for s in cleaned))
        self.assertLessEqual(len(cleaned), 4)

    def test_brief_json_roundtrip_and_reference_carries_template_path(self):
        brief = intake.build_brief(_pack("cobalt-grid"), intake.KEEP["cobalt-grid"])
        json.dumps(brief, ensure_ascii=False)  # serializable
        self.assertIn("templates/cobalt-grid/", brief["reference"])
        self.assertEqual(brief["style_name"], "钴蓝网格简报风")
        self.assertTrue(brief["layout_patterns"])


class PureFunctionTests(unittest.TestCase):
    """Pure helpers independent of the source tree."""

    def test_normalize_name_strips_style_suffix(self):
        self.assertEqual(intake.normalize_name("终端命令行风"), "终端命令行")
        self.assertEqual(intake.normalize_name("党政红风格"), "党政红")

    def test_audit_family_pair_requires_name_or_palette_affinity(self):
        fp_a = frozenset({"#000000", "#FFFFFF"})
        fp_b = frozenset({"#000000", "#FFFFFF"})
        # identical fingerprints + jaccard 1.0 -> suspected family
        self.assertTrue(intake.audit_family_pair("甲风", fp_a, "乙风", fp_b))
        # disjoint palettes + distinct names -> no suspicion
        fp_c = frozenset({"#123456", "#ABCDEF"})
        self.assertFalse(intake.audit_family_pair("甲风", fp_a, "完全不同的名字风", fp_c))

    def test_contrait_ratio_basics(self):
        self.assertGreater(intake._contrast("#000080", "#FFFFFF"), 4.5)
        self.assertLess(intake._contrast("#FFAAAA", "#FFFFFF"), 4.5)


if __name__ == "__main__":
    unittest.main()
