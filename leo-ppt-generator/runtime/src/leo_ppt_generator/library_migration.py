"""模板迁移的文件事务与收据校验；所有路径显式相对交付根或证据根。"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile

from .qualification import digest, file_reference, read_evidence_bytes, verify_reference
from .storage import atomic_write_json, json_document_bytes

RECEIPT_KIND = "template-library-migration-receipt"
PLAN_KIND = "template-library-migration-plan"
CURRENT = "leo-ppt-generator/template-library/catalog/current.json"
PUBLICATION_IDENTITY = ("transaction_id", "base_revision", "plan_digest")
STRUCTURAL_GATES = {"asset-bytes", "identity-reference", "probe", "v2-catalog", "consumer-closure", "bundle", "manifest-hashes"}
CLOSURE_ROOTS = ("leo-ppt-generator/runtime/src", "leo-ppt-generator/scripts", "leo-ppt-generator/tests",
    "leo-ppt-generator/evals", "leo-ppt-generator/SKILL.md", "leo-ppt-generator/references",
    "leo-ppt-generator/prompts", "docs/plans", "docs/prd", "docs/leo-ppt-generator", "CHANGELOG.md")
CLOSURE_FILES = {"leo-ppt-generator/SKILL.md", "CHANGELOG.md"}
LEGACY_SIGNATURES = (
    r"references/styles", r"canonical/(?:styles|themes|brands|fonts|ornaments|layouts|templates|components|axes|presets)(?=[/\s\"']|$)",
    r"[\"']canonical[\"']\s*/\s*[\"'](?:styles|themes|brands|fonts|ornaments|layouts|templates|components|axes|presets)[\"']",
    r"(?:asset_resolver|template-registry|page-type-regime)[/-]v1", r"qa-profile", r"retired-styles-tree")
LEGACY_FOLDERS = {"styles": "visual/styles", "themes": "visual/themes", "brands": "visual/brands",
    "fonts": "visual/fonts", "ornaments": "visual/ornaments", "layouts": "executable/layouts",
    "templates": "executable/templates", "components": "executable/components", "presets": "collections/presets"}
AXIS_FOLDERS = {"argument": "semantic/argument-modes", "page-semantics": "semantic/page-types",
    "chart": "semantic/guides/chart", "infographic": "semantic/guides/infographic",
    "structure": "executable/layouts/guides", "rendering": "executable/renderers/guides"}


class MigrationError(ValueError):
    pass


def scan_consumer_closure(root):
    """固定 roots 的逐命中账本；旧迁移输入与历史证据不冒充活动消费者。"""
    root = Path(root).absolute()
    hits, roots = [], []
    migration_owners = {"leo-ppt-generator/scripts/migrate_template_library.py",
                        "leo-ppt-generator/runtime/src/leo_ppt_generator/library_migration.py"}
    for relative in CLOSURE_ROOTS:
        base = safe_path(root, relative)
        roots.append({"path": relative, "exists": base.is_file() if relative in CLOSURE_FILES else base.is_dir()})
        paths = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
        for path in paths:
            if path.is_symlink():
                raise MigrationError("migration_closure_symlink:" + path.relative_to(root).as_posix())
            if not path.is_file() or path.suffix.lower() not in {".py", ".json", ".md", ".txt", ".yaml", ".yml", ".sh", ".js", ".html", ".toml"}:
                continue
            name = path.relative_to(root).as_posix()
            body = read_evidence_bytes(root, name).decode("utf-8")
            classification, disposition = "active-consumer", "migrate"
            if name in migration_owners:
                classification, disposition = "migration-input", "retain-migration-only"
            elif name == "CHANGELOG.md":
                classification, disposition = "provenance", "retain-changelog-history"
            elif name.startswith(("docs/plans/", "docs/prd/")):
                classification, disposition = "plan-control", "retain-control"
            elif "/evidence/" in name or "/reviews/" in name:
                classification, disposition = "provenance", "retain-read-only"
            elif name.startswith("leo-ppt-generator/tests/test_migration"):
                classification, disposition = "test-fixture", "retain-negative-contract"
            elif name.startswith("docs/leo-ppt-generator/") and path.suffix == ".md":
                # 只读历史记录仍进入逐命中账本；不能按旧日期把活动指引一概排除。
                if (body.startswith("---\n") and re.search(r"(?m)^status: historical-reference$", body.split("\n---", 1)[0])):
                    classification, disposition = "provenance", "retain-explicit-historical-reference"
                elif name.startswith("docs/leo-ppt-generator/tech-plans/") and "性质：技术方案（HOW）" in body:
                    classification, disposition = "plan-control", "retain-tech-plan-requiring-spec-plan"
                elif name.startswith("docs/leo-ppt-generator/evals/") and re.match(r"# .+测试报告[（(]\d{4}-\d{2}-\d{2}[）)]", body):
                    classification, disposition = "provenance", "retain-dated-evaluation-report"
                elif (name == "docs/leo-ppt-generator/template-rebuild-baseline.md"
                      and "本文是 U1 的冻结记录与摘要" in body):
                    classification, disposition = "provenance", "retain-frozen-baseline-record"
                elif (name == "docs/leo-ppt-generator/template-rebuild-verification.md"
                      and re.search(r"本登记截至 \d{4}-\d{2}-\d{2} 本实施批", body)):
                    classification, disposition = "provenance", "retain-bounded-verification-record"
            for signature in LEGACY_SIGNATURES:
                for match in re.finditer(signature, body):
                    hits.append({"path": name, "line": body.count("\n", 0, match.start()) + 1,
                        "signature": match.group(), "classification": classification,
                        "owner": name, "disposition": disposition})
    hits.sort(key=lambda row: (row["path"], row["line"], row["signature"]))
    return {"roots": roots, "signatures": list(LEGACY_SIGNATURES), "hits": hits,
        "unclassified_hits": sum(not row["classification"] for row in hits),
        "active_legacy_hits": sum(row["disposition"] == "migrate" for row in hits)}


def verify_consumer_closure(root):
    """零命中须覆盖十个消费者根及强制 CHANGELOG 文件，且类型全部正确。"""
    closure = scan_consumer_closure(root)
    missing = [row["path"] for row in closure["roots"] if not row["exists"]]
    if missing:
        raise MigrationError("migration_closure_roots_incomplete:" + ",".join(missing))
    if closure["active_legacy_hits"] or closure["unclassified_hits"]:
        raise MigrationError("migration_consumer_closure_not_zero:" + str(closure["active_legacy_hits"]))
    return closure


def mapped_library_path(relative):
    parts = PurePosixPath(relative).parts
    if relative == "canonical/templates/README.md":
        return "governance/authoring/templates.md"
    if relative == "canonical/layouts/manifest.json":
        return "governance/migration/provenance/layout-manifest-v1.json"
    if relative == "canonical/components/chart-palettes/pool.json":
        return "reference/pools/chart-palettes/pool.json"
    if relative.startswith("canonical/presets/scene-presets/"):
        return "reference/sources/scene-presets/" + relative.removeprefix("canonical/presets/scene-presets/")
    if len(parts) > 2 and parts[0] == "canonical":
        if parts[1] == "axes":
            if len(parts) < 5 or parts[2] not in AXIS_FOLDERS:
                raise MigrationError("migration_unknown_axis_path:" + relative)
            return "canonical/" + AXIS_FOLDERS[parts[2]] + "/" + "/".join(parts[3:])
        if parts[1] in LEGACY_FOLDERS:
            return "canonical/" + LEGACY_FOLDERS[parts[1]] + "/" + "/".join(parts[2:])
        if parts[1] not in {"semantic", "visual", "executable", "collections"}:
            raise MigrationError("migration_unknown_canonical_path:" + relative)
    return relative


def transformed_library_bytes(relative, body):
    if relative != "library.json":
        return body
    from .storage import canonical_json_bytes
    declaration = json.loads(body)
    declaration["schema_version"] = 2
    declaration["protocol"].update(resolver="asset_resolver/v2", builder="capability_manifest/template-registry/v2")
    from .asset_resolver import ASSET_ID_RE
    declaration["protocol"]["asset_id_pattern"] = ASSET_ID_RE.pattern
    return canonical_json_bytes(declaration)


def materialize_shadow_library(source, target):
    """仅供 stage 的字节转换器；不授予 stage/发布资格，不改来源库。"""
    source, target = Path(source).absolute(), Path(target).absolute()
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise MigrationError("migration_shadow_not_isolated")
    if target.exists() and any(target.iterdir()):
        raise MigrationError("migration_shadow_not_empty")
    target.mkdir(parents=True, exist_ok=True)
    mapping, seen = [], set()
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source).as_posix()
        if path.is_symlink():
            raise MigrationError("migration_symlink_rejected:" + relative)
        if not path.is_file() or relative.startswith("catalog/") or path.name.startswith(".maintenance"):
            continue
        destination = mapped_library_path(relative)
        if destination in seen:
            raise MigrationError("migration_target_collision:" + destination)
        seen.add(destination)
        before = file_state(source, relative)
        body = transformed_library_bytes(relative, read_evidence_bytes(source, relative))
        if file_state(source, relative) != before:
            raise MigrationError("migration_source_drift:" + relative)
        out = safe_path(target, destination)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("xb") as handle:
            handle.write(body)
            os.fchmod(handle.fileno(), before["mode"])
        mapping.append({"source": relative, "target": destination, "source_state": before,
                        "target_state": file_state(target, destination)})
    return mapping


def git_state(root):
    root = Path(root).absolute()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    raw = subprocess.check_output(["git", "status", "--porcelain=v1", "--no-renames", "-z", "--untracked-files=all"], cwd=root).decode()
    dirty = {}
    for entry in raw.split("\0"):
        if entry:
            path = entry[3:]
            if path in {"leo-ppt-generator/template-library/.maintenance.json", "leo-ppt-generator/template-library/.maintenance.lock"}:
                continue
            dirty[path] = {"status": entry[:2], "state": file_state(root, path)}
    return {"head": head, "dirty": dirty}


def _check_source(plan):
    state = git_state(plan["source_root"])
    if state["head"] != plan["base_revision"] or state["dirty"] != plan["dirty_snapshot"]:
        raise MigrationError("migration_delivery_head_or_dirty_drift")
    for path, expected in plan["source_snapshot"].items():
        if file_state(plan["source_root"], path) != expected:
            raise MigrationError("migration_source_drift:" + path)
    expected_paths = {path for path, row in plan["source_snapshot"].items() if row["type"] == "file"}
    if _migration_file_paths(plan["source_root"]) != expected_paths:
        raise MigrationError("migration_source_file_set_drift")


def _migration_file_paths(root):
    """与 preview 相同的完整交付集合；库内附属字节不能由 gitignore 隐藏。"""
    root = Path(root).absolute()
    listed = subprocess.check_output(["git", "ls-files", "-c", "-o", "--exclude-standard", "-z",
        "--", "leo-ppt-generator", "CHANGELOG.md"], cwd=root).decode().split("\0")
    candidates = {path for path in listed if path}
    library = safe_path(root, "leo-ppt-generator/template-library")
    if library.exists():
        for path in library.rglob("*"):
            if path.is_symlink() or not path.is_dir():
                candidates.add(path.relative_to(root).as_posix())
    candidates -= {"leo-ppt-generator/template-library/.maintenance.json",
                   "leo-ppt-generator/template-library/.maintenance.lock"}
    return {path for path in candidates if file_state(root, path)["type"] != "absent"}


def _check_work_root(source, work):
    source, work = Path(source).absolute(), Path(work).absolute()
    if any(path.is_symlink() for path in (work, *work.parents)):
        raise MigrationError("migration_work_root_symlink")
    if work == source:
        raise MigrationError("migration_work_root_is_delivery")
    if work.is_relative_to(source):
        result = subprocess.run(["git", "check-ignore", "-q", "--no-index", str(work.relative_to(source)) + "/"], cwd=source)
        if result.returncode:
            raise MigrationError("migration_work_root_must_be_ignored")
    return work


def _write_sealed(path, body, field="receipt_digest"):
    body = {key: value for key, value in body.items() if key != field}
    body[field] = digest(body)
    if path.exists():
        if json.loads(read_evidence_bytes(path.parent, path.name)) != body:
            raise MigrationError("migration_immutable_artifact_conflict:" + path.name)
    else:
        atomic_write_json(path, body)
        fsync_directory(path.parent)
    return body


def verify_value_gate(root, reference):
    """预迁移门必须引用真实双 lane 导出及旧链；缺失不会降级为成功。"""
    from .quality_replay import verify_legacy_baseline
    from .application.expression_pipeline import load_committed_input
    from .quality_metrics import deck_quality_for_run
    value = sealed(load_document(root, reference), "receipt_digest")
    if value.get("kind") != "expression-pre-migration-value" or value.get("status") != "passed":
        raise MigrationError("migration_pre_value_gate_missing")
    verify_legacy_baseline(root, value["baseline"])
    relations, joins = {}, set()
    for row in value["cases"]:
        run = safe_path(root, row["run"])
        committed = load_committed_input(run)
        page = next(page for page in committed["payload"]["pack"]["pages"] if page["page_id"] == row["page_id"])
        quality = deck_quality_for_run(run, include_visual=False)
        if any(status != "passed" for status in quality["channels"].values()):
            raise MigrationError("migration_pre_value_export_failed")
        exported = quality["lanes"][row["lane"]]["pages"][row["page_id"]]
        actual = file_reference(root, (run / exported["artifact"]).relative_to(root).as_posix())
        if row["artifact"] != actual or exported["status"] != "passed" or row["relation"] != page["expression"]["relation"]["kind"]:
            raise MigrationError("migration_pre_value_artifact_mismatch")
        review = load_document(root, row["review"])
        if (review.get("artifact") != actual or not review.get("reviewer") or not review.get("rationale")
                or review.get("severe_defects") != 0 or review.get("relation_verified") is not True):
            raise MigrationError("migration_pre_value_review_missing")
        identity = (row["run"], row["page_id"], row["lane"])
        if identity in joins:
            raise MigrationError("migration_pre_value_duplicate_page")
        joins.add(identity)
        relations.setdefault(row["relation"], set()).add(row["lane"])
    if len([lanes for lanes in relations.values() if lanes == {"image", "render:html"}]) < 3:
        raise MigrationError("migration_pre_value_dual_lane_incomplete")
    return value


def preview_migration(source_root, out_plan, *, prerequisite=None):
    """只写唯一计划；临时转换用来计算真实目标 hash，不触碰 delivery。"""
    import base64
    from .template_catalog import build_catalog
    from .storage import canonical_json_bytes
    source = Path(source_root).absolute()
    out = Path(out_plan).absolute()
    work = _check_work_root(source, out.parent)
    if out.name != "migration-plan.json":
        raise MigrationError("migration_unique_plan_name_required")
    state = git_state(source)
    library = source / "leo-ppt-generator/template-library"
    paths = _migration_file_paths(source)
    descriptors = {}
    with tempfile.TemporaryDirectory(prefix="leo-migration-preview-") as temporary:
        target = Path(temporary).resolve() / "library"
        rows = materialize_shadow_library(library, target)
        for row in rows:
            before, after = "leo-ppt-generator/template-library/" + row["source"], "leo-ppt-generator/template-library/" + row["target"]
            descriptors[after] = {"operation": "normalize" if row["source"] == "library.json" else "copy",
                "source": before, "source_relative_to_library": row["source"], "sha256": row["target_state"]["sha256"],
                "mode": row["target_state"]["mode"]}
            paths.add(before)
        outputs = build_catalog(target)
        generation = outputs["registry.json"]["catalog_generation"]
        catalog = {"catalog/generations/" + generation + "/" + path: value for path, value in outputs.items()}
        catalog["catalog/current.json"] = {"kind": "template-catalog-pointer", "schema_version": 2, "generation": generation}
        for path, body in catalog.items():
            raw = canonical_json_bytes(body)
            descriptors["leo-ppt-generator/template-library/" + path] = {"operation": "derived", "sha256": hashlib.sha256(raw).hexdigest(),
                "mode": 0o644, "payload": base64.b64encode(raw).decode()}
    for path in sorted(paths):
        if not path.startswith("leo-ppt-generator/template-library/"):
            before = file_state(source, path)
            descriptors[path] = {"operation": "copy", "source": path, "sha256": before["sha256"], "mode": before["mode"]}
    touched = paths | set(descriptors)
    snapshot = {path: file_state(source, path) for path in sorted(touched)}
    deletes = [{"path": path, "expected": snapshot[path], "after_publish": snapshot[path], "already_absent": "only-after-journaled-delete"}
               for path in sorted(paths - set(descriptors)) if snapshot[path]["type"] == "file"]
    gap = "migration_pre_value_gate_missing"
    if prerequisite is not None:
        verify_value_gate(work, prerequisite)
        gap = None
    closure = scan_consumer_closure(source)
    plan = {"schema_version": 2, "kind": PLAN_KIND, "phase": "preview", "gate": "U7-A" if gap else "U7-B",
        "source_root": str(source), "base_revision": state["head"], "dirty_snapshot": state["dirty"],
        "source_snapshot": snapshot, "closure": closure, "mapping": descriptors,
        "target_hashes": {path: row["sha256"] for path, row in sorted(descriptors.items())},
        "delete_allowlist": deletes, "allowlist_digest": digest(deletes), "prerequisite": prerequisite,
        "gaps": [gap] if gap else [], "owner_sha256": file_reference(Path(__file__).parent, Path(__file__).name)["sha256"]}
    if git_state(source) != state or any(file_state(source, path) != before for path, before in snapshot.items()):
        raise MigrationError("migration_source_changed_during_preview")
    plan["plan_digest"] = digest(plan)
    validate_plan_contract(plan)
    return _write_sealed(out, plan, "plan_digest")


def _target_bytes(plan, path):
    import base64
    row = plan["mapping"][path]
    if row["operation"] == "derived":
        body = base64.b64decode(row["payload"], validate=True)
    elif row["operation"] in {"copy", "normalize"}:
        body = read_evidence_bytes(plan["source_root"], row["source"])
        if row["operation"] == "normalize":
            body = transformed_library_bytes(row["source_relative_to_library"], body)
    else:
        raise MigrationError("migration_operation_invalid")
    if hashlib.sha256(body).hexdigest() != plan["target_hashes"][path]:
        raise MigrationError("migration_target_hash_mismatch:" + path)
    return body


def stage_migration(plan_path, staging_root, *, checkpoint=None):
    """完整独立 worktree 只接收执行快照；有外部 dirty 的 shadow 不可覆盖。"""
    plan_path = Path(plan_path).absolute()
    work = plan_path.parent
    plan_ref = file_reference(work, plan_path.name)
    plan = validate_plan(load_document(work, plan_ref))
    verify_value_gate(work, plan["prerequisite"])
    if plan["owner_sha256"] != file_reference(Path(__file__).parent, Path(__file__).name)["sha256"]:
        raise MigrationError("migration_owner_changed")
    _check_source(plan)
    staging = _check_work_root(plan["source_root"], staging_root)
    if staging == Path(plan["source_root"]) or Path(plan["source_root"]).is_relative_to(staging):
        raise MigrationError("migration_shadow_not_isolated")
    state_path = work / "stage-journal.json"
    if not (staging / ".git").exists():
        if staging.exists() and any(staging.iterdir()):
            raise MigrationError("migration_shadow_not_empty")
        subprocess.run(["git", "worktree", "add", "--detach", str(staging), plan["base_revision"]], cwd=plan["source_root"], check=True, capture_output=True)
    top = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=staging, text=True).strip()
    if Path(top).absolute() != staging:
        raise MigrationError("migration_shadow_not_worktree")
    if state_path.exists():
        journal = sealed(json.loads(read_evidence_bytes(work, state_path.name)), "journal_digest")
        if journal["plan_digest"] != plan["plan_digest"] or journal["staging_root"] != str(staging):
            raise MigrationError("migration_stage_journal_conflict")
    else:
        state = git_state(staging)
        if state["head"] != plan["base_revision"] or state["dirty"]:
            raise MigrationError("migration_shadow_dirty")
        journal = {"phase": "stage", "plan_digest": plan["plan_digest"], "staging_root": str(staging), "files": {},
            "before": {path: file_state(staging, path) for path in plan["source_snapshot"]}}
    if set(git_state(staging)["dirty"]) - set(plan["source_snapshot"]):
        raise MigrationError("migration_shadow_foreign_dirty")
    for path in sorted(plan["target_hashes"], key=lambda name: (name == CURRENT, name)):
        row = plan["mapping"][path]
        desired = {"type": "file", "sha256": row["sha256"], "mode": row["mode"]}
        actual = file_state(staging, path)
        if journal.get("pending") == {"path": path, "state": desired} and actual == desired:
            journal["files"][path] = desired
        if path in journal["files"]:
            if actual != desired:
                raise MigrationError("migration_stage_external_drift:" + path)
            continue
        if actual != journal["before"][path]:
            raise MigrationError("migration_stage_external_drift:" + path)
        journal["pending"] = {"path": path, "state": desired}
        journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
        atomic_write_json(state_path, journal)
        compare_and_swap_file(staging, path, expected=actual, body=_target_bytes(plan, path), mode=row["mode"], checkpoint=checkpoint)
        journal["files"][path] = desired
        journal.pop("pending", None)
        journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
        atomic_write_json(state_path, journal)
    for row in plan["delete_allowlist"]:
        path = row["path"]
        actual = file_state(staging, path)
        absent = {"type": "absent", "sha256": None, "mode": None}
        if journal.get("pending") == {"path": path, "state": absent} and actual == absent:
            journal["files"][path] = absent
        if actual["type"] == "absent" and journal["files"].get(path, {}).get("type") == "absent":
            continue
        if actual != journal["before"][path]:
            raise MigrationError("migration_stage_delete_drift:" + path)
        journal["pending"] = {"path": path, "state": absent}
        journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
        atomic_write_json(state_path, journal)
        if actual["type"] == "file":
            _unlink_cas(staging, path, actual, checkpoint=checkpoint)
        journal["files"][path] = {"type": "absent", "sha256": None, "mode": None}
        journal.pop("pending", None)
        journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
        atomic_write_json(state_path, journal)
    _check_source(plan)
    return _write_sealed(work / "stage-receipt.json", {"schema_version": 2, "kind": RECEIPT_KIND,
        "phase": "stage", "status": "passed", "plan": plan_ref, "plan_digest": plan["plan_digest"],
        "staging_root": str(staging), "staging_hashes": _staged_hashes(plan, staging),
        "journal": file_reference(work, state_path.name)})


def _staged_hashes(plan, staging):
    for row in plan["delete_allowlist"]:
        if file_state(staging, row["path"])["type"] != "absent":
            raise MigrationError("migration_staging_legacy_file_remains:" + row["path"])
    return _converged_hashes(plan, staging)


def _converged_hashes(plan, root):
    actual_paths = _migration_file_paths(root)
    expected_paths = set(plan["target_hashes"])
    if actual_paths != expected_paths:
        raise MigrationError("migration_convergence_file_set_mismatch:" + json.dumps({
            "extra": sorted(actual_paths - expected_paths), "missing": sorted(expected_paths - actual_paths)}))
    hashes = {}
    for path in sorted(actual_paths):
        state = file_state(root, path)
        expected = {"type": "file", "sha256": plan["target_hashes"][path], "mode": plan["mapping"][path]["mode"]}
        if state != expected:
            raise MigrationError("migration_convergence_file_state_mismatch:" + path)
        hashes[path] = state["sha256"]
    return hashes


def verify_migration(plan_path, staging_root, out_receipt, *, visual_receipt=None):
    """结构验证与真实 U6-A 共同签发 publication-ready；缺一路保持 blocked。"""
    import uuid
    from .template_catalog import LibraryContext, read_catalog, scan_records
    from .quality_replay import evaluate_quality_replay
    work, staging = Path(plan_path).absolute().parent, Path(staging_root).absolute()
    output = Path(out_receipt).absolute()
    if output.parent != work:
        raise MigrationError("migration_receipt_root_mismatch")
    plan_ref = file_reference(work, Path(plan_path).name)
    plan = validate_plan(load_document(work, plan_ref))
    staged_ref = file_reference(work, "stage-receipt.json")
    stage = receipt_document(work, staged_ref, "stage", plan_digest=plan["plan_digest"])
    if stage["staging_root"] != str(staging) or stage["plan"] != plan_ref:
        raise MigrationError("migration_stage_receipt_mismatch")
    _check_source(plan)
    attempt = work / "verify-attempts" / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    checks, gaps = {}, []
    hashes = None

    def check(name, action):
        try:
            details = action()
            evidence = {"status": "passed", "details": details}
        except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
            evidence = {"status": "failed", "reason": str(exc)}
            gaps.append(name + ":" + str(exc))
        evidence.update(plan_digest=plan["plan_digest"], gate=name, inputs_digest=digest(plan["target_hashes"]))
        path = attempt / (name + ".json")
        atomic_write_json(path, evidence)
        checks[name] = {"status": evidence["status"], "evidence": file_reference(work, path.relative_to(work).as_posix())}
        return evidence

    library = staging / "leo-ppt-generator/template-library"
    check("asset-bytes", lambda: {"files": _staged_hashes(plan, staging)})
    check("identity-reference", lambda: {"records": scan_records(library)})
    check("v2-catalog", lambda: {"catalog_generation": read_catalog(LibraryContext(library))["catalog_generation"]})

    def probe():
        registry = read_catalog(LibraryContext(library))
        prefix = "catalog/generations/" + registry["catalog_generation"] + "/"
        view = json.loads(read_evidence_bytes(library, prefix + "views/execution-pairings.json"))
        if not view["candidates"] or {row["identity"]["lane"] for row in view["candidates"]} != {"render:html", "image"}:
            raise MigrationError("migration_real_probe_qualification_incomplete")
        return view

    check("probe", probe)

    check("consumer-closure", lambda: verify_consumer_closure(staging))

    def bundle_check():
        package = staging / "leo-ppt-generator"
        command = [str(Path(plan["source_root"]) / "leo-ppt-generator/runtime/.venv/bin/python"), "-m", "unittest", "tests.test_library_bundle"]
        log = attempt / "bundle.log"
        with log.open("wb") as handle:
            process = subprocess.run(command, cwd=package, env=dict(os.environ, PYTHONPATH="runtime/src", LEO_PPT_BUNDLE=str(package)),
                                     stdout=handle, stderr=subprocess.STDOUT)
        text = log.read_text()
        if process.returncode != 0 or not re.search(r"Ran [1-9][0-9]* tests", text) or not re.search(r"^OK(?:\s|$)", text, re.M):
            raise MigrationError("migration_bundle_validation_failed:" + str(process.returncode))
        return {"command": command, "exit_code": process.returncode, "log": file_reference(work, log.relative_to(work).as_posix())}

    check("bundle", bundle_check)
    check("manifest-hashes", lambda: {"files": _staged_hashes(plan, staging), "catalog": verify_catalog_files(library)})
    visual_status = "blocked"
    if visual_receipt is None:
        gaps.append("migration_u6a_receipt_missing")
    else:
        visual = sealed(load_document(work, visual_receipt), "receipt_digest")
        live = evaluate_quality_replay(work, visual["plan"])
        if (visual == live and live["status"] == "passed" and live["phase"] == "U6-A" and live["publication_ready"]):
            visual_status = "passed"
        else:
            gaps.append("migration_u6a_not_passed_or_stale")
    hashes = _staged_hashes(plan, staging)
    result = {"schema_version": 2, "kind": RECEIPT_KIND, "phase": "verify", "status": "passed" if not gaps else "blocked",
        "publication_ready": not gaps, "plan": plan_ref, "plan_digest": plan["plan_digest"], "stage": staged_ref,
        "staging_root": str(staging), "staging_hashes": hashes, "checks": checks,
        "visual_receipt": visual_receipt, "visual_status": visual_status, "gaps": gaps}
    return _write_sealed(output, result)


def _verified_for_publication(work, plan_ref, verified_ref):
    from .quality_replay import evaluate_quality_replay
    from .template_catalog import LibraryContext, read_catalog
    plan = validate_plan(load_document(work, plan_ref))
    if plan["owner_sha256"] != file_reference(Path(__file__).parent, Path(__file__).name)["sha256"]:
        raise MigrationError("migration_owner_changed")
    verify_value_gate(work, plan["prerequisite"])
    receipt = receipt_document(work, verified_ref, "verify", plan_digest=plan["plan_digest"])
    if (receipt.get("plan") != plan_ref or receipt.get("publication_ready") is not True
            or set(receipt.get("checks", {})) != STRUCTURAL_GATES
            or any(row["status"] != "passed" for row in receipt["checks"].values())):
        raise MigrationError("migration_publication_not_verified")
    for gate, row in receipt["checks"].items():
        evidence = load_document(work, row["evidence"])
        if (evidence.get("gate") != gate or evidence.get("status") != "passed" or evidence.get("plan_digest") != plan["plan_digest"]
                or evidence.get("inputs_digest") != digest(plan["target_hashes"])):
            raise MigrationError("migration_verification_evidence_stale")
        if gate == "bundle":
            details = evidence["details"]
            log = verify_reference(work, details["log"]).decode()
            if details["exit_code"] != 0 or not re.search(r"Ran [1-9][0-9]* tests", log) or not re.search(r"^OK(?:\s|$)", log, re.M):
                raise MigrationError("migration_bundle_receipt_invalid")
    staging = Path(receipt["staging_root"])
    if receipt["staging_hashes"] != _staged_hashes(plan, staging):
        raise MigrationError("migration_verified_manifest_mismatch")
    verify_consumer_closure(staging)
    read_catalog(LibraryContext(staging / "leo-ppt-generator/template-library"))
    visual = sealed(load_document(work, receipt["visual_receipt"]), "receipt_digest")
    live = evaluate_quality_replay(work, visual["plan"])
    if visual != live or live["status"] != "passed" or live["phase"] != "U6-A" or not live["publication_ready"]:
        raise MigrationError("migration_u6a_not_passed_or_stale")
    return plan, receipt


def _check_untouched(plan):
    state = git_state(plan["source_root"])
    if state["head"] != plan["base_revision"]:
        raise MigrationError("migration_delivery_head_drift")
    touched = set(plan["source_snapshot"])
    outside = lambda rows: {path: value for path, value in rows.items() if path not in touched}
    if outside(state["dirty"]) != outside(plan["dirty_snapshot"]):
        raise MigrationError("migration_external_dirty_drift")


def _save_original(work, delivery, path, state):
    if state["type"] == "absent":
        return None
    backup = "backups/" + digest({"path": path, "state": state}) + ".bin"
    target = safe_path(work, backup)
    body = read_evidence_bytes(delivery, path)
    if hashlib.sha256(body).hexdigest() != state["sha256"]:
        raise MigrationError("migration_backup_source_drift:" + path)
    if target.exists():
        if read_evidence_bytes(work, backup) != body:
            raise MigrationError("migration_backup_conflict:" + path)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        fsync_directory(work)
        with target.open("xb") as handle:
            handle.write(body); handle.flush(); os.fsync(handle.fileno())
        fsync_directory(target.parent)
    return file_reference(work, backup)


def fsync_directory(path):
    """迁移持久化屏障不能把目录同步失败降级为成功。"""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_journal(path, journal):
    if journal.get("phase") == "publish":
        journal["journal_generation"] += 1
    journal["journal_digest"] = digest({key: value for key, value in journal.items() if key != "journal_digest"})
    atomic_write_json(path, journal)
    fsync_directory(path.parent)


def _publication_identity(plan):
    return {"plan_digest": plan["plan_digest"], "base_revision": plan["base_revision"],
            "transaction_id": digest({"plan": plan["plan_digest"], "base": plan["base_revision"],
                                      "delivery": str(Path(plan["source_root"]).absolute())})}


def _check_publication_journal(plan, journal):
    sealed(journal, "journal_digest")
    if (journal.get("schema_version") != 2 or journal.get("phase") != "publish"
            or any(journal.get(key) != value for key, value in _publication_identity(plan).items())
            or type(journal.get("journal_generation")) is not int or journal["journal_generation"] < 1
            or journal.get("status") not in {"running", "passed", "restoring", "restored", "blocked"}
            or not isinstance(journal.get("files"), list)):
        raise MigrationError("migration_publication_identity_mismatch")
    seen = set()
    for row in journal.get("files", []):
        if not isinstance(row, dict):
            raise MigrationError("migration_publication_journal_state_mismatch")
        path = row.get("path")
        if path in seen or path not in plan["target_hashes"]:
            raise MigrationError("migration_publication_journal_scope_mismatch")
        seen.add(path)
        expected = {"type": "file", "sha256": plan["target_hashes"][path], "mode": plan["mapping"][path]["mode"]}
        before = plan["source_snapshot"][path]
        backup = row.get("backup")
        if (row.get("before") != before or row.get("after") != expected
                or row.get("target_sha256") != expected["sha256"]
                or row.get("status") not in {"prepared", "replaced", "restored", "external-drift"}
                or (before["type"] == "absent" and backup is not None)
                or (before["type"] == "file" and (not isinstance(backup, dict) or backup != {
                    "path": "backups/" + digest({"path": path, "state": before}) + ".bin", "sha256": before["sha256"]}))):
            raise MigrationError("migration_publication_journal_state_mismatch")
    return journal


def _publication_marker(work, plan, journal, *, confirmed=False):
    path = Path(work) / "publication-marker.json"
    if not path.is_file() or path.is_symlink():
        raise MigrationError("migration_publication_marker_unconfirmed")
    marker = sealed(json.loads(read_evidence_bytes(work, path.name)), "marker_digest")
    if (marker.get("schema_version") != 2
            or any(marker.get(key) != value for key, value in _publication_identity(plan).items())
            or marker.get("state") not in {"prepared", "current-switched"}
            or type(marker.get("journal_generation")) is not int
            or not 1 <= marker["journal_generation"] <= journal["journal_generation"]):
        raise MigrationError("migration_publication_marker_unconfirmed")
    if confirmed and (marker["state"] != "current-switched"
            or marker["journal_generation"] != journal["journal_generation"]
            or marker.get("journal_digest") != journal["journal_digest"]
            or marker.get("current_sha256") != plan["target_hashes"].get(CURRENT)):
        raise MigrationError("migration_publication_marker_unconfirmed")
    return marker


def _confirm_publication(work, plan, journal, state):
    marker = {"schema_version": 2, **_publication_identity(plan), "state": state,
              "journal_generation": journal["journal_generation"], "journal_digest": journal["journal_digest"],
              "current_sha256": plan["target_hashes"][CURRENT]}
    marker["marker_digest"] = digest(marker)
    atomic_write_json(Path(work) / "publication-marker.json", marker)
    fsync_directory(work)
    return marker


def _verify_publication_confirmation(work, plan, published=None):
    journal = _check_publication_journal(plan, json.loads(read_evidence_bytes(work, "publication-progress.json")))
    if published is not None and any(published.get(key) != journal[key]
                                     for key in (*PUBLICATION_IDENTITY, "journal_generation")):
        raise MigrationError("migration_publication_receipt_stale")
    marker = _publication_marker(work, plan, journal, confirmed=True)
    if (journal["status"] != "passed" or journal.get("current_switched") is not True
            or {row["path"]: row["target_sha256"] for row in journal["files"]} != plan["target_hashes"]
            or any(row["status"] != "replaced" for row in journal["files"])):
        raise MigrationError("migration_publication_journal_incomplete")
    if published is not None:
        if (load_document(work, published["journal"]) != journal
                or load_document(work, published["marker"]) != marker):
            raise MigrationError("migration_publication_receipt_stale")
    return journal


def _recover_publication(work, plan):
    progress = Path(work) / "publication-progress.json"
    if not progress.exists():
        if (Path(work) / "publication-marker.json").exists():
            raise MigrationError("migration_publication_journal_missing")
        return 0
    journal = _check_publication_journal(plan, json.loads(read_evidence_bytes(work, progress.name)))
    _publication_marker(work, plan, journal)
    conflicts = _restore_entries(work, plan["source_root"], journal["files"])
    journal.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
    _write_journal(progress, journal)
    if conflicts:
        raise MigrationError("migration_restore_external_drift")
    return journal["journal_generation"]


def _unlink_cas(root, relative, expected, *, checkpoint=None):
    path = safe_path(root, relative)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if checkpoint:
            checkpoint("before_delete", relative)
        if file_state(root, relative) != expected:
            raise MigrationError("migration_cleanup_drift:" + relative)
        parent = os.stat(path.parent, follow_symlinks=False)
        pinned = os.fstat(fd)
        if (parent.st_dev, parent.st_ino) != (pinned.st_dev, pinned.st_ino):
            raise MigrationError("migration_parent_changed:" + relative)
        os.unlink(path.name, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)


def _restore_entries(work, delivery, entries):
    """只恢复仍等于本批目标状态的文件；外部改写留下并明确阻断。"""
    conflicts = []
    for row in reversed(entries):
        try:
            current = file_state(delivery, row["path"])
            if current == row["before"]:
                row["status"] = "restored"
                continue
            if current != row["after"]:
                raise MigrationError("migration_restore_external_drift")
            if row["before"]["type"] == "absent":
                _unlink_cas(delivery, row["path"], current)
            else:
                body = verify_reference(work, row["backup"])
                if hashlib.sha256(body).hexdigest() != row["before"]["sha256"]:
                    raise MigrationError("migration_backup_hash_mismatch")
                compare_and_swap_file(delivery, row["path"], expected=current, body=body, mode=row["before"]["mode"])
            row["status"] = "restored"
        except (ValueError, OSError) as exc:
            row["status"] = "external-drift"
            conflicts.append({"path": row["path"], "reason": str(exc)})
    return conflicts


def publish_targets(work, plan, staging, *, checkpoint=None):
    """受上层 verified gate 保护的文件事务；供真实故障注入测试单独观察。"""
    work, staging, delivery = Path(work), Path(staging), Path(plan["source_root"])
    journal_path = work / "publication-progress.json"
    if CURRENT not in plan["target_hashes"]:
        raise MigrationError("migration_current_target_missing")
    _check_untouched(plan)
    if journal_path.exists():
        old = _check_publication_journal(plan, json.loads(read_evidence_bytes(work, journal_path.name)))
        if old["status"] == "passed":
            try:
                confirmed = _verify_publication_confirmation(work, plan)
            except MigrationError as exc:
                if str(exc) != "migration_publication_marker_unconfirmed":
                    raise
            else:
                if all(file_state(delivery, row["path"]) == row["after"] for row in confirmed["files"]):
                    return confirmed
    generation = _recover_publication(work, plan)
    journal = {"schema_version": 2, "phase": "publish", **_publication_identity(plan),
               "journal_generation": generation, "status": "running", "current_switched": False, "files": []}
    _write_journal(journal_path, journal)
    _confirm_publication(work, plan, journal, "prepared")
    try:
        if checkpoint:
            checkpoint("after_prepared_marker", CURRENT)
        for path in sorted(plan["target_hashes"], key=lambda name: (name == CURRENT, name)):
            before = plan["source_snapshot"][path]
            if file_state(delivery, path) != before:
                raise MigrationError("migration_delivery_drift:" + path)
            body = read_evidence_bytes(staging, path)
            if hashlib.sha256(body).hexdigest() != plan["target_hashes"][path]:
                raise MigrationError("migration_staging_drift:" + path)
            after = {"type": "file", "sha256": plan["target_hashes"][path], "mode": plan["mapping"][path]["mode"]}
            row = {"path": path, "before": before, "after": after, "target_sha256": after["sha256"],
                   "backup": _save_original(work, delivery, path, before), "status": "prepared"}
            journal["files"].append(row)
            _write_journal(journal_path, journal)
            compare_and_swap_file(delivery, path, expected=before, body=body, mode=after["mode"], checkpoint=checkpoint)
            row["status"] = "replaced"
            journal["current_switched"] = journal["current_switched"] or path == CURRENT
            _write_journal(journal_path, journal)
            if checkpoint:
                checkpoint("after_replace", path)
        _check_untouched(plan)
        journal["status"] = "passed"
        _write_journal(journal_path, journal)
        if checkpoint:
            checkpoint("before_current_confirmation", CURRENT)
        _confirm_publication(work, plan, journal, "current-switched")
        if checkpoint:
            checkpoint("after_current_confirmation", CURRENT)
        return journal
    except BaseException:
        conflicts = _restore_entries(work, delivery, journal["files"])
        journal.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
        _write_journal(journal_path, journal)
        raise


def _seal_publication_receipt(work, plan, body, *, expected):
    """保留不可变分代凭证；根收据只以 CAS 更新到最新已确认的一代。"""
    journal = _verify_publication_confirmation(work, plan)
    marker = _publication_marker(work, plan, journal, confirmed=True)
    _check_untouched(plan)
    if any(file_state(plan["source_root"], row["path"]) != row["after"] for row in journal["files"]):
        raise MigrationError("migration_publication_delivery_drift")
    relative = "publications/" + journal["transaction_id"] + "/" + str(journal["journal_generation"])
    folder = safe_path(work, relative)
    folder.mkdir(parents=True, exist_ok=True)
    for directory in (folder, folder.parent, folder.parent.parent, Path(work)):
        fsync_directory(directory)
    _write_sealed(folder / "journal.json", journal, "journal_digest")
    _write_sealed(folder / "marker.json", marker, "marker_digest")
    result = _write_sealed(folder / "receipt.json", {**body,
        **{key: journal[key] for key in (*PUBLICATION_IDENTITY, "journal_generation")},
        "journal": file_reference(work, relative + "/journal.json"),
        "marker": file_reference(work, relative + "/marker.json")})
    compare_and_swap_file(work, "publication-receipt.json", expected=expected, body=json_document_bytes(result))
    return result


def publish_migration(plan_path, receipt_path, delivery_root, *, checkpoint=None):
    work = Path(plan_path).absolute().parent
    plan_ref = file_reference(work, Path(plan_path).name)
    receipt_ref = file_reference(work, Path(receipt_path).absolute().relative_to(work).as_posix())
    plan, verified = _verified_for_publication(work, plan_ref, receipt_ref)
    delivery = Path(delivery_root).absolute()
    if delivery != Path(plan["source_root"]).absolute():
        raise MigrationError("migration_delivery_root_mismatch")
    with locked_publication(delivery, plan_digest=plan["plan_digest"]):
        publication_path = work / "publication-receipt.json"
        expected_receipt = file_state(work, publication_path.name)
        if publication_path.exists():
            previous = receipt_document(work, file_reference(work, publication_path.name), "publish", plan_digest=plan["plan_digest"])
            if previous["verified"] != receipt_ref:
                raise MigrationError("migration_publication_receipt_conflict")
            _check_untouched(plan)
            try:
                journal = _verify_publication_confirmation(work, plan, previous)
            except MigrationError as exc:
                if str(exc) not in {"migration_publication_receipt_stale", "migration_publication_marker_unconfirmed",
                                    "migration_publication_journal_incomplete"}:
                    raise
            else:
                if all(file_state(delivery, row["path"]) == row["after"] for row in journal["files"]):
                    return previous
            # cleanup 的回滚不改不可变发布收据；只按原 journal 恢复后重放同一批。
            _recover_cleanup_rollback(work, plan, previous)
        _recover_publication(work, plan)
        _check_source(plan)
        publish_targets(work, plan, verified["staging_root"], checkpoint=checkpoint)
        return _seal_publication_receipt(work, plan, {"schema_version": 2, "kind": RECEIPT_KIND,
            "phase": "publish", "status": "passed", "plan": plan_ref, "plan_digest": plan["plan_digest"],
            "verified": receipt_ref, "delivery_root": str(delivery), "base_revision": plan["base_revision"],
            "dirty_before": plan["dirty_snapshot"]}, expected=expected_receipt)


def cleanup_migration(plan_path, publication_path, delivery_root, *, checkpoint=None):
    work, delivery = Path(plan_path).absolute().parent, Path(delivery_root).absolute()
    plan_ref = file_reference(work, Path(plan_path).name)
    plan = validate_plan(load_document(work, plan_ref))
    published_ref = file_reference(work, Path(publication_path).absolute().relative_to(work).as_posix())
    published = receipt_document(work, published_ref, "publish", plan_digest=plan["plan_digest"])
    if published.get("plan") != plan_ref or published["delivery_root"] != str(delivery) or plan["source_root"] != str(delivery):
        raise MigrationError("migration_cleanup_root_mismatch")
    plan, verified = _verified_for_publication(work, plan_ref, published["verified"])
    final_path = work / "cleanup-receipt.json"
    with locked_publication(delivery, plan_digest=plan["plan_digest"]) as marker:
        _verify_publication_confirmation(work, plan, published)
        if final_path.exists():
            final = _verify_final_state(work, file_reference(work, final_path.name), stage_receipt=verified["visual_receipt"])
            _release_cleanup_maintenance(work, final_path, marker, final)
            return final
        _check_untouched(plan)
        if any(file_state(delivery, path)["sha256"] != sha for path, sha in plan["target_hashes"].items()):
            raise MigrationError("migration_cleanup_delivery_drift")
        progress_path = work / "cleanup-progress.json"
        binding = {key: published[key] for key in (*PUBLICATION_IDENTITY, "journal_generation")}
        journal = {"schema_version": 2, "phase": "cleanup", **binding, "status": "running", "files": []}
        if progress_path.exists():
            previous = _check_cleanup_journal(plan, json.loads(read_evidence_bytes(work, progress_path.name)))
            if any(previous.get(key) != value for key, value in binding.items()):
                if (any(previous.get(key) != binding[key] for key in PUBLICATION_IDENTITY)
                        or previous.get("status") != "restored"
                        or any(file_state(delivery, row["path"]) != row["before"] for row in previous["files"])):
                    raise MigrationError("migration_cleanup_journal_stale")
            else:
                journal = previous
        entries = {row["path"]: row for row in journal["files"]}
        absent = {"type": "absent", "sha256": None, "mode": None}
        try:
            for allowed in plan["delete_allowlist"]:
                path = allowed["path"]
                state = file_state(delivery, path)
                if (state == absent and path in entries and entries[path]["before"] == allowed["expected"]
                        and entries[path].get("status") in {"prepared", "deleted"}):
                    entries[path]["status"] = "deleted"
                    continue
                if state != allowed["expected"]:
                    raise MigrationError("migration_cleanup_drift:" + path)
                row = {"path": path, "before": state, "after": absent, "backup": _save_original(work, delivery, path, state), "status": "prepared"}
                entries[path] = row
                journal["files"] = list(entries.values())
                _write_journal(progress_path, journal)
                _unlink_cas(delivery, path, state, checkpoint=checkpoint)
                row["status"] = "deleted"
                _write_journal(progress_path, journal)
                if checkpoint:
                    checkpoint("after_delete", path)
            staging_hashes = _staged_hashes(plan, Path(verified["staging_root"]))
            actual = _converged_hashes(plan, delivery)
            if actual != staging_hashes:
                raise MigrationError("migration_final_hash_convergence_failed")
            closure = verify_consumer_closure(delivery)
            verify_catalog_files(delivery / "leo-ppt-generator/template-library")
            _check_untouched(plan)
            journal["status"] = "passed"
            _write_journal(progress_path, journal)
            result = {"schema_version": 2, "kind": RECEIPT_KIND, "phase": "cleanup", "status": "passed",
                "plan": plan_ref, **binding, "publication": published_ref, "delivery_root": str(delivery),
                "staging_hashes": staging_hashes, "delivery_hashes": actual, "closure": closure,
                "deleted": journal["files"], "journal": file_reference(work, progress_path.name)}
            with tempfile.TemporaryDirectory(prefix=".final-verify-", dir=work) as temporary:
                candidate = Path(temporary) / "cleanup-receipt.json"
                _write_sealed(candidate, result)
                final = _verify_final_state(work, file_reference(work, candidate.relative_to(work).as_posix()), stage_receipt=verified["visual_receipt"])
                if final_path.exists():
                    raise MigrationError("migration_final_receipt_conflict")
                candidate.rename(final_path)
                fsync_directory(work)
                if checkpoint:
                    checkpoint("after_final_receipt", final_path.name)
                _release_cleanup_maintenance(work, final_path, marker, final)
                return final
        except BaseException:
            # 最终收据已经持久化时只保留 maintenance，重试重新校验后解除。
            # 此处再回滚文件会使不可变最终收据指向不存在的状态。
            if final_path.exists():
                raise
            journal["status"] = "restoring"
            _write_journal(progress_path, journal)
            cleanup_conflicts = _restore_entries(work, delivery, journal["files"])
            publication = sealed(load_document(work, published["journal"]), "journal_digest")
            conflicts = cleanup_conflicts + _restore_entries(work, delivery, publication["files"])
            journal.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
            _write_journal(progress_path, journal)
            publication.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
            _write_journal(work / "publication-progress.json", publication)
            if not marker.exists():
                atomic_write_json(marker, {"schema_version": 1, "plan_digest": plan["plan_digest"]})
            raise


def _check_cleanup_journal(plan, journal):
    sealed(journal, "journal_digest")
    if (journal.get("phase") != "cleanup"
            or any(journal.get(key) != value for key, value in _publication_identity(plan).items())
            or type(journal.get("journal_generation")) is not int or journal["journal_generation"] < 1
            or journal.get("status") not in {"running", "passed", "restoring", "restored", "blocked"}
            or not isinstance(journal.get("files"), list)):
        raise MigrationError("migration_cleanup_journal_stale")
    allowlist = {row["path"]: row["expected"] for row in plan.get("delete_allowlist", [])}
    seen = set()
    for row in journal["files"]:
        if not isinstance(row, dict) or row.get("path") in seen or row.get("path") not in allowlist:
            raise MigrationError("migration_cleanup_journal_scope_mismatch")
        path = row["path"]
        seen.add(path)
        before = allowlist[path]
        if (row.get("before") != before or row.get("after") != {"type": "absent", "sha256": None, "mode": None}
                or row.get("status") not in {"prepared", "deleted", "restored", "external-drift"}
                or row.get("backup") != {"path": "backups/" + digest({"path": path, "state": before}) + ".bin",
                                          "sha256": before["sha256"]}):
            raise MigrationError("migration_cleanup_journal_state_mismatch")
    return journal


def _recover_cleanup_rollback(work, plan, published):
    progress = work / "cleanup-progress.json"
    if not progress.exists():
        raise MigrationError("migration_published_delivery_drift")
    cleanup = _check_cleanup_journal(plan, json.loads(read_evidence_bytes(work, progress.name)))
    if (any(cleanup.get(key) != published.get(key) for key in (*PUBLICATION_IDENTITY, "journal_generation"))
            or cleanup.get("status") not in {"restoring", "restored", "blocked"}):
        raise MigrationError("migration_published_delivery_drift")
    publication = _check_publication_journal(plan, load_document(work, published["journal"]))
    if (publication.get("status") != "passed" or any(publication.get(key) != published.get(key)
            for key in (*PUBLICATION_IDENTITY, "journal_generation"))):
        raise MigrationError("migration_publication_journal_conflict")
    live = _check_publication_journal(plan, json.loads(read_evidence_bytes(work, "publication-progress.json")))
    _publication_marker(work, plan, live)
    conflicts = _restore_entries(work, plan["source_root"], cleanup["files"])
    conflicts += _restore_entries(work, plan["source_root"], publication["files"])
    cleanup.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
    _write_journal(progress, cleanup)
    publication.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
    publication["journal_generation"] = max(publication["journal_generation"], live["journal_generation"])
    _write_journal(work / "publication-progress.json", publication)
    if conflicts:
        raise MigrationError("migration_restore_external_drift")


def _release_cleanup_maintenance(work, final_path, marker, final):
    """先有可重读的最终收据，再解除维护；断点重试不依赖内存通过状态。"""
    on_disk = receipt_document(work, file_reference(work, final_path.relative_to(work).as_posix()), "cleanup",
                               plan_digest=final["plan_digest"])
    if on_disk != final:
        raise MigrationError("migration_final_receipt_conflict")
    owner = json.loads(read_evidence_bytes(marker.parent, marker.name))
    if owner.get("plan_digest") != final["plan_digest"]:
        raise MigrationError("migration_maintenance_owner_conflict")
    marker.unlink()
    fsync_directory(marker.parent)


def safe_path(root, relative):
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or PurePosixPath(relative).is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise MigrationError("migration_path_invalid")
    root = Path(root).absolute()
    path = root / relative
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise MigrationError("migration_symlink_rejected:" + relative)
    return path


def file_state(root, relative):
    path = safe_path(root, relative)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"type": "absent", "sha256": None, "mode": None}
    if not stat.S_ISREG(metadata.st_mode):
        raise MigrationError("migration_file_type_invalid:" + relative)
    body = read_evidence_bytes(root, relative)
    after = path.lstat()
    if (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise MigrationError("migration_file_changed_during_read:" + relative)
    return {"type": "file", "sha256": hashlib.sha256(body).hexdigest(), "mode": stat.S_IMODE(metadata.st_mode)}


def sealed(document, field):
    if not isinstance(document, dict) or document.get(field) != digest({k: v for k, v in document.items() if k != field}):
        raise MigrationError("migration_" + field + "_mismatch")
    return document


def load_document(root, reference):
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise MigrationError("migration_reference_invalid")
    return json.loads(verify_reference(root, reference))


def validate_plan_contract(plan):
    from jsonschema import Draft202012Validator
    sealed(plan, "plan_digest")
    schema = json.loads((Path(__file__).parent / "schemas/migration-plan-v2.schema.json").read_text())
    if next(Draft202012Validator(schema).iter_errors(plan), None) is not None:
        raise MigrationError("migration_plan_schema_mismatch")
    if not Path(plan["source_root"]).is_absolute():
        raise MigrationError("migration_source_root_invalid")
    if [row["path"] for row in plan["closure"]["roots"]] != list(CLOSURE_ROOTS):
        raise MigrationError("migration_closure_roots_mismatch")
    for path in plan["source_snapshot"]:
        safe_path(plan["source_root"], path)
        if not path.startswith("leo-ppt-generator/") and path != "CHANGELOG.md":
            raise MigrationError("migration_write_scope_invalid")
    for path, row in plan["mapping"].items():
        if row["operation"] == "derived":
            if not path.startswith("leo-ppt-generator/template-library/catalog/"):
                raise MigrationError("migration_derived_scope_invalid")
        else:
            if row["source"] not in plan["source_snapshot"] or plan["source_snapshot"][row["source"]]["type"] != "file":
                raise MigrationError("migration_mapping_source_invalid")
            safe_path(plan["source_root"], row["source"])
            if row["operation"] == "normalize" and (row.get("source_relative_to_library") != "library.json"
                    or row["source"] != "leo-ppt-generator/template-library/library.json"
                    or path != row["source"]):
                raise MigrationError("migration_normalization_scope_invalid")
            if row["operation"] == "copy":
                prefix = "leo-ppt-generator/template-library/"
                expected = prefix + mapped_library_path(row["source"][len(prefix):]) if row["source"].startswith(prefix) else row["source"]
                if path != expected:
                    raise MigrationError("migration_mapping_destination_invalid")
    return plan


def validate_plan(plan):
    validate_plan_contract(plan)
    if (plan.get("schema_version") != 2 or plan.get("kind") != PLAN_KIND or plan.get("phase") != "preview"
            or plan.get("gate") != "U7-B" or not re.fullmatch(r"[0-9a-f]{40}", plan.get("base_revision", ""))):
        raise MigrationError("migration_execution_plan_required")
    if (not isinstance(plan.get("source_snapshot"), dict) or not plan["source_snapshot"]
            or not isinstance(plan.get("target_hashes"), dict) or not plan["target_hashes"]):
        raise MigrationError("migration_snapshot_empty")
    if set(plan.get("mapping", {})) != set(plan["target_hashes"]):
        raise MigrationError("migration_mapping_incomplete")
    for path, sha in plan["target_hashes"].items():
        safe_path(plan["source_root"], path)
        if (not path.startswith("leo-ppt-generator/") and path != "CHANGELOG.md") or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise MigrationError("migration_write_scope_invalid")
        if plan["mapping"][path].get("sha256") != sha or path not in plan["source_snapshot"]:
            raise MigrationError("migration_mapping_hash_mismatch")
    deletes = plan.get("delete_allowlist")
    if not isinstance(deletes, list) or len({row["path"] for row in deletes}) != len(deletes):
        raise MigrationError("migration_delete_allowlist_invalid")
    for row in deletes:
        safe_path(plan["source_root"], row["path"])
        if (set(row) != {"path", "expected", "after_publish", "already_absent"}
                or row["path"] in plan["target_hashes"] or not row["path"].startswith("leo-ppt-generator/")
                or row["expected"] != plan["source_snapshot"].get(row["path"])
                or row["expected"].get("type") != "file" or row["after_publish"] != row["expected"]
                or row["already_absent"] != "only-after-journaled-delete"):
            raise MigrationError("migration_delete_allowlist_invalid")
    if plan.get("allowlist_digest") != digest(deletes):
        raise MigrationError("migration_allowlist_digest_mismatch")
    return plan


def receipt_document(root, reference, phase, *, plan_digest=None):
    receipt = sealed(load_document(root, reference), "receipt_digest")
    if (receipt.get("schema_version") != 2 or receipt.get("kind") != RECEIPT_KIND
            or receipt.get("phase") != phase or receipt.get("status") != "passed"
            or (plan_digest is not None and receipt.get("plan_digest") != plan_digest)):
        raise MigrationError("migration_" + phase + "_receipt_invalid")
    return receipt


def verify_catalog_files(library):
    """验证 current 指向完整不可变 v2 generation，含每个派生 view 的字节。"""
    library = Path(library)
    pointer = json.loads(read_evidence_bytes(library, "catalog/current.json"))
    generation = pointer.get("generation", "")
    if pointer.get("schema_version") != 2 or not re.fullmatch(r"[0-9a-f]{64}", generation):
        raise MigrationError("migration_v2_current_required")
    prefix = "catalog/generations/" + generation + "/"
    build = json.loads(read_evidence_bytes(library, prefix + "build-manifest.json"))
    if (build.get("schema_version") != 2 or build.get("catalog_generation") != generation
            or set(build.get("output_hashes", {})) != {"registry.json", "views/execution-pairings.json",
                "views/relation-capabilities.json", "views/visual.json"}):
        raise MigrationError("migration_v2_build_invalid")
    for path, sha in build["output_hashes"].items():
        verify_reference(library, {"path": prefix + path, "sha256": sha})
    registry = json.loads(read_evidence_bytes(library, prefix + "registry.json"))
    if (registry.get("schema_version") != 2 or registry.get("catalog_generation") != generation
            or not registry.get("asset_generation") or not registry.get("evidence_set_digest")):
        raise MigrationError("migration_v2_registry_invalid")
    from .template_catalog import catalog_inputs, validate_library
    from jsonschema import Draft202012Validator
    validate_library(library)
    schema = json.loads((Path(__file__).parent / "schemas/template-registry-v2.schema.json").read_text())
    if list(Draft202012Validator(schema).iter_errors(registry)):
        raise MigrationError("migration_v2_registry_invalid")
    expected = catalog_inputs(library)
    if digest(expected) != generation or any(registry.get(key) != value or build.get(key) != value for key, value in expected.items()):
        raise MigrationError("migration_v2_source_stale")
    return {"generation": generation, "current": file_reference(library, "catalog/current.json")}


def verify_final_receipt(root, reference, *, stage_receipt):
    """U6-B 必须重核正式 cleanup→publish→verify→plan 链，手填 hash 字典无效。"""
    receipt = receipt_document(root, reference, "cleanup")
    marker = maintenance_path(receipt["delivery_root"])
    if marker.exists() or marker.is_symlink():
        raise MigrationError("migration_delivery_in_maintenance")
    with library_operation(marker.parent):
        return _verify_final_state(root, reference, stage_receipt=stage_receipt)


def _verify_final_state(root, reference, *, stage_receipt):
    """供持锁 cleanup 检查最终字节；公开验证仍要求 maintenance 已解除。"""
    final = receipt_document(root, reference, "cleanup")
    plan = validate_plan(load_document(root, final["plan"]))
    if final.get("plan_digest") != plan["plan_digest"]:
        raise MigrationError("migration_final_plan_mismatch")
    published = receipt_document(root, final["publication"], "publish", plan_digest=plan["plan_digest"])
    verified = receipt_document(root, published["verified"], "verify", plan_digest=plan["plan_digest"])
    # 正式 verify gate 会重算 staged catalog、bundle 日志和 U6-A；拒绝自签摘要字典。
    _verified_for_publication(root, final["plan"], published["verified"])
    if (published.get("plan") != final["plan"] or verified.get("plan") != final["plan"]
            or verified.get("visual_receipt") != stage_receipt or not verified.get("publication_ready")
            or set(verified.get("checks", {})) != STRUCTURAL_GATES
            or any(row.get("status") != "passed" for row in verified["checks"].values())):
        raise MigrationError("migration_verification_chain_incomplete")
    for row in verified["checks"].values():
        evidence = load_document(root, row["evidence"])
        if evidence.get("status") != "passed" or evidence.get("plan_digest") != plan["plan_digest"]:
            raise MigrationError("migration_structural_evidence_invalid")
    staging = Path(verified["staging_root"])
    delivery = Path(published["delivery_root"])
    if (delivery.absolute() != Path(plan["source_root"]).absolute() or delivery.absolute() == staging.absolute()
            or final.get("delivery_root") != published["delivery_root"]
            or final.get("staging_hashes") != verified.get("staging_hashes")
            or final.get("staging_hashes") != plan["target_hashes"]
            or final.get("delivery_hashes") != plan["target_hashes"]):
        raise MigrationError("migration_convergence_manifest_mismatch")
    for directory in (staging, delivery):
        _converged_hashes(plan, directory)
    journal = _verify_publication_confirmation(root, plan, published)
    if (journal.get("plan_digest") != plan["plan_digest"] or journal.get("phase") != "publish"
            or journal.get("status") != "passed" or journal.get("current_switched") is not True
            or {row["path"]: row.get("target_sha256") for row in journal.get("files", [])} != plan["target_hashes"]
            or any(row.get("status") != "replaced" for row in journal.get("files", []))):
        raise MigrationError("migration_publication_journal_incomplete")
    deleted = {row["path"]: row for row in final.get("deleted", [])}
    cleanup_journal = _check_cleanup_journal(plan, load_document(root, final["journal"]))
    if (any(final.get(key) != published.get(key) or cleanup_journal.get(key) != published.get(key)
            for key in (*PUBLICATION_IDENTITY, "journal_generation"))
            or cleanup_journal.get("phase") != "cleanup" or cleanup_journal.get("status") != "passed"
            or cleanup_journal.get("plan_digest") != plan["plan_digest"]
            or cleanup_journal.get("files") != final.get("deleted")
            or any(row.get("status") != "deleted" for row in final.get("deleted", []))):
        raise MigrationError("migration_cleanup_journal_incomplete")
    if set(deleted) != {row["path"] for row in plan["delete_allowlist"]}:
        raise MigrationError("migration_cleanup_manifest_incomplete")
    for row in plan["delete_allowlist"]:
        if deleted[row["path"]].get("before") != row["expected"] or file_state(delivery, row["path"])["type"] != "absent":
            raise MigrationError("migration_cleanup_drift:" + row["path"])
    closure = verify_consumer_closure(delivery)
    if final.get("closure") != closure:
        raise MigrationError("migration_final_consumer_closure_failed")
    verify_catalog_files(delivery / "leo-ppt-generator/template-library")
    verify_catalog_files(staging / "leo-ppt-generator/template-library")
    return final


def maintenance_path(delivery):
    return Path(delivery) / "leo-ppt-generator/template-library/.maintenance.json"


def require_available(library):
    path = Path(library) / ".maintenance.json"
    if path.exists() or path.is_symlink():
        raise MigrationError("library_in_maintenance")


@contextmanager
def _library_lock(library, *, exclusive=False):
    """锁住库目录本身；只读安装也能参与互斥，不创建或替换锁文件。"""
    import fcntl
    root = Path(library).absolute()
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            code = "migration_maintenance_lock_busy" if exclusive else "library_in_maintenance"
            raise MigrationError(code) from exc
        current, pinned = os.stat(root, follow_symlinks=False), os.fstat(fd)
        if (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino):
            raise MigrationError("migration_library_root_changed")
        yield
    finally:
        os.close(fd)


@contextmanager
def library_operation(library):
    """消费者在完整读写期间持共享锁；发布前的检查与操作不能分离。"""
    require_available(library)
    with _library_lock(library):
        require_available(library)
        yield


@contextmanager
def locked_publication(delivery, *, plan_digest):
    """进程锁与持久 maintenance 分离；中断后仍阻止普通消费者执行。"""
    import fcntl
    marker = maintenance_path(delivery)
    safe_path(delivery, marker.relative_to(delivery).as_posix())
    marker.parent.mkdir(parents=True, exist_ok=True)
    with _library_lock(marker.parent, exclusive=True):
        lock = marker.with_name(".maintenance.lock")
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MigrationError("migration_maintenance_lock_busy") from exc
            if marker.exists():
                current = json.loads(read_evidence_bytes(marker.parent, marker.name))
                if current.get("plan_digest") != plan_digest:
                    raise MigrationError("migration_maintenance_owner_conflict")
            else:
                atomic_write_json(marker, {"schema_version": 1, "plan_digest": plan_digest})
                fsync_directory(marker.parent)
            yield marker
        finally:
            os.close(fd)


def compare_and_swap_file(root, relative, *, expected, body, mode=0o644, checkpoint=None):
    """固定目录描述符后核对旧字节；仅替换明确绑定的单个普通文件。"""
    path = safe_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = None
    try:
        if file_state(root, relative) != expected:
            raise MigrationError("migration_cas_mismatch:" + relative)
        fd, temporary = tempfile.mkstemp(prefix=".migration-", dir=path.parent)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body); handle.flush()
            os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
        if checkpoint:
            checkpoint("before_cas", relative)
        if file_state(root, relative) != expected:
            raise MigrationError("migration_cas_mismatch:" + relative)
        # 父目录被交换时不把写入悄悄落到另一棵树。
        current_parent = os.stat(path.parent, follow_symlinks=False)
        pinned_parent = os.fstat(parent_fd)
        if (current_parent.st_dev, current_parent.st_ino) != (pinned_parent.st_dev, pinned_parent.st_ino):
            raise MigrationError("migration_parent_changed:" + relative)
        os.replace(Path(temporary).name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        temporary = None
        os.fsync(parent_fd)
        actual = file_state(root, relative)
        if actual != {"type": "file", "sha256": hashlib.sha256(body).hexdigest(), "mode": mode}:
            raise MigrationError("migration_cas_postwrite_drift:" + relative)
        return actual
    finally:
        if temporary is not None:
            try:
                os.unlink(Path(temporary).name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)
