#!/usr/bin/env python3
"""Export a speaker script (讲稿) from a delivered PPTX or a deck master.

Sources (exactly one required):
  --pptx    read per-slide notes via python-pptx (authoritative post-assembly
            source; this is what the audience-facing deck actually carries);
  --master  read ``- speaker_script：`` bullets per ``## P<N>`` page block from
            a deck-master markdown file (pre-assembly source).

Output is deterministic markdown. Pages without notes are listed honestly as
（无备注）and counted in a footer summary — the exporter never invents script
text. Exit codes: 0 = exported; 2 = usage or IO error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SPEAKER_LINE = re.compile(r"^\s*[-*]?\s*speaker_script\s*[:：]\s*(.+)$")
PAGE_HEADING = re.compile(r"^##\s+P(\d+)\s*(.*)$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def notes_from_pptx(path: Path) -> "list[tuple[str, str]]":
    from pptx import Presentation

    try:
        presentation = Presentation(str(path))
    except Exception as exc:  # pptx raises assorted errors on bad files
        fail(f"cannot open pptx {path}: {exc}")
    pages: list[tuple[str, str]] = []
    for index, slide in enumerate(presentation.slides, start=1):
        title = ""
        if slide.shapes.title is not None and slide.shapes.title.text_frame:
            title = slide.shapes.title.text_frame.text.strip().splitlines()[0] if slide.shapes.title.text_frame.text.strip() else ""
        text = ""
        if slide.has_notes_slide:
            text = slide.notes_slide.notes_text_frame.text.strip()
        pages.append((f"第 {index} 页{('：' + title) if title else ''}", text))
    return pages


def notes_from_master(path: Path) -> "list[tuple[str, str]]":
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read master {path}: {exc}")
    pages: list[tuple[str, str]] = []
    current: "tuple[str, list[str]] | None" = None
    for raw in text.splitlines():
        heading = PAGE_HEADING.match(raw)
        if heading:
            if current is not None:
                pages.append((current[0], "\n".join(current[1]).strip()))
            number, title = heading.group(1), heading.group(2).strip()
            current = (f"第 {number} 页{('：' + title) if title else ''}", [])
            continue
        if current is None:
            continue
        line = SPEAKER_LINE.match(raw)
        if line:
            current[1].append(line.group(1).strip())
    if current is not None:
        pages.append((current[0], "\n".join(current[1]).strip()))
    if not pages:
        fail(f"no '## P<N>' page headings found in {path}")
    return pages


def render(source_label: str, pages: "list[tuple[str, str]]") -> str:
    lines = [f"# 讲稿（来源：{source_label}）", ""]
    missing = 0
    for label, text in pages:
        lines.append(f"## {label}")
        lines.append("")
        if text:
            lines.append(text)
        else:
            lines.append("（无备注）")
            missing += 1
        lines.append("")
    lines.append(f"共 {len(pages)} 页；有备注 {len(pages) - missing} 页，缺备注 {missing} 页（缺页请回母版补 speaker_script 后重建 notes）。")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Export a speaker script from PPTX notes or a deck master.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pptx", help="delivered PPTX file")
    source.add_argument("--master", help="deck-master markdown file")
    parser.add_argument("--out", help="output markdown path (default stdout)")
    args = parser.parse_args(argv)

    if args.pptx:
        pages = notes_from_pptx(Path(args.pptx))
        label = f"PPTX notes — {Path(args.pptx).name}"
    else:
        pages = notes_from_master(Path(args.master))
        label = f"deck master — {Path(args.master).name}"

    output = render(label, pages)
    if args.out:
        try:
            Path(args.out).write_text(output, encoding="utf-8")
        except OSError as exc:
            fail(f"cannot write {args.out}: {exc}")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
