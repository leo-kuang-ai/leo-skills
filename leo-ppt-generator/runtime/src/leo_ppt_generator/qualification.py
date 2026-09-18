"""能力声明与逐 relation/lane 的字节证据准入；不拥有候选排名。"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import stat
import sys
from functools import lru_cache
from pathlib import Path, PurePosixPath

from .storage import canonical_json_bytes

ORACLE_PATH = "evidence/oracles/relation-output-v1.json"
RECEIPTS_PATH = "evidence/capability-receipts.json"
POLICY = "qualification-v1/2"
STATES = ("rejected", "unverified", "provisional", "publication-qualified")


def qualification_admits(qualification, *, purpose="publication"):
    """非发布验证可消费实测 provisional；缺证据或其他 gap 永不放行。"""
    if purpose not in {"publication", "validation"}:
        raise QualificationError("qualification_purpose_invalid")
    if qualification.get("status") == "publication-qualified":
        return True
    return (purpose == "validation" and qualification.get("status") == "provisional"
            and qualification.get("probe_receipts") and qualification.get("evidence_set_digest")
            and bool(qualification.get("gaps"))
            and set(qualification["gaps"]).issubset({"visual_review_not_run", "u6a_required"})) is True


class QualificationError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def evidence_digest(receipt):
    return digest({k: v for k, v in receipt.items() if k != "evidence_digest"})


def read_evidence_bytes(root, relative, *, max_bytes=32 * 1024 * 1024):
    """按目录描述符逐层打开，拒绝路径逃逸、链接与读取期间的字节变化。"""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise QualificationError("evidence_path_invalid")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"..", "."} for part in relative.split("/")) or "" in relative.split("/"):
        raise QualificationError("evidence_path_invalid")
    descriptors = []
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in path.parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise QualificationError("evidence_file_type_or_size")
        chunks, size = [], 0
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise QualificationError("evidence_file_type_or_size")
            chunks.append(chunk)
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise QualificationError("evidence_changed_during_read")
        return b"".join(chunks)
    except OSError as exc:
        raise QualificationError("evidence_file_unavailable: " + relative) from exc
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def file_reference(root, relative):
    return {"path": relative, "sha256": hashlib.sha256(read_evidence_bytes(root, relative)).hexdigest()}


def verify_reference(root, reference):
    body = read_evidence_bytes(root, reference["path"])
    if hashlib.sha256(body).hexdigest() != reference["sha256"]:
        raise QualificationError("evidence_stale: " + reference["path"])
    return body


@lru_cache(maxsize=512)
def _environment_file_hash(path, size, mtime_ns, ctime_ns, inode):
    from .storage import sha256_file
    return sha256_file(Path(path))


def _fingerprint_file(path):
    metadata = path.stat()
    return _environment_file_hash(str(path), metadata.st_size, metadata.st_mtime_ns,
                                  metadata.st_ctime_ns, metadata.st_ino)


def is_execution_source(relative):
    """环境指纹和旧链封存共用同一执行源码成员规则。"""
    return (relative in {"relation_oracle.py", "raster_oracle.py", "raster_text.swift", "image_deck/expression_adapter.py"}
            or relative.endswith(".py") and relative.startswith(("render/", "providers/")))


def environment_fingerprint():
    """不输出凭据、主目录或主机名；执行源码变化也使旧 receipt 失效。"""
    package = Path(__file__).parent
    versions = {}
    for name in ("playwright", "Pillow", "python-pptx", "jsonschema"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    source = {path.relative_to(package).as_posix(): _fingerprint_file(path)
              for path in sorted(package.rglob("*")) if path.is_file()
              and is_execution_source(path.relative_to(package).as_posix())}
    from .render.assets import font_dirs, vendor_dir
    from .render.readiness import _apply_browsers_path, _default_playwright_cache
    browser_root = _apply_browsers_path() or _default_playwright_cache()
    browser = {}
    if browser_root:
        cache = Path(browser_root)
        for pattern in ("**/chrome", "**/headless_shell", "**/chrome-headless-shell", "**/chrome.exe", "**/Chromium"):
            for path in sorted(cache.glob(pattern)):
                if path.is_file():
                    browser[path.relative_to(cache).as_posix()] = _fingerprint_file(path)
    if os.environ.get("LEO_PPT_RENDER_CHROMIUM"):
        override = Path(os.environ["LEO_PPT_RENDER_CHROMIUM"])
        browser = {"explicit-executable": _fingerprint_file(override)} if override.is_file() else {"explicit-executable": None}
    fonts, vendor = {}, {}
    for index, directory in enumerate(font_dirs()):
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".otf", ".ttf", ".woff", ".woff2", ".ttc"}:
                fonts[f"{index}/{path.relative_to(directory).as_posix()}"] = _fingerprint_file(path)
    directory = vendor_dir()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            vendor[path.relative_to(directory).as_posix()] = _fingerprint_file(path)
    return {"system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "python": platform.python_version(),
            "implementation": sys.implementation.name, "packages": versions,
            "execution_source_digest": digest(source), "browser_binaries": browser,
            "font_files": fonts, "vendor_files": vendor}


def _load_schema(name):
    return json.loads((Path(__file__).parent / "schemas" / name).read_text(encoding="utf-8"))


def _verify_schema(receipt):
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(_load_schema("capability-evidence-v1.schema.json")).iter_errors(receipt))
    if errors:
        raise QualificationError("evidence_schema_mismatch: " + errors[0].message)


def verify_capability_evidence(receipt, *, library_root, asset_generation,
                               expected_dependencies, environment):
    """重新读取当前 owner/oracle/fixture/导出/观测/裁决；历史 passed 无优先权。"""
    _verify_schema(receipt)
    if receipt["evidence_digest"] != evidence_digest(receipt):
        raise QualificationError("evidence_digest_mismatch")
    if receipt["asset_generation"] != asset_generation:
        raise QualificationError("evidence_generation_stale")
    if receipt["dependency_hashes"] != expected_dependencies or not expected_dependencies:
        raise QualificationError("evidence_dependency_stale")
    for relative, expected in expected_dependencies.items():
        verify_reference(library_root, {"path": relative, "sha256": expected})
    oracle_ref = receipt["oracle"]
    if oracle_ref["path"] != ORACLE_PATH:
        raise QualificationError("evidence_oracle_owner_mismatch")
    oracle = json.loads(verify_reference(library_root, oracle_ref))
    if (oracle.get("owner"), oracle.get("version")) != (oracle_ref["owner"], oracle_ref["version"]):
        raise QualificationError("evidence_oracle_owner_mismatch")
    relation, lane = receipt["relation"], receipt["lane"]
    rule, lane_rule = oracle["relations"].get(relation), oracle["lanes"].get(lane)
    if not rule or not lane_rule:
        raise QualificationError("evidence_relation_lane_invalid")
    recorded_environment = json.loads(verify_reference(library_root, receipt["environment"]))
    if recorded_environment != environment:
        raise QualificationError("evidence_environment_stale")
    required_checks = set(oracle["common"] + rule["required_checks"])
    artifacts = []
    provider_identities = set()
    for name, accepted in (("positive", True), ("negative", False)):
        probe = receipt["probes"][name]
        fixture = json.loads(verify_reference(library_root, probe["fixture"]))
        artifact_body = verify_reference(library_root, probe["artifact"])
        # PNG 文件头与尺寸/解码检查不代表视觉合格，但拒绝伪装的导出。
        import io
        from PIL import Image
        try:
            with Image.open(io.BytesIO(artifact_body)) as image:
                if image.format != "PNG" or image.size != (2560, 1440):
                    raise ValueError("invalid PNG")
                image.verify()
        except Exception as exc:
            raise QualificationError("evidence_export_invalid") from exc
        artifacts.append(probe["artifact"])
        observation = json.loads(verify_reference(library_root, probe["observation"]))
        if (observation.get("artifact") != probe["artifact"]
                or observation.get("fixture") != probe["fixture"]
                or observation.get("oracle_sha256") != oracle_ref["sha256"]
                or observation.get("relation") != relation or observation.get("lane") != lane
                or observation.get("environment_sha256") != receipt["environment"]["sha256"]):
            raise QualificationError("evidence_observation_binding_mismatch")
        checks = observation.get("checks", {})
        if set(checks) != required_checks or any(type(v) is not bool for v in checks.values()):
            raise QualificationError("evidence_observation_incomplete")
        from .relation_oracle import evaluate_output
        if not observation.get("measurement"):
            raise QualificationError("evidence_output_measurement_missing")
        measurement = json.loads(verify_reference(library_root, observation["measurement"]))
        if measurement.get("artifact_sha256") != probe["artifact"]["sha256"]:
            raise QualificationError("evidence_output_measurement_mismatch")
        proposal_refs = [path for path in expected_dependencies if path.startswith("evidence/proposals/") and path.endswith("/proposal.json")]
        if proposal_refs:
            if len(proposal_refs) != 1:
                raise QualificationError("proposal_evidence_snapshot_mismatch")
            proposal = json.loads(read_evidence_bytes(library_root, proposal_refs[0]))
            if measurement.get("proposal_sha256") != digest(proposal):
                raise QualificationError("proposal_evidence_output_mismatch")
        render_input = observation.get("render_input")
        if lane == "image":
            from .raster_oracle import evaluate_raster_output, verify_image_probe_source
            try:
                provider = verify_image_probe_source(root=library_root, fixture=fixture, relation=relation,
                    artifact=probe["artifact"], render_input=render_input,
                    provider_reference=probe.get("provider_receipt"), dependencies=expected_dependencies)
                provider_identities.add((provider["provider"], provider["model"], provider["contract_sha256"]))
                review = json.loads(verify_reference(library_root, observation["raster_review"]))
                evaluated = evaluate_raster_output(fixture.get("expected"), artifact_body, review,
                    relation=relation, oracle=oracle, environment_sha256=receipt["environment"]["sha256"])
                if evaluated["measurement"] != measurement:
                    raise QualificationError("image_output_measurement_mismatch")
                computed = evaluated["checks"]
            except (ValueError, KeyError, TypeError) as exc:
                raise QualificationError("image_output_evidence_invalid: " + str(exc)) from exc
        else:
            if (not render_input or measurement.get("data_sha256") != render_input["sha256"]
                    or json.loads(verify_reference(library_root, render_input)) != fixture.get("data")
                    or measurement.get("template_sha256") not in {
                        h for p, h in expected_dependencies.items() if p.endswith("/page.html")}):
                raise QualificationError("evidence_output_source_mismatch")
            computed = evaluate_output(fixture.get("expected"), measurement, relation=relation, oracle=oracle)
        if computed != checks:
            raise QualificationError("evidence_output_check_mismatch")
        observed_accepted = all(checks.values())
        if (probe["status"] != "passed" or observed_accepted != accepted
                or (not accepted and checks[rule["negative_check"]] is not False)):
            raise QualificationError("evidence_probe_failed: " + name)
        if lane_rule.get("requires_provider_receipt") and lane != "image":
            provider = probe.get("provider_receipt")
            if not provider:
                raise QualificationError("evidence_provider_receipt_missing")
            provider_data = json.loads(verify_reference(library_root, provider))
            if (provider_data.get("status") != "succeeded" or not provider_data.get("request_id")
                    or provider_data.get("artifact") != probe["artifact"]
                    or provider_data.get("fixture") != probe["fixture"]
                    or provider_data.get("lane") != lane):
                raise QualificationError("evidence_provider_receipt_mismatch")
    if (receipt["probes"]["positive"]["fixture"] == receipt["probes"]["negative"]["fixture"]
            or artifacts[0] == artifacts[1]):
        raise QualificationError("evidence_probe_not_independent")
    if lane == "image" and len(provider_identities) != 1:
        raise QualificationError("evidence_provider_contract_conflict")
    review = receipt.get("visual_review")
    if lane_rule.get("requires_visual_review"):
        if review is None:
            return {"status": "provisional", "gaps": ["visual_review_not_run"]}
        reviewed = json.loads(verify_reference(library_root, review))
        if (reviewed.get("artifacts") != artifacts or reviewed.get("oracle_sha256") != oracle_ref["sha256"]
                or reviewed.get("environment_sha256") != receipt["environment"]["sha256"]):
            raise QualificationError("evidence_visual_review_stale")
        if reviewed.get("status") != "passed" or reviewed.get("severe_defects") != 0 or not reviewed.get("reviewer"):
            raise QualificationError("evidence_visual_review_failed")
        if not reviewed.get("u6a"):
            return {"status": "provisional", "gaps": ["u6a_required"]}
        from .quality_replay import verify_capability_publication
        verify_capability_publication(library_root, receipt, reviewed["u6a"])
    return {"status": "publication-qualified", "gaps": []}


def verify_provider_qualification(qualification, *, library_root, contract_sha256):
    """候选和冻结消费共用同一 Provider 合同门，不能借用其他模型的探针资格。"""
    import re
    if not isinstance(contract_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", contract_sha256):
        raise QualificationError("evidence_provider_contract_missing")
    receipts = qualification.get("receipt_payloads")
    if not receipts:
        raise QualificationError("binding_qualification_evidence_missing")
    from .image_deck.expression_adapter import verify_provider_export
    for capability in receipts:
        if capability.get("lane") != "image":
            raise QualificationError("evidence_provider_lane_mismatch")
        for name in ("positive", "negative"):
            reference = capability["probes"][name]["provider_receipt"]
            provider = json.loads(verify_reference(library_root, reference))
            if provider.get("contract_sha256") != contract_sha256:
                raise QualificationError("evidence_provider_contract_mismatch")
            verify_provider_export(provider, root=Path(library_root) / PurePosixPath(reference["path"]).parent)
            if provider.get("evidence_source") != "provider-http" or provider.get("purpose") != "capability-probe":
                raise QualificationError("image_real_provider_evidence_required")


def _aggregate(statuses):
    return next((status for status in STATES if status in statuses), "unverified")


def derive_qualification(asset, *, asset_generation, evidence_receipts=None,
                         library_root=None, expected_dependencies=None, environment=None):
    """未经核验的声明只能 unverified；失败、漂移不能被另一条通过记录遮盖。"""
    receipts = [r for r in (evidence_receipts or []) if isinstance(r, dict) and r.get("asset_id") == asset.get("asset_id")]
    lanes = {}
    for lane in asset.get("lanes", []):
        relations = {}
        for relation in asset.get("relations", []):
            candidates = [r for r in receipts if r.get("lane") == lane and r.get("relation") == relation]
            statuses, gaps, ids = [], list(asset.get("gaps", {}).get(lane, [])), []
            seen = set()
            for receipt in candidates:
                try:
                    if not library_root or expected_dependencies is None or environment is None:
                        raise QualificationError("evidence_verification_context_missing")
                    if receipt.get("receipt_id") in seen:
                        raise QualificationError("evidence_duplicate_receipt")
                    seen.add(receipt.get("receipt_id"))
                    result = verify_capability_evidence(receipt, library_root=library_root,
                        asset_generation=asset_generation, expected_dependencies=expected_dependencies.get(lane, expected_dependencies),
                        environment=environment)
                    statuses.append(result["status"])
                    gaps.extend(result["gaps"])
                    ids.append(receipt["receipt_id"])
                except (QualificationError, ValueError, TypeError, KeyError) as exc:
                    statuses.append("rejected")
                    gaps.append(str(exc))
            if not candidates:
                gaps.append("positive_negative_evidence_missing")
            if asset.get("gaps", {}).get(lane):
                statuses.append("rejected")
            relations[relation] = {"status": _aggregate(statuses), "probe_receipts": sorted(ids), "gaps": sorted(set(gaps)),
                                   "evidence_set_digest": digest(sorted(candidates, key=canonical_json_bytes)) if candidates else None}
        lanes[lane] = {"status": _aggregate([r["status"] for r in relations.values()]), "relations": relations}
    lifecycle = asset.get("lifecycle_status", "unknown")
    if lifecycle not in {"unknown", "legacy", "executable", "retired"}:
        raise QualificationError("qualification_lifecycle_invalid")
    if lifecycle == "retired":
        for lane in lanes.values():
            lane["status"] = "rejected"
            for relation in lane["relations"].values():
                relation.update(status="rejected", gaps=sorted(set(relation["gaps"] + ["asset_retired"])))
    return {"schema_version": 1, "asset_id": asset["asset_id"], "asset_generation": asset_generation,
            "lifecycle_status": lifecycle, "qualification_status": _aggregate([r["status"] for r in lanes.values()]),
            "evidence_set_digest": digest(sorted(receipts, key=canonical_json_bytes)) if receipts else None,
            "lanes": lanes}


def load_receipts(library_root):
    path = Path(library_root) / RECEIPTS_PATH
    if not path.exists() and not path.is_symlink():
        return []
    try:
        payload = json.loads(read_evidence_bytes(library_root, RECEIPTS_PATH))
        if not isinstance(payload, dict) or not isinstance(payload.get("receipts"), list):
            raise QualificationError("evidence_manifest_invalid")
        return payload["receipts"]
    except (ValueError, OSError) as exc:
        raise QualificationError("evidence_manifest_invalid") from exc


def asset_generation(library_root):
    """无 evidence 的输入代：协议、位置/治理规则、策略和全部 canonical 字节。"""
    root = Path(library_root)
    paths = [root / "library.json"]
    for subtree in ("canonical", "governance/schemas", "governance/rules", "governance/vocabularies"):
        paths.extend(path for path in sorted((root / subtree).rglob("*")) if not path.is_dir() or path.is_symlink())
    sources = {path.relative_to(root).as_posix(): file_reference(root, path.relative_to(root).as_posix())["sha256"] for path in paths}
    return digest({"policy": POLICY, "sources": sources})


def layout_capability_contract(layout_entity, *, resolver, lane=None, proposal=None):
    """只从现有 structure/slots/输入/双向 renderer 引用提取待验证能力。"""
    profile = proposal["profile"] if proposal else layout_entity["data"]
    structure = profile.get("structure") or {}
    encodings = {entry.get("kind") for entry in structure.get("encodings", [])}
    group_relations = {entry.get("relation") for entry in structure.get("groups", [])}
    relations = set()
    if structure.get("reading_order") and "group" in group_relations:
        relations.add("independent")
    if encodings & {"comparison", "table"} or "contrast" in group_relations:
        relations.add("comparison")
    if "sequence" in encodings or "sequence" in group_relations:
        relations.add("process")
    if "chart-svg" in encodings:
        relations.update(("trend", "comparison"))
    if "time-series" in encodings:
        relations.add("trend")
    if "directed-graph" in encodings or "causal" in group_relations:
        relations.add("causal")
    lanes = [lane for lane, value in (profile.get("renderer_support") or {}).items()
             if lane in {"render:html", "image"} and isinstance(value, str) and value.strip()]
    if lane is not None:
        lanes = [item for item in lanes if item == lane]
    gaps = {lane: [] for lane in lanes}
    dependencies = {}
    entities = [layout_entity]
    root = Path(layout_entity["trusted_root"])
    for lane in lanes:
        if not structure.get("reading_order") or not profile.get("slots"):
            gaps[lane].append("owner_structure_missing")
        if lane == "render:html":
            try:
                template = resolver.resolve(profile["renderer_support"][lane])
                entities.append(template)
                data = template["data"]
                if profile["asset_id"] not in data.get("layout_profiles", []) or data.get("lane") != lane:
                    gaps[lane].append("lane_dependency_mismatch")
                from .template_inputs import slot_input_path_errors
                slot_errors = slot_input_path_errors(data, profile)
                if slot_errors:
                    gaps[lane].extend(["lane_slot_closure_missing", *slot_errors])
            except ValueError:
                gaps[lane].append("lane_dependency_missing")
        else:
            # image 的构图说明不能充当有 identity 和版本的 recipe。
            recipe_ref = profile.get("image_recipe")
            if not recipe_ref:
                gaps[lane].append("image_recipe_missing")
            else:
                try:
                    recipe = resolver.resolve(recipe_ref)
                    entities.append(recipe)
                    if recipe["data"].get("lane") != lane:
                        gaps[lane].append("lane_dependency_mismatch")
                    from .image_deck.recipe import validate_recipe
                    validate_recipe(recipe["data"], profile)
                except ValueError as exc:
                    gaps[lane].extend(["lane_dependency_missing", str(exc)])
    for entity in entities:
        path = Path(entity["path"])
        if not path.is_absolute():
            path = root / path
        try:
            for child in sorted(path.parent.iterdir()):
                if child.is_file() or child.is_symlink():
                    relative = child.relative_to(root).as_posix()
                    dependencies[relative] = file_reference(root, relative)["sha256"]
        except (ValueError, OSError) as exc:
            raise QualificationError("owner_root_or_file_invalid") from exc
    lifecycle = profile.get("lifecycle_status", "unknown")
    if proposal is not None:
        from .task_local_layout_proposals import proposal_reference
        relative = proposal_reference(proposal)
        if json.loads(read_evidence_bytes(root, relative)) != proposal:
            raise QualificationError("proposal_evidence_snapshot_mismatch")
        dependencies[relative] = file_reference(root, relative)["sha256"]
    return {"asset_id": profile["asset_id"], "lifecycle_status": lifecycle,
            "lanes": sorted(lanes), "relations": sorted(relations), "gaps": gaps}, dependencies


def qualify_layout(layout_entity, *, resolver, relation, lane, proposal=None):
    root = layout_entity["trusted_root"]
    contract, dependencies = layout_capability_contract(layout_entity, resolver=resolver, lane=lane, proposal=proposal)
    if relation not in contract["relations"] or lane not in contract["lanes"]:
        return {"status": "rejected", "gaps": ["relation_lane_not_declared"], "probe_receipts": []}
    generation = asset_generation(root)
    if proposal:
        from .task_local_layout_proposals import proposal_probe_output
        path = proposal_probe_output(proposal) + "/capability-receipts.json"
        try:
            available = json.loads(read_evidence_bytes(root, path))["receipts"]
        except (ValueError, OSError, KeyError) as exc:
            raise QualificationError("proposal_evidence_missing") from exc
    else:
        available = load_receipts(root)
    receipts = [r for r in available if r.get("asset_id") == contract["asset_id"]
                and r.get("lane") == lane and r.get("relation") == relation]
    result = derive_qualification(contract, asset_generation=generation, library_root=root,
        expected_dependencies=dependencies, environment=environment_fingerprint(), evidence_receipts=receipts)
    selected = result["lanes"][lane]["relations"][relation]
    closure = evidence_closure(root, receipts) if selected["status"] in {"provisional", "publication-qualified"} else []
    return {**result["lanes"][lane]["relations"][relation],
            "asset_generation": generation, "evidence_set_digest": result["evidence_set_digest"],
            "receipt_payloads": receipts, "evidence_files": closure}


def evidence_closure(root, receipts):
    """receipt、oracle、输入、产物与原始观测的封闭文件集合。"""
    refs = {}

    def include(reference):
        if reference is None:
            return None
        path = reference["path"]
        body = verify_reference(root, reference)
        normalized = {"path": path, "sha256": reference["sha256"]}
        if path in refs and refs[path] != normalized:
            raise QualificationError("evidence_reference_conflict")
        refs[path] = normalized
        return body

    for receipt in receipts:
        for path, sha in receipt["dependency_hashes"].items():
            if path.startswith("evidence/proposals/"):
                include({"path": path, "sha256": sha})
        for key in ("oracle", "environment", "visual_review"):
            include(receipt.get(key))
        if receipt.get("visual_review"):
            review = json.loads(verify_reference(root, receipt["visual_review"]))
            if review.get("u6a"):
                from .quality_replay import capability_publication_files
                for reference in capability_publication_files(root, review["u6a"]):
                    include(reference)
        for probe in receipt["probes"].values():
            for key in ("fixture", "artifact"):
                include(probe.get(key))
            if probe.get("provider_receipt"):
                provider = json.loads(include(probe["provider_receipt"]))
                prefix = PurePosixPath(probe["provider_receipt"]["path"]).parent
                for key in ("artifact", "provider_image", "response", "request"):
                    if provider.get(key):
                        reference = provider[key]
                        include({**reference, "path": (prefix / reference["path"]).as_posix()})
            observation = json.loads(include(probe["observation"]))
            for key in ("measurement", "render_input", "raster_review"):
                include(observation.get(key))
    return [refs[path] for path in sorted(refs)]


def freeze_qualification_evidence(qualification, *, source_root, target_root):
    """只复制绑定中已经核验的证据；缺文件或同路径不同字节均拒绝。"""
    if not qualification.get("receipt_payloads") or not qualification.get("evidence_files"):
        raise QualificationError("binding_qualification_evidence_missing")
    refs = evidence_closure(source_root, qualification["receipt_payloads"])
    if refs != qualification["evidence_files"]:
        raise QualificationError("binding_qualification_evidence_changed")
    from .storage import atomic_write_bytes
    for reference in refs:
        target = Path(target_root) / reference["path"]
        if any(p.is_symlink() for p in [target, *target.parents]):
            raise QualificationError("evidence_path_invalid")
        body = verify_reference(source_root, reference)
        if target.exists():
            verify_reference(target_root, reference)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(target, body)


def verify_bound_qualification(qualification, *, layout_entity, resolver, relation, lane, purpose, proposal=None,
                               provider_contract_sha256=None):
    """冻结后只依赖当前执行资产与封存证据；不重新发现共享库或重新选型。"""
    receipts = qualification.get("receipt_payloads")
    if not receipts or not qualification.get("evidence_files"):
        raise QualificationError("binding_qualification_evidence_missing")
    root = layout_entity["trusted_root"]
    if lane == "image":
        verify_provider_qualification(qualification, library_root=root, contract_sha256=provider_contract_sha256)
    if evidence_closure(root, receipts) != qualification["evidence_files"]:
        raise QualificationError("binding_qualification_evidence_changed")
    contract, dependencies = layout_capability_contract(layout_entity, resolver=resolver, lane=lane, proposal=proposal)
    result = derive_qualification(contract, asset_generation=qualification["asset_generation"],
        library_root=root, expected_dependencies=dependencies, environment=environment_fingerprint(), evidence_receipts=receipts)
    selected = result["lanes"].get(lane, {}).get("relations", {}).get(relation, {})
    if (result["evidence_set_digest"] != qualification["evidence_set_digest"]
            or selected != {key: qualification[key] for key in ("status", "probe_receipts", "gaps", "evidence_set_digest")}
            or not qualification_admits({**selected, "evidence_set_digest": result["evidence_set_digest"]}, purpose=purpose)):
        raise QualificationError("binding_qualification_stale")
