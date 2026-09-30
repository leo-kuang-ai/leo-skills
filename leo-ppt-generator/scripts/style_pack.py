#!/usr/bin/env python3
"""style_pack v2：新库风格包导出/导入（U8，方案 §7.3/【F2】）。

数据/代码分离：
  - 数据实体（brief JSON）导入 v2 用户库 canonical/visual/styles；
  - 可执行内容（page.html/JS/CSS/SVG 活动内容）默认进入用户库
    reference/candidates 隔离区：可浏览、静态检查、转换，不能自动出样；
  - 采用为可执行模板须在用户库 governance/trust/ 落 executable-adoption-v1
    记录（绑定代码 digest + 实际审阅来源）；包内自报 trusted 一律无效。

Usage:
  python3 scripts/style_pack.py export <名> --out DIR
  python3 scripts/style_pack.py import DIR [--home DIR]
  python3 scripts/style_pack.py adopt DIR --reviewed-by <维护者> --basis <依据> [--home DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))

from leo_ppt_generator.styles import default_home, load_style  # noqa: E402

EXECUTABLE_SUFFIXES = {".html", ".js", ".css", ".svg", ".mjs"}


def _user_library(home: Path | None) -> Path:
    return (home or default_home()) / "template-library"


def _import_library(home: Path | None) -> Path:
    from leo_ppt_generator.user_library import user_library_root
    return user_library_root(home or default_home())


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_export(name: str, out_dir: Path) -> int:
    loaded = load_style(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "brief.json").write_text(
        json.dumps(loaded["brief"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "kind": "leo-style-pack", "schema_version": 2,
        "asset_id": loaded["asset_id"], "name": loaded["name"],
        "lifecycle": loaded["lifecycle"],
        "files": {"brief.json": hashlib.sha256(
            (out_dir / "brief.json").read_bytes()).hexdigest()},
        "note": "数据导出（脱敏由导出方负责）；不含执行面内容",
    }
    _write_json(out_dir / "manifest.json", manifest)
    print(json.dumps({"exported": loaded["asset_id"], "out": str(out_dir)}, ensure_ascii=False))
    return 0


def _pack_json(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("pack_duplicate_json_key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique)


def _pack_relative(value):
    if (not isinstance(value, str) or not value or "\\" in value
            or PurePosixPath(value).is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ValueError("pack_path_invalid")
    return value


def _verified_pack(pack_dir):
    from leo_ppt_generator.asset_resolver import ASSET_ID_RE
    from leo_ppt_generator.qualification import read_evidence_bytes
    if pack_dir.is_symlink():
        raise ValueError("pack_path_invalid")
    pack_dir = pack_dir.resolve(strict=True)
    manifest_bytes = read_evidence_bytes(pack_dir, "manifest.json")
    manifest = _pack_json(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("kind") != "leo-style-pack" or manifest.get("schema_version") != 2:
        raise ValueError("非 v2 风格包")
    if manifest.get("trusted") or str(manifest.get("asset_id", "")).startswith("builtin:"):
        raise ValueError("包内信任声明无效（pack_trusted_claim_invalid）；builtin 身份不可由导入包冒充")
    identity = manifest.get("asset_id")
    if (not isinstance(identity, str) or not ASSET_ID_RE.fullmatch(identity)
            or not identity.startswith("user:style:")):
        raise ValueError("pack_identity_invalid")
    title = _pack_relative(manifest.get("name"))
    if "/" in title or len(title) > 80:
        raise ValueError("pack_name_invalid")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("pack_files_empty")
    contents = {}
    for name, expected in sorted(files.items()):
        _pack_relative(name)
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("pack_hash_invalid")
        body = read_evidence_bytes(pack_dir, name)
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("文件缺失或 hash 不符：" + name)
        contents[name] = body
    return manifest, contents, hashlib.sha256(manifest_bytes).hexdigest()


def _prepared_import(pack_dir, home, *, pack=None, allow_existing=False):
    """读取并校验整个包后才规划写入；包名、实体身份与源路径分别检查。"""
    from jsonschema import Draft7Validator
    from referencing import Registry, Resource
    from leo_ppt_generator.asset_resolver import AssetResolver, _declared_dependencies, builtin_library_root
    manifest, contents, _ = pack or _verified_pack(pack_dir)
    identity, title = manifest["asset_id"], manifest["name"]
    governance = builtin_library_root() / "governance/schemas"
    resources = [json.loads(path.read_text()) for path in governance.glob("*.schema.json")]
    registry = Registry().with_resources((value["$id"], Resource.from_contents(value)) for value in resources if "$id" in value)
    schema = json.loads((governance / "style-brief-v2.schema.json").read_text())
    writes, messages, records = {}, [], {}
    primary = None
    for name, body in contents.items():
        if Path(name).suffix.lower() in EXECUTABLE_SUFFIXES:
            target = "reference/candidates/" + title + "/" + name
            messages.append({"quarantined": name, "to": target, "reason": "executable_content_default_isolated"})
        else:
            brief = _pack_json(body)
            errors = list(Draft7Validator(schema, registry=registry).iter_errors(brief))
            if errors or not brief["asset_id"].startswith("user:style:"):
                raise ValueError("pack_entity_invalid:" + name)
            asset_id = brief["asset_id"]
            if asset_id in records:
                raise ValueError("pack_duplicate_identity:" + asset_id)
            records[asset_id] = brief
            if asset_id == identity:
                primary = brief
            brief.setdefault("source", {})["origin"] = "user-imported"
            slug = asset_id.split(":", 2)[-1]
            target = "canonical/visual/styles/" + slug + "/brief.json"
            body = (json.dumps(brief, ensure_ascii=False, indent=2) + "\n").encode()
            messages.append({"imported": asset_id})
        if target in writes:
            raise ValueError("pack_target_collision")
        writes[target] = body
    if identity not in records:
        raise ValueError("pack_primary_entity_missing")
    if (primary is None or primary.get("name") != manifest.get("name")
            or primary.get("lifecycle") != manifest.get("lifecycle")):
        raise ValueError("pack_manifest_entity_mismatch")
    resolver = AssetResolver(home=home)
    for asset_id, brief in records.items():
        if not allow_existing and resolver.lookup(asset_id, kind="style", scope="user"):
            raise ValueError("pack_identity_conflict:" + asset_id)
        for dependency in _declared_dependencies(brief):
            if dependency not in records:
                resolver.resolve_dependencies(dependency)
    visiting, visited = set(), set()
    def walk(asset_id):
        if asset_id in visiting:
            raise ValueError("pack_dependency_cycle")
        if asset_id in visited:
            return
        visiting.add(asset_id)
        for dependency in _declared_dependencies(records[asset_id]):
            if dependency in records:
                walk(dependency)
        visiting.remove(asset_id)
        visited.add(asset_id)
    for asset_id in records:
        walk(asset_id)
    return writes, messages


def _check_candidate_scope(root, allowed):
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("采用候选软链接被拒绝")
        if path.is_file() and path.suffix.lower() in EXECUTABLE_SUFFIXES and path.relative_to(root).as_posix() not in allowed:
            raise ValueError("采用候选越界:" + path.relative_to(root).as_posix())


def cmd_import(pack_dir: Path, home: Path | None) -> int:
    from leo_ppt_generator.user_library import user_library_writer, bootstrap_user_library, publish_user_library
    try:
        library = _import_library(home)
        # 包预验在创建 home 前进行；锁内再次读取，避免预验与执行之间发生漂移。
        _prepared_import(pack_dir, library.parent)
        with user_library_writer(library):
            bootstrap = bootstrap_user_library(library)
            writes, messages = _prepared_import(pack_dir, library.parent)
            publish_user_library(library, {**bootstrap, **writes})
        for message in messages:
            print(json.dumps(message, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("usage: " + str(exc), file=sys.stderr)
        return 2


def cmd_adopt(pack_dir: Path, reviewed_by: str, basis: str, home: Path | None) -> int:
    from leo_ppt_generator.library_migration import safe_path, file_state
    from leo_ppt_generator.user_library import user_library_writer, bootstrap_user_library, publish_user_library, json_bytes
    from leo_ppt_generator.qualification import read_evidence_bytes
    if not isinstance(reviewed_by, str) or len(reviewed_by.strip()) < 2:
        print("usage: review_reviewer_invalid", file=sys.stderr)
        return 2
    if not isinstance(basis, str) or len(basis.strip()) < 8:
        print("usage: review_basis_invalid", file=sys.stderr)
        return 2
    try:
        library = _import_library(home)
        with user_library_writer(library):
            if bootstrap_user_library(library):
                raise ValueError("采用候选范围缺失")
            manifest, contents, manifest_sha256 = _verified_pack(pack_dir)
            data_writes, _ = _prepared_import(pack_dir, library.parent,
                pack=(manifest, contents, manifest_sha256), allow_existing=True)
            guards = {}
            for relative, body in data_writes.items():
                actual = read_evidence_bytes(library, relative)
                if actual != body:
                    raise ValueError("采用候选摘要漂移:" + relative)
                guards[relative] = hashlib.sha256(actual).hexdigest()
            title = manifest["name"]
            expected = {name: body for name, body in contents.items() if Path(name).suffix.lower() in EXECUTABLE_SUFFIXES}
            if not expected:
                raise ValueError("无可执行内容可采用")
            candidate_root = safe_path(library, "reference/candidates/" + title)
            if not candidate_root.is_dir():
                raise ValueError("采用候选范围缺失")
            code_digests = {}
            for relative, body in expected.items():
                actual = read_evidence_bytes(candidate_root, relative)
                if actual != body:
                    raise ValueError("采用候选摘要漂移:" + relative)
                code_digests[title + "/" + relative] = hashlib.sha256(actual).hexdigest()
            _check_candidate_scope(candidate_root, expected)
            adoption = {
                "kind": "executable-adoption", "schema_version": 1,
                "adoption_id": "adopt-" + hashlib.sha256(json.dumps(code_digests, sort_keys=True).encode()).hexdigest()[:12],
                "template_asset_id": manifest["asset_id"], "scope": "user", "code_digests": code_digests,
                "review": {"reviewed_by": reviewed_by, "basis": basis},
                "adopted_from": "manifest_sha256:" + manifest_sha256,
            }
            relative = "governance/trust/" + adoption["adoption_id"] + ".json"
            idempotent = file_state(library, relative)["type"] != "absent"
            if idempotent and _pack_json(read_evidence_bytes(library, relative)) != adoption:
                raise ValueError("adoption_identity_conflict")
            publish_user_library(library, {} if idempotent else {relative: json_bytes(adoption)},
                                 guards=guards, validator=lambda: _check_candidate_scope(candidate_root, expected))
            print(json.dumps({"adopted": adoption["adoption_id"], "bound_files": len(code_digests), "idempotent": idempotent}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("usage: " + str(exc), file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="style_pack v2（新库数据/代码分离）")
    sub = parser.add_subparsers(dest="command", required=True)
    p_export = sub.add_parser("export")
    p_export.add_argument("name")
    p_export.add_argument("--out", required=True)
    p_import = sub.add_parser("import")
    p_import.add_argument("pack_dir")
    p_import.add_argument("--home")
    p_adopt = sub.add_parser("adopt")
    p_adopt.add_argument("pack_dir")
    p_adopt.add_argument("--reviewed-by", required=True)
    p_adopt.add_argument("--basis", required=True)
    p_adopt.add_argument("--home")
    args = parser.parse_args(argv)
    if args.command == "export":
        return cmd_export(args.name, Path(args.out).expanduser())
    if args.command == "import":
        return cmd_import(Path(args.pack_dir).expanduser(), Path(args.home).expanduser() if args.home else None)
    return cmd_adopt(Path(args.pack_dir).expanduser(), args.reviewed_by, args.basis,
                     Path(args.home).expanduser() if args.home else None)


if __name__ == "__main__":
    raise SystemExit(main())
