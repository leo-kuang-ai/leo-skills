#!/usr/bin/env python3
"""按冻结用例运行真实关系探针；只写证据，不自动发布 catalog 或授予资格。"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.qualification import (
    ORACLE_PATH, asset_generation, digest, environment_fingerprint, evidence_digest,
    file_reference, layout_capability_contract, read_evidence_bytes, verify_reference,
    evidence_closure,
)
from leo_ppt_generator.relation_oracle import evaluate_output, validate_expectation
from leo_ppt_generator.render.page import RenderSession, render_page
from leo_ppt_generator.storage import atomic_write_json


def image_probe_inputs(*, library_root, cases):
    """生成待授权调用的真实 recipe 输入；不调用 Provider，不授予资格。"""
    from .library_migration import library_operation
    with library_operation(library_root):
        from .raster_oracle import image_probe_input
        resolver = AssetResolver(library=Path(library_root).resolve(strict=True))
        result = []
        for case in cases["cases"]:
            layout = resolver.resolve(case["layout_id"])
            contract, _ = layout_capability_contract(layout, resolver=resolver, lane="image")
            gaps = contract["gaps"].get("image", [])
            if case["relation"] not in contract["relations"]:
                gaps = [*gaps, "relation_not_declared"]
            if "image" not in contract["lanes"] or gaps:
                result.append({"case_id": case["case_id"], "status": "blocked", "gaps": gaps or ["image_lane_unsupported"]})
                continue
            recipe = resolver.resolve(layout["data"]["image_recipe"])["data"]
            for name in ("positive", "negative"):
                fixture = {"expected": case["expected"], "data": case[name], "case_id": case["case_id"], "probe": name}
                result.append({"case_id": case["case_id"], "probe": name, "status": "not_run",
                               "input": image_probe_input(recipe, fixture, case["relation"])})
        return result


def _run_image_case(*, case, layout, resolver, evidence, root, write, identity, generation, oracle, oracle_ref, env_ref):
    from .raster_oracle import evaluate_raster_output, image_probe_input, verify_image_probe_source
    contract, dependencies = layout_capability_contract(layout, resolver=resolver, lane="image")
    owner_gaps = contract["gaps"].get("image", [])
    if "image" not in contract["lanes"]:
        owner_gaps = [*owner_gaps, "image_lane_unsupported"]
    if case["relation"] not in contract["relations"]:
        owner_gaps = [*owner_gaps, "relation_not_declared"]
    row = {"case_id": case["case_id"], "relation": case["relation"], "lane": "image", "receipt": None,
           "status": "blocked", "qualification_status": "rejected" if owner_gaps else "unverified",
           "owner_gaps": owner_gaps, "gaps": []}
    if not evidence or owner_gaps:
        row["gaps"] = owner_gaps or ["image_provider_and_geometry_evidence_required"]
        return row, None
    if set(evidence) != {"positive", "negative"}:
        raise ValueError("image_probe_evidence_incomplete")
    recipe = resolver.resolve(layout["data"]["image_recipe"])["data"]
    probes = {}
    for name in ("positive", "negative"):
        prefix = case["case_id"] + "/image-" + name
        try:
            supplied = evidence[name]
            if set(supplied) != {"provider_receipt", "raster_review"}:
                raise ValueError("image_probe_evidence_invalid")
            provider_ref, review_ref = supplied["provider_receipt"], supplied["raster_review"]
            provider = json.loads(verify_reference(root, provider_ref))
            artifact = {**provider["artifact"], "path": (PurePosixPath(provider_ref["path"]).parent / provider["artifact"]["path"]).as_posix()}
            fixture_data = {"expected": case["expected"], "data": case[name], "case_id": case["case_id"], "probe": name}
            fixture = write(prefix + "-fixture.json", fixture_data)
            data = write(prefix + "-input.json", image_probe_input(recipe, fixture_data, case["relation"]))
            verify_image_probe_source(root=root, fixture=fixture_data, relation=case["relation"], artifact=artifact,
                                      render_input=data, provider_reference=provider_ref, dependencies=dependencies)
            evaluated = evaluate_raster_output(case["expected"], verify_reference(root, artifact),
                json.loads(verify_reference(root, review_ref)), relation=case["relation"], oracle=oracle,
                environment_sha256=env_ref["sha256"])
            measurement = write(prefix + "-measurement.json", evaluated["measurement"])
            checks = evaluated["checks"]
            accepted = all(checks.values())
            passed = accepted if name == "positive" else not accepted and not checks[oracle["relations"][case["relation"]]["negative_check"]]
            observation = write(prefix + "-observation.json", {"artifact": artifact, "fixture": fixture,
                "oracle_sha256": oracle_ref["sha256"], "environment_sha256": env_ref["sha256"],
                "lane": "image", "relation": case["relation"], "measurement": measurement,
                "render_input": data, "raster_review": review_ref, "checks": checks})
            probes[name] = {"status": "passed" if passed else "failed", "fixture": fixture, "artifact": artifact,
                            "provider_receipt": provider_ref, "observation": observation}
            if not passed:
                row["gaps"].append({"probe": name, "failed_checks": [k for k, v in checks.items() if not v],
                                    "negative_incorrectly_accepted": name == "negative" and accepted})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            row["gaps"].append({"probe": name, "reason": type(exc).__name__, "detail": str(exc)[:1000]})
    receipt = None
    if len(probes) == 2:
        receipt = {"schema_version": 1, "kind": "capability-evidence", "receipt_id": identity + "/image/" + case["case_id"],
            "asset_id": case["layout_id"], "asset_generation": generation, "lane": "image", "relation": case["relation"],
            "oracle": oracle_ref, "environment": env_ref, "dependency_hashes": dependencies,
            "probes": probes, "visual_review": None}
        receipt["evidence_digest"] = evidence_digest(receipt)
        row["receipt"] = write(case["case_id"] + "/image-receipt.json", receipt)
    row.update(status="failed" if row["gaps"] else "passed",
               qualification_status="rejected" if row["gaps"] else "provisional")
    return row, receipt


def run_probes(*, library_root, cases, output, proposal=None, image_evidence=None):
    from .library_migration import library_operation
    with library_operation(library_root):
        root = Path(library_root).resolve(strict=True)
        relative = PurePosixPath(output)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in output
                or len(relative.parts) < 3 or relative.parts[:2] != ("evidence", "probes")):
            raise ValueError("probe_output_scope_invalid")
        directory = root / relative
        if any(p.is_symlink() for p in (directory, *directory.parents)):
            raise ValueError("probe_output_scope_invalid")
        oracle = json.loads(read_evidence_bytes(root, ORACLE_PATH))
        if not isinstance(cases, dict) or set(cases) != {"schema_version", "owner", "cases"} or cases["schema_version"] != 1 or not cases["owner"]:
            raise ValueError("probe_cases_invalid")
        ids = set()
        for case in cases["cases"]:
            if set(case) != {"case_id", "relation", "layout_id", "expected", "positive", "negative"}:
                raise ValueError("probe_case_invalid")
            import re
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", case["case_id"]) or case["case_id"] in ids:
                raise ValueError("probe_case_identity_invalid")
            ids.add(case["case_id"])
            validate_expectation(case["expected"], case["relation"])
        if not ids:
            raise ValueError("probe_cases_empty")
        if proposal is not None and image_evidence:
            raise ValueError("proposal_probe_scope_mismatch")
        generation, environment = asset_generation(root), environment_fingerprint()
        if image_evidence is not None and (not isinstance(image_evidence, dict) or not set(image_evidence).issubset(ids)):
            raise ValueError("image_probe_evidence_scope_invalid")
        identity = digest({"cases": cases, "asset_generation": generation, "environment": environment,
                           "proposal": proposal, "image_evidence": image_evidence})
        if directory.exists():
            report = json.loads(read_evidence_bytes(root, (relative / "report.json").as_posix()))
            if report["input_digest"] != identity:
                raise ValueError("probe_input_conflict")
            for reference in report["files"]:
                verify_reference(root, reference)
            return report
        # 先固定现有 catalog；探针自身追加 evidence 后当前代应变 stale，不能边写边重新发现。
        resolver = AssetResolver(library=root)
        resolver.entities
        directory.mkdir(parents=True)

        def write(name, value):
            path = relative / name
            atomic_write_json(root / path, value)
            return file_reference(root, path.as_posix())

        write("cases.json", cases)
        env_ref = write("environment.json", environment)
        oracle_ref = {**file_reference(root, ORACLE_PATH), "owner": oracle["owner"], "version": oracle["version"]}
        results, receipts = [], []
        with RenderSession() as session:
            for case in cases["cases"]:
                layout = resolver.resolve(case["layout_id"])
                if proposal is not None and (proposal["base_asset"] != case["layout_id"] or proposal["lane"] != "render:html"):
                    raise ValueError("proposal_probe_scope_mismatch")
                contract, dependencies = layout_capability_contract(layout, resolver=resolver, lane="render:html", proposal=proposal)
                template_id = layout["data"].get("renderer_support", {}).get("render:html")
                probes, gaps = {}, []
                for name in ("positive", "negative"):
                    prefix = case["case_id"] + "/" + name
                    fixture = write(prefix + "-fixture.json", {"expected": case["expected"], "data": case[name], "case_id": case["case_id"], "probe": name})
                    data = write(prefix + "-input.json", case[name])
                    image_path = relative / (prefix + ".png")
                    measurement_path = relative / (prefix + "-measurement.json")
                    try:
                        rendered = render_page(template_id, root / data["path"], root / image_path,
                            resolver=resolver, session=session, observation_path=root / measurement_path,
                            probe_proposal=proposal)
                        measurement = json.loads(read_evidence_bytes(root, measurement_path.as_posix()))
                        checks = evaluate_output(case["expected"], measurement, relation=case["relation"], oracle=oracle)
                        accepted = all(checks.values())
                        passed = accepted if name == "positive" else (not accepted and not checks[oracle["relations"][case["relation"]]["negative_check"]])
                        artifact = file_reference(root, image_path.as_posix())
                        observation = write(prefix + "-observation.json", {
                            "artifact": artifact, "fixture": fixture, "oracle_sha256": oracle_ref["sha256"],
                            "environment_sha256": env_ref["sha256"], "lane": "render:html", "relation": case["relation"],
                            "measurement": file_reference(root, measurement_path.as_posix()), "render_input": data, "checks": checks})
                        probes[name] = {"status": "passed" if passed else "failed", "fixture": fixture,
                            "artifact": artifact, "observation": observation}
                        if not passed:
                            gaps.append({"probe": name, "failed_checks": [k for k, v in checks.items() if not v],
                                         "negative_incorrectly_accepted": name == "negative" and accepted})
                    except (ValueError, RuntimeError, OSError) as exc:
                        gaps.append({"probe": name, "reason": getattr(exc, "reason_code", type(exc).__name__), "detail": str(exc)[:1000]})
                if len(probes) == 2:
                    receipt = {"schema_version": 1, "kind": "capability-evidence", "receipt_id": identity + "/" + case["case_id"],
                        "asset_id": case["layout_id"], "asset_generation": generation, "lane": "render:html", "relation": case["relation"],
                        "oracle": oracle_ref, "environment": env_ref, "dependency_hashes": dependencies,
                        "probes": probes, "visual_review": None}
                    receipt["evidence_digest"] = evidence_digest(receipt)
                    receipts.append(receipt)
                    receipt_ref = write(case["case_id"] + "/receipt.json", receipt)
                else:
                    receipt_ref = None
                owner_gaps = contract["gaps"].get("render:html", [])
                if case["relation"] not in contract["relations"]:
                    owner_gaps = [*owner_gaps, "relation_not_declared"]
                results.append({"case_id": case["case_id"], "relation": case["relation"], "lane": "render:html",
                    "status": "passed" if not gaps else "failed", "gaps": gaps, "owner_gaps": owner_gaps,
                    "qualification_status": "rejected" if gaps or owner_gaps else "provisional", "receipt": receipt_ref})
                image_row, image_receipt = _run_image_case(case=case, layout=layout, resolver=resolver,
                    evidence=(image_evidence or {}).get(case["case_id"]), root=root, write=write, identity=identity,
                    generation=generation, oracle=oracle, oracle_ref=oracle_ref, env_ref=env_ref)
                results.append(image_row)
                if image_receipt is not None:
                    receipts.append(image_receipt)
        if generation != asset_generation(root) or environment != environment_fingerprint():
            raise ValueError("probe_inputs_changed_during_run")
        write("capability-receipts.json", {"receipts": receipts})
        files = {p.relative_to(root).as_posix(): file_reference(root, p.relative_to(root).as_posix())
                 for p in sorted(directory.rglob("*")) if p.is_file()}
        for reference in evidence_closure(root, receipts):
            files[reference["path"]] = reference
        report = {"schema_version": 1, "kind": "relation-probe-report", "input_digest": identity,
            "asset_generation": generation, "oracle": oracle_ref, "environment": env_ref, "results": results,
            "files": [files[p] for p in sorted(files)], "publication_ready": False,
            "status": "failed" if any(r["status"] == "failed" for r in results) else
                      "blocked" if any(r["status"] == "blocked" for r in results) else "passed"}
        write("report.json", report)
        return report
