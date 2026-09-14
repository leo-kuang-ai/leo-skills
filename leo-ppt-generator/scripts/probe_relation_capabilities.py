#!/usr/bin/env python3
"""按冻结用例运行真实关系探针；只写证据，不自动发布 catalog 或授予资格。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.qualification import (
    ORACLE_PATH, asset_generation, digest, environment_fingerprint, evidence_digest,
    file_reference, layout_capability_contract, read_evidence_bytes, verify_reference,
)
from leo_ppt_generator.relation_oracle import evaluate_output, validate_expectation
from leo_ppt_generator.render.page import RenderSession, render_page
from leo_ppt_generator.storage import atomic_write_json


def run_probes(*, library_root, cases, output):
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
    generation, environment = asset_generation(root), environment_fingerprint()
    identity = digest({"cases": cases, "asset_generation": generation, "environment": environment})
    if directory.exists():
        report = json.loads(read_evidence_bytes(root, (relative / "report.json").as_posix()))
        if report["input_digest"] != identity:
            raise ValueError("probe_input_conflict")
        for reference in report["files"]:
            verify_reference(root, reference)
        return report
    directory.mkdir(parents=True)

    def write(name, value):
        path = relative / name
        atomic_write_json(root / path, value)
        return file_reference(root, path.as_posix())

    write("cases.json", cases)
    env_ref = write("environment.json", environment)
    oracle_ref = {**file_reference(root, ORACLE_PATH), "owner": oracle["owner"], "version": oracle["version"]}
    resolver = AssetResolver(library=root)
    results, receipts = [], []
    with RenderSession() as session:
        for case in cases["cases"]:
            layout = resolver.resolve(case["layout_id"])
            contract, dependencies = layout_capability_contract(layout, resolver=resolver, lane="render:html")
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
                        resolver=resolver, session=session, observation_path=root / measurement_path)
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
            results.append({"case_id": case["case_id"], "relation": case["relation"], "lane": "image", "status": "blocked",
                "gaps": ["image_recipe_provider_output_oracle_required"], "qualification_status": "unverified", "receipt": None})
    if generation != asset_generation(root) or environment != environment_fingerprint():
        raise ValueError("probe_inputs_changed_during_run")
    write("capability-receipts.json", {"receipts": receipts})
    files = [file_reference(root, p.relative_to(root).as_posix()) for p in sorted(directory.rglob("*")) if p.is_file()]
    report = {"schema_version": 1, "kind": "relation-probe-report", "input_digest": identity,
        "asset_generation": generation, "oracle": oracle_ref, "environment": env_ref, "results": results,
        "files": files, "publication_ready": False,
        "status": "failed" if any(r["status"] == "failed" for r in results) else "blocked"}
    write("report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--out", required=True, help="库内 evidence/probes/<name> 相对路径")
    args = parser.parse_args(argv)
    try:
        result = run_probes(library_root=args.library_root, cases=json.loads(args.cases.read_text()), output=args.out)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] == "passed" else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
