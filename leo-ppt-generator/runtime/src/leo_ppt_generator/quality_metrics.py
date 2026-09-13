"""质量事件的只读聚合；不从渲染方式推断纠错，不把缺失观测算作零。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext, ROUND_DOWN
from functools import lru_cache
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

from filelock import FileLock
from jsonschema import Draft202012Validator

from .storage import atomic_write_bytes, atomic_write_json


class MetricEventError(ValueError):
    reason_code = "quality_event_invalid"


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


@lru_cache(maxsize=1)
def _validator():
    schema = json.loads((Path(__file__).parent / "schemas" /
                         "quality-event-v1.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_event(event):
    errors = list(_validator().iter_errors(event))
    if errors:
        raise MetricEventError(errors[0].message)
    if event["kind"] == "call" and event["payload"]["amount"] is not None:
        amount = event["payload"]["amount"]
        try:
            parsed = Decimal(amount)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise MetricEventError("invalid charge amount") from exc
        if not parsed.is_finite() or parsed < 0:
            raise MetricEventError("charge amount must be finite and non-negative")
    return event


def _unique_events(events, run_id, window, targets):
    seen = {}
    identity_phases = {}
    for event in events:
        validate_event(event)
        if event["run_id"] != run_id or event["window"] != window:
            continue
        payload = event["payload"]
        identity_field = {"call": "call_id", "rework": "feedback_id"}.get(event["kind"])
        if identity_field:
            identity = (event["kind"], payload[identity_field])
            if identity in identity_phases and identity_phases[identity] != event["phase"]:
                raise MetricEventError("identity cannot move across authorization phases")
            identity_phases[identity] = event["phase"]
        pages = [payload["page"]] if event["kind"] == "tf" else payload["pages"]
        if not set(pages).issubset(targets):
            raise MetricEventError("event page is outside frozen target set")
        key = event["event_id"]
        if key in seen and _canonical(seen[key]) != _canonical(event):
            raise MetricEventError("conflicting event_id: " + key)
        seen[key] = event
    return [seen[key] for key in sorted(seen)]


def _tf(events, targets):
    triggered, complete = set(), set()
    event_count = 0
    for event in events:
        if event["kind"] != "tf":
            continue
        p = event["payload"]
        if p["triggers"]:
            triggered.add(p["page"])
            event_count += len(p["triggers"])
        if p["complete"]:
            complete.add(p["page"])
    k = len(triggered)
    n = len(complete - triggered)
    t = len(targets)
    u = t - k - n
    return {"caliber_version": "tf-caliber-v2", "K": k, "N": n, "U": u, "T": t,
            "event_count": event_count, "rate": k / (k + n) if k + n else None,
            "coverage": (k + n) / t if t else None,
            "target_interval": [k / t, (k + u) / t] if t else None,
            "status": "not_applicable" if not t else ("blocked" if u else "observed")}


def _cost(events):
    amounts = [Decimal(e["payload"]["amount"]) for e in events
               if e["kind"] == "call" and e["payload"]["amount"] is not None]
    # 同时保留最大整数位、最小小数位与累加进位，避免默认 28 位精度吞掉金额。
    integer_places = max([1] + [a.adjusted() + 1 for a in amounts])
    scale = max([0] + [-a.as_tuple().exponent for a in amounts])
    with localcontext() as ctx:
        ctx.prec = integer_places + scale + len(str(len(amounts) + 1)) + 24
        return _cost_in_context(events)


def _cost_in_context(events):
    calls = {}
    for event in events:
        if event["kind"] != "call":
            continue
        payload = event["payload"]
        key = payload["call_id"]
        if key in calls and _canonical(calls[key]) != _canonical(payload):
            raise MetricEventError("conflicting call_id: " + key)
        calls[key] = payload
    unknown, totals, buckets, per_page = [], {}, {}, {}
    for key, payload in sorted(calls.items()):
        if any(payload[field] is None for field in ("amount", "currency", "price_version")):
            unknown.append(key)
            continue
        amount = Decimal(payload["amount"])
        currency = payload["currency"]
        version = payload["price_version"]
        totals[currency] = totals.get(currency, Decimal(0)) + amount
        versions = buckets.setdefault(currency, {})
        versions[version] = versions.get(version, Decimal(0)) + amount
        pages = sorted(payload["pages"])
        page_totals = per_page.setdefault(currency, {})
        # 最后一页接收除法余数，保证页级之和严格等于实际调用金额。
        quantum = Decimal(1).scaleb(min(amount.as_tuple().exponent, -12))
        share = (amount / len(pages)).quantize(quantum, rounding=ROUND_DOWN)
        allocated = Decimal(0)
        for i, page in enumerate(pages):
            value = amount - allocated if i == len(pages) - 1 else share
            page_totals[page] = page_totals.get(page, Decimal(0)) + value
            allocated += value
    def encode(values):
        return {key: encode(value) if isinstance(value, dict) else format(value, "f")
                for key, value in sorted(values.items())}
    return {"caliber_version": "cost-caliber-v2", "calls": len(calls),
            "known_totals": encode(totals), "price_buckets": encode(buckets),
            "per_page": encode({currency: {page: amount.normalize() for page, amount in pages.items()}
                                for currency, pages in per_page.items()}), "unknown_calls": unknown,
            "known_call_coverage": (len(calls) - len(unknown)) / len(calls) if calls else None,
            "window_complete": False,
            "status": "blocked" if unknown or not calls else "partial",
            "limitation": "recorded calls do not prove complete billing-window coverage"}


def _rework(events):
    feedback = {}
    for event in events:
        if event["kind"] != "rework" or event["payload"]["actor"] != "user":
            continue
        p = event["payload"]
        key = (event["phase"], p["feedback_id"])
        group = feedback.setdefault(key, {"states": set(), "pages": set(), "reasons": set()})
        group["states"].add(p["state"])
        group["pages"].update(p["pages"])
        group["reasons"].add(p["reason"])
    if not feedback:
        return {"caliber_version": "rework-caliber-v1", "status": "not_yet_observed",
                "completed_rounds": None, "cycles": []}
    cycles = []
    for (phase, identity), group in sorted(feedback.items()):
        states = group["states"]
        if "cancelled" in states and "presented" in states:
            raise MetricEventError("conflicting final states for feedback_id: " + identity)
        state = ("presented" if "presented" in states else
                 "cancelled" if "cancelled" in states else
                 "revised" if "revised" in states else "received")
        cycle_complete = {"received", "revised", "presented"}.issubset(states)
        cycles.append({"feedback_id": identity, "phase": phase, "state": state,
                       "complete": cycle_complete,
                       "pages": sorted(group["pages"]), "reasons": sorted(group["reasons"])})
    return {"caliber_version": "rework-caliber-v1", "status": "partial",
            "completed_rounds": sum(c["complete"] for c in cycles),
            "cycles": cycles, "window_complete": False}


def aggregate_metrics(events, *, run_id, window, target_pages, phase="after-authorization"):
    """聚合一个调用者显式固定的 run/window；函数不写文件。"""
    if not isinstance(run_id, str) or not run_id or not isinstance(window, str) or not window:
        raise MetricEventError("run_id and window are required")
    phases = ("before-authorization", "after-authorization", "development")
    if phase not in phases:
        raise MetricEventError("invalid observation phase")
    pages = list(target_pages)
    if any(not isinstance(p, str) or not p for p in pages) or len(set(pages)) != len(pages):
        raise MetricEventError("target_pages must contain unique non-empty string identities")
    unique = _unique_events(events, run_id, window, set(pages))
    synthetic = [e["event_id"] for e in unique if e["source"] == "synthetic"]
    unique = [e for e in unique if e["source"] != "synthetic"]
    selected = [e for e in unique if e["phase"] == phase]
    return {"schema_version": 1, "run_id": run_id, "window": window, "phase": phase,
            "evidence_level": "recorded-events", "excluded_synthetic_events": synthetic,
            "target_pages": sorted(pages), "tf": _tf(selected, pages),
            "cost": _cost(selected), "rework": _rework(selected),
            "cost_by_phase": {p: _cost([e for e in unique if e["phase"] == p]) for p in phases}}


def deck_quality_for_run(run_path, report):
    """Derive the four evidence channels from the run's current artifacts.

    Presence of a file is only an input to the channel decision.  Binding
    digests must be present for every selected page and an export channel is
    blocked until a real PNG exists; no channel is upgraded from another one.
    """
    root = Path(run_path)
    evidence = []
    pack = root / "input" / "content-pack.json"
    if pack.is_file():
        evidence.append({"channel": "schema", "status": "passed", "path": str(pack)})
    else:
        evidence.append({"channel": "schema", "status": "not_run"})
    binding = root / "input" / "content-binding.json"
    selection = root / "input" / "layout-selection.json"
    if binding.is_file() or selection.is_file():
        source = binding if binding.is_file() else selection
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            rows = payload.get("pages") or payload.get("selection") or {}
            rows = rows.values() if isinstance(rows, dict) else rows
            status = ("passed" if isinstance(rows, list) and rows
                      and all(isinstance(row, dict)
                              and row.get("expression_binding_digest")
                              and row.get("materialization_binding_digest")
                              for row in rows) else "failed")
        except (OSError, ValueError, AttributeError):
            status = "error"
        evidence.append({"channel": "binding", "status": status, "path": str(source)})
    else:
        evidence.append({"channel": "binding", "status": "not_run"})
    facts_status = ("passed" if report.get("tf")
                    and report["tf"].get("status") in {"observed", "not_applicable"}
                    else "not_run")
    evidence.append({"channel": "facts", "status": facts_status})
    export_candidates = [root / "image-deck", root / "work" / "image-deck", root / "rendered"]
    exports = [path for path in export_candidates
               if path.is_dir() and any(path.rglob("*.png"))]
    evidence.append({"channel": "export", "status": "passed" if exports else "blocked",
                     "paths": [str(path) for path in exports]})
    states = {item["status"] for item in evidence}
    priority = ("error", "failed", "stale", "blocked", "not_run", "passed")
    overall = next(state for state in priority if state in states)
    return {"schema_version": 1, "overall_status": overall,
            "channels": {item["channel"]: item["status"] for item in evidence},
            "evidence": evidence}


def scorecard_for_run(run_path):
    """读取显式冻结窗口与加性事件，不从 manifest 猜测观测分母。"""
    root = Path(run_path)
    if not root.is_dir():
        raise MetricEventError("run directory does not exist")
    window_path = root / "observability" / "quality-window.json"
    if not window_path.exists():
        return {"schema_version": 1, "status": "blocked",
                "reason_code": "quality_window_not_recorded", "target_pages": None,
                "tf": None, "cost": None, "rework": None}
    window_bytes = window_path.read_bytes()
    config = json.loads(window_bytes)
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise MetricEventError("invalid quality window")
    if not isinstance(config.get("target_pages"), list):
        raise MetricEventError("quality window requires frozen target_pages")
    events_path = root / "observability" / "quality-events.jsonl"
    events = []
    event_bytes = events_path.read_bytes() if events_path.exists() else b""
    for line in event_bytes.decode("utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    closure_path = root / "observability" / "quality-closure.json"
    closed = closure_path.exists()
    if closed:
        closure = json.loads(closure_path.read_text(encoding="utf-8"))
        observed_seal = {"schema_version": 1, "window_sha256": hashlib.sha256(window_bytes).hexdigest(),
                         "events_sha256": hashlib.sha256(event_bytes).hexdigest()}
        if closure != observed_seal:
            raise MetricEventError("quality observation seal is stale")
    report = aggregate_metrics(events, run_id=config.get("run_id"),
                             window=config.get("window"), target_pages=config["target_pages"],
                             phase=config.get("phase", "after-authorization"))
    report["observation_closed"] = closed
    return report


@contextmanager
def _observation_write(run_path):
    root = Path(run_path).resolve()
    if not root.is_dir():
        raise MetricEventError("run directory does not exist")
    directory = root / "observability"
    if directory.is_symlink():
        raise MetricEventError("observation symlink forbidden")
    directory.mkdir(exist_ok=True)
    for name in ("quality.lock", "quality-window.json", "quality-events.jsonl", "quality-closure.json"):
        path = directory / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise MetricEventError("observation requires regular files")
    with FileLock(str(directory / "quality.lock"), timeout=10):
        yield root, directory


def _observation_seal(directory):
    def digest(name):
        path = directory / name
        return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()
    return {"schema_version": 1, "window_sha256": digest("quality-window.json"),
            "events_sha256": digest("quality-events.jsonl")}


def start_observation(run_path, *, window, target_pages, phase):
    """选页级 lane 前固定分母；重放不变更窗口，也不补造历史窗口。"""
    if not isinstance(target_pages, list):
        raise MetricEventError("target_pages must be a JSON array")
    with _observation_write(run_path) as (root, directory):
        run = json.loads((root / "run.json").read_text(encoding="utf-8"))
        run_id = run.get("run_id")
        aggregate_metrics([], run_id=run_id, window=window, target_pages=target_pages, phase=phase)
        config = {"schema_version": 1, "run_id": run_id, "window": window,
                  "phase": phase, "target_pages": sorted(target_pages)}
        path = directory / "quality-window.json"
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != config:
                raise MetricEventError("quality window is immutable; create a new run")
            return config
        prepared = [root / "image-deck/slide_jobs.json", root / "work/image-deck/slide_jobs.json",
                    root / "input/content-binding.json", root / "input/layout-selection.json"]
        if any(p.exists() for p in prepared) or (directory / "quality-events.jsonl").exists():
            raise MetricEventError("quality window must start before lane preparation")
        atomic_write_json(path, config)
        return config


def record_quality_event(run_path, event):
    """加性事件按稳定身份幂等写入；在锁内验证整批后原子替换。"""
    validate_event(event)
    with _observation_write(run_path) as (root, directory):
        path = directory / "quality-window.json"
        if not path.is_file():
            raise MetricEventError("quality window not started")
        config = json.loads(path.read_text(encoding="utf-8"))
        if any(event[key] != config[key] for key in ("run_id", "window")):
            raise MetricEventError("event does not belong to frozen window")
        stream = directory / "quality-events.jsonl"
        rows = [json.loads(line) for line in stream.read_text(encoding="utf-8").splitlines()
                if line.strip()] if stream.exists() else []
        aggregate_metrics([*rows, event], run_id=config["run_id"], window=config["window"],
                          target_pages=config["target_pages"], phase=config["phase"])
        scorecard_for_run(root)
        if any(row["event_id"] == event["event_id"] for row in rows):
            return {"event_id": event["event_id"], "idempotency_status": "replayed"}
        if (directory / "quality-closure.json").exists():
            raise MetricEventError("quality observation is closed")
        if event["kind"] == "rework" and event["payload"]["actor"] == "user":
            previous = {row["payload"]["state"] for row in rows
                        if row["kind"] == "rework" and row["payload"]["actor"] == "user"
                        and row["payload"]["feedback_id"] == event["payload"]["feedback_id"]}
            state = event["payload"]["state"]
            required = {"received": set(), "revised": {"received"},
                        "presented": {"received", "revised"}, "cancelled": {"received"}}[state]
            if not required.issubset(previous) or previous.intersection({"presented", "cancelled"}):
                raise MetricEventError("user feedback lifecycle transition invalid")
        rows.append(event)
        atomic_write_bytes(stream, ("\n".join(_canonical(row) for row in rows) + "\n").encode("utf-8"))
        return {"event_id": event["event_id"], "idempotency_status": "created"}


def record_runtime_tf(run_path, *, page, operation_id, triggers, generation_method, complete=False):
    """只消费调用者显式声明的降级，不从 --rework 或生成方式推断 TF。"""
    window = Path(run_path) / "observability/quality-window.json"
    if not window.is_file():
        raise MetricEventError("quality window not started")
    config = json.loads(window.read_text(encoding="utf-8"))
    return record_quality_event(run_path, {
        "schema_version": 1, "event_id": "tf:" + operation_id,
        "run_id": config["run_id"], "window": config["window"], "phase": config["phase"],
        "kind": "tf", "source": "runtime", "payload": {"page": str(page),
        "triggers": sorted(set(triggers)), "complete": complete, "generation_method": generation_method}})


def close_observation(run_path):
    """固定事件流字节；关闭本身不证明账单完整，也不把未观察页归为 N。"""
    with _observation_write(run_path) as (root, directory):
        if not (directory / "quality-window.json").is_file():
            raise MetricEventError("quality window not started")
        scorecard_for_run(root)
        seal = _observation_seal(directory)
        path = directory / "quality-closure.json"
        if not path.exists():
            atomic_write_json(path, seal)
        return seal


def dispatch_discipline_warnings(run_path):
    """R-81 残留④：聚合 WS6 观察哨的调度纪律告警（只读，不写事件流）。

    ``reports/run-ledger.jsonl`` 的 ``dispatch_discipline_warning`` 行按
    agent 聚合计数；无账本返回空表。告警是观察面，不进入 TF/K 口径。
    """

    ledger = Path(run_path) / "reports" / "run-ledger.jsonl"
    by_agent: dict[str, dict] = {}
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("step") != "dispatch_discipline_warning":
                continue
            agent = str(entry.get("agent_id") or "unknown")
            row = by_agent.setdefault(agent, {"warnings": 0, "max_recorded_by_agent": 0})
            row["warnings"] += 1
            recorded = entry.get("recorded_by_agent")
            if isinstance(recorded, int):
                row["max_recorded_by_agent"] = max(row["max_recorded_by_agent"], recorded)
    return {"schema_version": 1, "kind": "dispatch-discipline-warnings", "agents": by_agent}
