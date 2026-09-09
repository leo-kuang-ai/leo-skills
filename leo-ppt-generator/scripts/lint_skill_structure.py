#!/usr/bin/env python3
r"""Skill structure lint (R-57): entry visibility + broken-link guard.

M1 lesson: the 19-case wipe was caused by an "entry visibility gap" — the
capability existed in references/scripts but SKILL.md never mentioned it.
This lint borrows the validate-skills.sh idea (marketingskills) and asserts
the structural contract that keeps the entry honest:

  1. SKILL.md line budget: hard limit --max-lines (default 500, agentskills
     spec), WARN threshold --warn-lines (default 450). Over budget → move
     detail to references/.
  2. Referenced-file existence: every relative path inside SKILL.md and
     references/*.md that points into a known skill top-level directory
     (references/ prompts/ scripts/ assets/ runtime/ samples/ bench/
     evals/ agents/ patches/ templates/) must exist on disk. Sources:
     markdown links ``[x](path)`` and backtick paths (``references/x.md``).
     - URLs, anchors, and placeholder paths (``<run>/``, ``${}``) are
       ignored;
     - a path that matches no file but is a filename PREFIX of an existing
       sibling counts as present (``patches/0007`` refers to
       ``patches/0007-codex-*.patch``);
     - lines carrying upstream-narrative words (上游/改编自/upstream/vendor/
       frontend-slides/未转写) are skipped: they cite the upstream repo's
       files, not ours;
     - vendored source-provenance docs (``template-library/reference/sources/retired-styles-tree/styles/0[45]_来源_*``)
       are excluded from scanning: their links target the upstream asset
       tree we deliberately do not copy.
  3. Frontmatter contract: SKILL.md must start with YAML frontmatter and
     carry non-empty ``name`` and ``description`` (agentskills spec: the
     only required fields).

Usage:
  lint_skill_structure.py [--root DIR] [--max-lines N] [--warn-lines N]

Exit codes: 0 = clean (warnings allowed); 1 = errors found; 2 = usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

DEFAULT_MAX_LINES = 500
DEFAULT_WARN_LINES = 450
TOP_DIRS = ("references/", "prompts/", "scripts/", "assets/", "templates/",
            "runtime/", "samples/", "bench/", "evals/", "agents/", "patches/")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
TICK_RE = re.compile(r"`([^`\n]+)`")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
NAME_RE = re.compile(r"^name:\s*(\S.*)$", re.M)
DESC_RE = re.compile(r"^description:\s*(\S.*)$", re.M)
# Upstream narrative context: the line cites another repo's file, not ours.
UPSTREAM_WORDS = ("上游", "改编自", "upstream", "vendor", "frontend-slides", "未转写")
# Vendored provenance docs whose links target the upstream asset tree.
VENDORED_PART_PREFIXES = ("04_来源", "05_来源")


def is_plausible_ref(ref: str) -> bool:
    """Only skill-internal, literal relative paths are checkable."""
    if not ref or ref.startswith(("http://", "https://", "mailto:", "//", "#")):
        return False
    if not ref.startswith(TOP_DIRS):
        return False
    return not any(ch in ref for ch in "<>${}*\\ ")


def ref_exists(root: Path, ref: str) -> bool:
    """Exact existence, or filename-prefix match against siblings."""
    target = root / ref
    if target.exists():
        return True
    if not ref.endswith("/"):
        parent = target.parent
        if parent.is_dir():
            return any(sibling.name.startswith(target.name) for sibling in parent.iterdir())
    return False


def extract_refs(line: str) -> list[str]:
    refs = list(LINK_RE.findall(line)) + list(TICK_RE.findall(line))
    return [r.split("#")[0].strip() for r in refs if is_plausible_ref(r.split("#")[0].strip())]


def lint(root: Path, max_lines: int, warn_lines: int,
         errors: list[str], warnings: list[str]) -> list[Path]:
    """Run all three checks; returns the scanned file list (for --json)."""
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        errors.append(f"SKILL.md 不存在: {skill_path}")
        return []
    skill_text = skill_path.read_text(encoding="utf-8", errors="replace")

    # --- Check 1: line budget ------------------------------------------------
    line_count = len(skill_text.splitlines())
    if line_count > max_lines:
        errors.append(
            f"SKILL.md 共 {line_count} 行，超过上限 {max_lines}（把细节移入 references/）")
    elif line_count > warn_lines:
        warnings.append(
            f"SKILL.md 共 {line_count} 行，超过预警线 {warn_lines}（接近 {max_lines} 上限）")

    # --- Check 3: frontmatter contract --------------------------------------
    fm = FRONTMATTER_RE.match(skill_text)
    if fm is None:
        errors.append("SKILL.md 缺 YAML frontmatter（--- 块）")
    else:
        if not NAME_RE.search(fm.group(1)):
            errors.append("frontmatter 缺非空 name 字段")
        if not DESC_RE.search(fm.group(1)):
            errors.append("frontmatter 缺非空 description 字段")

    # --- Check 2: referenced-file existence ---------------------------------
    files = [skill_path]
    refs_dir = root / "references"
    if refs_dir.is_dir():
        files += sorted(
            p for p in refs_dir.rglob("*.md")
            if not any(part.startswith(VENDORED_PART_PREFIXES) for part in p.parts)
        )
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"无法读取 {path}: {exc}")
            continue
        prev_line = ""
        for line_no, line in enumerate(text.splitlines(), start=1):
            # Upstream-narrative context may sit on the reference line or the
            # line right above it ("> 上游出处：\n> xhs-skill `path`").
            if not any(word in line or word in prev_line for word in UPSTREAM_WORDS):
                for ref in extract_refs(line):
                    if not ref_exists(root, ref):
                        errors.append(
                            f"断链: {path.relative_to(root)}:{line_no} 引用 "
                            f"{ref} 不存在")
            prev_line = line
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="技能结构 lint（R-57）：行数上限 / 引用文件存在性 / frontmatter 契约")
    parser.add_argument("--root", default=None, help="技能根目录（默认脚本所在技能）")
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument("--warn-lines", type=int, default=DEFAULT_WARN_LINES)
    args = parser.parse_args(argv)

    root = (Path(args.root).expanduser().resolve() if args.root
            else Path(__file__).resolve().parents[1])
    if not root.is_dir():
        print(f"根目录不存在: {root}", file=sys.stderr)
        return EXIT_USAGE
    if args.warn_lines > args.max_lines:
        print("--warn-lines 不得大于 --max-lines", file=sys.stderr)
        return EXIT_USAGE

    errors: list[str] = []
    warnings: list[str] = []
    files = lint(root, args.max_lines, args.warn_lines, errors, warnings)

    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"lint_skill_structure: scanned {len(files)} files, "
          f"{len(warnings)} warning(s), {len(errors)} error(s)")
    return EXIT_ERROR if errors else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
