#!/usr/bin/env python3
r"""Capability manifest (R-60): machine-readable skill capability inventory.

marketingskills keeps a hand-maintained VERSIONS.md so agents can compare
against local copies and detect updates. Here the inventory is derived from
the tree itself (no hand-maintained numbers to drift): counts + sha256 per
file for the four capability layers, plus a per-layer digest, producing a
single capability-manifest.json that `leo-ppt doctor` can cite and diff
after `npx skills add` updates ("did my 137 style briefs actually sync?").

历史 v1 的分层计数规则如下（旧 --style-index 派生索引已随 U10 退役，
template-library registry 由 --template-library 构建）：
  styles     every .md under template-library/reference/sources/retired-styles-tree/styles/, per top-level axis dir;
  briefs     the style-brief subset: top-level *.md under template-library/reference/sources/retired-styles-tree/styles
             + 01_通用母版 (all) + 02_行业内容域 (excluding per-industry
             _content_rules.md) + 03_场景用途结构 (all)
             + 05_来源_awesome-gpt-image-2/借鉴新增;
  scripts    files under scripts/ (any extension, __pycache__ excluded);
  references every .md under references/ (styles included, per dir).

Every file gets a sha256; each layer gets a digest = sha256 over the
sorted "relpath:hash" lines; the manifest gets a top-level digest over the
four layer digests. Determinism: sorted paths, no timestamps, no clock.

--compare OLD_MANIFEST prints (and, with --out, writes) a diff:
  - per-layer count changes and digest changes;
  - files added / removed / hash-changed per layer.
Identical trees compare clean. Diff information is informational: exit 0.

Usage:
  capability_manifest.py [--root DIR] [--out FILE] [--compare OLD.json]
                         [--pretty]
  capability_manifest.py --template-library [--library-root DIR]
                         [--library-publish | --library-check]

Canonical template-library checks must use the second form. The default
four-layer manifest is a compatibility snapshot of the retired reference
tree and is labelled ``source=retired-reference`` in its JSON output.

Exit codes: 0 = ok (diff or not); 2 = usage error (missing root/manifest).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import os
import shutil
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))

SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_USAGE = 2

STYLES_DIR = Path("template-library/reference/sources/retired-styles-tree/styles")
REFERENCES_DIR = Path("references")
SCRIPTS_DIR = Path("scripts")
# 保留 v1 的历史 brief 投影，不用作新索引的候选资格数。
BRIEF_RULES = (
    ("", "top"),
    ("01_通用母版", "all"),
    ("02_行业内容域", "exclude_rules"),
    ("03_场景用途结构", "all"),
    (Path("05_来源_awesome-gpt-image-2") / "借鉴新增", "all"),
)
AXIS_NAME_RE = re.compile(r"^\d{2}_")


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _hash_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# template-library registry builder（唯一 builder，方案 §6）
# --------------------------------------------------------------------------- #

def derive_structure_admission(library_root: Path) -> dict:
    """dashi K5/U5：结构准入派生——从 canonical 声明与既有验证记录得出，
    不另存手写准入名单。HTML 绑定声明即验证（renderer 反向绑定经
    lint_template_contract 核对）；image profile 需 structure 声明 +
    renderer_support.image 构图说明；缺声明记 unknown 不准入自动池。
    """
    layouts_dir = library_root / "canonical" / "layouts"
    sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))
    from leo_ppt_generator.layout_selection import structure_fingerprint
    total = html_declared = image_declared = unknown = 0
    families: set[str] = set()
    for path in sorted(layouts_dir.glob("*/layout.json")):
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        total += 1
        renderer = profile.get("renderer_support") or {}
        fingerprint = structure_fingerprint(profile)
        declared = fingerprint != "unknown"
        if declared:
            families.add(fingerprint)
        if isinstance(renderer.get("render:html"), str):
            if declared:
                html_declared += 1
            else:
                unknown += 1
        elif declared and isinstance(renderer.get("image"), str):
            image_declared += 1
        elif not declared:
            unknown += 1
    return {
        "total_layouts": total,
        "html_declared": html_declared,
        "image_declared": image_declared,
        "structure_unknown": unknown,
        "distinct_families": len(families),
        "auto_pool": html_declared + image_declared,
    }


def derive_qualification(asset: dict, *, asset_generation: str, evidence_receipts: list[dict] | None = None) -> dict:
    """Derive qualification from owner declaration plus probe receipts.

    Declarations without matching, generation-bound positive and negative probes
    remain unverified and can never enter publication-qualified views.
    """
    receipts = evidence_receipts or []
    aid = asset.get("asset_id")
    bound = [r for r in receipts if r.get("asset_id") == aid and r.get("asset_generation") == asset_generation]
    positive = any(r.get("probe") == "positive" and r.get("status") == "passed" for r in bound)
    negative = any(r.get("probe") == "negative" and r.get("status") == "passed" for r in bound)
    status = "publication-qualified" if positive and negative else ("provisional" if asset.get("provisional") else "unverified")
    digest = hashlib.sha256(_json_bytes(sorted(bound, key=lambda x: json.dumps(x, sort_keys=True)))).hexdigest() if bound else None
    return {"schema_version": 1, "asset_id": aid, "asset_generation": asset_generation,
            "qualification_status": status, "evidence_set_digest": digest,
            "lanes": {lane: {"status": status if lane in (asset.get("lanes") or ["render:html"]) else "unverified",
                              "probe_receipts": [r.get("receipt_id") for r in bound if r.get("lane") == lane]}
                       for lane in (asset.get("lanes") or ["render:html"])} }


def build_qualification_manifest(library_root: Path, evidence_path: Path | None = None) -> dict:
    """Build a generation-bound qualification view; declarations alone stay unverified."""
    registry = build_template_registry(library_root)
    receipts = []
    if evidence_path and evidence_path.is_file():
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        receipts = payload if isinstance(payload, list) else payload.get("receipts", [])
    rows = []
    for entity in registry["entities"]:
        if entity.get("kind") not in {"layout", "template"}:
            continue
        try:
            data = json.loads((library_root / entity["path"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        lanes = list((data.get("renderer_support") or {}).keys()) or [data.get("lane", "render:html")]
        rows.append(derive_qualification({"asset_id": entity["asset_id"], "lanes": lanes},
                                         asset_generation=registry["generation"],
                                         evidence_receipts=receipts))
    return {"schema_version": 1, "kind": "qualification-manifest",
            "asset_generation": registry["generation"],
            "evidence_set_digest": hashlib.sha256(_json_bytes(receipts)).hexdigest() if receipts else None,
            "qualifications": rows}


def build_template_registry(library_root: Path) -> dict:
    """从 canonical + governance 输入确定性构建 registry（不写盘）。

    generation = 输入摘要；无时间戳。evidence_set_digest 由 style_validation
    提供（U2）；本 builder 只在 curation/evidence 输入存在时纳入 source_digest。
    """
    sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))
    from leo_ppt_generator.asset_resolver import (
        KIND_CANONICAL_DIR, KIND_ENTITY_FILE, _declared_dependencies, _validate_library_declaration,
        revision_of,
    )

    library_root = Path(library_root).resolve()
    _validate_library_declaration(library_root)
    entities: list[dict] = []
    ids: set[str] = set()
    canonical = library_root / "canonical"
    for kind, dirname in sorted(KIND_CANONICAL_DIR.items()):
        base = canonical / dirname
        if not base.is_dir():
            continue
        # Axis entities are grouped as canonical/axes/<axis-kind>/<slug>/manifest.json;
        # other canonical entities use canonical/<kind>/<slug>/<entity-file>.
        pattern = (f"*/*/{KIND_ENTITY_FILE[kind]}" if kind == "axis"
                   else f"*/{KIND_ENTITY_FILE[kind]}")
        for manifest_path in sorted(base.glob(pattern)):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ValueError(
                    f"registry_entity_invalid: {manifest_path.name}: {exc}") from exc
            asset_id = data.get("asset_id")
            declared_scope = str(asset_id).split(":", 1)[0] if asset_id else ""
            if declared_scope != "builtin" or asset_id in ids:
                raise ValueError(f"registry_asset_id_invalid: {asset_id!r}")
            ids.add(asset_id)
            entities.append({
                "asset_id": asset_id,
                "kind": kind,
                "path": manifest_path.relative_to(library_root).as_posix(),
                "revision": revision_of(data),
                "name": data.get("name") or asset_id.rsplit(":", 1)[-1],
                "aliases": data.get("aliases", []) if isinstance(data.get("aliases"), list) else [],
                "lifecycle": data.get("lifecycle", "draft"),
                "dependencies": _declared_dependencies(data),
            })
    entities.sort(key=lambda entity: entity["asset_id"])
    known = {entity["asset_id"] for entity in entities}
    for entity in entities:
        for dep in entity["dependencies"]:
            if dep not in known:
                raise ValueError(
                    f"registry_dependency_missing: {entity['asset_id']} -> {dep}")

    sources: dict[str, str] = {}
    for path in sorted(library_root.glob("canonical/**/*")):
        if path.is_file():
            sources[path.relative_to(library_root).as_posix()] = sha256_file(path)
    for rel in ("library.json", "governance/curation.json",
                "governance/schemas/style-brief-v2.schema.json"):
        path = library_root / rel
        if path.is_file():
            sources[rel] = sha256_file(path)
    source_digest = _hash_bytes(_json_bytes(sources))
    return {
        "kind": "template-registry",
        "schema_version": 1,
        "generation": source_digest[:32],
        "source_digest": source_digest,
        "evidence_set_digest": None,
        "entities": entities,
    }


def inventory_template_library(library_root: Path) -> dict:
    """保留坏文件与冲突分母；盘点不授予执行资格，也不发布 catalog。"""
    from collections import Counter, defaultdict
    from leo_ppt_generator.asset_resolver import KIND_CANONICAL_DIR, KIND_ENTITY_FILE

    library_root = Path(library_root).resolve()
    rows, file_hashes = [], {}
    identities, aliases = defaultdict(list), defaultdict(set)
    for kind, dirname in sorted(KIND_CANONICAL_DIR.items()):
        base = library_root / "canonical" / dirname
        pattern = f"*/*/{KIND_ENTITY_FILE[kind]}" if kind == "axis" else f"*/{KIND_ENTITY_FILE[kind]}"
        for path in sorted(base.glob(pattern)):
            relative = path.relative_to(library_root).as_posix()
            row = {"path": relative, "kind": kind, "asset_id": None,
                   "state": "unknown", "gaps": [], "sha256": None}
            rows.append(row)
            if path.is_symlink() or not path.resolve().is_relative_to(library_root):
                row["gaps"].append("unsafe_path")
                continue
            try:
                raw = path.read_bytes()
                row["sha256"] = _hash_bytes(raw)
                file_hashes[relative] = row["sha256"]
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("entity must be an object")
            except (OSError, ValueError) as exc:
                row["gaps"].append("unreadable_manifest")
                continue
            identity = data.get("asset_id")
            row["asset_id"] = identity if isinstance(identity, str) else None
            if not isinstance(identity, str) or not identity.startswith(f"builtin:{kind}:"):
                row["gaps"].append("invalid_identity")
                continue
            identities[identity].append(relative)
            alias_values = data.get("aliases") or []
            if not isinstance(alias_values, list):
                row["gaps"].append("invalid_aliases")
                alias_values = []
            for alias in [data.get("name"), *alias_values]:
                if isinstance(alias, str) and alias.strip():
                    aliases[(kind, alias.strip().casefold())].add(identity)
            row["state"] = "retired" if data.get("lifecycle") == "retired" else "legacy"
            if kind == "style":
                if not data.get("source"):
                    row["gaps"].append("source_unknown")
                bindings = data.get("bindings")
                if not isinstance(bindings, dict) or not bindings.get("theme_default"):
                    row["gaps"].append("theme_missing")
            renderer = data.get("renderer_support")
            if kind == "layout" and (not isinstance(renderer, dict) or not any(renderer.values())):
                row["gaps"].append("renderer_missing")
            if kind == "template" and data.get("lane") == "render:html":
                html = path.with_name("page.html")
                if html.is_symlink() or not html.is_file():
                    row["gaps"].append("template_missing")
            # active 只表示旧生命周期；必须另有组合级运行证据才能晋升 executable。
            if row["state"] != "retired":
                row["gaps"].append("combination_admission_not_verified")
    unsafe_files = []
    for path in sorted((library_root / "canonical").rglob("*")):
        if path.is_symlink() or not path.resolve().is_relative_to(library_root):
            unsafe_files.append(path.relative_to(library_root).as_posix())
        elif path.is_file():
            file_hashes[path.relative_to(library_root).as_posix()] = sha256_file(path)
    states = Counter(row["state"] for row in rows)
    gaps = Counter(gap for row in rows for gap in row["gaps"])
    duplicates = {identity: paths for identity, paths in sorted(identities.items()) if len(paths) > 1}
    conflicts = [{"kind": kind, "alias": alias, "asset_ids": sorted(ids)}
                 for (kind, alias), ids in sorted(aliases.items()) if len(ids) > 1]
    return {"schema_version": 1, "kind": "template-library-inventory",
            "denominator": {"raw_manifests": len(rows), "unique_identities": len(identities)},
            "counts_by_kind": dict(sorted(Counter(row["kind"] for row in rows).items())),
            "states": {state: states[state] for state in ("unknown", "legacy", "executable", "retired")},
            "gap_counts": dict(sorted(gaps.items())), "duplicate_identities": duplicates,
            "alias_conflicts": conflicts, "assets": rows,
            "files": file_hashes, "unsafe_files": unsafe_files,
            "source_digest": _hash_bytes(_json_bytes(file_hashes)),
            "claim_ceiling": "inventory-only", "migration_complete": False}


def publish_template_registry(registry: dict, library_root: Path) -> dict:
    """staging → catalog/generations/<gen>/ → 原子替换 current.json（构建锁内）。"""
    library_root = Path(library_root).resolve()
    catalog = library_root / "catalog"
    generations = catalog / "generations"
    generation = registry["generation"]
    target = generations / generation
    updated = False
    if target.exists():
        # 同输入重复发布：校验既有代内容一致即幂等成功。
        existing = json.loads((target / "registry.json").read_text(encoding="utf-8"))
        if existing.get("source_digest") != registry["source_digest"]:
            raise ValueError("registry_generation_conflict")
        # The generation is input-derived, so a builder algorithm change can
        # produce different entities without changing the generation. Refresh
        # the same generation instead of treating the old registry as fresh.
        if existing != registry:
            registry_tmp = target / ".registry.json.tmp"
            registry_tmp.write_bytes(_json_bytes(registry))
            os.replace(registry_tmp, target / "registry.json")
            build_manifest = {
                "kind": "template-registry-build",
                "schema_version": 1,
                "generation": generation,
                "source_digest": registry["source_digest"],
                "output_hashes": {
                    "registry.json": _hash_bytes(_json_bytes(registry)),
                },
                "policy": "capability_manifest/template-registry/v1",
            }
            build_tmp = target / ".build-manifest.json.tmp"
            build_tmp.write_bytes(_json_bytes(build_manifest))
            os.replace(build_tmp, target / "build-manifest.json")
            updated = True
    else:
        staging = catalog / "staging"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        try:
            (staging / "registry.json").write_bytes(_json_bytes(registry))
            build_manifest = {
                "kind": "template-registry-build",
                "schema_version": 1,
                "generation": generation,
                "source_digest": registry["source_digest"],
                "output_hashes": {
                    "registry.json": _hash_bytes(_json_bytes(registry)),
                },
                "policy": "capability_manifest/template-registry/v1",
            }
            (staging / "build-manifest.json").write_bytes(_json_bytes(build_manifest))
            generations.mkdir(parents=True, exist_ok=True)
            os.replace(staging, target)
            updated = True
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
    pointer = {"kind": "template-catalog-pointer", "schema_version": 1,
               "generation": generation}
    pointer_tmp = catalog / ".current.json.tmp"
    pointer_tmp.write_bytes(_json_bytes(pointer))
    os.replace(pointer_tmp, catalog / "current.json")
    return {"generation": generation, "published": True, "updated": updated}


def rollback_template_catalog(library_root: Path, target_generation: str) -> dict:
    """批次回滚（U12/R-85b）：current.json 指针原子切回既有 generation。

    消费方经 current.json 解析代——指针回切即整库回滚，generation 目录
    不移动不删除。目标代必须已存在、registry 可读且自洽；目标即当前代
    时空操作返回。回滚动作写 `reports/` 之外只动指针文件本身。
    """

    import os
    import shutil
    from filelock import FileLock

    library_root = Path(library_root).resolve()
    catalog = library_root / "catalog"
    target_dir = catalog / "generations" / target_generation
    registry_path = target_dir / "registry.json"
    if not registry_path.is_file():
        raise ValueError(f"rollback_generation_missing: {target_dir}")
    published = json.loads(registry_path.read_text(encoding="utf-8"))
    if published.get("generation") != target_generation:
        raise ValueError("rollback_generation_identity_mismatch")
    with FileLock(str(catalog / ".publish.lock")):
        pointer_path = catalog / "current.json"
        current = json.loads(pointer_path.read_text(encoding="utf-8"))
        current_generation = current.get("generation")
        if current_generation == target_generation:
            return {"rolled_back": False, "generation": current_generation,
                    "reason": "already-current"}
        pointer = {"kind": "template-catalog-pointer", "schema_version": 1,
                   "generation": target_generation}
        pointer_tmp = catalog / ".current.json.tmp"
        pointer_tmp.write_bytes(_json_bytes(pointer))
        os.replace(pointer_tmp, pointer_path)
    return {"rolled_back": True, "from": current_generation, "to": target_generation}


def check_template_registry(library_root: Path) -> tuple[dict, int]:
    """只读校验 catalog，并区分 missing/invalid/stale/current。"""
    try:
        fresh = build_template_registry(library_root)
    except ValueError as exc:
        return {"reason_code": "registry_rebuild_failed", "catalog_state": "invalid",
                "detail": str(exc)}, 2
    try:
        pointer = json.loads((library_root / "catalog" / "current.json").read_text())
    except FileNotFoundError:
        return {"reason_code": "registry_pointer_missing",
                "catalog_state": "missing",
                "expected_generation": fresh["generation"]}, 1
    except (OSError, ValueError) as exc:
        return {"reason_code": "registry_pointer_invalid", "catalog_state": "invalid",
                "detail": str(exc), "expected_generation": fresh["generation"]}, 1
    if pointer.get("generation") != fresh["generation"]:
        return {"reason_code": "registry_stale",
                "catalog_state": "stale",
                "expected_generation": fresh["generation"],
                "actual_generation": pointer.get("generation")}, 1
    registry_path = (library_root / "catalog" / "generations" /
                     fresh["generation"] / "registry.json")
    try:
        published = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"reason_code": "registry_content_stale",
                "catalog_state": "missing",
                "generation": fresh["generation"]}, 1
    except (OSError, ValueError) as exc:
        return {"reason_code": "registry_content_invalid", "catalog_state": "invalid",
                "detail": str(exc), "generation": fresh["generation"]}, 1
    if published != fresh:
        return {"reason_code": "registry_content_stale",
                "catalog_state": "stale",
                "generation": fresh["generation"],
                "entities": len(fresh["entities"])}, 1
    return {"reason_code": "none", "generation": fresh["generation"],
            "catalog_state": "current", "entities": len(fresh["entities"])}, 0


def rel_sorted(root: Path, rel_dir: Path, pattern: str = "*.md") -> list[Path]:
    base = root / rel_dir
    if not base.is_dir():
        return []
    return sorted(
        (p.relative_to(root) for p in base.rglob(pattern) if p.is_file()),
        key=lambda p: p.as_posix())


def layer_files(root: Path, layer: str) -> list[Path]:
    if layer == "styles":
        return rel_sorted(root, STYLES_DIR)
    if layer == "references":
        return rel_sorted(root, REFERENCES_DIR)
    if layer == "scripts":
        base = root / SCRIPTS_DIR
        if not base.is_dir():
            return []
        return sorted(
            (p.relative_to(root) for p in base.iterdir() if p.is_file()),
            key=lambda p: p.as_posix())
    raise ValueError(layer)


def brief_files(root: Path) -> list[Path]:
    """Style-brief subset（capability-manifest v1 历史 brief 口径）。"""
    files: list[Path] = []
    styles_root = root / STYLES_DIR
    for sub, rule in BRIEF_RULES:
        base = styles_root / sub
        if not base.is_dir():
            continue
        if rule == "top":
            files += sorted(
                (p.relative_to(root) for p in base.glob("*.md") if p.is_file()),
                key=lambda p: p.as_posix())
            continue
        hits = [p for p in base.rglob("*.md") if p.is_file()]
        if rule == "exclude_rules":
            hits = [p for p in hits if p.name != "_content_rules.md"]
        files += sorted((p.relative_to(root) for p in hits),
                        key=lambda p: p.as_posix())
    return files


def digest_for(files: list[Path], hashes: dict[Path, str]) -> str:
    lines = [f"{p.as_posix()}:{hashes[p]}" for p in files]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def build_manifest(root: Path) -> dict:
    layers: dict[str, list[Path]] = {
        "styles": layer_files(root, "styles"),
        "briefs": brief_files(root),
        "scripts": layer_files(root, "scripts"),
        "references": layer_files(root, "references"),
    }
    hashes: dict[Path, str] = {}
    for files in layers.values():
        for path in files:
            if path not in hashes:
                hashes[path] = sha256_file(root / path)

    def layer_entry(files: list[Path]) -> dict:
        return {
            "count": len(files),
            "digest": digest_for(files, hashes),
            "files": {p.as_posix(): hashes[p] for p in files},
        }

    entries = {name: layer_entry(files) for name, files in layers.items()}
    top_digest = hashlib.sha256(
        "\n".join(f"{name}:{entries[name]['digest']}"
                  for name in sorted(entries)).encode("utf-8")).hexdigest()

    # styles axis breakdown for doctor readability.
    axis: dict[str, int] = {}
    styles_root = root / STYLES_DIR
    if styles_root.is_dir():
        for child in sorted(styles_root.iterdir()):
            if child.is_dir() and AXIS_NAME_RE.match(child.name):
                axis[child.name] = len([
                    p for p in child.rglob("*.md")
                    if p.is_file() and p.name != "_content_rules.md"])
        axis["(top)"] = len([p for p in styles_root.glob("*.md") if p.is_file()])
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "capability-manifest",
        "source": "retired-reference",
        "canonical_entrypoint": "capability_manifest.py --template-library --library-check",
        "skill": root.name,
        "digest": top_digest,
        "layers": entries,
        "styles_axis_counts": axis,
        "note": "能力清单版本（R-60）：doctor 比对安装副本与本地树的能力级 diff。",
    }


def compare_manifests(current: dict, old: dict) -> dict:
    """Count changes / file additions / removals / hash drift per layer."""
    result: dict = {"identical": current.get("digest") == old.get("digest"),
                    "layers": {}}
    for name in sorted(set(current.get("layers", {})) | set(old.get("layers", {}))):
        now = current.get("layers", {}).get(name, {})
        was = old.get("layers", {}).get(name, {})
        now_files = now.get("files", {})
        was_files = was.get("files", {})
        added = sorted(set(now_files) - set(was_files))
        removed = sorted(set(was_files) - set(now_files))
        changed = sorted(
            path for path in set(now_files) & set(was_files)
            if now_files[path] != was_files[path])
        result["layers"][name] = {
            "count_before": was.get("count"),
            "count_after": now.get("count"),
            "count_delta": (now.get("count", 0) - was.get("count", 0)
                            if was.get("count") is not None else None),
            "digest_before": was.get("digest"),
            "digest_after": now.get("digest"),
            "added": added,
            "removed": removed,
            "hash_changed": changed,
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="能力清单版本表（R-60）：styles/briefs/scripts/references "
                    "计数与 sha256 摘要，可 --compare 旧清单出 diff")
    parser.add_argument("--root", default=None, help="技能根目录（默认脚本所在技能）")
    parser.add_argument("--out", default=None,
                        help="清单落盘路径（默认只打印 stdout JSON）")
    parser.add_argument("--compare", default=None, help="旧 capability-manifest.json")
    parser.add_argument("--pretty", action="store_true", help="stdout 用缩进格式")
    parser.add_argument("--template-library", "--canonical", dest="template_library",
                        action="store_true",
                        help="canonical 模板库 registry（catalog/generations + current 指针；正式入口）")
    parser.add_argument("--library-root", help="template-library 根（默认 <root>/template-library）")
    parser.add_argument("--library-publish", action="store_true", help="配合 --template-library 发布")
    parser.add_argument("--library-check", action="store_true", help="配合 --template-library 只读校验")
    parser.add_argument("--library-inventory", action="store_true", help="只读盘点 canonical，保留缺失及冲突分母")
    parser.add_argument("--library-qualification", action="store_true", help="派生 generation-bound qualification view")
    parser.add_argument("--evidence-receipts", help="relation/probe receipt JSON for qualification")
    parser.add_argument("--library-rollback", metavar="GENERATION",
                        help="配合 --template-library：current.json 指针原子切回既有 generation（批次回滚）")
    args = parser.parse_args(argv)

    root = (Path(args.root).expanduser().resolve() if args.root
            else Path(__file__).resolve().parents[1])
    if not root.is_dir():
        print(f"根目录不存在: {root}", file=sys.stderr)
        return EXIT_USAGE

    if args.library_inventory:
        if args.library_publish or args.library_check or args.compare:
            parser.error("--library-inventory 不与发布、校验或旧清单比较混用")
        library = Path(args.library_root).expanduser().resolve() if args.library_root else root / "template-library"
        if not (library / "library.json").is_file():
            parser.error("模板库声明缺失")
        payload = json.dumps(inventory_template_library(library), ensure_ascii=False, indent=2, sort_keys=True)
        if args.out:
            output = Path(args.out)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return 0

    if args.template_library:
        if args.compare or (args.out and not args.library_qualification):
            parser.error("--template-library 不与旧清单参数混用")
        library_root = (Path(args.library_root).expanduser().resolve()
                        if args.library_root else root / "template-library")
        if not library_root.is_dir():
            print(f"模板库根不存在: {library_root}", file=sys.stderr)
            return EXIT_USAGE
        if args.library_qualification:
            evidence = Path(args.evidence_receipts).expanduser().resolve() if args.evidence_receipts else None
            result = build_qualification_manifest(library_root, evidence)
            code = 0
        elif args.library_rollback:
            if args.library_publish or args.library_check:
                parser.error("--library-rollback 不与发布或校验混用")
            try:
                result = rollback_template_catalog(library_root, args.library_rollback)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return EXIT_USAGE
            code = 0
        elif args.library_check:
            result, code = check_template_registry(library_root)
        elif args.library_publish:
            registry = build_template_registry(library_root)
            result = publish_template_registry(registry, library_root)
            result = {**result, "entities": len(registry["entities"])}
            code = 0
        else:
            registry = build_template_registry(library_root)
            result = {"generation": registry["generation"],
                      "entities": len(registry["entities"]),
                      "source_digest": registry["source_digest"],
                      "structure_admission": derive_structure_admission(library_root)}
            code = 0
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.library_qualification and args.out:
            output = Path(args.out).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return code

    manifest = build_manifest(root)
    if args.compare:
        old_path = Path(args.compare).expanduser().resolve()
        if not old_path.is_file():
            print(f"旧清单不存在: {old_path}", file=sys.stderr)
            return EXIT_USAGE
        try:
            old = json.loads(old_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"旧清单不可解析: {exc}", file=sys.stderr)
            return EXIT_USAGE
        diff = compare_manifests(manifest, old)
        manifest["compare"] = diff
        summary_lines = []
        for name, layer in diff["layers"].items():
            delta = layer["count_delta"]
            delta_text = f"{delta:+d}" if delta is not None else "?"
            summary_lines.append(
                f"{name}: {layer['count_before']} -> {layer['count_after']} "
                f"({delta_text}), +{len(layer['added'])} "
                f"-{len(layer['removed'])} ~{len(layer['hash_changed'])}")
        print("capability diff: " + ("identical" if diff["identical"] else "CHANGED"))
        for line in summary_lines:
            print("  " + line)

    payload = json.dumps(manifest, ensure_ascii=False,
                         indent=2 if (args.pretty or args.out) else None,
                         sort_keys=True)
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(payload)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
