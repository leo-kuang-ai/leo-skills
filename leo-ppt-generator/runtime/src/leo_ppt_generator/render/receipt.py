"""E1 DELIVERY-GATE 指纹收据：五类 sha256 指纹的采集、落盘与新鲜度断言。

指纹收据机制改编自 slides-grab（MIT），据用户线下授权（总架构师 R-10），
由 ``slides-grab/src/design-gate-state.js`` 的五类指纹与 ``diffFingerprints``
对称差逻辑移植为 Python（功能语义保留，实现走本仓 ``storage.sha256_file``
流式哈希与原子写）。

五类指纹与真实 run 目录结构的映射（类别缺失时记显式空清单，不报错）：

1. ``page_artifacts``   每页产物：``image-deck/origin_image/*``（slides 页图）、
   ``editable/pages/**``（页 PPTX，如存在）、``final/*.pptx``（成册 PPTX，
   页号为空 → 漂移时按全册波及）。
2. ``local_assets``     本地输入资产：``input/**`` 中非样式类冻结输入
   （slides.json、backend-contract.json 等）。
3. ``qa_reports``       QA 报告：``final/validation-summary.json``、
   ``final/failure-report.json``、``reports/*.json``（排除
   ``timing.json``——每条命令都会追加的观测churn；排除收据自身）。
4. ``render_previews``  渲染预览：``reports/render-preview/**``、
   ``final/render-preview/**``。
5. ``template_style_sources`` 模板样式源：``input/**`` 中
   style/deck-spec/theme 命名文件 + run 内 ``template-library/canonical/templates/**``。

排除项（churn，不属于交付语义）：``logs/**``、``observability/**``、
``run.json``、全部点文件/锁文件与符号链接。

收据 schema v1（R-3 裁决）：五类 ``{相对路径: sha256}`` 映射 +
``linked_assets{sources_manifest, beta_sidecars}``（M0 两键显式 null 占位）+
顶层 ``builder_id`` 上下文字段（M0 为 null）。收据文件自身不进任何指纹。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage import atomic_write_json, sha256_file

RECEIPT_SCHEMA_VERSION = 1
RECEIPT_KIND = "delivery_receipt"
RECEIPT_RELATIVE_PATH = Path("reports") / "delivery-receipt.json"

FINGERPRINT_CLASSES = (
    "page_artifacts",
    "local_assets",
    "qa_reports",
    "render_previews",
    "template_style_sources",
)

# deck 级产物（无页号）漂移 → 全册波及，与页产物同类的"交付物"语义。
_DECK_LEVEL_SUFFIXES = (".pptx",)

_STYLE_SOURCE_RE = re.compile(r"style|deck[-_]spec|theme", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"(\d+)")

# reports/ 下的观测 churn 与收据自身：不进指纹，否则 verify 自污染。
_REPORTS_EXCLUDED = {"timing.json", RECEIPT_RELATIVE_PATH.name}


class ReceiptError(ValueError):
    """收据操作违反合同时的稳定错误分类。"""

    reason_code = "delivery_receipt_invalid"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _page_number(relative_path: str) -> int | None:
    """从产物相对路径推断页号（slide_03 / page_003 等）；成册级返回 None。"""

    stem = Path(relative_path).stem
    match = _PAGE_NUMBER_RE.search(stem)
    return int(match.group(1)) if match else None


def _iter_regular_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.name.startswith("."):
            continue
        files.append(path)
    return files


def _fingerprint_map(
    run_root: Path,
    files: list[Path],
    *,
    external_anchor: Path | None = None,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in files:
        resolved = path.resolve()
        try:
            key = resolved.relative_to(run_root).as_posix()
        except ValueError:
            # 库回退：模板文件在 run 之外，锚定模板库根并加 library/ 前缀，
            # 键仍确定（create/verify 同码路径一致）。
            if external_anchor is None:
                raise
            key = f"library/{resolved.relative_to(external_anchor).as_posix()}"
        mapping[key] = sha256_file(resolved)
    return mapping


def _template_library_root(root: Path) -> Path:
    """模板库根：run 本地优先，退回技能库 canonical（与渲染搜索同源）。"""
    snapshot = root / "input/asset-snapshot"
    if snapshot.exists():
        return snapshot / "builtin/canonical/templates"
    run_local = root / "template-library/canonical/templates"
    if run_local.is_dir():
        return run_local
    from ..asset_resolver import _candidate_bundle_roots
    for bundle_root in _candidate_bundle_roots():
        candidate = Path(bundle_root) / "template-library/canonical/templates"
        if candidate.is_dir():
            return candidate
    return run_local


def _used_template_files(root: Path, input_files: list[Path], *, allow_missing: bool) -> list[Path]:
    run_local_root = root / "template-library/canonical/templates"
    template_root = _template_library_root(root)
    selected = set()
    design_found = False
    for path in input_files:
        if path.suffix != ".json":
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if not isinstance(value, dict) or value.get("entity") != "resolved-design":
            continue
        design_found = True
        pages = value.get("pages")
        if not isinstance(pages, list) or any(not isinstance(page, dict) for page in pages):
            raise ReceiptError("delivery_template_binding_invalid")
        for page in pages:
            template_id = page.get("template_id")
            if template_id is None:
                continue
            if not isinstance(template_id, str) or not re.fullmatch(
                r"builtin:template:[a-z0-9][a-z0-9-]*", template_id
            ):
                raise ReceiptError("delivery_template_binding_invalid")
            selected.add(template_id.rsplit(":", 1)[-1])
    # 「缺绑定即拒绝」只对 run 本地模板根生效（run 自己 stage 了模板却无
    # 冻结绑定 = 不可解释）；库回退时无绑定表示该 run 未消费模板，留空清单。
    if run_local_root.is_dir() and not design_found:
        raise ReceiptError("delivery_template_binding_required")
    files = []
    templates_anchor = template_root.resolve()
    for slug in sorted(selected):
        directory = template_root / slug
        if directory.is_symlink() or not directory.resolve().is_relative_to(templates_anchor):
            raise ReceiptError("delivery_template_path_invalid")
        if (directory / "page.html").is_symlink():
            raise ReceiptError("delivery_template_path_invalid")
        if not allow_missing and not (directory / "page.html").is_file():
            raise ReceiptError("delivery_template_source_missing")
        files.extend(_iter_regular_files(directory))
    return files


def collect_fingerprints(run_root: str | Path, *, allow_missing: bool = False) -> dict[str, dict[str, str]]:
    """采集一个 run 目录的五类指纹；缺失类别记显式空清单。"""

    root = Path(run_root).resolve()

    page_files = [
        *(
            _iter_regular_files(root / "image-deck" / "origin_image")
        ),
        *(_iter_regular_files(root / "editable" / "pages")),
        *(
            path
            for path in _iter_regular_files(root / "final")
            if path.suffix.lower() in _DECK_LEVEL_SUFFIXES
        ),
    ]

    input_files = _iter_regular_files(root / "input")
    style_inputs = [
        path for path in input_files if _STYLE_SOURCE_RE.search(path.name)
    ]
    plain_inputs = [
        path for path in input_files if not _STYLE_SOURCE_RE.search(path.name)
    ]

    qa_files = [
        path
        for path in _iter_regular_files(root / "reports")
        if path.suffix.lower() == ".json" and path.name not in _REPORTS_EXCLUDED
    ]
    for name in ("validation-summary.json", "failure-report.json"):
        candidate = root / "final" / name
        if candidate.is_file() and not candidate.is_symlink():
            qa_files.append(candidate)

    preview_files = [
        *(_iter_regular_files(root / "reports" / "render-preview")),
        *(_iter_regular_files(root / "final" / "render-preview")),
    ]

    template_files = [
        *style_inputs,
        *_used_template_files(root, input_files, allow_missing=allow_missing),
    ]
    templates_anchor = _template_library_root(root).resolve()

    return {
        "page_artifacts": _fingerprint_map(root, page_files),
        "local_assets": _fingerprint_map(root, plain_inputs),
        "qa_reports": _fingerprint_map(root, qa_files),
        "render_previews": _fingerprint_map(root, preview_files),
        "template_style_sources": _fingerprint_map(
            root, template_files, external_anchor=templates_anchor
        ),
    }


def _run_identity(run_root: Path) -> dict[str, Any]:
    try:
        value = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {"run_id": None, "route": None}
    if not isinstance(value, dict):
        return {"run_id": None, "route": None}
    return {
        "run_id": value.get("run_id") if isinstance(value.get("run_id"), str) else None,
        "route": value.get("route") if isinstance(value.get("route"), str) else None,
    }


def content_binding_summary(run_root: str | Path) -> dict | None:
    """dashi K7：从冻结 run 输入派生内容绑定摘要（可重建，非第二份真值）。

    关联当前内容包（content_digest/页身份）、整册选择（policy/每页 layout）
    与冻结设计（design_digest）。输入缺失返回 None（无绑定的 run 不伪造）。
    """
    root = Path(run_root).resolve()
    summary: dict = {}
    pack_path = root / "input" / "page-content-pack.json"
    if pack_path.is_file():
        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ReceiptError("content_pack_unreadable")
        summary["content_digest"] = pack.get("content_digest")
        summary["page_ids"] = [p.get("page_id") for p in pack.get("pages", [])]
        summary["page_count"] = len(pack.get("pages", []))
    selection_path = root / "input" / "layout-selection.json"
    if selection_path.is_file():
        try:
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ReceiptError("layout_selection_unreadable")
        summary["selection_policy"] = selection.get("policy_version")
        summary["selection_status"] = selection.get("status")
        summary["selected_layouts"] = {
            pid: entry.get("layout_id")
            for pid, entry in (selection.get("selection") or {}).items()}
        summary["binding_digests"] = {
            pid: entry.get("binding_digest")
            for pid, entry in (selection.get("selection") or {}).items()}
    design_path = root / "input" / "resolved-design.json"
    if design_path.is_file():
        try:
            design = json.loads(design_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ReceiptError("resolved_design_unreadable")
        summary["design_digest"] = design.get("design_digest")
        summary["design_context_digest"] = design.get("design_context_digest")
    return summary or None


def create_delivery_receipt(run_root: str | Path) -> dict[str, Any]:
    """采集五类指纹并原子写入收据；返回路径、sha256 与收据本体。"""

    root = Path(run_root).resolve()
    if not root.is_dir():
        raise ReceiptError("run_root_missing")
    fingerprints = collect_fingerprints(root)
    identity = _run_identity(root)
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "created_at": _utc_now(),
        "run_root": str(root),
        "run_id": identity["run_id"],
        "route": identity["route"],
        "delivery_stage": None,
        "builder_id": None,
        "fingerprints": fingerprints,
        "content_binding": content_binding_summary(root),
        "linked_assets": {
            "sources_manifest": None,
            "beta_sidecars": None,
        },
        "receipt_sha256_excludes_self": True,
    }
    target = root / RECEIPT_RELATIVE_PATH
    atomic_write_json(target, receipt)
    return {
        "path": str(target),
        "sha256": sha256_file(target),
        "receipt": receipt,
        "counts": {name: len(items) for name, items in fingerprints.items()},
    }


def _diff_fingerprints(
    recorded: dict[str, str], current: dict[str, str]
) -> list[dict[str, Any]]:
    """slides-grab diffFingerprints 的对称差：sha 变化/新增/缺失都算漂移。"""

    changed: list[dict[str, Any]] = []
    for path in sorted(set(recorded) | set(current)):
        before = recorded.get(path)
        after = current.get(path)
        if before != after:
            changed.append(
                {
                    "path": path,
                    "recorded_sha256": before,
                    "current_sha256": after,
                    "change": (
                        "modified"
                        if before is not None and after is not None
                        else ("added" if after is not None else "missing")
                    ),
                }
            )
    return changed


def _infer_impact(changed: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """按指纹类别推断波及面：页产物→页号；资产/样式源→全册；QA→仅 QA。"""

    impacted_pages: list[int] = []
    page_paths: list[str] = []
    deck_level_drift = False
    for entry in changed.get("page_artifacts", []):
        number = _page_number(entry["path"])
        if number is None:
            deck_level_drift = True
        else:
            impacted_pages.append(number)
            page_paths.append(entry["path"])

    actions: list[str] = []
    if impacted_pages or deck_level_drift:
        if deck_level_drift:
            actions.append("成册级页产物漂移：全册页都在波及面，重走交付验证")
        else:
            actions.append(
                "页产物漂移：该页重走视觉 QA 并创建新的 artifact revision"
            )
    if changed.get("local_assets"):
        actions.append("本地输入资产漂移：全册页都在波及面，重估样张继承")
    if changed.get("template_style_sources"):
        actions.append("模板/样式源漂移：全册页都在波及面，重估样张继承")
    if changed.get("qa_reports"):
        actions.append("QA 报告漂移：仅需重跑 QA，不必重建页面")
    if changed.get("render_previews"):
        actions.append("渲染预览漂移：重跑独立渲染证据")

    if changed.get("local_assets") or changed.get("template_style_sources"):
        scope = "deck"
    elif changed.get("page_artifacts"):
        scope = "deck" if deck_level_drift else "page"
    elif changed.get("qa_reports"):
        scope = "qa_only"
    elif changed.get("render_previews"):
        scope = "render_previews"
    else:
        scope = "none"

    return {
        "scope": scope,
        "impacted_pages": sorted(set(impacted_pages)),
        "impacted_page_paths": sorted(page_paths),
        "recommended_actions": actions,
    }


def _load_receipt(root: Path) -> dict[str, Any]:
    target = root / RECEIPT_RELATIVE_PATH
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ReceiptError("delivery_receipt_invalid") from exc
    if not isinstance(value, dict):
        raise ReceiptError("delivery_receipt_invalid")
    if value.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ReceiptError("delivery_receipt_schema_unsupported")
    if value.get("kind") != RECEIPT_KIND:
        raise ReceiptError("delivery_receipt_invalid")
    fingerprints = value.get("fingerprints")
    if not isinstance(fingerprints, dict) or not set(fingerprints) == set(
        FINGERPRINT_CLASSES
    ):
        raise ReceiptError("delivery_receipt_invalid")
    for items in fingerprints.values():
        if not isinstance(items, dict) or not all(
            isinstance(digest, str) and len(digest) == 64
            for digest in items.values()
        ):
            raise ReceiptError("delivery_receipt_invalid")
    return value


def verify_delivery_receipt(run_root: str | Path) -> dict[str, Any]:
    """重算五类指纹与收据比对，输出 fresh/stale + 波及面推断。

    返回 ``status`` ∈ ``fresh | stale | missing | invalid``；``missing``
    表示收据文件不存在（不抛错，交由调用方决定阻断语义）。
    """

    root = Path(run_root).resolve()
    target = root / RECEIPT_RELATIVE_PATH
    if not target.is_file():
        return {
            "status": "missing",
            "run_root": str(root),
            "receipt_path": str(target),
            "fresh": False,
            "changed": [],
            "impact": {"scope": "none", "impacted_pages": [], "impacted_page_paths": [], "recommended_actions": []},
        }
    try:
        receipt = _load_receipt(root)
    except ReceiptError:
        return {
            "status": "invalid",
            "run_root": str(root),
            "receipt_path": str(target),
            "fresh": False,
            "changed": [],
            "impact": {"scope": "none", "impacted_pages": [], "impacted_page_paths": [], "recommended_actions": []},
        }

    recorded: dict[str, dict[str, str]] = receipt["fingerprints"]
    try:
        current = collect_fingerprints(root, allow_missing=True)
    except ReceiptError as exc:
        return {
            "status": "invalid", "run_root": str(root), "receipt_path": str(target),
            "fresh": False, "reason_code": str(exc), "changed": [],
            "impact": {"scope": "deck", "impacted_pages": [], "impacted_page_paths": [],
                       "recommended_actions": ["修复冻结设计与模板源绑定后重新生成收据"]},
        }
    changed_by_class = {
        name: _diff_fingerprints(recorded[name], current[name])
        for name in FINGERPRINT_CLASSES
    }
    changed = [
        {"class": name, **entry}
        for name in FINGERPRINT_CLASSES
        for entry in changed_by_class[name]
    ]
    # dashi K7：内容绑定摘要（内容包/整册选择/冻结设计）漂移同样失效收据——
    # 页身份、页序或选中版式变化不能被指纹类别掩盖。
    try:
        current_binding = content_binding_summary(root)
    except ReceiptError as exc:
        return {
            "status": "invalid", "run_root": str(root), "receipt_path": str(target),
            "fresh": False, "reason_code": str(exc), "changed": [],
            "impact": {"scope": "deck", "impacted_pages": [], "impacted_page_paths": [],
                       "recommended_actions": ["修复 run 输入区内容绑定文件后重新生成收据"]},
        }
    if receipt.get("content_binding") != current_binding:
        changed.append({"class": "content_binding", "path": "input/*",
                        "before": "recorded", "after": "current"})
    impact = _infer_impact(changed_by_class)
    return {
        "status": "stale" if changed else "fresh",
        "run_root": str(root),
        "receipt_path": str(target),
        "created_at": receipt.get("created_at"),
        "fresh": not changed,
        "changed": changed,
        "impact": impact,
    }
