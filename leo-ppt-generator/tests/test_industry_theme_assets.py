"""U3 行业合并交付：九方向种子资产合同 + 长尾主题投影 fixture（§8.1–8.3）。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.render.theme import ThemeContrastError, compute_effective_theme
from leo_ppt_generator.style_validation import deck_style_eligibility, scan_evidence_set

SEEDS = ("management-clear", "finance-navy", "consulting-pyramid", "tech-dark",
         "gov-red", "health-clean", "edu-bright", "brand-creative", "academic-austere")
ROLES_REQUIRED = ("background", "surface", "text", "primary", "on_primary",
                  "muted", "border", "accent")


class IndustryThemeAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = AssetResolver()

    def test_nine_seeds_active_with_theme_and_features(self) -> None:
        for slug in SEEDS:
            resolved = self.resolver.resolve(f"builtin:style:{slug}")
            self.assertEqual(resolved["lifecycle"], "active", slug)
            brief = resolved["data"]
            self.assertGreaterEqual(len(brief["visual_language"]["features"]), 2, slug)
            theme_id = brief["bindings"]["theme_default"]
            self.assertTrue(theme_id, f"{slug} 缺主题绑定")
            theme = self.resolver.resolve(theme_id)
            self.assertEqual(theme["kind"], "theme")

    def test_seed_themes_pass_contrast_in_every_declared_mode(self) -> None:
        for slug in SEEDS:
            style = self.resolver.resolve(f"builtin:style:{slug}")
            theme = self.resolver.resolve(style["data"]["bindings"]["theme_default"])
            for mode in theme["data"]["modes"]:
                effective = compute_effective_theme(theme["data"], mode=mode)  # 不抛即通过
                for role in ROLES_REQUIRED:
                    self.assertIn(role, effective["colors"], f"{slug}/{mode} 缺角色 {role}")

    def test_tech_dark_declares_light_variant(self) -> None:
        theme = self.resolver.resolve("builtin:theme:tech-dark-mode")
        self.assertEqual(sorted(theme["data"]["modes"]), ["dark", "light"])
        style = self.resolver.resolve("builtin:style:tech-dark")
        self.assertEqual(sorted(style["data"]["bindings"]["modes_supported"]), ["dark", "light"])

    def test_every_seed_routes_cover_four_deck_roles(self) -> None:
        for slug in SEEDS:
            resolved = self.resolver.resolve(f"builtin:style:{slug}")
            routes = resolved["data"]["bindings"]["layout_routes"]
            page_types = {route["page_type"] for route in routes}
            self.assertTrue({"cover", "content", "data", "closing"} <= page_types,
                            f"{slug} 路由缺四角色: {page_types}")

    def test_font_manifest_registered_with_license(self) -> None:
        font = self.resolver.resolve("builtin:font:noto-sans-sc")
        manifest = font["data"]
        self.assertEqual(len(manifest["files"]), 2)
        self.assertEqual(manifest["license"]["status"], "verified-distributable")
        notice = SKILL / "NOTICE"
        self.assertIn("Noto", notice.read_text(encoding="utf-8"))

    def test_industry_rules_survive_theme_binding(self) -> None:
        # 行业规则在 governance/rules/domains，主题切换不删除规则文件。
        domains = SKILL / "template-library/governance/rules/domains"
        self.assertTrue(any(domains.glob("**/content-rules.md")),
                        "行业内容规则必须保留在治理区")

    def test_deck_style_requires_evidence_not_declaration(self) -> None:
        # 声明路由 ≠ 整稿资格：资格只能由证据派生（F5）。九种子矩阵证据
        # 落盘后必须派生 deck-style；无证据风格（迁移草稿）不得取得资格。
        evidence_set = scan_evidence_set(SKILL / "template-library")
        for slug in SEEDS:
            result = deck_style_eligibility(evidence_set, f"builtin:style:{slug}")
            self.assertEqual(result["kind"], "deck-style",
                             f"{slug} 矩阵证据已落盘，应派生整稿资格")
        no_evidence = deck_style_eligibility(evidence_set,
                                             "builtin:style:clean-professional")
        self.assertEqual(no_evidence["kind"], "page-component",
                         "clean-professional 无整稿证据，不得取得整稿资格")

    def test_theme_projection_fixtures_declare_sources_and_gaps(self) -> None:
        fixtures = sorted((SKILL / "evals/fixtures/template-quality/theme-projection").glob("*.json"))
        self.assertEqual(len(fixtures), 3)
        for fixture in fixtures:
            doc = json.loads(fixture.read_text(encoding="utf-8"))
            self.assertIn("field_sources", doc)
            self.assertTrue(doc["adaptation_gaps"], f"{fixture.name} 缺口不得为空")
            for field, source in doc["field_sources"].items():
                self.assertTrue(source.split(":", 1)[0] in {"explicit", "inferred", "default"},
                                f"{fixture.name}.{field} 来源非法: {source}")
            brief_ref = SKILL / "template-library" / doc["brief_ref"]
            self.assertTrue(brief_ref.is_file(), f"{fixture.name} brief_ref 悬空")


if __name__ == "__main__":
    unittest.main()
