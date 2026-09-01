#!/usr/bin/env python3
r"""Capability manifest (R-60): machine-readable skill capability inventory.

marketingskills keeps a hand-maintained VERSIONS.md so agents can compare
against local copies and detect updates. Here the inventory is derived from
the tree itself (no hand-maintained numbers to drift): counts + sha256 per
file for the four capability layers, plus a per-layer digest, producing a
single capability-manifest.json that `leo-ppt doctor` can cite and diff
after `npx skills add` updates ("did my 137 style briefs actually sync?").

Layers and counting rules (brief counting mirrors lint_style_index.py so
the two stay mutually checkable):
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
from pathlib import Path

SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_USAGE = 2

STYLES_DIR = Path("references") / "styles"
REFERENCES_DIR = Path("references")
SCRIPTS_DIR = Path("scripts")
# Brief subset counting must stay aligned with lint_style_index.py.
BRIEF_RULES = (
    ("", "top"),
    ("01_通用母版", "all"),
    ("02_行业内容域", "exclude_rules"),
    ("03_场景用途结构", "all"),
    (Path("05_来源_awesome-gpt-image-2") / "借鉴新增", "all"),
)
AXIS_NAME_RE = re.compile(r"^\d{2}_")


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
    args = parser.parse_args(argv)

    root = (Path(args.root).expanduser().resolve() if args.root
            else Path(__file__).resolve().parents[1])
    if not root.is_dir():
        print(f"根目录不存在: {root}", file=sys.stderr)
        return EXIT_USAGE

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
