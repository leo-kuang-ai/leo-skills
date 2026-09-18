"""受约束的任务内 geometry/slot 提案；不修改 canonical、正文、主题或用户范围。"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re
from pathlib import Path

from .storage import canonical_json_bytes


class ProposalError(ValueError):
    pass


ALLOWED_OPS = ("set_region_assignment", "set_anchor_gap", "set_span", "set_slot_mapping")


def _digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonical_ops(ops):
    return sorted(ops, key=lambda op: (ALLOWED_OPS.index(op["op"]) if op.get("op") in ALLOWED_OPS else len(ALLOWED_OPS),
                                      op.get("target", ""), canonical_json_bytes(op)))


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
    if resolver_root is not None:
        root = Path(resolver_root).absolute()
        if any(path.is_symlink() for path in (root, *root.parents)):
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
            numeric = op["value"].values() if isinstance(op["value"], dict) else [op["value"]]
            if any(isinstance(value, (int, float)) and not math.isfinite(value) for value in numeric):
                raise ProposalError("proposal_value_invalid")
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
                if slots[target].get("content_type") != slots[op["value"]].get("content_type"):
                    raise ProposalError("proposal_slot_type_mismatch")
                fields = {field["name"]: field for field in (template or {}).get("input_fields", [])}
                if lane == "render:html":
                    left, right = fields.get(target), fields.get(op["value"])
                    if not left or not right or (left.get("type"), left.get("items")) != (right.get("type"), right.get("items")):
                        raise ProposalError("proposal_slot_type_mismatch")


def apply_task_local_proposal(proposal, *, base_profile, base_generation, run_scope,
                              allowed_assets, content, theme, template=None, collect_failures=False):
    """返回独立 profile 与投影置换；所有输入保持原字节语义，候选一次性评估。"""
    validate_task_local_proposal(proposal, run_scope=run_scope, allowed_assets=allowed_assets,
        base_profile=base_profile, base_generation=base_generation, template=template)
    before = _digest({"base": base_profile, "content": content, "theme": theme})
    results = []
    document = deepcopy(proposal)
    for entry in document["candidates"]:
        entry["ops"] = _canonical_ops(entry["ops"])
    document["candidates"].sort(key=lambda entry: entry["candidate_id"])
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
        gap = None
        for region in profile["regions"].values():
            if (region["x"] < 0 or region["y"] < 0 or region["width"] <= 0 or region["height"] <= 0
                    or region["x"] + region["width"] > profile["canvas"]["width"]
                    or region["y"] + region["height"] > profile["canvas"]["height"]):
                gap = "proposal_canvas_overflow"
        # slot_mapping 只允许置换，不能复制覆盖或删除一个原来的内容槽。
        if mapping and (set(mapping) != set(mapping.values()) or len(set(mapping.values())) != len(mapping)):
            gap = "proposal_content_mapping_not_bijective"
        # 模板按原 region 名消费 CSS；共享 region 的槽必须一起移动，禁止隐式移动另一槽。
        assignments = {}
        for name, slot in profile["slots"].items():
            original = base_profile["slots"][name].get("region")
            target = slot.get("region")
            if original in assignments and assignments[original] != target:
                gap = "proposal_shared_region_conflict"
            assignments[original] = target
        geometry = deepcopy(profile["regions"])
        for original, target in assignments.items():
            if original is not None and target is not None:
                geometry[original] = deepcopy(profile["regions"][target])
        profile["regions"] = geometry
        for name, slot in profile["slots"].items():
            if "region" in base_profile["slots"][name]:
                slot["region"] = base_profile["slots"][name]["region"]
        if gap:
            if not collect_failures:
                raise ProposalError(gap)
            results.append({"candidate_id": candidate["candidate_id"], "lane": candidate["lane"],
                            "status": "failed", "gap": gap})
            continue
        normalized = {**candidate, "ops": _canonical_ops(candidate["ops"])}
        results.append({"source_kind": "task-local-proposal", "run_scope": run_scope,
            "proposal_digest": _digest({"base_asset_digest": proposal["base_asset_digest"],
                "base_generation": base_generation, "run_scope": run_scope, "candidate": normalized}),
            "base_asset": proposal["base_asset"], "base_generation": base_generation,
            "candidate_id": candidate["candidate_id"], "lane": candidate["lane"],
            "profile": profile, "slot_mapping": mapping,
            "document": deepcopy(document),
            "content": deepcopy(content), "theme": deepcopy(theme),
            "content_digest": _digest(content), "theme_digest": _digest(theme),
            "qualification_status": "unverified"})
    if before != _digest({"base": base_profile, "content": content, "theme": theme}):
        raise ProposalError("proposal_mutated_inputs")
    return results


def replay_bound_proposal(proposal, *, resolver, content, theme, run_scope=None):
    """从原版式与封闭 op 重放；不能信任绑定中手写的 effective profile。"""
    if not isinstance(proposal, dict) or "document" not in proposal:
        raise ProposalError("proposal_snapshot_missing")
    base = resolver.resolve(proposal["base_asset"])
    lane = proposal["lane"]
    template = (resolver.resolve(base["data"]["renderer_support"][lane])["data"]
                if lane == "render:html" else None)
    rows = apply_task_local_proposal(proposal["document"], base_profile=base["data"],
        base_generation=resolver.generation, run_scope=run_scope or proposal["run_scope"],
        allowed_assets={base["asset_id"]}, content=content, theme=theme, template=template,
        collect_failures=True)
    actual = next((row for row in rows if row["candidate_id"] == proposal["candidate_id"]), None)
    if actual != proposal:
        raise ProposalError("proposal_snapshot_changed")
    return actual


def effective_layout_profile(binding, *, resolver):
    proposal = binding.get("proposal")
    result = deepcopy(proposal["profile"] if proposal else resolver.resolve(binding["layout_id"])["data"])
    if proposal:
        result["slot_mapping"] = deepcopy(proposal["slot_mapping"])
    return result


def remap_slot_data(data, mapping):
    """只置换已有顶层输入字段，保留其余内容；容量和模板类型仍由统一预编译验证。"""
    result = deepcopy(data)
    for source, target in mapping.items():
        if source in data:
            result[target] = deepcopy(data[source])
        else:
            result.pop(target, None)
    return result


def proposal_reference(proposal):
    return "evidence/proposals/" + proposal["proposal_digest"] + "/" + _digest(proposal) + "/proposal.json"


def proposal_probe_output(proposal):
    return "evidence/probes/proposal-" + _digest(proposal)


def prepare_proposal_workspace(resolver, *, run_root, run_scope, input_digest):
    """只在任务根隔离复制输入库；共享 catalog/资产和原证据从不被补写。"""
    import shutil
    import tempfile
    from filelock import FileLock
    from .asset_resolver import AssetResolver
    from .storage import atomic_write_json, fsync_directory

    run_root = Path(run_root).absolute()
    if not re.fullmatch(r"[0-9a-f]{64}", input_digest):
        raise ProposalError("proposal_path_outside_root")
    roots = {"builtin": resolver.builtin_root, "user/template-library": resolver.user_root}
    roots = {scope: Path(root).absolute() for scope, root in roots.items() if root is not None and Path(root).exists()}
    if any(path.is_symlink() for root in roots.values() for path in (root, *root.parents)):
        raise ProposalError("proposal_path_outside_root")
    if any(run_root.is_relative_to(root) or root.is_relative_to(run_root) for root in roots.values()):
        raise ProposalError("proposal_path_outside_root")
    parent = run_root / ".proposal-work"
    if any(path.is_symlink() for path in (parent, *parent.parents)):
        raise ProposalError("proposal_path_outside_root")
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / input_digest

    def snapshot_files(root):
        rows = {}
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ProposalError("proposal_path_outside_root")
            if path.is_file():
                rows[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return rows

    source_files = {scope: snapshot_files(root) for scope, root in roots.items()}
    marker = {"run_scope": run_scope, "input_digest": input_digest, "source_files": source_files}
    lock = parent / (input_digest + ".lock")
    if lock.is_symlink():
        raise ProposalError("proposal_path_outside_root")
    with FileLock(str(lock)):
        if target.is_symlink():
            raise ProposalError("proposal_path_outside_root")
        if target.exists():
            if json.loads((target / "scope.json").read_text()) != marker:
                raise ProposalError("proposal_workspace_stale")
            for scope, files in source_files.items():
                actual = snapshot_files(target / "asset-snapshot" / scope)
                if any(actual.get(path) != expected for path, expected in files.items()):
                    raise ProposalError("proposal_workspace_stale")
                if any(not path.startswith(("evidence/proposals/", "evidence/probes/proposal-")) for path in set(actual) - set(files)):
                    raise ProposalError("proposal_workspace_stale")
        else:
            with tempfile.TemporaryDirectory(prefix=".stage-", dir=parent) as temporary:
                stage = Path(temporary)
                for scope, root in roots.items():
                    destination = stage / "asset-snapshot" / scope
                    shutil.copytree(root, destination)
                    if snapshot_files(destination) != source_files[scope] or snapshot_files(root) != source_files[scope]:
                        raise ProposalError("proposal_source_changed")
                atomic_write_json(stage / "scope.json", marker)
                stage.rename(target)
                fsync_directory(parent)
    return AssetResolver.from_snapshot(target / "asset-snapshot")


def proposal_candidate_factory(documents, *, resolver, run_scope, design_context, probe_cases=None, read_only=False):
    """共享候选失败后只展开一次有限候选；每个 patch 必须有自己的真实证据。"""
    from .qualification import read_evidence_bytes
    from .storage import atomic_write_json
    attempted = set()

    def candidates(page, lane):
        document = documents.get(page["page_id"])
        if document is None:
            return []
        key = (page["page_id"], lane)
        if key in attempted:
            raise ProposalError("proposal_recursive_attempt")
        attempted.add(key)
        base = resolver.resolve(document["base_asset"])
        template = (resolver.resolve(base["data"]["renderer_support"]["render:html"])["data"]
                    if base["data"].get("renderer_support", {}).get("render:html") else None)
        theme = {key: deepcopy(design_context["effective"].get(key, {})) for key in ("colors", "fonts", "chart_palette")}
        rows = apply_task_local_proposal(document, base_profile=base["data"], base_generation=resolver.generation,
            run_scope=run_scope, allowed_assets={base["asset_id"]}, content=page, theme=theme,
            template=template, collect_failures=True)
        output = []
        for row in rows:
            if row["lane"] != lane:
                continue
            if row.get("status") == "failed":
                output.append(row)
                continue
            root = Path(base["trusted_root"])
            path = proposal_reference(row)
            try:
                # 工作库仅由 prepare_proposal_workspace 建立，禁止对活动库取证写入。
                scope_path = resolver.builtin_root.parent.parent / "scope.json"
                scope = json.loads(scope_path.read_text())
                if scope["run_scope"] != run_scope:
                    raise ProposalError("proposal_run_scope_mismatch")
                if (root / path).exists():
                    if json.loads(read_evidence_bytes(root, path)) != row:
                        raise ProposalError("proposal_snapshot_changed")
                elif not read_only:
                    atomic_write_json(root / path, row)
                else:
                    raise ProposalError("proposal_snapshot_missing")
                if probe_cases is not None and lane == "render:html" and not read_only:
                    from .capability_probes import run_probes
                    cases = {**probe_cases, "cases": [case for case in probe_cases.get("cases", [])
                        if case["layout_id"] == row["base_asset"] and case["relation"] == page["expression"]["relation"]["kind"]]}
                    run_probes(library_root=root, cases=cases, output=proposal_probe_output(row), proposal=row)
                output.append(row)
            except (ValueError, OSError, KeyError) as exc:
                output.append({"candidate_id": row["candidate_id"], "lane": lane, "status": "failed", "gap": str(exc)})
        return output
    return candidates


def curation_feedback(proposal, outcomes):
    """只聚合本次证据，任何成功/使用次数都不自动晋升共享资产。"""
    allowed = {candidate["candidate_id"] for candidate in proposal["candidates"]}
    if len(outcomes) > 3 or any(row.get("candidate_id") not in allowed for row in outcomes):
        raise ProposalError("proposal_feedback_scope_mismatch")
    if len({row["candidate_id"] for row in outcomes}) != len(outcomes):
        raise ProposalError("proposal_feedback_duplicate_attempt")
    return {"schema_version": 1, "kind": "task-local-curation-feedback", "run_scope": proposal["run_scope"],
        "proposal_digest": proposal["proposal_digest"], "attempts": deepcopy(outcomes), "automatic_promotion": False}
