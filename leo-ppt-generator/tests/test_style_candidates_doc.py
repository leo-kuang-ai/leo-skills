#!/usr/bin/env python3
"""style-candidates.md 文档合同测试（风格进货批 S4b）：候补矿登记表存在性
与行数预算、七路勘察确认的剩余源零遗漏逐源覆盖、每源触发/去重字段与七字段
合同在场、进化机制声明（非承诺入库/三类使用信号/四重去重+lint 门+220 硬顶
余量检查/金样板与预览补齐义务）、许可红线沿袭。"""
import unittest
from pathlib import Path

DOC = (
    Path(__file__).resolve().parents[1]
    / "references" / "style-candidates.md"
)
LINE_BUDGET = 120
MECHANISM_BUDGET = 15

# Every remaining mine confirmed by the seven-route survey and ruled NOT into
# this intake batch. The list is the zero-omission contract: dropping a source
# from the registry silently loses the evolution inventory.
SURVEY_SOURCES = (
    "gpt-image2-ppt-skills",
    "slides-grab",
    "beautiful-html-templates",
    "OfficeCLI",
    "open-kimi",
    "academic-ppt-master",
    "huashu",
    "frontend-slides",
    "dashi",
    "Office-PowerPoint-MCP",
    "Mck",
    "awesome-gpt-image-2",
    "nano-banana",
    "MultiAgentPPT",
    "AI-PPT-Slides",
    "scholar-ppt-cn",
    "xhs-visual-director",
    "awesome-ppt-skills",
    "ian-handdrawn",
)


class StyleCandidatesDocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = DOC.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()

    def test_doc_exists_and_within_line_budget(self):
        self.assertTrue(DOC.exists())
        self.assertLessEqual(len(self.lines), LINE_BUDGET)

    def test_mechanism_header_section_within_budget(self):
        # The evolution-mechanism contract must stay terse; locate the section
        # between its heading and the next "## " heading and count non-blank
        # body lines (heading itself excluded).
        start = next(
            i for i, l in enumerate(self.lines) if l.startswith("## 进化机制"))
        end = next(i for i, l in enumerate(self.lines)
                   if i > start and l.startswith("## "))
        body = [l for l in self.lines[start + 1:end] if l.strip()]
        self.assertLessEqual(len(body), MECHANISM_BUDGET)

    def test_all_survey_mines_registered_zero_omission(self):
        for name in SURVEY_SOURCES:
            self.assertIn(name, self.content, f"候补矿未登记: {name}")

    def test_every_source_carries_trigger_and_dedup_fields(self):
        # Each entry must answer WHEN to restock and WHAT it duplicates —
        # the two fields that make the inventory actionable rather than a
        # wish list.
        self.assertGreaterEqual(
            self.content.count("触发："), len(SURVEY_SOURCES))
        self.assertGreaterEqual(
            self.content.count("去重："), len(SURVEY_SOURCES))
        for field in ("源项目", "规模与载体", "勘察定级", "净新预估",
                      "精选建议", "触发条件", "去重注意"):
            self.assertIn(field, self.content)

    def test_evolution_mechanism_contract_present(self):
        for fragment in (
            "候补≠承诺入库",
            "不占 220 硬顶",
            "R-30",
            "R-64",
            "R-55",
            "四重去重",
            "family_duplicate",
            "四条治理 lint",
            "220 硬顶余量检查",
            "金样板",
            "预览",
        ):
            self.assertIn(fragment, self.content)

    def test_licensing_red_lines_carried(self):
        # GordenPPTSkill (non-commercial) stays banned; AGPL / no-LICENSE
        # mines stay idea-level only.
        self.assertIn("GordenPPTSkill", self.content)
        self.assertIn("AGPL", self.content)
        self.assertIn("无 LICENSE", self.content)


if __name__ == "__main__":
    unittest.main()
