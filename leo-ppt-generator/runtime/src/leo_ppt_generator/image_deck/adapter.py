"""固定 codex-ppt 图片能力的稳定 adapter。"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from filelock import FileLock

from .._vendor.codex_ppt import assemble_ppt
from ..contracts import ContractError, PageArtifact
from ..storage import (
    atomic_materialize,
    atomic_write_json,
    canonical_json,
    fsync_file,
    sha256_bytes,
    sha256_file,
)

# sources_manifest.json v1 的轻量合同校验（完整校验在技能包
# scripts/check_sources_manifest.py；runtime 侧只做冻结前阻断）。
SOURCES_SCHEMA_VERSION = 1
SOURCES_MANIFEST_KIND = "visual-sources"
SOURCES_SOURCE_CLASSES = frozenset(
    {
        "user-material",
        "derived-crop",
        "ai-generated",
        "illustrative",
        "native-rebuild",
        "deterministic-render",
        "deterministic-overlay",
    }
)
SOURCES_TIERS = frozenset({"引用", "估算", "示意"})
SOURCES_NULL_REF_CLASSES = frozenset(
    {"ai-generated", "native-rebuild", "deterministic-overlay"}
)
_SOURCES_SENSITIVE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|password|authorization|bearer|secret)"
)
_SOURCES_PAGE_ID = re.compile(r"^slide_(\d+)$")


def validate_sources_manifest(data: Any) -> dict[str, Any]:
    """冻结前轻量校验：结构、枚举、自指纹与敏感扫描；非法即 ContractError。"""
    if not isinstance(data, dict):
        raise ContractError("sources_manifest_invalid")
    if data.get("schema_version") != SOURCES_SCHEMA_VERSION or data.get(
        "manifest_kind"
    ) != SOURCES_MANIFEST_KIND:
        raise ContractError("sources_manifest_invalid")
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ContractError("sources_manifest_invalid")
    for page in pages:
        if not isinstance(page, dict):
            raise ContractError("sources_manifest_invalid")
        page_id = page.get("page_id")
        if not isinstance(page_id, str) or not _SOURCES_PAGE_ID.match(page_id):
            raise ContractError("sources_manifest_invalid")
        visuals = page.get("visuals")
        if not isinstance(visuals, list):
            raise ContractError("sources_manifest_invalid")
        for visual in visuals:
            if not isinstance(visual, dict):
                raise ContractError("sources_manifest_invalid")
            if visual.get("source_class") not in SOURCES_SOURCE_CLASSES:
                raise ContractError("sources_manifest_invalid")
            tier = visual.get("tier")
            if tier not in SOURCES_TIERS:
                raise ContractError("sources_manifest_invalid")
            if visual.get("source_ref") is None and (
                visual.get("source_class") not in SOURCES_NULL_REF_CLASSES
                or tier == "引用"
            ):
                raise ContractError("sources_manifest_invalid")
    recorded = data.get("contents_sha256")
    payload = {key: value for key, value in data.items() if key != "contents_sha256"}
    if not isinstance(recorded, str) or sha256_bytes(
        canonical_json(payload).encode()
    ) != recorded:
        raise ContractError("sources_manifest_invalid")
    if _SOURCES_SENSITIVE.search(canonical_json(payload)):
        raise ContractError("sources_manifest_invalid")
    return data


class ImageDeckAdapter:
    contract_version = 1

    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.jobs_path = self.run_dir / "slide_jobs.json"
        self.images_dir = self.run_dir / "origin_image"

    def prepare(
        self,
        slides: list[dict[str, Any]],
        sources_manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not slides or len(slides) > 50:
            raise ContractError("input_too_large" if len(slides) > 50 else "empty_deck")
        numbers = [int(slide["number"]) for slide in slides]
        if numbers != list(range(1, len(slides) + 1)):
            raise ContractError("invalid_page_sequence")
        if sources_manifest is not None:
            validate_sources_manifest(sources_manifest)
            fingerprint = sha256_bytes(
                canonical_json(
                    {"slides": slides, "sources_manifest": sources_manifest}
                ).encode()
            )
        else:
            # 无 sources 输入时保持旧算法逐字节不变（旧 run 恢复兼容，CI-3）。
            fingerprint = sha256_bytes(canonical_json(slides).encode())
        if self.jobs_path.is_file():
            existing = self._jobs()
            if existing.get("prepare_fingerprint") == fingerprint:
                return existing
            raise ContractError("image_prepare_fingerprint_conflict")
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.chmod(0o700)
        jobs = {
            "schema_version": 1,
            "revision": 0,
            "prepare_fingerprint": fingerprint,
            "run_status": "prepared",
            "operations": {},
            "sources": (
                None
                if sources_manifest is None
                else {
                    "path": "input/sources-manifest.json",
                    "contents_sha256": sources_manifest.get("contents_sha256"),
                }
            ),
            "slides": [
                {
                    "number": number,
                    "slide_id": f"slide_{number:02d}",
                    "status": "pending",
                    "notes": str(slide.get("notes", "")),
                }
                for number, slide in zip(numbers, slides)
            ],
        }
        atomic_write_json(self.jobs_path, jobs)
        return jobs

    def _jobs(self) -> dict[str, Any]:
        if not self.jobs_path.is_file():
            raise ContractError("image_deck_not_prepared")
        return json.loads(self.jobs_path.read_text(encoding="utf-8"))

    def _assert_run_mutable(self) -> None:
        run_path = self.run_dir.parent / "run.json"
        if run_path.is_file():
            try:
                status = json.loads(run_path.read_text(encoding="utf-8")).get("status")
            except (OSError, ValueError, TypeError) as exc:
                raise ContractError("run_index_invalid") from exc
            if status == "cancelled":
                raise ContractError("run_cancelled_mutation_forbidden")

    def state_hash(self) -> str:
        return sha256_bytes(canonical_json(self._jobs()).encode())

    def record(
        self,
        number: int,
        image: str | Path,
        *,
        backend: str,
        expected_revision: int,
        operation_id: str,
        agent_id: str | None = None,
        expected_state_hash: str | None = None,
        lease: str | None = None,
        generation: int | None = None,
    ) -> PageArtifact:
        self._assert_run_mutable()
        source = Path(image).resolve()
        if not source.is_file():
            raise ContractError("missing_page_artifact")
        fingerprint = sha256_bytes(
            canonical_json(
                {
                    "number": number,
                    "source_sha256": sha256_file(source),
                    "backend": backend,
                    "agent_id": agent_id,
                    "expected_state_hash": expected_state_hash,
                    "lease": lease,
                    "generation": generation,
                }
            ).encode()
        )
        with FileLock(str(self.run_dir / ".slide_jobs.json.lock")):
            jobs = self._jobs()
            operation = jobs["operations"].get(operation_id)
            if operation:
                if operation["fingerprint"] != fingerprint:
                    raise ContractError("idempotency_conflict")
                slide = next(item for item in jobs["slides"] if item["number"] == number)
                target = self.run_dir / slide["artifact"]
                return PageArtifact.from_source(
                    f"page_{number:03d}", "image", target, target, None, notes=slide["notes"]
                )
            if expected_state_hash and sha256_bytes(canonical_json(jobs).encode()) != expected_state_hash:
                raise ContractError("state_hash_conflict")
            if jobs["revision"] != expected_revision:
                raise ContractError("vendor_revision_conflict")
            try:
                slide = next(item for item in jobs["slides"] if item["number"] == number)
            except StopIteration as exc:
                raise ContractError("unknown_page") from exc
            target = self.images_dir / f"slide_{number:02d}{source.suffix.lower()}"
            shutil.copy2(source, target)
            fsync_file(target)
            slide.update(
                {
                    "status": "recorded",
                    "artifact": target.relative_to(self.run_dir).as_posix(),
                    "sha256": sha256_file(target),
                    "backend": backend,
                    "agent_id": agent_id,
                }
            )
            jobs["operations"][operation_id] = {
                "fingerprint": fingerprint,
                "status": "completed",
                "slide_id": slide["slide_id"],
                "lease": lease,
                "generation": generation,
            }
            jobs["revision"] += 1
            atomic_write_json(self.jobs_path, jobs)
        return PageArtifact.from_source(
            f"page_{number:03d}", "image", target, target, None, notes=slide["notes"]
        )

    def artifacts(self) -> list[PageArtifact]:
        jobs = self._jobs()
        artifacts = []
        for slide in jobs["slides"]:
            if slide["status"] != "recorded":
                raise ContractError("missing_page_artifact")
            path = self.run_dir / slide["artifact"]
            if not path.is_file() or sha256_file(path) != slide["sha256"]:
                raise ContractError("artifact_hash_mismatch")
            artifacts.append(
                PageArtifact.from_source(
                    f"page_{slide['number']:03d}", "image", path, path, None, notes=slide["notes"]
                )
            )
        return artifacts

    def finalize(self, output: str | Path, *, rebuild: bool = False) -> dict[str, Any]:
        self._assert_run_mutable()
        lock_root = self.run_dir.parent if (self.run_dir.parent / "run.json").is_file() else self.run_dir
        with FileLock(str(lock_root / ".run-mutation.lock")):
            return self._finalize_locked(output, rebuild=rebuild)

    def _finalize_locked(self, output: str | Path, *, rebuild: bool = False) -> dict[str, Any]:
        artifacts = self.artifacts()
        output_path = Path(output).resolve()
        artifact_fingerprint = sha256_bytes(
            canonical_json([artifact.artifact_sha256 for artifact in artifacts]).encode()
        )
        jobs = self._jobs()
        previous = jobs.get("delivery")
        if previous:
            previous_path = Path(previous["pptx"])
            if (
                previous.get("artifact_fingerprint") == artifact_fingerprint
                and previous_path.is_file()
                and sha256_file(previous_path) == previous.get("sha256")
            ):
                return {
                    "status": "completed",
                    "delivery_type": "image",
                    "pptx": str(previous_path),
                    "pptx_sha256": previous["sha256"],
                    "page_count": len(artifacts),
                    "idempotency_status": "replayed",
                    "artifact_revision": previous.get("revision", 1),
                    "pages": previous.get("pages", []),
                }
            if not rebuild:
                raise ContractError("image_assemble_rebuild_required")
            revision = int(previous.get("revision", 1)) + 1
            output_path = output_path.with_name(f"{output_path.stem}.r{revision}{output_path.suffix}")
        else:
            revision = 1
        notes = {index: artifact.notes for index, artifact in enumerate(artifacts, 1) if artifact.notes}
        images = [artifact.artifact_path for artifact in artifacts]
        def build(destination: Path) -> None:
            if not assemble_ppt.create_presentation(images, str(destination), speaker_notes=notes):
                raise ContractError("finalizer_failed")

        atomic_materialize(output_path, build)
        output_sha256 = sha256_file(output_path)
        jobs["run_status"] = "completed"
        jobs["delivery"] = {
            "type": "image",
            "pptx": str(output_path),
            "sha256": output_sha256,
            "artifact_fingerprint": artifact_fingerprint,
            "revision": revision,
            "pages": [
                {
                    "page_id": artifact.page_id,
                    "artifact_ref": artifact.artifact_path,
                    "artifact_sha256": artifact.artifact_sha256,
                    "source_ref": artifact.source_path,
                    "source_sha256": artifact.source_sha256,
                    "notes": artifact.notes,
                    "width": artifact.width,
                    "height": artifact.height,
                }
                for artifact in artifacts
            ],
        }
        jobs["revision"] += 1
        atomic_write_json(self.jobs_path, jobs)
        return {
            "status": "completed",
            "delivery_type": "image",
            "pptx": str(output_path),
            "pptx_sha256": output_sha256,
            "page_count": len(artifacts),
            "idempotency_status": "created",
            "artifact_revision": revision,
            "pages": jobs["delivery"]["pages"],
        }
