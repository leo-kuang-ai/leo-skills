#!/usr/bin/env python3
"""check_references.py — 学术 deck 文献元数据一致性校验（R-13）。

对母版 markdown（deck-master-v<N>.md）的参考文献页/段与正文含 DOI 行做
确定性校验：同输入同 stdout，不依赖模型、不联网（联网 CrossRef/arXiv
交叉核验属后续工作，本脚本只做材料内核对）。

机制来源：file-github/codex-claude-academic-skills
scientific-toolkit-skill/references/scientific-skills/citation-management/
scripts/validate_citations.py L148-157——DOI 格式正则
``^10\\.\\d{4,}/\\S+$``（invalid_doi_format）与年份合理性检查思想
（上游快照 2026-08-31）。本包在其上分层：DOI 格式非法与信息不一致为
FAIL（exit 1，交付前拦截对象，strict 档并入交付披露）；GB/T 7714
格式提示保持 WARN 不阻断。

检测项：
  1. DOI 格式（FAIL）：形如 DOI 字段的值（``DOI:`` / ``doi.org/`` 引导）
     须匹配 ``^10\\.\\d{4,}/\\S+$``；不匹配即 FAIL。
  2. 同文献多处引用一致性（FAIL）：母版内按 DOI 分组，文献页条目间
     年份或题名不一致即 FAIL；按题名分组，条目间 DOI 不一致即 FAIL
     （正文含 DOI 行并入 DOI 分组参与交叉核对）。
  3. GB/T 7714 简单格式提示（WARN）：条目缺文献类型标识（[J]/[C]/[M]/
     [D]/[N]/[R]/[S]/[P]/[A]/[EB/OL]/[DB/OL]/[J/OL]）、缺年份、年份在
     1600–当前年+5 之外。
  4. 母版无参考文献页/段：INFO 一条跳过，exit 0（向后兼容，非学术
     母版零影响）。

用法：python3 scripts/check_references.py <deck-master.md> [--json]
输出：stdout 人类可读报告（或 --json 全量 JSON）；退出码
  0 通过（WARN/INFO 不改退出码）/ 1 文献信息不一致或 DOI 格式非法 /
  2 用法或读取错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Vocabularies and thresholds (edit here, not in detectors).
# ---------------------------------------------------------------------------

# A reference section is a `## ` heading carrying any of these markers.
REF_HEADER_RE = re.compile(r"参考文献|文献页|引用文献|references", re.I)
# Bibliography entry lines inside the reference section. Numbered forms
# beyond the ASCII bullet/`[N]` shapes (full-width ［1］, "1." / "1、") are
# recognized too so entries never drop silently (see parse_master_entries).
ENTRY_LINE_RE = re.compile(
    r"^\s*(?:[-*]|[\[［【]\d+[\]］】]|\d+[.、．])\s*(.+)$")

# DOI field carriers: "DOI: x" / "doi：x" / "doi.org/x". The captured token
# is then validated against DOI_VALID_RE.
DOI_LABEL_RE = re.compile(
    r"(?:doi\s*[:：=]\s*|doi\.org/)([^\s，，;;。》」】)]+)", re.I)
DOI_VALID_RE = re.compile(r"^10\.\d{4,}/\S+$")
# Bare well-formed DOIs (no label) still join consistency grouping.
DOI_BARE_RE = re.compile(r"(?<![0-9A-Za-z])(10\.\d{4,}/[^\s，，;;。》」】)]+)")
DOI_TRAILING_PUNCT = ".,;:、。"

YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
YEAR_MIN = 1600

# GB/T 7714 document-type tags (closed set, case-insensitive).
GB_TYPE_TAG_RE = re.compile(
    r"\[(?:J|C|M|D|N|R|S|P|A|EB/OL|DB/OL|J/OL|CP/OL)\]", re.I)
TITLE_CJK_BRACKET_RE = re.compile(r"[《<]([^《》<>]{4,})[》>]")

PAGE_HEADER_RE = re.compile(r"^##\s+(.+)$", re.M)


class ReferenceParseError(Exception):
    """Raised on unreadable or unusable master input."""


class RefEntry:
    """One DOI-bearing line: bibliography entry or in-text citation line."""

    __slots__ = ("page", "line_no", "raw", "dois", "year", "title",
                 "type_tag", "in_bibliography")

    def __init__(self, page, line_no, raw, dois, year, title, type_tag,
                 in_bibliography):
        self.page = page
        self.line_no = line_no
        self.raw = raw
        self.dois = dois
        self.year = year
        self.title = title
        self.type_tag = type_tag
        self.in_bibliography = in_bibliography

    @property
    def where(self):
        return f"第 {self.line_no} 行"


def normalize_doi(token: str) -> str:
    return token.rstrip(DOI_TRAILING_PUNCT).strip().casefold()


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", title).casefold()


def extract_title(line: str):
    """Title = CJK book-bracket content, else the segment right before the
    GB/T 7714 type tag (``作者. 题名[J]. 出处…``); None when neither exists."""
    m = TITLE_CJK_BRACKET_RE.search(line)
    if m:
        return m.group(1).strip()
    tag = GB_TYPE_TAG_RE.search(line)
    if not tag:
        return None
    segments = [s.strip() for s in re.split(r"[.。]", line[:tag.start()]) if s.strip()]
    return segments[-1] if segments else None


def parse_master_entries(text: str) -> "tuple[list[RefEntry], bool]":
    """Split the master into DOI-bearing entries plus a has-section flag.

    Reference-section entry lines become bibliography entries; DOI-bearing
    lines elsewhere become in-text citation occurrences (they join DOI-group
    cross-checks but carry no full bibliographic record).
    """
    entries: list[RefEntry] = []
    in_ref_section = False
    page = "文档头"
    for idx, raw in enumerate(text.splitlines(), start=1):
        header = PAGE_HEADER_RE.match(raw)
        if header:
            in_ref_section = bool(REF_HEADER_RE.search(header.group(1)))
            page = header.group(1).strip()
            continue
        stripped = raw.strip()
        if not stripped:
            continue
        entry_m = ENTRY_LINE_RE.match(raw)
        # Inside the reference section every non-empty line is an entry, with
        # or without a recognized bullet/numbering prefix: full-width ［1］ or
        # "1." numbering must not silently drop entries (and flip has_section
        # to a misleading "no reference section" INFO).
        in_bib = in_ref_section
        if not in_bib and not DOI_LABEL_RE.search(raw) and not DOI_BARE_RE.search(raw):
            continue
        content = entry_m.group(1) if entry_m else stripped
        dois = []
        for m in DOI_LABEL_RE.finditer(content):
            dois.append(m.group(1))
        for m in DOI_BARE_RE.finditer(content):
            token = m.group(1)
            if normalize_doi(token) not in {normalize_doi(d) for d in dois}:
                dois.append(token)
        year_m = YEAR_RE.search(content)
        tag_m = GB_TYPE_TAG_RE.search(content) if in_bib else None
        entries.append(RefEntry(
            page=page, line_no=idx, raw=content,
            dois=[normalize_doi(d) for d in dois if normalize_doi(d)],
            year=year_m.group(1) if year_m else None,
            title=extract_title(content) if in_bib else None,
            type_tag=tag_m.group(0) if tag_m else None,
            in_bibliography=in_bib,
        ))
    has_section = any(e.in_bibliography for e in entries)
    return entries, has_section


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def _finding(severity, page, where, message):
    return {"severity": severity, "page": page, "where": where,
            "message": message}


def _excerpt(text, limit=32):
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…"


def check_doi_format(entries):
    """Label-carried DOI tokens must match ^10\\.\\d{4,}/\\S+$ (FAIL)."""
    findings = []
    seen = set()
    for entry in entries:
        for m in DOI_LABEL_RE.finditer(entry.raw):
            token = normalize_doi(m.group(1))
            if not token or (entry.page, entry.line_no, token) in seen:
                continue
            seen.add((entry.page, entry.line_no, token))
            if not DOI_VALID_RE.match(token):
                findings.append(_finding(
                    "FAIL", entry.page, entry.where,
                    f"DOI 格式非法「{token}」——须形如 10.<4位以上数字>/<后缀>，"
                    "回母版核对 DOI 是否抄错"))
    return findings


def check_consistency(entries):
    """Same DOI → same year/title across bibliography entries; same title →
    same DOI. In-text lines join the DOI grouping for cross-checking."""
    findings = []
    by_doi: dict[str, list[RefEntry]] = {}
    for entry in entries:
        for doi in entry.dois:
            by_doi.setdefault(doi, []).append(entry)
    for doi, group in sorted(by_doi.items()):
        bib = [e for e in group if e.in_bibliography]
        if len(bib) < 2:
            continue
        years = sorted({e.year for e in bib if e.year})
        if len(years) > 1:
            findings.append(_finding(
                "FAIL", " / ".join(dict.fromkeys(e.page for e in bib)), "",
                f"同 DOI「{doi}」年份不一致（{' vs '.join(years)}，"
                f"第 {'、'.join(str(e.line_no) for e in bib)} 行）——"
                "同一文献多处引用信息须一致，回母版核对"))
        titles = {normalize_title(e.title) for e in bib if e.title}
        if len(titles) > 1:
            shown = " vs ".join(_excerpt(t, 24) for t in sorted(titles))
            findings.append(_finding(
                "FAIL", " / ".join(dict.fromkeys(e.page for e in bib)), "",
                f"同 DOI「{doi}」题名不一致（{shown}，"
                f"第 {'、'.join(str(e.line_no) for e in bib)} 行）——"
                "同一文献多处引用信息须一致，回母版核对"))

    by_title: dict[str, list[RefEntry]] = {}
    for entry in entries:
        if entry.in_bibliography and entry.title:
            by_title.setdefault(normalize_title(entry.title), []).append(entry)
    for title, group in sorted(by_title.items()):
        if len(group) < 2:
            continue
        dois = sorted({d for e in group for d in e.dois})
        if len(dois) > 1:
            findings.append(_finding(
                "FAIL", " / ".join(dict.fromkeys(e.page for e in group)), "",
                f"同题名「{_excerpt(title, 24)}」DOI 不一致（"
                f"{' vs '.join(dois)}，第 {'、'.join(str(e.line_no) for e in group)} 行）"
                "——同一文献多处引用信息须一致，回母版核对"))
    return findings


def check_gbt7714(entries):
    """Bibliography entries: type tag / year presence and plausibility (WARN)."""
    findings = []
    max_year = date.today().year + 5
    for entry in entries:
        if not entry.in_bibliography:
            continue
        if not entry.type_tag:
            findings.append(_finding(
                "WARN", entry.page, entry.where,
                "条目缺 GB/T 7714 文献类型标识（[J]/[C]/[M]/[D]/[EB/OL] 等）——"
                "补齐后再交付"))
        if not entry.year:
            findings.append(_finding(
                "WARN", entry.page, entry.where,
                "条目缺出版年份——补齐年份后再交付"))
        elif not (YEAR_MIN <= int(entry.year) <= max_year):
            findings.append(_finding(
                "WARN", entry.page, entry.where,
                f"年份「{entry.year}」在合理范围（{YEAR_MIN}–{max_year}）之外——"
                "回母版核对是否抄错"))
    return findings


def run_checks(entries, has_section):
    findings = []
    if not has_section:
        findings.append(_finding(
            "INFO", "全 deck", "",
            "母版无参考文献页/段，文献元数据校验跳过（联网 CrossRef/arXiv "
            "交叉核验属后续，本脚本只做材料内核对）"))
        return findings
    findings += check_doi_format(entries)
    findings += check_consistency(entries)
    findings += check_gbt7714(entries)
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render_human(file_name, entries, findings):
    bib = sum(1 for e in entries if e.in_bibliography)
    lines = [
        f"REFERENCES: {file_name}",
        f"ENTRIES: {len(entries)} 条（文献页条目 {bib} / 正文含 DOI 行 "
        f"{len(entries) - bib}）——离线材料内核对，未联网交叉核验",
    ]
    for f in findings:
        loc = " ".join(x for x in (f["page"], f["where"]) if x)
        lines.append(f"[{f['severity']}] " + (f"{loc}：" if loc else "") + f["message"])
    counts = {sev: sum(1 for f in findings if f["severity"] == sev)
              for sev in ("FAIL", "WARN", "INFO")}
    lines.append(
        f"SUMMARY: FAIL {counts['FAIL']} / WARN {counts['WARN']} / "
        f"INFO {counts['INFO']} —— FAIL 为文献信息不一致或 DOI 格式非法，"
        "回母版核对后重跑；strict 档 FAIL 并入交付披露")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="学术 deck 文献元数据一致性校验（R-13，离线）")
    parser.add_argument("master", help="母版 markdown 路径（deck-master-v<N>.md）")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 而非人类可读报告")
    args = parser.parse_args(argv)

    path = Path(args.master)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: 无法读取母版 {path}: {exc}", file=sys.stderr)
        return 2
    if not text.strip():
        print("ERROR: 母版为空文件", file=sys.stderr)
        return 2

    entries, has_section = parse_master_entries(text)
    findings = run_checks(entries, has_section)
    fails = sum(1 for f in findings if f["severity"] == "FAIL")
    exit_code = 1 if fails else 0

    if args.json:
        payload = {
            "file": str(path),
            "entries": {
                "total": len(entries),
                "bibliography": sum(1 for e in entries if e.in_bibliography),
                "citations": sum(1 for e in entries if not e.in_bibliography),
            },
            "exit": exit_code,
            "counts": {sev: sum(1 for f in findings if f["severity"] == sev)
                       for sev in ("FAIL", "WARN", "INFO")},
            "online_crosscheck": "not-performed (offline; CrossRef/arXiv 属后续)",
            "findings": findings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(render_human(path.name, entries, findings))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
