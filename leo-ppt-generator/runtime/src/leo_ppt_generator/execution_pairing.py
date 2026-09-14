"""执行配对的判别式身份；输入为 resolver records，禁止自行查路径或授予资格。"""
from __future__ import annotations

import hashlib
from copy import deepcopy
from .storage import canonical_json_bytes


class PairingError(ValueError):
    pass


def _identity(record):
    return {"asset_id": record["asset_id"], "revision": record["revision"]}


def pairing_identity(*, layout, executable, lane, catalog_generation, evidence_digest,
                     proposal=None):
    if lane not in {"render:html", "image"} or not catalog_generation or not evidence_digest:
        raise PairingError("execution_pairing_incomplete")
    kind = "template" if lane == "render:html" else "recipe"
    if executable.get("kind") != kind or executable["data"].get("lane") != lane:
        raise PairingError("execution_pairing_lane_mismatch")
    scope = layout["asset_id"].split(":", 1)[0]
    identity = {"source_kind": "canonical", "scope": scope,
        "catalog_generation": catalog_generation, "lane": lane,
        "layout_identity": _identity(layout),
        "template_identity": _identity(executable) if kind == "template" else None,
        "recipe_identity": _identity(executable) if kind == "recipe" else None,
        "capability_evidence_digest": evidence_digest}
    if proposal is not None:
        if not proposal.get("proposal_digest") or not proposal.get("run_scope"):
            raise PairingError("proposal_identity_incomplete")
        identity.update(source_kind="task-local-proposal", proposal_digest=proposal["proposal_digest"],
                        run_scope=proposal["run_scope"])
    return identity


def pairing_key(identity):
    """所有判别字段参与去重；缺字段、混合分支和未知扩展均拒绝。"""
    from jsonschema import Draft202012Validator
    import json
    from pathlib import Path
    schema = json.loads((Path(__file__).parent / "schemas/execution-pairing-v1.schema.json").read_text())
    if list(Draft202012Validator(schema).iter_errors(identity)):
        raise PairingError("execution_pairing_schema_mismatch")
    return hashlib.sha256(canonical_json_bytes(identity)).hexdigest()


def validate_candidate_view(view):
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    root = Path(__file__).parent / "schemas"
    pairing = json.loads((root / "execution-pairing-v1.schema.json").read_text())
    schema = json.loads((root / "execution-candidate-view-v1.schema.json").read_text())
    registry = Registry().with_resource(pairing["$id"], Resource.from_contents(pairing))
    if list(Draft202012Validator(schema, registry=registry).iter_errors(view)):
        raise PairingError("execution_candidate_view_schema_mismatch")
    identities = set()
    for candidate in view["candidates"]:
        identity = candidate["identity"]
        key = pairing_key(identity)
        if (key != candidate["identity_digest"] or key in identities
                or identity["catalog_generation"] != view["catalog_generation"]):
            raise PairingError("execution_candidate_identity_mismatch")
        identities.add(key)
        from .qualification import qualification_admits
        if any(evidence["evidence_set_digest"] != identity["capability_evidence_digest"]
               or not qualification_admits(evidence, purpose=view["qualification_purpose"])
               for evidence in candidate["relations"].values()):
            raise PairingError("execution_candidate_evidence_mismatch")
    return view


def derive_execution_pairings(layouts, executables, qualifications, *, catalog_generation,
                             qualification_purpose="publication"):
    """owner 双向引用、输入槽位与当前关系证据的交集；无物理路径或排名。"""
    executable_by_id = {record["asset_id"]: record for record in executables}
    if len(executable_by_id) != len(executables):
        raise PairingError("execution_pairing_duplicate_asset")
    result, gaps = {}, []
    for layout in layouts:
        owner = layout["data"]
        for lane in ("render:html", "image"):
            executable_id = ((owner.get("renderer_support") or {}).get(lane) if lane == "render:html"
                             else owner.get("image_recipe"))
            executable = executable_by_id.get(executable_id) if isinstance(executable_id, str) else None
            if executable is None:
                gaps.append({"layout_id": layout["asset_id"], "lane": lane, "reason": "lane_dependency_missing"})
                continue
            data = executable["data"]
            slots = ({entry.get("slot") for entry in data.get("slot_bindings", [])} if lane == "render:html"
                     else set(data.get("slot_map", {})))
            from .template_inputs import slot_input_path_errors
            if (layout["asset_id"] not in data.get("layout_profiles", [])
                    or not set(owner.get("slots", {})).issubset(slots)
                    or (lane == "render:html" and slot_input_path_errors(data, owner))):
                gaps.append({"layout_id": layout["asset_id"], "lane": lane, "reason": "lane_slot_closure_missing"})
                continue
            qualification = qualifications.get(layout["asset_id"], {})
            for relation, evidence in qualification.get("lanes", {}).get(lane, {}).get("relations", {}).items():
                from .qualification import qualification_admits
                if not qualification_admits(evidence, purpose=qualification_purpose):
                    continue
                identity = pairing_identity(layout=layout, executable=executable, lane=lane,
                    catalog_generation=catalog_generation, evidence_digest=evidence["evidence_set_digest"])
                key = pairing_key(identity)
                entry = result.setdefault(key, {"identity": identity, "identity_digest": key, "relations": {}})
                if relation in entry["relations"] and entry["relations"][relation] != evidence:
                    raise PairingError("execution_pairing_evidence_conflict")
                entry["relations"][relation] = deepcopy(evidence)
    return validate_candidate_view({"schema_version": 1, "kind": "execution-candidate-view", "catalog_generation": catalog_generation,
            "qualification_purpose": qualification_purpose,
            "candidates": sorted(result.values(), key=canonical_json_bytes),
            "gaps": sorted({canonical_json_bytes(g): g for g in gaps}.values(), key=canonical_json_bytes)})
