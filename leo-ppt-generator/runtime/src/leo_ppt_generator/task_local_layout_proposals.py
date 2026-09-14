"""受约束的任务内 geometry/slot 提案；不修改 canonical、正文、主题或用户范围。"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .storage import canonical_json_bytes


class ProposalError(ValueError):
    pass


ALLOWED_OPS = ("set_region_assignment", "set_anchor_gap", "set_span", "set_slot_mapping")


def _digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonical_ops(ops):
    return sorted(ops, key=lambda op: (ALLOWED_OPS.index(op["op"]), op["target"], canonical_json_bytes(op)))


def proposal_digest(proposal):
    body = deepcopy({key: value for key, value in proposal.items() if key != "proposal_digest"})
    for candidate in body.get("candidates", []):
        candidate["ops"] = _canonical_ops(candidate["ops"])
    body["candidates"] = sorted(body.get("candidates", []), key=lambda candidate: candidate["candidate_id"])
    return _digest(body)


def validate_task_local_proposal(proposal, *, run_scope, allowed_assets, resolver_root=None,
                                 base_profile=None, base_generation=None, template=None):
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).parent / "schemas/task-local-layout-proposal-v1.schema.json").read_text())
    if list(Draft202012Validator(schema).iter_errors(proposal)):
        raise ProposalError("proposal_schema_invalid")
    if proposal["run_scope"] != run_scope:
        raise ProposalError("proposal_run_scope_mismatch")
    if proposal["base_asset"] not in allowed_assets:
        raise ProposalError("proposal_asset_not_allowed")
    if proposal["proposal_digest"] != proposal_digest(proposal):
        raise ProposalError("proposal_digest_mismatch")
    if base_profile is None or base_generation is None:
        raise ProposalError("proposal_base_snapshot_required")
    if (proposal["base_generation"] != base_generation or base_profile["asset_id"] != proposal["base_asset"]
            or _digest(base_profile) != proposal["base_asset_digest"]):
        raise ProposalError("proposal_base_stale")
    if resolver_root is not None and Path(resolver_root).is_symlink():
        raise ProposalError("proposal_path_outside_root")
    ids = set()
    for candidate in proposal["candidates"]:
        if candidate["candidate_id"] in ids or candidate["candidate_id"].startswith(("builtin:", "user:")):
            raise ProposalError("proposal_identity_collision")
        ids.add(candidate["candidate_id"])
        lane = candidate["lane"]
        if not (base_profile.get("renderer_support") or {}).get(lane):
            raise ProposalError("proposal_lane_unsupported")
        seen = set()
        for op in candidate["ops"]:
            if op["base_asset"] != proposal["base_asset"] or op["lane"] != lane:
                raise ProposalError("proposal_op_scope_mismatch")
            if (op["op"], op["target"]) in seen:
                raise ProposalError("proposal_target_conflict")
            seen.add((op["op"], op["target"]))
            target = op["target"]
            regions, slots = base_profile.get("regions", {}), base_profile.get("slots", {})
            if op["op"] == "set_region_assignment":
                if target not in slots or op["value"] not in regions:
                    raise ProposalError("proposal_anchor_unknown")
            elif op["op"] == "set_anchor_gap":
                if target not in regions or op["anchor"] not in regions or target == op["anchor"]:
                    raise ProposalError("proposal_anchor_unknown")
            elif op["op"] == "set_span":
                if target not in regions:
                    raise ProposalError("proposal_anchor_unknown")
            elif op["op"] == "set_slot_mapping":
                if target not in slots or op["value"] not in slots:
                    raise ProposalError("proposal_slot_unknown")
                fields = {field["name"]: field for field in (template or {}).get("input_fields", [])}
                if lane == "render:html":
                    left, right = fields.get(target), fields.get(op["value"])
                    if not left or not right or (left.get("type"), left.get("items")) != (right.get("type"), right.get("items")):
                        raise ProposalError("proposal_slot_type_mismatch")


def apply_task_local_proposal(proposal, *, base_profile, base_generation, run_scope,
                              allowed_assets, content, theme, template=None):
    """返回独立 profile 与投影置换；所有输入保持原字节语义，候选一次性评估。"""
    validate_task_local_proposal(proposal, run_scope=run_scope, allowed_assets=allowed_assets,
        base_profile=base_profile, base_generation=base_generation, template=template)
    before = _digest({"base": base_profile, "content": content, "theme": theme})
    results = []
    for candidate in proposal["candidates"]:
        profile = deepcopy(base_profile)
        mapping = {}
        for op in _canonical_ops(candidate["ops"]):
            target, value = op["target"], op["value"]
            if op["op"] == "set_region_assignment":
                profile["slots"][target]["region"] = value
            elif op["op"] == "set_anchor_gap":
                anchor = profile["regions"][op["anchor"]]
                profile["regions"][target]["y"] = anchor["y"] + anchor["height"] + value
            elif op["op"] == "set_span":
                profile["regions"][target].update(value)
            else:
                mapping[target] = value
        for region in profile["regions"].values():
            if (region["x"] < 0 or region["y"] < 0 or region["width"] <= 0 or region["height"] <= 0
                    or region["x"] + region["width"] > profile["canvas"]["width"]
                    or region["y"] + region["height"] > profile["canvas"]["height"]):
                raise ProposalError("proposal_canvas_overflow")
        # slot_mapping 只允许置换，不能复制覆盖或删除一个原来的内容槽。
        if mapping and (set(mapping) != set(mapping.values()) or len(set(mapping.values())) != len(mapping)):
            raise ProposalError("proposal_content_mapping_not_bijective")
        normalized = {**candidate, "ops": _canonical_ops(candidate["ops"])}
        results.append({"source_kind": "task-local-proposal", "run_scope": run_scope,
            "proposal_digest": _digest({"base_asset_digest": proposal["base_asset_digest"],
                "base_generation": base_generation, "run_scope": run_scope, "candidate": normalized}),
            "base_asset": proposal["base_asset"], "base_generation": base_generation,
            "candidate_id": candidate["candidate_id"], "lane": candidate["lane"],
            "profile": profile, "slot_mapping": mapping,
            "content_digest": _digest(content), "theme_digest": _digest(theme),
            "qualification_status": "unverified"})
    if before != _digest({"base": base_profile, "content": content, "theme": theme}):
        raise ProposalError("proposal_mutated_inputs")
    return results


def curation_feedback(proposal, outcomes):
    """只聚合本次证据，任何成功/使用次数都不自动晋升共享资产。"""
    allowed = {candidate["candidate_id"] for candidate in proposal["candidates"]}
    if len(outcomes) > 3 or any(row.get("candidate_id") not in allowed for row in outcomes):
        raise ProposalError("proposal_feedback_scope_mismatch")
    if len({row["candidate_id"] for row in outcomes}) != len(outcomes):
        raise ProposalError("proposal_feedback_duplicate_attempt")
    return {"schema_version": 1, "kind": "task-local-curation-feedback", "run_scope": proposal["run_scope"],
        "proposal_digest": proposal["proposal_digest"], "attempts": deepcopy(outcomes), "automatic_promotion": False}
