"""intake_slidesgrab_officecli 迁移器单元测试(风格进货批 C2)。

覆盖:决策表完整性(西式 35 / 韩式 60 / OfficeCLI 全目录 = keep + skip,
不重不漏)、C2 配额带(slides-grab 25-30、净增 ≥30)、韩式保真纪律
(韩文原名入 aliases、四角色 HEX 可溯源)、OfficeCLI 六分组
variant-dimension 标注与金样板登记、去重门语义复用(S1a 同构)、
幂等重跑与盘上文件与脚本再生成一致。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "intake_slidesgrab_officecli.py"
SLIDESGRAB_SRC = Path("/Users/kuang/knowledge/ppt-github/slides-grab/src")
OFFICECLI_STYLES = Path(
    "/Users/kuang/knowledge/ppt-github/OfficeCLI/skills/morph-ppt/reference/styles"
)

spec = importlib.util.spec_from_file_location("intake_c2", SCRIPT)
intake = importlib.util.module_from_spec(spec)
sys.modules["intake_c2"] = intake
spec.loader.exec_module(intake)


def _sources():
    west, ko = intake.load_slidesgrab()
    office = intake.load_officecli()
    return west, ko, office


@unittest.skipUnless(
    SLIDESGRAB_SRC.is_dir() and OFFICECLI_STYLES.is_dir(), "C2 sources not available"
)
class IntakeTableTests(unittest.TestCase):
    """Decision-table integrity against both real source trees."""

    def test_decisions_cover_every_source_exactly_once(self):
        west, ko, office = _sources()
        self.assertEqual(set(intake.KEEP_WEST) | set(intake.SKIP_WEST), set(west))
        self.assertFalse(set(intake.KEEP_WEST) & set(intake.SKIP_WEST))
        self.assertEqual(set(intake.KEEP_KO) | set(intake.SKIP_KO), set(ko))
        self.assertFalse(set(intake.KEEP_KO) & set(intake.SKIP_KO))
        office_skip = {k for k, v in intake.SKIP_OFFICECLI.items() if v}
        self.assertEqual(
            set(intake.KEEP_OFFICECLI) | office_skip, set(office)
        )
        self.assertFalse(set(intake.KEEP_OFFICECLI) & office_skip)

    def test_quota_band_slidesgrab_25_to_30(self):
        slidesgrab = len(intake.KEEP_KO) + len(intake.KEEP_WEST)
        self.assertGreaterEqual(slidesgrab, 25)
        self.assertLessEqual(slidesgrab, 30)

    def test_quota_band_c2_total_at_least_30(self):
        total = len(intake.KEEP_KO) + len(intake.KEEP_WEST) + len(intake.KEEP_OFFICECLI)
        self.assertGreaterEqual(total, 30)
        self.assertLessEqual(total, 40)

    def test_korean_priority_ko_picks_outnumber_west(self):
        # 韩式 60 套是全新审美——保真收录应多于西式精选。
        self.assertGreater(len(intake.KEEP_KO), len(intake.KEEP_WEST) * 3)

    def test_korean_aliases_keep_native_titles(self):
        # 韩文原名必须入 aliases,保证原名可检索。
        _, ko, _ = _sources()
        hangul = 0
        for num, keep in intake.KEEP_KO.items():
            joined = " ".join(keep["aliases"])
            if any("\uac00" <= ch <= "\ud7a3" for ch in joined):
                hangul += 1
        self.assertGreaterEqual(hangul, 10, "韩文原名 aliases 覆盖不足")

    def test_keep_entries_carry_required_shape(self):
        for scope, table in (
            ("ko", intake.KEEP_KO),
            ("west", intake.KEEP_WEST),
            ("office", intake.KEEP_OFFICECLI),
        ):
            for src_id, keep in table.items():
                self.assertTrue(keep["name"].endswith("风"), f"{scope} {src_id}: name needs 风 suffix")
                self.assertGreater(len(keep["vd"].split()), 5, f"{scope} {src_id}: vd too thin")
                self.assertTrue(keep["pairing"], f"{scope} {src_id}: pairing missing")
                self.assertEqual(
                    set(keep["anchors"]), {"primary", "secondary", "accent", "neutral"},
                    f"{scope} {src_id}: anchors need four roles",
                )
                self.assertGreaterEqual(len(keep["layout"]), 3, f"{scope} {src_id}: layout too thin")
                self.assertGreaterEqual(len(keep["negatives"]), 3, f"{scope} {src_id}: negatives too thin")

    def test_skip_entries_map_to_real_leo_concepts(self):
        # Concept dedupe spot anchors: the highest-risk duplicate families.
        self.assertEqual(intake.SKIP_WEST["01"]["leo"], "玻璃拟态风")
        self.assertEqual(intake.SKIP_WEST["20"]["leo"], "蒸汽波风")
        self.assertEqual(intake.SKIP_KO["DD05"]["leo"], "玻璃拟态风")
        self.assertEqual(intake.SKIP_KO["DD33"]["leo"], "蓝晒图纸风")
        # C-batch parallel additions are recorded as such, not silently dropped.
        self.assertIn("C 系并行批", intake.SKIP_WEST["03"]["reason"])
        self.assertIn("C 系并行批", intake.SKIP_KO["DD03"]["reason"])
        # Source-anchor impossibility is an explicit skip reason, never guessed hex.
        self.assertIn("无 HEX", intake.SKIP_OFFICECLI["dark--velvet-rose"]["reason"])


@unittest.skipUnless(
    SLIDESGRAB_SRC.is_dir() and OFFICECLI_STYLES.is_dir(), "C2 sources not available"
)
class OfficeCLIMetaTests(unittest.TestCase):
    """variant 第二维度与金样板登记纪律。"""

    def test_every_keep_has_group_and_group_is_known(self):
        _, _, office = _sources()
        known = {"bw", "dark", "light", "mixed", "vivid", "warm"}
        families = {"flat", "glass", "hand-drawn", "dashboard", "photographic",
                    "editorial", "collage", "diagram"}
        densities = {"core", "supportive", "sparse"}
        for d, keep in intake.KEEP_OFFICECLI.items():
            group = office[d]["group"]
            self.assertIn(group, known, f"{d}: unknown variant dimension {group}")
            self.assertIn(keep["family"][0], families, f"{d}: bad paired family")
            self.assertIn(keep["family"][1], densities, f"{d}: bad paired density")

    def test_golden_samples_registered_only_for_existing_pptx(self):
        for d, keep in intake.KEEP_OFFICECLI.items():
            pptx = keep.get("pptx")
            if pptx is None:
                continue
            self.assertTrue((OFFICECLI_STYLES / d / pptx).is_file(),
                            f"{d}: registered sample {pptx} missing in source")


class GateSemanticsTests(unittest.TestCase):
    """门语义:不依赖源目录也能验证决策表自洽。"""

    def test_targets_are_namespaced_and_unique(self):
        paths = intake.target_paths()
        self.assertEqual(len(paths), len(set(paths.values())))
        for key, path in paths.items():
            rel = path.relative_to(intake.STYLES_ROOT)
            self.assertTrue(str(rel).startswith(("15_", "16_")), f"{key}: {rel} 越界")
            self.assertFalse(path.parent == intake.STYLES_ROOT, "C2 不写顶层")

    def test_no_keep_name_collides_across_scopes(self):
        names = [k["name"] for table in (intake.KEEP_KO, intake.KEEP_WEST,
                                         intake.KEEP_OFFICECLI) for k in table.values()]
        self.assertEqual(len(names), len(set(names)))


@unittest.skipUnless(
    SLIDESGRAB_SRC.is_dir() and OFFICECLI_STYLES.is_dir(), "C2 sources not available"
)
class PipelineTests(unittest.TestCase):
    """端到端:check 门通过 + write 幂等。"""

    def test_check_gate_passes_with_real_library(self):
        problems, code = intake.run(write=False)
        self.assertEqual(code, 0, f"gates failed: {problems[:5]}")
        self.assertEqual(problems, [])

    def test_write_is_idempotent_and_on_disk_files_match(self):
        problems, code = intake.run(write=True)
        self.assertEqual(code, 0, f"write failed: {problems[:5]}")
        # Second run must stay green (files already on disk count as own targets).
        problems, code = intake.run(write=False)
        self.assertEqual(code, 0, f"re-check failed: {problems[:5]}")
        # Spot check: every target exists and re-parses as a valid brief JSON.
        import json
        import re
        for key, path in intake.target_paths().items():
            self.assertTrue(path.is_file(), f"{key}: {path} missing")
            text = path.read_text(encoding="utf-8")
            m = re.search(r"```json\n(.*?)\n```", text, re.S)
            self.assertIsNotNone(m, f"{key}: no json block")
            brief = json.loads(m.group(1))
            self.assertEqual(brief["style_name"], path.stem)
            self.assertTrue(brief["layout_patterns"])
        # Golden samples copied verbatim.
        for d, keep in intake.KEEP_OFFICECLI.items():
            pptx = keep.get("pptx")
            if pptx is None:
                continue
            dst = intake.SAMPLES_GOLDEN / pptx
            self.assertTrue(dst.is_file(), f"golden sample {pptx} not copied")


if __name__ == "__main__":
    unittest.main()
