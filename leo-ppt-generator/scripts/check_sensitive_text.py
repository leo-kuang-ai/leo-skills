#!/usr/bin/env python3
r"""Deterministic sensitive-text candidate scanner (R-53, two-layer detection).

Layer 1 (this script): word/pattern surface scan that only LOCATES review
candidates. A hit is a lead, never a verdict — whether a candidate is actually
sensitive is decided by the agent's context layer (data_classification gate,
scene semantics). Zero hits do not prove the text is safe either.

Layer 2 (agent): graded determination per data_classification. See the
--profile notes below.

Rules:
  phone    mainland mobile numbers 1[3-9]\d{9} with digit word-boundaries
           (never matches inside a longer digit run, so ID numbers and order
           IDs do not double-report);
  idcard   18-digit resident ID cards. GB 11643-1999 checksum must pass,
           which removes most false positives. Under --profile confidential
           --strict, checksum-failing 18-digit candidates are ALSO reported
           as low-confidence hits (full-surface mode);
  terms    user-supplied glossary (--custom-terms FILE) for internal
           codenames, project aliases, etc. One term per line, "#" comments
           and blank lines ignored, optional "term|reason" (| or TAB).
           Matched case-insensitively as literals.

Masking discipline: every hit is echoed ONLY as a masked string (keep the
first/last few characters, e.g. 138****5678). The full sensitive value is
never written to stdout/stderr/JSON.

Profiles:
  internal      (default) phone + checksum-validated idcard + custom terms;
  confidential  same set; with --strict additionally keeps checksum-failing
                idcard-shaped candidates for the context layer to judge.

Usage:
  check_sensitive_text.py PATH [--profile internal|confidential] [--strict]
                        [--custom-terms FILE] [--json]

PATH is a UTF-8 text file, or a directory scanned recursively for
.md/.txt files.

Exit codes: 0 = scan completed (candidates are leads, not failures);
2 = usage error (bad args, missing path, unreadable glossary).
Deterministic: sorted files, document-order hits, sorted JSON keys, no
timestamps, stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROFILES = ("internal", "confidential")
TEXT_EXTENSIONS = {".md", ".txt"}

# Digit word-boundaries keep a phone match out of longer digit runs (order IDs,
# bank cards, ID numbers).
PHONE_RE = re.compile(r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])")
IDCARD_RE = re.compile(r"(?<![0-9Xx])[1-9][0-9]{5}(?:18|19|20)[0-9]{2}"
                       r"(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])"
                       r"[0-9]{3}[0-9Xx](?![0-9Xx])")

IDCARD_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
IDCARD_CHECK_CHARS = "10X98765432"

TWO_LAYER_NOTE = ("词面命中只是复核候选，不是结论；零命中也不代表语境安全。"
                  "分级判定由 agent 语境层（data_classification 门）作出。")


def idcard_checksum_ok(value: str) -> bool:
    """GB 11643-1999 checksum for an 18-char ID (last char may be X)."""
    if len(value) != 18:
        return False
    try:
        total = sum(int(ch) * w for ch, w in zip(value[:17], IDCARD_WEIGHTS))
    except ValueError:
        return False
    return IDCARD_CHECK_CHARS[total % 11] == value[17].upper()


def mask(value: str) -> str:
    """Mask a hit, keeping the same total length and a small head/tail.

    Phones keep 3+4 (e.g. 138****5678); everything else keeps 2+2. Values of
    length <= 4 keep only their first character. The full value never leaks.
    """
    n = len(value)
    if n <= 4:
        return value[0] + "*" * (n - 1) if n else value
    if n == 11 and value.isdigit():
        return value[:3] + "*" * 4 + value[7:]
    return value[:2] + "*" * (n - 4) + value[-2:]


def load_custom_terms(path: Path) -> list[dict]:
    """Parse the glossary: one term per line, "#" comments, "term|reason"."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"无法读取词表 {path}: {exc}") from exc
    terms: list[dict] = []
    for line_no, raw_line in enumerate(raw.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[|\t]", line, maxsplit=1)
        term = parts[0].strip()
        if not term:
            continue
        reason = parts[1].strip() if len(parts) > 1 else "用户词表"
        terms.append({
            "pattern": re.compile(re.escape(term), re.IGNORECASE),
            "term_len": len(term),
            "reason": reason,
            "source_line": line_no,
        })
    return terms


def line_col(text: str, offset: int) -> tuple[int, int]:
    """1-based (line, column-in-characters) for a match offset."""
    line = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    return line, offset - last_nl


def scan_text(text: str, profile: str, strict: bool,
              custom_terms: list[dict]) -> list[dict]:
    """Scan one document; returns hits in document order (deterministic)."""
    hits: list[dict] = []

    def add(kind: str, start: int, end: int, extra: dict | None = None) -> None:
        line, col = line_col(text, start)
        hits.append({
            "kind": kind,
            "line": line,
            "column": col,
            "masked": mask(text[start:end]),
            **(extra or {}),
        })

    for m in PHONE_RE.finditer(text):
        add("phone", m.start(), m.end(), {"confidence": "high"})

    for m in IDCARD_RE.finditer(text):
        ok = idcard_checksum_ok(m.group(0))
        if ok:
            add("idcard", m.start(), m.end(),
                {"confidence": "high", "checksum": "valid"})
        elif strict:
            # confidential --strict only: keep checksum-failing candidates as
            # low-confidence leads for the context layer (full-surface mode).
            add("idcard", m.start(), m.end(),
                {"confidence": "low", "checksum": "invalid"})

    for term in custom_terms:
        for m in term["pattern"].finditer(text):
            add("term", m.start(), m.end(),
                {"confidence": "high", "reason": term["reason"],
                 "terms_file_line": term["source_line"]})

    hits.sort(key=lambda h: (h["line"], h["column"], h["kind"]))
    return hits


def iter_input_files(path: Path) -> tuple[list[Path], list[str]]:
    """Expand the input path into a sorted list of files plus skip warnings."""
    if path.is_file():
        return [path], []
    if not path.exists():
        raise ValueError(f"输入路径不存在: {path}")
    if not path.is_dir():
        raise ValueError(f"输入既不是文件也不是目录: {path}")
    files = sorted(p for p in path.rglob("*")
                   if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS)
    skipped = sorted(str(p) for p in path.rglob("*")
                     if p.is_file() and p.suffix.lower() not in TEXT_EXTENSIONS)
    warn = [f"跳过非文本扩展名文件: {s}" for s in skipped]
    return files, warn


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="敏感文本候选扫描（两层检测的词面层：候选≠结论，"
                    "分级判定由 agent 语境层作出）。输出一律遮蔽，不回显完整敏感值。")
    parser.add_argument("path", type=Path, help="UTF-8 文本文件或目录（递归 .md/.txt）")
    parser.add_argument("--profile", choices=PROFILES, default="internal",
                        help="规则分级：internal 默认全开（手机+校验位身份证+词表）；"
                             "confidential 配合 --strict 时加报校验位不过的身份证候选")
    parser.add_argument("--strict", action="store_true",
                        help="全量模式（仅 --profile confidential 下有效）")
    parser.add_argument("--custom-terms", type=Path, default=None,
                        help="用户词表文件：一行一词，# 为注释，可用 | 或 TAB 附原因")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.strict and args.profile != "confidential":
        print("--strict 仅在 --profile confidential 下有效", file=sys.stderr)
        return 2

    custom_terms: list[dict] = []
    if args.custom_terms is not None:
        if not args.custom_terms.is_file():
            print(f"词表文件不存在或不是文件: {args.custom_terms}", file=sys.stderr)
            return 2
        try:
            custom_terms = load_custom_terms(args.custom_terms)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    try:
        files, warnings = iter_input_files(args.path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(f"无法读取（跳过）: {path}: {exc}")
            continue
        hits = scan_text(text, args.profile, args.strict, custom_terms)
        if hits or args.json:
            results.append({"file": str(path), "hits": hits})
        if not args.json:
            for h in hits:
                print(f"{path}:{h['line']}:{h['column']} {h['kind']} "
                      f"{h['masked']} (confidence={h['confidence']})")

    total = sum(len(r["hits"]) for r in results)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    if args.json:
        payload = {
            "profile": args.profile,
            "strict": args.strict,
            "files_scanned": len(files),
            "candidate_count": total,
            "results": results,
            "warnings": warnings,
            "note": TWO_LAYER_NOTE,
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=1,
                  sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(f"候选 {total} 处（文件 {len(files)} 个，profile={args.profile}）")
        print(TWO_LAYER_NOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
