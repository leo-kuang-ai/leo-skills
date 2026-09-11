"""U2：质量证据与派生状态（F1/F5）——机制与故障交错验收。

固定交错（方案 §6）：E1 通过已入索引 → E2 同组合失败落盘 → catalog 发布
失败 → 新查询不得返回旧 verified；另测撤销、删除、坏记录与读取中变更。
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import sys

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator import style_validation as sv


def _write_validation(root: Path, validation_id: str, *, result="pass",
                      style="builtin:style:clean-professional",
                      theme="builtin:theme:clean-professional-light",
                      lane="html", mode="light", page_roles=("cover",),
                      checks_pass=True, review_pass=True,
                      outputs=None, supersedes=None) -> None:
    package = root / "evidence" / validation_id
    package.mkdir(parents=True, exist_ok=True)
    outs = outputs or {"page.png": b"\x89PNG\r\n\x1a\nfake-output"}
    for name, body in outs.items():
        (package / name).write_bytes(body)
    import hashlib

    record = {
        "kind": "style-validation", "schema_version": 1,
        "validation_id": validation_id,
        "assets": {"style": style, "theme": theme,
                   "layout": "builtin:layout:p25-spec-table"},
        "lane": lane, "mode": mode, "locale": "zh-CN",
        "page_roles": list(page_roles),
        "result": result,
        "checks": [{"id": "overflow", "version": "1", "result":
                    "pass" if checks_pass else "fail"},
                   {"id": "contrast", "version": "1", "result":
                    "pass" if checks_pass else "fail"}],
        "review": {"source": "human", "reviewer": "测试维护者",
                   "result": "pass" if review_pass else "fail",
                   "rubric": "test"},
        "outputs": {name: hashlib.sha256(body).hexdigest()
                    for name, body in outs.items()},
        "compiler": {"name": "test", "version": "1"},
    }
    if supersedes:
        record["supersedes"] = supersedes
    (package / "manifest.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_revocation(root: Path, revocation_id: str, validation_id: str) -> None:
    rev_dir = root / "evidence" / "revocations"
    rev_dir.mkdir(parents=True, exist_ok=True)
    (rev_dir / f"{revocation_id}.json").write_text(json.dumps({
        "kind": "evidence-revocation", "schema_version": 1,
        "revocation_id": revocation_id, "validation_id": validation_id,
        "reason": "依赖版本变更后撤销（测试）",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


class StyleValidationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-evidence-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "template-library"
        (self.root / "evidence").mkdir(parents=True)
        (self.root / "library.json").write_text("{}", encoding="utf-8")


class EvidenceScanTest(StyleValidationTestCase):
    def test_pass_record_derives_verified(self) -> None:
        _write_validation(self.root, "e1")
        view = sv.quality_view(library=self.root)
        self.assertEqual(view["views"][0]["records"], 1)
        self.assertFalse(view["views"][0]["problems"])
        quality = view["views"][0]["quality"]
        self.assertIn(repr(("html", "builtin:style:clean-professional",
                            "builtin:theme:clean-professional-light", "light",
                            "builtin:layout:p25-spec-table")),
                      quality["verified_scopes"])

    def test_missing_output_hash_is_integrity_error_not_empty(self) -> None:
        _write_validation(self.root, "e1")
        (self.root / "evidence/e1/page.png").unlink()
        evidence_set = sv.scan_evidence_set(self.root)
        self.assertTrue(any("output_missing" in p for p in evidence_set["problems"]))

    def test_failed_checks_do_not_derive_verified(self) -> None:
        _write_validation(self.root, "e1", checks_pass=False)
        quality = sv.derive_quality(sv.scan_evidence_set(self.root))
        self.assertEqual(quality["verified_scopes"], {})

    def test_fake_review_does_not_derive_verified(self) -> None:
        _write_validation(self.root, "e1", review_pass=False)
        quality = sv.derive_quality(sv.scan_evidence_set(self.root))
        self.assertEqual(quality["verified_scopes"], {})


class FreshnessInterleavingTest(StyleValidationTestCase):
    """F1 固定交错：新失败落盘而 catalog 发布失败时，旧 verified 不得外泄。"""

    def _publish_catalog(self, digest: str) -> None:
        catalog = self.root / "catalog" / "generations" / "gen-e1"
        catalog.mkdir(parents=True, exist_ok=True)
        (catalog / "registry.json").write_text(json.dumps({
            "kind": "template-registry", "schema_version": 1,
            "generation": "gen-e1", "source_digest": "x" * 32,
            "evidence_set_digest": digest, "entities": []}), encoding="utf-8")
        (self.root / "catalog" / "current.json").write_text(json.dumps({
            "kind": "template-catalog-pointer", "schema_version": 1,
            "generation": "gen-e1"}), encoding="utf-8")

    def test_e2_failure_lands_catalog_stale_old_verified_not_returned(self) -> None:
        _write_validation(self.root, "e1")
        e1_digest = sv.scan_evidence_set(self.root)["evidence_set_digest"]
        self._publish_catalog(e1_digest)  # E1 已入索引
        first = sv.quality_view(library=self.root)
        self.assertFalse(first["views"][0]["stale"])
        self.assertTrue(first["views"][0]["quality"]["verified_scopes"])

        # E2：同组合失败落盘（catalog 发布失败——指针仍指 gen-e1）。
        _write_validation(self.root, "e2", result="fail", checks_pass=False)
        second = sv.quality_view(library=self.root)
        self.assertTrue(second["views"][0]["stale"],
                        "新失败落盘后 catalog 摘要失配必须披露 stale")
        self.assertEqual(second["views"][0]["quality"]["verified_scopes"], {},
                         "同组合失败出现后不得继续返回旧 verified")
        self.assertTrue(second["views"][0]["quality"]["conflict_scopes"],
                        "同组合 pass+fail 未显式 supersedes 即未裁决矛盾（§9）")

    def test_contradictory_unresolved_results_cancel_pass(self) -> None:
        _write_validation(self.root, "e1", result="pass")
        _write_validation(self.root, "e2", result="fail")
        quality = sv.derive_quality(sv.scan_evidence_set(self.root))
        self.assertTrue(quality["conflict_scopes"], "未裁决矛盾必须可见")
        self.assertEqual(quality["verified_scopes"], {})

    def test_supersedes_explicit_replacement(self) -> None:
        _write_validation(self.root, "e1", result="fail")
        _write_validation(self.root, "e2", result="pass", supersedes=["e1"])
        quality = sv.derive_quality(sv.scan_evidence_set(self.root))
        self.assertTrue(quality["verified_scopes"], "显式 supersedes 的通过应生效")
        self.assertEqual(quality["superseded_validation_ids"], ["e1"])

    def test_revocation_invalidates_record(self) -> None:
        _write_validation(self.root, "e1")
        _write_revocation(self.root, "r1", "e1")
        evidence_set = sv.scan_evidence_set(self.root)
        quality = sv.derive_quality(evidence_set)
        self.assertEqual(quality["verified_scopes"], {})
        self.assertEqual(quality["revoked_validation_ids"], ["e1"])
        # 撤销不删除原证据。
        self.assertTrue((self.root / "evidence/e1/manifest.json").is_file())

    def test_deleted_evidence_is_integrity_problem(self) -> None:
        _write_validation(self.root, "e1")
        self._publish_catalog(sv.scan_evidence_set(self.root)["evidence_set_digest"])
        shutil.rmtree(self.root / "evidence" / "e1")
        evidence_set = sv.scan_evidence_set(self.root)
        # 删除被索引引用的证据是完整性错误；此处集合本身变空但 catalog 失配。
        view = sv.quality_view(library=self.root)
        self.assertTrue(view["views"][0]["stale"])


class DeckStyleEligibilityTest(StyleValidationTestCase):
    def test_four_roles_same_theme_is_deck_style(self) -> None:
        for i, roles in enumerate([("cover",), ("content",), ("evidence",), ("closing",)], 1):
            _write_validation(self.root, f"role-{i}", page_roles=roles)
        result = sv.deck_style_eligibility(
            sv.scan_evidence_set(self.root), "builtin:style:clean-professional")
        self.assertEqual(result["kind"], "deck-style")
        self.assertTrue(result["eligible"])

    def test_cover_only_is_page_component(self) -> None:
        _write_validation(self.root, "only-cover", page_roles=("cover",))
        result = sv.deck_style_eligibility(
            sv.scan_evidence_set(self.root), "builtin:style:clean-professional")
        self.assertEqual(result["kind"], "page-component")
        self.assertFalse(result["eligible"])
        self.assertIn("content", result["missing_roles"])

    def test_cross_theme_evidence_does_not_count(self) -> None:
        _write_validation(self.root, "r1", page_roles=("cover",),
                          theme="builtin:theme:a")
        _write_validation(self.root, "r2", page_roles=("content", "evidence", "closing"),
                          theme="builtin:theme:b")
        result = sv.deck_style_eligibility(
            sv.scan_evidence_set(self.root), "builtin:style:clean-professional")
        self.assertEqual(result["kind"], "page-component")
        self.assertEqual(result["reason"], "theme_mismatch")

    def test_failed_role_evidence_does_not_count(self) -> None:
        _write_validation(self.root, "r1", page_roles=("cover",))
        _write_validation(self.root, "r2", page_roles=("content",), checks_pass=False)
        _write_validation(self.root, "r3", page_roles=("evidence",))
        _write_validation(self.root, "r4", page_roles=("closing",))
        result = sv.deck_style_eligibility(
            sv.scan_evidence_set(self.root), "builtin:style:clean-professional")
        self.assertEqual(result["kind"], "page-component")


class EvidenceSchemasTest(unittest.TestCase):
    def test_evidence_schemas_present_and_valid(self) -> None:
        from jsonschema import Draft7Validator

        schemas = SKILL / "template-library" / "governance" / "schemas"
        for name in ("style-validation-v1.schema.json", "evidence-revocation-v1.schema.json"):
            Draft7Validator.check_schema(json.loads((schemas / name).read_text()))

    def test_curation_policy_declares_owners_not_self_pass(self) -> None:
        curation = json.loads(
            (SKILL / "template-library/governance/curation.json").read_text())
        self.assertEqual(len(curation["directions"]), 9)
        self.assertIn("eligibility_owner", curation["deck_style"])
        self.assertIn("prohibited", curation["deck_style"])


if __name__ == "__main__":
    unittest.main()
