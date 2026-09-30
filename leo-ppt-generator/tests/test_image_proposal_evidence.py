"""任务内 image proposal 的输入与准入回归；不运行或伪造真实 Provider。"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import shutil

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.capability_probes import image_probe_inputs, run_probes
from leo_ppt_generator.qualification import digest, file_reference
from leo_ppt_generator.raster_oracle import replay_image_probe_input
from leo_ppt_generator.storage import atomic_write_json
from leo_ppt_generator.task_local_layout_proposals import (
    apply_task_local_proposal, prepare_proposal_workspace, proposal_digest,
    proposal_probe_output, proposal_reference, image_proposal_scope,
    proposal_image_evidence_path, load_proposal_image_evidence, proposal_candidate_factory,
)

ROOT = Path(__file__).resolve().parents[1]


class ImageProposalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.context = {"effective": {}}
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        source = AssetResolver(library=ROOT / "template-library")
        pins = [source.fingerprint(identity) for identity in ("builtin:layout:p25-spec-table",
                "builtin:recipe:p25-spec-table", "builtin:template:spec-table")]
        source = source.freeze_assets(self.root / "source", pins)
        from leo_ppt_generator.qualification import ORACLE_PATH
        (source.builtin_root / ORACLE_PATH).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "template-library" / ORACLE_PATH, source.builtin_root / ORACLE_PATH)
        self.resolver = prepare_proposal_workspace(source, run_root=self.root / "run",
            run_scope="image-proposal-test", input_digest="a" * 64)
        self.library = self.resolver.builtin_root
        self.profile = self.resolver.resolve("builtin:layout:p25-spec-table")["data"]
        self.document = {"schema_version": 1, "run_scope": "image-proposal-test",
            "base_asset": self.profile["asset_id"], "base_generation": self.resolver.generation,
            "base_asset_digest": digest(self.profile), "candidates": [
                {"candidate_id": "image-fit", "lane": "image", "ops": [
                    {"op": "set_span", "target": "content", "value": {"width": 1040, "height": 550},
                     "base_asset": self.profile["asset_id"], "lane": "image"}]}]}
        self.document["proposal_digest"] = proposal_digest(self.document)
        theme = {key: deepcopy(self.context["effective"].get(key, {})) for key in ("colors", "fonts", "chart_palette")}
        self.proposal = apply_task_local_proposal(self.document, base_profile=self.profile,
            base_generation=self.resolver.generation, run_scope="image-proposal-test",
            allowed_assets={self.profile["asset_id"]}, content={"page_id": "comparison", "expression": {"relation": {"kind": "comparison"}},
                "structures": {"table": {"columns": ["维度", "甲", "乙"], "rows": [["时长", "6", "2"]]}},
                "claim": "比较结果", "items": [], "required_text": []}, theme=theme)[0]
        atomic_write_json(self.library / proposal_reference(self.proposal), self.proposal)
        self.cases = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())
        self.cases["cases"] = [case for case in self.cases["cases"] if case["relation"] == "comparison"]

    def test_positive_negative_inputs_use_the_same_replayed_patch_and_preserve_facts(self):
        before = deepcopy((self.cases, self.proposal, self.profile))
        rows = image_probe_inputs(library_root=self.library, cases=self.cases, proposal=self.proposal)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["status"], "not_run")
            layout = json.loads(row["input"]["prompt"].split("结构与槽位：", 1)[1])
            self.assertEqual(layout["regions"]["content"]["width"], 1040)
            self.assertEqual(layout["probe_scope"]["proposal_sha256"], digest(self.proposal))
            self.assertEqual(layout["probe_scope"]["run_scope"], "image-proposal-test")
            content = json.loads(row["input"]["prompt"].split("正文与事实：", 1)[1].split("\n表达合同：", 1)[0])
            self.assertEqual(content, self.cases["cases"][0][row["probe"]])
        self.assertEqual(before, (self.cases, self.proposal, self.profile))

    def test_image_proposal_with_no_provider_evidence_stays_blocked(self):
        report = run_probes(library_root=self.library, cases=self.cases,
            output=proposal_probe_output(self.proposal), proposal=self.proposal)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(report["results"][0]["lane"], "image")
        self.assertEqual(report["results"][0]["qualification_status"], "unverified")
        self.assertFalse(report["publication_ready"])

    def test_resealed_profile_and_cross_run_scope_fail_before_evidence_or_render(self):
        for mutation in ("profile", "scope", "lane", "base"):
            proposal = deepcopy(self.proposal)
            if mutation == "profile": proposal["profile"]["regions"]["content"]["width"] += 1
            elif mutation == "scope": proposal["run_scope"] = "another-run"
            elif mutation == "lane": proposal["lane"] = "render:html"
            else: proposal["base_asset"] = "builtin:layout:other"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                image_probe_inputs(library_root=self.library, cases=self.cases, proposal=proposal)

    def test_slot_permutation_is_in_both_probe_prompts_without_altering_fixture_content(self):
        document = deepcopy(self.document)
        for left, right in (("rows", "columns"), ("columns", "rows")):
            document["candidates"][0]["ops"].append({"op": "set_slot_mapping", "target": left,
                "value": right, "base_asset": self.profile["asset_id"], "lane": "image"})
        document["proposal_digest"] = proposal_digest(document)
        proposal = apply_task_local_proposal(document, base_profile=self.profile,
            base_generation=self.resolver.generation, run_scope="image-proposal-test",
            allowed_assets={self.profile["asset_id"]}, content=self.proposal["content"], theme=self.proposal["theme"])[0]
        atomic_write_json(self.library / proposal_reference(proposal), proposal)
        for row in image_probe_inputs(library_root=self.library, cases=self.cases, proposal=proposal):
            layout = json.loads(row["input"]["prompt"].split("结构与槽位：", 1)[1])
            self.assertEqual(layout["slot_mapping"], {"rows": "columns", "columns": "rows"})
            self.assertEqual(layout["probe_scope"], image_proposal_scope(proposal))

    def frozen_probe(self):
        from leo_ppt_generator.qualification import layout_capability_contract
        base = self.resolver.resolve(self.profile["asset_id"])
        _, dependencies = layout_capability_contract(base, resolver=self.resolver, lane="image", proposal=self.proposal)
        case = self.cases["cases"][0]
        fixture = {"expected": case["expected"], "data": case["positive"], "case_id": case["case_id"], "probe": "positive"}
        return fixture, dependencies

    def test_frozen_source_replay_matches_prepared_prompt_without_current_catalog(self):
        expected = image_probe_inputs(library_root=self.library, cases=self.cases, proposal=self.proposal)[0]["input"]
        fixture, dependencies = self.frozen_probe()
        frozen = self.root / "detached-evidence"
        for relative in dependencies:
            destination = frozen / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.library / relative, destination)
        actual, proposal = replay_image_probe_input(root=frozen, fixture=fixture, relation="comparison", dependencies=dependencies)
        self.assertEqual(actual, expected)
        self.assertEqual(proposal, self.proposal)
        self.assertFalse((frozen / "catalog/current.json").exists())

    def test_frozen_source_replay_rejects_base_and_resealed_patch_tampering(self):
        fixture, dependencies = self.frozen_probe()
        original_path = proposal_reference(self.proposal)
        changed = deepcopy(self.proposal)
        changed["profile"]["regions"]["content"]["width"] += 1
        changed_path = proposal_reference(changed)
        atomic_write_json(self.library / changed_path, changed)
        forged = {path: value for path, value in dependencies.items() if path != original_path}
        forged[changed_path] = file_reference(self.library, changed_path)["sha256"]
        with self.assertRaisesRegex(ValueError, "proposal_snapshot_changed"):
            replay_image_probe_input(root=self.library, fixture=fixture, relation="comparison", dependencies=forged)
        base_path = next(path for path in dependencies if path.endswith("/layout.json"))
        base = json.loads((self.library / base_path).read_text())
        base["regions"]["content"]["width"] -= 1
        atomic_write_json(self.library / base_path, base)
        for reseal in (False, True):
            forged = dict(dependencies)
            if reseal:
                forged[base_path] = file_reference(self.library, base_path)["sha256"]
            with self.subTest(resealed=reseal), self.assertRaises(ValueError):
                replay_image_probe_input(root=self.library, fixture=fixture, relation="comparison", dependencies=forged)

    def test_frozen_source_replay_rejects_relation_and_dependency_scope_changes(self):
        fixture, dependencies = self.frozen_probe()
        with self.assertRaisesRegex(ValueError, "image_proposal_evidence_scope_mismatch"):
            replay_image_probe_input(root=self.library, fixture=fixture, relation="independent", dependencies=dependencies)
        for suffix in ("/recipe.json", "/layout.json"):
            incomplete = {path: value for path, value in dependencies.items() if not path.endswith(suffix)}
            with self.subTest(missing=suffix), self.assertRaises(ValueError):
                replay_image_probe_input(root=self.library, fixture=fixture, relation="comparison", dependencies=incomplete)

    def evidence_document(self):
        prefix = Path(proposal_image_evidence_path(self.proposal)).parent
        evidence = {}
        for probe in ("positive", "negative"):
            refs = {}
            for kind in ("provider_receipt", "raster_review"):
                relative = (prefix / probe / (kind + ".json")).as_posix()
                atomic_write_json(self.library / relative, {"test_only": True, "status": "not_run"})
                refs[kind] = file_reference(self.library, relative)
            evidence[probe] = refs
        return {"schema_version": 1, "kind": "image-proposal-evidence",
                "scope": image_proposal_scope(self.proposal), "cases": {"comparison": evidence}}

    def test_import_references_require_complete_same_run_same_proposal_same_root(self):
        path = proposal_image_evidence_path(self.proposal)
        document = self.evidence_document()
        atomic_write_json(self.library / path, document)
        self.assertEqual(load_proposal_image_evidence(self.proposal, root=self.library, cases=self.cases), document["cases"])
        for mutation in ("run", "digest", "base", "page", "lane", "missing-negative", "outside", "traversal", "hash", "symlink"):
            changed = deepcopy(document)
            if mutation in {"run", "digest", "base", "page", "lane"}:
                key = {"run": "run_scope", "digest": "proposal_sha256", "base": "base_asset", "page": "page_id", "lane": "lane"}[mutation]
                changed["scope"][key] = "another"
            elif mutation == "missing-negative": del changed["cases"]["comparison"]["negative"]
            else:
                ref = changed["cases"]["comparison"]["positive"]["provider_receipt"]
                if mutation == "outside": ref["path"] = "evidence/capability-receipts.json"
                elif mutation == "traversal": ref["path"] = str(Path(path).parent / ".." / "another.json")
                elif mutation == "hash": ref["sha256"] = "0" * 64
                else:
                    original = self.library / ref["path"]
                    linked = original.with_name("linked.json")
                    linked.symlink_to(original)
                    ref["path"] = linked.relative_to(self.library).as_posix()
            atomic_write_json(self.library / path, changed)
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, OSError)):
                load_proposal_image_evidence(self.proposal, root=self.library, cases=self.cases)

    def test_factory_returns_specific_gap_and_never_qualifies_missing_image_exports(self):
        page = self.proposal["content"]
        factory = proposal_candidate_factory({page["page_id"]: self.document}, resolver=self.resolver,
            run_scope="image-proposal-test", design_context=self.context, probe_cases=self.cases)
        rows = factory(page, "image")
        self.assertEqual(rows, [{"candidate_id": "image-fit", "lane": "image", "status": "failed",
                                "gap": "image_proposal_provider_and_geometry_evidence_required"}])
        self.assertFalse((self.library / proposal_probe_output(self.proposal)).exists())
        with self.assertRaisesRegex(ValueError, "proposal_recursive_attempt"):
            factory(page, "image")

    def test_imported_non_provider_files_fail_the_same_probe_gate(self):
        document = self.evidence_document()
        atomic_write_json(self.library / proposal_image_evidence_path(self.proposal), document)
        page = self.proposal["content"]
        factory = proposal_candidate_factory({page["page_id"]: self.document}, resolver=self.resolver,
            run_scope="image-proposal-test", design_context=self.context, probe_cases=self.cases)
        rows = factory(page, "image")
        self.assertEqual(rows, [self.proposal])
        report = json.loads((self.library / proposal_probe_output(self.proposal) / "report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["results"][0]["qualification_status"], "rejected")
        self.assertEqual(len(report["results"][0]["gaps"]), 2)
        from leo_ppt_generator.qualification import qualify_layout
        qualification = qualify_layout(self.resolver.resolve(self.profile["asset_id"]), resolver=self.resolver,
            relation="comparison", lane="image", proposal=self.proposal)
        self.assertNotEqual(qualification["status"], "publication-qualified")
        self.assertNotEqual(qualification["status"], "provisional")

    def test_cached_probe_cannot_escape_its_task_scope(self):
        output = proposal_probe_output(self.proposal)
        run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
        scope_root = self.resolver.builtin_root.parent.parent
        marker = json.loads((scope_root / "scope.json").read_text())
        marker["run_scope"] = "another-run"
        atomic_write_json(scope_root / "scope.json", marker)
        with self.assertRaisesRegex(ValueError, "proposal_run_scope_mismatch"):
            run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)

    def v2_workspace(self):
        from leo_ppt_generator.library_migration import materialize_shadow_library
        from leo_ppt_generator.template_catalog import LibraryContext, build_catalog, publish_catalog
        source = self.root / "v1-for-v2"
        shutil.copytree(self.library, source)
        shutil.copyfile(ROOT / "template-library/library.json", source / "library.json")
        shutil.copytree(ROOT / "template-library/governance", source / "governance", dirs_exist_ok=True)
        library = self.root / "v2"
        materialize_shadow_library(source, library)
        publish_catalog(library, build_catalog(library))
        resolver = AssetResolver(context=LibraryContext(library))
        self.resolver = prepare_proposal_workspace(resolver, run_root=self.root / "v2-run",
            run_scope="image-proposal-test", input_digest="b" * 64)
        self.library = self.resolver.builtin_root
        self.document["base_generation"] = self.resolver.generation
        self.document["proposal_digest"] = proposal_digest(self.document)
        self.proposal = apply_task_local_proposal(self.document, base_profile=self.profile,
            base_generation=self.resolver.generation, run_scope="image-proposal-test",
            allowed_assets={self.profile["asset_id"]}, content=self.proposal["content"], theme=self.proposal["theme"])[0]
        atomic_write_json(self.library / proposal_reference(self.proposal), self.proposal)
        return library, resolver

    def test_v2_proposal_inputs_and_blocked_probe_replay_use_fixed_execution_snapshot(self):
        _, source = self.v2_workspace()
        rows = image_probe_inputs(library_root=self.library, cases=self.cases, proposal=self.proposal)
        self.assertEqual(len(rows), 2)
        output = proposal_probe_output(self.proposal)
        first = run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
        self.assertEqual(first["status"], "blocked")
        self.assertEqual(first["results"][0]["qualification_status"], "unverified")
        self.assertFalse(first["publication_ready"])
        second = run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
        self.assertEqual(second, first)
        self.assertEqual(image_probe_inputs(library_root=self.library, cases=self.cases, proposal=self.proposal), rows)
        resumed = prepare_proposal_workspace(source, run_root=self.root / "v2-run",
            run_scope="image-proposal-test", input_digest="b" * 64)
        self.assertEqual(resumed.fingerprint(self.profile["asset_id"]), self.resolver.fingerprint(self.profile["asset_id"]))
        # 活动 reader 仍须拒绝陈旧 catalog，取证修复不能放松通用 execution 门。
        with self.assertRaisesRegex(ValueError, "stale_catalog"):
            AssetResolver(library=self.library).entities

    def test_v2_proposal_rejects_canonical_scope_and_snapshot_drift_before_cached_result(self):
        self.v2_workspace()
        output = proposal_probe_output(self.proposal)
        run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
        targets = [Path(self.resolver.resolve(self.profile["asset_id"])["path"]),
                   self.library.parent / "asset-snapshot.json",
                   self.library.parent.parent / "scope.json"]
        for target in targets:
            original = target.read_bytes()
            try:
                changed = json.loads(original)
                if target.name == "scope.json":
                    changed["run_scope"] = "another-run"
                else:
                    changed["external-change"] = True
                atomic_write_json(target, changed)
                with self.subTest(path=target.name), self.assertRaises(ValueError):
                    run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
            finally:
                target.write_bytes(original)

    def test_v2_cached_proposal_rejects_output_environment_receipt_and_unlisted_bytes(self):
        import os
        self.v2_workspace()
        output = proposal_probe_output(self.proposal)
        report = run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
        previous = os.environ.get("LEO_PPT_RENDER_CHROMIUM")
        try:
            os.environ["LEO_PPT_RENDER_CHROMIUM"] = str(self.root / "different-browser")
            with self.assertRaisesRegex(ValueError, "probe_input_conflict"):
                run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
        finally:
            if previous is None:
                os.environ.pop("LEO_PPT_RENDER_CHROMIUM", None)
            else:
                os.environ["LEO_PPT_RENDER_CHROMIUM"] = previous
        for name in ("environment.json", "capability-receipts.json", "report.json"):
            target = self.library / output / name
            original = target.read_bytes()
            try:
                document = json.loads(original)
                document["tampered"] = True
                atomic_write_json(target, document)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
            finally:
                target.write_bytes(original)
        extra = self.library / output / "unlisted/report.json"
        atomic_write_json(extra, {})
        with self.assertRaisesRegex(ValueError, "probe_cache_file_set_mismatch"):
            run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
        extra.unlink()
        other = self.library / "evidence/probes/proposal-other/external.json"
        atomic_write_json(other, {})
        with self.assertRaisesRegex(ValueError, "probe_input_files_changed"):
            run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal)
        other.unlink()
        self.assertEqual(run_probes(library_root=self.library, cases=self.cases, output=output, proposal=self.proposal), report)

    def test_v2_live_html_probe_cache_allows_only_its_own_output_change(self):
        library, _ = self.v2_workspace()
        output = "evidence/probes/v2-cache-replay"
        report = run_probes(library_root=library, cases=self.cases, output=output)
        self.assertEqual(next(row for row in report["results"] if row["lane"] == "render:html")["status"], "passed")
        self.assertEqual(run_probes(library_root=library, cases=self.cases, output=output), report)
        for relative in ("evidence/external.json", "catalog/current.json", "canonical/executable/layouts/p25-spec-table/layout.json"):
            path = library / relative
            original = path.read_bytes() if path.exists() else None
            try:
                atomic_write_json(path, {"external": True})
                with self.subTest(path=relative), self.assertRaises(ValueError):
                    run_probes(library_root=library, cases=self.cases, output=output)
            finally:
                path.unlink() if original is None else path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
