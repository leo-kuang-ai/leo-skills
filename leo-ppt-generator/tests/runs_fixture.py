"""合成 run fixture 工厂（控制台可视化测试与浏览器验收共用）。

按写侧契约（docs/plans/2026-09-07-004 R2 核验的字段级事实）生成 run 目录：
run.json / slide_jobs.json|page_jobs.json / events.ndjson / reports/timing.json /
observability/backend_stats.jsonl / logs/run.log / final/(deck.pptx+validation-summary)。
页 PNG 用 Pillow 纯色小图（无文字依赖）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

PNG_COLOR = (36, 87, 214)


def _png_bytes(color=PNG_COLOR, size=(96, 54)) -> bytes:
    try:
        from PIL import Image
        from io import BytesIO
    except ImportError:  # 无 Pillow 环境退化为最小合法 PNG（1x1）
        return bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000d49444154789c626001000000ffff030000060005"
            "57bfabd40000000049454e44ae426082"
        )
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_run(
    home: Path,
    *,
    project: str = "demo-proj",
    run_id: str = "a3f2c1d4e5b64708901234567890abcd",
    route: str = "generate",
    total: int = 12,
    recorded: int = 7,
    failed_pages: tuple[int, ...] = (3,),
    timeout_pages: tuple[int, ...] = (),
    active_pages: tuple[int, ...] = (),
    status: str = "in_progress",
    stage: str = "image.dispatch",
    with_png: bool = True,
    final: bool = False,
    bad_event_lines: int = 0,
    corrupt_run_json: bool = False,
    artifact_override: dict[int, str] | None = None,
    input_path: str = "/tmp/fixture-input.md",
) -> Path:
    run_dir = Path(home) / "projects" / project / "runs" / ("run-" + run_id[:8])
    (run_dir / "image-deck").mkdir(parents=True, exist_ok=True)
    (run_dir / "editable").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "observability").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "final").mkdir(parents=True, exist_ok=True)

    excluded = set(failed_pages) | set(timeout_pages) | set(active_pages)
    recorded_set = {n for n in range(1, total + 1) if n not in excluded} & set(
        # 取前 recorded 个可用页作为成功页，保证 completed == recorded 语义。
        [n for n in range(1, total + 1) if n not in excluded][:recorded]
    )
    completed = len(recorded_set)
    failed_count = len(failed_pages) + len(timeout_pages)

    if corrupt_run_json:
        (run_dir / "run.json").write_text("{ not-json", encoding="utf-8")
    else:
        run_json = {
            "schema_version": 1,
            "run_id": run_id,
            "route": route,
            "runtime_identity": "fixture",
            "revision": 9,
            "status": status,
            "stage": stage,
            "created_at": "2026-09-07T08:00:00Z",
            "page_order": list(range(1, total + 1)),
            "input": {"original_path": input_path, "kind": "content"},
            "domains": {
                "image": {
                    "path": "image-deck",
                    "progress": {
                        "total_units": total,
                        "completed": completed,
                        "failed": failed_count,
                        "active": len(active_pages),
                        "pending": total - completed - failed_count - len(active_pages),
                        "estimated_remaining_seconds": None,
                    },
                },
                "editable": {"path": "editable"},
            },
        }
        (run_dir / "run.json").write_text(
            json.dumps(run_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    slides = []
    for number in range(1, total + 1):
        slide_id = f"slide_{number:02d}"
        entry = {"number": number, "slide_id": slide_id, "status": "pending", "notes": None}
        if number in recorded_set:
            artifact = (artifact_override or {}).get(number, f"origin_image/{slide_id}.png")
            entry.update(
                status="recorded",
                artifact=artifact,
                sha256="fixture",
                backend="zhipu",
                agent_id="agent-fixture",
            )
            if with_png and artifact.startswith("origin_image/"):
                target = run_dir / "image-deck" / artifact
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(_png_bytes())
        slides.append(entry)
    (run_dir / "image-deck" / "slide_jobs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "revision": 3,
                "prepare_fingerprint": "fixture",
                "run_status": status,
                "operations": {},
                "sources": [],
                "slides": slides,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # editable page_jobs（active 落盘）
    pages = []
    for number in range(1, max(total, 1) + 1):
        page_status = "active" if number in active_pages else "pending"
        pages.append(
            {
                "page_id": f"page_{number:03d}",
                "number": number,
                "status": page_status,
                "source": f"slide_{number:02d}",
                "page_dir": f"editable/work/page_{number:03d}",
                "source_sha256": "fixture",
                "notes": None,
            }
        )
    (run_dir / "editable" / "page_jobs.json").write_text(
        json.dumps({"schema_version": 1, "pages": pages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    timing_pages = []
    for number in failed_pages:
        timing_pages.append(
            {"unit_id": f"slide_{number:02d}", "status": "failed", "reason_code": "upstream_image_failed"}
        )
    for number in timeout_pages:
        timing_pages.append(
            {"unit_id": f"slide_{number:02d}", "status": "timeout", "reason_code": "upstream_timeout"}
        )
    timing = {
        # 键名对齐生产 writer（observability.py：stage/duration_seconds），
        # 防止合成契约漂移掩盖读侧缺陷（产品评审#2 的根因）。
        "stages": [
            {"stage": "run advance --stage image.prepare", "started_at": "2026-09-07T08:00:01Z", "completed_at": "2026-09-07T08:00:04Z", "duration_seconds": 3.0, "status": "completed"},
            {"stage": "image prepare", "started_at": "2026-09-07T08:00:04Z", "completed_at": "2026-09-07T08:00:12Z", "duration_seconds": 8.0, "status": "completed"},
            {"stage": "image record --slide 1", "started_at": "2026-09-07T08:01:00Z", "completed_at": "2026-09-07T08:01:12Z", "duration_seconds": 12.0, "status": "completed"},
            {"stage": "image record --slide 3", "started_at": "2026-09-07T08:02:00Z", "completed_at": "2026-09-07T08:02:31Z", "duration_seconds": 31.0, "status": "failed"},
        ],
        "pages": timing_pages,
        "backend_calls": [],
        "summary": {"total_duration_seconds": 621.4},
    }
    (run_dir / "reports" / "timing.json").write_text(
        json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    events = []
    seq = 0

    def emit(kind: str, data: dict) -> None:
        nonlocal seq
        seq += 1
        events.append({"schema_version": 1, "seq": seq, "at": f"2026-09-07T08:{seq:02d}:00Z", "kind": kind, "data": data})

    emit("run.created", {"actor": "agent-fixture", "status": "created"})
    emit("run.stage_advanced", {"subject": "image.prepare", "status": "ok"})
    emit("image.prepared", {"actor": "agent-fixture", "status": "ok", "slide_id": None})
    emit("run.stage_advanced", {"subject": "image.dispatch", "status": "ok"})
    for number in sorted(recorded_set):
        emit("image.recorded", {"actor": "agent-fixture", "status": "ok", "slide_id": f"slide_{number:02d}", "artifact_ref": f"origin_image/slide_{number:02d}.png"})
    emit("run.retry", {"status": "retrying", "reason_code": "upstream_image_failed"})
    lines = [json.dumps(event, ensure_ascii=False) for event in events]
    for _ in range(bad_event_lines):
        lines.append("{ broken-event")
    (run_dir / "events.ndjson").write_text("\n".join(lines) + "\n", encoding="utf-8")

    stats = [
        {"ts": "2026-09-07T08:01:12Z", "slide": 1, "backend": "zhipu", "page_type": "body", "attempts": 1, "tokens": 1200},
        {"ts": "2026-09-07T08:01:30Z", "slide": 2, "backend": "zhipu", "page_type": "body", "attempts": 1, "tokens": 1180},
        {"ts": "2026-09-07T08:02:31Z", "slide": 3, "backend": "zhipu", "page_type": "body", "attempts": 2, "tokens": "not-recorded"},
    ]
    (run_dir / "observability" / "backend_stats.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in stats) + "\n", encoding="utf-8"
    )

    (run_dir / "logs" / "run.log").write_text(
        "\n".join(
            [
                json.dumps({"command": "image prepare", "status": "completed", "reason_code": "ok", "duration_ms": 8000}),
                json.dumps({"command": "image record --slide 3", "status": "failed", "reason_code": "upstream_image_failed", "duration_ms": 31000}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    if final:
        (run_dir / "final" / "deck.pptx").write_bytes(b"PK-fixture-pptx")
        gates = {name: {"status": "passed"} for name in (
            "schema", "references", "visual", "overflow", "consistency", "delivery"
        )}
        (run_dir / "final" / "validation-summary.json").write_text(
            json.dumps({"quality_gates": gates}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return run_dir
