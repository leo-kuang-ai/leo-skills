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


EVIDENCE_STATES = ("error", "failed", "stale", "blocked", "not_run", "passed")


def _evidence_status(states):
    return next((state for state in EVIDENCE_STATES if state in states), "not_run")


def _run_relative(root, path):
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise MetricEventError("evidence_outside_run") from exc
    if ".." in candidate.parts:
        raise MetricEventError("evidence_outside_run")
    return candidate.as_posix()


def _export_evidence(root, payload, generation):
    from .qualification import read_evidence_bytes
    from .content_projection import verify_binding_reference
    from PIL import Image
    import io
    lanes = {"render:html": {"status": "not_run", "pages": {}}, "image": {"status": "not_run", "pages": {}}}
    try:
        manifest = json.loads(read_evidence_bytes(root, "pipeline-result.json"))
    except (ValueError, OSError):
        for lane in payload["bindings"]:
            lanes[lane].update(status="blocked", blocker="export_manifest_missing")
        return lanes
    if (manifest.get("input_generation") != generation
            or manifest.get("input_digest") != payload["request"]["input_digest"]):
        for lane in payload["bindings"]:
            lanes[lane].update(status="stale", blocker="export_generation_stale")
        return lanes
    artifact_owners = set()
    for lane, bindings in payload["bindings"].items():
        rows = lanes[lane]["pages"]
        declared = manifest.get("receipt_refs", {}).get(lane, {})
        if set(declared) != set(bindings):
            lanes[lane].update(status="failed", blocker="export_page_set_mismatch")
            continue
        for pid, binding in bindings.items():
            claim = declared[pid]
            if claim.get("status") != "passed":
                state = claim.get("status") if claim.get("status") in EVIDENCE_STATES else "error"
                rows[pid] = {"status": state, "blocker": claim.get("reason_code", "export_not_completed")}
                continue
            try:
                artifact_path = _run_relative(root, claim["artifact"])
                receipt_path = _run_relative(root, claim["receipt"])
                if artifact_path in artifact_owners:
                    raise MetricEventError("export_artifact_reused")
                artifact_owners.add(artifact_path)
                raw = read_evidence_bytes(root, artifact_path)
                receipt_bytes = read_evidence_bytes(root, receipt_path)
                receipt = json.loads(receipt_bytes)
                verify_binding_reference(receipt, binding)
                if receipt.get("out_sha256") != hashlib.sha256(raw).hexdigest():
                    raise MetricEventError("export_artifact_stale")
                with Image.open(io.BytesIO(raw)) as picture:
                    dimensions = picture.size
                    if picture.format != "PNG" or dimensions != (2560, 1440):
                        raise MetricEventError("export_dimensions_invalid")
                    picture.verify()
                if (receipt.get("width"), receipt.get("height")) != dimensions:
                    raise MetricEventError("export_receipt_dimensions_mismatch")
                if lane == "render:html":
                    if (receipt.get("kind") != "render_provenance" or receipt.get("backend") != lane
                            or receipt.get("template_id") != binding["template_id"]
                            or receipt.get("overflow_check") != "pass" or not receipt.get("renderer")):
                        raise MetricEventError("html_export_receipt_invalid")
                    template_hashes = {sha for pin in binding["effective"]["assets"] if pin["asset_id"] == binding["template_id"]
                                       for path, sha in pin["files"].items() if path.endswith("/page.html")}
                    data = read_evidence_bytes(root, (Path(artifact_path).parent / "data.json").as_posix())
                    if (receipt.get("template_sha256") not in template_hashes
                            or receipt.get("data_sha256") != hashlib.sha256(data).hexdigest()
                            or receipt.get("content_digest") != payload["pack"]["content_digest"]):
                        raise MetricEventError("html_export_input_or_template_stale")
                else:
                    from .image_deck.expression_adapter import verify_provider_export
                    verify_provider_export(receipt, root=(root / receipt_path).parent, binding=binding)
                    if (receipt.get("kind") != "provider-export-receipt" or receipt.get("status") != "succeeded"
                            or receipt.get("lane") != "image" or not receipt.get("provider")
                            or receipt.get("evidence_source") != "provider-http"
                            or not receipt.get("request_id") or receipt.get("page_id") != pid
                            or receipt.get("run_id") != payload["request"]["run_id"]
                            or receipt.get("input_generation") != generation):
                        raise MetricEventError("provider_export_receipt_missing_or_invalid")
                rows[pid] = {"status": "passed", "artifact": artifact_path, "receipt": receipt_path,
                    "artifact_sha256": hashlib.sha256(raw).hexdigest(), "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest()}
            except (OSError, ValueError, KeyError, TypeError) as exc:
                state = "stale" if "stale" in str(exc) or "digest_mismatch" in str(exc) else "failed"
                rows[pid] = {"status": state, "blocker": str(exc)}
        lanes[lane]["status"] = _evidence_status([row["status"] for row in rows.values()])
    return lanes


def _visual_evidence(root, generation, exports):
    from .qualification import read_evidence_bytes, digest, verify_reference
    from .quality_replay import evaluate_quality_replay
    try:
        receipt = json.loads(read_evidence_bytes(root, "qa/visual-replay.json"))
    except (ValueError, OSError) as exc:
        if isinstance(exc, FileNotFoundError) or isinstance(exc.__cause__, FileNotFoundError):
            return {"status": "not_run", "blocker": "visual_replay_receipt_missing"}
        return {"status": "error", "blocker": "visual_replay_receipt_invalid"}
    evidence_root, run_relative = root, ""
    if receipt.get("kind") == "quality-replay-attachment":
        from .quality_replay import _safe_directory
        try:
            evidence_root = Path(receipt["evidence_root"]).absolute()
            if (not evidence_root.is_absolute() or _safe_directory(evidence_root, receipt["run"]) != root
                    or any(path.is_symlink() for path in (evidence_root, *evidence_root.parents))):
                raise ValueError("visual_attachment_root_mismatch")
            run_relative = receipt["run"]
            receipt = json.loads(verify_reference(evidence_root, receipt["receipt"]))
        except (ValueError, OSError, KeyError, TypeError):
            return {"status": "stale", "blocker": "visual_attachment_invalid"}
    if receipt.get("kind") != "quality-replay-receipt" or not receipt.get("plan"):
        return {"status": "error", "blocker": "visual_receipt_schema_mismatch"}
    if receipt.get("receipt_digest") != digest({key: value for key, value in receipt.items() if key != "receipt_digest"}):
        return {"status": "stale", "blocker": "visual_receipt_digest_mismatch"}
    current = evaluate_quality_replay(evidence_root, receipt["plan"])
    if current["status"] != "passed":
        return {"status": current["status"], "blocker": ";".join(current["gaps"])}
    if current != receipt:
        return {"status": "stale", "blocker": "visual_replay_inputs_changed"}
    actual = {(run_relative + "/" if run_relative else "") + row["artifact"]: row["artifact_sha256"] for lane in exports.values()
              for row in lane["pages"].values() if row["status"] == "passed"}
    reviewed = {row["artifact"]["path"]: row["artifact"]["sha256"] for row in current["cases"]
                if row.get("input_generation") == generation and row["status"] == "passed" and row.get("run", "") == run_relative}
    if not actual or not reviewed or any(actual.get(path) != sha for path, sha in reviewed.items()):
        return {"status": "stale", "blocker": "visual_artifact_set_stale"}
    return {"status": "passed", "phase": current["phase"], "receipt": "qa/visual-replay.json",
            "coverage": "all-exported-pages" if actual == reviewed else "representative-pages",
            "reviewed_pages": len(reviewed), "exported_pages": len(actual),
            "user_benefit": current.get("user_benefit", {"status": "not_run", "blocker": "user_outcome_data_missing"}),
            "user_replay": current.get("user_replay", {"status": "not_run", "blocker": "user_defect_replay_required"})}


def deck_quality_for_run(run_path, report=None, *, include_visual=True):
    """当前输入、事实投影、双层绑定与真实导出四通道；观测事件不授予质量。"""
    from .application.expression_pipeline import load_committed_input, ExpressionPipelineError
    from .asset_resolver import AssetResolver
    from .content_projection import verify_effective_binding, materialize_html, materialize_image_prompt, binding_impact
    from .template_inputs import display_texts, validate_template_data
    root = Path(run_path).resolve()
    channels = dict.fromkeys(("schema", "facts", "binding", "export"), "not_run")
    evidence = []
    lanes = {lane: {"status": "not_run", "pages": {}} for lane in ("render:html", "image")}
    visual = {"status": "not_run", "blocker": "visual_replay_receipt_missing"}
    try:
        committed = load_committed_input(root)
    except (ValueError, OSError) as exc:
        reason = str(exc)
        channels["schema"] = "not_run" if reason == "input_pointer_missing" else "stale"
        channels["export"] = "blocked"
        evidence.append({"channel": "schema", "status": channels["schema"], "blocker": reason})
    else:
        payload = committed["payload"]
        channels["schema"] = "passed"
        evidence.append({"channel": "schema", "status": "passed", "generation": committed["generation"]})
        try:
            resolver = AssetResolver.from_snapshot(committed["root"] / "asset-snapshot")
            fact_errors, binding_errors, capacity_errors = [], [], []
            for lane, bindings in payload["bindings"].items():
                for pid, binding in bindings.items():
                    page = next(p for p in payload["pack"]["pages"] if p["page_id"] == pid)
                    verify_effective_binding(binding, page, resolver=resolver, frozen_design=payload["designs"][lane])
                    if lane == "render:html":
                        projected = materialize_html(binding, page, resolver=resolver)
                        capacity_errors.extend(validate_template_data(resolver.resolve(binding["template_id"])["data"], projected))
                        texts = display_texts(projected)
                    else:
                        projected = materialize_image_prompt(binding, page, payload["designs"][lane], resolver=resolver)
                        texts = projected["required_text"]
                    displayed = "\n".join(texts)
                    for required in page["required_text"]:
                        if required not in displayed:
                            fact_errors.append({"page_id": pid, "lane": lane, "reason": "required_text_not_projected", "text": required})
                    for number in payload["pack"]["numbers"]:
                        if pid in number["page_ids"] and (number["value"] not in displayed or number.get("unit") and number["unit"] not in displayed):
                            fact_errors.append({"page_id": pid, "lane": lane, "reason": "number_or_unit_not_projected", "fact_ref": number["item_id"]})
            channels["facts"] = "failed" if fact_errors else "passed"
            channels["schema"] = "failed" if capacity_errors else "passed"
            if payload.get("impact") != binding_impact(payload.get("previous_bindings", {}), payload["bindings"]):
                binding_errors.append("impact_receipt_missing_or_stale")
            channels["binding"] = "stale" if binding_errors else "passed"
            evidence.extend([{"channel": "facts", "status": channels["facts"], "gaps": fact_errors},
                             {"channel": "schema", "status": channels["schema"], "capacity_errors": capacity_errors},
                             {"channel": "binding", "status": channels["binding"], "gaps": binding_errors}])
        except (ValueError, OSError, KeyError, TypeError) as exc:
            channels["binding"] = "stale" if "changed" in str(exc) or "mismatch" in str(exc) else "error"
            evidence.append({"channel": "binding", "status": channels["binding"], "blocker": str(exc)})
        lanes = _export_evidence(root, payload, committed["generation"])
        channels["export"] = _evidence_status([lanes[lane]["status"] for lane in payload["bindings"]])
        if include_visual:
            visual = _visual_evidence(root, committed["generation"], lanes)
    states = set(channels.values())
    if visual["status"] in {"failed", "stale", "error"}:
        states.add(visual["status"])
    overall = _evidence_status(states)
    if overall == "passed":
        overall = ("visual_validated" if visual["status"] == "passed" and visual.get("phase") == "U6-B" and visual.get("coverage") == "all-exported-pages" else
                   "image_validated" if lanes["image"]["status"] == "passed" else
                   "html_validated" if lanes["render:html"]["status"] == "passed" else "implementation_complete")
    return {"schema_version": 1, "overall_status": overall, "channels": channels, "evidence": evidence,
            "lanes": lanes, "visual": visual,
            "user_replay": visual.get("user_replay", {"status": "not_run", "blocker": "user_defect_replay_required"}),
            "user_benefit": visual.get("user_benefit", {"status": "not_run", "blocker": "user_outcome_data_missing"}),
            "publication_ready": False}


def scorecard_for_run(run_path):
    """读取显式冻结窗口与加性事件，不从 manifest 猜测观测分母。"""
    root = Path(run_path)
    if not root.is_dir():
        raise MetricEventError("run directory does not exist")
    window_path = root / "observability" / "quality-window.json"
    if not window_path.exists():
        return {"schema_version": 1, "status": "blocked",
                "reason_code": "quality_window_not_recorded", "target_pages": None,
                "tf": None, "cost": None, "rework": None, "deck_quality": deck_quality_for_run(root)}
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
    report["deck_quality"] = deck_quality_for_run(root)
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
