#!/usr/bin/env python3
"""build_rendered_ledger.py — 渲染事实账本（R-41）。

从 run 的图像记录（image-deck/slide_jobs.json 的 delivery.pages[]，fallback
origin_image 扫描 + events.ndjson image.recorded）与 OCR 产物（run 下
reports/ocr/ 、ocr/ 、image-deck/ocr/ 内 page_<N>.txt / slide_<NN>.txt）聚合
每页呈现事实到 <run>/reports/rendered-ledger.json：
  - ocr_text_head：OCR 文本前 N 字符（默认 160，空白折叠）；
  - key_numbers：数字正则抽取（带常用单位/百分比），去重保序 top5；
  - chart_count：图表指称计数（图[F<N>]/图表/chart/Fig 口径，见 CHART_RE）；
  - notes_head：slide_jobs 讲稿摘要前 N 字符（无 notes 时 null）。
无 OCR 记录的页如实标注 ocr_status=missing（不编造文本）；key_numbers 在
missing 时从 notes 抽取并标注 source=notes。

思想来源：QMAI 章节保存即摄取（chapter-ingest：从成品提取结构化事实落账）+
webnovel data-agent 五投影——"上一轮实际呈现了什么"作为多轮改稿对照基线。

确定性：无时钟、无随机；页序固定、字段排序固定、去重保序。

用法：build_rendered_ledger.py <run-dir> [--out FILE] [--head-chars N] [--top-k N]
退出码：0 正常（含 missing 页）；2 run 目录无效或找不到任何页记录。
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

NUMBER_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:亿美元|亿元|万元|千万|亿|万|千|%|元|美元|秒|分钟|分|小时|天|人|次|条|页|个|倍|张|项|年|月|日)")
# Chart-reference counting: explicit figure tags first, then generic words.
CHART_RE = re.compile(r"图\s*\[?\s*F?\d|图表|chart|Chart|Fig\.?", re.IGNORECASE)
DEFAULT_HEAD_CHARS = 160
DEFAULT_TOP_K = 5
OCR_DIRS = ("reports/ocr", "ocr", "image-deck/ocr")
PAGE_TXT_RES = ("page_{n}.txt", "page_{n:02d}.txt", "page_{n:03d}.txt",
                "slide_{n:02d}.txt", "slide_{n:03d}.txt", "S{n}.txt")


def fold_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_key_numbers(text: str, top_k: int) -> list[str]:
    seen: dict[str, None] = {}
    for m in NUMBER_RE.finditer(text):
        token = fold_ws(m.group(0))
        if token:
            seen.setdefault(token, None)
        if len(seen) >= top_k:
            break
    return list(seen)[:top_k]


def chart_count(text: str) -> int:
    return len(CHART_RE.findall(text))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pages(run_dir: Path) -> list[dict]:
    """Page records from canonical slide_jobs delivery, with event fallback."""
    pages: list[dict] = []
    jobs_path = run_dir / "image-deck" / "slide_jobs.json"
    if not jobs_path.is_file():
        jobs_path = run_dir / "slide_jobs.json"
    if jobs_path.is_file():
        try:
            payload = json.loads(jobs_path.read_text(encoding="utf-8"))
            pages = (payload.get("delivery") or {}).get("pages") or []
        except (OSError, json.JSONDecodeError):
            pages = []
    if pages:
        return [p for p in pages if isinstance(p, dict)]

    # Fallback: origin_image files + image.recorded events for fingerprints.
    events: dict[str, str] = {}
    events_path = run_dir / "events.ndjson"
    if events_path.is_file():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("kind") == "image.recorded" and entry.get("data", {}).get("artifact_ref"):
                data = entry["data"]
                slide_id = str(data.get("slide_id") or "")
                m = re.search(r"(\d+)", slide_id)
                if m:
                    events[int(m.group(1))] = str(data.get("artifact_ref"))
    found: dict[int, dict] = {}
    image_dir = run_dir / "image-deck" / "origin_image"
    for png in sorted(image_dir.glob("slide_*.png")) if image_dir.is_dir() else []:
        m = re.search(r"(\d+)", png.stem)
        if m:
            found[int(m.group(1))] = {
                "page_id": f"page_{int(m.group(1)):03d}",
                "artifact_ref": str(png),
                "artifact_sha256": sha256_file(png),
                "notes": None,
                "width": None,
                "height": None,
            }
    for number, ref in events.items():
        if number not in found:
            path = Path(ref)
            found[number] = {
                "page_id": f"page_{number:03d}",
                "artifact_ref": ref,
                "artifact_sha256": sha256_file(path) if path.is_file() else None,
                "notes": None, "width": None, "height": None,
            }
    return [found[k] for k in sorted(found)]


def _slide_number(page: dict) -> int | None:
    pid = str(page.get("page_id") or page.get("slide_id") or "")
    ref = str(page.get("artifact_ref") or page.get("source_ref") or "")
    for raw in (pid, ref):
        m = re.search(r"(\d+)", raw)
        if m:
            return int(m.group(1))
    return None


def find_ocr_text(run_dir: Path, number: int) -> str | None:
    for rel in OCR_DIRS:
        base = run_dir / rel
        if not base.is_dir():
            continue
        for pattern in PAGE_TXT_RES:
            candidate = base / pattern.format(n=number)
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
    return None


def build_ledger(run_dir: Path, head_chars: int, top_k: int) -> dict:
    pages = load_pages(run_dir)
    entries = []
    missing_ocr = 0
    for page in pages:
        number = _slide_number(page)
        ocr_text = find_ocr_text(run_dir, number) if number is not None else None
        notes = page.get("notes")
        notes_text = fold_ws(str(notes)) if notes else ""
        if ocr_text is not None:
            folded = fold_ws(ocr_text)
            entry = {
                "page_id": page.get("page_id") or (f"page_{number:03d}" if number else None),
                "slide_no": number,
                "artifact_sha256": page.get("artifact_sha256"),
                "ocr_status": "ok",
                "ocr_text_head": folded[:head_chars],
                "key_numbers": extract_key_numbers(folded, top_k),
                "chart_count": chart_count(folded),
                "notes_head": notes_text[:head_chars] or None,
            }
        else:
            missing_ocr += 1
            entry = {
                "page_id": page.get("page_id") or (f"page_{number:03d}" if number else None),
                "slide_no": number,
                "artifact_sha256": page.get("artifact_sha256"),
                "ocr_status": "missing",
                "ocr_text_head": None,
                # Numbers still summarized from speaker notes, explicitly sourced.
                "key_numbers": [
                    {"value": v, "source": "notes"} for v in extract_key_numbers(notes_text, top_k)
                ],
                "chart_count": chart_count(notes_text) if notes_text else 0,
                "notes_head": notes_text[:head_chars] or None,
            }
        entries.append(entry)
    entries.sort(key=lambda e: (e["slide_no"] is None, e["slide_no"] or 0, str(e["page_id"])))
    jobs_path = run_dir / "image-deck" / "slide_jobs.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "rendered-ledger",
        "run": run_dir.name,
        "source": {
            "slide_jobs": "image-deck/slide_jobs.json" if jobs_path.is_file() else "origin_image+events",
            "slide_jobs_sha256": sha256_file(jobs_path) if jobs_path.is_file() else None,
        },
        "pages_total": len(entries),
        "pages_missing_ocr": missing_ocr,
        "pages": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="聚合 run 每页渲染事实到 rendered-ledger.json")
    parser.add_argument("run", help="run 目录")
    parser.add_argument("--out", default=None, help="输出路径（默认 <run>/reports/rendered-ledger.json）")
    parser.add_argument("--head-chars", type=int, default=DEFAULT_HEAD_CHARS)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    args = parser.parse_args(argv)

    run_dir = Path(args.run).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"run 目录不存在: {run_dir}", file=sys.stderr)
        return EXIT_USAGE
    ledger = build_ledger(run_dir, args.head_chars, args.top_k)
    if not ledger["pages"]:
        print("找不到任何页记录（slide_jobs / origin_image / events 均无）", file=sys.stderr)
        return EXIT_USAGE
    out = Path(args.out).expanduser().resolve() if args.out else \
        run_dir / "reports" / "rendered-ledger.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(out),
        "pages_total": ledger["pages_total"],
        "pages_missing_ocr": ledger["pages_missing_ocr"],
    }, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
