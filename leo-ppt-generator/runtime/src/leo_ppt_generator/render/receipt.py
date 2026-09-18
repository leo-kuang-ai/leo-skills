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


def _fingerprint_map(run_root: Path, files: list[Path]) -> dict[str, str]:
    mapping = {}
    for path in files:
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ReceiptError("delivery_artifact_path_invalid")
        try:
            relative = path.relative_to(run_root).as_posix()
        except ValueError as exc:
            raise ReceiptError("delivery_artifact_path_invalid") from exc
        mapping[relative] = sha256_file(path)
    return mapping


def _used_template_files(committed: dict) -> list[Path]:
    """仅按冻结 binding 的资产身份收集模板与主题，支持 builtin/user scope。"""
    from ..asset_resolver import AssetResolver
    resolver = AssetResolver.from_snapshot(committed["root"] / "asset-snapshot")
    identities = {pin["asset_id"] for bindings in committed["payload"]["bindings"].values()
                  for binding in bindings.values() for pin in binding["effective"]["assets"]}
    files = []
    for identity in sorted(identities):
        entity = resolver.resolve(identity)
        if entity["kind"] not in {"template", "theme", "style"}:
            continue
        path = Path(entity["path"])
        if not path.is_absolute():
            path = Path(entity["trusted_root"]) / path
        files.extend(_iter_regular_files(path.parent))
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

    from ..application.expression_pipeline import load_committed_input, materialization_paths, ExpressionPipelineError
    try:
        committed = load_committed_input(root)
    except ExpressionPipelineError as exc:
        raise ReceiptError(exc.reason_code) from exc
    for lane, bindings in committed["payload"]["bindings"].items():
        for pid in bindings:
            for path in materialization_paths(root, lane, pid):
                if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
                    raise ReceiptError("delivery_artifact_path_invalid")
                if path.is_file():
                    page_files.append(path)
                elif not allow_missing:
                    raise ReceiptError("delivery_materialization_missing")
            if not allow_missing:
                from ..content_projection import load_run_binding, verify_binding_reference
                try:
                    bound = load_run_binding(root, pid, backend=lane)
                    artifact, sidecar = materialization_paths(root, lane, pid)
                    if lane == "render:html":
                        from .provenance import load_render_receipt, verify_receipt_matches_artifact
                        rendered = load_render_receipt(sidecar)
                        verify_receipt_matches_artifact(rendered, artifact)
                        verify_binding_reference(rendered, bound["binding"])
                    else:
                        from ..image_deck.expression_adapter import verify_provider_export
                        verify_provider_export(json.loads(sidecar.read_text()), root=sidecar.parent, binding=bound["binding"])
                except (ValueError, OSError) as exc:
                    raise ReceiptError("delivery_materialization_invalid: " + str(exc)) from exc
    input_files = [root / "input/current.json", *_iter_regular_files(committed["root"])]
    # 交付可附带来源及讲稿合同；它们不替代冻结表达，但修改仍须使收据失效。
    for name in ("sources-manifest.json", "slides.json"):
        supplemental = root / "input" / name
        if supplemental.is_symlink():
            raise ReceiptError("delivery_artifact_path_invalid")
        if supplemental.is_file():
            input_files.append(supplemental)
    template_files = set(_used_template_files(committed))
    template_files.update(path for path in input_files if _STYLE_SOURCE_RE.search(path.name))
    plain_inputs = [path for path in input_files if path not in template_files]


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
        *(_iter_regular_files(root / "previews")),
        *(_iter_regular_files(root / "reports" / "render-preview")),
        *(_iter_regular_files(root / "final" / "render-preview")),
    ]


    return {
        "page_artifacts": _fingerprint_map(root, page_files),
        "local_assets": _fingerprint_map(root, plain_inputs),
        "qa_reports": _fingerprint_map(root, qa_files),
        "render_previews": _fingerprint_map(root, preview_files),
        "template_style_sources": _fingerprint_map(root, sorted(template_files)),
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
    """只从提交代派生所有 lane 的摘要；不重新选择，不从主 lane 外推其他 lane。"""
    root = Path(run_root).resolve()
    from ..application.expression_pipeline import load_committed_input, materialization_paths, ExpressionPipelineError
    from ..content_projection import verify_binding_reference
    try:
        committed = load_committed_input(root)
        payload = committed["payload"]
        pack = payload["pack"]
        summary = {"content_digest": pack["content_digest"], "page_ids": [p["page_id"] for p in pack["pages"]],
            "page_count": len(pack["pages"]), "input_generation": committed["generation"],
            "expression_binding_digests": {}, "materialization_binding_digests": {},
            "selected_layouts": {}, "design_digests": {}, "page_artifact_numbers": {}}
        for lane, selection in payload["lane_selections"].items():
            summary["materialization_binding_digests"][lane] = {}
            summary["selected_layouts"][lane] = {}
            summary["design_digests"][lane] = payload["designs"][lane]["design_digest"]
            for pid, entry in selection["selection"].items():
                verify_binding_reference(entry, entry["binding"])
                expression = entry["expression_binding_digest"]
                if summary["expression_binding_digests"].get(pid, expression) != expression:
                    raise ValueError("expression_binding_cross_lane_mismatch")
                summary["expression_binding_digests"][pid] = expression
                summary["materialization_binding_digests"][lane][pid] = entry["materialization_binding_digest"]
                summary["selected_layouts"][lane][pid] = entry["layout_id"]
                for path in materialization_paths(root, lane, pid):
                    summary["page_artifact_numbers"][path.relative_to(root).as_posix()] = entry["binding"]["number"]
        return summary
    except ExpressionPipelineError as exc:
        raise ReceiptError(exc.reason_code) from exc
    except (KeyError, ValueError, TypeError) as exc:
        raise ReceiptError("content_binding_invalid: " + str(exc)) from exc


def _disclosure_summary(root: Path) -> dict[str, Any] | None:
    """U14 披露工件摘要（延迟导入，避免收据基础面依赖披露模块）。"""

    try:
        from ..delivery_disclosure import disclosure_summary

        return disclosure_summary(root)
    except Exception:  # 披露面任何异常不得阻断收据采集
        return None


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
        # R-79/U14：交付披露摘要为**加性块**，不属于五类指纹——verify 不比对
        # 本块（披露工件按 not_run 口径缺失即 null），旧收据验证不受影响。
        "disclosure": _disclosure_summary(root),
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


def _infer_impact(changed: dict[str, list[dict[str, Any]]], page_numbers=None) -> dict[str, Any]:
    """按指纹类别推断波及面：页产物→页号；资产/样式源→全册；QA→仅 QA。"""

    impacted_pages: list[int] = []
    page_paths: list[str] = []
    deck_level_drift = False
    for entry in changed.get("page_artifacts", []):
        number = (page_numbers or {}).get(entry["path"], _page_number(entry["path"]))
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
    binding = value.get("content_binding")
    fields = {"content_digest", "page_ids", "page_count", "input_generation",
              "expression_binding_digests", "materialization_binding_digests",
              "selected_layouts", "design_digests", "page_artifact_numbers"}
    if not isinstance(binding, dict) or set(binding) != fields:
        raise ReceiptError("binding_schema_mismatch")
    try:
        pages = binding["page_ids"]
        if (not isinstance(pages, list) or not pages or any(not isinstance(pid, str) or not pid for pid in pages)
                or len(set(pages)) != len(pages) or type(binding["page_count"]) is not int
                or binding["page_count"] != len(pages)
                or not isinstance(binding["expression_binding_digests"], dict)
                or set(binding["expression_binding_digests"]) != set(pages)):
            raise ValueError("page identity")
        materials = binding["materialization_binding_digests"]
        if (not isinstance(materials, dict) or not materials or not set(materials).issubset({"render:html", "image"})
                or set(binding["selected_layouts"]) != set(materials)
                or set(binding["design_digests"]) != set(materials)):
            raise ValueError("lane identity")
        hashes = [binding["content_digest"], binding["input_generation"],
                  *binding["expression_binding_digests"].values(), *binding["design_digests"].values()]
        seen_pages = set()
        for lane, entries in materials.items():
            if not isinstance(entries, dict) or not entries or not set(entries).issubset(pages):
                raise ValueError("page identity")
            if set(entries) != set(binding["selected_layouts"][lane]):
                raise ValueError("layout identity")
            hashes.extend(entries.values())
            seen_pages.update(entries)
        if seen_pages != set(pages) or any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes):
            raise ValueError("binding digest")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ReceiptError("binding_schema_mismatch") from exc
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
    except ReceiptError as exc:
        return {
            "status": "invalid",
            "reason_code": str(exc),
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
    impact = _infer_impact(changed_by_class, (current_binding or {}).get("page_artifact_numbers"))
    return {
        "status": "stale" if changed else "fresh",
        "run_root": str(root),
        "receipt_path": str(target),
        "created_at": receipt.get("created_at"),
        "fresh": not changed,
        "changed": changed,
        "impact": impact,
    }
