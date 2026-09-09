"""主风格 aliases 迁移测试（S1b 任务 3 / R-63 遗留债）。

覆盖：注入行为（补缺/不覆盖已有/跳过变体）、数据表形状（每条 2-5 个、
非空字符串、不含自身名、无重复键）、真实库全量校验（主风格 aliases
全覆盖防回潮，变体不携带 aliases）。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import migrate_style_aliases as msa  # noqa: E402


def _write_brief(root: Path, rel: str, payload: dict) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# test\n\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    return path


def _base(name: str) -> dict:
    return {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": name,
        "best_for": "测试",
        "visual_direction": "test",
        "canvas": {"aspect_ratio": "16:9", "background": "#FFFFFF",
                   "composition": "t", "density": "low"},
        "color_palette": {"primary": "#111111", "secondary": "#222222",
                          "accent": "#333333", "neutral": "#444444", "rule": "t"},
        "typography": {"title": "Arial", "body": "Arial", "labels": "Arial"},
        "layout_patterns": ["t"],
    }


class InjectBehavior(unittest.TestCase):
    def test_injects_missing_master_and_skips_variant_and_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            styles = root / Path("template-library/reference/sources/retired-styles-tree/styles")
            _write_brief(styles, "01_通用母版/x/水墨禅意风.md", _base("水墨禅意风"))
            _write_brief(styles, "03_场景用途结构/x/年报风.md",
                         {**_base("年报风"), "variant_of": "成果汇报风"})
            kept = {**_base("麦肯锡咨询风"), "aliases": ["保留别名"]}
            _write_brief(styles, "01_通用母版/x/麦肯锡咨询风.md", kept)

            stats = msa.inject_aliases(styles)

            self.assertEqual(stats["injected"], 1)
            self.assertEqual(stats["skipped_variant"], 1)
            self.assertEqual(stats["skipped_existing"], 1)
            self.assertEqual(stats["missing_from_table"], 0)

            injected = json.loads(
                (styles / "01_通用母版/x/水墨禅意风.md").read_text(encoding="utf-8")
                .split("```json\n")[1].split("\n```")[0]
            )
            self.assertEqual(injected["aliases"], msa.ALIASES["水墨禅意风"])
            # Surgical insert: style_name line stays intact right before aliases.
            raw = (styles / "01_通用母版/x/水墨禅意风.md").read_text(encoding="utf-8")
            self.assertIn('"style_name": "水墨禅意风",\n  "aliases":', raw)
            # Existing aliases are never overwritten.
            preserved = json.loads(
                (styles / "01_通用母版/x/麦肯锡咨询风.md").read_text(encoding="utf-8")
                .split("```json\n")[1].split("\n```")[0]
            )
            self.assertEqual(preserved["aliases"], ["保留别名"])
            # Variants stay untouched.
            variant = json.loads(
                (styles / "03_场景用途结构/x/年报风.md").read_text(encoding="utf-8")
                .split("```json\n")[1].split("\n```")[0]
            )
            self.assertNotIn("aliases", variant)

    def test_injection_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            styles = Path(tmp) / Path("template-library/reference/sources/retired-styles-tree/styles")
            _write_brief(styles, "01/a/扁平风.md", _base("扁平风"))
            first = msa.inject_aliases(styles)
            second = msa.inject_aliases(styles)
            self.assertEqual(first["injected"], 1)
            self.assertEqual(second["injected"], 0)
            self.assertEqual(second["skipped_existing"], 1)


class TableShape(unittest.TestCase):
    def test_table_entries_are_2_to_5_nonempty_and_not_self(self):
        self.assertGreaterEqual(len(msa.ALIASES), 100)
        for name, aliases in msa.ALIASES.items():
            self.assertTrue(2 <= len(aliases) <= 5, f"{name}: {aliases}")
            for alias in aliases:
                self.assertIsInstance(alias, str)
                self.assertTrue(alias.strip(), f"{name}: empty alias")
                self.assertNotEqual(alias, name, f"{name}: alias equals style name")
            self.assertEqual(len(aliases), len(set(aliases)), f"{name}: dup aliases")


class RealLibrary(unittest.TestCase):
    def test_all_master_styles_carry_aliases(self):
        gaps = msa.check_aliases(msa.STYLES_ROOT)
        self.assertEqual(gaps, [], f"主风格缺 aliases: {gaps}")

    def test_alias_table_never_targets_variants(self):
        # R-66: variants stay reachable via their master's aliases; this
        # migration must never inject into a variant brief. The table is
        # fixed data, so assert against the live variant set (parallel
        # intake batches may add variants carrying their own aliases —
        # allowed by the schema and out of this migration's scope).
        variant_names = {
            str(brief["style_name"])
            for _path, _text, _match, brief in msa.iter_briefs(msa.STYLES_ROOT)
            if "variant_of" in brief
        }
        overlap = sorted(variant_names & set(msa.ALIASES))
        self.assertEqual(overlap, [], f"数据表误含变体名: {overlap}")


if __name__ == "__main__":
    unittest.main()
