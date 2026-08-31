"""D1-T5 render provenance sidecar 的校验与并入。

``render page/chart`` 成功时在产物旁写 ``<out>.render.json``（schema 见
``page.render_page`` / ``chart.render_chart``）；``image record
--render-receipt <path>`` 消费它：

1. 校验 sidecar 结构（kind/schema_version/out_sha256）。
2. 校验 ``out_sha256`` 与被 record 的落盘产物一致（防张冠李戴）。
3. 把 sidecar 内容并入 ``slide_jobs.json`` 该页 entry 的 ``provenance``
   字段（在 ``ImageDeckAdapter.record`` 完成后、同一 FileLock 纪律下
   追加写；provenance 留在 slide_jobs entry 层，不动 PageArtifact schema
   ——设计 §3.1.5 / §10.3-1）。

backend 枚举合同：``render:html`` | ``render:mermaid`` | ``render:echarts``；
sidecar 的 ``backend`` 必须与 record 的 ``--backend`` 一致。
"""

from __future__ import annotations

import json
from filelock import FileLock
from pathlib import Path
from typing import Any

from ..storage import atomic_write_json, sha256_file
from .errors import RenderError

PROVENANCE_KIND = "render_provenance"
RENDER_BACKENDS = ("render:html", "render:mermaid", "render:echarts")
REQUIRED_FIELDS = (
    "schema_version",
    "kind",
    "backend",
    "renderer",
    "out_sha256",
    "width",
    "height",
)


def load_render_receipt(path: str | Path) -> dict[str, Any]:
    """读取并结构校验 sidecar；不匹配合同 → ``render_receipt_invalid``。"""

    receipt_path = Path(path)
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RenderError("render_receipt_invalid", f"unreadable: {exc}") from exc
    if not isinstance(value, dict) or value.get("kind") != PROVENANCE_KIND:
        raise RenderError("render_receipt_invalid", "kind is not render_provenance")
    if value.get("schema_version") != 1:
        raise RenderError("render_receipt_invalid", "unsupported schema_version")
    if value.get("backend") not in RENDER_BACKENDS:
        raise RenderError(
            "render_receipt_invalid",
            f"backend must be one of {RENDER_BACKENDS}, got {value.get('backend')!r}",
        )
    missing = [field for field in REQUIRED_FIELDS if field not in value]
    if missing:
        raise RenderError("render_receipt_invalid", f"missing fields: {missing}")
    return value


def verify_receipt_matches_artifact(
    receipt: dict[str, Any], artifact_path: str | Path
) -> None:
    """sidecar 的 ``out_sha256`` 必须与被 record 的产物逐字节一致。"""

    artifact = Path(artifact_path)
    if not artifact.is_file():
        raise RenderError("render_receipt_invalid", f"artifact missing: {artifact}")
    actual = sha256_file(artifact)
    if actual != receipt.get("out_sha256"):
        raise RenderError(
            "render_receipt_invalid",
            "out_sha256 mismatch: receipt was not issued for this artifact",
        )


def attach_provenance_to_slide(
    image_deck_dir: str | Path,
    number: int,
    receipt: dict[str, Any],
    *,
    backend: str | None = None,
) -> dict[str, Any]:
    """把 sidecar 内容并入 ``slide_jobs.json`` 该页 entry。

    复用 adapter 的锁文件与原子写纪律（不发明第二套状态迁移）；每次并入
    作为一个 revision 变更。返回并入后的 entry 摘要。
    """

    deck_dir = Path(image_deck_dir)
    jobs_path = deck_dir / "slide_jobs.json"
    if not jobs_path.is_file():
        raise RenderError("render_receipt_invalid", "slide_jobs.json missing")
    if backend is not None and receipt.get("backend") != backend:
        raise RenderError(
            "render_receipt_invalid",
            f"receipt backend {receipt.get('backend')!r} != record backend {backend!r}",
        )
    with FileLock(str(deck_dir / ".slide_jobs.json.lock")):
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
        slide = next(
            (item for item in jobs.get("slides", []) if item.get("number") == number),
            None,
        )
        if slide is None:
            raise RenderError("render_receipt_invalid", f"unknown page number {number}")
        artifact = deck_dir / slide["artifact"]
        verify_receipt_matches_artifact(receipt, artifact)
        slide["provenance"] = dict(receipt)
        jobs["revision"] = int(jobs.get("revision", 0)) + 1
        atomic_write_json(jobs_path, jobs)
    return {
        "slide_id": slide.get("slide_id"),
        "backend": receipt.get("backend"),
        "template_id": receipt.get("template_id"),
        "data_sha256": receipt.get("data_sha256"),
        "out_sha256": receipt.get("out_sha256"),
        "renderer": receipt.get("renderer"),
    }
