"""R-73 required_text ↔ OCR 对齐门与 OCR 通道适配（KTD8 compose/thin-glue）。

通道（一条龙）：复用 vendored ``paddle_text_hints.submit_and_fetch``（接受
任意页图路径）＋ ``text_blocks_to_lines`` → ``lines[].text`` 拼接落
``image-deck/ocr/page_<N>.txt``（与 ``build_rendered_ledger`` 的 OCR_DIRS
口径一致）。缺 token、依赖缺失、任务失败/超时一律返回 ``status=not_run``
并带稳定 reason code——不把未运行包装成通过。builtin-ink 纯几何检测不能
读字，不是对齐数据源。

对齐门：只对 provenance 判定为「图像 lane 整页生成页」生效（判域来自冻结
sources-manifest 与 slide entry 事实，禁用路由启发式）；composite 文字层由
R-70 构造性断言保证，不做 OCR 重复校验；render lane 确定性产物同样豁免。
断言阈值可配、豁免清单按条登记；WARN 校准（红例 100% 拦截、误报 ≤5%）通过
前不得切 enforce 硬门。离线 fixture 校验聚合是机制级代理，不冒充真实 OCR。
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from .contracts import ContractError
from .storage import atomic_write_json

# 与 scripts/build_rendered_ledger.py 的 OCR_DIRS / 页文本命名口径保持一致。
OCR_DIRS = ("reports/ocr", "ocr", "image-deck/ocr")
PAGE_TXT_PATTERNS = (
    "page_{n}.txt",
    "page_{n:02d}.txt",
    "page_{n:03d}.txt",
    "slide_{n:02d}.txt",
    "slide_{n:03d}.txt",
)
CHANNEL_OCR_DIR = "image-deck/ocr"
ALIGN_SIDECAR_PATTERN = "page_{n:03d}.align.json"

DEFAULT_THRESHOLD = 1.0  # 逐字合同：任何必现条目缺失/错字即不达标
CONFIG_RELATIVE_PATH = "input/ocr-alignment.json"
CALIBRATION_REPORT_RELATIVE_PATH = "reports/ocr-calibration.json"
ACCEPTANCE_RED_INTERCEPT_MIN = 1.0
ACCEPTANCE_FALSE_POSITIVE_MAX = 0.05

# 图像 lane 整页生成页的来源类；其余来源类（用户素材/裁剪/render/overlay）
# 不做 OCR 对齐——生成错误是本门唯一目标。
GENERATED_SOURCE_CLASSES = frozenset({"ai-generated", "illustrative"})
_CONSTRUCTIVE_SOURCE_CLASSES = frozenset({"deterministic-overlay", "deterministic-render"})

_PADDLE_RUNTIME_DIR = (
    Path(__file__).resolve().parent / "_vendor" / "editable_ppt" / "editppt" / "runtime"
)


class OcrAlignmentError(ContractError):
    """OCR 对齐门合同失败；``reason_code`` 落在实例上，CLI 映射稳定透传。"""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail


def normalize_text(value: str) -> str:
    """对齐归一：NFC + 空白折叠。不做大小写/全半角改写（单位与标点是事实）。"""

    import unicodedata

    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def load_alignment_config(run_dir: str | Path) -> dict[str, Any]:
    """``<run>/input/ocr-alignment.json`` → 门配置；缺省 WARN + 逐字阈值。"""

    path = Path(run_dir) / CONFIG_RELATIVE_PATH
    if not path.is_file():
        return {
            "schema_version": 1,
            "mode": "warn",
            "threshold": DEFAULT_THRESHOLD,
            "exemptions": [],
        }
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OcrAlignmentError("ocr_alignment_config_invalid", f"无法读取：{exc}") from exc
    if not isinstance(config, dict):
        raise OcrAlignmentError("ocr_alignment_config_invalid", "配置必须是对象")
    mode = config.get("mode", "warn")
    if mode not in ("warn", "enforce"):
        raise OcrAlignmentError("ocr_alignment_config_invalid", f"mode 必须为 warn|enforce：{mode!r}")
    threshold = config.get("threshold", DEFAULT_THRESHOLD)
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0 < threshold <= 1:
        raise OcrAlignmentError("ocr_alignment_config_invalid", f"threshold 必须 ∈ (0,1]：{threshold!r}")
    exemptions = config.get("exemptions", [])
    if not isinstance(exemptions, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("text"), str)
        or not isinstance(item.get("reason"), str)
        for item in exemptions
    ):
        raise OcrAlignmentError(
            "ocr_alignment_config_invalid", "exemptions 必须是 {text, reason, page?} 对象数组")
    return {
        "schema_version": 1,
        "mode": mode,
        "threshold": float(threshold),
        "exemptions": exemptions,
    }


def evaluate_alignment(
    required_text: list[str],
    ocr_text: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    exemptions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """逐条子串断言（归一后）；返回 pass|fail|exempt 判定与披露明细。"""

    haystack = normalize_text(ocr_text)
    exempt_texts = {
        normalize_text(item["text"]) for item in (exemptions or []) if isinstance(item, dict)
    }
    matched: list[str] = []
    missing: list[str] = []
    exempted: list[str] = []
    for item in required_text:
        needle = normalize_text(item)
        if needle in exempt_texts:
            exempted.append(item)
        elif needle in haystack:
            matched.append(item)
        else:
            missing.append(item)
    checked = matched + missing
    ratio = (len(matched) / len(checked)) if checked else 1.0
    status = "exempt" if not checked else ("pass" if ratio >= threshold else "fail")
    return {
        "status": status,
        "ratio": round(ratio, 4),
        "threshold": threshold,
        "matched": matched,
        "missing": missing,
        "exempted": exempted,
    }


def resolve_gate_mode(config: dict[str, Any], run_dir: str | Path) -> str:
    """WARN 校准通过（红例 100% 拦截、误报 ≤5%）前拒绝 enforce 硬门。"""

    if config["mode"] != "enforce":
        return "warn"
    report_path = Path(run_dir) / CALIBRATION_REPORT_RELATIVE_PATH
    if not report_path.is_file():
        raise OcrAlignmentError(
            "ocr_calibration_required_for_enforce",
            f"mode=enforce 需要 {CALIBRATION_REPORT_RELATIVE_PATH} 中 status=passed 的校准报告",
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise OcrAlignmentError("ocr_alignment_config_invalid", f"校准报告不可读：{exc}") from exc
    if report.get("status") != "passed":
        raise OcrAlignmentError(
            "ocr_calibration_required_for_enforce", "校准报告未通过，维持 WARN")
    return "enforce"


def page_gate_applies(
    sources_manifest: dict[str, Any] | None,
    number: int,
    *,
    generation_method: str | None = None,
    slide_provenance: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """判域：仅图像 lane 整页生成页；事实来源＝provenance sidecar/冻结清单。"""

    if generation_method == "composite":
        return False, "composite-constructive"
    if slide_provenance and str(slide_provenance.get("backend", "")).startswith("render:"):
        return False, "render-deterministic"
    if sources_manifest is None:
        return False, "sources-manifest-missing"
    page = next(
        (
            item
            for item in sources_manifest.get("pages", [])
            if isinstance(item, dict) and item.get("page_id") == f"slide_{number:02d}"
        ),
        None,
    )
    if page is None:
        return False, "page-not-in-manifest"
    classes = {
        visual.get("source_class")
        for visual in page.get("visuals", [])
        if isinstance(visual, dict)
    }
    if classes & _CONSTRUCTIVE_SOURCE_CLASSES:
        return False, "constructive-layer"
    if classes & GENERATED_SOURCE_CLASSES:
        return True, "image-generated-page"
    return False, "source-class-not-generated"


def locate_ocr_text(run_dir: str | Path, number: int) -> Path | None:
    """按 OCR_DIRS × 命名模式定位页 OCR 文本；与 rendered ledger 同口径。"""

    root = Path(run_dir)
    for rel in OCR_DIRS:
        base = root / rel
        if not base.is_dir():
            continue
        for pattern in PAGE_TXT_PATTERNS:
            candidate = base / pattern.format(n=number)
            if candidate.is_file():
                return candidate
    return None


def gate_for_page(
    run_dir: str | Path,
    number: int,
    required_text: list[str],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """单页对齐门：OCR 文本在 → 断言 + 落 sidecar；不在 → not_run 披露。"""

    root = Path(run_dir)
    config = config or load_alignment_config(root)
    txt_path = locate_ocr_text(root, number)
    if txt_path is None:
        return {
            "status": "not_run",
            "reason_code": "ocr_text_missing",
            "mode": config["mode"],
            "message": "页 OCR 文本不存在（通道未运行或未落盘）；门未执行，不构成通过",
        }
    verdict = evaluate_alignment(
        required_text,
        txt_path.read_text(encoding="utf-8", errors="replace"),
        threshold=config["threshold"],
        exemptions=[
            item
            for item in config["exemptions"]
            if item.get("page") in (None, number, f"slide_{number:02d}")
        ],
    )
    verdict.update({"mode": config["mode"], "ocr_text": str(txt_path)})
    sidecar = root / CHANNEL_OCR_DIR / ALIGN_SIDECAR_PATTERN.format(n=number)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(sidecar, {
        "schema_version": 1,
        "kind": "ocr-alignment",
        "page": number,
        **verdict,
    })
    return verdict


def required_text_for_page(slides_contract: list[dict[str, Any]], number: int) -> list[str]:
    """从冻结 slides 合同取该页 required_text；无声明返回空列表。"""

    for slide in slides_contract:
        if not isinstance(slide, dict):
            continue
        if slide.get("number") == number or slide.get("slide_id") == f"slide_{number:02d}":
            items = slide.get("required_text")
            return [str(item) for item in items] if isinstance(items, list) else []
    return []


# --------------------------------------------------------------------------- #
# OCR 通道（一条龙）：paddle_text_hints → lines[].text 拼接 → page_<N>.txt
# --------------------------------------------------------------------------- #

def run_page_ocr(
    page_image: str | Path,
    out_dir: str | Path,
    number: int,
    *,
    token: str | None = None,
    model: str | None = None,
    timeout: int = 300,
    min_glyph: int = 6,
    submit_fn: Callable[[Path, str, str, int], list[dict]] | None = None,
) -> dict[str, Any]:
    """单页 OCR 一条龙。任何不可运行条件都返回 not_run，绝不发起半次调用。

    ``submit_fn`` 是测试注入 seam（默认真 paddle 云调用）；产物为
    ``<out_dir>/page_<N>.txt``（lines[].text 按序换行拼接）。
    """

    image_path = Path(page_image)
    if not image_path.is_file():
        return {"status": "not_run", "reason_code": "ocr_page_image_missing",
                "detail": f"页图不存在：{image_path}"}
    token = token or os.environ.get("PADDLE_OCR_TOKEN", "")
    if not token:
        return {"status": "not_run", "reason_code": "ocr_token_missing",
                "detail": "缺 PADDLE_OCR_TOKEN；门显式未运行并披露，不冒充通过"}
    try:
        import numpy  # noqa: F401
        import requests  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        return {"status": "not_run", "reason_code": "ocr_dependency_missing",
                "detail": f"OCR 通道依赖缺失：{exc}"}
    import sys

    sys.path.insert(0, str(_PADDLE_RUNTIME_DIR))
    try:
        from paddle_text_hints import DEFAULT_MODEL, submit_and_fetch, text_blocks_to_lines
        from page_text_metrics import load_gray
    except ImportError as exc:
        return {"status": "not_run", "reason_code": "ocr_dependency_missing",
                "detail": f"paddle_text_hints 不可导入：{exc}"}
    model = model or DEFAULT_MODEL
    started = time.monotonic()
    try:
        submit = submit_fn or submit_and_fetch
        pages = submit(image_path, token, model, timeout)
        gray = load_gray(image_path)
        lines = text_blocks_to_lines(pages[0], gray, min_glyph)
    except RuntimeError as exc:
        detail = str(exc)
        reason = "ocr_job_timeout" if "timed out" in detail else "ocr_job_failed"
        return {"status": "not_run", "reason_code": reason, "detail": detail[:300]}
    text = "\n".join(str(line.get("text", "")) for line in lines)
    out_path = Path(out_dir) / f"page_{number}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + ("\n" if text else ""), encoding="utf-8")
    elapsed = round(time.monotonic() - started, 1)
    return {
        "status": "ok",
        "out": str(out_path),
        "lines": len(lines),
        "elapsed_seconds": elapsed,
        "model": model,
        "cost_disclosure": (
            "PaddleOCR-VL 云调用：API 不回传计费明细，用量按 aistudio 平台账单核对；"
            "WARN 期算力成本须入交付披露汇总"
        ),
    }


# --------------------------------------------------------------------------- #
# 离线校准集（机制级代理）：干净 60 / 红 30，校准/验收分集
# --------------------------------------------------------------------------- #

def build_offline_calibration_manifest(
    target_dir: str | Path,
    *,
    clean_count: int = 60,
    red_count: int = 30,
    acceptance_ratio: float = 0.4,
) -> dict[str, Any]:
    """确定性生成离线 fixture 校准集并落盘 manifest（不冒充真实 OCR）。

    红例＝对某条 required item 做单字符确定性腐蚀（形近替换），对齐门必须
    拦截；干净例＝逐字一致的 OCR 文本。acceptance 分集按比例从两类中隔抽，
    校准/验收互斥。
    """

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    corrupt_pairs = (("收", "牧"), ("率", "本"), ("长", "民"), ("点", "占"), ("比", "毕"))
    cases: list[dict[str, Any]] = []
    for index in range(clean_count):
        required = [
            f"第{index + 1}号页面结论句：指标增长与结构优化并重",
            f"要点{index}-A：收入 12{index % 10}.5 亿元（估算）",
            f"要点{index}-B：毛利率 3{index % 10}.2% 同比提升",
        ]
        cases.append({
            "case_id": f"clean-{index + 1:03d}",
            "kind": "clean",
            "required_text": required,
            "ocr_text": "\n".join(required),
            "expected": "pass",
        })
    for index in range(red_count):
        required = [
            f"红例{index + 1:03d}结论句：效率与质量双线推进",
            f"红例要点{index}-A：成本 {1_000 + index} 万元（估算）",
            f"红例要点{index}-B：交付周期缩短 1{index % 10}%",
        ]
        victim = required[index % len(required)]
        original, replacement = corrupt_pairs[index % len(corrupt_pairs)]
        corrupted = victim.replace(original, replacement, 1)
        if corrupted == victim:  # 模板字面缺该字时退化为删字（仍单字符腐蚀）
            corrupted = victim.replace("：", "", 1)
        ocr_lines = [corrupted if line == victim else line for line in required]
        cases.append({
            "case_id": f"red-{index + 1:03d}",
            "kind": "red",
            "required_text": required,
            "ocr_text": "\n".join(ocr_lines),
            "expected": "fail",
        })
    calibration: list[str] = []
    acceptance: list[str] = []
    for position, case in enumerate(cases):
        (acceptance if position % 5 < round(acceptance_ratio * 5) else calibration).append(
            case["case_id"])
    manifest = {
        "schema_version": 1,
        "kind": "ocr-alignment-calibration",
        "fixture": True,
        "fixture_note": "离线 fixture 机制级代理：合成 OCR 文本，无页图，不冒充真实 OCR 校准",
        "threshold": DEFAULT_THRESHOLD,
        "cases": cases,
        "split": {"calibration": calibration, "acceptance": acceptance},
    }
    manifest_path = target / "ocr-calibration-manifest.json"
    atomic_write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def evaluate_calibration_set(manifest: dict[str, Any]) -> dict[str, Any]:
    """分集评估：验收分集红例全拦且误报 ≤5% 才 passed（WARN→硬门的依据）。"""

    if manifest.get("kind") != "ocr-alignment-calibration":
        raise OcrAlignmentError("ocr_calibration_report_invalid", "manifest kind 不符")
    by_id = {case["case_id"]: case for case in manifest["cases"]}
    splits = manifest["split"]
    thresholds = manifest.get("threshold", DEFAULT_THRESHOLD)

    def evaluate_split(case_ids: list[str]) -> dict[str, Any]:
        red_total = red_intercepted = clean_total = false_positives = 0
        failures: list[dict[str, Any]] = []
        for case_id in case_ids:
            case = by_id[case_id]
            verdict = evaluate_alignment(
                case["required_text"], case["ocr_text"], threshold=thresholds)
            if case["kind"] == "red":
                red_total += 1
                if verdict["status"] == "fail":
                    red_intercepted += 1
                else:
                    failures.append({"case_id": case_id, "problem": "red-not-intercepted"})
            else:
                clean_total += 1
                if verdict["status"] != "pass":
                    false_positives += 1
                    failures.append({"case_id": case_id, "problem": "clean-flagged"})
        return {
            "cases": len(case_ids),
            "red_total": red_total,
            "red_intercept_rate": round(red_intercepted / red_total, 4) if red_total else None,
            "clean_total": clean_total,
            "false_positive_rate": round(false_positives / clean_total, 4) if clean_total else None,
            "failures": failures,
        }

    calibration = evaluate_split(splits["calibration"])
    acceptance = evaluate_split(splits["acceptance"])
    passed = (
        acceptance["red_total"] > 0
        and acceptance["red_intercept_rate"] >= ACCEPTANCE_RED_INTERCEPT_MIN
        and acceptance["false_positive_rate"] is not None
        and acceptance["false_positive_rate"] <= ACCEPTANCE_FALSE_POSITIVE_MAX
        and calibration["red_intercept_rate"] == ACCEPTANCE_RED_INTERCEPT_MIN
    )
    report = {
        "schema_version": 1,
        "kind": "ocr-alignment-report",
        "fixture": manifest.get("fixture", False),
        "threshold": thresholds,
        "splits": {"calibration": calibration, "acceptance": acceptance},
        "criteria": {
            "red_intercept_min": ACCEPTANCE_RED_INTERCEPT_MIN,
            "false_positive_max": ACCEPTANCE_FALSE_POSITIVE_MAX,
        },
        "status": "passed" if passed else "failed",
        "note": "fixture=True 为离线机制级校准；真实页图校准集须在 R-70c 后按届时页型采集并盖 regime 版本戳",
    }
    return report
