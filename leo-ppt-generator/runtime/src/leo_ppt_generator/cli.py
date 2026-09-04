"""leo-ppt 的版本化确定性命令接口。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__
from .application.routes import (
    ROUTES,
    RouteContractError,
    classify_input,
    route_definition,
    select_route,
)
from .application.run_index import IdempotencyConflict, RevisionConflict, RunIndex
from .backend_execution import BackendExecutionError
from .config.backend_contract import BackendContractError, BackendRegistry
from .config.channel_catalog import channel_by_name, channel_names
from .config.provider_registry import ProviderRegistry
from .config.receipt_store import FileReceiptStore
from .config.models import HostCapabilityState, ProviderName, RouteName
from .config.reason_codes import ReasonCode
from .config.service import ConfigService, ConfigServiceError, StatusRequest
from .config.wizard import ConfigWizard, WizardCancelled
from .config.runtime_config import (
    RuntimeConfigError,
    assert_run_quota,
    configure_openai_compatible_profile,
    configure_provider_profile,
    default_home,
    load_runtime_config,
    openai_compatible_profile,
)
from .contracts import ContractError, PageArtifact
from .credentials import (
    PROVIDERS,
    CredentialError,
    CredentialInputResolver,
    credential_manager,
)
from .editable.adapter import EditableAdapter
from .evidence import EvidenceError, record_acceptance, record_provenance, record_visual
from .hybrid.assembler import HybridAssembler
from .image_deck.adapter import ImageDeckAdapter
from .lifecycle import CleanupConflict, Lifecycle
from .render.chart import render_chart
from .render.errors import RenderError
from .render.page import parse_size, render_page
from .render.provenance import attach_provenance_to_slide, load_render_receipt
from .render.raster import rasterize_svg
from .render.readiness import probe_fast as render_probe_fast
from .render.readiness import render_ready as _render_readiness_report
from .render.receipt import RECEIPT_RELATIVE_PATH, ReceiptError, create_delivery_receipt, verify_delivery_receipt
from .observability import (
    command_name,
    record_command,
    resolve_run_dir,
    primary_action_for,
    utc_now,
    write_delivery_reports,
)
from .setup import SetupContractError, build_setup_report, render_setup_report
from .storage import (
    atomic_write_json,
    canonical_json,
    durable_copy_file,
    fsync_directory,
    inspect_regular_file,
    secure_user_tree,
    sha256_bytes,
)
from .styles import StyleStoreError, list_styles, load_style, save_style
from .layout_bank import (
    CapacityFilterError,
    filter_layout_bank_by_capacity,
    list_layout_bank,
    load_layout_bank,
    load_style_layouts,
)
from .templates import (
    StyleColorOverrideError,
    StyleVarOverrideError,
    TemplateError,
    compose_layout,
    compose_style,
    list_templates,
)
from .upgrade.baseline import (
    import_baseline,
    inspect_image_delivery,
    load_baseline,
)
from .upstream_bridge import CODEX_TOOLS, UpstreamBridgeError, run_upstream

PROTOCOL = "leo-ppt-machine/v1"
MAX_SLIDES_CONTRACT_BYTES = 1024 * 1024

# provider 枚举从 checked-in 渠道目录派生；新增渠道不改本文件。
CHANNEL_PROVIDERS = channel_names()
EXTERNAL_PROVIDER_CHOICES = ("openai", "openai-compatible", "atlascloud", *CHANNEL_PROVIDERS)
BACKEND_PROVIDER_CHOICES = ("builtin-imagegen", *EXTERNAL_PROVIDER_CHOICES)
PROFILE_CONFIGURABLE_PROVIDERS = ("openai-compatible", *CHANNEL_PROVIDERS)
PROVIDER_EXAMPLES = "|".join(EXTERNAL_PROVIDER_CHOICES)


def _duration_seconds(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("duration must be a number") from exc
    if parsed < 0 or parsed > 7 * 24 * 60 * 60:
        raise argparse.ArgumentTypeError("duration must be between 0 and 604800 seconds")
    return parsed


def envelope(status: str, reason_code: str, **payload: Any) -> dict[str, Any]:
    result = {
        "protocol": PROTOCOL,
        "schema_version": 1,
        "status": status,
        "reason_code": reason_code,
        **payload,
    }
    result.setdefault("artifact_refs", [])
    result.setdefault("evidence_refs", [])
    result.setdefault("warnings", [])
    result.setdefault("blockers", [])
    result.setdefault("message", f"操作结果：{reason_code}")
    result.setdefault(
        "suggested_actions",
        ["运行 run diagnose 并按 reason-codes.md 处理"]
        if status in {"blocked", "failed", "interrupted"}
        else [],
    )
    return result


def _version_report() -> dict[str, Any]:
    """返回不读取配置、不访问网络的版本合同。"""

    runtime_identity = None
    bundle_root = None
    install_channel = None
    try:
        current = json.loads((default_home() / "current").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        current = {}
    if isinstance(current.get("runtime_identity"), str):
        runtime_identity = current["runtime_identity"]
    if isinstance(current.get("bundle_root"), str):
        bundle_root = current["bundle_root"]
    _KNOWN_CHANNELS = {"plugin", "agent-skill", "standalone"}
    recorded = current.get("install_channel")
    if isinstance(recorded, str) and recorded in _KNOWN_CHANNELS:
        install_channel = recorded
    else:
        # 元数据缺失或非法渠道（空串、手改值）时按 bundle 路径推导，不原样透传。
        normalized_bundle = str(bundle_root or "").replace("\\", "/")
        if "/plugins/" in normalized_bundle:
            install_channel = "plugin"
        elif "/.agents/skills/" in normalized_bundle:
            install_channel = "agent-skill"
        elif bundle_root:
            install_channel = "standalone"
        else:
            install_channel = "unknown"
    return {
        "protocol": "leo-ppt-version/v1",
        "schema_version": 1,
        "status": "ready",
        "reason_code": "version_reported",
        "package_version": __version__,
        "runtime_version": __version__,
        "runtime_identity": runtime_identity,
        "install_channel": install_channel,
        "config_schema_version": 2,
        "setup_schema_version": 1,
        "cli_path": str(Path(sys.argv[0]).resolve()) if sys.argv else None,
    }


def _runtime_manager_metadata() -> tuple[Path, Path] | None:
    """读取安装 manager 的受管 current 元数据。"""

    current_path = default_home() / "current"
    try:
        value = json.loads(current_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    manager = value.get("runtime_manager")
    bundle = value.get("bundle_root")
    if not isinstance(manager, str) or not isinstance(bundle, str):
        return None
    manager_path = Path(manager).expanduser().resolve()
    bundle_path = Path(bundle).expanduser().resolve()
    if not manager_path.is_file() or not bundle_path.is_dir():
        return None
    return manager_path, bundle_path


def _dispatch_runtime_lifecycle(args: argparse.Namespace) -> dict[str, Any]:
    metadata = _runtime_manager_metadata()
    if metadata is None:
        return envelope(
            "blocked",
            "runtime_manager_unavailable",
            primary_action={"kind": "run_cli", "command": "重新运行安装器或 bootstrap"},
        )
    manager, _bundle = metadata
    command = [sys.executable, str(manager), "rollback"]
    if args.identity:
        command.extend(["--identity", args.identity])
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=900,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return envelope("blocked", "runtime_lifecycle_unavailable", message=str(exc))
    stream = result.stdout if result.stdout.strip() else result.stderr
    try:
        payload = json.loads(stream)
    except (TypeError, json.JSONDecodeError):
        return envelope(
            "blocked",
            "runtime_lifecycle_protocol_invalid",
            details={"stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]},
        )
    if not isinstance(payload, dict):
        return envelope("blocked", "runtime_lifecycle_protocol_invalid")
    status = "ready" if result.returncode == 0 else "blocked"
    reason = str(payload.get("reason_code", "runtime_rolled_back"))
    if result.returncode != 0:
        reason = str(payload.get("reason_code", "runtime_lifecycle_failed"))
    return envelope(status, reason, runtime=payload)


def doctor_report(route: str | None) -> dict[str, Any]:
    if route is not None and route not in ROUTES:
        return envelope(
            "blocked",
            "unknown_route",
            route=route,
            checks={"package_import": "passed", "route": "failed"},
            warnings=[],
        )
    required = {"generate"} if route == "generate" else ({"edit"} if route else set())
    backend = BackendRegistry.default().select("fixture", required=required)
    config_error: RuntimeConfigError | None = None
    try:
        config = load_runtime_config()
        config_report: dict[str, Any] = {
            "status": "passed",
            "path": str(config.path),
            "values": {
                key: {"value": value, "source": config.sources[key], "route": route or "all"}
                for key, value in config.values.items()
            },
            "warnings": list(config.warnings),
        }
    except RuntimeConfigError as exc:
        config_error = exc
        config_report = {
            "status": "failed",
            "reason_code": str(exc),
            "path": str(default_home() / "config.yaml"),
            "values": {},
            "warnings": [],
        }
    directory_fsync = fsync_directory(Path(__file__).resolve().parent)
    warnings = [
        "真实 provider、OCR、Office viewer 与 PowerPoint 桌面仍需分别现场验证。",
        *config_report["warnings"],
    ]
    if not directory_fsync:
        warnings.append("当前文件系统不支持目录 fsync；barrier durability 已降级。")
    office_viewer = shutil.which("libreoffice") or shutil.which("soffice")
    office_needed = route in {"direct-editable", "upgrade-full", "upgrade-selected"}
    manager = credential_manager()

    def credential_reference(provider: str) -> dict[str, Any]:
        try:
            report = manager.status(provider)
        except CredentialError:
            return {
                "status": "resolver_unavailable",
                "reference_type": "os-store",
                "evidence_refs": [f"credential://status/{provider}"],
            }
        return {
            "status": report["status"],
            "reference_type": report["reference_type"],
            "evidence_refs": report["evidence_refs"],
        }

    credential_references = {
        "builtin-imagegen": {"status": "host_check_required", "reference_type": "host-managed", "evidence_refs": ["doctor://credential/builtin-imagegen"]},
        **{provider: credential_reference(provider) for provider in PROVIDERS},
    }
    provider_available = any(
        credential_references[provider]["status"] == "available"
        for provider in EXTERNAL_PROVIDER_CHOICES
    )
    compatible_profile = openai_compatible_profile() if config_error is None else None
    readiness = {
        "local_runtime": {"status": "ready", "reason_code": "package_import_passed"},
        "config": config_report,
        "credential_reference": {
            "status": "available" if provider_available else "missing",
            "reason_code": "credential_reference_available" if provider_available else "credential_reference_missing",
        },
        "worker": {
            "status": "host_check_required",
            "reason_code": "worker_host_capability_unverified",
        },
        "provider": {
            "status": "not_probed",
            "reason_code": "provider_field_smoke_required",
        },
        "office_viewer": {
            "status": "available" if office_viewer else ("optional_missing" if office_needed else "not_required"),
            "path": office_viewer,
        },
        "manual_acceptance": {
            "status": "required",
            "reason_code": "manual_visual_acceptance_required",
        },
        "render_backend": _render_readiness_doctor_facet(),
        "route_contract": {"status": "passed" if route else "not_requested"},
    }
    status = "blocked" if config_error else "ready"
    reason_code = str(config_error) if config_error else "ready"
    readiness_summary = {
        "local_mechanism": "blocked" if config_error else "ready",
        "field_execution": "action_required",
        "next_actions": (
            ["fix_runtime_config"]
            if config_error
            else [
                "create_and_validate_backend_contract",
                "verify_worker_capability",
                "run_provider_smoke",
                "record_manual_acceptance",
            ]
        ),
    }
    return envelope(
        status,
        reason_code,
        route=route,
        checks={
            "package_import": "passed",
            "route": "passed" if route else "not_requested",
            "image_deck_adapter": "passed",
            "editable_adapter": "passed",
            "backend_contract": backend.name,
            "directory_fsync": "passed" if directory_fsync else "degraded",
            "office_viewer": office_viewer or ("optional_missing" if office_needed else "not_required"),
        },
        config=config_report["values"],
        readiness=readiness,
        readiness_summary=readiness_summary,
        credential_references=credential_references,
        provider_profiles={
            "openai-compatible": {
                "status": "available" if compatible_profile else "missing",
                "endpoint_origin": compatible_profile.get("endpoint_origin") if compatible_profile else None,
                "model": compatible_profile.get("model") if compatible_profile else None,
            }
        },
        warnings=warnings,
    )


def _json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _render_readiness_doctor_facet() -> dict[str, Any]:
    """doctor 的 render_backend 分面：可选能力，missing 不阻断整体 status。

    默认走零 driver 的文件系统级探测（``probe_fast``；不 spin playwright
    driver，避免高频 doctor 的 asyncio teardown 噪声）；启动级真值以
    ``render ready`` 为准，``LEO_PPT_RENDER_DOCTOR_LAUNCH=1`` 打开完整探测。
    """

    if os.environ.get("LEO_PPT_RENDER_DOCTOR_LAUNCH") == "1":
        report = _render_readiness_report()
    else:
        report = render_probe_fast().to_dict()
    return {
        "status": report["status"].removeprefix("render_backend_"),
        "reason_code": report["status"],
        "optional": True,
        "playwright_version": report.get("playwright_version"),
        "chromium_version": report.get("chromium_version"),
        "chromium_path": report.get("chromium_path"),
        "fonts_present": report.get("fonts_present"),
        "install_guide": report.get("install_guide"),
        "warnings": report.get("warnings", []),
    }


def _parse_pages(value: str | None) -> set[int]:
    if not value:
        return set()
    return {int(item) for item in value.split(",") if item.strip()}


def _runtime_identity(explicit: str | None) -> str:
    if explicit:
        return explicit
    configured = os.environ.get("LEO_PPT_RUNTIME_IDENTITY")
    if configured:
        return configured
    executable = Path(sys.executable).absolute()
    # macOS venv 的 python 通常是指向 Homebrew/framework Python 的符号链接。
    # 先沿调用路径查找受管 runtime receipt；resolve 后的解释器路径只作兼容回退。
    candidates = (executable, executable.resolve())
    seen: set[Path] = set()
    for candidate in candidates:
        for parent in candidate.parents:
            if parent in seen:
                continue
            seen.add(parent)
            receipt = parent / "runtime.json"
            if receipt.is_file():
                try:
                    value = _json_file(receipt)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                identity = value.get("runtime_identity")
                if isinstance(identity, str) and identity:
                    return identity
    return f"development-{__version__}"


def _run_path(args: argparse.Namespace) -> str:
    value = getattr(args, "run_path", None) or getattr(args, "run_dir", None)
    if not value:
        raise ContractError("run_path_required")
    return str(value)


def _state_hash(run: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(run).encode())


def _domain_path(run_path: str | Path, domain: str) -> Path:
    root = Path(run_path).resolve()
    return root / domain if (root / "run.json").is_file() else root


def _delivery_output_path(run_path: str | Path, requested: str | None) -> str:
    root = Path(run_path).resolve()
    default = root / "final/deck.pptx"
    if not (root / "run.json").is_file():
        return str(Path(requested).resolve() if requested else default)
    final_root = root / "final"
    if final_root.is_symlink():
        raise ContractError("output_path_untrusted")
    target = Path(requested).resolve() if requested else default
    try:
        target.relative_to(final_root.resolve())
    except ValueError as exc:
        raise ContractError("output_outside_run") from exc
    return str(target)


def _freeze_slides_contract(run_path: str | Path, source_path: str | Path) -> Path:
    root = Path(run_path).resolve()
    source = Path(source_path)
    if not (root / "run.json").is_file():
        return source
    try:
        source_identity = inspect_regular_file(source, max_bytes=MAX_SLIDES_CONTRACT_BYTES)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc
    target = root / "input/slides.json"
    try:
        if target.is_file() or target.is_symlink():
            frozen_identity = inspect_regular_file(
                target, max_bytes=MAX_SLIDES_CONTRACT_BYTES
            )
            if frozen_identity["sha256"] != source_identity["sha256"]:
                raise ContractError("slides_fingerprint_conflict")
        else:
            durable_copy_file(
                source_identity["path"], target, max_bytes=MAX_SLIDES_CONTRACT_BYTES
            )
    except ValueError as exc:
        raise ContractError(str(exc)) from exc

    index = RunIndex(root)
    snapshot = index.snapshot()
    supplemental_inputs = snapshot.get("supplemental_inputs", {})
    if not isinstance(supplemental_inputs, dict):
        raise ContractError("run_index_invalid")
    existing = supplemental_inputs.get("slides")
    if existing is not None and not isinstance(existing, dict):
        raise ContractError("run_index_invalid")
    metadata = {
        "original_path": (
            existing.get("original_path")
            if isinstance(existing, dict) and existing.get("original_path")
            else str(source_identity["path"])
        ),
        "path": "input/slides.json",
        "size": source_identity["size"],
        "sha256": source_identity["sha256"],
    }
    if existing is not None and existing.get("sha256") != metadata["sha256"]:
        raise ContractError("slides_fingerprint_conflict")
    if existing != metadata:
        supplemental_inputs = dict(supplemental_inputs)
        supplemental_inputs["slides"] = metadata
        index.update(
            expected_revision=snapshot["revision"],
            changes={"supplemental_inputs": supplemental_inputs},
        )
    return target


def _require_prepare_input(run_path: str | Path) -> None:
    index_path = Path(run_path).resolve() / "run.json"
    if index_path.is_file() and _json_file(index_path).get("input_available") is False:
        raise ContractError("input_file_missing")


def _run_input_sources(run_path: str | Path, *, pages: set[int] | None = None) -> list[str]:
    root = Path(run_path).resolve()
    source_root = root / "editable" / "sources"
    if source_root.is_dir():
        values = sorted(
            path for path in source_root.iterdir() if path.is_file() and not path.is_symlink()
        )
    else:
        run = _json_file(root / "run.json")
        values = [root / run["input"]["path"]]
    if pages:
        selected = []
        for number in sorted(pages):
            if number < 1 or number > len(values):
                raise ContractError("selection_out_of_range")
            selected.append(values[number - 1])
        values = selected
    return [str(path) for path in values]


def _normalize_run_sources(
    run_path: str | Path, *, pages: set[int] | None = None
) -> tuple[list[str], bool, dict[int, str]]:
    root = Path(run_path).resolve()
    run = _json_file(root / "run.json")
    requested_pages = pages
    if str(run.get("route", "")).startswith("upgrade-"):
        try:
            baseline = load_baseline(root)
            baseline_pages = baseline["pages"]
            sources = [str(Path(page["artifact"]).resolve()) for page in baseline_pages]
            notes = {
                int(page["number"]): str(page.get("notes", ""))
                for page in baseline_pages
                if isinstance(page.get("number"), int)
            }
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise ContractError("upgrade_baseline_manifest_invalid") from exc
        if not sources or any(not Path(source).is_file() for source in sources):
            raise ContractError("upgrade_baseline_artifact_missing")
        if requested_pages is not None:
            selected = []
            for number in sorted(requested_pages):
                if number < 1 or number > len(sources):
                    raise ContractError("selection_out_of_range")
                selected.append(sources[number - 1])
            sources = selected
        return sources, bool(run["input"].get("office_trusted")), notes
    upstream_run = root / "editable" / "upstream"
    source_pages = sorted(upstream_run.glob("pages/page_*/source.png"))
    if not source_pages:
        source = root / run["input"]["path"]
        arguments = [
            "prepare",
            str(source),
            "--job-dir",
            str(upstream_run),
            "--no-text-hints",
        ]
        if run["input"].get("office_trusted"):
            arguments.append("--office-trusted")
        backend_contract = root / run["backend_contract"]["path"]
        upstream = run_upstream(
            "editable-ppt",
            arguments,
            backend_contract=backend_contract if backend_contract.is_file() else None,
        )
        _persist_execution_receipt(run_path, upstream)
        if upstream["returncode"] != 0:
            raise ContractError("editable_input_normalization_failed")
        try:
            secure_user_tree(upstream_run)
        except ValueError as exc:
            raise ContractError(str(exc)) from exc
        # 上游 prepare 为输入归一化工具，不能把 vendor 的 page_jobs 状态
        # 带入用户 run。归一化完成后只保留不可变的页面源和 notes manifest。
        for vendor_state in (
            upstream_run / "page_jobs.json",
            upstream_run / "deck_run_state.json",
        ):
            try:
                vendor_state.unlink(missing_ok=True)
            except OSError as exc:
                raise ContractError("vendor_state_cleanup_failed") from exc
        source_pages = sorted(upstream_run.glob("pages/page_*/source.png"))
    if not source_pages:
        raise ContractError("normalized_page_sources_missing")
    notes_by_page: dict[int, str] = {}
    notes_manifest = upstream_run / "notes_manifest.json"
    if notes_manifest.is_file():
        try:
            notes_value = _json_file(notes_manifest)
            for entry in notes_value.get("notes", []):
                if isinstance(entry, dict) and isinstance(entry.get("page_index"), int):
                    notes_by_page[entry["page_index"]] = str(entry.get("text", ""))
        except (OSError, ValueError, TypeError):
            raise ContractError("notes_manifest_invalid")
    selected = source_pages
    if pages:
        selected = []
        for number in sorted(pages):
            if number < 1 or number > len(source_pages):
                raise ContractError("selection_out_of_range")
            selected.append(source_pages[number - 1])
    return [str(path) for path in selected], bool(run["input"].get("office_trusted")), notes_by_page


def _upgrade_hybrid_plan(run_path: str | Path) -> dict[str, Any]:
    """读取当前 upgrade-selected 状态，生成不可变 partial 提案指纹。"""
    root = Path(run_path).resolve()
    run = _json_file(root / "run.json")
    if run.get("route") != "upgrade-selected":
        raise ContractError("upgrade_route_required")
    baseline = load_baseline(root)
    image_artifacts = [
        PageArtifact.from_source(
            page["page_id"],
            "image",
            page["artifact"],
            page["artifact"],
            None,
            notes=str(page.get("notes", "")),
            width=int(page["width"]),
            height=int(page["height"]),
        )
        for page in baseline["pages"]
    ]
    editable_by_id = {
        artifact.page_id: artifact
        for artifact in EditableAdapter(_domain_path(root, "editable")).artifacts(
            allow_incomplete=True
        )
    }
    selected = set(run.get("selected_pages", []))
    if not selected:
        raise ContractError("selection_required")
    failures = {
        number: "page_rebuild_failed"
        for number in selected
        if f"page_{number:03d}" not in editable_by_id
    }
    artifacts = [editable_by_id.get(item.page_id, item) for item in image_artifacts]
    baseline_fingerprint = HybridAssembler.baseline_fingerprint(artifacts)
    confirmation = HybridAssembler.failure_fingerprint(
        failures,
        selected_pages=selected,
        baseline_fingerprint=baseline_fingerprint,
    ) if failures else None
    return {
        "selected_pages": sorted(selected),
        "failures": {str(key): value for key, value in failures.items()},
        "artifacts": artifacts,
        "baseline_fingerprint": baseline_fingerprint,
        "confirmation_fingerprint": confirmation,
    }


def _operation_payload(
    *, operation_id: str, idempotency_status: str, safe_to_retry: bool, state_hash: str
) -> dict[str, Any]:
    return {
        "operation_id": operation_id,
        "idempotency_status": idempotency_status,
        "safe_to_retry": safe_to_retry,
        "state_hash": state_hash,
    }


def _record_event(run_path: str | Path, kind: str, **data: Any) -> None:
    root = Path(run_path).resolve()
    if (root / "run.json").is_file():
        RunIndex(root).event(kind, {"actor": "leo-ppt", **data})


def _mark_delivery_completed(run_path: str | Path, *, stage: str) -> None:
    """把 delivery 成功写回唯一 run lifecycle，禁止完成后再 cancel。"""
    root = Path(run_path).resolve()
    if not (root / "run.json").is_file():
        return
    owner = RunIndex(root)
    current = owner.snapshot()
    if current.get("status") == "cancelled":
        raise ContractError("run_cancelled_mutation_forbidden")
    if current.get("status") == "completed" and current.get("stage") == stage:
        return
    owner.update(
        expected_revision=current["revision"],
        changes={"status": "completed", "stage": stage},
    )


def _lease_for_operation(
    run_path: str | Path,
    *,
    unit_id: str,
    actor: str,
    operation_id: str,
    requested_lease: str | None,
    requested_generation: int | None,
) -> tuple[str | None, int | None]:
    """为顶层 run 发行或校验 lease；独立 adapter fixture 不强制此边界。"""
    root = Path(run_path).resolve()
    if not (root / "run.json").is_file():
        return requested_lease, requested_generation
    owner = RunIndex(root)
    operation = owner.snapshot().get("operations", {}).get(operation_id)
    if operation and operation.get("lease"):
        lease = operation["lease"]
        generation = int(operation.get("generation", 0))
    else:
        issued = owner.issue_lease(unit_id, actor=actor, operation_id=operation_id)
        lease = issued["lease"]
        generation = int(issued["generation"])
    if requested_lease is not None and requested_lease != lease:
        raise IdempotencyConflict("lease_invalid")
    if requested_generation is not None and requested_generation != generation:
        raise IdempotencyConflict("generation_conflict")
    if not operation or operation.get("status") != "completed":
        owner.validate_lease(operation_id=operation_id, lease=lease, generation=generation)
    return lease, generation


def _complete_worker_operation(
    run_path: str | Path, operation_id: str, *, artifact_ref: str
) -> None:
    root = Path(run_path).resolve()
    if not (root / "run.json").is_file():
        return
    RunIndex(root).complete_operation(
        operation_id,
        result={"artifact_ref": artifact_ref},
    )


def _persist_execution_receipt(run_path: str | Path, result: dict[str, Any]) -> None:
    """把 backend execution 的非秘密 receipt 绑定到 run identity。"""
    receipt = result.get("execution_receipt")
    root = Path(run_path).resolve()
    if not isinstance(receipt, dict) or not (root / "run.json").is_file():
        return
    receipt_hash = sha256_bytes(canonical_json(receipt).encode("utf-8"))
    owner = RunIndex(root)
    current = owner.snapshot()
    existing = current.get("backend_execution")
    if isinstance(existing, dict) and existing.get("receipt_hash") == receipt_hash:
        return
    owner.update(
        expected_revision=current["revision"],
        changes={
            "backend_execution": {
                "receipt_hash": receipt_hash,
                "receipt": receipt,
            }
        },
    )


def _run_result(
    status: str,
    reason_code: str,
    run: dict[str, Any],
    **payload: Any,
) -> dict[str, Any]:
    artifact_refs = [
        value
        for value in run.get("artifacts", [])
        if isinstance(value, str)
    ]
    delivery_readiness = _delivery_readiness(run)
    if delivery_readiness is not None:
        payload.setdefault("delivery_readiness", delivery_readiness)
        payload.setdefault("evidence_refs", delivery_readiness["evidence_refs"])
    return envelope(
        status,
        reason_code,
        run_id=run["run_id"],
        route=run["route"],
        stage=run["stage"],
        run=run,
        state_hash=_state_hash(run),
        progress=_progress_from_run(run),
        artifact_refs=artifact_refs,
        **payload,
    )


def _delivery_receipt_gate(root: Path) -> dict[str, Any]:
    """DELIVERY-GATE 收据门：收据存在且 verify fresh 才算通过。

    无收据 → not_run（披露，不崩）；stale/invalid → blocked。验证只在
    收据存在时重算指纹，活跃 run 的常规命令只付一次存在性检查的成本。
    """

    receipt_path = root / RECEIPT_RELATIVE_PATH
    try:
        outcome = verify_delivery_receipt(root)
    except (OSError, ReceiptError):
        outcome = {"status": "invalid", "fresh": False}
    status = {"fresh": "passed", "missing": "not_run"}.get(
        outcome["status"], "blocked"
    )
    return {
        "gate": "delivery_receipt",
        "status": status,
        "reason_code": f"delivery_receipt_{outcome['status']}",
        "fresh": bool(outcome.get("fresh")),
        "path": str(receipt_path),
        "impact": outcome.get("impact") if status == "blocked" else None,
    }


def _delivery_readiness(run: dict[str, Any]) -> dict[str, Any] | None:
    output_dir = run.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir:
        return None
    root = Path(output_dir).resolve()
    summary_path = root / "final/validation-summary.json"
    if not summary_path.is_file():
        if run.get("status") != "completed":
            return None
        return {
            "status": "artifact_invalid",
            "reason_code": "delivery_summary_required",
            "artifact_ready": False,
            "missing_gates": [],
            "unverified_gates": [],
            "evidence_refs": [],
        }
    try:
        summary = _json_file(summary_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "status": "artifact_invalid",
            "reason_code": "delivery_summary_invalid",
            "artifact_ready": False,
            "missing_gates": [],
            "unverified_gates": [],
            "evidence_refs": [],
        }
    if not isinstance(summary, dict) or not isinstance(summary.get("quality_gates"), dict):
        return {
            "status": "artifact_invalid",
            "reason_code": "delivery_summary_invalid",
            "artifact_ready": False,
            "missing_gates": [],
            "unverified_gates": [],
            "evidence_refs": [],
        }
    gates = summary["quality_gates"]
    required_acceptance = ("visual_render", "manual_visual_acceptance")
    missing = [
        name
        for name in required_acceptance
        if not isinstance(gates.get(name), dict) or gates[name].get("status") != "passed"
    ]
    unverified = [
        name
        for name, value in gates.items()
        if name not in required_acceptance
        and isinstance(value, dict)
        and value.get("status") not in {"passed", "not_applicable"}
    ]
    evidence_refs = [str(summary_path)]
    for value in gates.values():
        if isinstance(value, dict) and isinstance(value.get("receipt"), str):
            evidence_refs.append(value["receipt"])
    evidence_refs.extend(str(path) for path in sorted((root / "reports").glob("provenance-*.json")))
    receipt_gate = _delivery_receipt_gate(root)
    if receipt_gate["status"] == "not_run":
        missing.append("delivery_receipt")
    elif receipt_gate["status"] != "passed":
        unverified.append("delivery_receipt")
    if receipt_gate["status"] != "passed" and receipt_gate["path"] not in evidence_refs:
        evidence_refs.append(receipt_gate["path"])
    artifact_ready = summary.get("passed") is True
    receipt_blocking = receipt_gate["status"] != "passed"
    status = (
        "artifact_invalid"
        if not artifact_ready
        else ("acceptance_pending" if missing or receipt_blocking else "accepted")
    )
    return {
        "status": status,
        "reason_code": {
            "artifact_invalid": "delivery_structure_not_ready",
            "acceptance_pending": "delivery_acceptance_pending",
            "accepted": "delivery_accepted",
        }[status],
        "artifact_ready": artifact_ready,
        "missing_gates": missing,
        "unverified_gates": unverified,
        "receipt_gate": receipt_gate,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
    }


def _progress_from_run(run: dict[str, Any]) -> dict[str, Any]:
    totals = {"total_units": 0, "completed": 0, "failed": 0, "active": 0, "pending": 0}
    for domain in run.get("domains", {}).values():
        if not isinstance(domain, dict):
            continue
        progress = domain.get("progress")
        if not isinstance(progress, dict):
            continue
        for key in totals:
            value = progress.get(key)
            if isinstance(value, int):
                totals[key] += value
    return {**totals, "estimated_remaining_seconds": None}


def _worker_dispatch_action(page_count: int) -> dict[str, Any]:
    maximum = load_runtime_config().values["max_concurrent_workers"]
    return {
        "kind": "request_worker_dispatch",
        "payload": {
            "dispatch_requirement": "multi_agent_required"
            if page_count > 1
            else "single_unit_current_agent_allowed",
            "page_count": page_count,
            "estimated_duration_per_page_seconds": 180,
            "suggested_max_concurrent": min(maximum, max(page_count, 1)),
            "runtime_fallback": False,
        },
    }


def _status_next_action(run: dict[str, Any]) -> dict[str, Any]:
    progress = _progress_from_run(run)
    if run.get("status") == "completed":
        readiness = _delivery_readiness(run)
        if readiness and readiness["status"] == "acceptance_pending":
            if readiness["missing_gates"] == ["delivery_receipt"]:
                return {
                    "kind": "create_delivery_receipt",
                    "payload": {"gate": "delivery_receipt"},
                }
            return {
                "kind": "record_delivery_evidence",
                "payload": {"missing_gates": readiness["missing_gates"]},
            }
        if readiness and readiness["status"] == "artifact_invalid":
            return {
                "kind": "repair_delivery_artifact",
                "payload": {"reason_code": readiness["reason_code"]},
            }
        return {"kind": "none", "payload": {}}
    if run.get("status") == "cancelled":
        return {"kind": "none", "payload": {}}
    if run.get("status") == "failed" or progress["failed"]:
        return {"kind": "diagnose", "payload": {"failed_units": progress["failed"]}}
    if progress["active"]:
        return {
            "kind": "wait_completion",
            "payload": {"active_units": progress["active"]},
        }
    if progress["pending"]:
        return _worker_dispatch_action(progress["pending"])
    if progress["total_units"] and progress["completed"] == progress["total_units"]:
        kind = "upgrade_finalize" if run["route"].startswith("upgrade-") else "finalize"
        return {"kind": kind, "payload": {}}
    return {"kind": "execute_step", "payload": {"step": route_definition(run["route"]).steps[0]}}


def _protocol_status(run: dict[str, Any]) -> str:
    if run.get("status") in {"completed", "cancelled", "failed"}:
        return str(run["status"])
    progress = _progress_from_run(run)
    if progress["active"] or progress["pending"]:
        return "waiting_for_worker"
    return "ready"


def _next_action(run: dict[str, Any], *, worker_available: bool, page_count: int) -> dict[str, Any]:
    route = route_definition(run["route"])
    stage = run["stage"]
    if stage == "created":
        next_step = route.steps[0]
    else:
        route.require_step(stage)
        position = route.steps.index(stage)
        if position == len(route.steps) - 1:
            return {"kind": "none", "reason_code": "route_complete"}
        next_step = route.steps[position + 1]
    if "dispatch" in next_step and page_count > 1 and not worker_available:
        return {"kind": "blocked", "step": next_step, "reason_code": "worker_capability_unavailable"}
    if "dispatch" in next_step and page_count == 1 and not worker_available:
        return {"kind": "single_unit_current_agent_allowed", "step": next_step, "reason_code": "single_unit_current_agent_allowed"}
    return {"kind": "execute_step", "step": next_step, "reason_code": "step_ready"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leo-ppt")
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor = subcommands.add_parser("doctor")
    doctor.add_argument("--route")
    doctor.add_argument("--json", action="store_true")

    version = subcommands.add_parser("version", help="查看版本与协议版本")
    version.add_argument("--json", action="store_true")
    rollback = subcommands.add_parser("rollback", help="回滚到健康 runtime")
    rollback.add_argument("--identity")
    rollback.add_argument("--json", action="store_true")

    setup = subcommands.add_parser("setup")
    setup.add_argument("--route", required=True)
    setup.add_argument(
        "--host-imagegen",
        choices=("available", "unavailable", "unknown"),
        default="unknown",
    )
    setup.add_argument(
        "--provider",
        choices=BACKEND_PROVIDER_CHOICES,
    )
    setup.add_argument("--require-mask", action="store_true")
    setup.add_argument(
        "--ocr-requirement",
        choices=("not_required", "editable_text_hints"),
        default="not_required",
    )
    setup.add_argument("--json", action="store_true")

    route = subcommands.add_parser("route")
    route.add_argument("--input-kind", required=True)
    route.add_argument("--editable", action="store_true")
    route.add_argument("--upgrade", action="store_true")
    route.add_argument("--pages")

    config = subcommands.add_parser("config")
    config.add_argument("--key-stdin", action="store_true")
    config_commands = config.add_subparsers(dest="config_command")
    config_status = config_commands.add_parser("status")
    config_status.add_argument("--route")
    config_status.add_argument(
        "--host-imagegen",
        choices=("available", "unavailable", "unknown"),
        default="unknown",
    )
    config_status.add_argument("--json", action="store_true")
    config_verify = config_commands.add_parser("verify")
    config_verify.add_argument("--route")
    config_verify.add_argument("--yes", action="store_true")
    config_verify.add_argument("--json", action="store_true")
    config_repair = config_commands.add_parser("repair")
    config_repair.add_argument("--route")
    config_repair.add_argument("--key-stdin", action="store_true")
    config_repair.add_argument("--json", action="store_true")
    config_provider = config_commands.add_parser("provider")
    provider_commands = config_provider.add_subparsers(
        dest="config_provider_command", required=True
    )
    provider_list = provider_commands.add_parser("list")
    provider_list.add_argument("--route")
    provider_list.add_argument("--json", action="store_true")
    provider_configure = provider_commands.add_parser("configure")
    provider_configure.add_argument(
        "--provider",
        choices=EXTERNAL_PROVIDER_CHOICES,
        required=True,
    )
    provider_configure.add_argument("--route")
    provider_configure.add_argument("--key-stdin", action="store_true")
    provider_configure.add_argument("--json", action="store_true")
    provider_prefer = provider_commands.add_parser("prefer")
    provider_prefer.add_argument(
        "--provider",
        choices=EXTERNAL_PROVIDER_CHOICES,
        required=True,
    )
    provider_prefer.add_argument("--route")
    provider_prefer.add_argument("--json", action="store_true")
    provider_auto = provider_commands.add_parser("auto")
    provider_auto.add_argument("--route")
    provider_auto.add_argument("--json", action="store_true")
    provider_reorder = provider_commands.add_parser("reorder")
    provider_reorder.add_argument("--providers", required=True)
    provider_reorder.add_argument("--json", action="store_true")
    provider_enabled = provider_commands.add_parser("enabled")
    provider_enabled.add_argument(
        "--provider",
        choices=EXTERNAL_PROVIDER_CHOICES,
        required=True,
    )
    provider_enabled.add_argument("--value", choices=("true", "false"), required=True)
    provider_enabled.add_argument("--json", action="store_true")
    provider_remove = provider_commands.add_parser("remove")
    provider_remove.add_argument(
        "--provider",
        choices=EXTERNAL_PROVIDER_CHOICES,
        required=True,
    )
    provider_remove.add_argument("--confirm", action="store_true")
    provider_remove.add_argument("--json", action="store_true")

    config_credential = config_commands.add_parser("credential")
    credential_commands = config_credential.add_subparsers(
        dest="config_credential_command", required=True
    )
    credential_status = credential_commands.add_parser("status")
    credential_status.add_argument("--provider")
    credential_status.add_argument("--json", action="store_true")
    credential_set = credential_commands.add_parser("set")
    credential_set.add_argument("--provider", choices=tuple(PROVIDERS), required=True)
    credential_set.add_argument("--overwrite", action="store_true")
    credential_set.add_argument("--key-stdin", action="store_true")
    credential_set.add_argument("--json", action="store_true")
    credential_remove = credential_commands.add_parser("remove")
    credential_remove.add_argument("--provider", choices=tuple(PROVIDERS), required=True)
    credential_remove.add_argument("--confirm", action="store_true")
    credential_remove.add_argument("--json", action="store_true")

    config_reset = config_commands.add_parser("reset")
    config_reset.add_argument("--confirm", action="store_true")
    config_reset.add_argument("--json", action="store_true")

    auth = subcommands.add_parser("auth")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)
    auth_add = auth_commands.add_parser("add")
    auth_add.add_argument("--provider", choices=tuple(PROVIDERS), required=True)
    auth_add.add_argument("--overwrite", action="store_true")
    auth_add.add_argument("--json", action="store_true")
    auth_status = auth_commands.add_parser("status")
    auth_status.add_argument("--provider", choices=tuple(PROVIDERS), required=True)
    auth_status.add_argument("--json", action="store_true")
    auth_remove = auth_commands.add_parser("remove")
    auth_remove.add_argument("--provider", choices=tuple(PROVIDERS), required=True)
    auth_remove.add_argument("--json", action="store_true")

    backend = subcommands.add_parser("backend")
    backend_commands = backend.add_subparsers(dest="backend_command", required=True)
    backend_report = backend_commands.add_parser("report")
    backend_report.add_argument("run_path", nargs="?")
    backend_create = backend_commands.add_parser("create")
    backend_create.add_argument(
        "--provider",
        choices=BACKEND_PROVIDER_CHOICES,
    )
    backend_create.add_argument(
        "--host-imagegen",
        choices=("available", "unavailable", "unknown"),
        default="unknown",
    )
    backend_create.add_argument("--mode", choices=("generate", "edit"), required=True)
    backend_create.add_argument("--model")
    backend_create.add_argument("--output", required=True)
    backend_create.add_argument("--overwrite", action="store_true")
    backend_validate = backend_commands.add_parser("validate")
    backend_validate.add_argument("contract")

    provider = subcommands.add_parser("provider")
    provider_commands = provider.add_subparsers(dest="provider_command", required=True)
    provider_configure = provider_commands.add_parser("configure")
    provider_configure.add_argument("--provider", choices=PROFILE_CONFIGURABLE_PROVIDERS, required=True)
    # openai-compatible 必填；渠道有 checked-in 默认值，可省略。
    provider_configure.add_argument("--base-url", required=False)
    provider_configure.add_argument("--model", required=False)

    run = subcommands.add_parser("run")
    run_commands = run.add_subparsers(dest="run_command", required=True)
    create = run_commands.add_parser("create")
    create.add_argument("--run-dir")
    create.add_argument("--output")
    create.add_argument("--project-root")
    create.add_argument("--route", required=True)
    create.add_argument("--input")
    create.add_argument("--backend-contract")
    create.add_argument("--idempotency-key")
    create.add_argument("--office-trusted", action="store_true")
    create.add_argument("--runtime-identity")
    status = run_commands.add_parser("status")
    status.add_argument("run_path", nargs="?")
    status.add_argument("--run-dir")
    status.add_argument("--json", action="store_true")
    next_step = run_commands.add_parser("next")
    next_step.add_argument("run_path", nargs="?")
    next_step.add_argument("--run-dir")
    next_step.add_argument("--page-count", type=int, required=True)
    next_step.add_argument("--worker-available", action="store_true")
    advance = run_commands.add_parser("advance")
    advance.add_argument("run_path", nargs="?")
    advance.add_argument("--run-dir")
    advance.add_argument("--expected-revision", type=int, required=True)
    advance.add_argument("--stage", required=True)
    diagnose = run_commands.add_parser("diagnose")
    diagnose.add_argument("run_path", nargs="?")
    diagnose.add_argument("--run-dir")
    diagnose.add_argument("--json", action="store_true")
    operation = run_commands.add_parser("operation")
    operation.add_argument("run_path", nargs="?")
    operation.add_argument("--run-dir")
    operation.add_argument("--id", required=True)
    operation.add_argument("--json", action="store_true")
    retry = run_commands.add_parser("retry")
    retry.add_argument("run_path", nargs="?")
    retry.add_argument("--run-dir")
    retry.add_argument("--from-failed-pages", action="store_true")
    cancel = run_commands.add_parser("cancel")
    cancel.add_argument("run_path", nargs="?")
    cancel.add_argument("--run-dir")
    cancel.add_argument("--expected-revision", type=int)
    cancel.add_argument("--wait-workers", action="store_true")
    run_cleanup = run_commands.add_parser("cleanup")
    run_cleanup.add_argument("run_path", nargs="?")
    run_cleanup.add_argument("--run-dir")
    run_cleanup.add_argument("--scope", choices=("temp", "failed-attempts", "input"), required=True)
    run_cleanup_mode = run_cleanup.add_mutually_exclusive_group(required=True)
    run_cleanup_mode.add_argument("--dry-run", action="store_true")
    run_cleanup_mode.add_argument("--apply", nargs="?", const="")
    run_cleanup.add_argument("--expected-revision", type=int)

    image = subcommands.add_parser("image")
    image_commands = image.add_subparsers(dest="image_command", required=True)
    prepare = image_commands.add_parser("prepare")
    prepare.add_argument("run_path", nargs="?")
    prepare.add_argument("--run-dir")
    prepare.add_argument("--slides")
    prepare.add_argument(
        "--sources",
        help="视觉来源清单（content/sources-manifest.json）；冻结进 run input 并入 prepare_fingerprint",
    )
    record = image_commands.add_parser("record")
    record.add_argument("run_path", nargs="?")
    record.add_argument("--run-dir")
    record.add_argument("--number", type=int)
    record.add_argument("--slide")
    record.add_argument("--image")
    record.add_argument("--result")
    record.add_argument("--backend", default="fixture")
    record.add_argument(
        "--page-type", choices=("chart", "text-heavy", "image"),
        help="页型标签（backend×页型路由统计用）",
    )
    record.add_argument("--attempts", type=int, default=1,
                        help="该页到达 accepted 的尝试次数")
    record.add_argument("--tokens", type=int, default=None,
                        help="该页图片 backend 的 token 用量（worker 回报透传，"
                             "缺省 not-recorded）")
    record.add_argument("--lease")
    record.add_argument("--generation", type=int)
    record.add_argument("--agent-id")
    record.add_argument("--expected-revision", type=int)
    record.add_argument("--expected-state-hash")
    record.add_argument("--operation-id")
    record.add_argument("--render-receipt",
                        help="render provenance sidecar（<png>.render.json）路径；"
                             "校验 out_sha256 一致后并入该页 slide entry 的 provenance 字段")
    record.add_argument("--worker-duration-seconds", type=_duration_seconds)
    record.add_argument("--backend-duration-seconds", type=_duration_seconds)
    image_sweep = image_commands.add_parser(
        "sweep", help="E4 全册清扫：非 rendered 页复位计划（--dry-run）/执行")
    image_sweep.add_argument("run_path", nargs="?")
    image_sweep.add_argument("--run-dir")
    image_sweep.add_argument("--max-rounds", type=int, default=2,
                             help="清扫轮次上限（协议 ≤2 轮；超限拒绝执行）")
    image_sweep.add_argument("--dry-run", action="store_true",
                             help="只输出复位计划，不改状态")
    finalize = image_commands.add_parser("finalize")
    finalize.add_argument("run_path", nargs="?")
    finalize.add_argument("--run-dir")
    finalize.add_argument("--output")
    finalize.add_argument("--rebuild", action="store_true")
    image_assemble = image_commands.add_parser("assemble")
    image_assemble.add_argument("run_path", nargs="?")
    image_assemble.add_argument("--run-dir")
    image_assemble.add_argument("--output")
    image_assemble.add_argument("--rebuild", action="store_true")

    render = subcommands.add_parser(
        "render", help="确定性渲染 lane（gamma M1：D 柱，与图像 backend 并列）")
    render_commands = render.add_subparsers(dest="render_command", required=True)
    render_ready_cmd = render_commands.add_parser(
        "ready", help="render backend readiness 三态探测（doctor 分面同源）")
    render_ready_cmd.add_argument("--json", action="store_true")
    render_page_cmd = render_commands.add_parser("page", help="HTML 模板 → PNG 页产物")
    render_page_cmd.add_argument("--template", required=True,
                                 help="assets/render-templates/<id>.html 的模板 id")
    render_page_cmd.add_argument("--data", required=True, help="slide data JSON 路径")
    render_page_cmd.add_argument("--out", required=True, help="PNG 输出路径")
    render_page_cmd.add_argument("--size", default="2560x1440",
                                 help="输出像素档（16:9；缺省 2560x1440 = dsf2）")
    render_page_cmd.add_argument("--timeout", type=float, default=60.0,
                                 help="单页渲染超时（秒）")
    render_page_cmd.add_argument("--theme-file",
                                 help="themeVariables JSON（deck colors 锚，见 render-contract.md）")
    render_chart_cmd = render_commands.add_parser(
        "chart", help="图表语法 → SVG（浏览器实例内 mermaid）")
    render_chart_cmd.add_argument("--dialect", choices=("mermaid",), default="mermaid")
    render_chart_cmd.add_argument("--source",
                                  help="11_图表语法方言 md（抽 ```mermaid-example 块）")
    render_chart_cmd.add_argument("--code-file", help="内联语法文件（全文）")
    render_chart_cmd.add_argument("--out", required=True, help="SVG 输出路径")
    render_chart_cmd.add_argument("--png", help="可选：resvg 栅格化 PNG 输出路径")
    render_chart_cmd.add_argument("--theme-file",
                                  help="themeVariables JSON（缺省 mermaid 默认并 WARN）")
    render_chart_cmd.add_argument("--scale-width", type=int, default=2560,
                                  help="栅格化 fitTo 宽度")

    editable = subcommands.add_parser("editable")
    editable_commands = editable.add_subparsers(dest="editable_command", required=True)
    editable_prepare = editable_commands.add_parser("prepare")
    editable_prepare.add_argument("run_path", nargs="?")
    editable_prepare.add_argument("--run-dir")
    editable_prepare.add_argument("--sources", nargs="+")
    editable_prepare.add_argument("--pages")
    editable_prepare.add_argument("--worker-available", action="store_true")
    editable_prepare.add_argument("--office-trusted", action="store_true")
    editable_next = editable_commands.add_parser("next")
    editable_next.add_argument("run_path", nargs="?")
    editable_next.add_argument("--run-dir")
    editable_next.add_argument("--json", action="store_true")
    editable_dispatch = editable_commands.add_parser("dispatch")
    editable_dispatch.add_argument("run_path", nargs="?")
    editable_dispatch.add_argument("--run-dir")
    editable_dispatch.add_argument("--page", required=True)
    editable_dispatch.add_argument("--agent-id", required=True)
    editable_dispatch.add_argument("--prompt-file", required=True)
    editable_dispatch.add_argument("--lease")
    editable_dispatch.add_argument("--generation", type=int)
    editable_record = editable_commands.add_parser("record")
    editable_record.add_argument("run_path", nargs="?")
    editable_record.add_argument("--run-dir")
    editable_record.add_argument("--page", required=True)
    editable_record.add_argument("--agent-id")
    editable_record.add_argument("--pptx")
    editable_record.add_argument("--validation")
    editable_record.add_argument("--manifest")
    editable_record.add_argument("--expected-revision", type=int)
    editable_record.add_argument("--expected-state-hash")
    editable_record.add_argument("--operation-id")
    editable_record.add_argument("--notes", default="")
    editable_record.add_argument("--backend")
    editable_record.add_argument("--worker-duration-seconds", type=_duration_seconds)
    editable_record.add_argument("--backend-duration-seconds", type=_duration_seconds)
    editable_record.add_argument("--lease")
    editable_record.add_argument("--generation", type=int)
    editable_reset = editable_commands.add_parser("reset")
    editable_reset.add_argument("run_path", nargs="?")
    editable_reset.add_argument("--run-dir")
    editable_reset.add_argument("--page", required=True)
    editable_reset.add_argument("--confirm-lost", action="store_true")
    editable_finalize = editable_commands.add_parser("finalize")
    editable_finalize.add_argument("run_path", nargs="?")
    editable_finalize.add_argument("--run-dir")
    editable_finalize.add_argument("--output")

    upgrade = subcommands.add_parser("upgrade")
    upgrade_commands = upgrade.add_subparsers(dest="upgrade_command", required=True)
    upgrade_inspect = upgrade_commands.add_parser("inspect")
    upgrade_inspect.add_argument("--source-run", required=True)
    upgrade_import = upgrade_commands.add_parser("import-baseline")
    upgrade_import.add_argument("run_path", nargs="?")
    upgrade_import.add_argument("--run-dir")
    upgrade_import.add_argument("--source-run", required=True)
    upgrade_propose = upgrade_commands.add_parser("propose")
    upgrade_propose.add_argument("run_path", nargs="?")
    upgrade_propose.add_argument("--run-dir")
    upgrade_finalize = upgrade_commands.add_parser("finalize")
    upgrade_finalize.add_argument("run_path", nargs="?")
    upgrade_finalize.add_argument("--run-dir")
    upgrade_finalize.add_argument("--output")
    upgrade_finalize.add_argument(
        "--partial-confirmation",
        help="确认当前冻结的失败集合后才允许生成 partial-hybrid",
    )
    # 保留旧参数仅用于给出明确迁移错误，不能绕过两阶段确认。
    upgrade_finalize.add_argument("--allow-partial", action="store_true")

    delivery = subcommands.add_parser("delivery")
    delivery_commands = delivery.add_subparsers(dest="delivery_command", required=True)
    assemble = delivery_commands.add_parser("assemble")
    assemble.add_argument("--artifacts", required=True)
    assemble.add_argument("--output", required=True)
    assemble.add_argument("--selected-pages")
    assemble.add_argument("--failures")
    assemble.add_argument("--partial-confirmation")
    delivery_receipt = delivery_commands.add_parser("receipt")
    delivery_receipt_commands = delivery_receipt.add_subparsers(
        dest="delivery_receipt_command", required=True
    )
    receipt_create = delivery_receipt_commands.add_parser("create")
    receipt_create.add_argument("run_path", nargs="?")
    receipt_create.add_argument("--run-dir")
    receipt_verify = delivery_receipt_commands.add_parser("verify")
    receipt_verify.add_argument("run_path", nargs="?")
    receipt_verify.add_argument("--run-dir")

    style = subcommands.add_parser("style")
    style_commands = style.add_subparsers(dest="style_command", required=True)
    style_list = style_commands.add_parser("list")
    style_list.add_argument("--home")
    style_list.add_argument(
        "--filter",
        help="按名称/别名字符串过滤（大小写不敏感；318 条全量输出前的轻量裁剪）",
    )
    style_load = style_commands.add_parser("load")
    style_load.add_argument("name")
    style_load.add_argument("--home")
    style_render = style_commands.add_parser("render")
    style_render.add_argument("style")
    style_render.add_argument("--home")
    style_render.add_argument("--mode", help="论证模式名（06_论证模式）")
    style_render.add_argument(
        "--brand", help="品牌身份名（10_品牌身份 或 $LEO_PPT_HOME/brands，用户 VI 优先）"
    )
    style_render.add_argument(
        "--anchor", action="store_true",
        help="附加风格锚附录（HEX/字族/渲染逐字节注入每页，防漂移；--brand 隐含开启）",
    )
    style_render.add_argument("--layout", help="版式名（12_版式库，如 P6 / KPI Tower）")
    style_render.add_argument("--image-type", help="信息图类型名（07_信息图类型）")
    style_render.add_argument(
        "--materialize",
        action="store_true",
        help="为图片生成路线附加构图指令块（CSS 骨架翻译为画布区块占比）",
    )
    style_render.add_argument(
        "--color",
        action="append",
        default=None,
        metavar="ROLE=HEX",
        help="deck 级调色板覆盖（可重复，role ∈ primary/secondary/accent/neutral，"
        "值须为 #RRGGBB；同一 role 重复给值时最后一次生效；role 非法、取值非 HEX、"
        "role 不在该风格或风格无 palette 均报 style_color_override_invalid）",
    )
    style_render.add_argument(
        "--var",
        action="append",
        default=None,
        metavar="KEY=VALUE",
        help="token sidecar 变量覆盖（可重复，key 形如 palette.accent / "
             "typography.title / density；palette 值须为 #RRGGBB；覆盖 primary/text "
             "按 4.5:1、accent 按 3:1 相对生效 background 做对比度硬校验（覆盖 "
             "background 时三者全量重查），不足报 style_var_contrast_insufficient；"
             "键不存在/值非法报 style_var_override_invalid；不带 --var 时输出逐字节不变）",
    )
    style_render.add_argument(
        "--guardrail",
        action="store_true",
        help="输出追加确定性设计护栏摘要（缺省输出保持逐字节不变）",
    )
    style_render.add_argument(
        "--layout-lock",
        action="store_true",
        help="输出追加版式系统锁定块（网格 token/安全边距/页码位/圆角线重，"
             "逐页逐字节相同注入防网格页码漂移；从 token_sidecar.layout（优先）"
             "或 brief 顶层 layout 键读取，两者皆无 → layout_lock_unavailable "
             "exit 2 不静默；不带旗标输出逐字节不变）",
    )
    style_render.add_argument("--list-templates", action="store_true")
    style_save = style_commands.add_parser("save")
    style_save.add_argument("name")
    style_save.add_argument("--content-file", required=True)
    style_save.add_argument("--home")
    style_save.add_argument("--overwrite", action="store_true")
    style_save.add_argument("--rename")
    style_layouts = style_commands.add_parser(
        "layouts",
        help="版式库 sidecar 只读查询（layout-bank-v1；输出含每文件 sha256 指纹）",
    )
    style_layouts.add_argument("--style", help="风格名：返回该风格的薄路由视图")
    style_layouts.add_argument("--layout", help="版式 P 码（如 P6）：返回单份版式 sidecar")
    style_layouts.add_argument(
        "--capacity",
        help="容量过滤（只读）：槽名<=N 逗号分隔，如 title<=8,items<=6；"
        "计数槽按 count_max、文本槽按 max_chars 判定，缺键版式如实报 missing",
    )

    evidence = subcommands.add_parser("evidence")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True)
    for name in ("provenance", "visual", "accept"):
        evidence_record = evidence_commands.add_parser(name)
        evidence_record.add_argument("run_path", nargs="?")
        evidence_record.add_argument("--run-dir")
        evidence_record.add_argument("--receipt", required=True)

    cleanup = subcommands.add_parser("cleanup")
    cleanup.add_argument("--run-dir", required=True)
    mode = cleanup.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply")
    cleanup.add_argument("--expected-revision", type=int)

    upstream = subcommands.add_parser("upstream")
    upstream.add_argument("--backend-contract")
    upstream.add_argument("--timeout", type=_duration_seconds)
    upstream.add_argument("capability", choices=("codex-ppt", "editable-ppt"))
    upstream.add_argument(
        "arguments",
        nargs=argparse.REMAINDER,
        help=(
            "固定上游参数。codex-ppt 的第一个参数是工具名："
            + ", ".join(sorted(CODEX_TOOLS))
            + "；editable-ppt 参数与原 editppt 命令树一致。"
        ),
    )
    return parser


def _is_executable_console_script(path: Path, *, platform_name: str) -> bool:
    return path.is_file() and (
        platform_name == "nt" or os.access(path, os.X_OK)
    )


def _resolve_cli_path(*, platform_name: str | None = None) -> str | None:
    """解析当前平台可直接执行的 console script，绝不返回猜测路径。"""

    platform_name = platform_name or os.name
    script_name = "leo-ppt.exe" if platform_name == "nt" else "leo-ppt"
    candidates = (
        os.environ.get("LEO_PPT_CLI_PROG"),
        shutil.which(script_name),
        str(Path(sys.executable).with_name(script_name)),
    )
    for value in candidates:
        if not value:
            continue
        try:
            candidate = Path(value).expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if _is_executable_console_script(candidate, platform_name=platform_name):
            return str(candidate)
    return None


def _module_action_materializer(shell):
    """在无 console script 的模块运行场景中保留可执行恢复命令。"""

    from .config.reason_codes import CommandRenderer

    renderer = CommandRenderer(shell)
    executable = str(Path(sys.executable).resolve())

    def materialize(intent):
        return renderer.render_prefixed(
            intent,
            executable=executable,
            prefix_arguments=("-m", "leo_ppt_generator"),
        )

    return materialize


def _config_service(manager=None) -> ConfigService:
    """从当前 runtime 事实构建统一配置服务。"""

    registry = ProviderRegistry.default()
    home = default_home()
    from .config.runtime_config import ConfigStore
    from .config.reason_codes import ShellKind

    store = ConfigStore(home)
    manager = manager or credential_manager()
    cli_path = _resolve_cli_path()
    shell = ShellKind.POWERSHELL if os.name == "nt" else ShellKind.POSIX

    def credential_reader(provider):
        facts = dict(manager.status(provider.value))
        if facts.get("reference_type") == "environment-reference":
            version = manager.environment_version(provider.value)
            if version is not None:
                facts["credential_version"] = version
        return facts

    return ConfigService(
        store,
        manager.store,
        registry,
        FileReceiptStore(home, registry),
        credential_reader=credential_reader,
        action_materializer=(
            _module_action_materializer(shell) if cli_path is None else None
        ),
        cli_path=cli_path,
        shell=shell,
    )


def _config_wizard(
    provider: str | None = None, *, key_stdin: bool = False
) -> ConfigWizard:
    """构造使用同一 CredentialManager/store 的交互式配置向导。"""

    manager = credential_manager()
    return ConfigWizard(
        _config_service(manager),
        CredentialInputResolver(manager.store, manager.environ),
        input_stream=sys.stdin,
        output_stream=sys.stdout,
        key_stdin=key_stdin,
        fixed_provider=provider,
    )


def _config_provider_list(request: StatusRequest) -> dict[str, Any]:
    service = _config_service()
    overview = service.overview(request)
    return envelope("ready", "provider_listed", **overview.to_dict())


def _update_provider_preference(
    provider: str, *, field: str, value: Any
) -> dict[str, Any]:
    service = _config_service()
    snapshot = service.config_store.read()
    profiles = dict(snapshot.document.get("provider_profiles", {}))
    profile = profiles.get(provider)
    if not isinstance(profile, dict):
        raise ConfigServiceError("provider_profile_invalid")
    updated = dict(profile)
    updated[field] = value
    profiles[provider] = updated
    candidate = dict(snapshot.document)
    candidate["provider_profiles"] = profiles
    service.config_store.compare_and_swap(snapshot.canonical_digest, candidate)
    return envelope(
        "completed",
        "provider_preference_updated",
        provider=provider,
        lifecycle_hint=(
            "影响提示：切换首选 Provider 不影响已完成的交付；"
            "未完成 run 若随后切换图片后端，需要重新确认样张。"
        ),
    )


def _remove_provider_profile(provider: str) -> dict[str, Any]:
    service = _config_service()
    snapshot = service.config_store.read()
    profiles = dict(snapshot.document.get("provider_profiles", {}))
    existed = profiles.pop(provider, None) is not None
    if not existed:
        return envelope("completed", "provider_not_found", provider=provider)
    candidate = dict(snapshot.document)
    candidate["provider_profiles"] = profiles
    if candidate.get("preferred_provider") == provider:
        candidate.pop("preferred_provider", None)
    service.config_store.compare_and_swap(snapshot.canonical_digest, candidate)
    service.receipt_store.invalidate(
        ProviderName(provider), "provider_removed", f"provider-remove-{provider}"
    )
    return envelope(
        "completed",
        "provider_removed",
        provider=provider,
        lifecycle_hint=(
            "影响提示：已移除 Provider 配置；未完成 run 如依赖该 Provider，"
            "将需要新的样张确认。钥匙串中的历史凭据条目未被自动删除。"
        ),
    )


def _dispatch_config_provider(args: argparse.Namespace) -> dict[str, Any]:
    command = args.config_provider_command
    request = StatusRequest(route=getattr(args, "route", None))
    if command == "list":
        return _config_provider_list(request)
    if command == "configure":
        report = _config_wizard(
            args.provider, key_stdin=args.key_stdin
        ).run(request).report
        return envelope(report.status.value, report.reason_code, report=report.to_dict())
    if command == "prefer":
        service = _config_service()
        report = service.set_preferred_provider(
            request,
            provider=args.provider,
            operation_id=f"config-prefer-{args.provider}",
        )
        return envelope(
            report.status.value,
            "provider_preferred",
            provider=args.provider,
            selection={"mode": "fixed"},
            report=report.to_dict(),
        )
    if command == "auto":
        report = _config_service().clear_preferred_provider(
            request,
            operation_id="config-auto",
        )
        return envelope(
            report.status.value,
            "provider_auto_selection_enabled",
            selection={"mode": "automatic"},
            report=report.to_dict(),
        )
    if command == "reorder":
        providers = tuple(
            item.strip() for item in args.providers.split(",") if item.strip()
        )
        _config_service().reorder_provider_priorities(providers)
        return envelope(
            "completed",
            "provider_priority_reordered",
            providers=list(providers),
        )
    if command == "enabled":
        return _update_provider_preference(
            args.provider, field="enabled", value=args.value == "true"
        )
    if not args.confirm:
        raise ConfigServiceError("destructive_confirmation_required")
    return _remove_provider_profile(args.provider)


def _dispatch_config_credential(args: argparse.Namespace) -> dict[str, Any]:
    manager = credential_manager()
    command = args.config_credential_command
    if command == "status":
        providers = (args.provider,) if args.provider else tuple(PROVIDERS)
        return envelope(
            "ready",
            "credential_status_reported",
            credentials=[manager.status(provider) for provider in providers],
        )
    if command == "set":
        if args.key_stdin:
            if manager.store.status(args.provider) == "available" and not args.overwrite:
                raise CredentialError("credential_overwrite_confirmation_required")
            selection = CredentialInputResolver(manager.store, manager.environ).select(
                args.provider,
                key_stdin=True,
                input_stream=sys.stdin,
                tty_stream=None,
                force_new_secret=True,
            )
            try:
                if selection.secret is None:
                    raise CredentialError("credential_input_channel_unavailable")
                # store 的协议签名是 write(secret: str)；显式受让最短生命周期文本副本，
                # 由 selection.close() 负责清零，避免跨通道传递 SecretBuffer 对象。
                manager.store.write(
                    args.provider, selection.secret.reveal_text()
                )
                result = manager.status(args.provider)
            finally:
                selection.close()
        else:
            result = manager.add(args.provider, overwrite=args.overwrite)
        return envelope("completed", str(result["reason_code"]), credential=result)
    if not args.confirm:
        raise ConfigServiceError("destructive_confirmation_required")
    result = manager.remove(args.provider)
    return envelope(
        "completed",
        str(result["reason_code"]),
        credential=result,
        lifecycle_hint=(
            "影响提示：已删除该 Provider 凭据引用；重新配置前相关图片节点将不可用。"
            "已完成交付不受影响。"
        ),
    )


def _dispatch_config(args: argparse.Namespace) -> dict[str, Any]:
    request = StatusRequest(route=getattr(args, "route", None))
    command = args.config_command
    if command is None:
        report = _config_wizard(
            key_stdin=getattr(args, "key_stdin", False)
        ).run(request).report
        return envelope(
            report.status.value,
            report.reason_code,
            report=report.to_dict(),
        )

    if command == "provider":
        return _dispatch_config_provider(args)
    if command == "credential":
        return _dispatch_config_credential(args)
    if command == "reset":
        if not args.confirm:
            raise ConfigServiceError("destructive_confirmation_required")
        service = _config_service()
        try:
            if hasattr(service.config_store, "reset"):
                service.config_store.reset()
            else:
                snapshot = service.config_store.read()
                service.config_store.compare_and_swap(
                    snapshot.canonical_digest,
                    {"schema_version": 2, "provider_profiles": {}},
                )
        except RuntimeConfigError as error:
            # CAS 冲突：不破坏并发写入者的配置，也不伪装成已 reset。
            raise ConfigServiceError(str(error.reason_code)) from error
        for provider in (
            ProviderName.OPENAI,
            ProviderName.OPENAI_COMPATIBLE,
            ProviderName.ATLASCLOUD,
        ):
            service.receipt_store.invalidate(
                provider, "config_reset", "config-reset"
            )
        return envelope(
            "completed",
            "config_reset",
            credentials_preserved=True,
        )

    service = _config_service()
    if command == "status":
        host_capabilities = (
            ("generate",) if args.host_imagegen == "available" else ()
        )
        overview = service.overview(
            request,
            host_capability_state=args.host_imagegen,
            host_capabilities=host_capabilities,
        )
        if (
            overview.selection_error is not None
            and service.config_store.read().values.get("provider_profiles")
        ):
            return envelope(
                "action_required",
                overview.selection_error,
                **overview.to_dict(),
                primary_action=primary_action_for(
                    overview.selection_error,
                    route=str(request.route or "generate"),
                    provider=PROVIDER_EXAMPLES,
                ),
            )
        return envelope(
            overview.report.status.value,
            overview.report.reason_code,
            **overview.to_dict(),
        )
    if command == "verify":
        if not args.yes:
            return envelope(
                "action_required",
                ReasonCode.PAID_VERIFICATION_CONSENT_REQUIRED.value,
                report=service.status(request).to_dict(),
                primary_action={
                    "kind": "run_cli",
                    "command": "config",
                    "verification": "在真实交互终端运行 config 并明确同意付费验证",
                },
            )
        # Provider smoke executor 尚未接入 CLI；显式同意不能被伪装成已验证，
        # 只能返回一个诚实的不可用状态与可执行恢复命令。
        report = service.verify(request)
        return envelope(
            "action_required",
            ReasonCode.PROVIDER_SMOKE_EXECUTOR_UNAVAILABLE.value,
            report=report.to_dict(),
            primary_action={
                "kind": "run_cli",
                "command": "config",
                "verification": "Provider smoke executor 接入后，在真实终端同意重试 config verify",
            },
        )
    if command == "repair":
        report = service.repair(request)
        eligibility = getattr(getattr(report, "execution_eligibility", None), "value", None)
        if eligibility == "blocked":
            report = _config_wizard(
                key_stdin=getattr(args, "key_stdin", False)
            ).run(request).report
        return envelope(
            report.status.value,
            report.reason_code,
            report=report.to_dict(),
        )
    raise ValueError(f"unknown config command: {command}")


def _parse_color_overrides(items: list[str] | None) -> dict[str, str] | None:
    """Turn repeated ``--color ROLE=HEX`` args into an ordered override dict.

    Malformed items (no ``=``) fail with the same StyleColorOverrideError the
    semantic paths use, so the whole override contract has one failure
    surface. Repeated roles: the last occurrence wins (documented CLI help).
    """
    if not items:
        return None
    colors: dict[str, str] = {}
    for item in items:
        role, sep, value = item.partition("=")
        if not sep:
            raise StyleColorOverrideError(
                f"style_color_override_invalid: expected ROLE=HEX, got "
                f"{item!r} (e.g. --color accent=#C0FF00)"
            )
        colors[role.strip()] = value.strip()
    return colors


def _parse_var_overrides(items: list[str] | None) -> dict[str, str] | None:
    """Turn repeated ``--var KEY=VALUE`` args into an ordered override dict.

    Same shape as ``_parse_color_overrides`` but failing with
    StyleVarOverrideError so the whole --var contract has one failure
    surface (semantic validation of key paths/HEX values lives in
    ``templates._merge_token_sidecar``). Repeated keys: last wins.
    """
    if not items:
        return None
    overrides: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep:
            raise StyleVarOverrideError(
                f"style_var_override_invalid: expected KEY=VALUE, got "
                f"{item!r} (e.g. --var palette.accent=#C0FF00)"
            )
        overrides[key.strip()] = value.strip()
    return overrides


def _dispatch_impl(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "version":
        return _version_report()
    if args.command == "rollback":
        return _dispatch_runtime_lifecycle(args)
    if args.command == "config":
        return _dispatch_config(args)
    if args.command == "doctor":
        return doctor_report(args.route)
    if args.command == "setup":
        selected_provider = args.provider
        decision = None
        service = _config_service()
        selection_error = None
        if selected_provider is None and service.config_store.read().values.get("provider_profiles"):
            try:
                decision = service.resolve_provider(
                    StatusRequest(route=args.route),
                    host_capability_state=HostCapabilityState(args.host_imagegen),
                )
                selected_provider = decision.provider.value
            except ConfigServiceError as error:
                selection_error = error.reason_code
        report = build_setup_report(
            args.route,
            host_imagegen=args.host_imagegen,
            selected_provider=selected_provider,
            required_image_capabilities={"mask"} if args.require_mask else set(),
            ocr_requirement=args.ocr_requirement,
        )
        if decision is not None:
            report["selection"] = {
                "source": decision.source,
                "priority": decision.priority,
                "config_digest": decision.config_digest,
            }
        if selection_error is not None:
            report["status"] = "action_required"
            report["reason_code"] = selection_error
            report["selected_provider"] = None
            report["primary_action"] = primary_action_for(
                selection_error,
                route=args.route,
                provider=PROVIDER_EXAMPLES,
            )
        return report
    if args.command == "route":
        selected = select_route(
            args.input_kind,
            editable=args.editable,
            upgrade=args.upgrade,
            selected_pages=_parse_pages(args.pages),
        )
        return envelope("ready", "route_selected", route=selected, next_action={"kind": "create_run"})
    if args.command == "auth":
        manager = credential_manager()
        if args.auth_command == "add":
            return manager.add(args.provider, overwrite=args.overwrite)
        if args.auth_command == "status":
            return manager.status(args.provider)
        return manager.remove(args.provider)
    if args.command == "provider":
        channel = channel_by_name(args.provider)
        if channel is not None:
            # 渠道：端点有 checked-in 默认 origin，base-url/model 均可省略。
            config = configure_provider_profile(
                args.provider,
                endpoint_origin=args.base_url or channel.endpoint_origin,
                model=args.model or channel.default_model,
            )
        else:
            if not args.base_url or not args.model:
                raise BackendContractError("provider_profile_fields_required")
            config = configure_openai_compatible_profile(
                endpoint_origin=args.base_url,
                model=args.model,
            )
        profile = config.values["provider_profiles"][args.provider]
        return envelope(
            "ready",
            "provider_profile_configured",
            provider=args.provider,
            endpoint_origin=profile["endpoint_origin"],
            model=profile["model"],
            next_action={"kind": "configure_credential_reference"},
        )
    if args.command == "backend":
        if getattr(args, "backend_command", "") == "report":
            run_path = _run_path(args)
            return envelope(
                "ready", "backend_report_ready",
                table=_backend_report(run_path), safe_to_retry=True,
            )
        registry = BackendRegistry.default()
        if args.backend_command == "create":
            output = Path(args.output).resolve()
            if output.exists() and not args.overwrite:
                raise BackendContractError("backend_contract_exists")
            provider = args.provider
            selection_source = "user-confirmed"
            selection = None
            if provider is None:
                route = (
                    RouteName.GENERATE
                    if args.mode == "generate"
                    else RouteName.DIRECT_EDITABLE
                )
                decision = _config_service().resolve_provider(
                    StatusRequest(route=route),
                    host_capability_state=HostCapabilityState(args.host_imagegen),
                )
                provider = decision.provider.value
                selection_source = decision.source
                selection = {
                    "source": decision.source,
                    "priority": decision.priority,
                    "config_digest": decision.config_digest,
                }
            credential_source = None
            credential_ref = None
            endpoint_origin = None
            model = args.model
            channel = channel_by_name(provider)
            profiles = load_runtime_config().values.get("provider_profiles", {})
            profile = profiles.get(provider) if selection is not None else None
            if isinstance(profile, dict):
                model = model or profile.get("model")
                credential_source = profile.get("credential_source")
                credential_ref = profile.get("credential_ref")
                endpoint_origin = profile.get("endpoint_origin")
                if channel is not None:
                    model = model or channel.default_model
                    endpoint_origin = endpoint_origin or channel.endpoint_origin
            elif channel is not None:
                # 渠道无 profile 时直接用目录默认值；凭据仍走引用解析。
                model = model or channel.default_model
                endpoint_origin = channel.endpoint_origin
                credential_source, credential_ref = credential_manager().reference(
                    provider
                )
            elif provider == "openai-compatible":
                profile = openai_compatible_profile()
                if profile is None:
                    raise BackendContractError("provider_profile_missing")
                endpoint_origin = profile["endpoint_origin"]
                model = model or profile["model"]
                credential_source = profile["credential_source"]
                credential_ref = profile["credential_ref"]
            elif provider in PROVIDERS:
                credential_source, credential_ref = credential_manager().reference(
                    provider
                )
            contract = registry.create_contract(
                provider,
                mode=args.mode,
                model=model,
                selection_source=selection_source,
                credential_source=credential_source,
                credential_ref=credential_ref,
                endpoint_origin=endpoint_origin,
                selection=selection,
            )
            try:
                atomic_write_json(output, contract)
            except OSError as exc:
                raise BackendContractError("backend_contract_unwritable") from exc
            return envelope(
                "ready",
                "backend_contract_created",
                contract_path=str(output),
                contract=contract,
                next_action={"kind": "create_run"},
            )
        try:
            contract = _json_file(args.contract)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BackendContractError("backend_contract_invalid") from exc
        if not isinstance(contract, dict):
            raise BackendContractError("backend_contract_invalid")
        backend = registry.load(contract)
        credential_source = contract["credential_source"]
        credential_ref = contract.get("credential_ref")
        if credential_source == "environment-reference":
            environment_name = str(credential_ref).removeprefix("env:")
            credential_status = "available" if os.environ.get(environment_name) else "missing"
        elif credential_source == "os-store-reference":
            credential_status = credential_manager().status(backend.name)["status"]
        else:
            credential_status = "host_check_required"
        return envelope(
            "ready",
            "backend_contract_valid",
            contract_path=str(Path(args.contract).resolve()),
            provider=backend.name,
            mode=contract["mode"],
            credential_reference_status=credential_status,
            next_action={
                "kind": "create_run" if credential_status != "missing" else "configure_credential_reference"
            },
        )
    if args.command == "run":
        if args.run_command == "create":
            output = args.output or args.run_dir
            if not output:
                raise ContractError("output_required")
            runtime_identity = _runtime_identity(args.runtime_identity)
            if args.input or args.backend_contract or args.output:
                if not args.input:
                    raise ContractError("input_required")
                if not args.backend_contract:
                    raise ContractError("backend_contract_required")
                creation = RunIndex.create_from_request(
                    output,
                    route=args.route,
                    input_path=args.input,
                    backend_contract_path=args.backend_contract,
                    runtime_identity=runtime_identity,
                    idempotency_key=args.idempotency_key,
                    office_trusted=args.office_trusted,
                    project_root=args.project_root,
                )
                index = creation.index
                run_snapshot = index.snapshot()
                operation_id = args.idempotency_key or f"create-{run_snapshot['run_id']}"
                return _run_result(
                    "ready",
                    "run_created" if creation.idempotency_status == "created" else "run_replayed",
                    run_snapshot,
                    operation_id=operation_id,
                    idempotency_status=creation.idempotency_status,
                    safe_to_retry=True,
                    next_action={"kind": "inspect_next"},
                )
            existed = (Path(output) / "run.json").is_file()
            index = RunIndex.create(output, route=args.route, runtime_identity=runtime_identity)
            run_snapshot = index.snapshot()
            return _run_result(
                "ready",
                "run_created" if not existed else "run_replayed",
                run_snapshot,
                operation_id=f"create-{run_snapshot['run_id']}",
                idempotency_status="replayed" if existed else "created",
                safe_to_retry=True,
                next_action={"kind": "inspect_next"},
            )
        run_path = _run_path(args)
        index = RunIndex(run_path)
        if args.run_command == "status":
            run_snapshot = index.reconcile_from_disk()
            return _run_result(
                _protocol_status(run_snapshot),
                "run_status",
                run_snapshot,
                next_action=_status_next_action(run_snapshot),
            )
        if args.run_command == "next":
            action = _next_action(index.snapshot(), worker_available=args.worker_available, page_count=args.page_count)
            status = "blocked" if action["kind"] == "blocked" else "ready"
            return _run_result(status, action["reason_code"], index.snapshot(), next_action=action)
        if args.run_command == "advance":
            before = index.snapshot()
            route_definition(before["route"]).require_step(args.stage)
            run = index.update(expected_revision=args.expected_revision, changes={"stage": args.stage, "status": "in_progress"})
            index.event(
                "run.stage_advanced",
                {"actor": "leo-ppt", "status": "in_progress", "subject": args.stage},
            )
            return _run_result(
                "ready",
                "stage_advanced",
                run,
                operation_id=f"advance-{before['revision']}-{args.stage}",
                idempotency_status="created",
                safe_to_retry=False,
            )
        if args.run_command == "diagnose":
            run_snapshot = index.reconcile_from_disk()
            return _run_result(
                "ready",
                "diagnosis_complete",
                run_snapshot,
                diagnosis=Lifecycle(run_path).diagnose(),
            )
        if args.run_command == "operation":
            operation = index.operation(args.id)
            return _run_result(
                "ready",
                "operation_status",
                index.snapshot(),
                operation_id=args.id,
                operation=operation,
                safe_to_retry=operation.get("safe_to_retry", False),
            )
        if args.run_command == "retry":
            index.reconcile_from_disk()
            result = index.retry(from_failed_pages=args.from_failed_pages)
            result.pop("run")
            recovery = {"reset_units": []}
            if result["idempotency_status"] == "created" and args.from_failed_pages:
                recovery = Lifecycle(run_path).reset_failed_pages()
                index.reconcile_from_disk()
            index.complete_retry(
                result["operation_id"], from_failed_pages=args.from_failed_pages
            )
            run_snapshot = index.snapshot()
            index.event(
                "run.retry",
                {
                    "actor": "leo-ppt",
                    "status": "ready",
                    "operation_id": result["operation_id"],
                },
            )
            return _run_result(
                "ready",
                "run_retry_ready",
                run_snapshot,
                **result,
                recovery=recovery,
                next_action={"kind": "inspect_next"},
            )
        if args.run_command == "cleanup":
            lifecycle = Lifecycle(run_path)
            current = index.snapshot()
            expected_revision = (
                current["revision"]
                if args.expected_revision is None
                else args.expected_revision
            )
            if args.dry_run:
                preview = lifecycle.cleanup_preview(
                    expected_revision=expected_revision, scope=args.scope
                )
                return _run_result(
                    "ready",
                    "cleanup_preview",
                    current,
                    preview=preview,
                    safe_to_retry=False,
                )
            preview_path = args.apply or str(
                Path(run_path) / f"reports/cleanup-preview-{args.scope}.json"
            )
            receipt = lifecycle.cleanup_apply(_json_file(preview_path))
            index.event(
                "run.cleanup",
                {
                    "actor": "leo-ppt",
                    "status": "completed",
                    "operation_id": f"cleanup-{receipt['fingerprint'][:16]}",
                    "evidence_refs": ["reports/cleanup-receipt.json"],
                },
            )
            return _run_result(
                "completed",
                "cleanup_applied",
                index.snapshot(),
                operation_id=f"cleanup-{receipt['fingerprint'][:16]}",
                idempotency_status="created",
                safe_to_retry=False,
                receipt=receipt,
            )
        if index.snapshot().get("status") == "completed":
            raise IdempotencyConflict("cancel_state_conflict")
        worker_outcome = None
        cancel_workers = None
        if args.wait_workers:
            grace_seconds = float(os.environ.get("LEO_PPT_CANCEL_GRACE_SECONDS", "300"))
            lifecycle = Lifecycle(run_path)
            worker_outcome = lifecycle.wait_for_workers(
                grace_seconds=grace_seconds
            )
            worker_mutation: dict[str, Any] = {}

            def cancel_workers() -> None:
                worker_mutation.update(lifecycle.cancel_worker_units())

        result = index.cancel(
            expected_revision=args.expected_revision,
            before_commit=cancel_workers,
        )
        if worker_outcome is not None:
            worker_outcome.update(worker_mutation)
        run = result.pop("run")
        index.event(
            "run.cancelled",
            {
                "actor": "leo-ppt",
                "status": "cancelled",
                "operation_id": result["operation_id"],
            },
        )
        return _run_result(
            "cancelled",
            "run_cancelled",
            run,
            **result,
            worker_outcome=worker_outcome,
            next_action={"kind": "none"},
        )
    if args.command == "render":
        if args.render_command == "ready":
            report = _render_readiness_report()
            ready = report["status"] == "render_backend_ready"
            return envelope(
                "ready" if ready else "blocked",
                report["status"],
                render=report,
                message=report.get("install_guide")
                or "渲染依赖探测通过，允许路由提议进入 render lane",
                suggested_actions=[]
                if ready
                else [
                    "pip install playwright（或 uv pip install playwright）",
                    'PLAYWRIGHT_BROWSERS_PATH="<LEO_PPT_HOME>/render-browsers" python -m playwright install chromium',
                    "完成后重跑 render ready；期间 render 路由提议被抑制并披露，图像 lane 不受影响",
                ],
            )
        if args.render_command == "page":
            theme = _json_file(args.theme_file) if args.theme_file else None
            result = render_page(
                args.template,
                args.data,
                args.out,
                size=parse_size(args.size),
                timeout_ms=int(args.timeout * 1000),
                theme_variables=theme,
            )
            return envelope(
                "ready",
                "render_page_completed",
                render=result,
                artifact_refs=[result["out"]],
                evidence_refs=[result["sidecar"]],
                warnings=result["warnings"],
                message="render page 完成；record 时用 --render-receipt 并入 provenance",
                safe_to_retry=True,
            )
        # render chart（dialect mermaid）
        if not args.source and not args.code_file:
            raise RenderError("render_data_invalid", "one of --source/--code-file required")
        result = render_chart(
            dialect=args.dialect,
            source=args.source,
            code_file=args.code_file,
            out=args.out,
            theme_file=args.theme_file,
        )
        raster = None
        if args.png:
            raster = rasterize_svg(
                svg_path=args.out, out_path=args.png, width=args.scale_width
            )
        return envelope(
            "ready",
            "render_chart_completed",
            render=result,
            raster=raster,
            artifact_refs=[result["out"], *([raster["out"]] if raster else [])],
            evidence_refs=[result["sidecar"]],
            warnings=result["warnings"],
            message="render chart 完成（SVG 位级确定；数值/单位/标签逐字保真）",
            safe_to_retry=True,
        )
    if args.command == "image":
        run_path = _run_path(args)
        adapter = ImageDeckAdapter(_domain_path(run_path, "image-deck"))
        if args.image_command == "prepare":
            _require_prepare_input(run_path)
            slides_path = args.slides
            if not slides_path:
                candidates = (
                    Path(run_path) / "work/slides.json",
                    Path(run_path) / "input/slides.json",
                )
                slides_path = next((str(path) for path in candidates if path.is_file()), None)
            if not slides_path:
                raise ContractError("slides_required")
            slides_path = str(_freeze_slides_contract(run_path, slides_path))
            slides = _json_file(slides_path)
            if not isinstance(slides, list) or len(slides) > 50:
                raise ContractError("input_too_large")
            sources_manifest = None
            if args.sources:
                sources_root = Path(run_path).resolve()
                sources_spec = Path(args.sources)
                if (sources_root / "run.json").is_file():
                    sources_target = sources_root / "input" / "sources-manifest.json"
                    try:
                        sources_identity = inspect_regular_file(
                            sources_spec, max_bytes=MAX_SLIDES_CONTRACT_BYTES
                        )
                        if sources_target.is_file() or sources_target.is_symlink():
                            frozen_sources = inspect_regular_file(
                                sources_target, max_bytes=MAX_SLIDES_CONTRACT_BYTES
                            )
                            if frozen_sources["sha256"] != sources_identity["sha256"]:
                                raise ContractError("sources_manifest_invalid")
                        else:
                            durable_copy_file(
                                sources_identity["path"],
                                sources_target,
                                max_bytes=MAX_SLIDES_CONTRACT_BYTES,
                            )
                    except ValueError as exc:
                        raise ContractError("sources_manifest_invalid") from exc
                    sources_frozen = sources_target
                else:
                    sources_frozen = sources_spec
                try:
                    sources_manifest = _json_file(sources_frozen)
                except (OSError, ValueError) as exc:
                    raise ContractError("sources_manifest_invalid") from exc
            existed = adapter.jobs_path.is_file()
            result = adapter.prepare(slides, sources_manifest=sources_manifest)
            state_hash = adapter.state_hash()
            _record_event(
                run_path,
                "image.prepared",
                status="ready",
                operation_id=f"image-prepare-{state_hash[:16]}",
            )
            return envelope(
                "ready",
                "image_deck_prepared",
                result=result,
                **_operation_payload(
                    operation_id=f"image-prepare-{state_hash[:16]}",
                    idempotency_status="replayed" if existed else "created",
                    safe_to_retry=True,
                    state_hash=state_hash,
                ),
                next_action=_worker_dispatch_action(len(slides)),
            )
        if args.image_command == "record":
            number = args.number
            if number is None and args.slide:
                try:
                    number = int(args.slide.rsplit("_", 1)[-1])
                except ValueError as exc:
                    raise ContractError("invalid_slide_id") from exc
            if number is None:
                raise ContractError("slide_required")
            image_path = args.result or args.image
            if not image_path:
                raise ContractError("result_required")
            jobs = adapter._jobs()
            expected_revision = (
                jobs["revision"] if args.expected_revision is None else args.expected_revision
            )
            operation_id = args.operation_id or f"image-{number}-{args.agent_id or 'agent'}"
            idempotency_status = (
                "replayed" if operation_id in jobs.get("operations", {}) else "created"
            )
            _append_backend_stats(
                run_path, number=number, backend=args.backend,
                page_type=getattr(args, "page_type", None),
                attempts=getattr(args, "attempts", 1) or 1,
                tokens=getattr(args, "tokens", None),
            )
            lease, generation = _lease_for_operation(
                run_path,
                unit_id=f"slide_{number:02d}",
                actor=args.agent_id or "agent",
                operation_id=operation_id,
                requested_lease=args.lease,
                requested_generation=args.generation,
            )
            artifact = adapter.record(
                number,
                image_path,
                backend=args.backend,
                expected_revision=expected_revision,
                operation_id=operation_id,
                agent_id=args.agent_id,
                expected_state_hash=args.expected_state_hash,
                lease=lease,
                generation=generation,
            )
            provenance_summary = None
            if getattr(args, "render_receipt", None):
                receipt = load_render_receipt(args.render_receipt)
                provenance_summary = attach_provenance_to_slide(
                    adapter.run_dir, number, receipt, backend=args.backend
                )
            _complete_worker_operation(
                run_path,
                operation_id,
                artifact_ref=artifact.artifact_path,
            )
            _record_event(
                run_path,
                "image.recorded",
                status="ready",
                slide_id=f"slide_{number:02d}",
                operation_id=operation_id,
                artifact_ref=artifact.artifact_path,
            )
            return envelope(
                "ready",
                "image_recorded",
                artifact=artifact.to_dict(),
                provenance=provenance_summary,
                **_operation_payload(
                    operation_id=operation_id,
                    idempotency_status=idempotency_status,
                    safe_to_retry=False,
                    state_hash=adapter.state_hash(),
                ),
                lease=lease,
                generation=generation,
            )
        if args.image_command == "sweep":
            deck_dir = _domain_path(run_path, "image-deck")
            jobs_path = deck_dir / "slide_jobs.json"
            if not jobs_path.is_file():
                raise ContractError("image_deck_not_prepared")
            jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
            attempts_by_page: dict[int, Any] = {}
            stats_path = Path(run_path) / "observability" / "backend_stats.jsonl"
            if stats_path.is_file():
                for line in stats_path.read_text(encoding="utf-8").splitlines():
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    slide_no = entry.get("slide")
                    if isinstance(slide_no, int):
                        attempts_by_page[slide_no] = entry.get("attempts", "not-recorded")
            plan = [
                {
                    "slide_id": slide.get("slide_id"),
                    "number": slide.get("number"),
                    "status": slide.get("status"),
                    "attempts": attempts_by_page.get(slide.get("number"), "not-recorded"),
                    "action": "redispatch"
                    if slide.get("status") == "pending"
                    else "reset_and_redispatch",
                }
                for slide in jobs.get("slides", [])
                if slide.get("status") != "recorded"
            ]
            sweep_log = Path(run_path) / "observability" / "render-sweep.jsonl"
            applied_rounds = 0
            if sweep_log.is_file():
                applied_rounds = sum(
                    1 for line in sweep_log.read_text(encoding="utf-8").splitlines() if line.strip()
                )
            if args.dry_run:
                return envelope(
                    "ready",
                    "render_sweep_planned",
                    sweep={
                        "mode": "dry_run",
                        "pages_total": len(jobs.get("slides", [])),
                        "unrendered_pages": len(plan),
                        "plan": plan,
                        "rendered_pages_skipped": len(jobs.get("slides", [])) - len(plan),
                        "rounds_applied": applied_rounds,
                        "max_rounds": args.max_rounds,
                    },
                    safe_to_retry=True,
                )
            if applied_rounds >= args.max_rounds:
                return envelope(
                    "blocked",
                    "render_sweep_rounds_exhausted",
                    sweep={
                        "rounds_applied": applied_rounds,
                        "max_rounds": args.max_rounds,
                        "unrendered_pages": len(plan),
                        "plan": plan,
                    },
                    message="清扫轮次已达协议上限（≤2 轮）；剩余失败页走缺页拒绝组装/"
                    "partial-hybrid 确认或向用户披露，不得无限复位",
                )
            recovery = Lifecycle(run_path).reset_failed_pages()
            entry = {
                "round": applied_rounds + 1,
                "reset_units": recovery.get("reset_units", []),
                "unrendered_pages": len(plan),
            }
            try:
                sweep_log.parent.mkdir(parents=True, exist_ok=True)
                with open(sweep_log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                pass
            return envelope(
                "ready",
                "render_sweep_applied",
                sweep={
                    "mode": "apply",
                    "round": applied_rounds + 1,
                    "max_rounds": args.max_rounds,
                    "plan": plan,
                    "recovery": recovery,
                    "rendered_pages_skipped": len(jobs.get("slides", [])) - len(plan),
                },
                safe_to_retry=False,
                next_action={"kind": "inspect_next"},
            )
        output = _delivery_output_path(run_path, args.output)
        assert_run_quota(Path(run_path).resolve(), load_runtime_config())
        result = adapter.finalize(output, rebuild=args.rebuild)
        _mark_delivery_completed(run_path, stage="image.finalize")
        report_refs = write_delivery_reports(Path(run_path).resolve(), result)
        _record_event(
            run_path,
            "image.assembled",
            status="completed",
            operation_id=f"image-assemble-{adapter.state_hash()[:16]}",
            artifact_ref=result["pptx"],
        )
        result.pop("status", None)
        return envelope(
            "completed",
            "image_delivery_completed",
            artifact_refs=[result["pptx"], *report_refs],
            evidence_refs=report_refs,
            state_hash=adapter.state_hash(),
            safe_to_retry=True,
            operation_id=f"image-assemble-{adapter.state_hash()[:16]}",
            **result,
        )
    if args.command == "editable":
        run_path = _run_path(args)
        adapter = EditableAdapter(_domain_path(run_path, "editable"))
        if args.editable_command == "prepare":
            _require_prepare_input(run_path)
            selected_pages = _parse_pages(args.pages)
            is_top_level_run = (Path(run_path) / "run.json").is_file()
            if args.sources:
                sources = args.sources
                office_trusted = args.office_trusted
                notes_by_page = {}
            elif is_top_level_run:
                sources, office_trusted, notes_by_page = _normalize_run_sources(
                    run_path, pages=selected_pages or None
                )
            else:
                sources = _run_input_sources(run_path, pages=selected_pages or None)
                office_trusted = args.office_trusted
                notes_by_page = {}
            for source in sources:
                classify_input(source, office_trusted=office_trusted)
            limit = 50 if selected_pages else 100
            if len(sources) > limit:
                raise ContractError("input_too_large")
            existed = adapter.jobs_path.is_file()
            result = adapter.prepare(
                sources,
                worker_available=args.worker_available or is_top_level_run,
                page_numbers=sorted(selected_pages) if selected_pages else None,
                notes=notes_by_page,
            )
            run_index_path = Path(run_path) / "run.json"
            if selected_pages and run_index_path.is_file():
                run_index = RunIndex(run_path)
                run_snapshot = run_index.snapshot()
                run_index.update(
                    expected_revision=run_snapshot["revision"],
                    changes={"selected_pages": sorted(selected_pages)},
                )
            _record_event(
                run_path,
                "editable.prepared",
                status=result["status"],
                operation_id=f"editable-prepare-{adapter.state_hash()[:16]}",
            )
            return envelope(
                result["status"],
                result["reason_code"],
                result=result,
                progress=result.get("progress"),
                next_action=result.get("next_action"),
                state_hash=result.get("state_hash", adapter.state_hash()),
                operation_id=f"editable-prepare-{adapter.state_hash()[:16]}",
                idempotency_status="replayed" if existed else "created",
                safe_to_retry=True,
            )
        if args.editable_command == "next":
            result = adapter.status()
            return envelope(
                "ready",
                result["reason_code"],
                next_action=result["next_action"],
                progress=result["progress"],
                state_hash=result["state_hash"],
            )
        if args.editable_command == "dispatch":
            dispatch_operation = f"dispatch-{args.page}-{args.agent_id}"
            lease, generation = _lease_for_operation(
                run_path,
                unit_id=args.page,
                actor=args.agent_id,
                operation_id=dispatch_operation,
                requested_lease=args.lease,
                requested_generation=args.generation,
            )
            result = adapter.dispatch(
                args.page,
                args.agent_id,
                args.prompt_file,
                lease=lease,
                generation=generation,
            )
            _record_event(
                run_path,
                "editable.dispatched",
                status="active",
                page_id=args.page,
                operation_id=dispatch_operation,
            )
            return envelope(
                "ready",
                "editable_dispatch_recorded",
                **_operation_payload(
                    operation_id=f"dispatch-{args.page}-{args.agent_id}",
                    idempotency_status=result["idempotency_status"],
                    safe_to_retry=True,
                    state_hash=result["state_hash"],
                ),
                dispatch=result["page"],
                lease=lease,
                generation=generation,
            )
        if args.editable_command == "reset":
            result = adapter.reset(args.page, confirm_lost=args.confirm_lost)
            _record_event(
                run_path,
                "editable.reset",
                status="pending",
                page_id=args.page,
                operation_id=f"reset-{args.page}-{result['state_hash'][:12]}",
            )
            return envelope(
                "ready",
                "editable_page_reset",
                **_operation_payload(
                    operation_id=f"reset-{args.page}-{result['state_hash'][:12]}",
                    idempotency_status="created",
                    safe_to_retry=False,
                    state_hash=result["state_hash"],
                ),
                page=result["page"],
            )
        if args.editable_command == "finalize":
            output = _delivery_output_path(run_path, args.output)
            assert_run_quota(Path(run_path).resolve(), load_runtime_config())
            result = adapter.finalize(output)
            _mark_delivery_completed(run_path, stage="editable.finalize")
            report_refs = write_delivery_reports(Path(run_path).resolve(), result)
            _record_event(
                run_path,
                "editable.finalized",
                status="completed",
                operation_id=f"editable-finalize-{adapter.state_hash()[:16]}",
                artifact_ref=result["pptx"],
            )
            return envelope(
                "completed",
                "editable_delivery_completed",
                artifact_refs=[result["pptx"], *report_refs],
                evidence_refs=report_refs,
                safe_to_retry=True,
                state_hash=adapter.state_hash(),
                operation_id=f"editable-finalize-{adapter.state_hash()[:16]}",
                **result,
            )
        jobs = adapter._jobs()
        page = next((item for item in jobs["pages"] if item["page_id"] == args.page), None)
        if page is None:
            raise ContractError("unknown_page")
        worker_dir = Path(page.get("worker_dir", "")) if page.get("worker_dir") else None
        pptx = args.pptx or (str(worker_dir / "page.pptx") if worker_dir else None)
        validation = args.validation or (str(worker_dir / "validation.json") if worker_dir else None)
        manifest = args.manifest or (str(worker_dir / "manifest.json") if worker_dir else None)
        if not pptx or not validation or not manifest:
            raise ContractError("editable_result_paths_required")
        expected_revision = jobs["revision"] if args.expected_revision is None else args.expected_revision
        operation_id = args.operation_id or f"editable-{args.page}-{args.agent_id or 'agent'}"
        idempotency_status = (
            "replayed" if operation_id in jobs.get("operations", {}) else "created"
        )
        lease_operation_id = (
            f"dispatch-{args.page}-{args.agent_id}"
            if page.get("lease")
            else operation_id
        )
        lease, generation = _lease_for_operation(
            run_path,
            unit_id=args.page,
            actor=args.agent_id or "agent",
            operation_id=lease_operation_id,
            requested_lease=args.lease,
            requested_generation=args.generation,
        )
        artifact = adapter.record(
            args.page,
            pptx,
            validation,
            manifest,
            expected_revision=expected_revision,
            operation_id=operation_id,
            notes=args.notes,
            agent_id=args.agent_id,
            expected_state_hash=args.expected_state_hash,
            lease=lease,
            generation=generation,
        )
        _complete_worker_operation(
            run_path,
            lease_operation_id,
            artifact_ref=artifact.artifact_path,
        )
        _record_event(
            run_path,
            "editable.recorded",
            status="ready",
            page_id=args.page,
            operation_id=operation_id,
            artifact_ref=artifact.artifact_path,
        )
        return envelope(
            "ready",
            "editable_recorded",
            artifact=artifact.to_dict(),
            **_operation_payload(
                operation_id=lease_operation_id,
                idempotency_status=idempotency_status,
                safe_to_retry=False,
                state_hash=adapter.state_hash(),
            ),
            record_operation_id=operation_id,
            lease=lease,
            generation=generation,
        )
    if args.command == "upgrade":
        if args.upgrade_command == "inspect":
            baseline = inspect_image_delivery(args.source_run)
            return envelope(
                "ready",
                "upgrade_baseline_inspected",
                baseline=baseline,
                state_hash=baseline["baseline_fingerprint"],
                safe_to_retry=True,
            )
        run_path = _run_path(args)
        if args.upgrade_command == "import-baseline":
            baseline = import_baseline(args.source_run, run_path)
            return envelope(
                "ready",
                "upgrade_baseline_imported",
                baseline=baseline,
                state_hash=baseline["baseline_fingerprint"],
                idempotency_status=baseline["idempotency_status"],
                safe_to_retry=True,
            )
        if args.upgrade_command == "propose":
            plan = _upgrade_hybrid_plan(run_path)
            proposal = {
                "schema_version": 1,
                "actor": os.environ.get("USER", "unknown"),
                "proposed_at": utc_now(),
                "run_id": _json_file(Path(run_path) / "run.json").get("run_id"),
                "selected_pages": plan["selected_pages"],
                "failures": plan["failures"],
                "baseline_fingerprint": plan["baseline_fingerprint"],
                "confirmation_fingerprint": plan["confirmation_fingerprint"],
            }
            proposal_path = Path(run_path).resolve() / "reports/partial-proposal.json"
            atomic_write_json(proposal_path, proposal)
            return envelope(
                "ready",
                "partial_hybrid_proposed",
                proposal=proposal,
                evidence_refs=[str(proposal_path)],
                state_hash=plan["confirmation_fingerprint"] or plan["baseline_fingerprint"],
                safe_to_retry=True,
            )
        run = _json_file(Path(run_path) / "run.json")
        if not (Path(run_path) / "image-baseline" / "baseline.json").is_file():
            raise ContractError("upgrade_baseline_required")
        output = _delivery_output_path(run_path, args.output)
        assert_run_quota(Path(run_path).resolve(), load_runtime_config())
        editable_adapter = EditableAdapter(_domain_path(run_path, "editable"))
        if run["route"] == "upgrade-full":
            result = editable_adapter.finalize(output)
        elif run["route"] == "upgrade-selected":
            plan = _upgrade_hybrid_plan(run_path)
            selected = set(plan["selected_pages"])
            failures = {int(key): value for key, value in plan["failures"].items()}
            if failures and not getattr(args, "partial_confirmation", None):
                raise ContractError("partial_hybrid_confirmation_required")
            proposal_path = Path(run_path).resolve() / "reports/partial-proposal.json"
            if failures:
                if not proposal_path.is_file():
                    raise ContractError("partial_hybrid_proposal_required")
                proposal = _json_file(proposal_path)
                if (
                    proposal.get("confirmation_fingerprint") != args.partial_confirmation
                    or proposal.get("baseline_fingerprint") != plan["baseline_fingerprint"]
                    or proposal.get("selected_pages") != plan["selected_pages"]
                    or proposal.get("failures") != plan["failures"]
                ):
                    raise ContractError("partial_hybrid_proposal_stale")
            artifacts = plan["artifacts"]
            baseline_fingerprint = plan["baseline_fingerprint"]
            confirmation = (
                args.partial_confirmation
                if failures
                else None
            )
            result = HybridAssembler().assemble(
                artifacts,
                output,
                selected_pages=selected,
                failures=failures,
                partial_confirmation=confirmation,
            )
            if failures:
                receipt_path = Path(run_path).resolve() / "reports/partial-confirmation.json"
                atomic_write_json(
                    receipt_path,
                    {
                        "schema_version": 1,
                        "actor": os.environ.get("USER", "unknown"),
                        "confirmed_at": utc_now(),
                        "baseline_fingerprint": baseline_fingerprint,
                        "selected_pages": sorted(selected),
                        "failures": {str(key): value for key, value in failures.items()},
                        "confirmation_fingerprint": confirmation,
                    },
                )
        else:
            raise ContractError("upgrade_route_required")
        upgrade_operation_id = (
            f"upgrade-finalize-{sha256_bytes(canonical_json(result).encode())[:16]}"
        )
        report_refs = write_delivery_reports(Path(run_path).resolve(), result)
        partial_receipt = Path(run_path).resolve() / "reports/partial-confirmation.json"
        if partial_receipt.is_file() and str(partial_receipt) not in report_refs:
            report_refs.append(str(partial_receipt))
        _mark_delivery_completed(run_path, stage="hybrid.finalize")
        _record_event(
            run_path,
            "upgrade.finalized",
            status="completed",
            operation_id=upgrade_operation_id,
            artifact_ref=result["pptx"],
        )
        upgrade_payload = {
            **result,
            "idempotency_status": result.get("idempotency_status", "created"),
        }
        return envelope(
            "completed",
            "upgrade_delivery_completed",
            artifact_refs=[result["pptx"], *report_refs],
            evidence_refs=report_refs,
            safe_to_retry=True,
            state_hash=sha256_bytes(canonical_json(result).encode()),
            operation_id=upgrade_operation_id,
            **upgrade_payload,
        )
    if args.command == "style":
        _home_arg = getattr(args, "home", None)
        home = Path(_home_arg).expanduser().resolve() if _home_arg else None
        if args.style_command == "list":
            styles = list_styles(home=home)
            needle = getattr(args, "filter", None)
            if needle:
                needle = str(needle).strip().lower()
                styles = [
                    item for item in styles
                    if needle in str(item.get("name", "")).lower()
                    or any(needle in str(a).lower() for a in item.get("aliases", []) or [])
                ]
            return envelope("ready", "style_listed", styles=styles, safe_to_retry=True)
        if args.style_command == "load":
            result = load_style(args.name, home=home)
            return envelope("ready", "style_loaded", style=result, safe_to_retry=True)
        if args.style_command == "layouts":
            # 只读查询（layout-bank-v1 sidecar）；不触碰 render 组装路径。
            # is not None（非 falsy）守卫：空串条件必须进解析层报
            # capacity_filter_invalid，而不是静默回落全量列表。
            if getattr(args, "capacity", None) is not None:
                if getattr(args, "style", None) or getattr(args, "layout", None):
                    raise CapacityFilterError(
                        "capacity_filter_conflict: --capacity 与 "
                        "--style/--layout 互斥，请只传其一"
                    )
                result = filter_layout_bank_by_capacity(args.capacity)
                return envelope(
                    "ready", "layout_bank_capacity_filtered",
                    capacity_filter=args.capacity,
                    matched=result["matched"],
                    missing=result["missing"],
                    safe_to_retry=True,
                )
            if getattr(args, "layout", None):
                return envelope(
                    "ready", "layout_bank_loaded",
                    layout=load_layout_bank(args.layout), safe_to_retry=True,
                )
            if getattr(args, "style", None):
                return envelope(
                    "ready", "style_layouts_loaded",
                    style_layouts=load_style_layouts(args.style),
                    safe_to_retry=True,
                )
            return envelope(
                "ready", "layout_bank_listed",
                layouts=list_layout_bank(), safe_to_retry=True,
            )
        if args.style_command == "render":
            if getattr(args, "list_templates", False):
                return envelope(
                    "ready", "templates_listed",
                    templates=list_templates(), safe_to_retry=True,
                )
            result = compose_style(
                args.style,
                mode=args.mode,
                colors=_parse_color_overrides(getattr(args, "color", None)),
                var_overrides=_parse_var_overrides(getattr(args, "var", None)),
                brand=getattr(args, "brand", None),
                anchor=bool(getattr(args, "anchor", False)),
                guardrail=bool(getattr(args, "guardrail", False)),
                layout_lock=bool(getattr(args, "layout_lock", False)),
            )
            if args.layout:
                result["layout"] = compose_layout(
                    args.layout,
                    image_type=args.image_type,
                    materialize=bool(getattr(args, "materialize", False)),
                )
            return envelope(
                "ready", "style_rendered", template=result, safe_to_retry=True,
            )
        try:
            content = Path(args.content_file).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise StyleStoreError("style_content_unreadable") from exc
        result = save_style(
            args.name,
            content,
            home=home,
            overwrite=args.overwrite,
            rename=args.rename,
        )
        return envelope("completed", "style_saved", style=result, safe_to_retry=False)
    if args.command == "evidence":
        run_path = _run_path(args)
        if args.evidence_command == "provenance":
            result = record_provenance(run_path, args.receipt)
            reason_code = "provenance_recorded"
        elif args.evidence_command == "visual":
            result = record_visual(run_path, args.receipt)
            reason_code = "visual_evidence_recorded"
        else:
            result = record_acceptance(run_path, args.receipt)
            reason_code = "manual_acceptance_recorded"
        return envelope(
            "completed",
            reason_code,
            evidence_refs=[result["path"]],
            receipt=result,
            idempotency_status=result["idempotency_status"],
            safe_to_retry=True,
        )
    if args.command == "delivery":
        if args.delivery_command == "receipt":
            run_path = _run_path(args)
            if args.delivery_receipt_command == "create":
                created = create_delivery_receipt(run_path)
                return envelope(
                    "completed",
                    "delivery_receipt_created",
                    artifact_refs=[created["path"]],
                    evidence_refs=[created["path"]],
                    receipt=created["receipt"],
                    counts=created["counts"],
                    safe_to_retry=True,
                )
            outcome = verify_delivery_receipt(run_path)
            status = "completed" if outcome["status"] == "fresh" else "blocked"
            evidence = (
                [outcome["receipt_path"]] if outcome["status"] != "missing" else []
            )
            return envelope(
                status,
                f"delivery_receipt_{outcome['status']}",
                delivery_receipt=outcome,
                evidence_refs=evidence,
                safe_to_retry=True,
            )
        artifacts = [PageArtifact.from_dict(value) for value in _json_file(args.artifacts)]
        failures = {int(key): value for key, value in (_json_file(args.failures) if args.failures else {}).items()}
        result = HybridAssembler().assemble(
            artifacts,
            args.output,
            selected_pages=_parse_pages(args.selected_pages) or None,
            failures=failures,
            partial_confirmation=args.partial_confirmation,
        )
        operation_id = f"delivery-{sha256_bytes(canonical_json(result).encode())[:16]}"
        delivery_payload = {**result, "idempotency_status": result.get("idempotency_status", "created")}
        return envelope(
            "completed",
            "delivery_completed",
            operation_id=operation_id,
            safe_to_retry=True,
            state_hash=sha256_bytes(canonical_json(result).encode()),
            **delivery_payload,
        )
    if args.command == "upstream":
        result = run_upstream(
            args.capability,
            args.arguments,
            backend_contract=args.backend_contract,
            timeout_seconds=args.timeout,
        )
        status = "completed" if result["returncode"] == 0 else "blocked"
        reason = (
            "upstream_tool_completed"
            if result["returncode"] == 0
            else ("upstream_subprocess_timeout" if result.get("timed_out") else "upstream_tool_failed")
        )
        return envelope(status, reason, result=result)
    lifecycle = Lifecycle(args.run_dir)
    if args.dry_run:
        if args.expected_revision is None:
            raise CleanupConflict("cleanup_revision_required")
        preview = lifecycle.cleanup_preview(expected_revision=args.expected_revision)
        return envelope("ready", "cleanup_preview", preview=preview)
    return envelope("completed", "cleanup_applied", receipt=lifecycle.cleanup_apply(_json_file(args.apply)))


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    run_dir = resolve_run_dir(args)
    name = command_name(args)
    try:
        result = _dispatch_impl(args)
    except Exception as error:
        record_command(
            run_dir,
            command=name,
            started_at=started_at,
            duration_seconds=time.monotonic() - started,
            status="blocked",
            reason_code=str(error) or getattr(error, "reason_code", "unhandled_error"),
        )
        raise
    is_created = result.get("idempotency_status") != "replayed"
    unit_id = getattr(args, "page", None) or getattr(args, "slide", None)
    worker_duration = getattr(args, "worker_duration_seconds", None)
    backend_duration = getattr(args, "backend_duration_seconds", None)
    backend_name = getattr(args, "backend", None)
    page_measurement = None
    backend_measurement = None
    if is_created and unit_id and worker_duration is not None:
        page_measurement = {
            "unit_id": unit_id,
            "command": name,
            "duration_seconds": worker_duration,
            "status": result.get("status", "unknown"),
        }
    if is_created and unit_id and backend_duration is not None:
        backend_measurement = {
            "unit_id": unit_id,
            "backend": backend_name or "not_recorded",
            "duration_seconds": backend_duration,
            "status": result.get("status", "unknown"),
        }
    record_command(
        run_dir,
        command=name,
        started_at=started_at,
        duration_seconds=time.monotonic() - started,
        status=result.get("status", "unknown"),
        reason_code=result.get("reason_code", "unknown"),
        page_measurement=page_measurement,
        backend_measurement=backend_measurement,
    )
    return result


ERRORS = (
    BackendExecutionError,
    EvidenceError,
    BackendContractError,
    RuntimeConfigError,
    ConfigServiceError,
    CleanupConflict,
    ContractError,
    ReceiptError,
    IdempotencyConflict,
    RevisionConflict,
    RouteContractError,
    StyleStoreError,
    TemplateError,
    UpstreamBridgeError,
    SetupContractError,
    CredentialError,
    WizardCancelled,
)




def _append_backend_stats(run_path, *, number, backend, page_type, attempts,
                          tokens=None):
    """Append one (backend, page_type, attempts) line for routing reports.

    Sidecar jsonl under the run dir — deliberately outside slide_jobs.json so
    the canonical state hash is unaffected; unwritable path is non-fatal
    (statistics must never block a record).
    """
    import json as _json
    from datetime import datetime, timezone

    try:
        stats_dir = Path(run_path) / "observability"
        stats_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "slide": number,
            "backend": backend,
            "page_type": page_type or "unlabeled",
            "attempts": attempts,
            "tokens": tokens if tokens is not None else "not-recorded",
        }
        with open(stats_dir / "backend_stats.jsonl", "a", encoding="utf-8") as fh:
            fh.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _backend_report(run_path):
    """Aggregate backend_stats.jsonl into a (backend, page_type) pass-rate table."""
    import json as _json
    from collections import defaultdict

    path = Path(run_path) / "observability" / "backend_stats.jsonl"
    agg = defaultdict(lambda: {"pages": 0, "attempts": 0, "tokens": 0})
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                e = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            key = (e.get("backend", "unknown"), e.get("page_type", "unlabeled"))
            agg[key]["pages"] += 1
            agg[key]["attempts"] += max(1, int(e.get("attempts", 1)))
            tk = e.get("tokens")
            if isinstance(tk, int):
                agg[key]["tokens"] += tk
    table = {}
    for (backend, page_type), v in sorted(agg.items()):
        first_pass = v["pages"] / v["attempts"] if v["attempts"] else 1.0
        table[f"{backend}/{page_type}"] = {
            "pages": v["pages"],
            "first_pass_rate": round(first_pass, 3),
            "tokens_total": v["tokens"] or "not-recorded",
        }
    return table

def main(argv: list[str] | None = None) -> int:
    if argv is None:
        invoked = Path(sys.argv[0]).expanduser()
        if invoked.is_absolute():
            resolved = invoked.resolve()
            if resolved.is_file() and os.access(resolved, os.X_OK):
                os.environ["LEO_PPT_CLI_PROG"] = str(resolved)
    args = build_parser().parse_args(argv)
    try:
        result = dispatch(args)
        # R8/R15：生命周期提示走 stderr 人类通道；任何模式都不进入 JSON 序列化体。
        lifecycle_hint = None
        if isinstance(result, dict):
            lifecycle_hint = result.pop("lifecycle_hint", None)
        if lifecycle_hint:
            print(lifecycle_hint, file=sys.stderr)
        if args.command == "version" and not args.json:
            print(f"leo-ppt {result['package_version']}")
            print(f"runtime {result['runtime_version']}")
            print(f"install channel {result['install_channel']}")
            print(f"config schema v{result['config_schema_version']}")
            print(f"setup schema v{result['setup_schema_version']}")
        elif args.command == "setup" and not args.json:
            print(render_setup_report(result))
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2 if result["status"] in {"blocked", "action_required", "choice_required"} else 0
    except ERRORS as error:
        # Prefer the class-level stable reason code (e.g.
        # style_color_override_invalid); str(error) carries the per-input
        # detail and must not become the reason_code consumers match on.
        reason = getattr(error, "reason_code", None) or str(error) or "contract_error"
        print(json.dumps(envelope("blocked", reason, next_action={"kind": "inspect_reason_code"}), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
