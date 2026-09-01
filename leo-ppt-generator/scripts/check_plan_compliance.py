#!/usr/bin/env python3
r"""Plan-compliance report (R-43): master talking points vs rendered text.

"Did we actually say what the confirmed master promised?" — a structured
per-page check of the deck master's bullet points against what the rendered
pages actually show (OCR read-back).

Inputs:
  - the confirmed deck master (deck-master-v<N>.md, same page syntax as
    check_master_contract.py: pages start with `## S<N>`; bullet lines are
    `- xxx` / `N. xxx` / `N、xxx`, with `标题/备注/视觉行/argument_role/
    数字登记表` lines excluded);
  - rendered text per page, from either the rendered ledger built by
    build_rendered_ledger.py (R-41: <run>/reports/rendered-ledger.json,
    field ocr_text_head) or a raw OCR directory (page_<N>.txt / slide_<NN>.txt,
    same resolution order as build_rendered_ledger). When an OCR dir is
    given its full text wins over the ledger's truncated head.

Status per page (four buckets, QMAI-style):
  full              every bullet's tokens found in that page's rendered text;
  partial_deviation at least one bullet unmatched (and page has OCR text);
  missing           page absent from the ledger/OCR dir, or no OCR text at
                    all (cannot verify — reported honestly, never fabricated);
  na                functional page (开场/封面/目录/章节/隔断/过渡/收束/
                    结尾/致谢/问答) or zero-bullet page: no bullet promise.

Deviations are capped at --max-deviations (default 5, PRD "偏差至多 N 条"),
each entry {page, point, evidence, suggestion}. Evidence quotes the unmatched
tokens plus where we looked; suggestion names the recovery loop (fix at the
master level and rebuild affected pages, see references/deck-master.md).

This is a LEAD, not a gate: deviation findings never change the exit code
(exit 0 whenever a report is produced; 2 only for usage errors). The agent
judges scene semantics on top, same two-layer discipline as
check_sensitive_text.py.

Determinism: no clock, no randomness, fixed page order, sorted JSON keys.

Usage:
  check_plan_compliance.py --master <deck-master.md> --run <run-dir> [--ocr-dir DIR]
                           [--ledger FILE] [--out FILE] [--max-deviations N]
  check_plan_compliance.py --master <deck-master.md> --ledger <rendered-ledger.json>

Exit codes: 0 = report written (deviations included); 2 = usage error.
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

DEFAULT_MAX_DEVIATIONS = 5
DEFAULT_OCR_DIRS = ("reports/ocr", "ocr", "image-deck/ocr")
PAGE_TXT_RES = ("page_{n}.txt", "page_{n:02d}.txt", "page_{n:03d}.txt",
                "slide_{n:02d}.txt", "slide_{n:03d}.txt", "S{n}.txt")

# Master page syntax mirrors check_master_contract.py (shared contract).
PAGE_RE = re.compile(r"^##\s+(S(\d+)|附)[^\n]*$", re.M)
TITLE_RE = re.compile(r"[-•]\s*标题[：:]\s*(.+)")
POINT_LINE_RE = re.compile(r"^\s*(?:[-•]|\d+\.|\d+、)\s*(.+)$", re.M)
POINT_LABEL_RE = re.compile(r"^要点\s*\d+\s*[：:]\s*")
_NON_POINT = ("标题", "备注", "视觉行", "argument_role", "数字登记表")
ROLE_RE = re.compile(r"(?:页面角色|角色|role)[：:]\s*([^\s,，;；。]+)", re.I)
FUNCTIONAL_ROLE_WORDS = (
    "开场", "封面", "目录", "章节", "隔断", "过渡", "收束", "结尾", "致谢", "问答",
)
# Tier marks / source refs are metadata, not renderable content.
TIER_MARK_RE = re.compile(r"[【（(]\s*(?:用户确认|引用|估算|示意)(?:\s*[|｜][^】）)]*)?\s*[】）)]")
SRC_SQ_RE = re.compile(r"\[\s*src\s*[：:][^\]]*\]")
ROUND_NOTE_RE = re.compile(r"(?:round|note|说明)\s*[：:][^】\]]*[\]}】]?")

# Tokenization for keyword matching: numbers (with trailing unit/percent, the
# highest-signal evidence a bullet landed) and word runs (CJK or latin).
NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|亿元|万元|千万|亿|万|千|元|美元|秒|分钟|分|小时|天|人|次|条|页|个|倍|张|项|年|月|日)?")
WORD_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z-]{2,}")
# Short glue words that carry no verifiable meaning on a rendered page.
STOP_WORDS = {
    "以及", "可以", "我们", "他们", "一个", "这个", "那个", "没有", "就是",
    "但是", "同时", "因此", "所以", "如果", "并且", "而且", "然后", "还是",
    "通过", "进行", "实现", "以及", "目前", "现在", "如下", "以上", "其中",
    "the", "and", "for", "with", "that", "this", "from", "are", "was",
}


def fold_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_point(raw: str) -> str:
    """Strip bullet metadata (tier marks, source refs) before matching."""
    text = POINT_LABEL_RE.sub("", raw)
    text = TIER_MARK_RE.sub("", text)
    text = SRC_SQ_RE.sub("", text)
    text = ROUND_NOTE_RE.sub("", text)
    return fold_ws(text)


def page_is_functional(body: str) -> bool:
    for m in ROLE_RE.finditer(body):
        if any(w in m.group(1) for w in FUNCTIONAL_ROLE_WORDS):
            return True
    return False


def parse_master(text: str) -> dict[int, dict]:
    """Parse master pages: {page_no: {header, title, points, functional}}."""
    matches = list(PAGE_RE.finditer(text))
    pages: dict[int, dict] = {}
    for i, m in enumerate(matches):
        if not m.group(2):  # `## 附` appendix: keep ordering, page_no None
            continue
        number = int(m.group(2))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end]
        title = TITLE_RE.search(body)
        points = [clean_point(p.group(1)) for p in POINT_LINE_RE.finditer(body)
                  if not any(k in p.group(1) for k in _NON_POINT)]
        pages[number] = {
            "header": m.group(0).lstrip("#").strip(),
            "title": fold_ws(title.group(1)) if title else None,
            "points": [p for p in points if p],
            "functional": page_is_functional(body),
        }
    return pages


def point_tokens(point: str) -> list[str]:
    """Content tokens of a bullet: numbers first, then meaningful words."""
    tokens: list[str] = []
    for m in NUMBER_TOKEN_RE.finditer(point):
        tokens.append(fold_ws(m.group(0)))
    for m in WORD_TOKEN_RE.finditer(point):
        word = m.group(0)
        if word.lower() not in STOP_WORDS and word not in STOP_WORDS:
            tokens.append(word)
    # De-dup, keep order; numbers survive as-is (they are load-bearing).
    seen: dict[str, None] = {}
    for token in tokens:
        seen.setdefault(token, None)
    return list(seen)


def _squash(text: str) -> str:
    """Remove all whitespace for tolerant substring matching (OCR spacing
    between a number and its unit must not break the evidence link)."""
    return re.sub(r"\s+", "", text)


def _token_in_text(token: str, squashed_text: str) -> bool:
    """Token presence: latin/digit tokens match whole; CJK runs match on any
    bigram (no segmentation — one shared 2-gram is enough spoken evidence)."""
    if not re.search(r"[\u4e00-\u9fff]", token):
        return token in squashed_text
    grams = [_squash(token)[i:i + 2] for i in range(len(_squash(token)) - 1)]
    return any(g in squashed_text for g in grams)


def match_point(point: str, rendered_text: str) -> tuple[bool, list[str]]:
    """Bullet matching: numbers are hard evidence, words are soft evidence.

    A bullet is matched when (a) every number token appears in the rendered
    text, and (b) at least half of the word tokens appear (>=1 when only a
    few; OCR rephrasing rarely keeps every wording, but a page that says the
    thing keeps the numbers and most of the terms).

    Returns (matched, missing_tokens). Empty-token bullets (pure glue) count
    as matched — there is nothing verifiable to miss.
    """
    tokens = point_tokens(point)
    if not tokens:
        return True, []
    text = _squash(rendered_text)
    numbers = [t for t in tokens if t[0].isdigit()]
    words = [t for t in tokens if not t[0].isdigit()]
    num_missing = [t for t in numbers if not _token_in_text(t, text)]
    word_missing = [t for t in words if not _token_in_text(t, text)]
    word_hits = len(words) - len(word_missing)
    matched = (not num_missing) and (not words or word_hits >= (len(words) + 1) // 2)
    return matched, (num_missing + word_missing if not matched else [])


def load_ledger(ledger_path: Path) -> dict[int, dict]:
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    pages: dict[int, dict] = {}
    for entry in payload.get("pages", []):
        number = entry.get("slide_no")
        if isinstance(number, int):
            pages[number] = entry
    return pages


def find_ocr_file(ocr_dir: Path, number: int) -> Path | None:
    for pattern in PAGE_TXT_RES:
        candidate = ocr_dir / pattern.format(n=number)
        if candidate.is_file():
            return candidate
    return None


def collect_rendered_text(run_dir: Path, ledger: dict[int, dict] | None,
                          ocr_dir: Path | None) -> dict[int, dict]:
    """Best available rendered text per page: full OCR file > ledger head."""
    texts: dict[int, dict] = {}
    if ledger:
        for number, entry in ledger.items():
            head = entry.get("ocr_text_head")
            texts[number] = {
                "source": "rendered-ledger",
                "status": entry.get("ocr_status", "missing"),
                "text": fold_ws(head) if head else "",
            }
    if ocr_dir is not None:
        for path in sorted(ocr_dir.iterdir()) if ocr_dir.is_dir() else []:
            m = re.match(r"^(?:page|slide|S)[_-]?(\d+)", path.stem, re.I)
            if m and path.is_file():
                number = int(m.group(1))
                text = fold_ws(path.read_text(encoding="utf-8", errors="replace"))
                texts[number] = {"source": f"ocr:{path.name}", "status": "ok", "text": text}
    return texts


def build_report(master_path: Path, master_pages: dict[int, dict],
                 rendered: dict[int, dict],
                 max_deviations: int) -> dict:
    page_rows: list[dict] = []
    deviations: list[dict] = []
    counts = {"full": 0, "partial_deviation": 0, "missing": 0, "na": 0}
    for number in sorted(master_pages):
        page = master_pages[number]
        row = {
            "page_no": number,
            "page_id": f"S{number}",
            "title": page["title"],
            "points_total": len(page["points"]),
        }
        if page["functional"] or not page["points"]:
            status = "na"
            row["reason"] = ("functional_page" if page["functional"]
                             else "zero_point_page")
            row["unmatched"] = []
        else:
            entry = rendered.get(number)
            if entry is None or not entry["text"]:
                status = "missing"
                row["reason"] = ("page_absent_from_render" if entry is None
                                 else "ocr_text_missing")
                row["unmatched"] = [
                    {"point": p, "missing_tokens": point_tokens(p)}
                    for p in page["points"]
                ]
            else:
                unmatched = []
                for point in page["points"]:
                    matched, missing = match_point(point, entry["text"])
                    if not matched:
                        unmatched.append(
                            {"point": point, "missing_tokens": missing})
                row["unmatched"] = unmatched
                status = "full" if not unmatched else "partial_deviation"
            row["text_source"] = entry["source"] if entry else None
        row["status"] = status
        counts[status] += 1
        page_rows.append(row)
        if status in ("partial_deviation", "missing"):
            for miss in row["unmatched"]:
                if len(deviations) >= max_deviations:
                    break
                if status == "missing":
                    evidence = (f"第 {number} 页无渲染文本可对照"
                                f"（{row.get('text_source') or 'ledger 中无该页'}）")
                    suggestion = "先补 OCR 回读（渲染 lane 记录）再核对该页履约"
                else:
                    evidence = (f"渲染文本未含: {'、'.join(miss['missing_tokens'][:6])}"
                                f"（对照来源 {row.get('text_source')}）")
                    suggestion = ("在母版层核对措辞或补齐该要点，按修复回路重建受影响页"
                                  "（见 references/deck-master.md）")
                deviations.append({
                    "page": number,
                    "point": miss["point"],
                    "evidence": evidence,
                    "suggestion": suggestion,
                })
    if len(deviations) >= max_deviations:
        total_unmatched = sum(len(r["unmatched"]) for r in page_rows
                              if r["status"] in ("partial_deviation", "missing"))
        if total_unmatched > max_deviations:
            deviations.append({
                "page": None,
                "point": f"(截断) 偏差条目超过 {max_deviations} 条上限",
                "evidence": f"实际未命中要点共 {total_unmatched} 条",
                "suggestion": "提高 --max-deviations 查看全部偏差",
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "plan-compliance",
        "master": {
            "path": str(master_path),
            "sha256": sha256_bytes(master_path.read_bytes()),
            "pages_total": len(master_pages),
        },
        "summary": {
            "status_counts": counts,
            "deviations_reported": len([d for d in deviations if d["page"] is not None]),
            "deviations_truncated": any(d["page"] is None for d in deviations),
        },
        "note": "线索级非门禁：偏差是复核线索，由 agent 结合语境判定，不阻断交付。",
        "pages": page_rows,
        "deviations": deviations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="计划履约报告（R-43）：母版要点 vs 渲染 OCR 回读，status 四档")
    parser.add_argument("--master", required=True, help="母版 deck-master.md 路径")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--run", help="run 目录（读 reports/rendered-ledger.json）")
    source.add_argument("--ledger", help="rendered-ledger.json 路径")
    parser.add_argument("--ocr-dir", help="OCR 文本目录（给定则优先于 ledger 摘要）")
    parser.add_argument("--out", help="输出路径（默认 <run>/reports/plan-compliance.json）")
    parser.add_argument("--max-deviations", type=int, default=DEFAULT_MAX_DEVIATIONS)
    args = parser.parse_args(argv)

    master_path = Path(args.master).expanduser().resolve()
    if not master_path.is_file():
        print(f"母版文件不存在: {master_path}", file=sys.stderr)
        return EXIT_USAGE
    master_text = master_path.read_text(encoding="utf-8", errors="replace")
    master_pages = parse_master(master_text)
    if not master_pages:
        print("母版中未找到任何 `## S<N>` 页", file=sys.stderr)
        return EXIT_USAGE

    ledger: dict[int, dict] | None = None
    run_dir: Path | None = None
    if args.run:
        run_dir = Path(args.run).expanduser().resolve()
        if not run_dir.is_dir():
            print(f"run 目录不存在: {run_dir}", file=sys.stderr)
            return EXIT_USAGE
        ledger_path = run_dir / "reports" / "rendered-ledger.json"
        if ledger_path.is_file():
            ledger = load_ledger(ledger_path)
    elif args.ledger:
        ledger_path = Path(args.ledger).expanduser().resolve()
        if not ledger_path.is_file():
            print(f"rendered-ledger 不存在: {ledger_path}", file=sys.stderr)
            return EXIT_USAGE
        ledger = load_ledger(ledger_path)

    ocr_dir: Path | None = None
    if args.ocr_dir:
        ocr_dir = Path(args.ocr_dir).expanduser().resolve()
        if not ocr_dir.is_dir():
            print(f"OCR 目录不存在: {ocr_dir}", file=sys.stderr)
            return EXIT_USAGE
    elif run_dir is not None:
        for rel in DEFAULT_OCR_DIRS:
            candidate = run_dir / rel
            if candidate.is_dir():
                ocr_dir = candidate
                break

    if ledger is None and ocr_dir is None:
        print("缺少渲染文本来源：给 --run（含 rendered-ledger）、--ledger 或 --ocr-dir",
              file=sys.stderr)
        return EXIT_USAGE

    rendered = collect_rendered_text(run_dir, ledger, ocr_dir)
    report = build_report(master_path, master_pages, rendered, args.max_deviations)

    out = (Path(args.out).expanduser().resolve() if args.out
           else (run_dir / "reports" / "plan-compliance.json" if run_dir else None))
    if out is None:
        print("未给 --out 且未给 --run：无法推断输出路径", file=sys.stderr)
        return EXIT_USAGE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({
        "out": str(out),
        "status_counts": report["summary"]["status_counts"],
        "deviations_reported": report["summary"]["deviations_reported"],
        "deviations_truncated": report["summary"]["deviations_truncated"],
    }, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
