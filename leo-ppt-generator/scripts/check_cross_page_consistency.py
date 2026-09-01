#!/usr/bin/env python3
"""check_cross_page_consistency.py — 长 deck 跨页一致性硬门禁（R-40）。

输入 confirmed 母版，检查三类跨页漂移，输出四分类（对齐
chinese-longnovel 一致性审查四分类，映射为 阻断/风险/承诺状态/通过）：

  ① 术语同实体异写：术语表内两行归一后同形，或正文页出现表内术语的
     变体形态——确定性归一规则：逐字符 NFKC（全半角折叠）→ 去空白 →
     casefold；归一后与表内术语同形而原文不同（差异仅限空格插入/全半角/
     大小写）即判变体。纯 ASCII 术语（如缩写）要求变体窗口两侧不是
     ASCII 字母数字（避免「ai」命中「said」类误报）；
  ② 页码编号连续性：`## S<N>` 序号跳号（缺号）或重复；
  ③ 固定件声明一致：页面正文含「固定件」的行按 `页码：规格` /
     `页脚：规格` / `署名位：规格` 解析（可多对，分号/逗号分隔；规格
     归一 = 去空白+全半角+大小写），同 kind 跨页出现不同规格即冲突。

四分类与退出码：
  - 阻断：①②③ 的发现项，仅当 deck 页数 > --threshold（默认 30）——
    存在即 exit 1（长 deck 漂移项不再淹没于日志）；
  - 风险：页数 ≤ threshold 时阻断类整体降级为风险（报告级，向后兼容，
    exit 0），另含固定件声明无法解析、承诺状态枚举非法；
  - 承诺状态：复用 deck-promises 状态（open/fulfilled/closed，与
    check_master_contract R-34 同形解析）逐条列出，open 项提示组装前
    须闭环；兑现核对归 R-34 判据，本类不占退出码；
  - 通过：各检查族无发现项的通过结论（无 `## 术语表` 节的存量母版
    按跳过-兼容处理，不报错）。

页数口径：母版内全部页块数（`## S<N>` + `## 附`）。

用法：python3 check_cross_page_consistency.py <deck-master.md> [--threshold 30]
退出码：0 通过或仅风险级发现；1 存在阻断级发现（页数 > threshold）；2 用法或
解析失败。
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

PAGE_RE = re.compile(r"^##\s+(S(\d+)|附)[^\n]*$", re.M)
ALL_SECTION_RE = re.compile(r"^##\s+.*$", re.M)
GLOSSARY_SECTION_RE = re.compile(r"^##\s+术语表\s*$", re.M)
PROMISES_BLOCK_RE = re.compile(r"^\s*deck-promises[：:][ \t]*$", re.M)
PROMISE_STATUSES = {"open", "fulfilled", "closed"}
FIXED_KINDS = ("页码", "页脚", "署名位")
# One declaration line may carry multiple `kind: spec` pairs; the lookahead
# splits a pair at the next kind keyword or at end of line.
FIXED_SPEC_RE = re.compile(
    r"(页码|页脚|署名位)\s*[：:](.*?)(?=\s*(?:页码|页脚|署名位)\s*[：:]|$)")
ASCII_ONLY_RE = re.compile(r"[0-9a-z]+$")
# Trailing list separators left over after pair splitting.
TRAILING_SEP_CHARS = "，,；;。、|"

EXIT_OK = 0
EXIT_BLOCK = 1
EXIT_USAGE = 2

BLOCK = "阻断"
RISK = "风险"
PROMISE = "承诺状态"
PASS = "通过"


class ParseError(Exception):
    """Master text is not parseable as a page-blocked deck master."""


# ---------------------------------------------------------------- parsing

def split_pages(text):
    """Ordered [(page_id, body)]; deck-level tables stop the last page body."""
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
        pid = "附" if m.group(0).startswith("## 附") else f"S{m.group(2)}"
        pages.append((pid, text[m.start():end]))
    return pages


def _table_rows(text, section_re):
    m = section_re.search(text)
    if not m:
        return []
    rows = []
    for ln in text[m.end():].splitlines():
        s = ln.strip()
        if s.startswith("## "):
            break
        if s.startswith("|"):
            rows.append(s)
    return rows


def _cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _is_separator(row):
    return bool(re.match(r"^[\s:-]+$", row.replace("|", "")))


def parse_glossary(text):
    """Rows of the `## 术语表` pipe table as [(术语, 缩写)]; [] when absent."""
    rows = []
    for row in _table_rows(text, GLOSSARY_SECTION_RE):
        if _is_separator(row):
            continue
        cells = _cells(row)
        if len(cells) < 2:
            continue
        term = cells[0]
        if not term or term == "术语":  # header row
            continue
        rows.append((term, cells[1] if len(cells) > 1 else ""))
    return rows


def _adjacent_pipe_rows(lines, start):
    rows = []
    for ln in lines[start:]:
        if ln.strip().startswith("|"):
            rows.append(ln.strip())
        else:
            break
    return rows


def parse_promise_rows(text):
    """deck-promises table rows (top-level or indented sub-table); [] if none."""
    lines = text.splitlines()
    rows = []
    for i, ln in enumerate(lines):
        if PROMISES_BLOCK_RE.match(ln):
            rows.extend(_adjacent_pipe_rows(lines, i + 1))
    return rows


def strip_promise_blocks(text):
    """Remove deck-promises blocks so their table cells cannot leak into
    page bodies and fake term-variant hits (pages keep their headers)."""
    lines = text.splitlines()
    drop = set()
    for i, ln in enumerate(lines):
        if PROMISES_BLOCK_RE.match(ln):
            drop.add(i)
            for j in range(i + 1, len(lines)):
                if lines[j].strip().startswith("|"):
                    drop.add(j)
                else:
                    break
    if not drop:
        return text
    return "\n".join(ln for i, ln in enumerate(lines) if i not in drop)


# ---------------------------------------------------------- normalization

def norm_form(s):
    """Deterministic sameness key: NFKC width fold → drop whitespace → fold."""
    out = []
    for ch in s:
        if ch.isspace():
            continue
        out.append(unicodedata.normalize("NFKC", ch))
    return "".join(out).casefold()


def norm_with_map(s):
    """(normalized string, raw index per normalized char) for window recovery."""
    chars, idxs = [], []
    for i, ch in enumerate(s):
        if ch.isspace():
            continue
        for nc in unicodedata.normalize("NFKC", ch).casefold():
            chars.append(nc)
            idxs.append(i)
    return "".join(chars), idxs


def _dedupe(items):
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


# ----------------------------------------------------------------- checks

def check_numbering(pages):
    """S<N> numbering must be contiguous from S1 with no repeats."""
    nums = [int(pid[1:]) for pid, _body in pages if pid != "附"]
    items = []
    if not nums:
        return items
    counts = {}
    for n in nums:
        counts[n] = counts.get(n, 0) + 1
    top = max(nums)
    for n in sorted(set(range(1, top + 1)) - set(counts)):
        items.append((BLOCK, f"页码跳号：S{n} 缺失（现有最大页号 S{top}）"))
    for n in sorted(n for n, c in counts.items() if c > 1):
        items.append((BLOCK, f"页码重复：S{n} 出现 {counts[n]} 次"))
    return items


def check_glossary_internal(rows):
    """Glossary rows whose normalized term/abbr collide but raw differ."""
    items = []
    for col, label in ((0, "同实体异写"), (1, "缩写异写")):
        groups = {}
        for row in rows:
            raw = row[col]
            key = norm_form(raw)
            if len(key) < 2:
                continue
            groups.setdefault(key, []).append(raw)
        for key in sorted(groups):
            raws = sorted(set(groups[key]))
            if len(raws) > 1:
                items.append((BLOCK, f"术语表内{label}：{' / '.join(raws)}"))
    return items


def check_body_variants(pages, rows):
    """Body occurrences that normalize onto a glossary form but differ raw."""
    page_norms = [(pid, body, norm_with_map(body)) for pid, body in pages]
    items = []
    for term, abbr in rows:
        for canon in (term, abbr):
            key = norm_form(canon)
            if not canon or len(key) < 2:
                continue
            latin = bool(ASCII_ONLY_RE.fullmatch(key))
            for pid, body, (chars, idxs) in page_norms:
                start = 0
                while True:
                    a = chars.find(key, start)
                    if a < 0:
                        break
                    b = a + len(key)
                    raw = body[idxs[a]:idxs[b - 1] + 1]
                    if raw != canon:
                        prev_ch = body[idxs[a] - 1] if idxs[a] > 0 else ""
                        k = idxs[b - 1] + 1
                        next_ch = body[k] if k < len(body) else ""
                        glued = ((prev_ch.isascii() and prev_ch.isalnum())
                                 or (next_ch.isascii() and next_ch.isalnum()))
                        if not (latin and glued):
                            items.append(
                                (BLOCK, f"{pid}：「{raw}」是表内术语"
                                        f"「{canon}」的变体（去空格/全半角"
                                        "归一后同形）"))
                    start = a + 1
    return _dedupe(items)


def check_fixed_elements(pages):
    """Same fixed-element kind declared with different specs across pages.

    Returns (findings, kinds_seen, has_declaration_lines).
    """
    items = []
    specs = {}  # (kind, norm spec) -> [page ids]
    kinds_seen = set()
    has_lines = False
    for pid, body in pages:
        for ln in body.splitlines():
            if "固定件" not in ln:
                continue
            has_lines = True
            pairs = [(m.group(1), norm_form(m.group(2)).rstrip(TRAILING_SEP_CHARS))
                     for m in FIXED_SPEC_RE.finditer(ln)]
            if not pairs:
                items.append((RISK, f"{pid}：固定件声明无法解析（须为"
                                    "「页码/页脚/署名位：规格」形式）"))
                continue
            for kind, spec in pairs:
                kinds_seen.add(kind)
                if not spec:
                    items.append((RISK, f"{pid}：固定件「{kind}」规格为空"))
                    continue
                specs.setdefault((kind, spec), []).append(pid)
    by_kind = {}
    for (kind, spec), pids in specs.items():
        by_kind.setdefault(kind, {})[spec] = pids
    for kind in FIXED_KINDS:
        variants = by_kind.get(kind)
        if not variants or len(variants) < 2:
            continue
        detail = "；".join(f"「{spec}」@{','.join(pids)}"
                          for spec, pids in sorted(variants.items()))
        items.append((BLOCK, f"固定件声明冲突（{kind}）：{detail}"))
    return items, sorted(kinds_seen), has_lines


def check_promises(text):
    """Report deck-promises states under the promise category (no exit impact)."""
    rows = parse_promise_rows(text)
    items = []
    if not rows:
        return items
    data = [r for r in rows[1:] if not _is_separator(r)]
    counts = {st: 0 for st in sorted(PROMISE_STATUSES)}
    for idx, row in enumerate(data, start=1):
        cells = _cells(row)
        if len(cells) < 4:
            items.append((RISK, f"deck-promises 行{idx}：列数不足"
                                f"（{len(cells)} < 4）"))
            continue
        promise, anchor, payoff, status = cells[:4]
        if status not in PROMISE_STATUSES:
            items.append((RISK, f"deck-promises「{promise}」：状态「{status}」"
                                f"不在封闭枚举 {sorted(PROMISE_STATUSES)}"))
            continue
        counts[status] += 1
        items.append((PROMISE, f"「{promise}」：{status}"
                              f"（锚页 {anchor}，兑现页 {payoff}）"))
    total = sum(counts.values())
    items.append((PROMISE, f"共 {total} 条承诺"
                          f"（open {counts['open']} / fulfilled "
                          f"{counts['fulfilled']} / closed "
                          f"{counts['closed']}）；open 项组装前须闭环"
                          "（兑现核对归 check_master_contract R-34 判据）"))
    return items


# ------------------------------------------------------------------ main

def analyze(text, threshold):
    """Return (lines, exit_code) for one master document."""
    pages = split_pages(strip_promise_blocks(text))
    page_count = len(pages)
    gloss_rows = parse_glossary(text)

    term_findings = (check_glossary_internal(gloss_rows)
                     + check_body_variants(pages, gloss_rows))
    numbering_findings = check_numbering(pages)
    fixed_findings, kinds_seen, has_fixed_lines = check_fixed_elements(pages)
    promise_findings = check_promises(text)

    blocking_mode = page_count > threshold

    block_items = []
    risk_items = []
    for level, msg in term_findings + numbering_findings + fixed_findings:
        if level == BLOCK and blocking_mode:
            block_items.append(msg)
        elif level == BLOCK:
            risk_items.append(f"（阻断降级：页数 ≤ 阈值）{msg}")
        else:
            risk_items.append(msg)
    for level, msg in promise_findings:
        if level == RISK:
            risk_items.append(msg)

    promise_items = [msg for level, msg in promise_findings if level == PROMISE]

    pass_items = []
    if not gloss_rows:
        pass_items.append("术语一致性：跳过（母版无 ## 术语表 节，向后兼容）")
    elif not term_findings:
        pass_items.append(f"术语一致性：通过（术语表 {len(gloss_rows)} 条，"
                          "正文无同实体异写变体）")
    if not numbering_findings:
        pass_items.append(f"页码连续性：通过（{page_count} 页编号连续，"
                          "无跳号/重复）")
    if not [m for lv, m in fixed_findings if lv == BLOCK]:
        if kinds_seen:
            pass_items.append(f"固定件一致性：通过（{len(kinds_seen)} 类声明"
                              "跨页一致）")
        elif not has_fixed_lines:
            pass_items.append("固定件一致性：通过（无固定件声明）")
    if not promise_findings:
        pass_items.append("承诺状态：跳过（无 deck-promises 表，向后兼容）")

    lines = [
        f"CROSS-PAGE-CONSISTENCY pages={page_count} threshold={threshold} "
        f"mode={'block' if blocking_mode else 'report'}",
    ]
    lines += [f"[{BLOCK}] {item}" for item in block_items] or [f"[{BLOCK}] （无）"]
    lines += [f"[{RISK}] {item}" for item in risk_items] or [f"[{RISK}] （无）"]
    lines += ([f"[{PROMISE}] {item}" for item in promise_items]
              or [f"[{PROMISE}] （无 deck-promises 表，跳过——向后兼容）"])
    lines += [f"[{PASS}] {item}" for item in pass_items] or [f"[{PASS}] （无）"]
    exit_code = EXIT_BLOCK if block_items else EXIT_OK
    lines.append(
        f"SUMMARY block={len(block_items)} risk={len(risk_items)} "
        f"promise={len(promise_items)} pass={len(pass_items)} "
        f"exit={exit_code}")
    return lines, exit_code


def main():
    ap = argparse.ArgumentParser(
        description="长 deck 跨页一致性硬门禁：术语同实体异写/页码跳号重复/"
                    "固定件声明冲突，四分类输出（阻断/风险/承诺状态/通过）")
    ap.add_argument("master", help="confirmed 母版 markdown 路径")
    ap.add_argument("--threshold", type=int, default=30,
                    help="阻断阈值：页数 ≤ 阈值时阻断类降为风险（默认 30）")
    args = ap.parse_args()
    if args.threshold < 1:
        print("FAIL: --threshold 须为正整数", file=sys.stderr)
        return EXIT_USAGE
    try:
        text = Path(args.master).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"FAIL: 无法读取 {args.master}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        lines, exit_code = analyze(text, args.threshold)
    except ParseError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return EXIT_USAGE
    for ln in lines:
        print(ln)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
