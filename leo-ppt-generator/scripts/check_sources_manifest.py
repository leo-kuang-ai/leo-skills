#!/usr/bin/env python3
"""sources_manifest.json 校验器（A2，退出码 CI-4：0 过 / 1 FAIL / 2 WARN）。

三种用法：
  check_sources_manifest.py <manifest.json 或 run 目录> [--strict] [--master <md>]
  check_sources_manifest.py --compile <run 目录> [--out <path>]
  check_sources_manifest.py --check-job-prompts <deck 目录>

- 默认档：schema / 枚举 / figure_id 唯一 / 页集合覆盖 / contents_sha256 自洽 /
  敏感扫描。命中 → exit 1。
- WARN 档（exit 2，可交付但须披露）：存在低审查状态图（caption-inferred /
  user-described / not-reviewed）、handling_mode=request-higher-resolution 未闭环、
  URL 缓存过期（读取 validate_assets 的缓存文件，TTL 默认 7 天）。
- --strict 档（在默认档之上追加 FAIL）：①tier=引用 的 visual 必须能回溯到用户
  输入（source_ref 存在于 sources/ 或 run 冻结输入，且 source_sha256 匹配）；
  ②tier=引用 且 source_class ∈ {ai-generated, illustrative} → FAIL（AI 图冒充
  引用证据）；③--master 给定时与母版图行 figure_id 集合一致；④引用级图
  review_status != vision-reviewed 且母版图行带位置性标注词 → FAIL。
- --compile：upgrade 路线聚合——读 <run>/pages/page_NNN/manifest.json 的
  asset_provenance 与 imagegen-jobs.json，映射为 deck 级 manifest
  （user-provided → user-material；asset-sheet-separated → derived-crop；
  imagegen → ai-generated；user-approved-rasterization → derived-crop；
  latex-rendered-formula → deterministic-render）。
- --check-job-prompts：C1-T2 静默丢失检出——slides.json（或 spec JSON）声明了
  required_text / style_lock 而 prompts/slide_NN.json 的 job prompt 缺对应
  "## Required Text Only" / "## Deck Style Lock" 块 → exit 1。

用法约定：脚本自包含（stdlib only），从技能目录内执行；路径见
references/sources-manifest-schema.md。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MANIFEST_KIND = "visual-sources"

SOURCE_CLASSES = (
    "user-material",
    "derived-crop",
    "ai-generated",
    "illustrative",
    "native-rebuild",
    "deterministic-render",
    "deterministic-overlay",
)
TIERS = ("引用", "估算", "示意")
HANDLING_MODES = (
    "preserve",
    "overview+detail",
    "split",
    "cross-slide",
    "not-use",
    "request-higher-resolution",
)
REVIEW_STATUSES = (
    "vision-reviewed",
    "metadata-reviewed",
    "caption-inferred",
    "user-described",
    "not-reviewed",
)
LOW_REVIEW_STATUSES = ("caption-inferred", "user-described", "not-reviewed")
# source_ref 允许为 null 的 source_class（且 tier 必须非引用）
NULL_REF_CLASSES = ("ai-generated", "native-rebuild", "deterministic-overlay")
# strict 档 ①②只针对引用级；derived-crop 的引用级同样要回溯源文件。
TRACE_REQUIRED_CLASSES = ("user-material", "derived-crop")

SENSITIVE_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|password|authorization|bearer|secret)"
)
POSITIONAL_RE = re.compile(
    r"(右上|左上|右下|左下|子图|箭头|高亮|标出区域|panel\s?[A-Z]|图内位置)"
)
FIGURE_ROW_RE = re.compile(r"图\[F(\d+)\]")
PAGE_ID_RE = re.compile(r"^slide_(\d+)$")

REQUIRED_TEXT_HEADER = "## Required Text Only"
STYLE_LOCK_HEADER = "## Deck Style Lock"
CACHE_TTL_DAYS = 7


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []

    def fail(self, item: str) -> None:
        self.fails.append(item)

    def warn(self, item: str) -> None:
        self.warns.append(item)

    def exit_code(self, *, strict: bool) -> int:
        if self.fails:
            return 1
        if self.warns:
            # WARN 档可交付但须披露；strict 下按 DELIVERY-GATE 语义同样阻止交付，
            # 调用方（交付门）把非 0 一律视为阻断。
            return 2
        return 0

    def dump(self) -> None:
        for item in self.fails:
            print(f"FAIL {item}")
        for item in self.warns:
            print(f"WARN {item}")
        if not self.fails and not self.warns:
            print("OK sources manifest passed (0 fail, 0 warn)")


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: 无法读取或解析 JSON（{exc}）") from exc


def resolve_manifest_path(target: Path) -> tuple[Path, Path | None]:
    """返回 (manifest 路径, run 目录或 None)。"""
    target = Path(target)
    if target.is_dir():
        run_dir = target
        manifest = target / "input" / "sources-manifest.json"
        if not manifest.is_file():
            manifest = target / "sources-manifest.json"
        if not manifest.is_file():
            raise ValueError(
                f"{target}: run 目录下未找到 input/sources-manifest.json（sources_manifest_missing）"
            )
        return manifest, run_dir
    if not target.is_file():
        raise ValueError(f"{target}: manifest 文件不存在（sources_manifest_missing）")
    return target, target.parent.parent if target.parent.name == "input" else None


def _resolve_local_ref(ref: str, roots: list[Path]) -> Path | None:
    candidate = Path(ref)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for root in roots:
        merged = root / candidate
        if merged.is_file():
            return merged
    return None


def _validate_visual(
    visual: dict,
    *,
    page_id: str,
    seen_figure_ids: dict[str, str],
    report: Report,
) -> None:
    where = f"{page_id}/{visual.get('visual_id', '?')}"
    if not isinstance(visual.get("visual_id"), str) or not visual["visual_id"].strip():
        report.fail(f"{where}: visual_id 缺失或为空")
    kind = visual.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        report.fail(f"{where}: kind 缺失或为空")
    source_class = visual.get("source_class")
    if source_class not in SOURCE_CLASSES:
        report.fail(f"{where}: source_class 非法（{source_class}）不在封闭枚举内")
    tier = visual.get("tier")
    if tier not in TIERS:
        report.fail(f"{where}: tier 非法（{tier}），必须是 引用/估算/示意 之一")
    for field, vocab in (
        ("handling_mode", HANDLING_MODES),
        ("review_status", REVIEW_STATUSES),
    ):
        value = visual.get(field)
        if value is not None and value not in vocab:
            report.fail(f"{where}: {field} 非法（{value}）不在封闭枚举内")
    figure_id = visual.get("figure_id")
    if figure_id is not None:
        if not isinstance(figure_id, str) or not re.fullmatch(r"F\d+", figure_id):
            report.fail(f"{where}: figure_id 格式非法（{figure_id}），应为 F<数字>")
        elif figure_id in seen_figure_ids:
            report.fail(
                f"{where}: figure_id {figure_id} 与 {seen_figure_ids[figure_id]} 重复"
            )
        else:
            seen_figure_ids[figure_id] = where
    source_ref = visual.get("source_ref")
    if source_ref is None:
        if source_class not in NULL_REF_CLASSES or tier == "引用":
            report.fail(
                f"{where}: source_ref 为 null 仅允许 {NULL_REF_CLASSES} 且 tier 非引用"
            )
    elif isinstance(source_ref, str):
        if not source_ref.strip():
            report.fail(f"{where}: source_ref 不能是空白字符串")
        if tier == "引用" and source_class in ("ai-generated", "illustrative"):
            report.fail(
                f"{where}: tier=引用 且 source_class={source_class}——AI/示意类图冒充引用证据"
            )
    else:
        report.fail(f"{where}: source_ref 必须是字符串或 null")
    # WARN：低审查状态与未闭环的高清请求。
    if visual.get("review_status") in LOW_REVIEW_STATUSES:
        report.warn(
            f"{where}: review_status={visual['review_status']}（低审查状态图，交付须披露）"
        )
    if visual.get("handling_mode") == "request-higher-resolution":
        report.warn(f"{where}: handling_mode=request-higher-resolution 未闭环")


def _check_cache_expiry(manifest: dict, roots: list[Path], report: Report) -> None:
    for root in roots:
        cache = root / "sources" / ".asset-validation.json"
        if not cache.is_file():
            continue
        try:
            entries = _load_json(cache)
        except ValueError:
            continue
        if not isinstance(entries, dict):
            continue
        cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)
        for page in manifest.get("pages", []):
            for visual in page.get("visuals", []):
                ref = visual.get("source_ref")
                if not isinstance(ref, str) or not ref.startswith("https://"):
                    continue
                record = entries.get(ref)
                if not isinstance(record, dict) or record.get("status") != "ok":
                    continue
                checked = record.get("checked_at")
                if isinstance(checked, str) and checked.endswith("Z"):
                    try:
                        stamp = datetime.fromisoformat(checked[:-1]).replace(
                            tzinfo=timezone.utc
                        )
                    except ValueError:
                        continue
                    if stamp < cutoff:
                        report.warn(f"URL 缓存过期（> {CACHE_TTL_DAYS} 天）: {ref}")
        return


def validate_manifest(
    manifest: dict,
    *,
    run_dir: Path | None,
    master: Path | None,
    strict: bool,
) -> Report:
    report = Report()
    if not isinstance(manifest, dict):
        report.fail("manifest 顶层必须是 JSON 对象")
        return report
    if manifest.get("schema_version") != SCHEMA_VERSION:
        report.fail(f"schema_version 必须为 {SCHEMA_VERSION}")
    if manifest.get("manifest_kind") != MANIFEST_KIND:
        report.fail(f"manifest_kind 必须为 {MANIFEST_KIND}")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        report.fail("pages 必须是非空数组")
        return report

    # 敏感扫描（canonical 全文）。
    payload = {key: value for key, value in manifest.items() if key != "contents_sha256"}
    if SENSITIVE_RE.search(canonical_json(payload)):
        report.fail("敏感字段命中（sources_manifest_invalid）")

    seen_figure_ids: dict[str, str] = {}
    seen_page_ids: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            report.fail("pages[] 条目必须是对象")
            continue
        page_id = page.get("page_id")
        if not isinstance(page_id, str) or not PAGE_ID_RE.match(page_id):
            report.fail(f"page_id 非法（{page_id}），应为 slide_<数字>")
            continue
        if page_id in seen_page_ids:
            report.fail(f"page_id 重复：{page_id}")
            continue
        seen_page_ids.add(page_id)
        visuals = page.get("visuals")
        if visuals is None:
            report.fail(f"{page_id}: 缺 visuals 数组（纯文字页须显式 visuals: []）")
        elif not isinstance(visuals, list):
            report.fail(f"{page_id}: visuals 必须是数组")
        else:
            for visual in visuals:
                if isinstance(visual, dict):
                    _validate_visual(
                        visual, page_id=page_id, seen_figure_ids=seen_figure_ids, report=report
                    )
                else:
                    report.fail(f"{page_id}: visuals[] 条目必须是对象")

    # contents_sha256 自洽。
    recorded = manifest.get("contents_sha256")
    if not isinstance(recorded, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded or ""):
        report.fail("contents_sha256 缺失或格式非法")
    else:
        recomputed = sha256_bytes(canonical_json(payload).encode("utf-8"))
        if recomputed != recorded:
            report.fail(
                f"contents_sha256 不自洽（记录 {recorded[:12]}… vs 重算 {recomputed[:12]}…）"
            )

    # 页集合覆盖（run 目录在场时对照 slide_jobs.json）。
    roots = _trace_roots(manifest, run_dir)
    if run_dir is not None:
        jobs_path = run_dir / "image-deck" / "slide_jobs.json"
        if not jobs_path.is_file():
            jobs_path = run_dir / "slide_jobs.json"
        if jobs_path.is_file():
            jobs = _load_json(jobs_path)
            job_pages = {
                f"slide_{int(item['number']):02d}"
                for item in jobs.get("slides", [])
                if isinstance(item, dict) and "number" in item
            }
            missing = sorted(job_pages - seen_page_ids)
            if missing:
                report.fail(f"页集合未覆盖 slide_jobs.json 的页：{', '.join(missing)}")

    _check_cache_expiry(manifest, roots, report)

    if strict:
        _strict_traceability(manifest, roots, report)

    if master is not None:
        _cross_check_master(master, manifest, report, strict=strict)
    return report


def _trace_roots(manifest: dict, run_dir: Path | None) -> list[Path]:
    roots: list[Path] = []
    if run_dir is not None:
        roots.append(run_dir / "input")
        # 项目根约定（run 位于 <project-root>/runs/<run-id>）：相对 source_ref
        # （如 sources/evidence.png）不依赖检查器 CWD 也能回溯（D-OBS-03）。
        roots.append(run_dir.resolve().parent.parent)
    generated_from = manifest.get("generated_from")
    if isinstance(generated_from, str) and generated_from.strip():
        roots.append(Path(generated_from).resolve().parent.parent)
    return roots


def _strict_traceability(manifest: dict, roots: list[Path], report: Report) -> None:
    extra_roots = [Path.cwd()]
    for page in manifest.get("pages", []):
        page_id = page.get("page_id", "?")
        for visual in page.get("visuals", []):
            where = f"{page_id}/{visual.get('visual_id', '?')}"
            tier = visual.get("tier")
            source_class = visual.get("source_class")
            if tier != "引用":
                continue
            if source_class in ("ai-generated", "illustrative"):
                # 默认档已 FAIL；此处不重复计。
                continue
            ref = visual.get("source_ref")
            if not isinstance(ref, str) or not ref.strip():
                report.fail(f"{where}: source_unverifiable——引用级 visual 无 source_ref")
                continue
            if ref.startswith("https://"):
                # URL 型引用源的可连性由 validate_assets 负责；strict 只要求登记。
                if not visual.get("source_sha256"):
                    report.warn(f"{where}: URL 引用源未记录 source_sha256（可交付须披露）")
                continue
            resolved = _resolve_local_ref(ref, roots + extra_roots)
            if resolved is None:
                report.fail(
                    f"{where}: source_unverifiable——引用级 source_ref 无法回溯用户输入（{ref}）"
                )
                continue
            expected = visual.get("source_sha256")
            if isinstance(expected, str) and expected:
                actual = sha256_file(resolved)
                if actual != expected:
                    report.fail(
                        f"{where}: source_unverifiable——源文件 sha256 不匹配（{ref}）"
                    )


def _cross_check_master(master: Path, manifest: dict, report: Report, *, strict: bool) -> None:
    try:
        text = master.read_text(encoding="utf-8")
    except OSError as exc:
        report.fail(f"母版文档无法读取：{exc}")
        return
    master_ids = set(FIGURE_ROW_RE.findall(text))
    manifest_ids = {
        visual.get("figure_id")
        for page in manifest.get("pages", [])
        for visual in page.get("visuals", [])
        if isinstance(visual.get("figure_id"), str)
    }
    if master_ids != manifest_ids:
        only_master = sorted(f"F{n}" for n in master_ids - {fid[1:] for fid in manifest_ids})
        only_manifest = sorted(manifest_ids - {f"F{n}" for n in master_ids})
        detail = []
        if only_master:
            detail.append(f"仅母版有：{', '.join(only_master)}")
        if only_manifest:
            detail.append(f"仅 manifest 有：{', '.join(only_manifest)}")
        report.fail("figure_id 集合与母版图行不一致（" + "；".join(detail) + "）")
    if not strict:
        return
    # ④ 引用级低审查图带位置性标注 → FAIL。
    for page in manifest.get("pages", []):
        for visual in page.get("visuals", []):
            fid = visual.get("figure_id")
            if not isinstance(fid, str):
                continue
            if visual.get("tier") != "引用":
                continue
            if visual.get("review_status") == "vision-reviewed":
                continue
            for line in text.splitlines():
                if f"图[{fid}]" in line and POSITIONAL_RE.search(line):
                    report.fail(
                        f"{page.get('page_id')}/{visual.get('visual_id')}: "
                        f"figure_review_status_insufficient——{fid} 未 vision-reviewed "
                        "但母版图行含位置性标注"
                    )
                    break


def compute_contents_sha256(manifest: dict) -> str:
    payload = {key: value for key, value in manifest.items() if key != "contents_sha256"}
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


COMPILE_CLASS_MAP = {
    "user-provided": "user-material",
    "asset-sheet-separated": "derived-crop",
    "imagegen": "ai-generated",
    "user-approved-rasterization": "derived-crop",
    "latex-rendered-formula": "deterministic-render",
}
COMPILE_TIER_MAP = {
    "user-material": "引用",
    "derived-crop": "引用",
    "ai-generated": "示意",
    "deterministic-render": "示意",
}


def compile_from_run(run_dir: Path, out_path: Path) -> int:
    pages_root = run_dir / "pages"
    if not pages_root.is_dir():
        print(f"FAIL {run_dir}: 未找到 pages/ 目录（upgrade 聚合需要页级 manifest）")
        return 1
    pages = []
    for page_dir in sorted(path for path in pages_root.iterdir() if path.is_dir()):
        match = re.fullmatch(r"page_(\d+)", page_dir.name)
        if not match:
            continue
        page_id = f"slide_{int(match.group(1)):02d}"
        manifest_path = page_dir / "manifest.json"
        visuals = []
        if manifest_path.is_file():
            page_manifest = _load_json(manifest_path)
            entries = page_manifest.get("asset_provenance", [])
            jobs = {}
            jobs_path = page_dir / "imagegen-jobs.json"
            if jobs_path.is_file():
                for job in _load_json(jobs_path).get("jobs", []):
                    if isinstance(job, dict) and isinstance(job.get("output"), str):
                        jobs[job["output"]] = job
            for index, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict):
                    continue
                source_type = entry.get("source_type")
                source_class = COMPILE_CLASS_MAP.get(source_type)
                if source_class is None:
                    print(
                        f"WARN {page_id}: asset_provenance source_type={source_type} "
                        "不在聚合映射表内，跳过该条"
                    )
                    continue
                output_path = entry.get("path")
                job = jobs.get(output_path) if isinstance(output_path, str) else None
                source_ref = None
                source_sha = None
                backend = "unknown"
                if job is not None:
                    backend = job.get("backend") or "unknown"
                    source_ref = output_path
                    source_sha = job.get("output_sha256")
                elif isinstance(entry.get("source"), str):
                    source_ref = entry["source"]
                    resolved = page_dir / source_ref
                    if resolved.is_file():
                        source_sha = sha256_file(resolved)
                visuals.append(
                    {
                        "visual_id": f"asset{index}",
                        "figure_id": None,
                        "kind": "asset",
                        "source_class": source_class,
                        "tier": COMPILE_TIER_MAP[source_class],
                        "handling_mode": None,
                        "review_status": None,
                        "source_ref": source_ref,
                        "source_sha256": source_sha,
                        "backend": backend,
                    }
                )
        pages.append({"page_id": page_id, "visuals": visuals})
    compiled = {
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "route": "upgrade",
        "run_ref": run_dir.name,
        "generated_from": "pages/*/manifest.json",
        "pages": pages,
    }
    compiled["contents_sha256"] = compute_contents_sha256(compiled)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(compiled, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = validate_manifest(compiled, run_dir=None, master=None, strict=False)
    report.dump()
    print(f"compiled manifest -> {out_path}")
    return report.exit_code(strict=False)


def check_job_prompts(deck_dir: Path) -> int:
    report = Report()
    slides_path = deck_dir / "slides.json"
    if not slides_path.is_file():
        candidates = ("input/slides.json", "spec.json", "deck_spec.json")
        slides_path = next(
            (deck_dir / name for name in candidates if (deck_dir / name).is_file()),
            slides_path,
        )
    if not slides_path.is_file():
        print(f"FAIL {deck_dir}: 未找到 slides.json（或 input/slides.json）")
        return 1
    spec = _load_json(slides_path)
    if isinstance(spec, dict):
        slides = spec.get("slides", [])
        style_lock = spec.get("style_lock")
    elif isinstance(spec, list):
        slides = spec
        style_lock = None
    else:
        print(f"FAIL {slides_path}: 顶层必须是对象（vendor spec）或数组（slides 列表）")
        return 1
    prompts_dir = deck_dir / "prompts"
    if not prompts_dir.is_dir():
        print(f"FAIL {deck_dir}: 未找到 prompts/ 目录（job prompt 缺块无法检出）")
        return 1
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        number = slide.get("number")
        if not isinstance(number, int):
            continue
        job_path = prompts_dir / f"slide_{number:02d}.json"
        if not job_path.is_file():
            report.fail(f"slide_{number:02d}: 缺 job prompt 文件 {job_path}")
            continue
        job = _load_json(job_path)
        prompt = job.get("prompt") if isinstance(job, dict) else None
        if not isinstance(prompt, str):
            report.fail(f"slide_{number:02d}: job 文件缺 prompt 字段")
            continue
        required_text = slide.get("required_text")
        if isinstance(required_text, list) and required_text:
            if REQUIRED_TEXT_HEADER not in prompt:
                report.fail(
                    f"slide_{number:02d}: slides.json 声明 required_text 但 job prompt 缺 "
                    f"{REQUIRED_TEXT_HEADER} 块（C1-T2 白名单静默丢失）"
                )
            else:
                for item in required_text:
                    if isinstance(item, str) and item.strip() and item not in prompt:
                        report.fail(
                            f"slide_{number:02d}: required_text 条目未逐字进入 job prompt：{item!r}"
                        )
        if style_lock and STYLE_LOCK_HEADER not in prompt:
            report.fail(
                f"slide_{number:02d}: spec 声明 style_lock 但 job prompt 缺 "
                f"{STYLE_LOCK_HEADER} 块（C1-T2 跨页锁静默丢失）"
            )
    report.dump()
    return report.exit_code(strict=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", help="manifest 文件或 run 目录")
    parser.add_argument("--strict", action="store_true", help="追加 strict FAIL 判据")
    parser.add_argument("--master", help="母版文档路径（对照图行 figure_id）")
    parser.add_argument("--compile", metavar="RUN", help="从 upgrade run 聚合 deck 级 manifest")
    parser.add_argument("--out", help="--compile 输出路径（默认 <run>/reports/sources-manifest.json）")
    parser.add_argument(
        "--check-job-prompts",
        metavar="DECK_DIR",
        help="检出 slides.json 声明 required_text/style_lock 而 job prompt 缺块",
    )
    args = parser.parse_args(argv)
    if args.check_job_prompts:
        return check_job_prompts(Path(args.check_job_prompts))
    if args.compile:
        return compile_from_run(Path(args.compile), Path(args.out) if args.out else Path(args.compile) / "reports" / "sources-manifest.json")
    if not args.target:
        parser.error("需要 target（manifest 或 run 目录）、--compile 或 --check-job-prompts")
    try:
        manifest_path, run_dir = resolve_manifest_path(Path(args.target))
        manifest = _load_json(manifest_path)
    except ValueError as exc:
        print(f"FAIL {exc}")
        return 1
    report = validate_manifest(
        manifest,
        run_dir=run_dir,
        master=Path(args.master) if args.master else None,
        strict=args.strict,
    )
    report.dump()
    code = report.exit_code(strict=args.strict)
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "mode": "strict" if args.strict else "default",
                "fails": len(report.fails),
                "warns": len(report.warns),
                "exit_code": code,
            },
            ensure_ascii=False,
        )
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
