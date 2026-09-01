#!/usr/bin/env python3
"""check_worker_brief.py — worker 简报完备性阶梯校验（R-46）。

worker 派发前对 job prompt（worker 简报）做四块完备性校验，缺任一 → exit 1
阻断该批派发并输出缺块+页清单。是 `check_sources_manifest.py --check-job-prompts`
（C1-T2，仅 required_text / style_lock 两块）的完备性扩展；机制来源：neuro-book
ChapterWriterBrief 状态阶梯（信息控制缺填 → 降级阻断 handoff，比事后 QA 便宜一个
数量级）。

四块阶梯（声明驱动：条件不成立的块自动豁免——向后兼容无术语表/登记表的 deck）：
  ① required_text 白名单块（`## Required Text Only`）：该页声明 required_text
     非空时必须存在，且每条逐字进入简报；
  ② style_lock 块（`## Deck Style Lock`）：spec 声明 style_lock 时每页必须存在；
  ③ 术语注入块（`## Deck Terminology`）：deck 术语表存在（deck_context.
     canonical_terms / glossary / terms 任一非空）时每页必须存在——按页裁剪注入
     的内容可变，块本身不得静默丢失；该页声明 terms 时每条逐字进入简报；
  ④ 数字登记行引用块（`## Number Ledger Rows`）：该页声明 number_ledger_refs
     非空（母版数字登记表页列的投影）时必须存在，且每条登记行引用逐字进入简报。

用法：
  check_worker_brief.py <deck 目录 | slides.json 路径>
  check_worker_brief.py --job <prompts/slide_NN.json> --spec <slides.json>

退出码：0 四块齐备（或全部豁免）；1 缺块/缺 job 文件（阻断派发）；2 用法或输入
不可解析。确定性：页号升序、缺块按阶梯序①→④，输出无时间戳，重复运行逐字节一致。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_TEXT_HEADER = "## Required Text Only"
STYLE_LOCK_HEADER = "## Deck Style Lock"
TERMINOLOGY_HEADER = "## Deck Terminology"
NUMBER_LEDGER_HEADER = "## Number Ledger Rows"

# Same resolution order as check_sources_manifest.py --check-job-prompts.
SPEC_CANDIDATES = ("slides.json", "input/slides.json", "spec.json", "deck_spec.json")
SLIDE_FILE_RE = re.compile(r"slide_(\d+)(?:\.json)?$", re.IGNORECASE)

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_USAGE = 2


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: 无法读取 {path}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def string_list(value) -> list[str]:
    """Normalize a JSON value to non-empty stripped strings (vendor 同口径)."""
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def spec_slides_and_lock(spec) -> tuple[list[dict], object]:
    if isinstance(spec, dict):
        slides = spec.get("slides", [])
        return ([s for s in slides if isinstance(s, dict)], spec.get("style_lock"))
    if isinstance(spec, list):
        return ([s for s in spec if isinstance(s, dict)], None)
    raise SystemExit(EXIT_USAGE)


def glossary_present(spec: dict) -> bool:
    """Deck-level 术语表存在信号：canonical_terms / glossary / terms 任一非空。"""
    ctx = spec.get("deck_context")
    if isinstance(ctx, dict) and string_list(ctx.get("canonical_terms")):
        return True
    for key in ("glossary", "terms"):
        value = spec.get(key)
        if isinstance(value, (list, dict)) and value:
            return True
    return False


def check_prompt(prompt: str, slide: dict, *, style_lock, deck_glossary: bool) -> list[str]:
    """Ladder ①→④ for one job prompt; returns FAIL details (page prefix 由调用方加)."""
    missing: list[str] = []

    required_text = string_list(slide.get("required_text"))
    if required_text and REQUIRED_TEXT_HEADER not in prompt:
        missing.append(f"缺 {REQUIRED_TEXT_HEADER} 块（required_text 白名单静默丢失）")
    for item in required_text:
        if item not in prompt:
            missing.append(f"required_text 条目未逐字进入简报：{item!r}")

    if style_lock and STYLE_LOCK_HEADER not in prompt:
        missing.append(f"缺 {STYLE_LOCK_HEADER} 块（跨页风格锁静默丢失）")

    if deck_glossary and TERMINOLOGY_HEADER not in prompt:
        missing.append(f"缺 {TERMINOLOGY_HEADER} 块（术语注入块静默丢失）")
    for term in string_list(slide.get("terms")):
        if term not in prompt:
            missing.append(f"术语条目未逐字进入简报：{term!r}")

    refs = string_list(slide.get("number_ledger_refs"))
    if refs and NUMBER_LEDGER_HEADER not in prompt:
        missing.append(f"缺 {NUMBER_LEDGER_HEADER} 块（数字登记行引用静默丢失）")
    for ref in refs:
        if ref not in prompt:
            missing.append(f"数字登记行引用未逐字进入简报：{ref!r}")
    return missing


def slide_number(slide: dict):
    number = slide.get("number")
    return number if isinstance(number, int) else None


def summarize(label: str, pages_checked: int, fails: list[str], code: int) -> int:
    for line in fails:
        print(f"FAIL {line}")
    if code == EXIT_OK:
        print(f"OK: {label} worker 简报四块齐备（或豁免），{pages_checked} 页通过")
    print(
        json.dumps(
            {
                "input": label,
                "pages_checked": pages_checked,
                "missing": len(fails),
                "exit_code": code,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return code


def run_deck(target: Path) -> int:
    """Deck mode: check every declared slide's prompts/slide_NN.json."""
    if target.is_dir():
        spec_path = next(
            ((target / name) for name in SPEC_CANDIDATES if (target / name).is_file()),
            None,
        )
        prompts_dir = target / "prompts"
    elif target.is_file():
        spec_path, prompts_dir = target, target.parent / "prompts"
    else:
        print(f"ERROR: 路径不存在：{target}", file=sys.stderr)
        return EXIT_USAGE
    if spec_path is None:
        names = " / ".join(SPEC_CANDIDATES)
        print(f"ERROR: {target}: 未找到 spec 文件（{names}）", file=sys.stderr)
        return EXIT_USAGE

    spec = load_json(spec_path)
    slides, style_lock = spec_slides_and_lock(spec)
    deck_glossary = glossary_present(spec) if isinstance(spec, dict) else False
    if not prompts_dir.is_dir():
        print(f"FAIL {target}: 缺 prompts/ 目录（job prompt 未生成，简报整体缺失）")
        return EXIT_MISSING

    fails: list[str] = []
    pages = 0
    for slide in sorted((s for s in slides if slide_number(s) is not None), key=slide_number):
        number = slide_number(slide)
        pages += 1
        job_path = prompts_dir / f"slide_{number:02d}.json"
        if not job_path.is_file():
            fails.append(f"slide_{number:02d}: 缺 job prompt 文件 {job_path}")
            continue
        job = load_json(job_path)
        prompt = job.get("prompt") if isinstance(job, dict) else None
        if not isinstance(prompt, str):
            fails.append(f"slide_{number:02d}: job 文件缺 prompt 字段")
            continue
        fails.extend(
            f"slide_{number:02d}: {detail}"
            for detail in check_prompt(
                prompt, slide, style_lock=style_lock, deck_glossary=deck_glossary
            )
        )
    code = EXIT_MISSING if fails else EXIT_OK
    return summarize(str(spec_path), pages, fails, code)


def run_job(job_path: Path, spec_path: Path) -> int:
    """Single-job mode: re-dispatch 单页复检，期望值一律由 --spec 派生。"""
    if not job_path.is_file():
        print(f"ERROR: job 文件不存在：{job_path}", file=sys.stderr)
        return EXIT_USAGE
    match = SLIDE_FILE_RE.search(job_path.name)
    if not match:
        print(f"ERROR: 文件名不含页号（需 slide_NN.json）：{job_path.name}", file=sys.stderr)
        return EXIT_USAGE
    spec = load_json(spec_path)
    slides, style_lock = spec_slides_and_lock(spec)
    number = int(match.group(1))
    slide = next((s for s in slides if slide_number(s) == number), None)
    if slide is None:
        print(f"ERROR: {spec_path} 未声明第 {number} 页", file=sys.stderr)
        return EXIT_USAGE
    job = load_json(job_path)
    prompt = job.get("prompt") if isinstance(job, dict) else None
    if not isinstance(prompt, str):
        return summarize(str(job_path), 1, [f"slide_{number:02d}: job 文件缺 prompt 字段"], EXIT_MISSING)
    deck_glossary = glossary_present(spec) if isinstance(spec, dict) else False
    fails = [
        f"slide_{number:02d}: {detail}"
        for detail in check_prompt(prompt, slide, style_lock=style_lock, deck_glossary=deck_glossary)
    ]
    return summarize(str(job_path), 1, fails, EXIT_MISSING if fails else EXIT_OK)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", help="deck 目录或 slides.json 路径（job 集模式）")
    parser.add_argument("--job", help="单个 job prompt 文件（单页复检模式，需 --spec）")
    parser.add_argument("--spec", help="单页模式下的 slides.json（期望值来源）")
    args = parser.parse_args(argv)

    if args.job and args.target:
        parser.error("--job 与位置参数 target 互斥")
    if args.job:
        if not args.spec:
            parser.error("--job 模式需要 --spec <slides.json>（期望值与豁免判定来源）")
        return run_job(Path(args.job), Path(args.spec))
    if not args.target:
        parser.error("需要 target（deck 目录或 slides.json）或 --job <file> --spec <slides.json>")
    return run_deck(Path(args.target))


if __name__ == "__main__":
    sys.exit(main())
