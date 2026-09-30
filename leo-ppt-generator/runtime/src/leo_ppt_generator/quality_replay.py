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


def _validate_schema(document, name, reason):
    """在业务语义校验前执行正式 schema；schema 失败不得降级成通过。"""
    try:
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).parent / "schemas" / name).read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda error: str(list(error.path)))
    except (OSError, ValueError, TypeError) as exc:
        raise ReplayError(reason, "error") from exc
    if errors:
        raise ReplayError(reason + ":" + errors[0].message, "error")


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


def _baseline_execution_sources(baseline):
    from .qualification import is_execution_source
    execution = {}
    for path, sha in baseline.get("execution_source_snapshot", baseline["source_snapshot"]).items():
        if "/leo_ppt_generator/" not in path:
            continue
        relative = path.split("/leo_ppt_generator/", 1)[1]
        if not is_execution_source(relative):
            continue
        if relative in execution:
            raise ReplayError("baseline_execution_source_ambiguous", "blocked")
        execution[relative] = sha
    if ("render/page.py" not in execution
            or digest(execution) != baseline["environment"].get("execution_source_digest")):
        raise ReplayError("baseline_execution_snapshot_incomplete", "blocked")
    return execution


def paired_environment_compatibility(baseline, current_environment):
    """独立裁决器可演进；浏览器、字体、Provider 和物化源码必须保持可比。"""
    from .qualification import is_execution_source
    old_environment = baseline["environment"]
    if ({key: value for key, value in old_environment.items() if key != "execution_source_digest"}
            != {key: value for key, value in current_environment.items() if key != "execution_source_digest"}):
        raise ReplayError("paired_environment_mismatch", "blocked")
    old_sources = _baseline_execution_sources(baseline)
    package = Path(__file__).parent
    current_sources = {path.relative_to(package).as_posix(): file_reference(package, path.relative_to(package).as_posix())["sha256"]
                       for path in sorted(package.rglob("*")) if path.is_file()
                       and is_execution_source(path.relative_to(package).as_posix())}
    if digest(current_sources) != current_environment.get("execution_source_digest"):
        raise ReplayError("replay_environment_changed_during_run", "stale")
    # oracle/OCR 是独立观测器；真正生成页面的 renderer/adapter 变化仍须双边重基线。
    def renderers(sources):
        return {path: sha for path, sha in sources.items()
                if path.startswith(("render/", "providers/", "_vendor/codex_ppt/image_providers/"))
                or path == "image_deck/expression_adapter.py"}
    old_renderers, current_renderers = renderers(old_sources), renderers(current_sources)
    if old_renderers != current_renderers:
        raise ReplayError("paired_renderer_source_rebaseline_required", "blocked")
    return {"status": "compatible", "execution_source_changed": old_sources != current_sources,
            "baseline_execution_source_digest": digest(old_sources), "current_execution_source_digest": digest(current_sources),
            "baseline_renderer_source_digest": digest(old_renderers), "current_renderer_source_digest": digest(current_renderers)}


def validate_legacy_image_export(root, reference):
    """验证历史 image 传输封存，不把旧链提升为新 production binding。

    旧链没有 expression/materialization binding。该桥只接受完整的原始 HTTP
    响应、Provider 原图和归一化 PNG；缺任一字节或使用本地协议测试均保持
    blocked。所有引用仍以任务根为边界，receipt 自己的附件引用以其目录为根。
    """
    body = _document(root, reference)
    _validate_schema(body, "legacy-image-export-v1.schema.json", "legacy_image_export_schema_mismatch")
    if (body["schema_version"] != 1 or body["kind"] != "legacy-image-export"
            or body["capture_mode"] not in {"captured-before-change", "reconstructed-historical"}
            or not re.fullmatch(r"[0-9a-f]{40}", body["source_revision"])
            or not body["page_id"]):
        raise ReplayError("legacy_image_export_identity_invalid", "blocked")
    _sealed(body, "export_digest")
    for path, sha in body["source_snapshot"].items():
        verify_reference(root, {"path": path, "sha256": sha})
    if not any(path.endswith("/image_providers/openai_compatible.py") for path in body["source_snapshot"]):
        raise ReplayError("legacy_image_source_snapshot_incomplete", "blocked")
    verify_reference(root, body["material"])
    selection = _document(root, body["selection"])
    contract = _document(root, body["provider_contract"])
    if not isinstance(selection, dict) or not isinstance(contract, dict):
        raise ReplayError("legacy_image_export_input_invalid", "blocked")
    receipt_ref = body["receipt"]
    receipt = _document(root, receipt_ref)
    if receipt.get("evidence_source") != "provider-http":
        raise ReplayError("legacy_image_provider_http_evidence_required", "blocked")
    if receipt.get("page_id") != body["page_id"]:
        raise ReplayError("legacy_image_page_identity_mismatch", "stale")
    if receipt.get("expression_binding_digest") or receipt.get("materialization_binding_digest"):
        raise ReplayError("legacy_image_must_not_claim_new_binding", "stale")
    from .image_deck.expression_adapter import verify_provider_export
    receipt_root = (Path(root) / receipt_ref["path"]).parent
    verify_provider_export(receipt, root=receipt_root, binding=None)
    _exact(selection, ("page_id", "material", "request", "provider_contract", "prompt_source", "theme_family")
           + (("theme",) if "theme_source" in body else ()),
           "legacy_image_selection_incomplete")
    request = _document(root, selection["request"])
    prompt = verify_reference(root, selection["prompt_source"]).decode("utf-8")
    transmitted = json.loads(verify_reference(receipt_root, receipt["request"]))
    if (selection["page_id"] != body["page_id"] or selection["material"] != body["material"]
            or selection["provider_contract"] != body["provider_contract"] or request != transmitted
            or request.get("prompt") != prompt or not selection["theme_family"]):
        raise ReplayError("legacy_image_selection_request_mismatch", "stale")
    if (receipt.get("contract_sha256") != body["provider_contract"]["sha256"] or receipt.get("provider") != contract.get("provider")
            or receipt.get("model") != contract.get("model")):
        raise ReplayError("legacy_image_provider_contract_mismatch", "stale")
    if "theme_source" in body:
        theme_ref = body["theme_source"]
        theme = _document(root, theme_ref)
        if (body["source_snapshot"].get(theme_ref["path"]) != theme_ref["sha256"]
                or not isinstance(theme, dict) or not theme or selection["theme"] != theme):
            raise ReplayError("legacy_image_historical_theme_mismatch", "stale")
    artifact = receipt_root / receipt["artifact"]["path"]
    return {"status": "verified", "capture_mode": body["capture_mode"],
            "page_id": body["page_id"], "artifact": file_reference(root, artifact.relative_to(root).as_posix()),
            "receipt": receipt_ref, "provider": receipt["provider"], "model": receipt["model"],
            "contract_sha256": receipt["contract_sha256"], "selection": body["selection"],
            "material": body["material"], "source_revision": body["source_revision"],
            "source_snapshot": body["source_snapshot"], "theme_family": selection["theme_family"]}


def _rebaseline_image_inputs(root, case, original):
    """image 旧侧只接受原基线已封存的 HTTP、prompt、主题和 contract 字节。"""
    if case["old_snapshot"] != original["receipt"]:
        raise ReplayError("paired_rebaseline_image_original_manifest_mismatch", "stale")
    archived = validate_legacy_image_export(root, original["receipt"])
    manifest = _document(root, original["receipt"])
    if "theme_source" not in manifest:
        raise ReplayError("paired_rebaseline_historical_image_theme_missing", "blocked")
    selected = _document(root, case["old_selection"])
    contract = _document(root, manifest["provider_contract"])
    request = _document(root, selected["request"])
    from .config.backend_contract import BackendRegistry
    BackendRegistry.default().load(contract)
    from .storage import json_document_bytes, sha256_bytes
    if (contract.get("mode") != "generate" or manifest["provider_contract"]["sha256"] != sha256_bytes(json_document_bytes(contract))
            or request != {"model": contract["model"], "prompt": request.get("prompt"), "n": 1, "size": "auto"}):
        raise ReplayError("paired_rebaseline_historical_image_request_unsupported", "blocked")
    if (archived["selection"] != case["old_selection"] or archived["material"] != case["material"]
            or archived["page_id"] != case["page_id"] or archived["theme_family"] != case["theme_family"]):
        raise ReplayError("paired_rebaseline_original_input_mismatch", "stale")
    new_request = _rebaseline_request(root, case)
    if (new_request.provider_contract != contract
            or new_request.design_context.get("effective") != selected["theme"]):
        raise ReplayError("paired_rebaseline_image_contract_or_theme_changed", "blocked")
    return manifest, selected, contract, request


def _rebaseline_provider_scope(root, plan, *, execute, provider_contracts):
    """参数只约束本次显式执行范围，不冒充用户授权记录。"""
    expected = set()
    for case in plan["cases"]:
        if case["lane"] == "image":
            manifest = _document(root, case["old_snapshot"])
            expected.add(manifest["provider_contract"]["sha256"])
    allowed = list(provider_contracts or ())
    if allowed and not execute:
        raise ReplayError("paired_rebaseline_provider_scope_requires_execute", "blocked")
    if execute and (len(allowed) != len(set(allowed)) or set(allowed) != expected):
        raise ReplayError("paired_rebaseline_provider_scope_mismatch", "blocked")


def _verify_historical_html_binding(binding, receipt, *, page, selected):
    """只校验历史基线；旧单摘要绝不进入生产 binding 消费路径。"""
    effective = binding.get("effective") if isinstance(binding, dict) else None
    theme = effective.get("theme") if isinstance(effective, dict) else None
    if not isinstance(theme, dict) or not theme or not isinstance(selected.get("theme"), dict):
        raise ReplayError("paired_rebaseline_historical_theme_missing", "blocked")
    if not isinstance(receipt, dict):
        raise ReplayError("paired_rebaseline_historical_binding_missing", "blocked")
    if (binding.get("template_id") != selected["template_id"] or binding.get("page_id") != page["page_id"]
            or binding.get("backend") != page["lane"] or theme != selected["theme"]):
        raise ReplayError("paired_rebaseline_old_theme_mismatch", "stale")
    dual = ("expression_binding_digest", "materialization_binding_digest")
    if "binding_digest" in binding:
        if (binding.get("schema_version") != 2 or any(key in binding or key in receipt for key in dual)
                or not re.fullmatch(r"[0-9a-f]{64}", str(binding.get("binding_digest", "")))):
            raise ReplayError("paired_rebaseline_historical_binding_schema_mismatch", "blocked")
        try:
            # 历史 710846e 的 content_projection.compute_binding_digest 原算法。
            value = {key: binding[key] for key in ("page_id", "layout_id", "template_id", "backend", "slot_map",
                "context_digest", "content_digest", "compiler", "effective", "eligibility")}
            value["item_ids"] = sorted(binding["item_ids"])
            computed = digest(value)
        except (KeyError, TypeError) as exc:
            raise ReplayError("paired_rebaseline_historical_binding_incomplete", "blocked") from exc
        if not receipt.get("binding_digest"):
            raise ReplayError("paired_rebaseline_historical_binding_missing", "blocked")
        if binding["binding_digest"] != computed or receipt.get("binding_digest") != computed:
            raise ReplayError("paired_rebaseline_historical_binding_receipt_mismatch", "stale")
    else:
        if any(key not in binding or key not in receipt for key in dual):
            raise ReplayError("paired_rebaseline_historical_binding_missing", "blocked")
        from .content_projection import verify_dual_binding_digests, verify_binding_reference
        try:
            verify_dual_binding_digests(binding)
            verify_binding_reference(receipt, binding)
        except ValueError as exc:
            raise ReplayError("paired_rebaseline_historical_binding_receipt_mismatch", "stale") from exc
    if (not binding.get("content_digest") or receipt.get("content_digest") != binding["content_digest"]
            or receipt.get("template_id") != binding["template_id"] or receipt.get("backend") != binding["backend"]):
        raise ReplayError("paired_rebaseline_historical_content_receipt_mismatch", "stale")


def _rebaseline_snapshot(root, reference, baseline, binding):
    from .asset_resolver import AssetResolver
    document = _document(root, reference)
    _exact(document, ("root", "files", "source_roots"), "paired_rebaseline_snapshot_invalid")
    directory = _safe_directory(root, document["root"])
    if not directory.is_dir() or not document["files"]:
        raise ReplayError("paired_rebaseline_snapshot_missing", "blocked")
    actual = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ReplayError("paired_rebaseline_snapshot_type_invalid")
        if path.is_file():
            relative = path.relative_to(directory).as_posix()
            actual[relative] = file_reference(directory, relative)["sha256"]
    listed = {}
    for item in document["files"]:
        _exact(item, ("path", "sha256"), "paired_rebaseline_snapshot_reference_invalid")
        if item["path"] in listed:
            raise ReplayError("paired_rebaseline_snapshot_duplicate")
        verify_reference(directory, item)
        listed[item["path"]] = item["sha256"]
    if actual != listed:
        raise ReplayError("paired_rebaseline_snapshot_stale", "stale")
    source_roots = document["source_roots"]
    if (not isinstance(source_roots, dict) or not source_roots
            or not set(source_roots).issubset({"builtin", "user"})):
        raise ReplayError("paired_rebaseline_historical_source_root_missing", "blocked")
    prefixes = {"builtin": "builtin/", "user": "user/template-library/"}
    for source in source_roots.values():
        _safe_directory(root, source)
    for path, sha in actual.items():
        if "/canonical/" not in path:
            continue
        scope = next((scope for scope, prefix in prefixes.items() if path.startswith(prefix)), None)
        if scope not in source_roots:
            raise ReplayError("paired_rebaseline_historical_source_root_missing", "blocked")
        relative = path[len(prefixes[scope]):]
        historical = source_roots[scope] + "/" + relative
        if baseline["source_snapshot"].get(historical) != sha:
            raise ReplayError("paired_rebaseline_asset_path_not_historical", "stale")
        verify_reference(root, {"path": historical, "sha256": sha})
    frozen = AssetResolver.from_snapshot(directory)
    effective = binding.get("effective") if isinstance(binding, dict) else None
    pins = effective.get("assets") if isinstance(effective, dict) else None
    if (not isinstance(pins, list) or not pins
            or any(not isinstance(pin, dict) or not isinstance(pin.get("asset_id"), str)
                   or pin.get("origin_scope") not in prefixes or not isinstance(pin.get("files"), dict)
                   or not pin["files"] for pin in pins)
            or len({pin["asset_id"] for pin in pins}) != len(pins)):
        raise ReplayError("paired_rebaseline_historical_asset_pins_missing", "blocked")
    for pin in pins:
        entity = frozen.resolve(pin["asset_id"])
        if (entity["data"].get("asset_id") != pin["asset_id"]
                or entity["origin_scope"] != pin["origin_scope"] or frozen.fingerprint(pin["asset_id"]) != pin):
            raise ReplayError("paired_rebaseline_asset_identity_mismatch", "stale")
        for relative, sha in pin["files"].items():
            scope = pin["origin_scope"]
            if actual.get(prefixes[scope] + relative) != sha:
                raise ReplayError("paired_rebaseline_asset_identity_path_mismatch", "stale")
    if not {binding["template_id"], binding["layout_id"]}.issubset({pin["asset_id"] for pin in pins}):
        raise ReplayError("paired_rebaseline_historical_selected_asset_pin_missing", "blocked")
    return frozen


def _rebaseline_request(root, case):
    from dataclasses import replace
    from .application.expression_pipeline import PipelineRequest
    from .content_pack import compile_content_pack
    body = _document(root, case["new_request"])
    request = PipelineRequest.from_dict(body)
    if not Path(request.library_root).is_absolute():
        raise ReplayError("paired_rebaseline_library_absolute_required", "blocked")
    source = request.pack["source"]
    material = verify_reference(root, case["material"])
    compiled = compile_content_pack(material.decode(), master_path=source["master_path"],
        master_revision=source["master_revision"], decision_source=source["decision_source"],
        post_confirm_chain=source["post_confirm_chain"])
    if compiled != request.pack or case["page_id"] not in {p["page_id"] for p in compiled["pages"]}:
        raise ReplayError("paired_rebaseline_material_mismatch", "stale")
    if case["lane"] not in request.lane_matrix.get(case["page_id"], []):
        raise ReplayError("paired_rebaseline_lane_mismatch")
    request = replace(request, run_root=str(_safe_directory(root, case["new_output"])))
    if _execution_fingerprint(request) != case["new_fingerprint"]:
        raise ReplayError("paired_rebaseline_new_source_stale", "stale")
    return request


def _immutable_replay_bytes(root, relative, body):
    """封存器只接受 absent 或完全相同字节；已有产物从不覆盖。"""
    import os
    target = _safe_directory(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        if read_evidence_bytes(root, relative) != body:
            raise ReplayError("paired_rebaseline_immutable_conflict", "stale")
    else:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return file_reference(root, relative)


def prepare_paired_rebaseline_plan(root, descriptor, output="qa/paired-rebaseline-plan.json"):
    """无导出、无 Provider 调用地封存计划；输入不完整时不写伪就绪计划。"""
    from .application.expression_pipeline import PipelineRequest
    from .storage import canonical_json_bytes
    plan = _document(root, descriptor)
    _exact(plan, ("schema_version", "kind", "baseline", "cases"), "paired_rebaseline_descriptor_invalid")
    for case in plan["cases"]:
        if "new_fingerprint" in case:
            raise ReplayError("paired_rebaseline_descriptor_contains_fingerprint")
        request = PipelineRequest.from_dict(_document(root, case["new_request"]))
        case["new_fingerprint"] = _execution_fingerprint(request)
    plan["environment"] = environment_fingerprint()
    plan["plan_digest"] = digest(plan)
    import tempfile
    root = Path(root).absolute()
    with tempfile.TemporaryDirectory(prefix=".rebaseline-plan-", dir=root) as temporary:
        path = Path(temporary) / "plan.json"
        atomic_write_json(path, plan)
        validate_paired_rebaseline_plan(root, file_reference(root, path.relative_to(root).as_posix()))
    return _immutable_replay_bytes(root, output, canonical_json_bytes(plan))


def validate_paired_rebaseline_plan(root, reference):
    """固定双方输入与源码；单独通过计划校验不代表导出或视觉通过。"""
    plan = _document(root, reference)
    _validate_schema(plan, "paired-rebaseline-v1.schema.json", "paired_rebaseline_schema_mismatch")
    _sealed(plan, "plan_digest")
    original = _document(root, plan["baseline"])
    if original.get("kind") != "legacy-visual-baseline":
        raise ReplayError("paired_rebaseline_recursive_baseline")
    baseline = verify_legacy_baseline(root, plan["baseline"])
    before = {page["case_id"]: page for page in baseline["pages"]}
    ids, old_paths, new_requests = set(), set(), {}
    for case in plan["cases"]:
        if case["case_id"] in ids or case["case_id"] not in before:
            raise ReplayError("paired_rebaseline_case_identity_invalid")
        ids.add(case["case_id"])
        old = before[case["case_id"]]
        if (any(case[key] != old[key] for key in ("page_id", "lane", "theme_family", "material"))
                or case["old_selection"] != old["selection"]):
            raise ReplayError("paired_rebaseline_original_input_mismatch", "stale")
        for field in ("old_output", "new_output"):
            _safe_directory(root, case[field])
        if case["old_output"] in old_paths:
            raise ReplayError("paired_rebaseline_output_collision")
        old_paths.add(case["old_output"])
        if case["new_output"] in new_requests and new_requests[case["new_output"]] != case["new_request"]:
            raise ReplayError("paired_rebaseline_run_collision")
        new_requests[case["new_output"]] = case["new_request"]
        if case["lane"] == "render:html":
            selected = _document(root, case["old_selection"])
            if not selected.get("binding") or not selected.get("theme"):
                raise ReplayError("paired_rebaseline_historical_binding_or_theme_missing", "blocked")
            _exact(selected, ("template_id", "input", "theme", "binding"), "paired_rebaseline_selection_incomplete")
            binding = _document(root, selected["binding"])
            receipt = _document(root, old["receipt"])
            _verify_historical_html_binding(binding, receipt, page=old, selected=selected)
            frozen = _rebaseline_snapshot(root, case["old_snapshot"], baseline, binding)
            pin = frozen.fingerprint(selected["template_id"])
            if receipt["template_sha256"] not in pin["files"].values():
                raise ReplayError("paired_rebaseline_template_changed", "stale")
        else:
            _rebaseline_image_inputs(root, case, old)
        _rebaseline_request(root, case)
    if ids != set(before):
        raise ReplayError("paired_rebaseline_missing_side_or_case", "blocked")
    for output, request_reference in new_requests.items():
        request = _document(root, request_reference)
        planned = {(case["page_id"], case["lane"]) for case in plan["cases"] if case["new_output"] == output}
        actual = [(pid, lane) for pid, lanes in request["lane_matrix"].items() for lane in lanes]
        if len(actual) != len(set(actual)) or set(actual) != planned:
            raise ReplayError("paired_rebaseline_unplanned_execution", "blocked")
    all_outputs = [Path(path) for path in old_paths | set(new_requests)]
    if len(all_outputs) != len(old_paths) + len(new_requests):
        raise ReplayError("paired_rebaseline_output_collision")
    for index, output in enumerate(all_outputs):
        if any(output.is_relative_to(other) or other.is_relative_to(output) for other in all_outputs[index + 1:]):
            raise ReplayError("paired_rebaseline_output_collision")
    inputs = [reference["path"], plan["baseline"]["path"], *baseline["source_snapshot"]]
    protected_directories = []
    for page in baseline["pages"]:
        inputs.extend(page[field]["path"] for field in ("material", "selection", "artifact", "receipt"))
        selected = _document(root, page["selection"])
        for field in ("input", "binding", "material", "request", "provider_contract", "prompt_source"):
            if isinstance(selected.get(field), dict) and "path" in selected[field]:
                inputs.append(selected[field]["path"])
    for case in plan["cases"]:
        inputs.extend(case[field]["path"] for field in ("material", "old_selection", "old_snapshot", "new_request"))
        snapshot = _document(root, case["old_snapshot"])
        if case["lane"] == "render:html":
            inputs.append(snapshot["root"])
            protected_directories.extend([snapshot["root"], *snapshot["source_roots"].values()])
        else:
            inputs.extend(snapshot[field]["path"] for field in ("receipt", "provider_contract", "theme_source"))
            inputs.extend(snapshot["source_snapshot"])
            receipt = _document(root, snapshot["receipt"])
            receipt_root = Path(snapshot["receipt"]["path"]).parent
            inputs.extend((receipt_root / receipt[field]["path"]).as_posix()
                          for field in ("request", "response", "provider_image", "artifact"))
    if any(Path(path).is_relative_to(output) for path in inputs for output in all_outputs):
        raise ReplayError("paired_rebaseline_output_overlaps_input")
    if any(output.is_relative_to(Path(path)) for path in protected_directories for output in all_outputs):
        raise ReplayError("paired_rebaseline_output_overlaps_input")
    if plan["environment"] != environment_fingerprint():
        raise ReplayError("paired_rebaseline_environment_mismatch", "blocked")
    return plan


def _rebaseline_new_side(root, case, *, execute, provider_contracts=()):
    from .application.expression_pipeline import load_committed_input, _request_body
    from .asset_resolver import AssetResolver
    from .content_projection import verify_effective_binding
    from .quality_metrics import deck_quality_for_run
    request = _rebaseline_request(root, case)
    if execute and any("image" in lanes for lanes in request.lane_matrix.values()):
        from .storage import json_document_bytes, sha256_bytes
        if sha256_bytes(json_document_bytes(request.provider_contract)) not in provider_contracts:
            raise ReplayError("paired_rebaseline_provider_scope_mismatch", "blocked")
    failure = execute_replay_request(root, {"request": case["new_request"]}, request,
        execute=execute, library_root=request.library_root)
    if failure:
        raise ReplayError("paired_rebaseline_new_route_failed:" + failure["reason_code"], "blocked")
    run = Path(request.run_root)
    committed = load_committed_input(run)
    payload = committed["payload"]
    expected = digest({k: v for k, v in _request_body(request).items() if k not in {"run_root", "library_root"}})
    if payload["request"]["input_digest"] != expected or payload["pack"] != request.pack:
        raise ReplayError("paired_rebaseline_new_request_stale", "stale")
    page = next(p for p in payload["pack"]["pages"] if p["page_id"] == case["page_id"])
    binding = payload["bindings"][case["lane"]][case["page_id"]]
    frozen = AssetResolver.from_snapshot(committed["root"] / "asset-snapshot")
    verify_effective_binding(binding, page, resolver=frozen, frozen_design=payload["designs"][case["lane"]])
    quality = deck_quality_for_run(run, include_visual=False)
    exported = quality["lanes"][case["lane"]]["pages"].get(case["page_id"], {})
    if any(status != "passed" for status in quality["channels"].values()) or exported.get("status") != "passed":
        raise ReplayError("paired_rebaseline_new_export_not_passed", "blocked")
    selected = _document(root, case["old_selection"])
    if binding["effective"]["theme"] != selected["theme"]:
        raise ReplayError("paired_rebaseline_theme_changed", "blocked")
    from .application.expression_pipeline import materialization_paths
    artifact, sidecar = materialization_paths(run, case["lane"], case["page_id"])
    if case["lane"] == "image":
        from .image_deck.expression_adapter import verify_provider_export
        receipt = json.loads(read_evidence_bytes(sidecar.parent, sidecar.name))
        verify_provider_export(receipt, root=sidecar.parent, binding=binding)
        if receipt["evidence_source"] != "provider-http":
            raise ReplayError("paired_rebaseline_real_provider_required", "blocked")
    return {"artifact": file_reference(root, artifact.relative_to(root).as_posix()),
            "receipt": file_reference(root, sidecar.relative_to(root).as_posix()),
            "execution": file_reference(root, (run / "qa/replay-execution.json").relative_to(root).as_posix()),
            "input_generation": committed["generation"],
            "expression_binding_digest": binding["expression_binding_digest"],
            "materialization_binding_digest": binding["materialization_binding_digest"]}


def _rebaseline_old_side(root, plan_reference, plan, case, *, execute):
    from .render.page import render_page
    from .storage import canonical_json_bytes
    import os
    selected = _document(root, case["old_selection"])
    baseline = verify_legacy_baseline(root, plan["baseline"])
    frozen = _rebaseline_snapshot(root, case["old_snapshot"], baseline, _document(root, selected["binding"]))
    directory = _safe_directory(root, case["old_output"])
    record_path = directory / "execution.json"
    expected = {"plan": plan_reference, "selection": case["old_selection"], "snapshot": case["old_snapshot"],
                "environment": plan["environment"]}
    if execute and not directory.exists():
        import tempfile
        directory.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".rebaseline-", dir=directory.parent) as temporary:
            stage = Path(temporary)
            render_page(selected["template_id"], Path(root) / selected["input"]["path"], stage / "page.png",
                        theme_variables=selected["theme"], resolver=frozen, binding=None)
            rendered = json.loads(read_evidence_bytes(stage, "page.png.render.json"))
            rendered["out"] = str(directory / "page.png")
            atomic_write_json(stage / "page.png.render.json", rendered)
            record = {**expected, "artifact_sha256": file_reference(stage, "page.png")["sha256"],
                      "receipt_sha256": file_reference(stage, "page.png.render.json")["sha256"]}
            record["receipt_digest"] = digest(record)
            (stage / "execution.json").write_bytes(canonical_json_bytes(record))
            if directory.exists():
                raise ReplayError("paired_rebaseline_output_conflict", "stale")
            os.rename(stage, directory)
    reference = file_reference(root, record_path.relative_to(root).as_posix())
    record = _document(root, reference)
    _sealed(record, "receipt_digest")
    if any(record.get(key) != value for key, value in expected.items()):
        raise ReplayError("paired_rebaseline_old_execution_stale", "stale")
    artifact = file_reference(root, (directory / "page.png").relative_to(root).as_posix())
    receipt_ref = file_reference(root, (directory / "page.png.render.json").relative_to(root).as_posix())
    _png(root, artifact)
    receipt = _document(root, receipt_ref)
    original = next(p for p in baseline["pages"] if p["case_id"] == case["case_id"])
    previous = _document(root, original["receipt"])
    if (record["artifact_sha256"] != artifact["sha256"] or record["receipt_sha256"] != receipt_ref["sha256"]
            or receipt.get("kind") != "render_provenance" or receipt.get("backend") != "render:html"
            or receipt.get("out_sha256") != artifact["sha256"] or receipt.get("overflow_check") != "pass"
            or receipt.get("out") != str(directory / "page.png")
            or (receipt.get("width"), receipt.get("height")) != (2560, 1440)
            or receipt.get("template_sha256") != previous["template_sha256"]
            or receipt.get("data_sha256") != selected["input"]["sha256"]):
        raise ReplayError("paired_rebaseline_old_export_stale", "stale")
    return {"artifact": artifact, "receipt": receipt_ref, "execution": reference}


def _rebaseline_old_image_side(root, plan_reference, plan, case, *, execute, provider_contracts=()):
    from .backend_execution import build_execution_context
    from .image_deck.expression_adapter import export_provider_image, verify_provider_export
    from .storage import canonical_json_bytes
    baseline = verify_legacy_baseline(root, plan["baseline"])
    original = next(page for page in baseline["pages"] if page["case_id"] == case["case_id"])
    manifest, selected, contract, request = _rebaseline_image_inputs(root, case, original)
    contract_sha = manifest["provider_contract"]["sha256"]
    if execute and contract_sha not in provider_contracts:
        raise ReplayError("paired_rebaseline_provider_scope_mismatch", "blocked")
    directory = _safe_directory(root, case["old_output"])
    expected = {"plan": plan_reference, "selection": case["old_selection"], "snapshot": case["old_snapshot"],
                "environment": plan["environment"], "request": selected["request"],
                "provider_contract": manifest["provider_contract"], "theme_source": manifest["theme_source"]}
    # 该 envelope 只适配传输 owner；不授予旧链新 recipe/binding 资格。
    envelope = {"kind": "image-recipe-input", "canvas": {"width": 2560, "height": 1440},
                "page_id": case["page_id"], "recipe_id": "historical-prompt:" + manifest["export_digest"],
                "prompt": request["prompt"]}
    identity = digest({"request": request, "recipe_input": envelope, "contract": contract_sha,
                       "materialization_binding_digest": None, "run_id": None, "input_generation": None})
    input_path = case["old_output"] + "/execution-input.json"
    if execute:
        if directory.exists() and not (directory / "execution-input.json").exists():
            raise ReplayError("paired_rebaseline_output_conflict", "stale")
        _immutable_replay_bytes(root, input_path, canonical_json_bytes(expected))
    if _document(root, file_reference(root, input_path)) != expected:
        raise ReplayError("paired_rebaseline_old_execution_stale", "stale")
    sidecar = directory / "page.png.provider.json"
    if execute and not sidecar.exists():
        context = build_execution_context(Path(root) / manifest["provider_contract"]["path"], directory)
        if (context.contract_sha256 != contract_sha or context.provider != contract["provider"]
                or context.model != contract["model"] or context.mode != "generate"):
            raise ReplayError("paired_rebaseline_execution_contract_changed", "stale")
        def checkpoint(_phase):
            _rebaseline_image_inputs(root, case, original)
            if environment_fingerprint() != plan["environment"]:
                raise ReplayError("paired_rebaseline_environment_mismatch", "stale")
        export_provider_image(envelope, context=context, output_root=directory, binding=None, checkpoint=checkpoint)
    receipt_ref = file_reference(root, sidecar.relative_to(root).as_posix())
    receipt = _document(root, receipt_ref)
    verify_provider_export(receipt, root=directory, binding=None)
    if receipt.get("evidence_source") != "provider-http":
        raise ReplayError("paired_rebaseline_real_provider_required", "blocked")
    if (receipt.get("input_digest") != identity or receipt.get("page_id") != case["page_id"]
            or receipt.get("recipe_id") != envelope["recipe_id"] or receipt.get("contract_sha256") != contract_sha
            or receipt.get("provider") != contract["provider"] or receipt.get("model") != contract["model"]
            or any(key in receipt for key in ("binding_digest", "expression_binding_digest", "materialization_binding_digest"))
            or _document(directory, receipt["request"]) != request):
        raise ReplayError("paired_rebaseline_old_image_export_stale", "stale")
    artifact = file_reference(root, (directory / receipt["artifact"]["path"]).relative_to(root).as_posix())
    record = {**expected, "artifact": artifact, "receipt": receipt_ref}
    record["receipt_digest"] = digest(record)
    record_path = case["old_output"] + "/execution.json"
    if execute:
        _immutable_replay_bytes(root, record_path, canonical_json_bytes(record))
    reference = file_reference(root, record_path)
    if _document(root, reference) != record:
        raise ReplayError("paired_rebaseline_old_execution_stale", "stale")
    return {"artifact": artifact, "receipt": receipt_ref, "execution": reference}


def execute_paired_rebaseline(root, reference, *, execute=False, provider_contracts=()):
    """同环境执行两侧物化；image 另需显式冻结 contract 执行范围。"""
    root = Path(root).absolute()
    plan = validate_paired_rebaseline_plan(root, reference)
    _rebaseline_provider_scope(root, plan, execute=execute, provider_contracts=provider_contracts)
    report = {"schema_version": 1, "kind": "paired-rebaseline-receipt", "plan": reference,
              "status": "blocked", "environment": plan["environment"], "cases": [], "gaps": [],
              "claim": "paired-runtime-only"}
    from .qualification import is_execution_source
    package = Path(__file__).parent
    snapshot = {}
    for path in sorted(package.rglob("*")):
        relative = path.relative_to(package).as_posix()
        if not path.is_file() or not is_execution_source(relative):
            continue
        archived = "qa/rebaseline-sources/" + plan["plan_digest"] + "/leo_ppt_generator/" + relative
        if execute:
            _immutable_replay_bytes(root, archived, read_evidence_bytes(package, relative))
        ref = file_reference(root, archived)
        if ref["sha256"] != file_reference(package, relative)["sha256"]:
            raise ReplayError("paired_rebaseline_execution_source_stale", "stale")
        snapshot[archived] = ref["sha256"]
    report["renderer_snapshot"] = snapshot
    for case in plan["cases"]:
        row = {"case_id": case["case_id"], "lane": case["lane"], "status": "blocked"}
        try:
            if case["lane"] == "render:html":
                old = _rebaseline_old_side(root, reference, plan, case, execute=execute)
            else:
                old = _rebaseline_old_image_side(root, reference, plan, case, execute=execute,
                                                 provider_contracts=provider_contracts)
            new = _rebaseline_new_side(root, case, execute=execute, provider_contracts=provider_contracts)
            row.update(status="passed", old=old, new=new)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            row.update(status=getattr(exc, "status", "blocked"), blocker=str(exc))
        report["cases"].append(row)
    validate_paired_rebaseline_plan(root, reference)
    report["gaps"] = [row["blocker"] for row in report["cases"] if row["status"] != "passed"]
    report["status"] = "passed" if not report["gaps"] else "blocked"
    report["receipt_digest"] = digest(report)
    return report


def verify_paired_rebaseline(root, reference, *, self_contained=False):
    recorded = _document(root, reference)
    _sealed(recorded, "receipt_digest")
    if recorded.get("kind") != "paired-rebaseline-receipt" or recorded.get("status") != "passed":
        raise ReplayError("paired_rebaseline_not_passed", "blocked")
    if self_contained:
        plan = _document(root, recorded["plan"])
        for case in plan["cases"]:
            request = _document(root, case["new_request"])
            library = Path(request["library_root"]).absolute()
            if not library.is_relative_to(Path(root).absolute()):
                raise ReplayError("capability_u6a_external_execution_library", "blocked")
            _safe_directory(root, library.relative_to(root).as_posix())
    current = execute_paired_rebaseline(root, recorded["plan"], execute=False)
    if current != recorded:
        raise ReplayError("paired_rebaseline_receipt_stale", "stale")
    return current


def verify_legacy_baseline(root, reference, *, self_contained=False):
    baseline = _document(root, reference)
    if baseline.get("kind") == "paired-rebaseline-receipt":
        rebase = verify_paired_rebaseline(root, reference, self_contained=self_contained)
        plan = _document(root, rebase["plan"])
        original = verify_legacy_baseline(root, plan["baseline"])
        result = deepcopy(original)
        for row in rebase["cases"]:
            page = next(p for p in result["pages"] if p["case_id"] == row["case_id"])
            page.update(artifact=row["old"]["artifact"], receipt=row["old"]["receipt"])
        result.update(environment=rebase["environment"], execution_source_snapshot=rebase["renderer_snapshot"],
                      paired_rebaseline=reference, original_baseline=plan["baseline"],
                      paired_new_sides={row["case_id"]: row["new"] for row in rebase["cases"]})
        result["baseline_digest"] = digest({"original": original["baseline_digest"], "rebaseline": rebase["receipt_digest"]})
        _baseline_execution_sources(result)
        return result
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
    _baseline_execution_sources(baseline)
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
        if page["lane"] == "image" and receipt.get("kind") == "legacy-image-export":
            exported = validate_legacy_image_export(root, page["receipt"])
            if (any(exported[key] != page[key] for key in ("page_id", "selection", "material", "artifact", "theme_family"))
                    or exported["source_revision"] != baseline["source_revision"]
                    or exported["capture_mode"] != baseline["capture_mode"]
                    or exported["contract_sha256"] != page["provider_contract_digest"]
                    or any(sources.get(path) != sha for path, sha in exported["source_snapshot"].items())):
                raise ReplayError("baseline_historical_image_join_mismatch", "stale")
            continue
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
            if receipt.get("evidence_source") != "provider-http":
                raise ReplayError("legacy_image_provider_http_evidence_required", "blocked")
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
        baseline = verify_legacy_baseline(root, plan["baseline"], self_contained=self_contained)
        report["baseline_digest"] = baseline["baseline_digest"]
        report["environment"] = environment_fingerprint()
        report["environment_comparison"] = paired_environment_compatibility(baseline, report["environment"])
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
            rebased_new = baseline.get("paired_new_sides", {}).get(case["case_id"])
            if rebased_new is not None and (artifact["sha256"] != rebased_new["artifact"]["sha256"]
                    or any(binding[key] != rebased_new[key] for key in ("expression_binding_digest", "materialization_binding_digest"))):
                raise ReplayError("paired_rebaseline_candidate_changed", "stale")
            old = before.get(case["case_id"])
            if old is None:
                row.update(status="blocked", blocker="baseline_pair_missing")
                continue
            if any(old[key] != case[key] for key in ("deck_id", "page_id", "lane", "theme_family", "material")):
                raise ReplayError("baseline_pair_input_mismatch", "stale")
            if lane == "image":
                from .storage import json_document_bytes, sha256_bytes
                if old["provider_contract_digest"] != sha256_bytes(json_document_bytes(payload["request"].get("provider_contract"))):
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
        verify_legacy_baseline(root, plan["baseline"], self_contained=self_contained)
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
