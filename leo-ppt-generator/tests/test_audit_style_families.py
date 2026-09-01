#!/usr/bin/env python3
"""audit_style_families.py 单测：名称归一 / 同族判定 / 聚簇 / 只读不修改 /
真实库存分布（201 文件口径） / --json 输出 / 双跑确定性 / R-66 家族合并口径
（variant_of 不计顶层、不参与同族判定；合并计划镜像、别名可检索、无同板回潮）。"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "audit_style_families.py"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import audit_style_families as audit  # noqa: E402


BRIEF_TEMPLATE = """# {name}

**适用场景:**
- 测试

**GPT-Image-2 风格 Brief:**
```json
{{
  "type": "16:9 full-slide PowerPoint image",
  "style_name": "{name}",
  "best_for": "{best_for}",
  "visual_direction": "{visual_direction}",
  "canvas": {{"aspect_ratio": "16:9", "background": "{background}",
             "composition": "test", "density": "medium"}},
  "color_palette": {{"primary": "{primary}", "secondary": "{secondary}",
                     "accent": "{accent}", "neutral": "{neutral}",
                     "rule": "test rule"}},
  "typography": {{"title": "思源黑体", "body": "Noto Sans SC", "labels": "Inter"}},
  "layout_patterns": ["a", "b"]
}}
```
"""


def _write_brief(root: Path, rel: str, **kwargs) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BRIEF_TEMPLATE.format(**kwargs), encoding="utf-8")


class HelpersTest(unittest.TestCase):
    def test_normalize_name_strips_style_suffixes(self):
        self.assertEqual(audit.normalize_name("清爽专业风格"), "清爽专业")
        self.assertEqual(audit.normalize_name("麦肯锡咨询风"), "麦肯锡咨询")
        self.assertEqual(audit.normalize_name("SaaS介绍风"), "SaaS介绍")
        # 单字『风』不误剥（风格名本身最后一个字）
        self.assertEqual(audit.normalize_name("风"), "风")

    def test_jaccard(self):
        self.assertEqual(audit._jaccard({"#A"}, {"#A"}), 1.0)
        self.assertEqual(audit._jaccard(set(), {"#A"}), 0.0)
        self.assertAlmostEqual(audit._jaccard({"#A", "#B"}, {"#B", "#C"}), 1 / 3)

    def test_pair_related_identical_palette_and_similar_name(self):
        a = {"base": "周报月报", "hexes": ["#0D9488", "#111827"]}
        b = {"base": "年终总结", "hexes": ["#0D9488", "#111827"]}
        related, why = audit.pair_related(a, b)
        self.assertTrue(related)
        self.assertIn("palette", why)

    def test_pair_related_distinct_styles_not_clustered(self):
        a = {"base": "水墨禅意", "hexes": ["#1A1A1A"]}
        b = {"base": "医疗健康", "hexes": ["#0EA5E9", "#FFFFFF"]}
        related, _ = audit.pair_related(a, b)
        self.assertFalse(related)


class FixtureAuditTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-audit-test-")
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _populate(self) -> None:
        _write_brief(self.root, "01_通用母版/商务专业/稳重商务风.md",
                     name="稳重商务风", best_for="汇报 述职",
                     visual_direction="clean professional report",
                     background="#FFFFFF",
                     primary="#0F766E", secondary="#111827",
                     accent="#F59E0B", neutral="#F8FAFC")
        _write_brief(self.root, "01_通用母版/商务专业/简约商务风.md",
                     name="简约商务风", best_for="汇报 总结",
                     visual_direction="clean professional minimal",
                     background="#FFFFFF",
                     primary="#0F766E", secondary="#111827",
                     accent="#F59E0B", neutral="#F8FAFC")
        _write_brief(self.root, "02_行业内容域/医疗健康/医疗信息风.md",
                     name="医疗信息风", best_for="医疗科普 教学",
                     visual_direction="clinical light hand-drawn illustration",
                     background="#F0FDF4",
                     primary="#10B981", secondary="#065F46",
                     accent="#0EA5E9", neutral="#ECFDF5")

    def test_cluster_detection_on_fixture(self):
        self._populate()
        entries = audit.brief_entries(self.root)
        self.assertEqual(len(entries), 3)
        report = audit.build_report(entries)
        clusters = report["suspected_family_clusters"]
        self.assertEqual(len(clusters), 1)
        names = {m["name"] for m in clusters[0]["members"]}
        self.assertEqual(names, {"稳重商务风", "简约商务风"})

    def test_variant_of_styles_are_not_independent_cluster_members(self):
        # R-66: a variant_of attribution removes the brief from top-level
        # cluster candidacy even with an identical palette fingerprint.
        self._populate()
        path = self.root / "01_通用母版" / "商务专业" / "简约商务风.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace('"style_name": "简约商务风",',
                         '"style_name": "简约商务风",\n  "variant_of": "稳重商务风",'),
            encoding="utf-8")
        entries = audit.brief_entries(self.root)
        report = audit.build_report(entries)
        self.assertEqual(report["suspected_family_clusters"], [])
        self.assertEqual(report["variant_styles"], 1)
        self.assertEqual(report["top_level_styles"], 2)
        self.assertEqual(report["family_merges"], {"稳重商务风": ["简约商务风"]})

    def test_axis_and_tone_tags(self):
        self._populate()
        entries = audit.brief_entries(self.root)
        by_name = {e["name"]: e for e in entries}
        self.assertEqual(by_name["稳重商务风"]["axis"], "01_通用母版")
        self.assertEqual(by_name["稳重商务风"]["subfamily"], "商务专业")
        self.assertIn("light", by_name["医疗信息风"]["tones"])
        self.assertIn("hand-drawn", by_name["医疗信息风"]["tones"])
        self.assertIn("汇报", by_name["稳重商务风"]["scenarios"])

    def test_no_side_effects_on_briefs(self):
        self._populate()
        before = {
            p: p.read_bytes() for p in self.root.rglob("*.md")
        }
        audit.build_report(audit.brief_entries(self.root))
        after = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        self.assertEqual(before, after)


class RealLibraryTest(unittest.TestCase):
    """真实库存：文件口径下限 + 内部一致性 + JSON 输出 + 双跑确定性（R-66 前置实测）。"""

    def test_real_library_counts_223(self):
        # Parallel intake batches grow the library concurrently; pin a
        # monotonic floor (S3 snapshot 223) plus internal consistency
        # instead of a hard total, so sibling batches do not break this
        # gate while shrinking the library still fails.
        entries = audit.brief_entries()
        self.assertGreaterEqual(len(entries), 223)
        report = audit.build_report(entries)
        self.assertEqual(report["total_briefs"], len(entries))
        self.assertEqual(sum(report["by_axis"].values()), len(entries))
        self.assertEqual(report["by_axis"]["顶层内置"], 11)

    def test_json_output_shape_and_determinism(self):
        runs = []
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--json"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            runs.append(json.loads(result.stdout))
        self.assertEqual(runs[0], runs[1])
        payload = runs[0]
        for key in ("total_briefs", "by_axis", "by_tone", "by_scenario",
                    "reused_palettes", "suspected_family_clusters",
                    "singleton_briefs", "top_level_styles", "variant_styles",
                    "family_merges"):
            self.assertIn(key, payload)


# R-66 强候选簇（合并前高 Jaccard 实测）：簇内每份原名全数保留。
MERGED_FAMILIES: dict[str, list[str]] = {
    "成果汇报风": ["周报月报风", "年终总结风", "晋升述职风", "高管汇报风"],
    "产品发布会风": ["品牌发布会风", "展会博览会风", "新品上市风"],
    "学术论文答辩风": ["学术会议风", "毕业答辩风", "课题申请风"],
    "商业计划书风": ["融资路演风", "创业大赛路演风", "财报季报风"],
    "战略咨询风": ["顾问报告风"],
    "互联网产品风": ["在线教育风"],
    "培训课件风": ["项目复盘风"],
    # S1a 批吸收 oh-my-ppt:同板中式传统色浅底簇(chinese-cream-blossom
    # 并入 chinese-porcelain-rose,指纹 7/9 重合)。
    "凝脂杨妃风": ["米白樱粉风"],
}


class FamilyMergeTest(unittest.TestCase):
    """R-66 合并后真实库存断言：每簇顶层=1、归属完整、别名可检索、无同板回潮。"""

    @classmethod
    def setUpClass(cls):
        cls.entries = audit.brief_entries()
        cls.by_name = {e["name"]: e for e in cls.entries}
        cls.report = audit.build_report(cls.entries)

    def test_all_variants_exist_and_point_at_declared_primaries(self):
        variants = 0
        for primary, names in MERGED_FAMILIES.items():
            primary_entry = self.by_name[primary]
            self.assertIsNone(primary_entry.get("variant_of"),
                               f"{primary} 不得自身是变体")
            for name in names:
                entry = self.by_name[name]
                self.assertEqual(entry.get("variant_of"), primary,
                                 f"{name} 未归属 {primary}")
                variants += 1
        self.assertEqual(self.report["variant_styles"], variants)
        # Top-level styles = every entry minus declared variants (see the
        # floor note in RealLibraryTest: no hard total, parallel batches).
        self.assertEqual(
            self.report["top_level_styles"], len(self.entries) - variants)

    def test_audit_family_merges_mirror_the_merge_plan(self):
        expected = {p: sorted(v) for p, v in MERGED_FAMILIES.items()}
        self.assertEqual(self.report["family_merges"], expected)

    def test_each_merged_cluster_has_exactly_one_top_level_style(self):
        # 五大强候选簇合并后顶层风格数合计 = 7 个主风格（每簇/每对恰好 1 个）。
        for primary, names in MERGED_FAMILIES.items():
            cluster_names = {primary, *names}
            top = [n for n in cluster_names
                   if self.by_name[n].get("variant_of") is None]
            self.assertEqual(
                len(top), 1,
                f"簇 {primary} 顶层风格应为 1，实际 {sorted(top)}")

    def test_primary_aliases_cover_all_merged_original_names(self):
        for primary, names in MERGED_FAMILIES.items():
            entry = self.by_name[primary]
            path = Path(audit.STYLES_ROOT) / entry["path"]
            brief = json.loads(
                re.search(r"```json\n(.*?)\n```", path.read_text("utf-8"), re.S).group(1))
            self.assertEqual(set(brief.get("aliases", [])), set(names),
                             f"{primary} aliases 须全数收录被合并原名")

    def test_no_identical_palette_pair_remains_at_top_level(self):
        # Jaccard==1.00 <=> 集合相等：合并后顶层（无 variant_of）不得再有同板对。
        top = [e for e in self.entries if e.get("variant_of") is None]
        fingerprints = {}
        for e in top:
            fp = frozenset(e["hexes"])
            if not fp:
                continue
            self.assertNotIn(
                fp, fingerprints,
                f"同板回潮: {e['name']} 与 {fingerprints.get(fp)}")
            fingerprints[fp] = e["name"]

    def test_merged_cluster_names_leave_suspected_clusters(self):
        merged_names = {n for v in MERGED_FAMILIES.values() for n in v} \
            | set(MERGED_FAMILIES)
        for cluster in self.report["suspected_family_clusters"]:
            members = {m["name"] for m in cluster["members"]}
            self.assertFalse(
                members <= merged_names,
                f"已合并簇仍在疑似同族清单: {sorted(members)}")

    def test_cluster_count_reduced_from_17(self):
        # 合并前实测 17 簇（48 份）；合并后须显著下降（当前 10，弱证据簇保留）。
        self.assertLess(len(self.report["suspected_family_clusters"]), 12)


if __name__ == "__main__":
    unittest.main()
