"""资格门测试使用临时证据；不得把本文件的合成观测当作真实运行证明。"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

from leo_ppt_generator.qualification import (
    ORACLE_PATH, QualificationError, derive_qualification, evidence_digest,
    file_reference, read_evidence_bytes, verify_capability_evidence,
)

ROOT = Path(__file__).resolve().parents[1]


class QualificationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ORACLE_PATH).parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "template-library" / ORACLE_PATH, self.root / ORACLE_PATH)
        self.oracle = json.loads((self.root / ORACLE_PATH).read_text())
        self.environment = {"test_environment": "mechanism-only"}
        self.write("environment.json", self.environment)
        self.write("owner.json", {"asset_id": "builtin:layout:probe", "structure": {"nodes": ["A", "B"]}})
        self.deps = {"owner.json": file_reference(self.root, "owner.json")["sha256"]}
        self.deps["owner/page.html"] = self.write("owner/page.html", {"purpose": "mechanism-only"})["sha256"]
        self.asset = {"asset_id": "builtin:layout:probe", "lanes": ["render:html", "image"],
                      "relations": ["process", "independent"], "lifecycle_status": "executable"}
        self.receipt = self.make_receipt()

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True))
        return file_reference(self.root, path)

    def make_receipt(self, relation="process", lane="render:html", name="one"):
        oracle = {**file_reference(self.root, ORACLE_PATH), "owner": self.oracle["owner"], "version": self.oracle["version"]}
        environment = file_reference(self.root, "environment.json")
        probes = {}
        for i, probe in enumerate(("positive", "negative")):
            prefix = f"{name}/{probe}"
            expected = {"required_text": ["A", "B"], "facts": [], "focus": "A", "reading_order": ["A", "B"],
                        "structure": {"nodes": ["A", "B"], "edges": [{"from": "A", "to": "B"}], "parallel": []}}
            if relation == "independent":
                expected["structure"] = {"items": ["A", "B"], "edges": []}
            data = {"probe": probe, "purpose": "mechanism test"}
            render_input = self.write(prefix + "-data.json", data)
            fixture = self.write(prefix + ".json", {"probe": probe, "data": data, "expected": expected})
            Image.new("RGB", (2560, 1440), color=(i * 200, 0, 0)).save(self.root / (prefix + ".png"))
            artifact = file_reference(self.root, prefix + ".png")
            checks = dict.fromkeys(self.oracle["common"] + self.oracle["relations"][relation]["required_checks"], True)
            if probe == "negative":
                checks[self.oracle["relations"][relation]["negative_check"]] = False
            edge = {"start": [180, 110], "end": [400, 110], "directed": True}
            measurement = self.write(prefix + "-measurement.json", {
                "schema_version": 1, "kind": "render-measurement", "source": "browser-dom",
                "artifact_sha256": artifact["sha256"], "viewport": [1280, 720],
                "data_sha256": render_input["sha256"], "template_sha256": self.deps["owner/page.html"],
                "texts": [{"text": value, "box": [100 + index * 300, 100, 80, 30], "font_size": 28}
                          for index, value in enumerate(("A", "B"))], "blocks": [],
                "edges": [edge] if (relation == "process" and probe == "positive") or
                                   (relation == "independent" and probe == "negative") else []})
            observation = self.write(prefix + "-observation.json", {
                "artifact": artifact, "fixture": fixture, "oracle_sha256": oracle["sha256"],
                "environment_sha256": environment["sha256"], "lane": lane, "relation": relation, "checks": checks})
            observed = json.loads((self.root / observation["path"]).read_text())
            observation = self.write(observation["path"], {**observed, "measurement": measurement, "render_input": render_input})
            probes[probe] = {"status": "passed", "fixture": fixture, "artifact": artifact, "observation": observation}
            if lane == "image":
                probes[probe]["provider_receipt"] = self.write(prefix + "-provider.json", {
                    "status": "succeeded", "request_id": "mechanism-test-only", "artifact": artifact, "fixture": fixture, "lane": lane})
        review = self.write(name + "/review.json", {"artifacts": [p["artifact"] for p in probes.values()],
            "oracle_sha256": oracle["sha256"], "environment_sha256": environment["sha256"],
            "status": "passed", "severe_defects": 0, "reviewer": "test-mechanism-only"})
        receipt = {"schema_version": 1, "kind": "capability-evidence", "receipt_id": name,
            "asset_id": self.asset["asset_id"], "asset_generation": "a" * 64, "relation": relation,
            "lane": lane, "oracle": oracle, "environment": environment, "dependency_hashes": dict(self.deps),
            "probes": probes, "visual_review": review}
        receipt["evidence_digest"] = evidence_digest(receipt)
        return receipt

    def derive(self, receipts=None, **options):
        return derive_qualification(self.asset, asset_generation="a" * 64,
            evidence_receipts=[self.receipt] if receipts is None else receipts,
            library_root=self.root, expected_dependencies=self.deps,
            environment=options.pop("environment", self.environment), **options)

    def lane(self, result, lane="render:html", relation="process"):
        return result["lanes"][lane]["relations"][relation]

    def test_positive_negative_evidence_is_specific_to_one_relation_and_lane(self):
        result = self.derive()
        self.assertEqual(self.lane(result)["status"], "publication-qualified")
        self.assertEqual(self.lane(result, "image")["status"], "unverified")
        self.assertEqual(self.lane(result, relation="independent")["status"], "unverified")
        self.assertEqual(result["qualification_status"], "unverified")

    def test_declaration_and_legacy_positive_flags_never_promote(self):
        self.asset["provisional"] = True
        self.assertEqual(self.derive([])["qualification_status"], "unverified")
        receipts = [{"asset_id": self.asset["asset_id"], "asset_generation": "a" * 64,
                     "lane": "render:html", "probe": probe, "status": "passed"} for probe in ("positive", "negative")]
        spec = importlib.util.spec_from_file_location("capability_manifest", ROOT / "scripts/capability_manifest.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.derive_qualification(self.asset, asset_generation="a" * 64, evidence_receipts=receipts)
        self.assertNotEqual(result["qualification_status"], "publication-qualified")

    def test_missing_negative_and_malformed_schema_fail_closed(self):
        for mutation in ("negative", "digest", "lane"):
            receipt = deepcopy(self.receipt)
            if mutation == "negative": del receipt["probes"]["negative"]
            if mutation == "digest": receipt["evidence_digest"] = "b" * 64
            if mutation == "lane": receipt["probes"]["positive"]["unexpected"] = True
            if mutation != "digest": receipt["evidence_digest"] = evidence_digest(receipt)
            with self.subTest(mutation=mutation):
                self.assertEqual(self.lane(self.derive([receipt]))["status"], "rejected")

    def test_every_evidence_byte_drift_revokes_qualification(self):
        references = [self.receipt["oracle"], self.receipt["environment"], self.receipt["visual_review"], {"path": "owner.json"}]
        for probe in self.receipt["probes"].values():
            references.extend(probe[key] for key in ("fixture", "artifact", "observation"))
        for ref in references:
            path = self.root / ref["path"]
            before = path.read_bytes()
            path.write_bytes(before + b" ")
            try:
                with self.subTest(path=ref["path"]):
                    self.assertEqual(self.lane(self.derive())["status"], "rejected")
            finally:
                path.write_bytes(before)

    def test_generation_environment_and_dependency_drift_reject(self):
        receipt = deepcopy(self.receipt)
        receipt["asset_generation"] = "b" * 64
        receipt["evidence_digest"] = evidence_digest(receipt)
        self.assertIn("evidence_generation_stale", self.lane(self.derive([receipt]))["gaps"])
        self.assertIn("evidence_environment_stale", self.lane(self.derive(environment={}))["gaps"])
        self.deps["missing.html"] = "b" * 64
        self.assertIn("evidence_dependency_stale", self.lane(self.derive())["gaps"])

    def test_failed_probe_and_accepted_semantically_wrong_negative_override_pass(self):
        failed = deepcopy(self.receipt)
        failed["receipt_id"] = "failed"
        failed["probes"]["negative"]["status"] = "failed"
        failed["evidence_digest"] = evidence_digest(failed)
        self.assertEqual(self.lane(self.derive([self.receipt, failed]))["status"], "rejected")
        probe = self.receipt["probes"]["negative"]
        observation = json.loads((self.root / probe["observation"]["path"]).read_text())
        observation["checks"]["dependency_edges"] = True
        probe["observation"] = self.write(probe["observation"]["path"], observation)
        self.receipt["evidence_digest"] = evidence_digest(self.receipt)
        self.assertIn("evidence_output_check_mismatch", self.lane(self.derive())["gaps"])

    def test_duplicate_receipts_reject_instead_of_masking_ambiguity(self):
        self.assertIn("evidence_duplicate_receipt", self.lane(self.derive([self.receipt, self.receipt]))["gaps"])

    def test_claimed_checks_without_output_measurements_cannot_qualify(self):
        # 旧 verifier 只核对布尔观测与摘要，会把纯色 PNG 晋升为关系能力。
        probe = self.receipt["probes"]["positive"]
        observation = json.loads((self.root / probe["observation"]["path"]).read_text())
        del observation["measurement"]
        probe["observation"] = self.write(probe["observation"]["path"], observation)
        self.receipt["evidence_digest"] = evidence_digest(self.receipt)
        self.assertEqual(self.lane(self.derive())["status"], "rejected")

    def test_visual_review_absence_is_provisional_and_retired_cannot_execute(self):
        self.receipt["visual_review"] = None
        self.receipt["evidence_digest"] = evidence_digest(self.receipt)
        self.assertEqual(self.lane(self.derive())["status"], "provisional")
        self.asset["lifecycle_status"] = "retired"
        self.assertEqual(self.lane(self.derive())["status"], "rejected")

    def test_image_needs_its_own_provider_file_bound_to_output(self):
        image = self.make_receipt(lane="image", name="image")
        self.assertEqual(self.lane(self.derive([image]), "image")["status"], "rejected")
        self.assertIn("image_output_oracle_unavailable", self.lane(self.derive([image]), "image")["gaps"])
        del image["probes"]["positive"]["provider_receipt"]
        image["evidence_digest"] = evidence_digest(image)
        self.assertEqual(self.lane(self.derive([image]), "image")["status"], "rejected")

    def test_paths_reject_symlink_ancestor_traversal_and_special_file(self):
        (self.root / "linked").symlink_to(self.root / "one", target_is_directory=True)
        for path in ("../owner.json", "/owner.json", "one/../owner.json", "linked/positive.png", "one//positive.png"):
            with self.subTest(path=path), self.assertRaises(QualificationError):
                read_evidence_bytes(self.root, path)

    def test_lane_dependency_missing_is_not_compensated_by_passed_receipt(self):
        self.asset["gaps"] = {"render:html": ["lane_dependency_missing"]}
        self.assertEqual(self.lane(self.derive())["status"], "rejected")

    def test_qualification_schema_preserves_orthogonal_lifecycle(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((ROOT / "runtime/src/leo_ppt_generator/schemas/qualification-v1.schema.json").read_text())
        validator = Draft202012Validator(schema)
        result = self.derive()
        self.assertFalse(list(validator.iter_errors(result)))
        result["lifecycle_status"] = "publication-qualified"
        self.assertTrue(list(validator.iter_errors(result)))

    def test_production_precompile_and_explicit_selection_cannot_bypass_evidence(self):
        from leo_ppt_generator.content_pack import compile_content_pack
        from leo_ppt_generator.content_projection import precompile_binding
        from leo_ppt_generator.layout_selection import allocate_deck
        from leo_ppt_generator.templates import resolve_design_context
        pack = compile_content_pack((ROOT / "references/authoring/page-expression-example.md").read_text(),
                                    master_path="references/authoring/page-expression-example.md")
        context = resolve_design_context("清爽专业风")
        page = pack["pages"][1]
        layout = "builtin:layout:p8-08-duo-compare-layouts"
        binding = precompile_binding(page, context, layout, content_digest=pack["content_digest"], numbers=pack["numbers"])
        self.assertFalse(binding["eligibility"]["qualified"])
        self.assertEqual(binding["eligibility"]["checks"]["qualification"]["status"], "unverified")
        self.assertTrue(any("positive_negative_evidence_missing" in reason for reason in binding["eligibility"]["hard_failures"]))
        pack["pages"] = [page]
        selection = allocate_deck(pack, context, candidates=[layout], explicit={page["page_id"]: layout})
        self.assertEqual(selection["status"], "explicit_unqualified")
        self.assertFalse(selection["selection"])
