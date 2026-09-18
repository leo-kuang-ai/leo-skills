"""基于固定输入、旧链字节和实际导出的 R-85/U6 回放；缺证据不签发通过。"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from contextvars import ContextVar
from copy import deepcopy
import io
import json
from pathlib import Path
import re

from PIL import Image

from .qualification import digest, environment_fingerprint, file_reference, read_evidence_bytes, verify_reference
from .storage import atomic_write_json

DIMENSIONS = {"fidelity", "relation", "readability", "focus"}
LANES = {"render:html", "image"}
_PUBLICATION_REPLAYS = ContextVar("capability_publication_replays", default=frozenset())


class ReplayError(ValueError):
    def __init__(self, reason, status="failed"):
        super().__init__(reason)
        self.status = status


def _exact(value, fields, reason):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ReplayError(reason, "error")


def _document(root, reference):
    if reference is None:
        raise ReplayError("replay_reference_missing", "blocked")
    _exact(reference, ("path", "sha256"), "replay_reference_invalid")
    try:
        return json.loads(verify_reference(root, reference))
    except FileNotFoundError as exc:
        raise ReplayError("replay_file_missing:" + reference["path"], "blocked") from exc
    except (ValueError, OSError) as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            raise ReplayError("replay_file_missing:" + reference["path"], "blocked") from exc
        raise ReplayError("replay_file_stale:" + reference["path"], "stale") from exc


def _sealed(document, field):
    if document.get(field) != digest({key: value for key, value in document.items() if key != field}):
        raise ReplayError(field + "_mismatch", "stale")


def _png(root, reference):
    try:
        body = verify_reference(root, reference)
        with Image.open(io.BytesIO(body)) as image:
            if image.format != "PNG" or image.size != (2560, 1440):
                raise ReplayError("replay_export_dimensions_invalid")
            image.verify()
    except FileNotFoundError as exc:
        raise ReplayError("replay_export_missing", "blocked") from exc


def _safe_directory(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ReplayError("replay_path_outside_root")
    path = Path(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in relative.split("/")) or "\\" in relative:
        raise ReplayError("replay_path_outside_root")
    result = Path(root) / path
    if any(p.is_symlink() for p in (result, *result.parents)):
        raise ReplayError("replay_path_outside_root")
    return result


def replay_run_path(root, plan, case):
    return _safe_directory(_safe_directory(root, plan["run_prefix"]), case["run"])


def capability_publication_files(library_root, bundle):
    """U6-A 附件必须是完整、可冻结的库内证据树，拒绝缺件、链接或目录外借证。"""
    _exact(bundle, ("root", "receipt", "files"), "capability_u6a_bundle_invalid")
    root = _safe_directory(library_root, bundle["root"])
    if not bundle["root"].startswith("evidence/replays/") or not root.is_dir():
        raise ReplayError("capability_u6a_root_invalid", "blocked")
    if not isinstance(bundle["files"], list) or not bundle["files"]:
        raise ReplayError("capability_u6a_files_missing", "blocked")
    listed = {}
    for reference in bundle["files"]:
        _exact(reference, ("path", "sha256"), "capability_u6a_reference_invalid")
        if reference["path"] in listed:
            raise ReplayError("capability_u6a_duplicate_file")
        verify_reference(root, reference)
        listed[reference["path"]] = reference["sha256"]
    actual = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ReplayError("capability_u6a_file_type_invalid")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            actual[relative] = file_reference(root, relative)["sha256"]
    if actual != listed or bundle["receipt"] not in bundle["files"]:
        raise ReplayError("capability_u6a_file_set_mismatch", "stale")
    return [{"path": bundle["root"] + "/" + path, "sha256": sha} for path, sha in sorted(listed.items())]


def verify_capability_publication(library_root, capability, bundle):
    """重算正式 A 回放，并确认通过页实际使用了待晋升的同一能力证据。"""
    from .application.expression_pipeline import load_committed_input
    files = capability_publication_files(library_root, bundle)
    root = _safe_directory(library_root, bundle["root"])
    key = str(root)
    active = _PUBLICATION_REPLAYS.get()
    if key in active:
        raise ReplayError("capability_u6a_recursive_dependency")
    token = _PUBLICATION_REPLAYS.set(active | {key})
    try:
        receipt = _document(root, bundle["receipt"])
        _sealed(receipt, "receipt_digest")
        if (receipt.get("kind") != "quality-replay-receipt" or receipt.get("phase") != "U6-A"
                or receipt.get("status") != "passed" or receipt.get("publication_ready") is not True):
            raise ReplayError("capability_u6a_not_passed", "blocked")
        current = evaluate_quality_replay(root, receipt.get("plan"), self_contained=True)
        if current != receipt or current["status"] != "passed" or not current["publication_ready"]:
            raise ReplayError("capability_u6a_not_passed_or_stale", "stale")
        # 晋升仅增加视觉引用；原正反探针、owner、环境和 generation 必须逐字相同。
        def probe_digest(value):
            return digest({k: v for k, v in value.items() if k not in {"visual_review", "evidence_digest"}})
        matched = False
        for row in current["cases"]:
            if row["status"] != "passed" or row.get("lane") != capability["lane"]:
                continue
            run = _safe_directory(root, row["run"])
            committed = load_committed_input(run)
            binding = next((binding for binding in committed["payload"]["bindings"][row["lane"]].values()
                            if binding["materialization_binding_digest"] == row["materialization_binding_digest"]), None)
            if binding is None or binding["layout_id"] != capability["asset_id"]:
                continue
            page = next(p for p in committed["payload"]["pack"]["pages"] if p["page_id"] == binding["page_id"])
            if page["expression"]["relation"]["kind"] != capability["relation"]:
                continue
            qualification = binding["eligibility"]["checks"]["qualification"]
            if any(probe_digest(value) == probe_digest(capability) for value in qualification["receipt_payloads"]):
                matched = True
        if not matched:
            raise ReplayError("capability_u6a_asset_evidence_unbound")
        if files != capability_publication_files(library_root, bundle):
            raise ReplayError("capability_u6a_changed_during_verification", "stale")
        return {"status": "passed", "receipt": bundle["receipt"], "files": files}
    finally:
        _PUBLICATION_REPLAYS.reset(token)


def replay_cases(plan, dataset):
    """A 执行固定全集，B 仅复验显式代表集；固定留出集摘要保持不变。"""
    if plan["phase"] == "U6-A":
        if plan["representatives"] is not None:
            raise ReplayError("r85_subset_not_allowed")
        return dataset["cases"]
    ids = plan["representatives"]
    known = {case["case_id"]: case for case in dataset["cases"]}
    if (not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or not set(ids).issubset(known)):
        raise ReplayError("delivery_representatives_invalid")
    cases = [known[identity] for identity in ids]
    if {case["lane"] for case in cases} != LANES:
        raise ReplayError("delivery_representatives_require_both_lanes", "blocked")
    return cases


def _execution_fingerprint(request):
    """拒答没有 committed generation，固定其实际源码和完整库输入供离线重算。"""
    from .application.expression_pipeline import _request_body
    package = Path(__file__).parent
    source = {path.relative_to(package).as_posix(): file_reference(package, path.relative_to(package).as_posix())["sha256"]
              for path in sorted(package.rglob("*")) if path.is_file() and path.suffix in {".py", ".json"}}
    library = Path(request.library_root).absolute()
    if any(path.is_symlink() for path in (library, *library.parents)):
        raise ReplayError("replay_library_path_invalid")
    files = {}
    for prefix in ("canonical", "governance", "evidence", "catalog"):
        for path in sorted((library / prefix).rglob("*")):
            if path.is_symlink():
                raise ReplayError("replay_library_path_invalid")
            if path.is_file():
                relative = path.relative_to(library).as_posix()
                files[relative] = file_reference(library, relative)["sha256"]
    files["library.json"] = file_reference(library, "library.json")["sha256"]
    body = _request_body(request)
    return {"request_digest": digest({k: v for k, v in body.items() if k not in {"run_root", "library_root"}}),
            "source_digest": digest(source), "library_digest": digest(files), "environment": environment_fingerprint()}


def _reproduce_rejection(request):
    from .asset_resolver import AssetResolver
    from .application.expression_pipeline import ExpressionPipelineError, qualify_pipeline_lane, _request_body
    from .content_pack import verify_content_pack
    verify_content_pack(request.pack)
    resolver = AssetResolver(library=Path(request.library_root))
    factory = None
    if request.proposals:
        body = _request_body(request)
        input_digest = digest({k: v for k, v in body.items() if k not in {"run_root", "library_root"}})
        workspace = Path(request.run_root) / ".proposal-work" / input_digest
        scope = json.loads(read_evidence_bytes(workspace, "scope.json"))
        if scope["run_scope"] != request.run_id:
            raise ReplayError("proposal_run_scope_mismatch", "stale")
        resolver = AssetResolver.from_snapshot(workspace / "asset-snapshot")
        from .task_local_layout_proposals import proposal_candidate_factory
        factory = proposal_candidate_factory(request.proposals, resolver=resolver, run_scope=request.run_id,
            design_context=request.design_context, probe_cases=request.proposal_probe_cases, read_only=True)
    if resolver.generation != request.catalog_generation:
        raise ReplayError("replay_rejection_catalog_stale", "stale")
    for lane in sorted({lane for lanes in request.lane_matrix.values() for lane in lanes}):
        selected = qualify_pipeline_lane(request, lane, resolver=resolver, proposal_factory=factory)
        if selected["status"] != "complete":
            return ExpressionPipelineError(selected["status"], phase="qualification", details=selected["page_status"]).as_dict()
    return None


def execute_replay_request(root, case, request, *, execute=False, library_root=None, self_contained=False):
    """持久化真实失败；重核共享资格算法，不相信可手改的 status/reason 字段。"""
    from dataclasses import replace
    from .application.expression_pipeline import ExpressionPipelineError
    from .application.routes import generate
    run = Path(request.run_root)
    path = run / "qa/replay-execution.json"
    relative = path.relative_to(root).as_posix()
    _safe_directory(root, relative)
    if execute:
        if library_root is None:
            raise ReplayError("replay_library_context_missing", "blocked")
        request = replace(request, library_root=str(Path(library_root).absolute()))
        start = _execution_fingerprint(request)
        log = run / "qa/replay-execution.log"
        _safe_directory(root, log.relative_to(root).as_posix())
        log.parent.mkdir(parents=True, exist_ok=True)
        failure = None
        with log.open("w") as handle, redirect_stdout(handle), redirect_stderr(handle):
            try:
                generate(request)
            except ExpressionPipelineError as exc:
                failure = exc.as_dict()
                print(json.dumps(failure, ensure_ascii=False))
        if start != _execution_fingerprint(request):
            raise ReplayError("replay_execution_inputs_changed", "stale")
        execution_library = Path(request.library_root).absolute()
        stored_library = (execution_library.relative_to(root).as_posix()
                          if execution_library.is_relative_to(root) else str(execution_library))
        receipt = {"schema_version": 1, "kind": "replay-execution", "request": case["request"],
            "run_id": request.run_id, "library_root": stored_library, "fingerprint": start,
            "failure": failure, "log": file_reference(root, log.relative_to(root).as_posix())}
        receipt["receipt_digest"] = digest(receipt)
        atomic_write_json(path, receipt)
    elif not path.exists():
        return None
    receipt = _document(root, file_reference(root, relative))
    _sealed(receipt, "receipt_digest")
    if (receipt.get("kind") != "replay-execution" or receipt.get("request") != case["request"]
            or receipt.get("run_id") != request.run_id):
        raise ReplayError("replay_execution_receipt_mismatch", "stale")
    recorded_library = Path(receipt["library_root"])
    if not recorded_library.is_absolute():
        recorded_library = _safe_directory(root, receipt["library_root"])
    request = replace(request, library_root=str(recorded_library))
    if self_contained:
        library = Path(request.library_root).absolute()
        if not library.is_relative_to(Path(root).absolute()):
            raise ReplayError("capability_u6a_external_execution_library", "blocked")
        _safe_directory(root, library.relative_to(root).as_posix())
    if receipt["fingerprint"] != _execution_fingerprint(request):
        raise ReplayError("replay_execution_inputs_stale", "stale")
    verify_reference(root, receipt["log"])
    failure = receipt["failure"]
    if failure is not None:
        if failure.get("phase") != "qualification":
            raise ReplayError("replay_execution_failed_outside_qualification", "blocked")
        if failure != _reproduce_rejection(request):
            raise ReplayError("replay_rejection_not_reproducible", "stale")
    return failure


def attach_replay_receipt(root, reference):
    """各 run 只保存显式引用；完整回放证据仍由任务根统一拥有。"""
    root = Path(root).absolute()
    report = _document(root, reference)
    _sealed(report, "receipt_digest")
    for relative in sorted({row["run"] for row in report["cases"]}):
        run = _safe_directory(root, relative)
        if not run.is_dir():
            continue
        target = _safe_directory(root, relative + "/qa/visual-replay.json")
        atomic_write_json(target, {"schema_version": 1, "kind": "quality-replay-attachment",
            "evidence_root": str(root), "run": relative, "receipt": reference})


def verify_legacy_baseline(root, reference):
    baseline = _document(root, reference)
    _exact(baseline, ("schema_version", "kind", "source_revision", "source_snapshot", "dirty_hashes",
        "capture_mode", "environment", "pages", "baseline_digest"), "baseline_schema_mismatch")
    if (baseline["schema_version"] != 1 or baseline["kind"] != "legacy-visual-baseline"
            or not re.fullmatch(r"[0-9a-f]{40}", baseline["source_revision"])
            or baseline["capture_mode"] not in {"captured-before-change", "reconstructed-historical"}):
        raise ReplayError("baseline_source_identity_invalid")
    _sealed(baseline, "baseline_digest")
    sources = baseline["source_snapshot"]
    if not isinstance(sources, dict) or not sources:
        raise ReplayError("baseline_source_snapshot_missing", "blocked")
    for path, sha in sources.items():
        verify_reference(root, {"path": path, "sha256": sha})
    from .qualification import is_execution_source
    execution = {}
    for path, sha in sources.items():
        if "/leo_ppt_generator/" in path:
            relative = path.split("/leo_ppt_generator/", 1)[1]
            if is_execution_source(relative):
                execution[relative] = sha
    if ("render/page.py" not in execution
            or digest(execution) != baseline["environment"].get("execution_source_digest")):
        raise ReplayError("baseline_execution_snapshot_incomplete", "blocked")
    if any(sources.get(path) != sha for path, sha in baseline["dirty_hashes"].items()):
        raise ReplayError("baseline_dirty_snapshot_mismatch", "stale")
    identities, artifacts = set(), set()
    if not baseline["pages"]:
        raise ReplayError("baseline_exports_missing", "blocked")
    for page in baseline["pages"]:
        _exact(page, ("case_id", "deck_id", "page_id", "lane", "theme_family", "material", "selection",
                      "artifact", "receipt", "provider_contract_digest"), "baseline_page_schema_mismatch")
        if page["case_id"] in identities or page["artifact"]["path"] in artifacts or page["lane"] not in LANES:
            raise ReplayError("baseline_page_identity_collision")
        identities.add(page["case_id"]); artifacts.add(page["artifact"]["path"])
        verify_reference(root, page["material"])
        _png(root, page["artifact"])
        selected = _document(root, page["selection"])
        receipt = _document(root, page["receipt"])
        if (receipt.get("out_sha256") != page["artifact"]["sha256"]
                or (receipt.get("width"), receipt.get("height")) != (2560, 1440)):
            raise ReplayError("baseline_receipt_artifact_mismatch", "stale")
        if page["lane"] == "render:html":
            if (receipt.get("kind") != "render_provenance" or receipt.get("backend") != "render:html"
                    or receipt.get("overflow_check") != "pass" or not receipt.get("renderer")
                    or receipt.get("template_id") != selected.get("template_id")
                    or receipt.get("template_sha256") not in {sha for path, sha in sources.items() if path.endswith(".html")}
                    or receipt.get("data_sha256") != selected.get("input", {}).get("sha256")):
                raise ReplayError("baseline_execution_source_mismatch")
            verify_reference(root, selected["input"])
        else:
            if not selected.get("binding"):
                raise ReplayError("baseline_provider_binding_missing", "blocked")
            from .image_deck.expression_adapter import verify_provider_export
            verify_provider_export(receipt, root=(Path(root) / page["receipt"]["path"]).parent,
                                   binding=selected["binding"])
    return baseline


def freeze_legacy_baseline(root, descriptor, output):
    """封存已真实导出的旧链；不生成分数，也不把当前 run 追认为历史。"""
    body = _document(root, descriptor)
    body.pop("baseline_digest", None)
    body["baseline_digest"] = digest(body)
    target = _safe_directory(root, output)
    if target.exists():
        if json.loads(read_evidence_bytes(root, output)) != body:
            raise ReplayError("baseline_already_frozen_conflict", "stale")
    else:
        # 先在内存中走相同验证器，再以不可覆盖方式封存。
        import tempfile
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".baseline-", dir=target.parent) as temporary:
            check = Path(temporary) / "baseline.json"
            atomic_write_json(check, body)
            verify_legacy_baseline(root, file_reference(root, check.relative_to(root).as_posix()))
        from .storage import canonical_json_bytes
        import os
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json_bytes(body)); handle.flush(); os.fsync(handle.fileno())
    return file_reference(root, output)


def validate_replay_dataset(dataset):
    _exact(dataset, ("schema_version", "kind", "owner", "origin", "families", "tasks", "cases", "dataset_digest"),
           "replay_dataset_schema_mismatch")
    _sealed(dataset, "dataset_digest")
    if dataset["schema_version"] != 1 or dataset["kind"] != "r85-heldout" or not dataset["owner"]:
        raise ReplayError("replay_dataset_identity_invalid")
    if dataset["origin"] not in {"recorded-task", "fixture"}:
        raise ReplayError("replay_dataset_origin_invalid")
    if (len(dataset["families"]) != 3 or len(set(dataset["families"])) != 3
            or len(dataset["tasks"]) != 10 or len(set(dataset["tasks"])) != 10):
        raise ReplayError("r85_matrix_axes_incomplete", "blocked")
    identities, pages, cells = set(), set(), set()
    tasks, decks = Counter(), set()
    for case in dataset["cases"]:
        _exact(case, ("case_id", "deck_id", "page_id", "lane", "theme_family", "task", "expected", "material", "request", "run"),
               "replay_case_schema_mismatch")
        key = (case["deck_id"], case["page_id"], case["lane"])
        if (case["case_id"] in identities or key in pages or case["lane"] not in LANES
                or case["theme_family"] not in dataset["families"] or case["task"] not in dataset["tasks"]
                or case["expected"] not in {"solvable", "unsolvable", "insufficient"}):
            raise ReplayError("replay_case_identity_invalid")
        identities.add(case["case_id"]); pages.add(key); decks.add(case["deck_id"])
        cells.add((case["theme_family"], case["task"]))
    # 双 lane 不重复贡献页数或任务样本；同一页不能被换 task 标签凑满分母。
    physical = {}
    for case in dataset["cases"]:
        key = (case["deck_id"], case["page_id"])
        label = (case["theme_family"], case["task"])
        if key in physical and physical[key] != label:
            raise ReplayError("replay_page_classification_conflict")
        physical[key] = label
    tasks.update(task for _, task in physical.values())
    coverage = {"matrix_cells": len(cells), "pages": len(physical), "decks": len(decks), "per_task": dict(tasks)}
    if len(cells) != 30 or len(physical) < 60 or len(decks) < 6 or any(tasks[task] < 4 for task in dataset["tasks"]):
        raise ReplayError("r85_coverage_incomplete:" + json.dumps(coverage, sort_keys=True), "blocked")
    return coverage


def _review(root, reference, *, case, artifact, baseline_page, candidate_ids):
    row = _document(root, reference)
    _exact(row, ("case_id", "artifact", "baseline_artifact", "reviewer", "method", "rationale", "scores",
                 "baseline_scores", "severe_defects", "acceptable_candidates"), "visual_review_schema_mismatch")
    if (row["case_id"] != case["case_id"] or row["artifact"] != artifact
            or row["baseline_artifact"] != baseline_page["artifact"]):
        raise ReplayError("visual_pair_artifact_mismatch", "stale")
    if not row["reviewer"] or row["method"] not in {"model", "human"} or not row["rationale"]:
        raise ReplayError("visual_reviewer_evidence_missing", "blocked")
    for field in ("scores", "baseline_scores"):
        if set(row[field]) != DIMENSIONS or any(type(score) not in (int, float) or not 1 <= score <= 5 for score in row[field].values()):
            raise ReplayError("visual_score_invalid")
    accepted = row["acceptable_candidates"]
    if not isinstance(accepted, list) or len(set(accepted)) != len(accepted) or not set(accepted).issubset(candidate_ids):
        raise ReplayError("visual_candidate_judgment_unbound")
    if type(row["severe_defects"]) is not int or row["severe_defects"] < 0:
        raise ReplayError("visual_defect_count_invalid")
    return row


def evaluate_user_outcomes(root, reference, *, cases, baseline_pages):
    """仅汇总绑定实际前后产物的用户观测；视觉分数不进入收益分母。"""
    if reference is None:
        return {"status": "not_run", "blocker": "user_outcome_data_missing"}
    document = _document(root, reference)
    if document.get("kind") != "user-outcome-observations" or document.get("schema_version") != 1:
        raise ReplayError("user_outcome_schema_mismatch", "error")
    if document.get("origin") != "recorded-user":
        return {"status": "not_run", "blocker": "user_outcome_not_recorded_user"}
    current = {row["case_id"]: row["artifact"] for row in cases if row["status"] == "passed"}
    previous = {row["case_id"]: row["artifact"] for row in baseline_pages}
    paired = {}
    if not document.get("owner") or not document.get("observations"):
        raise ReplayError("user_outcome_observations_missing", "blocked")
    for ref in document["observations"]:
        row = _document(root, ref)
        _exact(row, ("case_id", "participant_id", "phase", "artifact", "conclusion_correct", "task_success",
                     "rework_count", "recorded_at", "source", "adjudicator"), "user_outcome_observation_invalid")
        if (row["phase"] not in {"before", "after"} or not row["participant_id"] or not row["adjudicator"]
                or not row["recorded_at"] or type(row["conclusion_correct"]) is not bool or type(row["task_success"]) is not bool
                or type(row["rework_count"]) is not int or row["rework_count"] < 0):
            raise ReplayError("user_outcome_observation_invalid")
        expected = (previous if row["phase"] == "before" else current).get(row["case_id"])
        if expected is None or expected != row["artifact"]:
            raise ReplayError("user_outcome_artifact_unbound", "stale")
        verify_reference(root, row["artifact"])
        verify_reference(root, row["source"])
        key = (row["participant_id"], row["case_id"])
        pair = paired.setdefault(key, {})
        if row["phase"] in pair:
            raise ReplayError("user_outcome_duplicate_observation")
        pair[row["phase"]] = row
    if any(set(pair) != {"before", "after"} for pair in paired.values()):
        raise ReplayError("user_outcome_pair_incomplete", "blocked")
    result = {"status": "passed", "scope": "recorded-observations", "evidence": reference,
              "paired_denominator": len(paired), "participants": len({key[0] for key in paired})}
    for phase in ("before", "after"):
        rows = [pair[phase] for pair in paired.values()]
        result[phase] = {"conclusion_recognition_rate": sum(row["conclusion_correct"] for row in rows) / len(rows),
            "task_success_rate": sum(row["task_success"] for row in rows) / len(rows),
            "rework_rate": sum(row["rework_count"] > 0 for row in rows) / len(rows)}
    result["delta"] = {key: result["after"][key] - value for key, value in result["before"].items()}
    return result


def evaluate_quality_replay(root, plan_reference, *, execute=False, library_root=None, self_contained=False):
    """同一计划驱动真实 route，随后按固定分母重读证据；无 mock Provider 晋升路径。"""
    from .application.expression_pipeline import PipelineRequest, ExpressionPipelineError, load_committed_input
    from .content_pack import compile_content_pack
    from .content_projection import verify_effective_binding
    from .asset_resolver import AssetResolver
    from .quality_metrics import deck_quality_for_run
    from .execution_pairing import pairing_key

    root = Path(root).absolute()
    report = {"schema_version": 1, "kind": "quality-replay-receipt", "plan": plan_reference,
              "status": "not_run", "phase": None, "cases": [], "gaps": [], "publication_ready": False,
              "user_benefit": {"status": "not_run", "blocker": "user_outcome_data_missing"}}
    try:
        plan = _document(root, plan_reference)
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).parent / "schemas/quality-replay-v1.schema.json").read_text())
        if list(Draft202012Validator(schema).iter_errors(plan)):
            raise ReplayError("replay_plan_schema_mismatch", "error")
        _exact(plan, ("schema_version", "kind", "phase", "dataset", "baseline", "reviews", "stage_receipt",
                      "delivery_convergence", "user_defect", "run_prefix", "representatives", "observations", "plan_digest"), "replay_plan_schema_mismatch")
        _sealed(plan, "plan_digest")
        if plan["schema_version"] != 1 or plan["kind"] != "quality-replay-plan" or plan["phase"] not in {"U6-A", "U6-B"}:
            raise ReplayError("replay_phase_invalid")
        report["phase"] = plan["phase"]
        dataset = _document(root, plan["dataset"])
        report["coverage"] = validate_replay_dataset(dataset)
        report["dataset_digest"] = dataset["dataset_digest"]
        cases = replay_cases(plan, dataset)
        report["scope"] = {"kind": "full-heldout" if plan["phase"] == "U6-A" else "delivery-representatives",
                           "case_ids": [case["case_id"] for case in cases], "run_prefix": plan["run_prefix"]}
        stage = None
        if plan["phase"] == "U6-B":
            stage = _document(root, plan["stage_receipt"])
            _sealed(stage, "receipt_digest")
            if (stage.get("phase") != "U6-A" or stage.get("status") != "passed" or not stage.get("publication_ready")
                    or stage.get("dataset_digest") != dataset["dataset_digest"]):
                raise ReplayError("delivery_stage_receipt_mismatch", "stale")
            stage_plan = _document(root, stage.get("plan"))
            if (stage_plan.get("phase") != "U6-A" or stage_plan.get("run_prefix") == plan["run_prefix"]
                    or stage_plan.get("baseline") != plan["baseline"]):
                raise ReplayError("delivery_stage_scope_mismatch", "stale")
            current_stage = evaluate_quality_replay(root, stage["plan"])
            if current_stage != stage or current_stage["status"] != "passed":
                raise ReplayError("delivery_stage_evidence_stale", "stale")
            report["inherited_r85"] = {"receipt": plan["stage_receipt"], "coverage": stage["coverage"],
                                       "metrics": stage["metrics"], "paired_decks": stage["paired_decks"]}
        baseline = verify_legacy_baseline(root, plan["baseline"])
        report["baseline_digest"] = baseline["baseline_digest"]
        report["environment"] = environment_fingerprint()
        if baseline["environment"] != report["environment"]:
            raise ReplayError("paired_environment_mismatch", "blocked")
        before = {page["case_id"]: page for page in baseline["pages"]}
        reviews = _document(root, plan["reviews"]) if plan["reviews"] is not None else {}
        if set(reviews) - {case["case_id"] for case in dataset["cases"]}:
            raise ReplayError("replay_review_case_unknown")
        runs, failures, metadata, run_owners = {}, {}, {}, {}
        for case in cases:
            deck = case["deck_id"]
            identity = (case["request"], case["material"], case["run"], case["theme_family"])
            if deck in metadata and metadata[deck] != identity:
                raise ReplayError("replay_deck_inputs_conflict")
            metadata[deck] = identity
            if case["run"] in run_owners and run_owners[case["run"]] != deck:
                raise ReplayError("replay_deck_run_collision")
            run_owners[case["run"]] = deck
            if deck in runs or deck in failures:
                continue
            request_body = _document(root, case["request"])
            material = verify_reference(root, case["material"])
            source = request_body["pack"]["source"]
            compiled = compile_content_pack(material.decode(), master_path=source["master_path"],
                master_revision=source["master_revision"], decision_source=source["decision_source"],
                post_confirm_chain=source["post_confirm_chain"])
            if compiled != request_body["pack"]:
                raise ReplayError("replay_material_pack_mismatch", "stale")
            request = PipelineRequest.from_dict(request_body)
            run = replay_run_path(root, plan, case)
            from dataclasses import replace
            request = replace(request, run_root=str(run))
            failure = execute_replay_request(root, case, request, execute=execute, library_root=library_root,
                                             self_contained=self_contained)
            if failure is not None:
                failures[deck] = failure
                continue
            try:
                committed = load_committed_input(run)
            except (ValueError, OSError) as exc:
                failures[deck] = {"reason_code": str(exc)}
                continue
            if committed["payload"]["pack"] != compiled:
                raise ReplayError("replay_run_content_stale", "stale")
            from .application.expression_pipeline import _request_body
            expected_request = digest({key: value for key, value in _request_body(request).items()
                                       if key not in {"run_root", "library_root"}})
            if committed["payload"]["request"]["input_digest"] != expected_request:
                raise ReplayError("replay_run_request_stale", "stale")
            runs[deck] = (run, committed, deck_quality_for_run(run, include_visual=False))
        paired = {}
        for case in cases:
            row = {"case_id": case["case_id"], "expected": case["expected"], "status": "not_run",
                   "run": replay_run_path(root, plan, case).relative_to(root).as_posix()}
            report["cases"].append(row)
            if case["deck_id"] in failures:
                failure = failures[case["deck_id"]]
                row.update(status="rejected" if failure["reason_code"] in {"no_candidates", "explicit_unqualified", "constraints_unsatisfied"} else "blocked", failure=failure)
                continue
            run, committed, quality = runs[case["deck_id"]]
            payload, lane, pid = committed["payload"], case["lane"], case["page_id"]
            if lane not in payload["bindings"] or pid not in payload["bindings"][lane]:
                raise ReplayError("replay_case_run_join_mismatch")
            binding = payload["bindings"][lane][pid]
            page = next(page for page in payload["pack"]["pages"] if page["page_id"] == pid)
            frozen = AssetResolver.from_snapshot(committed["root"] / "asset-snapshot")
            verify_effective_binding(binding, page, resolver=frozen, frozen_design=payload["designs"][lane])
            exported = quality["lanes"][lane]["pages"].get(pid, {})
            if any(value != "passed" for value in quality["channels"].values()) or exported.get("status") != "passed":
                row.update(status="blocked", quality=quality)
                continue
            artifact = file_reference(root, (run / exported["artifact"]).relative_to(root).as_posix())
            old = before.get(case["case_id"])
            if old is None:
                row.update(status="blocked", blocker="baseline_pair_missing")
                continue
            if any(old[key] != case[key] for key in ("deck_id", "page_id", "lane", "theme_family", "material")):
                raise ReplayError("baseline_pair_input_mismatch", "stale")
            if lane == "image" and old["provider_contract_digest"] != digest(payload["request"].get("provider_contract")):
                raise ReplayError("paired_provider_mismatch", "blocked")
            candidates = payload["lane_selections"][lane].get("top3", {}).get(pid)
            if candidates is None:
                row.update(status="blocked", blocker="replay_candidate_trace_missing")
                continue
            candidate_ids = {pairing_key(entry["identity"]) for entry in candidates}
            if any(pairing_key(entry["identity"]) != entry["identity_digest"] for entry in candidates) or len(candidates) > 3:
                raise ReplayError("replay_candidate_trace_stale", "stale")
            if case["case_id"] not in reviews:
                row.update(status="not_run", blocker="paired_visual_review_missing", artifact=artifact, lane=lane)
                continue
            selected = pairing_key(binding["execution_pairing_identity"])
            review = _review(root, reviews.get(case["case_id"]), case=case, artifact=artifact,
                             baseline_page=old, candidate_ids=candidate_ids | {selected})
            semantic = selected in review["acceptable_candidates"]
            passed = (case["expected"] == "solvable" and review["severe_defects"] == 0 and all(score >= 4 for score in review["scores"].values())
                and not any(review["baseline_scores"][key] >= 4 and review["scores"][key] < review["baseline_scores"][key] for key in DIMENSIONS))
            row.update(status="passed" if passed else "failed", artifact=artifact, input_generation=committed["generation"],
                expression_binding_digest=binding["expression_binding_digest"], materialization_binding_digest=binding["materialization_binding_digest"],
                top3_hit=bool(set(review["acceptable_candidates"]) & candidate_ids), selected_semantic=semantic,
                scores=review["scores"], baseline_scores=review["baseline_scores"], lane=lane)
            paired.setdefault(case["deck_id"], []).append((pid, review))
        solvable = [row for row in report["cases"] if row["expected"] == "solvable"]
        report["metrics"] = {"solvable_denominator": len(solvable),
            "coverage": sum(row.get("artifact") is not None for row in solvable) / len(solvable) if solvable else None,
            "top3_hit": sum(row.get("top3_hit", False) for row in solvable) / len(solvable) if solvable else None,
            "selected_semantic": sum(row.get("selected_semantic", False) for row in solvable) / len(solvable) if solvable else None,
            "separate_denominators": {kind: {"total": sum(row["expected"] == kind for row in report["cases"]),
                "rejected": sum(row["expected"] == kind and row["status"] == "rejected" for row in report["cases"])} for kind in ("unsolvable", "insufficient")}}
        valid_decks = 0
        for rows in paired.values():
            if not 10 <= len({pid for pid, _ in rows}) <= 14:
                continue
            if sum(sum(review["scores"][key] - review["baseline_scores"][key] for _, review in rows) > 0 for key in DIMENSIONS) >= 2:
                valid_decks += 1
        report["paired_decks"] = valid_decks
        if plan["phase"] == "U6-A" and valid_decks < 3:
            report["gaps"].append("paired_deck_coverage_or_improvement_incomplete")
        if {row.get("lane") for row in report["cases"] if row["status"] == "passed"} != LANES:
            report["gaps"].append("real_dual_lane_export_required")
        if any(row["status"] in {"failed", "blocked", "not_run"} for row in report["cases"]):
            report["gaps"].append("replay_cases_not_passed")
        if plan["phase"] == "U6-A" and (not solvable or any(report["metrics"][key] < threshold for key, threshold in (("coverage", .9), ("top3_hit", .9), ("selected_semantic", .85)))):
            report["gaps"].append("r85_threshold_not_met")
        if dataset["origin"] != "recorded-task":
            report["gaps"].append("fixture_only_not_publication_evidence")
        for kind, counts in report["metrics"]["separate_denominators"].items():
            if plan["phase"] == "U6-A" and counts["total"] == 0:
                report["gaps"].append(kind + "_denominator_missing")
        if plan["phase"] == "U6-B":
            stage_rows = {row["case_id"]: row for row in stage["cases"]}
            for row in report["cases"]:
                if row["status"] == "passed" and any(row.get(key) != stage_rows.get(row["case_id"], {}).get(key)
                    for key in ("expression_binding_digest", "materialization_binding_digest")):
                    raise ReplayError("delivery_binding_changed", "stale")
            from .library_migration import verify_final_receipt
            convergence = verify_final_receipt(root, plan["delivery_convergence"], stage_receipt=plan["stage_receipt"])
            report["delivery_convergence"] = {"receipt": plan["delivery_convergence"],
                                               "plan_digest": convergence["plan_digest"]}
            defect = _document(root, plan["user_defect"])
            if not defect.get("source") or not defect.get("case_ids") or not set(defect["case_ids"]).issubset({row["case_id"] for row in report["cases"] if row["status"] == "passed"}):
                raise ReplayError("user_defect_replay_incomplete", "blocked")
            verify_reference(root, defect["source"])
            if defect.get("origin") == "equivalent-fixture":
                proof = _document(root, defect.get("isomorphism"))
                if set(proof) != {"trigger", "content_relation", "failure", "acceptance"} or not all(proof.values()):
                    raise ReplayError("user_defect_isomorphism_missing", "blocked")
            elif defect.get("origin") != "user-defect":
                raise ReplayError("user_defect_identity_missing", "blocked")
            report["user_replay"] = {"status": "passed", "origin": defect["origin"], "source": defect["source"]}
            report["user_benefit"] = evaluate_user_outcomes(root, plan["observations"], cases=report["cases"], baseline_pages=baseline["pages"])
        if environment_fingerprint() != report["environment"]:
            raise ReplayError("replay_environment_changed_during_run", "stale")
        verify_legacy_baseline(root, plan["baseline"])
        verify_reference(root, plan_reference)
        verify_reference(root, plan["dataset"])
        if plan["reviews"]:
            verify_reference(root, plan["reviews"])
        for request_ref, material_ref, _, _ in metadata.values():
            verify_reference(root, request_ref)
            verify_reference(root, material_ref)
        report["status"] = "failed" if any(row["status"] == "failed" for row in report["cases"]) else ("passed" if not report["gaps"] else "blocked")
        report["publication_ready"] = report["status"] == "passed" and plan["phase"] == "U6-A"
    except ReplayError as exc:
        report.update(status=exc.status, publication_ready=False)
        report["gaps"].append(str(exc))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        report.update(status="error", publication_ready=False)
        report["gaps"].append(str(exc))
    report["receipt_digest"] = digest(report)
    return report
