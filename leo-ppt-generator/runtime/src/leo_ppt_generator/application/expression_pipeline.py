"""唯一表达生产编排；原子输入先提交，RunIndex 和 lane 消费冻结代。"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from filelock import FileLock

from ..storage import atomic_write_json, canonical_json_bytes, fsync_directory
from ..qualification import read_evidence_bytes, file_reference
from ..content_projection import verify_binding_reference, verify_dual_binding_digests
from ..layout_selection import allocate_deck


class ExpressionPipelineError(ValueError):
    def __init__(self, reason_code, *, phase="request", retryable=False, details=None):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.phase = phase
        self.retryable = retryable
        self.details = details or {}

    def as_dict(self):
        return {"schema_version": 1, "kind": "PipelineFailure", "status": "failed",
                "reason_code": self.reason_code, "phase": self.phase,
                "retryable": self.retryable, "details": self.details}


def _digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def materialization_paths(run_root, lane, page_id):
    if lane not in {"render:html", "image"}:
        raise ExpressionPipelineError("materialization_binding_lane_unsupported")
    target = Path(run_root) / "rendered" / lane.replace(":", "-") / hashlib.sha256(page_id.encode()).hexdigest()[:20]
    return target / "page.png", target / ("page.png.render.json" if lane == "render:html" else "page.png.provider.json")


def _materialize_html_page(artifact, sidecar, *, binding, page, resolver, checkpoint):
    """先封存一页的输入、PNG 和收据，再原子公开；重试只读已提交页。"""
    from ..content_projection import materialize_html
    from ..render.page import render_page
    from ..render.provenance import load_render_receipt, verify_receipt_matches_artifact

    target = artifact.parent
    _safe_root(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = materialize_html(binding, page, resolver=resolver)

    def verify_committed(directory):
        for name in ("data.json", artifact.name, sidecar.name):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ExpressionPipelineError("materialization_page_incomplete", phase="materialization")
        try:
            actual = json.loads((directory / "data.json").read_bytes())
        except (ValueError, OSError) as exc:
            raise ExpressionPipelineError("materialization_input_mismatch", phase="materialization") from exc
        if actual != data:
            raise ExpressionPipelineError("materialization_input_mismatch", phase="materialization")
        receipt = load_render_receipt(directory / sidecar.name)
        if receipt["data_sha256"] != hashlib.sha256((directory / "data.json").read_bytes()).hexdigest():
            raise ExpressionPipelineError("materialization_input_mismatch", phase="materialization")
        verify_receipt_matches_artifact(receipt, directory / artifact.name)
        verify_binding_reference(receipt, binding)

    # 同页重试共用锁；渲染失败只留下不可见 staging，不生成半页成品。
    lock = target.parent / (target.name + ".lock")
    if lock.is_symlink():
        raise ExpressionPipelineError("materialization_output_conflict", phase="materialization")
    with FileLock(str(lock)):
        _safe_root(target)
        if target.exists():
            verify_committed(target)
            return
        with tempfile.TemporaryDirectory(prefix=".page-staging-", dir=target.parent) as temporary:
            staging = Path(temporary)
            _write_once(staging, "data.json", data)
            render_page(binding["template_id"], staging / "data.json", staging / artifact.name,
                        binding=binding, pack_page=page, resolver=resolver)
            receipt = load_render_receipt(staging / sidecar.name)
            receipt["out"] = str(artifact.resolve())
            atomic_write_json(staging / sidecar.name, receipt)
            verify_committed(staging)
            checkpoint("after_page_render")
            for path in staging.iterdir():
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
            fsync_directory(staging)
            # 不替换任何已有目录；竞争或外部写入保留原状态并失败。
            if target.exists() or target.is_symlink():
                raise ExpressionPipelineError("materialization_output_conflict", phase="materialization")
            staging.rename(target)
            fsync_directory(target.parent)
            checkpoint("after_page_publish")


def selection_digest(selection: dict[str, Any]) -> str:
    if not isinstance(selection, dict) or not selection:
        raise ExpressionPipelineError("selection_frozen_mismatch")
    for entry in selection.values():
        verify_binding_reference(entry)
    return _digest({pid: {key: entry[key] for key in ("layout_id", "expression_binding_digest", "materialization_binding_digest")}
                    for pid, entry in sorted(selection.items())})


@dataclass(frozen=True)
class PipelineRequest:
    pack: dict[str, Any]
    design_context: dict[str, Any]
    catalog_generation: str = ""
    lane_matrix: dict[str, list[str]] = field(default_factory=dict)
    run_root: str = ""
    run_id: str = ""
    library_root: str = ""
    policy_revision: str = "expression-policy-v1"
    explicit: dict[str, dict[str, str]] = field(default_factory=dict)
    purpose: str = "publication"
    provider_contract: dict[str, Any] | None = None
    proposals: dict[str, Any] = field(default_factory=dict)
    proposal_probe_cases: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, value):
        try:
            return cls(**value)
        except (TypeError, ValueError) as exc:
            raise ExpressionPipelineError("pipeline_request_schema_mismatch") from exc


def verify_selection_frozen(result):
    if (not isinstance(result, dict) or not result.get("selection_frozen")
            or result.get("selection_digest") != selection_digest(result.get("selection"))):
        raise ExpressionPipelineError("selection_frozen_mismatch", phase="compose")
    for entry in result["selection"].values():
        verify_binding_reference(entry, entry.get("binding"))
        verify_dual_binding_digests(entry["binding"])
        if not entry["binding"]["eligibility"]["qualified"]:
            raise ExpressionPipelineError("selection_unqualified", phase="qualification")


def _safe_root(path):
    root = Path(path).absolute()
    for parent in [*reversed(root.parents), root]:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ExpressionPipelineError("input_root_invalid", phase="freeze")
    return root


def _validate_payload(payload):
    from ..content_pack import verify_content_pack
    from ..templates import _design_digest
    from ..content_projection import binding_impact
    try:
        verify_content_pack(payload["pack"])
        pages = {page["page_id"]: page for page in payload["pack"]["pages"]}
        if not payload["asset_pins"] or not payload["lane_selections"]:
            raise ValueError("partial_input_freeze")
        requested_lanes = {lane for lanes in payload["request"]["lane_matrix"].values() for lane in lanes}
        if (set(payload["lane_selections"]) != requested_lanes or set(payload["designs"]) != requested_lanes
                or set(payload["bindings"]) != requested_lanes or not requested_lanes.issubset({"render:html", "image"})):
            raise ValueError("partial_input_freeze")
        expressions = {}
        for lane, selection in payload["lane_selections"].items():
            verify_selection_frozen(selection)
            if any(entry["binding"]["qualification_purpose"] != payload["request"]["purpose"] for entry in selection["selection"].values()):
                raise ValueError("input_qualification_purpose_mismatch")
            ids = {pid for pid, lanes in payload["request"]["lane_matrix"].items() if lane in lanes}
            if set(selection["selection"]) != ids or not ids.issubset(pages):
                raise ValueError("input_page_set_mismatch")
            design = payload["designs"][lane]
            if _design_digest(design) != design["design_digest"]:
                raise ValueError("input_design_digest_mismatch")
            if {p["page_id"] for p in design["pages"]} != ids:
                raise ValueError("input_design_page_mismatch")
            for pid, entry in selection["selection"].items():
                binding = payload["bindings"][lane][pid]
                if binding.get("proposal") and binding["proposal"]["run_scope"] != payload["request"]["run_id"]:
                    raise ValueError("proposal_run_scope_mismatch")
                if binding != entry["binding"] or binding["backend"] != lane or binding["page_id"] != pid:
                    raise ValueError("input_binding_join_mismatch")
                if lane == "image":
                    from ..storage import json_document_bytes
                    expected = hashlib.sha256(json_document_bytes(payload["request"]["provider_contract"])).hexdigest()
                    if binding["effective"].get("provider_contract_sha256") != expected:
                        raise ValueError("input_provider_contract_mismatch")
                if binding["content_digest"] != payload["pack"]["content_digest"]:
                    raise ValueError("input_content_digest_mismatch")
                designed_page = next(p for p in design["pages"] if p["page_id"] == pid)
                if (designed_page["layout_id"] != binding["layout_id"]
                        or binding["page_expression_digest"] != _digest(pages[pid]["expression"])
                        or binding["page_content_digest"] != pages[pid]["page_content_digest"]):
                    raise ValueError("input_binding_join_mismatch")
                if pid in expressions and expressions[pid] != binding["expression_binding_digest"]:
                    raise ValueError("expression_binding_cross_lane_mismatch")
                expressions[pid] = binding["expression_binding_digest"]
        if set(expressions) != set(pages):
            raise ValueError("partial_input_freeze")
        if payload.get("impact") != binding_impact(payload.get("previous_bindings", {}), payload["bindings"]):
            raise ValueError("input_impact_mismatch")
    except (KeyError, TypeError, ValueError) as exc:
        raise ExpressionPipelineError(str(exc), phase="freeze") from exc


def _write_once(root, relative, value):
    body = canonical_json_bytes(value)
    target = root / relative
    if target.exists() or target.is_symlink():
        try:
            if json.loads(read_evidence_bytes(root, relative)) != value:
                raise ValueError("different bytes")
        except (ValueError, OSError) as exc:
            raise ExpressionPipelineError("input_generation_conflict", phase="freeze") from exc
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(target, value)


def _manifest_files(root):
    return {path.relative_to(root).as_posix(): file_reference(root, path.relative_to(root).as_posix())["sha256"]
            for path in sorted(root.rglob("*")) if (not path.is_dir() or path.is_symlink())
            and path.relative_to(root).as_posix() != "input-manifest.json"}


def _read_generation(directory, *, generation, expected_manifest=None):
    try:
        manifest = json.loads(read_evidence_bytes(directory, "input-manifest.json"))
        if manifest["generation"] != generation or (expected_manifest is not None and _digest(manifest) != expected_manifest):
            raise ValueError("manifest identity")
        if manifest["files"] != _manifest_files(directory):
            raise ValueError("manifest files")
        payload = json.loads(read_evidence_bytes(directory, "generation.json"))
        if _digest(payload) != generation:
            raise ValueError("generation identity")
        _validate_payload(payload)
        return payload, manifest
    except (KeyError, ValueError, OSError) as exc:
        raise ExpressionPipelineError("input_generation_invalid", phase="freeze") from exc


def load_committed_input(run_root):
    root = _safe_root(run_root)
    try:
        pointer = json.loads(read_evidence_bytes(root, "input/current.json"))
    except (OSError, ValueError) as exc:
        raise ExpressionPipelineError("input_pointer_missing", phase="freeze") from exc
    generation = pointer.get("generation")
    if (not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{64}", generation)
            or set(pointer) != {"schema_version", "generation", "manifest_digest"}
            or pointer["schema_version"] != 1
            or not isinstance(pointer["manifest_digest"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", pointer["manifest_digest"])):
        raise ExpressionPipelineError("input_pointer_invalid", phase="freeze")
    directory = root / "input/generations" / generation
    payload, manifest = _read_generation(directory, generation=generation, expected_manifest=pointer.get("manifest_digest"))
    return {"root": directory, "generation": generation, "payload": payload, "manifest": manifest}


def committed_input_root(run_root):
    return load_committed_input(run_root)["root"]


def _recover_payload(run_root, input_digest):
    """pointer 前的中断只能复用同请求的冻结数据，不能再次调用分配器。"""
    found = {}
    for subtree in ("input/generations", "input/.staging"):
        base = run_root / subtree
        if not base.exists():
            continue
        _safe_root(base)
        for directory in sorted(base.iterdir()):
            if not re.fullmatch(r"[0-9a-f]{64}", directory.name):
                raise ExpressionPipelineError("input_generation_invalid", phase="freeze")
            _safe_root(directory)
            payload = json.loads(read_evidence_bytes(directory, "generation.json"))
            if payload.get("request", {}).get("input_digest") != input_digest:
                raise ExpressionPipelineError("input_generation_conflict", phase="freeze")
            if _digest(payload) != directory.name:
                raise ExpressionPipelineError("input_generation_invalid", phase="freeze")
            _validate_payload(payload)
            found[directory.name] = payload
    if len(found) > 1:
        raise ExpressionPipelineError("input_generation_conflict", phase="freeze")
    return next(iter(found.values()), None)


def write_atomic_input_generation(run_root, payload, *, generation, resolver=None, checkpoint=None):
    """staging → immutable generation → current；相同输入重试不会重写或覆盖。"""
    if not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{64}", generation) or generation != _digest(payload):
        raise ExpressionPipelineError("input_generation_digest_mismatch", phase="freeze")
    _validate_payload(payload)
    root = _safe_root(run_root)
    root.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint or (lambda phase: None)
    lock = root / ".input.lock"
    if lock.is_symlink():
        raise ExpressionPipelineError("input_lock_invalid", phase="freeze")
    with FileLock(str(lock)):
        pointer_path = root / "input/current.json"
        if pointer_path.exists() or pointer_path.is_symlink():
            committed = load_committed_input(root)
            if committed["generation"] != generation:
                raise ExpressionPipelineError("input_generation_conflict", phase="freeze")
            return committed["root"]
        immutable = root / "input/generations" / generation
        if immutable.exists() or immutable.is_symlink():
            _, manifest = _read_generation(immutable, generation=generation)
        else:
            staging = _safe_root(root / "input/.staging" / generation)
            staging.mkdir(parents=True, exist_ok=True)
            primary_lane = sorted(payload["lane_selections"])[0]
            documents = {"generation.json": payload, "page-content-pack.json": payload["pack"],
                "lane-selections.json": payload["lane_selections"], "resolved-designs.json": payload["designs"],
                "bindings.json": payload["bindings"], "asset-pins.json": payload["asset_pins"],
                "impact.json": payload["impact"],
                "layout-selection.json": payload["lane_selections"][primary_lane],
                "resolved-design.json": payload["designs"][primary_lane]}
            if "image" in payload["bindings"]:
                documents["provider-contract.json"] = payload["request"]["provider_contract"]
            for relative, value in documents.items():
                _write_once(staging, relative, value)
            checkpoint("after_documents")
            if resolver is None:
                raise ExpressionPipelineError("input_asset_resolver_missing", phase="freeze")
            frozen = resolver.freeze_assets(staging / "asset-snapshot", payload["asset_pins"])
            from ..qualification import freeze_qualification_evidence
            from ..content_projection import verify_effective_binding
            pages = {page["page_id"]: page for page in payload["pack"]["pages"]}
            try:
                for lane, bindings in payload["bindings"].items():
                    for pid, binding in bindings.items():
                        freeze_qualification_evidence(binding["eligibility"]["checks"]["qualification"],
                            source_root=resolver.resolve(binding["layout_id"])["trusted_root"],
                            target_root=frozen.resolve(binding["layout_id"])["trusted_root"])
                        verify_effective_binding(binding, pages[pid], resolver=frozen,
                                                 frozen_design=payload["designs"][lane])
            except (ValueError, KeyError, OSError) as exc:
                raise ExpressionPipelineError(str(exc), phase="freeze") from exc
            checkpoint("after_evidence")
            manifest = {"schema_version": 1, "generation": generation, "files": _manifest_files(staging)}
            _write_once(staging, "input-manifest.json", manifest)
            _read_generation(staging, generation=generation)
            checkpoint("before_generation")
            immutable.parent.mkdir(parents=True, exist_ok=True)
            os.rename(staging, immutable)
            fsync_directory(immutable.parent)
        checkpoint("before_pointer")
        atomic_write_json(pointer_path, {"schema_version": 1, "generation": generation, "manifest_digest": _digest(manifest)})
        checkpoint("after_pointer")
        return immutable


def _request_body(request):
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).parents[1] / "schemas/expression-pipeline-v1.schema.json").read_text())
    body = asdict(request)
    if list(Draft202012Validator(schema["$defs"]["PipelineRequest"]).iter_errors(body)):
        raise ExpressionPipelineError("pipeline_request_schema_mismatch")
    return body


def qualify_pipeline_lane(request, lane, *, resolver, proposal_factory=None):
    """生产与失败证据重核共用资格计算，不冻结输入、不渲染或调用 Provider。"""
    pages = [page for page in request.pack["pages"] if lane in request.lane_matrix[page["page_id"]]]
    selected = allocate_deck({**request.pack, "pages": pages}, request.design_context, backend=lane,
        explicit=request.explicit.get(lane), resolver=resolver, qualification_purpose=request.purpose,
        provider_contract=request.provider_contract if lane == "image" else None, proposal_factory=proposal_factory)
    return selected


def run_expression_pipeline(request: PipelineRequest, *, resolver=None, checkpoint=None):
    """route 调用的唯一生产 owner；qualification 失败时不创建可见 run 输入。"""
    from ..asset_resolver import AssetResolver
    from ..content_pack import verify_content_pack
    from ..content_projection import materialize_html, materialize_image_prompt, verify_effective_binding
    from ..templates import compose_design
    from .run_index import RunIndex
    if not isinstance(request, PipelineRequest):
        raise ExpressionPipelineError("pipeline_request_schema_mismatch")
    if resolver is not None and not getattr(resolver, "execution_allowed", True):
        raise ExpressionPipelineError("diagnostic_resolver_not_executable")
    body = _request_body(request)
    verify_content_pack(request.pack)
    ids = {page["page_id"] for page in request.pack["pages"]}
    if set(request.lane_matrix) != ids:
        raise ExpressionPipelineError("pipeline_lane_matrix_incomplete")
    if not set(request.proposals).issubset(ids):
        raise ExpressionPipelineError("proposal_page_scope_mismatch")
    run_root = _safe_root(request.run_root)
    from contextlib import ExitStack
    from ..library_migration import library_operation, require_available
    with ExitStack() as library_locks:
        if request.library_root:
            require_available(request.library_root)
            # 已冻结任务允许源库离线；仍存在的源库必须参与发布互斥。
            if Path(request.library_root).is_dir():
                library_locks.enter_context(library_operation(request.library_root))
        if resolver is None and not (run_root / "input/current.json").exists():
            resolver = AssetResolver(library=Path(request.library_root))
        if resolver is not None:
            library_locks.enter_context(resolver.library_session())
        input_digest = _digest({key: value for key, value in body.items() if key not in {"run_root", "library_root"}})
        checkpoint = checkpoint or (lambda phase: None)
        proposal_factory = None
        if request.proposals and not (run_root / "input/current.json").exists():
            from ..task_local_layout_proposals import prepare_proposal_workspace, proposal_candidate_factory, validate_task_local_proposal
            resolver = resolver or AssetResolver(library=Path(request.library_root))
            for document in request.proposals.values():
                base = resolver.resolve(document["base_asset"])
                template_id = base["data"].get("renderer_support", {}).get("render:html")
                validate_task_local_proposal(document, run_scope=request.run_id, allowed_assets={base["asset_id"]},
                    resolver_root=base["trusted_root"], base_profile=base["data"], base_generation=resolver.generation,
                    template=resolver.resolve(template_id)["data"] if template_id else None)
            resolver = prepare_proposal_workspace(resolver, run_root=run_root, run_scope=request.run_id, input_digest=input_digest)
            proposal_factory = proposal_candidate_factory(request.proposals, resolver=resolver, run_scope=request.run_id,
                design_context=request.design_context, probe_cases=request.proposal_probe_cases)
        if (run_root / "input/current.json").exists():
            committed = load_committed_input(run_root)
            if committed["payload"]["request"]["input_digest"] != input_digest:
                raise ExpressionPipelineError("input_generation_conflict", phase="freeze")
            payload = committed["payload"]
            directory, generation = committed["root"], committed["generation"]
        elif (recovered := _recover_payload(run_root, input_digest)) is not None:
            payload = recovered
            generation = _digest(payload)
            resolver = resolver or AssetResolver(library=Path(request.library_root))
            directory = write_atomic_input_generation(run_root, payload, generation=generation, resolver=resolver, checkpoint=checkpoint)
        else:
            resolver = resolver or AssetResolver(library=Path(request.library_root))
            if resolver.generation != request.catalog_generation:
                raise ExpressionPipelineError("pipeline_catalog_generation_mismatch")
            selections, designs, bindings, pins = {}, {}, {}, {}
            lanes = sorted({lane for requested in request.lane_matrix.values() for lane in requested})
            for lane in lanes:
                pages = [page for page in request.pack["pages"] if lane in request.lane_matrix[page["page_id"]]]
                selected = qualify_pipeline_lane(request, lane, resolver=resolver, proposal_factory=proposal_factory)
                if request.proposals:
                    from ..task_local_layout_proposals import curation_feedback
                    feedback = {pid: curation_feedback(request.proposals[pid], attempts)
                        for pid, attempts in selected["proposal_attempts"].items() if pid in request.proposals}
                    atomic_write_json(run_root / "qa" / ("proposal-curation-" + lane.replace(":", "-") + ".json"), feedback)
                if selected["status"] != "complete":
                    raise ExpressionPipelineError(selected["status"], phase="qualification", details=selected["page_status"])
                selected.update(selection_frozen=True, selection_digest=selection_digest(selected["selection"]))
                verify_selection_frozen(selected)
                selections[lane] = selected
                bindings[lane] = {pid: entry["binding"] for pid, entry in selected["selection"].items()}
                compose_pages = []
                for page in pages:
                    binding = bindings[lane][page["page_id"]]
                    slots = materialize_html(binding, page, resolver=resolver) if lane == "render:html" else {}
                    compose_pages.append({"page_id": page["page_id"], "page_no": page["number"],
                        "page_role": page["narrative_role"], "layout": binding["layout_id"], "slots": slots})
                    for pin in binding["effective"]["assets"]:
                        if pin["asset_id"] in pins and pins[pin["asset_id"]] != pin:
                            raise ExpressionPipelineError("input_asset_pin_conflict", phase="freeze")
                        pins[pin["asset_id"]] = pin
                designs[lane] = compose_design(request.design_context["style"]["asset_id"], pages=compose_pages,
                    selection=selected, design_context=request.design_context, resolver=resolver)
                verify_selection_frozen(selected)
                for page in pages:
                    verify_effective_binding(bindings[lane][page["page_id"]], page, resolver=resolver, frozen_design=designs[lane])
            payload = {"request": {"run_id": request.run_id, "input_digest": input_digest,
                                  "catalog_generation": request.catalog_generation, "policy_revision": request.policy_revision,
                                  "lane_matrix": request.lane_matrix, "purpose": request.purpose,
                                  "provider_contract": request.provider_contract},
                       "pack": request.pack, "lane_selections": selections, "designs": designs,
                       "bindings": bindings, "asset_pins": sorted(pins.values(), key=lambda pin: pin["asset_id"])}
            from ..content_projection import binding_impact
            payload["impact"] = binding_impact({}, bindings)
            generation = _digest(payload)
            directory = write_atomic_input_generation(run_root, payload, generation=generation, resolver=resolver, checkpoint=checkpoint)
        index = RunIndex.create(run_root, route="generate", runtime_identity=request.policy_revision, run_id=request.run_id)
        index.register_input_generation(generation)
        checkpoint("after_run_index")
        frozen_resolver = AssetResolver.from_snapshot(directory / "asset-snapshot")
        outputs = {}
        for lane, by_page in payload["bindings"].items():
            outputs[lane] = {}
            for pid, binding in by_page.items():
                page = next(p for p in payload["pack"]["pages"] if p["page_id"] == pid)
                artifact, sidecar = materialization_paths(run_root, lane, pid)
                target = artifact.parent
                if lane == "render:html":
                    _materialize_html_page(artifact, sidecar, binding=binding, page=page,
                                          resolver=frozen_resolver, checkpoint=checkpoint)
                    outputs[lane][pid] = {"status": "passed", "artifact": str(artifact), "receipt": str(sidecar),
                                          "expression_binding_digest": binding["expression_binding_digest"],
                                          "materialization_binding_digest": binding["materialization_binding_digest"]}
                else:
                    _safe_root(target)
                    target.mkdir(parents=True, exist_ok=True)
                    prompt = materialize_image_prompt(binding, page, payload["designs"][lane], resolver=frozen_resolver)
                    _write_once(target, "provider-input.json", prompt)
                    from ..backend_execution import build_execution_context, BackendExecutionError
                    from ..image_deck.expression_adapter import export_provider_image, ImageExportError
                    try:
                        context = build_execution_context(directory / "provider-contract.json", run_root)
                        export_provider_image(prompt, context=context, output_root=target, binding=binding,
                                              pack_page=page, resolver=frozen_resolver,
                                              run_id=request.run_id, input_generation=generation)
                        outputs[lane][pid] = {"status": "passed", "artifact": str(artifact), "receipt": str(sidecar)}
                    except (ImageExportError, BackendExecutionError) as exc:
                        outputs[lane][pid] = {"status": "blocked", "reason_code": str(exc)}
                    outputs[lane][pid].update({key: binding[key] for key in ("expression_binding_digest", "materialization_binding_digest")})
        result = {"schema_version": 1, "kind": "PipelineResult", "run_id": request.run_id,
            "input_digest": input_digest, "input_generation": generation,
            "selection": payload["lane_selections"], "resolved_design": payload["designs"],
            "bindings": payload["bindings"], "receipt_refs": outputs,
            "purpose": request.purpose, "publication_ready": False,
            "status": "blocked" if any(row["status"] == "blocked" for lane in outputs.values() for row in lane.values()) else
                      ("lanes_materialized" if "image" in outputs else "html_validated")}
        atomic_write_json(run_root / "pipeline-result.json", result)
        return result
