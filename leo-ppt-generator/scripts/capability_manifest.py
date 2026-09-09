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


def check_template_registry(library_root: Path) -> tuple[dict, int]:
    """只读校验 current 指针的 generation 与源输入一致（漂移即非零）。"""
    try:
        fresh = build_template_registry(library_root)
    except ValueError as exc:
        return {"reason_code": "registry_rebuild_failed", "detail": str(exc)}, 2
    try:
        pointer = json.loads((library_root / "catalog" / "current.json").read_text())
    except (OSError, ValueError):
        return {"reason_code": "registry_pointer_missing",
                "expected_generation": fresh["generation"]}, 1
    if pointer.get("generation") != fresh["generation"]:
        return {"reason_code": "registry_stale",
                "expected_generation": fresh["generation"],
                "actual_generation": pointer.get("generation")}, 1
    registry_path = (library_root / "catalog" / "generations" /
                     fresh["generation"] / "registry.json")
    try:
        published = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"reason_code": "registry_content_stale",
                "generation": fresh["generation"]}, 1
    if published != fresh:
        return {"reason_code": "registry_content_stale",
                "generation": fresh["generation"],
                "entities": len(fresh["entities"])}, 1
    return {"reason_code": "none", "generation": fresh["generation"],
            "entities": len(fresh["entities"])}, 0


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
    args = parser.parse_args(argv)

    root = (Path(args.root).expanduser().resolve() if args.root
            else Path(__file__).resolve().parents[1])
    if not root.is_dir():
        print(f"根目录不存在: {root}", file=sys.stderr)
        return EXIT_USAGE

    if args.template_library:
        if args.compare or args.out:
            parser.error("--template-library 不与旧清单参数混用")
        library_root = (Path(args.library_root).expanduser().resolve()
                        if args.library_root else root / "template-library")
        if not library_root.is_dir():
            print(f"模板库根不存在: {library_root}", file=sys.stderr)
            return EXIT_USAGE
        if args.library_check:
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
                      "source_digest": registry["source_digest"]}
            code = 0
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
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
