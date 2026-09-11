"""style-alias-colloquial Judge must use the live catalog, not a name subset."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "evals/fixtures/scripts/judge_style_alias_colloquial.py"
spec = importlib.util.spec_from_file_location("style_alias_judge", SCRIPT)
judge = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(judge)


class LiveCatalogJudgeTest(unittest.TestCase):
    def test_current_catalog_resolves_alias_and_primary_name(self):
        index, error = judge._live_style_index()
        self.assertIsNone(error)
        self.assertIn("Dracula紫风", index["styles"])
        self.assertIn("Dracula紫风", index["terminal_hits"])
        self.assertEqual(
            judge.judge("库里真实收录的是 Dracula紫风，适合技术分享。"), []
        )

    def test_unknown_quoted_style_is_rejected(self):
        problems = judge.judge(
            "库里对应的是 Dracula紫风；可选「不存在的紫风」作为终端风格。"
        )
        self.assertTrue(any("不在库" in problem for problem in problems))

    def test_registry_revision_drift_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="leo-style-judge-") as tmp:
            root = Path(tmp)
            library = root / "template-library"
            brief = {
                "schema_version": 2,
                "entity": "style-brief",
                "asset_id": "builtin:style:drift-fixture",
                "name": "漂移测试风",
                "aliases": ["drift"],
                "lifecycle": "active",
                "taxonomy": {"families": ["终端配色"]},
            }
            brief_path = library / "canonical/styles/drift-fixture/brief.json"
            brief_path.parent.mkdir(parents=True)
            brief_path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
            (library / "library.json").parent.mkdir(parents=True, exist_ok=True)
            (library / "library.json").write_text(
                json.dumps({"kind": "template-library"}), encoding="utf-8"
            )
            generation = "g1"
            registry = {
                "generation": generation,
                "entities": [{
                    "asset_id": brief["asset_id"],
                    "kind": "style",
                    "path": "canonical/styles/drift-fixture/brief.json",
                    "revision": "0000000000000000",
                    "name": brief["name"],
                    "aliases": brief["aliases"],
                    "lifecycle": "active",
                }],
            }
            catalog = library / "catalog"
            (catalog / "generations" / generation).mkdir(parents=True)
            (catalog / "current.json").write_text(
                json.dumps({"generation": generation}), encoding="utf-8"
            )
            (catalog / "generations" / generation / "registry.json").write_text(
                json.dumps(registry, ensure_ascii=False), encoding="utf-8"
            )
            old_bundle = os.environ.get("LEO_PPT_BUNDLE")
            os.environ["LEO_PPT_BUNDLE"] = str(root)
            try:
                index, error = judge._live_style_index()
                self.assertIsNone(index)
                self.assertIn("stale_catalog", error)
                problems = judge.judge("技术分享场景不触发排除，可以选择终端风格。")
                self.assertTrue(any("canonical style catalog" in p for p in problems))
            finally:
                if old_bundle is None:
                    os.environ.pop("LEO_PPT_BUNDLE", None)
                else:
                    os.environ["LEO_PPT_BUNDLE"] = old_bundle


if __name__ == "__main__":
    unittest.main()
