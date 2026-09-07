"""样张决策的可追溯声明与实际输入绑定；不代表人工身份认证或最终验收。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from filelock import FileLock
from PIL import Image

from ..contracts import ContractError
from ..storage import atomic_write_bytes, atomic_write_json, canonical_json, sha256_bytes, sha256_file


RECEIPT_PATH = Path("reports/sample-decision.json")
REQUIRED_PATH = Path("reports/sample-decision-required.json")


def _error(reason: str) -> ContractError:
    error = ContractError(reason)
    error.reason_code = reason
    return error


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise _error("sample_decision_invalid") from exc


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _file(path: str | Path) -> dict[str, str]:
    target = Path(path).expanduser().resolve()
    try:
        return {"path": str(target), "sha256": sha256_file(target)}
    except OSError as exc:
        raise _error("sample_decision_input_missing") from exc


def _binding(root: Path, sample: Path, slides: Path, binding: Path) -> dict[str, Any]:
    value = _json(binding)
    required = {"backend", "width", "height", "generation_method", "style_visual_path", "layout_binding_path"}
    if not isinstance(value, dict) or set(value) != required:
        raise _error("sample_binding_invalid")
    for name in ("backend", "generation_method", "style_visual_path"):
        if not isinstance(value[name], str) or not value[name].strip():
            raise _error("sample_binding_invalid")
    if any(type(value[name]) is not int or value[name] <= 0 for name in ("width", "height")):
        raise _error("sample_binding_invalid")
    if value["width"] * 9 != value["height"] * 16:
        raise _error("sample_dimensions_mismatch")
    if value["layout_binding_path"] is not None and (
        not isinstance(value["layout_binding_path"], str) or not value["layout_binding_path"].strip()
    ):
        raise _error("sample_binding_invalid")
    run = _json(root / "run.json")
    try:
        backend_path = (root / run["backend_contract"]["path"]).resolve()
        backend_path.relative_to(root)
        backend = _json(backend_path)
        # render-lane deck（WS5/D-OBS-01）：样张实际由 render:html 产出，
        # binding.backend 允许页级渲染 backend 而非强制图像渠道名。
        allowed_backends = {backend["provider"]}
        if backend["provider"] == "render-lane":
            allowed_backends.update({"render:html", "render:mermaid"})
        if value["backend"] not in allowed_backends:
            raise _error("sample_backend_mismatch")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise _error("sample_backend_contract_required") from exc
    try:
        with Image.open(sample) as image:
            if image.size != (value["width"], value["height"]):
                raise _error("sample_dimensions_mismatch")
            image.verify()
    except (OSError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise _error("sample_image_invalid") from exc
    content = _json(slides)
    if not isinstance(content, list) or not content:
        raise _error("sample_slides_invalid")
    def asset(raw: str) -> dict[str, str]:
        path = Path(raw).expanduser()
        return _file(path if path.is_absolute() else binding.parent / path)
    return {
        "sample": _file(sample),
        "slides_sha256": _digest(content),
        "style_visual": asset(value["style_visual_path"]),
        "layout_binding": asset(value["layout_binding_path"]) if value["layout_binding_path"] else None,
        "backend": value["backend"],
        "backend_contract_sha256": _digest(backend),
        "width": value["width"],
        "height": value["height"],
        "generation_method": value["generation_method"],
    }


def _decision(source: str, authorization_ref: Path, quote: str) -> dict[str, str]:
    if not isinstance(source, str) or source not in {"user-confirmed", "user-delegated"} or not isinstance(quote, str) or not quote.strip():
        raise _error("sample_decision_source_invalid")
    try:
        if quote not in authorization_ref.read_text(encoding="utf-8"):
            raise _error("sample_authorization_quote_missing")
    except (OSError, UnicodeError) as exc:
        raise _error("sample_authorization_required") from exc
    return {"source": source, "authorization_ref": str(authorization_ref.resolve()), "quote": quote}


def record_sample_decision(
    run_root: str | Path, *, sample: str | Path, slides: str | Path,
    binding: str | Path, decision_source: str, authorization_ref: str | Path,
    authorization_quote: str, supersedes: str | None = None,
) -> dict[str, Any]:
    root = Path(run_root).resolve()
    if not (root / "run.json").is_file():
        raise _error("sample_run_required")
    decision = _decision(decision_source, Path(authorization_ref).resolve(), authorization_quote)
    payload = {
        "schema_version": 1,
        "kind": "sample_decision",
        "run_root": str(root),
        "inputs": {"slides": str(Path(slides).resolve()), "binding": str(Path(binding).resolve())},
        "binding": _binding(root, Path(sample).resolve(), Path(slides).resolve(), Path(binding).resolve()),
        "decision": decision,
    }
    payload["contents_sha256"] = _digest(payload)
    target = root / RECEIPT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(root / ".sample-decision.lock")):
        atomic_write_json(root / REQUIRED_PATH, {"schema_version": 1, "required": True})
        if target.exists():
            previous_bytes = target.read_bytes()
            previous_digest = sha256_bytes(previous_bytes)
            try:
                existing = _json(target)
            except ContractError:
                if supersedes != previous_digest:
                    raise
                existing = None
            if existing == payload:
                return {"status": "verified", "path": str(target), "receipt_sha256": sha256_file(target), "idempotency_status": "replayed", "decision_source": decision_source}
            if supersedes != previous_digest:
                raise _error("sample_decision_conflict")
            atomic_write_bytes(root / "reports/sample-decisions" / f"{previous_digest}.json", previous_bytes)
        atomic_write_json(target, payload)
        receipt_digest = sha256_file(target)
    return {"status": "verified", "path": str(target), "receipt_sha256": receipt_digest, "idempotency_status": "created", "decision_source": decision_source}


def verify_sample_decision(
    run_root: str | Path, *, slides: str | Path | None = None,
    binding: str | Path | None = None, allow_legacy: bool = False,
) -> dict[str, Any]:
    root = Path(run_root).resolve()
    target = root / RECEIPT_PATH
    if not target.exists():
        if allow_legacy and binding is None and not (root / REQUIRED_PATH).exists():
            return {"status": "not_run", "mode": "legacy", "reason_code": "sample_decision_not_recorded"}
        raise _error("sample_decision_required")
    try:
        receipt_bytes = target.read_bytes()
        value = json.loads(receipt_bytes)
    except (OSError, ValueError) as exc:
        raise _error("sample_decision_invalid") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("kind") != "sample_decision":
        raise _error("sample_decision_invalid")
    if value.get("run_root") != str(root) or value.get("contents_sha256") != _digest({k: v for k, v in value.items() if k != "contents_sha256"}):
        raise _error("sample_decision_invalid")
    try:
        decision = value["decision"]
        _decision(decision["source"], Path(decision["authorization_ref"]), decision["quote"])
        current = _binding(
            root, Path(value["binding"]["sample"]["path"]),
            Path(slides).resolve() if slides is not None else Path(value["inputs"]["slides"]),
            Path(binding).resolve() if binding is not None else Path(value["inputs"]["binding"]),
        )
    except (KeyError, TypeError) as exc:
        raise _error("sample_decision_invalid") from exc
    if current != value["binding"]:
        raise _error("sample_decision_stale")
    receipt_digest = sha256_bytes(receipt_bytes)
    if not target.is_file() or sha256_file(target) != receipt_digest:
        raise _error("sample_decision_conflict")
    return {"status": "verified", "path": str(target), "receipt_sha256": receipt_digest, "decision_source": decision["source"], "binding_sha256": _digest(current)}
