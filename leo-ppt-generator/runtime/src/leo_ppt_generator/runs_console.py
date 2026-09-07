"""生成任务（run）只读控制台数据层。

只读 ``${LEO_PPT_HOME}/projects/*/runs/*/`` 下落盘事实并聚合为控制台视图：
任务列表、详情（流程步骤/页网格/事件时间线/链路聚合/交付卡）与页图沙箱。
设计约束（docs/plans/2026-09-07-004）：

- 纯标准库、纯读：不写任何文件、不 import config 域与 run_index（写侧）；
- home 由 web.py 解析后注入（读侧不复制平台逻辑）；
- 任何解析失败按"缺数据"降级（None/跳过/计数），绝不把坏数据放大成 5xx；
- 页图沙箱：客户端只提供 run_id + 页码，真实路径取自 slide_jobs entry 的
  ``artifact`` 字段，``resolve()`` 后必须仍在该 run 目录内且后缀在白名单。
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

_RUN_ID_RE = re.compile(r"^[0-9a-f]{8,64}$")
_PREVIEW_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_EVENTS_WINDOW = 200
_EVENTS_MAX_LIMIT = 500
# image 路线页级失败没有事件，落点在 timing.pages / run.log（方案 R2 核验）。
_FAILURE_STATUSES = {"failed", "timeout", "blocked"}
# 路线步骤序列的唯一读侧副本（架构评审#4：与写侧 application/routes.ROUTES
# 的 steps 逐路线对齐，由 tests/test_runs_console.py 锁定防漂移）。
ROUTE_STEP_SEQUENCES = {
    "generate": ["image.prepare", "image.dispatch", "image.finalize"],
    "direct-editable": [
        "editable.prepare",
        "editable.dispatch",
        "editable.finalize",
    ],
    "upgrade-full": [
        "image.inspect",
        "editable.prepare",
        "editable.dispatch",
        "editable.finalize",
    ],
    "upgrade-selected": [
        "image.inspect",
        "editable.prepare-selected",
        "editable.dispatch",
        "hybrid.assemble",
    ],
}

# 阶段 key → timing stages[].stage 值（=CLI 命令名）的归属子串（近似口径）。
_STAGE_COMMAND_HINTS = {
    "prepare": ("prepare",),
    "dispatch": ("record", "dispatch", "sweep"),
    "finalize": ("finalize", "assemble"),
    "inspect": ("inspect",),
    "assemble": ("assemble",),
}


class RunLookupError(KeyError):
    """run 不存在或不可读；reason_code 固定 run_not_found。"""

    reason_code = "run_not_found"


class PreviewLookupError(KeyError):
    """页图不可得（不存在/沙箱拒绝）；reason_code 固定 preview_not_found。"""

    reason_code = "preview_not_found"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _mtime_or_none(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _events_tail(
    path: Path,
    *,
    before_seq: int | None = None,
    limit: int = _EVENTS_WINDOW,
) -> dict[str, Any]:
    """逐行解析 events.ndjson：坏行跳过计数，默认返回尾部窗口。"""

    rows: list[dict[str, Any]] = []
    bad_lines = 0
    total = 0
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"events": [], "bad_lines": 0, "total_lines": 0}
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        total += 1
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            bad_lines += 1
            continue
        if not isinstance(event, dict):
            bad_lines += 1
            continue
        if before_seq is not None:
            seq = event.get("seq")
            if isinstance(seq, int) and seq >= before_seq:
                continue
        rows.append(event)
    if before_seq is None:
        window = rows[-limit:]
    else:
        # 紧邻 before_seq 之前的 N 条（此前误取全文件最旧 N 条导致跳段）。
        window = rows[-limit:]
    return {"events": window, "bad_lines": bad_lines, "total_lines": total}


def _stage_label(stage_key: str) -> str:
    domain, _, step = stage_key.partition(".")
    labels = {
        "prepare": "准备",
        "prepare-selected": "准备（选定页）",
        "dispatch": "逐页生成",
        "finalize": "交付",
        "inspect": "检查",
        "assemble": "组装",
    }
    return labels.get(step, step or domain or stage_key)


class RunScanner:
    """扫描并聚合本机 run 目录（只读，带短 TTL 缓存）。

    缓存动机（运维评审#1/架构#2）：ThreadingHTTPServer 下列表/详情/每张页图
    共享同一 scanner 实例，无缓存时一轮 3s 轮询触发 ~13 次全量目录扫描。
    索引缓存 TTL 默认 1.5s（< 3s 轮询周期，新 run 最迟下一轮可见）；
    jobs 文档按 (path, mtime, size) 失效。clock/monotonic 可注入供测试。
    """

    def __init__(
        self,
        home: Path,
        *,
        clock: Any = time.time,
        monotonic: Any = time.monotonic,
        index_ttl: float = 1.5,
    ) -> None:
        self._home = Path(home)
        self._clock = clock
        self._monotonic = monotonic
        self._index_ttl = index_ttl
        self._lock = threading.Lock()
        self._index_cache: dict[str, dict[str, Any]] | None = None
        self._index_cached_at: float = float("-inf")
        self._jobs_cache: dict[tuple[str, int, int], dict[str, Any] | None] = {}

    # ------------------------------------------------------------- 发现
    def invalidate_cache(self) -> None:
        """测试与显式刷新钩子：清空索引与 jobs 缓存。"""
        with self._lock:
            self._index_cache = None
            self._index_cached_at = float("-inf")
            self._jobs_cache.clear()

    def _run_index(self) -> dict[str, dict[str, Any]]:
        """run_id -> {project, dir, run_json, mtime}；坏 run.json 跳过。

        扫描持锁执行（运维复评：避免 TTL 过期瞬间 detail+缩略图惊群
        各自全量扫描；命中路径零开销）。
        """
        with self._lock:
            now = self._monotonic()
            if (
                self._index_cache is not None
                and now - self._index_cached_at < self._index_ttl
            ):
                return self._index_cache
            index = self._scan_all_locked()
            self._index_cache = index
            self._index_cached_at = self._monotonic()
            return index

    def _scan_all_locked(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        projects_dir = self._home / "projects"
        try:
            project_dirs = sorted(p for p in projects_dir.iterdir() if p.is_dir())
        except OSError:
            return index
        for project_dir in project_dirs:
            runs_dir = project_dir / "runs"
            try:
                run_dirs = sorted(p for p in runs_dir.iterdir() if p.is_dir())
            except OSError:
                continue
            for run_dir in run_dirs:
                run_json_path = run_dir / "run.json"
                document = _read_json(run_json_path)
                if document is None:
                    continue
                run_id = document.get("run_id")
                if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id):
                    continue
                mtime = _mtime_or_none(run_json_path)
                if mtime is None:
                    continue
                # 陈旧检测取 run.json 与 events.ndjson 的较新者（PRD FR3）：
                # dispatch 期间 events 持续追加而 run.json 可能长时间不动。
                events_mtime = _mtime_or_none(run_dir / "events.ndjson")
                if events_mtime is not None:
                    mtime = max(mtime, events_mtime)
                index[run_id] = {
                    "project": project_dir.name,
                    "dir": run_dir,
                    "run_json": document,
                    "mtime": mtime,
                }
        return index

    def home_missing(self) -> bool:
        return not (self._home / "projects").is_dir()

    @staticmethod
    def _primary_domain(route: str) -> str:
        return "image" if route == "generate" else "editable"

    def _progress_of(self, document: dict[str, Any]) -> dict[str, Any] | None:
        domains = document.get("domains")
        if not isinstance(domains, dict):
            return None
        domain = domains.get(self._primary_domain(str(document.get("route", ""))))
        if not isinstance(domain, dict):
            return None
        progress = domain.get("progress")
        if not isinstance(progress, dict):
            return None  # 刚创建未 reconcile：仅 {path}
        return {
            key: progress.get(key)
            for key in ("total_units", "completed", "failed", "active", "pending")
        }

    def _list_entry(self, run_id: str, info: dict[str, Any]) -> dict[str, Any]:
        document = info["run_json"]
        stale_minutes = None
        if document.get("status") not in {"completed", "failed", "cancelled"}:
            stale_minutes = round(max(0.0, self._clock() - info["mtime"]) / 60.0, 1)
        return {
            "run_id": run_id,
            "short_id": run_id[:4],
            "project": info["project"],
            "route": document.get("route"),
            "status": document.get("status"),
            "stage": document.get("stage"),
            "stage_label": _stage_label(str(document.get("stage", ""))),
            "progress": self._progress_of(document),
            "updated_at": info["mtime"],
            "stale_minutes": stale_minutes,
        }

    def list_runs(self) -> dict[str, Any]:
        index = self._run_index()
        runs = [self._list_entry(run_id, info) for run_id, info in index.items()]
        runs.sort(key=lambda item: item["updated_at"], reverse=True)
        return {"runs": runs, "home_missing": self.home_missing()}

    # ------------------------------------------------------------- 详情
    def _find(self, run_id: str) -> dict[str, Any]:
        if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id):
            raise RunLookupError(run_id)
        info = self._run_index().get(run_id)
        if info is None:
            raise RunLookupError(run_id)
        return info

    def _steps_of(
        self,
        route: str,
        current_stage: str,
        timing: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        sequences = ROUTE_STEP_SEQUENCES
        stages = timing.get("stages") if isinstance(timing, dict) else None
        stages = stages if isinstance(stages, list) else []

        def stage_duration(key: str) -> float | None:
            # 生产 writer（observability.py）落 stage/duration_seconds；
            # 兼容旧合成 fixture 的 command/duration（产品评审#2 修复）。
            step = key.partition(".")[2]
            hints = _STAGE_COMMAND_HINTS.get(step.replace("-selected", ""), ())
            total = 0.0
            matched = False
            for entry in stages:
                if not isinstance(entry, dict):
                    continue
                command = str(entry.get("stage") or entry.get("command") or "")
                duration = entry.get("duration_seconds", entry.get("duration"))
                if any(hint in command for hint in hints):
                    matched = True
                    if isinstance(duration, (int, float)):
                        total += float(duration)
            return round(total, 1) if matched else None

        keys = sequences.get(route, sequences["generate"])
        try:
            position = keys.index(current_stage) if current_stage in keys else -1
        except ValueError:
            position = -1
        steps = []
        for index, key in enumerate(keys):
            if position >= 0:
                state = "done" if index < position else ("current" if index == position else "pending")
            else:
                state = "unknown"
            steps.append(
                {
                    "key": key,
                    "label": _stage_label(key),
                    "state": state,
                    "duration_seconds": stage_duration(key),
                }
            )
        return steps

    def _jobs_document(
        self, run_dir: Path, route: str
    ) -> tuple[dict[str, Any] | None, str]:
        """route → (jobs 文档, 条目键名)；按 (path, mtime, size) 缓存。"""
        relative = (
            ("image-deck", "slide_jobs.json", "slides")
            if route == "generate"
            else ("editable", "page_jobs.json", "pages")
        )
        path = run_dir.joinpath(*relative[:2])
        try:
            stat = path.stat()
            key = (str(path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return None, relative[2]
        with self._lock:
            if key in self._jobs_cache:
                return self._jobs_cache[key], relative[2]
        document = _read_json(path)
        with self._lock:
            # 运维复评：每 path 只保留最新版本，防 dispatch 期间高频重写
            # 导致的缓存无上界增长。
            for stale_key in [
                candidate for candidate in self._jobs_cache if candidate[0] == str(path)
            ]:
                del self._jobs_cache[stale_key]
            self._jobs_cache[key] = document
        return document, relative[2]

    def _pages_of(self, info: dict[str, Any], timing: dict[str, Any] | None) -> list[dict[str, Any]]:
        run_dir: Path = info["dir"]
        document = info["run_json"]
        route = str(document.get("route", ""))
        jobs, jobs_kind = self._jobs_document(run_dir, route)
        timing_pages: dict[str, dict[str, Any]] = {}
        if isinstance(timing, dict) and isinstance(timing.get("pages"), list):
            for entry in timing["pages"]:
                if isinstance(entry, dict) and isinstance(entry.get("unit_id"), str):
                    timing_pages[entry["unit_id"]] = entry
        # 第二失败源（方案数据契约）：logs/run.log 的 failed/blocked 行，
        # command 尾部 --slide N / --page N 提取单元（timing 缺失时兜底）。
        try:
            log_lines = (run_dir / "logs" / "run.log").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError:
            log_lines = []
        for line in log_lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict) or str(entry.get("status")) not in _FAILURE_STATUSES:
                continue
            command = str(entry.get("command") or "")
            marker = "slide " if "slide" in command else ("page " if "page" in command else "")
            if not marker:
                continue
            tail = command.split(marker)[-1].strip().split()[0]
            try:
                number = int(tail)
            except ValueError:
                continue
            unit_id = (
                f"slide_{number:02d}" if marker == "slide " else f"page_{number:03d}"
            )
            timing_pages.setdefault(
                unit_id, {"unit_id": unit_id, "status": entry.get("status"), "reason_code": entry.get("reason_code")}
            )
        pages: list[dict[str, Any]] = []
        if isinstance(jobs, dict) and isinstance(jobs.get(jobs_kind), list):
            for entry in jobs[jobs_kind]:
                if not isinstance(entry, dict):
                    continue
                number = entry.get("number") if isinstance(entry.get("number"), int) else None
                unit_id = entry.get("slide_id") or entry.get("page_id")
                status = entry.get("status")
                failure = timing_pages.get(str(unit_id) if unit_id else "")
                state = "recorded" if status == "recorded" else (
                    "active" if status == "active" else "pending"
                )
                if failure and str(failure.get("status")) in _FAILURE_STATUSES:
                    state = "timeout" if failure.get("status") == "timeout" else "failed"
                pages.append(
                    {
                        "number": number,
                        "unit_id": unit_id,
                        "state": state,
                        "artifact": entry.get("artifact"),
                        "backend": entry.get("backend"),
                        "agent_id": entry.get("agent_id"),
                        "failure_reason": failure.get("reason_code") if failure else None,
                    }
                )
            pages.sort(key=lambda item: (item["number"] is None, item["number"] if isinstance(item["number"], int) else 0))
            return pages
        # jobs 缺失/坏：按 page_order 或 1..total 生成 unknown 占位（PRD FR10）。
        progress = self._progress_of(document) or {}
        total = progress.get("total_units")
        order = document.get("page_order")
        numbers = order if isinstance(order, list) and order else list(range(1, (total or 0) + 1))
        for number in numbers[: max(0, int(total or len(numbers)))]:
            pages.append(
                {
                    "number": number,
                    "unit_id": None,
                    "state": "unknown",
                    "artifact": None,
                    "backend": None,
                    "agent_id": None,
                    "failure_reason": None,
                }
            )
        return pages

    def _delivery_of(self, info: dict[str, Any]) -> dict[str, Any]:
        run_dir: Path = info["dir"]
        document = info["run_json"]
        route = str(document.get("route", ""))
        delivery: dict[str, Any] = {"deck_path": None, "gates": None, "failure_summary": None, "manifests": []}
        deck = run_dir / "final" / "deck.pptx"
        if deck.is_file():
            delivery["deck_path"] = str(deck)
        summary = _read_json(run_dir / "final" / "validation-summary.json")
        if isinstance(summary, dict) and isinstance(summary.get("quality_gates"), dict):
            delivery["gates"] = [
                {"name": name, "status": value.get("status") if isinstance(value, dict) else value}
                for name, value in summary["quality_gates"].items()
            ]
        failure_report = _read_json(run_dir / "final" / "failure-report.json")
        if isinstance(failure_report, dict):
            failures = failure_report.get("failures")
            delivery["failure_summary"] = {
                "failures": len(failures) if isinstance(failures, list) else None,
                "recovery_action": failure_report.get("recovery_action"),
            }
        if route == "upgrade-selected":
            try:
                manifests = sorted((run_dir / "final").glob("*.delivery.json"))
            except OSError:
                manifests = []
            delivery["manifests"] = [str(item) for item in manifests]
        if delivery["gates"] is None and document.get("status") == "failed":
            delivery["failure_summary"] = delivery["failure_summary"] or {
                "failures": None,
                "recovery_action": None,
                "failed_stage": document.get("stage"),
            }
        return delivery

    def _backend_stats_of(self, info: dict[str, Any]) -> dict[str, Any]:
        run_dir: Path = info["dir"]
        stats: dict[str, dict[str, Any]] = {}
        try:
            lines = (run_dir / "observability" / "backend_stats.jsonl").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError:
            return {"providers": {}, "tokens_recorded": True}
        tokens_recorded = True
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            provider = entry.get("backend")
            if not isinstance(provider, str):
                continue
            bucket = stats.setdefault(provider, {"calls": 0, "attempts": 0, "tokens": 0})
            bucket["calls"] += 1
            attempts = entry.get("attempts")
            if isinstance(attempts, int):
                bucket["attempts"] += attempts
            tokens = entry.get("tokens")
            if isinstance(tokens, int):
                bucket["tokens"] += tokens
            elif not isinstance(tokens, int):
                tokens_recorded = False
        return {"providers": stats, "tokens_recorded": tokens_recorded}

    def run_detail(
        self,
        run_id: str,
        *,
        events_before: int | None = None,
        events_limit: int | None = None,
    ) -> dict[str, Any]:
        info = self._find(run_id)
        run_dir: Path = info["dir"]
        document = info["run_json"]
        limit = min(max(1, events_limit or _EVENTS_WINDOW), _EVENTS_MAX_LIMIT)
        timing = _read_json(run_dir / "reports" / "timing.json")
        events = _events_tail(
            run_dir / "events.ndjson",
            before_seq=events_before,
            limit=limit,
        )
        summary = timing.get("summary") if isinstance(timing, dict) else None
        entry = self._list_entry(run_id, info)
        entry.update(
            {
                "created_at": document.get("created_at"),
                "input_original_path": (document.get("input") or {}).get("original_path")
                if isinstance(document.get("input"), dict)
                else None,
                "steps": self._steps_of(str(document.get("route", "")), str(document.get("stage", "")), timing),
                "pages": self._pages_of(info, timing),
                "events_window": events,
                "delivery": self._delivery_of(info),
                "backend_stats": self._backend_stats_of(info),
                "duration_seconds": summary.get("total_duration_seconds")
                if isinstance(summary, dict)
                else None,
            }
        )
        return entry

    # ------------------------------------------------------------- 页图沙箱
    def page_image(self, run_id: str, number: int) -> tuple[bytes, str]:
        info = self._find(run_id)
        run_dir: Path = info["dir"]
        document = info["run_json"]
        route = str(document.get("route", ""))
        jobs, _jobs_kind = self._jobs_document(run_dir, route)
        if not isinstance(jobs, dict) or not isinstance(jobs.get("slides"), list):
            raise PreviewLookupError(run_id)
        artifact = None
        for entry in jobs["slides"]:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("number"), int)
                and entry.get("number") == number
            ):
                artifact = entry.get("artifact")
                break
        if not isinstance(artifact, str) or not artifact:
            raise PreviewLookupError(number)
        # artifact 相对 image-deck 域根（写侧 adapter.py 契约）。
        domain_root = run_dir / "image-deck"
        candidate = domain_root / artifact
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            raise PreviewLookupError(number)
        inside = resolved.is_relative_to(domain_root.resolve())
        if not inside:
            raise PreviewLookupError(number)
        content_type = _PREVIEW_TYPES.get(resolved.suffix.lower())
        if content_type is None:
            raise PreviewLookupError(number)
        try:
            return resolved.read_bytes(), content_type
        except OSError:
            raise PreviewLookupError(number)
