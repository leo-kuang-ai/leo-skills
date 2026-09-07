#!/usr/bin/env python3
r"""Capability manifest (R-60): machine-readable skill capability inventory.

marketingskills keeps a hand-maintained VERSIONS.md so agents can compare
against local copies and detect updates. Here the inventory is derived from
the tree itself (no hand-maintained numbers to drift): counts + sha256 per
file for the four capability layers, plus a per-layer digest, producing a
single capability-manifest.json that `leo-ppt doctor` can cite and diff
after `npx skills add` updates ("did my 137 style briefs actually sync?").

历史 v1 的分层计数规则如下；新 style-index 与 lint 采用独立的共享资产分类，
不再要求新分类计数与以下兼容投影相等：
  styles     every .md under references/styles/, per top-level axis dir;
  briefs     the style-brief subset: top-level *.md under references/styles
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
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import quote

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))
from leo_ppt_generator.styles import style_asset_inventory, style_reference_problems

SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_USAGE = 2

STYLES_DIR = Path("references") / "styles"
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
STYLE_INDEX_VERSION = 1
PAGE_LIMIT = 40
PAGE_BYTES = 12 * 1024


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _hash_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _source_bytes(path: Path) -> bytes:
    body = path.read_bytes()
    if path.name == "_INDEX.md":
        body = re.sub(rb"<!-- style-index:start -->.*?<!-- style-index:end -->", b"", body, flags=re.S)
    return body


def build_style_index(root: Path) -> dict:
    """从源构建索引，与 capability-manifest v1 的历史计数完全分离。"""
    import style_hard_rules

    root = Path(root).resolve()
    styles_root = root / STYLES_DIR
    if not styles_root.is_dir():
        raise ValueError("style_index_source_missing")
    entries = style_asset_inventory(styles_root)
    members = style_hard_rules.current_family_members(styles_root)
    problems = style_reference_problems(entries, members=members if (root / "scripts/style_hard_rules.py").is_file() else None)
    for entry in entries:
        if entry["asset_role"] in {"style", "pool"} or entry["compatibility"]["legacy_callable"] or "asset_outside_root" in entry["diagnostics"]:
            problems.extend({"code": code, "path": entry["path"]} for code in entry["diagnostics"])
        entry["path"] = (STYLES_DIR / entry["path"]).as_posix()
        if Path(entry["path"]).name == "_INDEX.md":
            entry.pop("file_sha256", None)
            entry.pop("style_content_digest", None)
            entry["source_slice_sha256"] = _hash_bytes(_source_bytes(root / entry["path"]))
            entry["digest_scope"] = "authored-regions"
        entry["facet_families"] = sorted(label for label, names in members.items() if entry["name"] in names)
        entry["family_basis"] = "authored" if isinstance(entry.get("taxonomy"), dict) and "families" in entry["taxonomy"] else "legacy-mapping" if entry["facet_families"] else "absent"
    if problems:
        raise ValueError("style_index_source_invalid: " + json.dumps(problems, ensure_ascii=False, sort_keys=True))
    sources = {}
    for entry in entries:
        path = root / entry["path"]
        sources[entry["path"]] = _hash_bytes(_source_bytes(path))
    policy_paths = (
        "scripts/capability_manifest.py", "scripts/style_hard_rules.py",
        "runtime/src/leo_ppt_generator/styles.py",
        "runtime/src/leo_ppt_generator/schemas/style-brief-v1.schema.json",
        "runtime/src/leo_ppt_generator/schemas/style-index-v1.schema.json",
    )
    for rel in policy_paths:
        path = root / rel
        if not path.is_file():
            path = SKILL_DIR / rel
        sources["policy:" + rel] = sha256_file(path)
    source_digest = _hash_bytes(_json_bytes(sources))
    counts = dict(sorted(Counter(entry["asset_role"] for entry in entries).items()))
    aliases = {}
    for entry in entries:
        if entry["asset_role"] not in {"style", "pool"}:
            continue
        for name in [entry["name"], *entry["aliases"]]:
            aliases.setdefault(name.strip().casefold(), []).append(entry["path"])
    navigation = styles_root / "00_索引/_INDEX.md"
    return {"kind": "style-index", "schema_version": 1, "generator_version": STYLE_INDEX_VERSION,
            "navigation_sha256": sha256_file(navigation) if navigation.is_file() else None,
            "source_digest": source_digest, "generation": source_digest, "source_files": sources,
            "counts": {"assets": len(entries), "by_role": counts,
                       "independent_styles": sum(e["asset_role"] == "style" and not e.get("variant_of") for e in entries)},
            "entries": entries, "name_alias_index": {k: sorted(set(v)) for k, v in sorted(aliases.items())}}


def _markdown_text(value) -> str:
    text = " ".join(str(value).split())
    for raw, escaped in (("\\", "\\\\"), ("|", "\\|"), ("`", "\\`"), ("[", "\\["), ("]", "\\]"), ("<", "&lt;"), (">", "&gt;")):
        text = text.replace(raw, escaped)
    return text


def _paged_markdown(prefix: str, title: str, rows: list[str], generation: str, *, page_rows: dict | None = None) -> dict[str, bytes]:
    header = f"# {title}\n\ngeneration: {generation}\n\n"
    pages = []
    chunk = []
    for row in rows:
        if len((header + row + "\n").encode()) + 256 > PAGE_BYTES:
            raise ValueError("style_index_entry_too_large")
        if chunk and (len(chunk) >= PAGE_LIMIT or len((header + "\n".join([*chunk, row]) + "\n").encode()) + 256 > PAGE_BYTES):
            pages.append(chunk)
            chunk = []
        chunk.append(row)
    pages.append(chunk)
    files = {}
    for i, page in enumerate(pages, 1):
        nav = []
        if i > 1:
            nav.append(f"[上一页]({Path(prefix).name}-{i - 1:03d}.md)")
        if i < len(pages):
            nav.append(f"[下一页]({Path(prefix).name}-{i + 1:03d}.md)")
        files[f"{prefix}-{i:03d}.md"] = (header + " | ".join(nav) + "\n\n" + "\n".join(page) + "\n").encode()
        if page_rows is not None:
            page_rows[f"{prefix}-{i:03d}.md"] = page
    return files


def render_style_index(index: dict) -> dict[str, bytes]:
    from jsonschema import Draft7Validator

    schema = json.loads((SKILL_DIR / "runtime/src/leo_ppt_generator/schemas/style-index-v1.schema.json").read_text())
    errors = sorted(Draft7Validator(schema).iter_errors(index), key=lambda error: str(error.path))
    if errors:
        raise ValueError("style_index_schema_invalid: " + errors[0].message)
    generation = index["generation"]
    files = {"catalog.json": _json_bytes(index)}
    by_path = {e["path"]: e for e in index["entries"]}
    name_rows = []
    row_names = {}
    for key, paths in index["name_alias_index"].items():
        refs = []
        for path in paths:
            entry = by_path[path]
            href = quote(os.path.relpath(path, str(STYLES_DIR / "generated")), safe="/.")
            refs.append(f"[{_markdown_text(entry['name'])}]({href}) ({entry['asset_role']})")
        row = f"- {_markdown_text(key)}: " + " / ".join(refs)
        name_rows.append(row)
        row_names[row] = key
    name_pages = {}
    files.update(_paged_markdown("names", "名称与别名", name_rows, generation, page_rows=name_pages))
    facets = {}
    for entry in index["entries"]:
        if entry["asset_role"] != "style":
            continue
        labels = entry["facet_families"] or ["未分类"]
        for label in labels:
            facets.setdefault(label, []).append(entry)
    facet_links = []
    for label, entries in sorted(facets.items()):
        prefix = "facets/family-" + _hash_bytes(label.encode())[:12]
        rows = []
        for entry in entries:
            href = quote(os.path.relpath(entry["path"], str(STYLES_DIR / "generated/facets")), safe="/.")
            display = entry["display"]
            details = []
            for key in ("suitable_for", "visual_character", "density"):
                field = display[key]
                value = field["value"] if field["present"] else "未记录"
                details.append(f"{key}: {_markdown_text(value)}" + (" [摘录]" if field["truncated"] else ""))
            hints = "; ".join(_markdown_text(v["value"]) for v in display["layout_hint"] if v["present"])
            details.append("layout_hint: " + (hints or "未记录"))
            rows.append(f"- [{_markdown_text(entry['name'])}]({href}) | {entry['asset_role']} | {entry['coverage']} | " + " | ".join(details))
        pages = _paged_markdown(prefix, label, rows, generation)
        files.update(pages)
        for path in pages:
            facet_links.append(f"- [{_markdown_text(label)}]({path})")
    name_links = [f"- [{_markdown_text(row_names[rows[0]])} 至 {_markdown_text(row_names[rows[-1]])}]({name})"
                  if rows else f"- [空名称页]({name})" for name, rows in sorted(name_pages.items())]
    files.update(_paged_markdown("by-family", "家族浏览入口", facet_links, generation))
    files.update(_paged_markdown("by-name-alias", "名称索引入口", name_links, generation))
    # 稳定入口只是路由，不复制成员列表。
    files["by-name-alias.md"] = (f"# 风格索引\n\ngeneration: {generation}\n\n"
                                   "- [按名称与别名](by-name-alias-001.md)\n"
                                   "- [按家族](by-family-001.md)\n").encode()
    count_lines = [f"- {role}: {count}" for role, count in index["counts"]["by_role"].items()]
    count_lines.extend([f"- 独立普通风格（排除变体）: {index['counts']['independent_styles']}",
                        f"- 全部源资产: {index['counts']['assets']}",
                        "", "style 包含变体，pool 单列；legacy capability-manifest 的 briefs 是历史兼容口径，不是推荐资格数。"])
    files["counts.md"] = (f"# 资产口径\n\ngeneration: {generation}\n\n" + "\n".join(count_lines) + "\n").encode()
    hashes = {path: _hash_bytes(body) for path, body in sorted(files.items())}
    files["manifest.json"] = _json_bytes({"kind": "style-index-output", "schema_version": 1,
                                         "generation": generation, "source_digest": index["source_digest"],
                                         "files": hashes, "snapshot_digest": _hash_bytes(_json_bytes(hashes))})
    return files


def check_style_index(index: dict, files: dict[str, bytes], directory: Path) -> tuple[dict, int]:
    reason = "none"
    actual_digest = None
    if not directory.is_dir():
        reason = "style_index_missing"
    else:
        try:
            actual = json.loads((directory / "catalog.json").read_text())
            actual_digest = actual.get("source_digest")
            if actual_digest != index["source_digest"]:
                reason = "style_index_stale"
            elif any(not (directory / name).is_file() or (directory / name).read_bytes() != body for name, body in files.items()):
                reason = "style_index_corrupt"
            elif {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()} != set(files):
                reason = "style_index_corrupt"
        except FileNotFoundError:
            reason = "style_index_missing"
        except (OSError, ValueError, AttributeError):
            reason = "style_index_corrupt"
    return {"kind": "style-index-check", "schema_version": 1, "reason_code": reason,
            "expected_source_digest": index["source_digest"], "actual_source_digest": actual_digest,
            "snapshot_digest": json.loads(files["manifest.json"])["snapshot_digest"],
            "next_action": "none" if reason == "none" else "使用独立源摘要查询；由维护者刷新发布索引"}, 0 if reason == "none" else 1


def publish_style_index(files: dict[str, bytes], directory: Path) -> None:
    directory.parent.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("style_index_output_symlink")
    backup = directory.with_name(directory.name + ".previous")
    if backup.exists():
        raise ValueError("style_index_previous_generation_pending")
    with tempfile.TemporaryDirectory(prefix=".style-index-", dir=directory.parent) as name:
        staging = Path(name) / "generation"
        staging.mkdir()
        for path, body in files.items():
            target = staging / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        if directory.exists():
            directory.rename(backup)
        try:
            staging.rename(directory)
        except OSError:
            if backup.exists():
                backup.rename(directory)
            raise
        if backup.exists():
            shutil.rmtree(backup)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    """Style-brief subset with lint_style_index counting rules."""
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
    parser.add_argument("--style-index", action="store_true", help="生成独立的风格索引（不改变旧清单口径）")
    parser.add_argument("--index-out", help="风格索引发布目录")
    parser.add_argument("--check", action="store_true", help="只读检查风格索引是否与源一致")
    args = parser.parse_args(argv)

    root = (Path(args.root).expanduser().resolve() if args.root
            else Path(__file__).resolve().parents[1])
    if not root.is_dir():
        print(f"根目录不存在: {root}", file=sys.stderr)
        return EXIT_USAGE

    if args.style_index:
        if args.compare or args.out:
            parser.error("--style-index 不与旧 --out/--compare 混用")
        directory = Path(args.index_out).expanduser().absolute() if args.index_out else root / STYLES_DIR / "generated"
        try:
            index = build_style_index(root)
            files = render_style_index(index)
            from lint_style_governance import check_document_links
            link_errors = check_document_links({(STYLES_DIR / "generated" / p).as_posix(): body.decode("utf-8")
                                               for p, body in files.items() if p.endswith(".md")}, root)
            if link_errors:
                raise ValueError("style_index_links_invalid: " + "; ".join(link_errors))
            if args.check:
                result, code = check_style_index(index, files, directory)
            elif args.index_out:
                publish_style_index(files, directory)
                result, code = check_style_index(index, files, directory)
            else:
                result, code = index, 0
        except (OSError, ValueError) as exc:
            result, code = {"kind": "style-index-check", "schema_version": 1,
                            "reason_code": "style_index_rebuild_failed", "detail": str(exc)}, 2
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return code
    if args.index_out or args.check:
        parser.error("--index-out/--check 需要 --style-index")

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
