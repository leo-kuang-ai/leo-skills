"""U1 迁移账本结构校验。

旧 StyleAssetInventoryTest（template-library/reference/sources/retired-styles-tree/styles 旧树的 MD 扫描分类：asset_role
嗅探 / _is_style_md / coverage 分级 / 重复名-变体闭包）已随 U10 消费者切换
退役——新协议的资产发现/身份/重复检测由 asset_resolver 拥有
（tests/test_asset_resolver.py），此处只保留迁移账本合同。
"""
import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime/src"))


class MigrationLedgerTest(unittest.TestCase):
    """U1 迁移账本结构校验（漂移检测用 scripts/freeze_template_rebuild_baseline.py --check）。"""

    LEDGER = SKILL / "template-library" / "governance" / "migration" / "asset-ledger.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = json.loads(cls.LEDGER.read_text(encoding="utf-8"))

    def test_every_styles_tree_source_asset_has_disposition(self) -> None:
        styles_root = SKILL / Path("template-library/reference/sources/retired-styles-tree/styles")
        expected = {
            "references/styles/" + path.relative_to(styles_root).as_posix()
            for path in styles_root.rglob("*") if path.is_file()
            and not any(part in {"generated", "generated.previous"}
                        or part.startswith(".style-index-")
                        for part in path.relative_to(styles_root).parts)
        }
        actual = {entry["source_path"] for entry in self.ledger["entries"]
                  if entry["source_path"].startswith("references/styles/")
                  and "/generated/" not in entry["source_path"]}
        self.assertEqual(actual, expected,
                         f"账本遗漏: {sorted(expected - actual)[:5]} 多出: {sorted(actual - expected)[:5]}")
        self.assertEqual(len(actual), 597)

    def test_ids_unique_and_dispositions_valid(self) -> None:
        valid = {"convert", "migrate-as-is", "merge", "to-reference", "rebuild-delete"}
        ids = [entry["target_asset_id"] for entry in self.ledger["entries"]]
        self.assertEqual(len(ids), len(set(ids)), "重复 asset_id")
        for entry in self.ledger["entries"]:
            self.assertIn(entry["disposition"], valid, entry["source_path"])
            self.assertIn(entry["owner_unit"], {"U3", "U5", "U9", "U10"}, entry["source_path"])

    def test_seed_slugs_reserved(self) -> None:
        reserved = {"management-clear", "finance-navy", "consulting-pyramid", "tech-dark",
                    "gov-red", "health-clean", "edu-bright", "brand-creative", "academic-austere"}
        slugs = {entry["target_asset_id"].split(":")[-1] for entry in self.ledger["entries"]}
        self.assertFalse(slugs & reserved, f"机械分配占用了种子 slug: {slugs & reserved}")

    def test_supplementary_sources_covered(self) -> None:
        sources = {entry["source_path"] for entry in self.ledger["entries"]}
        for rel in ("references/style-presets.json", "assets/render-fonts/NotoSansSC-Regular.otf",
                    "runtime/src/leo_ppt_generator/schemas/style-brief-v1.schema.json"):
            self.assertIn(rel, sources, f"补充资产缺账: {rel}")


if __name__ == "__main__":
    unittest.main()
