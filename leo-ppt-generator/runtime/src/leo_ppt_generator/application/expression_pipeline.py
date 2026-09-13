"""表达优先生产编排的薄入口；不拥有内容、排名或模板真值。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import hashlib
import json
from pathlib import Path
import os

from ..layout_selection import allocate_deck


class ExpressionPipelineError(ValueError):
    pass


def selection_digest(selection: dict[str, Any]) -> str:
    """对选型身份做稳定摘要；不包含时间、绝对路径或展示文案。"""
    payload = {pid: {"layout_id": entry.get("layout_id"),
                     "binding_digest": entry.get("binding_digest"),
                     "expression_binding_digest": entry.get("expression_binding_digest"),
                     "materialization_binding_digest": entry.get("materialization_binding_digest")}
               for pid, entry in sorted((selection or {}).items())}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class PipelineRequest:
    pack: dict[str, Any]
    design_context: dict[str, Any]
    backend: str = "render:html"
    run_id: str = ""
    policy_revision: str = "expression-policy-v1"


def verify_selection_frozen(result: dict[str, Any]) -> None:
    """compose 前的冻结门：摘要缺失或漂移时拒绝继续。"""
    if not result.get("selection_frozen") or result.get("selection_digest") != selection_digest(result.get("selection")):
        raise ExpressionPipelineError("selection_frozen_mismatch")


def run_expression_pipeline(request: PipelineRequest, *, resolver=None, proposal: dict[str, Any] | None = None) -> dict[str, Any]:
    """固定 pack → qualified candidates → allocate 顺序，返回冻结前 selection。"""
    if not isinstance(request, PipelineRequest) or not request.pack.get("pages"):
        raise ExpressionPipelineError("expression_incomplete")
    if not isinstance(request.design_context, dict):
        raise ExpressionPipelineError("design_context_missing")
    if proposal is not None:
        from ..task_local_layout_proposals import ProposalError, validate_task_local_proposal
        try:
            validate_task_local_proposal(proposal, run_scope=request.design_context.get("run_scope", "default"),
                                         allowed_assets=set(request.design_context.get("allowed_assets", [])))
        except ProposalError as exc:
            raise ExpressionPipelineError(str(exc)) from exc
    result = allocate_deck(request.pack, request.design_context,
                           backend=request.backend, resolver=resolver)
    if not result.get("selection") or set(result["selection"]) != {
        page["page_id"] for page in request.pack["pages"]
    }:
        raise ExpressionPipelineError("selection_incomplete")
    result["selection_digest"] = selection_digest(result["selection"])
    result["selection_frozen"] = True
    result["pipeline"] = {"schema_version": 1, "run_id": request.run_id or "in-memory",
                          "input_digest": hashlib.sha256(json.dumps(request.pack, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                          "catalog_generation": getattr(resolver, "generation", "unknown"),
                          "policy_revision": request.policy_revision,
                          "materialization": request.backend}
    return result


def write_atomic_input_generation(run_root: Path, payload: dict[str, Any], *, generation: str) -> Path:
    """Persist frozen pipeline inputs through staging and an atomic current pointer."""
    root = Path(run_root).resolve(); staging = root / "input" / ".staging" / generation
    staging.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    target = staging / "generation.json"
    target.write_text(body, encoding="utf-8")
    fd = os.open(target, os.O_RDONLY); os.fsync(fd); os.close(fd)
    immutable = root / "input" / "generations" / generation
    immutable.parent.mkdir(parents=True, exist_ok=True)
    if immutable.exists():
        if (immutable / "generation.json").read_text(encoding="utf-8") != body:
            raise ExpressionPipelineError("input_generation_conflict")
    else:
        os.replace(staging, immutable)
    pointer = root / "input" / "current.json"
    tmp = pointer.with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema_version": 1, "generation": generation}, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, pointer)
    return immutable
