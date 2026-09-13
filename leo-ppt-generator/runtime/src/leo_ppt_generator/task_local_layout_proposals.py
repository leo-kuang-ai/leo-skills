"""Run-scoped layout proposal validation; proposals never mutate canonical assets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ProposalError(ValueError):
    pass


ALLOWED_OPS = frozenset({"set_region_assignment", "set_anchor_gap", "set_span", "set_slot_mapping"})


def proposal_digest(proposal: dict) -> str:
    payload = {k: proposal[k] for k in sorted(proposal) if k != "proposal_digest"}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_task_local_proposal(proposal: dict, *, run_scope: str, allowed_assets: set[str], resolver_root: Path | None = None) -> None:
    try:
        if "candidates" not in proposal:
            # Legacy in-memory callers are validated by the semantic checks below;
            # persisted v1 proposals must use the closed candidates contract.
            pass
        else:
            from jsonschema import Draft202012Validator
            schema = json.loads((Path(__file__).parent / "schemas" / "task-local-layout-proposal-v1.schema.json").read_text())
            errors = list(Draft202012Validator(schema).iter_errors(proposal))
            if errors:
                raise ProposalError("proposal_schema_invalid: " + errors[0].message)
    except ProposalError:
        raise
    except Exception as exc:
        raise ProposalError("proposal_schema_unavailable") from exc
    if not isinstance(proposal, dict) or proposal.get("run_scope") != run_scope:
        raise ProposalError("proposal_run_scope_mismatch")
    if proposal.get("proposal_digest") != proposal_digest(proposal):
        raise ProposalError("proposal_digest_mismatch")
    if proposal.get("base_asset") not in allowed_assets:
        raise ProposalError("proposal_asset_not_allowed")
    candidates = proposal.get("candidates") if "candidates" in proposal else [proposal]
    if not isinstance(candidates, list) or len(candidates) > 3:
        raise ProposalError("proposal_candidate_limit")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ProposalError("proposal_candidate_invalid")
        for op in candidate.get("ops", candidate.get("patch", [])):
            allowed_ops = ALLOWED_OPS if "candidates" in proposal else ALLOWED_OPS | {"set_slot", "set_region", "set_recipe"}
            if not isinstance(op, dict) or op.get("op") not in allowed_ops:
                raise ProposalError("proposal_op_not_allowed")
            if "fact_refs" in op or op.get("delete_facts") or op.get("remove_content"):
                raise ProposalError("proposal_cannot_delete_facts")
            if op.get("lane") not in (None, "image", "render:html"):
                raise ProposalError("proposal_lane_unsupported")
            if "candidates" in proposal and not op.get("target"):
                raise ProposalError("proposal_anchor_missing")
            if "value" in op and isinstance(op["value"], (int, float)) and not (-10000 <= op["value"] <= 10000):
                raise ProposalError("proposal_value_out_of_range")
            if resolver_root is not None and "path" in op:
                path = (resolver_root / str(op["path"])).resolve()
                if resolver_root.resolve() not in path.parents and path != resolver_root.resolve():
                    raise ProposalError("proposal_path_outside_root")
