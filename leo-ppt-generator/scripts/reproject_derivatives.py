#!/usr/bin/env python3
"""reproject_derivatives.py — 派生物重投影（R-38）。

从最高 confirmed 基线（含 post-confirm 修订链）母版确定性重建派生物，并对
不可确定性重建的派生物做漂移检测。上游依据：webnovel-writer `projections retry`
（只补投影不重跑前序阶段）+ chinese-longnovel「从 committed 正文重建投影，
不用投影覆盖正文」——母版是人确认的内容真值，派生物只是机器投影。

探测到的真实派生物形态（决定实现形态）：
  - sources-manifest.json：母版视觉图行（`图[F<N>] 模式:… 状态:… 焦点:…`）的机器
    投影，自指纹 = sha256(canonical_json(去 contents_sha256 的全 manifest))，
    与 check_sources_manifest.py 自洽口径一致 → 可确定性重建（图行字段），
    流程字段（source_ref/source_sha256/tier/source_class/backend）从现有
    manifest 同 figure_id 继承，不凭空编造。
  - 术语表投影：母版 `## 术语表` 与 `## 数字登记表` pipe 表节 →
    content/glossary-projection.json 结构化投影（含页指针与母版 sha256 锚）。
  - slides.json：由 LLM 在样张确认等会话状态后从母版生成（含 style_lock /
    required_text / canonical_terms），无确定性生成链 → 不重建，仅做页集合
    漂移检测并列清单。

用法：
  reproject_derivatives.py --project-root DIR [--dry-run] [--json]

退出码：0 完成（无漂移或已重建/更新）；2 无 confirmed 基线或母版不可解析。
漂移清单固定输出到 stdout（--json 时为结构化 JSON）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Sibling-script reuse: single confirmed-baseline walk shared with
# expire_candidates (pending rollback = chain break, never truth).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_confirmed_baseline import find_confirmed_baseline  # noqa: E402

SCHEMA_VERSION = 1
PAGE_RE = re.compile(r"^##\s+(S(\d+)|附)[^\n]*$", re.M)
ALL_SECTION_RE = re.compile(r"^##\s+.*$", re.M)
LEDGER_SECTION_RE = re.compile(r"^##\s+数字登记表\s*$", re.M)
GLOSSARY_SECTION_RE = re.compile(r"^##\s+术语表\s*$", re.M)
# Visual figure line: 图[F1] 模式:preserve 状态:vision-reviewed 焦点:… | 承载:…
FIG_LINE_RE = re.compile(r"图\[F(\d+)\]\s*模式:([^\s|]+)\s*状态:([^\s|]+)(?:\s*焦点:([^|]*))?")
PAGE_ID_RE = re.compile(r"^slide_\d+$")

EXIT_OK = 0
EXIT_USAGE = 2

GLOSSARY_OUT = "glossary-projection.json"
MANIFEST_OUT = "sources-manifest.json"


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_confirmed_master(content_dir: Path) -> tuple[Path, list[str]] | None:
    """Highest confirmed baseline incl. post-confirm chain (shared walk).

    Delegates to find_confirmed_baseline: a pending rollback version
    (confirmation: pending + revision_kind: post-confirm) is a chain break,
    so the projection truth falls back to the lower confirmed root —
    unconfirmed content never becomes the reproject baseline. Wrapper kept
    because deck_template imports this symbol.
    """
    return find_confirmed_baseline(content_dir)


def split_pages(text: str) -> list[tuple[str, str]]:
    """Ordered [(page_id, body)]; deck-level tables stop the last page body."""
    matches = list(PAGE_RE.finditer(text))
    if not matches:
        return []
    section_starts = [m.start() for m in ALL_SECTION_RE.finditer(text)]
    pages = []
    for idx, m in enumerate(matches):
        end = len(text)
        for pos in section_starts:
            if pos > m.start():
                end = pos
                break
        header = m.group(0)
        pid = "附" if header.startswith("## 附") else f"S{m.group(2)}"
        pages.append((pid, text[m.start():end]))
    return pages


def page_id_for(pid: str, order: list[str]) -> str:
    """S<N> → slide_%02d; the appendix takes its sequence position."""
    if pid == "附":
        return f"slide_{order.index(pid) + 1:02d}"
    return f"slide_{int(pid[1:]):02d}"


def table_rows(text: str, section_re: re.Pattern) -> list[list[str]]:
    m = section_re.search(text)
    if not m:
        return []
    rows = []
    seen_header = False
    for ln in text[m.end():].splitlines():
        s = ln.strip()
        if s.startswith("## "):
            break
        if s.startswith("|"):
            if not seen_header:
                seen_header = True  # first pipe row is the header
                continue
            if re.fullmatch(r"[\s:-]+", s.replace("|", "")):
                continue
            rows.append([c.strip() for c in s.strip().strip("|").split("|")])
    return rows


def parse_master(master: Path) -> dict:
    text = master.read_text(encoding="utf-8")
    pages = split_pages(text)
    if not pages:
        raise ValueError("母版无任何页块（## S<N> 或 ## 附）")
    order = [pid for pid, _ in pages]
    page_visuals: dict[str, list[dict]] = {}
    for pid, body in pages:
        visuals = []
        for m in FIG_LINE_RE.finditer(body):
            visual = {
                "visual_id": f"f{m.group(1)}",
                "figure_id": f"F{m.group(1)}",
                "kind": "figure",
                "handling_mode": m.group(2) or None,
                "review_status": m.group(3) or None,
            }
            focus = (m.group(4) or "").strip()
            if focus:
                visual["focus"] = focus
            visuals.append(visual)
        page_visuals[page_id_for(pid, order)] = visuals

    ledger_rows = table_rows(text, LEDGER_SECTION_RE)
    glossary_rows = table_rows(text, GLOSSARY_SECTION_RE)
    return {
        "pages": [{"page_id": page_id_for(pid, order), "master_page": pid}
                  for pid, _ in pages],
        "page_visuals": page_visuals,
        "number_ledger": [
            {"value": r[0] if len(r) > 0 else "", "pages": r[1] if len(r) > 1 else "",
             "source": r[2] if len(r) > 2 else "", "caliber": r[3] if len(r) > 3 else "",
             "period": r[4] if len(r) > 4 else "", "unit": r[5] if len(r) > 5 else "",
             "evidence_tier": r[6] if len(r) > 6 else "",
             "verified": r[7] if len(r) > 7 else "", "as_of": r[8] if len(r) > 8 else ""}
            for r in ledger_rows],
        "glossary": [
            {"cells": r} for r in glossary_rows],
    }


# Fields only the generation flow can know; carried over by figure_id.
FLOW_FIELDS = ("tier", "source_class", "source_ref", "source_sha256", "backend")


def merge_manifest(existing: dict | None, parsed: dict, master: Path) -> tuple[dict, list[str]]:
    """Rebuild sources-manifest from master figure lines, carrying flow fields."""
    old_pages = {}
    if existing:
        for page in existing.get("pages") or []:
            if isinstance(page, dict) and isinstance(page.get("page_id"), str):
                old_pages[page["page_id"]] = {
                    (v.get("figure_id") if isinstance(v, dict) else None): v
                    for v in (page.get("visuals") or []) if isinstance(v, dict)
                }
    changes: list[str] = []
    pages_out = []
    for page in parsed["pages"]:
        pid = page["page_id"]
        old_visuals = old_pages.pop(pid, {})
        visuals = []
        for fresh in parsed["page_visuals"][pid]:
            merged = dict(fresh)
            old = old_visuals.pop(fresh["figure_id"], None)
            if old:
                for field in FLOW_FIELDS:
                    if old.get(field) is not None:
                        merged[field] = old[field]
            visuals.append(merged)
        removed = sorted(f for f in old_visuals if f)
        if removed:
            changes.append(f"{pid}: 母版已无图行 {removed}，投影删除")
        visuals.sort(key=lambda v: int(v["figure_id"][1:]))
        pages_out.append({"page_id": pid, "visuals": visuals})
    for pid in sorted(old_pages):
        changes.append(f"{pid}: 母版已无该页块，投影删除整页")

    master_rel = f"content/{master.name}"
    old_master = (existing or {}).get("generated_from")
    if existing and old_master != master_rel:
        changes.append(f"generated_from 漂移: {old_master} → {master_rel}")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": "visual-sources",
        "route": (existing or {}).get("route", "generate"),
        "run_ref": (existing or {}).get("run_ref"),
        "generated_from": master_rel,
        "pages": pages_out,
    }
    manifest["contents_sha256"] = sha256_text(canonical_json(manifest))
    return manifest, changes


def manifest_diff(old: dict | None, new: dict) -> list[str]:
    if old is None:
        return ["sources-manifest.json 不存在：将新建投影（流程字段为空，待 image prepare 链补齐）"]
    old_key = {p.get("page_id"): p for p in old.get("pages") or []}
    new_key = {p.get("page_id"): p for p in new.get("pages")}
    diffs: list[str] = []
    for pid in sorted(set(old_key) | set(new_key)):
        if pid not in new_key:
            diffs.append(f"{pid}: 页删除")
            continue
        if pid not in old_key:
            diffs.append(f"{pid}: 页新增（visuals={len(new_key[pid]['visuals'])}）")
            continue
        before = canonical_json(old_key[pid])
        after = canonical_json(new_key[pid])
        if before != after:
            diffs.append(f"{pid}: visuals 漂移")
    if old.get("generated_from") != new.get("generated_from"):
        diffs.append(f"generated_from: {old.get('generated_from')} → {new.get('generated_from')}")
    return diffs


def check_slides_drift(project_root: Path, parsed: dict) -> list[str]:
    """slides.json is an LLM/session product: detect page-set drift only."""
    candidates = [
        project_root / "content" / "slides.json",
        project_root / "slides.json",
    ]
    run_inputs = sorted((project_root / "runs").glob("*/input/slides.json")) if \
        (project_root / "runs").is_dir() else []
    candidates.extend(run_inputs)
    slides_path = next((p for p in candidates if p.is_file()), None)
    if slides_path is None:
        return ["slides.json 未找到：跳过页集合漂移检测（无该派生物）"]
    try:
        payload = json.loads(slides_path.read_text(encoding="utf-8"))
        slides = payload.get("slides") or []
    except (OSError, json.JSONDecodeError):
        return [f"slides.json 不可解析: {slides_path}"]
    master_pages = {p["master_page"] for p in parsed["pages"]}
    slide_nums = {f"S{int(s.get('number'))}" for s in slides
                  if isinstance(s, dict) and s.get("number") is not None}
    drift = []
    if master_pages != slide_nums:
        only_master = sorted(master_pages - slide_nums)
        only_slides = sorted(slide_nums - master_pages)
        if only_master:
            drift.append(f"母版页块 {only_master} 在 slides.json 缺失")
        if only_slides:
            drift.append(f"slides.json 页 {only_slides} 在母版无对应页块")
    if not drift:
        return []
    return [f"[{slides_path.relative_to(project_root)}] {d}" for d in drift]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 confirmed 母版重投影派生物（manifest/术语表重建 + slides 漂移检测）")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--dry-run", action="store_true", help="只 diff，不写任何文件")
    parser.add_argument("--json", action="store_true", help="结构化 JSON 输出")
    args = parser.parse_args(argv)

    root = Path(args.project_root).expanduser().resolve()
    content = root / "content"
    if not content.is_dir():
        print(f"content/ 不存在: {content}", file=sys.stderr)
        return EXIT_USAGE

    found = find_confirmed_master(content)
    if found is None:
        print("无 confirmed 基线（含 post-confirm 链）母版：无可投影真值，退出。", file=sys.stderr)
        return EXIT_USAGE
    master, chain = found
    try:
        parsed = parse_master(master)
    except (OSError, ValueError) as exc:
        print(f"母版解析失败: {exc}", file=sys.stderr)
        return EXIT_USAGE

    manifest_path = content / MANIFEST_OUT
    existing = None
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None

    new_manifest, merge_notes = merge_manifest(existing, parsed, master)
    manifest_changes = manifest_diff(existing, new_manifest)
    slides_drift = check_slides_drift(root, parsed)

    glossary_path = content / GLOSSARY_OUT
    glossary = {
        "schema_version": SCHEMA_VERSION,
        "kind": "glossary-projection",
        "generated_from": f"content/{master.name}",
        "master_sha256": sha256_file(master),
        "post_confirm_chain": chain,
        "terms": parsed["glossary"],
        "number_ledger": parsed["number_ledger"],
    }
    glossary_changes: list[str] = []
    if glossary_path.is_file():
        try:
            old_g = json.loads(glossary_path.read_text(encoding="utf-8"))
            if canonical_json(old_g) != canonical_json(glossary):
                glossary_changes = ["glossary-projection.json 与母版投影不一致，将重建"]
        except (OSError, json.JSONDecodeError):
            glossary_changes = ["glossary-projection.json 不可解析，将重建"]
    else:
        glossary_changes = ["glossary-projection.json 不存在，将新建"]

    actions: list[str] = []
    if not args.dry_run:
        if existing is None or manifest_changes:
            manifest_path.write_text(
                json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            actions.append(f"重建 {MANIFEST_OUT}")
        if glossary_path.is_file() is False or glossary_changes:
            glossary_path.write_text(
                json.dumps(glossary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            actions.append(f"重建 {GLOSSARY_OUT}")
    else:
        actions.append("dry-run：未写任何文件")

    drift = merge_notes + manifest_changes + glossary_changes + slides_drift
    result = {
        "schema_version": SCHEMA_VERSION,
        "project_root": str(root),
        "confirmed_master": master.name,
        "post_confirm_chain": chain,
        "dry_run": bool(args.dry_run),
        "actions": actions,
        "drift": drift,
        "pages": len(parsed["pages"]),
        "figure_lines": sum(len(v) for v in parsed["page_visuals"].values()),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"confirmed 基线: {master.name}" + (f"（链: {' → '.join(chain)}）" if chain else ""))
        for action in actions:
            print(f"动作: {action}")
        if drift:
            print("漂移清单:")
            for item in drift:
                print(f"  - {item}")
        else:
            print("漂移清单: 无")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
