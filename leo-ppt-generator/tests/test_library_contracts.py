"""U9：治理区合同完整性——schema/词表/最小 fixture 实体全部可校验。

合同先于 U4/U5 实现（防止组合器、CSS 编译器、容量检查各自定义合同）。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCHEMAS = SKILL / "template-library" / "governance" / "schemas"
VOCAB = SKILL / "template-library" / "governance" / "vocabularies"
FIXTURE = SKILL / "tests" / "fixtures" / "minimal-template-library"

ENTITY_SCHEMA = {
    "canonical/styles/minimal-clean/brief.json": "style-brief-v2.schema.json",
    "canonical/themes/minimal-light/theme.json": "render-theme-v1.schema.json",
    "canonical/layouts/minimal-table/layout.json": "layout-profile-v1.schema.json",
    "canonical/templates/minimal-table/template.json": "template-v1.schema.json",
}

EXPECTED_SCHEMAS = {
    "library.schema.json", "asset-common.schema.json", "style-brief-v2.schema.json",
    "render-theme-v1.schema.json", "layout-profile-v1.schema.json",
    "template-v1.schema.json", "resolved-design-v1.schema.json",
    "axis-manifest-v1.schema.json", "brand-v1.schema.json", "preset-v1.schema.json",
    "font-manifest-v1.schema.json", "ornament-manifest-v1.schema.json",
    "catalog-registry-v1.schema.json",
    # U1 账本 disposition=convert 的旧 schema 归档（"v1 保留为迁移输入"，
    # 见 governance/migration/asset-ledger.json）。
    "style-brief-v1.schema.json", "style-index-v1.schema.json",
    "layout-bank-v1.schema.json",
    # U2 验证证据 schema（evidence 包与撤销记录，见 tests/test_style_validation.py）。
    "style-validation-v1.schema.json", "evidence-revocation-v1.schema.json",
    # U7 QA profile 合同；R-33 可执行模板采用记录（style_pack adopt）。
    "render-qa-profile-v1.schema.json", "executable-adoption-v1.schema.json",
    "page-expression-v1.schema.json", "qualification-v1.schema.json",
}


def _validator(name: str):
    from jsonschema import Draft7Validator
    from referencing import Registry, Resource
    import referencing.jsonschema

    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    # $ref 跨文件解析：把同目录全部 schema 注册进 referencing registry。
    resources = []
    for path in SCHEMAS.glob("*.schema.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "$id" in doc:
            resources.append((doc["$id"], Resource.from_contents(doc)))
    registry = Registry().with_resources(resources)
    return Draft7Validator(schema, registry=registry), registry


class LibraryContractsTest(unittest.TestCase):
    def test_all_builtin_layout_profiles_validate(self) -> None:
        validator, _ = _validator("layout-profile-v1.schema.json")
        paths = sorted((SKILL / "template-library/canonical/layouts").glob("*/layout.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(layout=path.parent.name):
                errors = list(validator.iter_errors(json.loads(path.read_text())))
                self.assertFalse(errors, [error.message for error in errors])

    def test_expected_schema_set_present(self) -> None:
        actual = {path.name for path in SCHEMAS.glob("*.schema.json")}
        self.assertEqual(actual, EXPECTED_SCHEMAS)

    def test_all_schemas_are_valid_draft7(self) -> None:
        from jsonschema import Draft7Validator

        for path in sorted(SCHEMAS.glob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft7Validator.check_schema(schema)

    def test_library_declaration_validates(self) -> None:
        validator, _ = _validator("library.schema.json")
        declaration = json.loads(
            (SKILL / "template-library" / "library.json").read_text(encoding="utf-8"))
        errors = list(validator.iter_errors(declaration))
        self.assertFalse(errors, f"library.json: {[e.message for e in errors]}")

    def test_fixture_entities_validate_against_governance_schemas(self) -> None:
        for entity_path, schema_name in ENTITY_SCHEMA.items():
            validator, _ = _validator(schema_name)
            document = json.loads((FIXTURE / entity_path).read_text(encoding="utf-8"))
            errors = list(validator.iter_errors(document))
            self.assertFalse(
                errors, f"{entity_path}: {[e.message for e in errors]}")

    def test_invalid_entities_rejected(self) -> None:
        validator, _ = _validator("render-theme-v1.schema.json")
        base = json.loads(
            (FIXTURE / "canonical/themes/minimal-light/theme.json").read_text())
        bad = json.loads(json.dumps(base))
        del bad["modes"]["light"]["background"]  # 必需角色缺失
        self.assertTrue(list(validator.iter_errors(bad)))
        bad2 = json.loads(json.dumps(base))
        bad2["modes"]["light"]["text"] = "14213D"  # 非 #RRGGBB
        self.assertTrue(list(validator.iter_errors(bad2)))

    def test_all_builtin_axis_manifests_validate_and_use_stable_ids(self) -> None:
        validator, _ = _validator("axis-manifest-v1.schema.json")
        axis_root = SKILL / "template-library" / "canonical" / "axes"
        manifests = sorted(axis_root.glob("*/*/manifest.json"))
        self.assertEqual(len(manifests), 124)
        errors = []
        from leo_ppt_generator.asset_resolver import ASSET_ID_RE
        for path in manifests:
            data = json.loads(path.read_text(encoding="utf-8"))
            errors.extend(f"{path}: {e.message}" for e in validator.iter_errors(data))
            self.assertRegex(data["asset_id"], ASSET_ID_RE)
            self.assertEqual(data["body_ref"], "body.md")
            self.assertTrue((path.parent / data["body_ref"]).is_file())
        self.assertFalse(errors, "axis manifests: " + "; ".join(errors[:10]))

    def test_layout_profile_enforces_logical_canvas(self) -> None:
        validator, _ = _validator("layout-profile-v1.schema.json")
        base = json.loads(
            (FIXTURE / "canonical/layouts/minimal-table/layout.json").read_text())
        wrong = json.loads(json.dumps(base))
        wrong["canvas"] = {"width": 1920, "height": 1080, "units": "logical-px"}
        self.assertTrue(list(validator.iter_errors(wrong)), "画布必须锁定 1280×720 逻辑 px")
        wrong_type = json.loads(json.dumps(base))
        wrong_type["layout_type"] = "free-css"
        self.assertTrue(list(validator.iter_errors(wrong_type)), "布局类型限定五类")

    def test_vocabularies_complete(self) -> None:
        conservatism = json.loads((VOCAB / "conservatism.json").read_text())
        self.assertEqual({t["id"] for t in conservatism["terms"]},
                         {"reserved", "balanced", "expressive"})
        environment = json.loads((VOCAB / "environment.json").read_text())
        self.assertGreaterEqual(len(environment["terms"]), 8)
        bright = next(t for t in environment["terms"] if t["id"] == "bright-large-venue")
        self.assertEqual(bright["default_mode_hint"], "light")
        density = json.loads((VOCAB / "density.json").read_text())
        self.assertEqual(len(density["tiers"]), 6)
        self.assertIn("very low, meditative", density["legacy_text_mapping"],
                      "现有 zen 自由文本必须有确定映射")
        roles = json.loads((VOCAB / "theme-roles.json").read_text())
        self.assertIn("background", roles["color_roles"]["required"])
        self.assertIn("title", roles["font_roles"]["required"])

    def test_seed_slugs_reserved_in_protocol(self) -> None:
        declaration = json.loads(
            (SKILL / "template-library" / "library.json").read_text())
        self.assertIn("logical_canvas", declaration["protocol"])
        canvas = declaration["protocol"]["logical_canvas"]
        self.assertEqual((canvas["width"], canvas["height"]), (1280, 720))


if __name__ == "__main__":
    unittest.main()
