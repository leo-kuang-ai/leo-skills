#!/usr/bin/env python3
"""compute_impact.py — 母版 diff → 受影响页清单（确定性推导）。

输入两个母版版本（old / new），解析数字登记表行、术语表行、页块与页内
交叉引用，输出"改母版后须重建哪些页"的清单：
  - 数字登记表行变化（行键 = 数值 × 页）：行页列指向的页受影响；
  - 术语表词形变化（行键 = 术语 × 缩写）：正文中含该词形的页受影响；
  - 交叉引用传递闭包：受影响页被其他页 cross-ref（「见第 X 页」「见 SX」）
    引用时，引用页一并纳入，迭代至不动点。

语义边界（对齐 chinese-longnovel「事实性修复从受影响点重建投影」）：
仅 diff 数字值与术语词形——纯文案改（不动数字/术语）不产出任何页。

用法：python3 compute_impact.py <old-master.md> <new-master.md> [--json]
退出码：0 正常（含零受影响页）；2 用法或解析失败。
"""
import argparse
import json
import re
import sys
from pathlib import Path

PAGE_RE = re.compile(r"^##\s+(S(\d+)|附)[^\n]*$", re.M)
ALL_SECTION_RE = re.compile(r"^##\s+.*$", re.M)
CROSS_REF_RE = re.compile(r"见[第附]?\s*(\S{1,4}?)\s*页|见\s*S(\d+)")
LEDGER_SECTION_RE = re.compile(r"^##\s+数字登记表\s*$", re.M)
GLOSSARY_SECTION_RE = re.compile(r"^##\s+术语表\s*$", re.M)
PAGE_REF_RE = re.compile(r"S(\d+)", re.I)


class ParseError(Exception):
    """Master text is not parseable as a page-blocked deck master."""


def page_sort_key(pid):
    """S<N> sorts numerically; the appendix page (附) sorts last."""
    if pid == "附":
        return (1, 0)
    return (0, int(pid[1:]))


def split_pages(text):
    """Return ordered [(page_id, header, body)] for `## S<N>` / `## 附` blocks.

    A page body ends at the next page block OR at any other `##` section —
    deck-level tables (数字登记表/术语表) must not leak into the last page's
    body, or term matching would hit the glossary rows themselves.
    """
    matches = list(PAGE_RE.finditer(text))
    if not matches:
        raise ParseError("未发现任何页块（## S<N> 或 ## 附）")
    section_starts = [m.start() for m in ALL_SECTION_RE.finditer(text)]
    pages = []
    for m in matches:
        end = len(text)
        for pos in section_starts:
            if pos > m.start():
                end = pos
                break
        header = m.group(0)
        pid = "附" if header.startswith("## 附") else f"S{m.group(2)}"
        pages.append((pid, header, text[m.start():end]))
    return pages


def _table_rows(text, section_re):
    """Pipe-table rows inside one `## <section>`; returns [] when absent."""
    m = section_re.search(text)
    if not m:
        return []
    rows = []
    for ln in text[m.end():].splitlines():
        s = ln.strip()
        if s.startswith("## "):  # next section ends the table
            break
        if s.startswith("|"):
            rows.append(s)
    return rows


def _cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _is_separator(row):
    # Strip ALL pipes: "| --- | --- |" must classify as a separator row.
    return bool(re.match(r"^[\s:-]+$", row.replace("|", "")))


def _resolve_page_cell(cell, page_seq):
    """Map a ledger/glossary page cell (S3 / 3 / 附 / mixed) to page ids."""
    ids = []
    for m in PAGE_REF_RE.finditer(cell):
        ids.append(f"S{m.group(1)}")
    if not ids and cell.strip() == "附":
        ids.append("附")
    if not ids and cell.strip().isdigit():
        n = int(cell.strip())
        if 1 <= n <= len(page_seq):
            ids.append(page_seq[n - 1])
    valid = set(page_seq)
    return [p for p in ids if p in valid]


def parse_ledger_keys(text, page_seq):
    """Ledger rows keyed by (数值, 页) — only the value/page pair participates
    in the diff (口径/来源 etc. are metadata, not fact-shape changes)."""
    keys = set()
    for row in _table_rows(text, LEDGER_SECTION_RE):
        if _is_separator(row):
            continue
        cells = _cells(row)
        if len(cells) < 2:
            continue
        value = cells[0]
        if not value or value == "数值":  # header row
            continue
        for pid in _resolve_page_cell(cells[1], page_seq):
            keys.add((value, pid))
    return keys


def parse_glossary_keys(text):
    """Glossary rows keyed by (术语, 缩写) — word-shape only, per contract."""
    keys = set()
    for row in _table_rows(text, GLOSSARY_SECTION_RE):
        if _is_separator(row):
            continue
        cells = _cells(row)
        if len(cells) < 2:
            continue
        term = cells[0]
        if not term or term == "术语":  # header row
            continue
        abbr = cells[1] if len(cells) > 1 else ""
        keys.add((term, abbr))
    return keys


def cross_ref_targets(body, page_seq):
    """Page ids referenced from one page body via 「见第 X 页」 / 「见 SX」."""
    targets = set()
    valid = set(page_seq)
    for m in CROSS_REF_RE.finditer(body):
        num, s_no = m.group(1), m.group(2)
        if s_no:
            pid = f"S{s_no}"
            if pid in valid:
                targets.add(pid)
        elif num and num.isdigit():
            n = int(num)
            if 1 <= n <= len(page_seq):
                targets.add(page_seq[n - 1])
    return targets


def _pages_containing(pages, word):
    """Page ids whose body contains the word (>=2 chars to avoid noise)."""
    if len(word) < 2:
        return set()
    return {pid for pid, _h, body in pages if word in body}


def compute_impact(old_text, new_text):
    """Deterministic impact set for old → new master versions."""
    old_pages = split_pages(old_text)
    new_pages = split_pages(new_text)
    old_seq = [pid for pid, _h, _b in old_pages]
    new_seq = [pid for pid, _h, _b in new_pages]

    old_ledger = parse_ledger_keys(old_text, old_seq)
    new_ledger = parse_ledger_keys(new_text, new_seq)
    old_gloss = parse_glossary_keys(old_text)
    new_gloss = parse_glossary_keys(new_text)

    numbers_removed = sorted(old_ledger - new_ledger)
    numbers_added = sorted(new_ledger - old_ledger)
    terms_removed = sorted(old_gloss - new_gloss)
    terms_added = sorted(new_gloss - old_gloss)

    reasons = {}
    new_page_ids = set(new_seq)

    def add(pid, reason):
        if pid in new_page_ids:
            reasons.setdefault(pid, []).append(reason)

    for value, pid in numbers_removed:
        add(pid, f"数字登记表:{value}（移除）")
    for value, pid in numbers_added:
        add(pid, f"数字登记表:{value}（新增）")
    for term, abbr in terms_removed:
        for pid in sorted(_pages_containing(old_pages, term)
                          | _pages_containing(old_pages, abbr)):
            add(pid, f"术语表:{term}（词形移除）")
    for term, abbr in terms_added:
        for pid in sorted(_pages_containing(new_pages, term)
                          | _pages_containing(new_pages, abbr)):
            add(pid, f"术语表:{term}（词形新增）")

    # Transitive closure over cross-refs in the NEW structure: a page that
    # references an affected page must be rebuilt too (iterate to fixpoint).
    refs = {pid: cross_ref_targets(body, new_seq) for pid, _h, body in new_pages}
    changed = True
    while changed:
        changed = False
        for pid, targets in refs.items():
            if pid in reasons:
                continue
            hits = sorted(t for t in targets if t in reasons)
            if hits:
                add(pid, "；".join(f"交叉引用→{t}" for t in hits))
                changed = True

    affected = sorted(reasons, key=page_sort_key)
    for pid in affected:
        reasons[pid] = sorted(set(reasons[pid]))
    return {
        "affected_pages": affected,
        "reasons": {pid: reasons[pid] for pid in affected},
        "numbers_removed": [f"{v}@{p}" for v, p in numbers_removed],
        "numbers_added": [f"{v}@{p}" for v, p in numbers_added],
        "terms_removed": [f"{t}|{a}" for t, a in terms_removed],
        "terms_added": [f"{t}|{a}" for t, a in terms_added],
    }


def main():
    ap = argparse.ArgumentParser(
        description="从两个母版版本的 diff 确定性推导受影响页清单")
    ap.add_argument("old", help="旧母版 markdown 路径")
    ap.add_argument("new", help="新母版 markdown 路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    texts = []
    for raw in (args.old, args.new):
        path = Path(raw)
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"FAIL: 无法读取 {raw}: {exc}", file=sys.stderr)
            return 2
    try:
        result = compute_impact(texts[0], texts[1])
    except ParseError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    affected = result["affected_pages"]
    print("AFFECTED: " + (", ".join(affected) if affected else "(none)"))
    for pid in affected:
        print(f"{pid}\t{'；'.join(result['reasons'][pid])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
