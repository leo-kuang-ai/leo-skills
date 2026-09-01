#!/usr/bin/env python3
"""Transcript timestamp-prefix validator/normalizer (R-03 audio/video route).

Accepted paragraph form: every non-blank, non-"#" content line carries a
timestamp range prefix, canonical form::

    mm:ss-mm:ss text...

The construct mirrors the AI-Media2Doc preprocessing protocol
(`[mm:ss - mm:ss 时间范围秒数:(Xs-Ys)] text`, frontend
VideoToMarkdown/index.vue) so host-produced or user-prepared transcripts from
that lineage validate as-is; they are canonicalized on --fix.

Validation checks, reported with line numbers:
  - missing prefix on a content line;
  - malformed timestamp (minutes 0-99 padded to 2 digits is accepted,
    seconds must be 00-59);
  - end range earlier than start range.

--fix rewrites to canonical form on stdout:
  - AI-Media2Doc-style / spaced prefixes collapse to `mm:ss-mm:ss `;
  - 1-digit minutes are zero-padded;
  - prefix-less content lines inherit the previous line's range (or
    `00:00-00:00` before the first valid line) as the default segment marker.

Exit codes: 0 = all lines conform; 1 = non-conforming lines found (with
--fix, the fixed text is still emitted); 2 = usage error.
Deterministic: pure text transform, stdlib only, no timestamps.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Canonical: mm:ss-mm:ss followed by whitespace then text.
CANONICAL_RE = re.compile(
    r"^([0-9]{1,2}):([0-9]{2})\s*-\s*([0-9]{1,2}):([0-9]{2})(?=\s)")

# AI-Media2Doc lineage: [mm:ss - mm:ss 时间范围秒数:(Xs-Ys)] text
AIM2D_RE = re.compile(
    r"^\[([0-9]{1,2}):([0-9]{2})\s*-\s*([0-9]{1,2}):([0-9]{2})"
    r"(?:\s*时间范围秒数[:：]?\s*\([0-9]+s-[0-9]+s\))?\]\s*")


def parse_ts(minutes: str, seconds: str) -> int | None:
    """Seconds since zero, or None when out of range (mm 0-99, ss 0-59)."""
    mm, ss = int(minutes), int(seconds)
    if mm > 99 or ss > 59:
        return None
    return mm * 60 + ss


def parse_prefix(line: str) -> tuple[int, int, int] | None:
    """Return (start_sec, end_sec, prefix_len) for a valid prefix, else None.

    Accepts the canonical `mm:ss-mm:ss ` form and the AI-Media2Doc bracket
    form. Purely malformed-but-shaped prefixes return None (reported as bad
    format rather than silently re-read).
    """
    for regex in (CANONICAL_RE, AIM2D_RE):
        m = regex.match(line)
        if m:
            start = parse_ts(m.group(1), m.group(2))
            end = parse_ts(m.group(3), m.group(4))
            if start is None or end is None or end < start:
                return None
            return start, end, m.end()
    return None


def analyze(text: str) -> list[dict]:
    """Find non-conforming content lines: file order, deterministic."""
    problems = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if parse_prefix(raw) is None:
            problems.append({
                "line": line_no,
                "reason": ("无时间戳前缀" if not _shaped_like_prefix(raw)
                           else "时间戳格式或区间非法（mm 0-99、ss 00-59、"
                                "结束不早于开始）"),
            })
    return problems


def _shaped_like_prefix(raw: str) -> bool:
    """True when the line starts with something resembling a timestamp."""
    head = raw.lstrip()[:20]
    return bool(re.match(r"^[\[]?[0-9]{1,2}:[0-9]", head))


def _canon_range(start: int, end: int) -> str:
    return f"{start // 60:02d}:{start % 60:02d}-{end // 60:02d}:{end % 60:02d}"


def fix(text: str) -> str:
    """Rewrite to canonical prefixes; inherit the last range when missing."""
    out_lines = []
    last_start, last_end = 0, 0
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(raw)
            continue
        m = CANONICAL_RE.match(raw) or AIM2D_RE.match(raw)
        if m:
            start = parse_ts(m.group(1), m.group(2))
            end = parse_ts(m.group(3), m.group(4))
            if start is None or end is None or end < start:
                # Malformed range: keep the default marker, drop the bad
                # prefix digits — leaving them in the text would re-import
                # the invalid range into the "fixed" output.
                out_lines.append(
                    f"{_canon_range(last_start, last_end)} "
                    f"{raw[m.end():].strip()}")
                continue
            last_start, last_end = start, end
            out_lines.append(f"{_canon_range(start, end)} {raw[m.end():].lstrip()}")
        else:
            out_lines.append(f"{_canon_range(last_start, last_end)} {stripped}")
    return "\n".join(out_lines) + ("\n" if text.endswith(("\n", "\r")) else "")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="转写稿时间戳前缀校验/规范化（段前缀 mm:ss-mm:ss，"
                    "与 AI-Media2Doc 预处理协议同构）；--fix 输出规范化全文")
    parser.add_argument("file", type=Path, help="UTF-8 转写稿文本文件")
    parser.add_argument("--fix", action="store_true",
                        help="输出规范化文本到 stdout（缺前缀行继承上一段区间，"
                             "段首前缺省 00:00-00:00）")
    parser.add_argument("--json", action="store_true",
                        help="以 JSON 输出校验结果")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.file.is_file():
        print(f"输入文件不存在或不是文件: {args.file}", file=sys.stderr)
        return 2
    try:
        text = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"无法读取文件: {exc}", file=sys.stderr)
        return 2

    problems = analyze(text)
    if args.fix:
        sys.stdout.write(fix(text))
    elif args.json:
        json.dump({"file": str(args.file),
                   "conforming": not problems,
                   "problems": problems},
                  sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
        sys.stdout.write("\n")
    else:
        if problems:
            for p in problems:
                print(f"{args.file}:{p['line']}: {p['reason']}")
        print(f"{'不符合' if problems else '符合'}时间戳前缀约定 "
              f"(mm:ss-mm:ss)；问题行 {len(problems)} 个")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
