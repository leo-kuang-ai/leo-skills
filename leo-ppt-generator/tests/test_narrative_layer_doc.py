#!/usr/bin/env python3
"""Narrative-methodology layer doc contract tests (S4n intake batch).

Guards the new narrative sub-layer under ``references/styles/06_论证模式``:

- existence: 12 narrative methodology entries + the beat library;
- beat library structure: 20 whitelisted beats, 12 rhythm signatures,
  explicit non-free-composition discipline and an exclusion note;
- per-entry contract: five required sections incl. the orthogonality
  statement (narrative layer = "how to say", argumentation axis = "how to
  prove", RST = paging structure);
- whitelist discipline: every beat cited by an entry must exist in the
  beat library (no invented beats, no free composition);
- style-presets.md bridge: the narrative field legend acknowledges the
  subclass as a valid storyline value.
"""
import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
AXIS_DIR = SKILL_DIR / "references" / "styles" / "06_论证模式"
NARRATIVE_DIR = AXIS_DIR / "叙事方法论"
BEAT_LIB = AXIS_DIR / "叙事拍库.md"
PRESETS = SKILL_DIR / "references" / "style-presets.md"

EXPECTED_ENTRIES = (
    "学术研究报告", "咨询决策", "创意提案", "事故复盘", "融资路演",
    "主旨演讲", "经营复盘", "产品发布", "科普讲解", "方案提案",
    "技术深潜", "工作坊教学",
)
REQUIRED_SECTIONS = (
    "## 1. 适用场景",
    "## 2. 页序骨架",
    "## 3. 节奏要点",
    "## 4. 与论证模式轴的关系（正交声明）",
    "## 5. 拍库白名单（选配组件，非自由组合）",
)
SECTION5 = "## 5. 拍库白名单（选配组件，非自由组合）"
# Chinese name + (original atom id) pairs cited in entry whitelists.
_BEAT_CITE_RE = re.compile(r"([\u4e00-\u9fffA-Za-z·]+)（([a-z][a-z0-9+-]*)）")


def _entry_paths() -> list[Path]:
    return sorted(NARRATIVE_DIR.glob("*.md"))


class NarrativeLayerDocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = BEAT_LIB.read_text(encoding="utf-8")
        cls.entries = {p.stem: p.read_text(encoding="utf-8") for p in _entry_paths()}

    def test_layer_files_exist(self):
        # The sub-layer is exactly the 12 intake entries; no strays.
        self.assertTrue(BEAT_LIB.exists(), "beat library missing")
        self.assertEqual(
            sorted(self.entries), sorted(EXPECTED_ENTRIES),
            "narrative sub-layer file set drifted from the 12 intake entries",
        )

    def test_beat_library_structure(self):
        # Selection criterion and counts must stay explicit and auditable.
        for fragment in (
            "arc_beat 33 / rhythm_signature 12",
            "共 **20 拍**",
            "**白名单纪律（M1 评估结论）**：拍**不自由组合**",
            "33−20=13",
        ):
            self.assertIn(fragment, self.lib)
        beat_rows = re.findall(r"^\| [^|#]", self._section(self.lib, "## 1."), re.M)
        sig_rows = re.findall(r"^\| [^|#]", self._section(self.lib, "## 2."), re.M)
        self.assertEqual(len(beat_rows) - 1, 20)   # minus header row
        self.assertEqual(len(sig_rows) - 1, 12)    # minus header row

    def test_each_entry_contract_and_orthogonality(self):
        # Every entry declares all five sections and the three-layer split:
        # narrative = how to say, argumentation axis = how to prove, RST = paging.
        for name, text in self.entries.items():
            for section in REQUIRED_SECTIONS:
                self.assertIn(section, text, f"{name}: missing {section}")
            self.assertIn("# 叙事方法论：", text)
            self.assertIn("三层正交", text)
            self.assertIn("管「怎么说」", text)
            self.assertIn("「怎么证」由论证模式轴承接", text)
            self.assertIn("rst-paging.md", text)

    def test_whitelist_beats_subset_of_library(self):
        # Beats are a whitelist component: any beat cited by an entry must be
        # a library beat (column 2 of the beat table), never an invented one.
        lib_beats = set(
            re.findall(r"^\| [^|]+ \| ([a-z][a-z0-9+-]*) \|", self._section(self.lib, "## 1."), re.M)
        )
        self.assertTrue(lib_beats, "beat table parse failed")
        for name, text in self.entries.items():
            section5 = text.split(SECTION5, 1)[1]
            cited = {m.group(2) for m in _BEAT_CITE_RE.finditer(
                section5.split("节奏签名")[0])}
            self.assertTrue(cited, f"{name}: empty beat whitelist")
            unknown = cited - lib_beats
            self.assertFalse(unknown, f"{name}: beats outside library: {unknown}")

    def test_presets_bridge_acknowledges_subclass(self):
        # style-presets.md narrative field must keep acknowledging the
        # narrative-methodology subclass as a valid storyline value.
        text = PRESETS.read_text(encoding="utf-8")
        self.assertIn("叙事方法论/", text)
        self.assertIn("正交可叠加", text)
        self.assertIn("叙事拍库.md", text)

    @staticmethod
    def _section(text: str, heading: str) -> str:
        # Return the body of a ## section up to the next ## heading.
        start = text.index(heading)
        nxt = re.search(r"^## ", text[start + len(heading):], re.M)
        return text[start:start + len(heading) + (nxt.start() if nxt else len(text))]


if __name__ == "__main__":
    unittest.main()
