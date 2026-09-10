"""冻结已完成 image delivery，供 upgrade routes 作为唯一输入基线。"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path

from ..contracts import ContractError
from ..image_deck.adapter import ImageDeckAdapter
from ..storage import (
    atomic_write_json,
    canonical_json,
    durable_copy_file,
    fsync_file,
    sha256_file,
)


class BaselineError(ContractError):
    reason_code = "upgrade_baseline_error"


# 源 run 输入区可关联快照（dashi K4）：内容包与冻结设计随 baseline 复制，
# 目标恢复只依赖已验证本地快照，不要求源目录在线。
_LINKED_INPUTS = {
    "content_pack": "input/page-content-pack.json",
    "resolved_design": "input/resolved-design.json",
}


def _linked_input_snapshots(source_root: Path) -> dict:
    """采集源 run 输入区关联快照的摘要（文件可缺，摘要在场必须可验证）。"""
    snapshots = {}
    for name, relative in _LINKED_INPUTS.items():
        path = source_root / relative
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BaselineError("upgrade_baseline_source_invalid") from exc
        entry = {"source_path": str(path), "sha256": sha256_file(path)}
        if isinstance(payload, dict):
            for key in ("content_digest", "design_digest"):
                if isinstance(payload.get(key), str):
                    entry[key] = payload[key]
        snapshots[name] = entry
    return snapshots


def load_baseline(run_dir: str | Path) -> dict:
    """读取并重新验证不可变 baseline；任何内容漂移都 fail closed。"""
    root = Path(run_dir).resolve()
    manifest_path = root / "image-baseline" / "baseline.json"
    if not manifest_path.is_file():
        raise BaselineError("upgrade_baseline_required")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages = value["pages"]
        delivery = value["delivery"]
        expected_fingerprint = value.get("manifest_fingerprint", value["baseline_fingerprint"])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BaselineError("upgrade_baseline_manifest_invalid") from exc
    if not isinstance(pages, list) or not pages:
        raise BaselineError("upgrade_baseline_manifest_invalid")
    for page in pages:
        try:
            artifact = Path(page["artifact"])
            if not artifact.is_file() or sha256_file(artifact) != page["artifact_sha256"]:
                raise BaselineError("upgrade_baseline_artifact_changed")
            notes = str(page.get("notes", ""))
            if hashlib.sha256(notes.encode("utf-8")).hexdigest() != page.get("notes_sha256"):
                raise BaselineError("upgrade_baseline_notes_changed")
            if int(page["width"]) <= 0 or int(page["height"]) <= 0:
                raise BaselineError("upgrade_baseline_manifest_invalid")
        except BaselineError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise BaselineError("upgrade_baseline_manifest_invalid") from exc
    delivery_path = Path(delivery.get("pptx", ""))
    if not delivery_path.is_file() or sha256_file(delivery_path) != delivery.get("pptx_sha256"):
        raise BaselineError("upgrade_baseline_delivery_changed")
    for name, snapshot in ((value.get("source_binding") or {}).get("linked_inputs") or {}).items():
        snapshot_path = Path(snapshot.get("path", ""))
        if not snapshot_path.is_file() or sha256_file(snapshot_path) != snapshot.get("sha256"):
            raise BaselineError("upgrade_baseline_source_invalid")
    payload = {
        key: item
        for key, item in value.items()
        if key not in {"baseline_fingerprint", "manifest_fingerprint"}
    }
    fingerprint = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    if fingerprint != expected_fingerprint:
        raise BaselineError("upgrade_baseline_manifest_changed")
    return value


def inspect_image_delivery(run_dir: str | Path) -> dict:
    root = Path(run_dir).resolve()
    run_path = root / "run.json"
    if not run_path.is_file():
        raise BaselineError("upgrade_baseline_source_missing")
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
        artifacts = ImageDeckAdapter(root / "image-deck").artifacts()
        jobs = json.loads((root / "image-deck" / "slide_jobs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        raise BaselineError("upgrade_baseline_source_invalid") from exc
    delivery = jobs.get("delivery")
    if not isinstance(delivery, dict) or not Path(delivery.get("pptx", "")).is_file():
        raise BaselineError("upgrade_baseline_delivery_missing")
    pptx = Path(delivery["pptx"]).resolve()
    if sha256_file(pptx) != delivery.get("sha256"):
        raise BaselineError("upgrade_baseline_delivery_hash_mismatch")
    pages = [
        {
            "page_id": artifact.page_id,
            "number": index,
            "source": artifact.source_path,
            "source_sha256": artifact.source_sha256,
            "artifact": artifact.artifact_path,
            "artifact_sha256": artifact.artifact_sha256,
            "notes": artifact.notes,
            "notes_sha256": hashlib.sha256(artifact.notes.encode("utf-8")).hexdigest(),
            "width": artifact.width,
            "height": artifact.height,
        }
        for index, artifact in enumerate(artifacts, 1)
    ]
    payload = {
        "schema_version": 1,
        "source_run_id": run.get("run_id"),
        "source_route": run.get("route"),
        "page_count": len(pages),
        "pages": pages,
        "delivery": {
            "pptx": str(pptx),
            "pptx_sha256": sha256_file(pptx),
            "artifact_fingerprint": delivery.get("artifact_fingerprint"),
        },
        "source_inputs": _linked_input_snapshots(root),
    }
    payload["baseline_fingerprint"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


def import_baseline(source_run: str | Path, target_run: str | Path) -> dict:
    source = inspect_image_delivery(source_run)
    target = Path(target_run).resolve()
    baseline_dir = target / "image-baseline"
    manifest_path = baseline_dir / "baseline.json"
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BaselineError("upgrade_baseline_manifest_invalid") from exc
        if existing.get("source_fingerprint", existing.get("baseline_fingerprint")) == source["baseline_fingerprint"]:
            return {**existing, "idempotency_status": "replayed"}
        raise BaselineError("upgrade_baseline_conflict")
    if source.get("source_route") != "generate":
        raise BaselineError("upgrade_baseline_route_mismatch")
    baseline_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    pages_dir = baseline_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        copied_pages = []
        for page in source["pages"]:
            source_path = Path(page["artifact"])
            destination = pages_dir / f"{page['page_id']}{source_path.suffix.lower()}"
            copied = durable_copy_file(source_path, destination, max_bytes=100 * 1024 * 1024)
            if copied["sha256"] != page["artifact_sha256"]:
                raise BaselineError("upgrade_baseline_artifact_changed")
            copied_page = {**page, "artifact": str(destination), "artifact_sha256": copied["sha256"]}
            copied_pages.append(copied_page)
        delivery_source = Path(source["delivery"]["pptx"])
        copied_delivery = durable_copy_file(
            delivery_source, baseline_dir / "image-delivery.pptx", max_bytes=100 * 1024 * 1024
        )
        if copied_delivery["sha256"] != source["delivery"]["pptx_sha256"]:
            raise BaselineError("upgrade_baseline_delivery_changed")
        # 关联输入快照（K4）：内容包与冻结设计复制进 baseline，复制完成并
        # 校验摘要后才随 manifest 一起发布；任何失败清理半份目录。
        copied_inputs = {}
        for name, snapshot in (source.get("source_inputs") or {}).items():
            snapshot_target = baseline_dir / f"{name}.json"
            copied_snapshot = durable_copy_file(
                Path(snapshot["source_path"]), snapshot_target, max_bytes=16 * 1024 * 1024)
            if copied_snapshot["sha256"] != snapshot["sha256"]:
                raise BaselineError("upgrade_baseline_source_invalid")
            copied_inputs[name] = {**snapshot, "path": str(snapshot_target)}
        target_run = {}
        target_run_path = target / "run.json"
        if target_run_path.is_file():
            try:
                target_run = json.loads(target_run_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise BaselineError("upgrade_baseline_manifest_invalid") from exc
        source_binding = {
            "source_run_id": source.get("source_run_id"),
            "source_run_path": str(Path(source_run).resolve()),
            "source_delivery_sha256": source["delivery"]["pptx_sha256"],
            "source_baseline_fingerprint": source["baseline_fingerprint"],
            "target_route": target_run.get("route", "upgrade-full"),
            "edit_backend": None,
            "linked_inputs": copied_inputs,
        }
        manifest = {
            **{k: v for k, v in source.items() if k != "source_inputs"},
            "baseline_id": uuid.uuid4().hex,
            "source_run_path": str(Path(source_run).resolve()),
            "source_fingerprint": source["baseline_fingerprint"],
            "pages": copied_pages,
            "delivery": {**source["delivery"], "pptx": str(baseline_dir / "image-delivery.pptx")},
            "source_binding": source_binding,
        }
        manifest_fingerprint = hashlib.sha256(
            canonical_json(
                {key: item for key, item in manifest.items() if key != "baseline_fingerprint"}
            ).encode("utf-8")
        ).hexdigest()
        # baseline_fingerprint 保持源 delivery 身份，manifest_fingerprint 绑定
        # target 内复制后的不可变路径与内容，兼容 inspect/import 的稳定 API。
        manifest["manifest_fingerprint"] = manifest_fingerprint
        manifest["baseline_fingerprint"] = source["baseline_fingerprint"]
        atomic_write_json(manifest_path, manifest)
        fsync_file(manifest_path)
    except (BaselineError, ValueError, OSError):
        # 失败不暴露可执行的半份基线：manifest 未发布前整目录清理
        # （durable_copy/atomic_write 的 ValueError/OSError 一并清理）。
        shutil.rmtree(baseline_dir, ignore_errors=True)
        raise
    return {**manifest, "idempotency_status": "created"}
