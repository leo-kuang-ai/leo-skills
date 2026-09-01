#!/usr/bin/env python3
"""Multi-round eval statistics for skill-up evaluation results (R-51).

Computes, from repeated evaluation rounds:

1. Per-case PASS rate with a Wilson score 95% confidence interval (z = 1.96),
   plus a verdict:
     - ``stable_pass``: CI lower bound > 0.5
     - ``stable_fail``: CI upper bound < 0.5
     - ``trending``:    interval spans 0.5, or sample count < --min-samples
   ERROR results count toward the denominator but never toward PASS.

2. Judge-fix replay comparison via ``--replay-before`` / ``--replay-after``
   (comma-separated numeric series, e.g. per-round PASS counts of the same
   case set replayed before and after a judge fix):
     - Mann-Whitney U, normal approximation with tie correction
       (sigma^2 = mn/12 * ((N+1) - sum(t^3-t)/(N(N-1)))) and continuity
       correction z = (|U - mn/2| - 0.5) / sigma;
     - Fisher exact test on the 2x2 PASS-count table. The table is derived
       automatically when both series are 0/1; otherwise pass --fisher-table
       a,b,c,d explicitly (or Fisher is reported as null with a reason).

Input formats (probed per file; unrecognized input fails loudly with exit 2):

(a) skill-up ``result.json`` (one file = one round; pass several files for
    several rounds). Observed real schema (probed from skill-up workspaces):
    {"skill_name": str, "schema_version": "v1alpha1", ...,
     "case_results": [{"case_id": str, "title": str,
                       "status": "PASS" | "FAIL" | "ERROR", ...}]}
    Only schema_version "v1alpha1" is accepted; other versions are rejected.

(b) Simple NDJSON: one JSON object per line,
    {"case": <str>, "status": "PASS" | "FAIL" | "ERROR", "round": <int, optional>}
    A single file may carry any number of rounds/cases.

Determinism: identical inputs produce byte-identical output (sorted cases,
sorted JSON keys, no timestamps). Stdlib only.

Usage:
    eval_stats.py ROUND_FILES... [--min-samples N] [--alpha A] [--json]
    eval_stats.py --replay-before NUMS --replay-after NUMS
                  [--fisher-table A,B,C,D] [--alpha A] [--json]

Exit codes: 0 on success, 2 on usage or input-format errors.
"""
import argparse
import json
import math
import sys
from pathlib import Path

Z_95 = 1.96
SUPPORTED_STATUSES = ("PASS", "FAIL", "ERROR")
SUPPORTED_SKILLUP_SCHEMA = ("v1alpha1")
FORMAT_SKILLUP = "skill-up-result-v1alpha1"
FORMAT_NDJSON = "ndjson-v1"


class FormatError(Exception):
    """Raised when an input file does not match a supported format."""


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def wilson_ci(passes, total, z=Z_95):
    """Wilson score interval for a binomial proportion, clamped to [0, 1].

    Returns (low, high) or None when total == 0.
    """
    if total <= 0:
        return None
    phat = passes / total
    denom = 1.0 + z * z / total
    center = (phat + z * z / (2.0 * total)) / denom
    half = (z / denom) * math.sqrt(
        phat * (1.0 - phat) / total + z * z / (4.0 * total * total)
    )
    return max(0.0, center - half), min(1.0, center + half)


def classify_verdict(low, high, total, min_samples=3):
    """Map a Wilson interval to stable_pass / stable_fail / trending."""
    if total < min_samples or low is None or high is None:
        return "trending"
    if low > 0.5:
        return "stable_pass"
    if high < 0.5:
        return "stable_fail"
    return "trending"


def _normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def mann_whitney_u(xs, ys, alpha=0.05):
    """Two-sided Mann-Whitney U via normal approximation.

    Tie correction over joint ranks; continuity correction on z.
    U is min(U_x, U_y) against mu = m*n/2.
    """
    m, n = len(xs), len(ys)
    if m == 0 or n == 0:
        raise ValueError("Mann-Whitney U requires non-empty samples on both sides")
    groups = [(v, 0) for v in xs] + [(v, 1) for v in ys]
    groups.sort(key=lambda p: p[0])
    ranks = []
    tie_cube_sum = 0
    i = 0
    while i < len(groups):
        j = i
        while j < len(groups) and groups[j][0] == groups[i][0]:
            j += 1
        t = j - i
        tie_cube_sum += t * t * t - t
        avg_rank = (i + 1 + j) / 2.0
        ranks.extend([avg_rank] * t)
        i = j
    rank_sum_x = sum(r for r, g in zip(ranks, groups) if g[1] == 0)
    u_x = rank_sum_x - m * (m + 1) / 2.0
    u_y = m * n - u_x
    u = min(u_x, u_y)
    big_n = m + n
    sigma2 = (m * n / 12.0) * (
        (big_n + 1) - tie_cube_sum / (big_n * (big_n - 1))
    )
    mu = m * n / 2.0
    sigma = math.sqrt(sigma2)
    z = (abs(u - mu) - 0.5) / sigma
    p = min(1.0, 2.0 * (1.0 - _normal_cdf(abs(z))))
    return {
        "u": u,
        "u_before": u_x,
        "u_after": u_y,
        "mu": mu,
        "sigma2": sigma2,
        "sigma": sigma,
        "z": z,
        "p": p,
        "significant": p < alpha,
        "alpha": alpha,
    }


def fisher_exact(a, b, c, d, alpha=0.05):
    """Two-sided Fisher exact test on table [[a, b], [c, d]].

    Probabilities share denominator C(N, c1), so the <= comparison for the
    two-sided sum runs entirely on integer weights: exact, no float drift.
    """
    r1, r2, c1 = a + b, c + d, a + c
    total_n = r1 + r2
    obs_weight = math.comb(r1, a) * math.comb(r2, c1 - a)
    denom = math.comb(total_n, c1)
    favorable = 0
    for k in range(max(0, c1 - r2), min(c1, r1) + 1):
        w = math.comb(r1, k) * math.comb(r2, c1 - k)
        if w <= obs_weight:
            favorable += w
    p = favorable / denom
    return {
        "table": [[a, b], [c, d]],
        "p": p,
        "significant": p < alpha,
        "alpha": alpha,
    }


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def _validate_status(status, where):
    if status not in SUPPORTED_STATUSES:
        raise FormatError(
            f"unknown status {status!r} at {where} "
            f"(expected one of {', '.join(SUPPORTED_STATUSES)})"
        )


def _parse_skillup(doc, where):
    version = doc.get("schema_version")
    if version not in SUPPORTED_SKILLUP_SCHEMA:
        raise FormatError(
            f"unsupported skill-up schema_version {version!r} in {where} "
            f"(supported: {', '.join(SUPPORTED_SKILLUP_SCHEMA)})"
        )
    case_results = doc.get("case_results")
    if not isinstance(case_results, list):
        raise FormatError(f"case_results must be a list in {where}")
    records = []
    for idx, item in enumerate(case_results):
        at = f"{where} case_results[{idx}]"
        if not isinstance(item, dict):
            raise FormatError(f"case result must be an object at {at}")
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise FormatError(f"missing case_id at {at}")
        _validate_status(item.get("status"), at)
        records.append({"case": case_id, "status": item["status"]})
    return {"format": FORMAT_SKILLUP, "records": records}


def _validate_ndjson_record(obj, where):
    case = obj.get("case")
    if not isinstance(case, str) or not case:
        raise FormatError(f"missing 'case' field at {where}")
    _validate_status(obj.get("status"), where)
    if "round" in obj and not isinstance(obj["round"], int):
        raise FormatError(f"'round' must be an integer at {where}")
    return {"case": case, "status": obj["status"]}


def _parse_ndjson_lines(text, where):
    records = []
    first_decode_error = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if first_decode_error is None:
                first_decode_error = f"invalid JSON at line {lineno}: {exc}"
            continue
        if not isinstance(obj, dict):
            raise FormatError(f"NDJSON line must be an object at {where} line {lineno}")
        records.append(_validate_ndjson_record(obj, f"{where} line {lineno}"))
    if not records:
        if first_decode_error is not None:
            raise FormatError(
                f"unrecognized input format: {where} "
                f"(not skill-up result.json or NDJSON; {first_decode_error})"
            )
        raise FormatError(f"no records found in {where}")
    return {"format": FORMAT_NDJSON, "records": records}


def parse_rounds_file(path):
    """Probe one input file: skill-up result.json or NDJSON. One round per file
    for the skill-up format; NDJSON carries its own records."""
    where = str(path)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise FormatError(f"cannot read {where}: {exc}")
    stripped = text.strip()
    if not stripped:
        raise FormatError(f"empty input file: {where}")
    try:
        whole = json.loads(stripped)
    except json.JSONDecodeError:
        return _parse_ndjson_lines(text, where)
    if isinstance(whole, dict) and "case_results" in whole:
        return _parse_skillup(whole, where)
    if isinstance(whole, dict) and "case" in whole and "status" in whole:
        # Single-line NDJSON object is also valid whole-file JSON.
        return {
            "format": FORMAT_NDJSON,
            "records": [_validate_ndjson_record(whole, f"{where} line 1")],
        }
    raise FormatError(
        f"unrecognized input format: {where} "
        f"(expected skill-up result.json or NDJSON lines)"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_numeric_series(value, flag):
    parts = [p.strip() for p in value.split(",")]
    series = []
    for p in parts:
        if not p:
            raise FormatError(f"{flag} contains an empty value: {value!r}")
        try:
            v = float(p)
        except ValueError:
            raise FormatError(f"{flag} value {p!r} is not a number")
        if not math.isfinite(v) or v < 0:
            raise FormatError(f"{flag} value {p!r} must be a non-negative number")
        series.append(v)
    if not series:
        raise FormatError(f"{flag} is empty")
    return series


def _parse_fisher_table(value):
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        raise FormatError(f"--fisher-table expects 4 integers, got {value!r}")
    cells = []
    for p in parts:
        try:
            n = int(p)
        except ValueError:
            raise FormatError(f"--fisher-table value {p!r} is not an integer")
        if n < 0:
            raise FormatError(f"--fisher-table value {p!r} must be non-negative")
        cells.append(n)
    return cells


def _fail(msg):
    print(f"eval_stats: error: {msg}", file=sys.stderr)
    return 2


def _fmt(x):
    return "n/a" if x is None else f"{x:.6f}"


def _text_report(payload):
    lines = []
    if payload["formats"]:
        lines.append(f"formats: {', '.join(payload['formats'])}")
    if payload["rounds"]:
        lines.append(f"rounds: {len(payload['rounds'])}")
    lines.append(f"min_samples: {payload['min_samples']}  alpha: {payload['alpha']}")
    if payload["cases"]:
        lines.append("cases:")
        for c in payload["cases"]:
            rate = "n/a" if c["rate"] is None else f"{c['rate']:.4f}"
            lines.append(
                f"  {c['case']}: {c['pass']}/{c['total']} pass (rate {rate})"
                f"  wilson95 [{_fmt(c['wilson_low'])}, {_fmt(c['wilson_high'])}]"
                f"  -> {c['verdict']}"
            )
    replay = payload.get("replay")
    if replay:
        lines.append("replay:")
        mw = replay["mann_whitney"]
        verdict = "significant" if mw["significant"] else "not significant"
        lines.append(
            f"  mann-whitney: U={mw['u']:.6f} mu={mw['mu']:.6f}"
            f" sigma2={mw['sigma2']:.6f} z={mw['z']:.6f} p={mw['p']:.6f}"
            f" -> {verdict} (alpha={mw['alpha']})"
        )
        fisher = replay["fisher"]
        if fisher is None:
            lines.append(
                "  fisher: n/a (series are not 0/1; pass --fisher-table a,b,c,d)"
            )
        else:
            verdict = "significant" if fisher["significant"] else "not significant"
            lines.append(
                f"  fisher: table {fisher['table']} p={fisher['p']:.6f}"
                f" -> {verdict} (alpha={fisher['alpha']})"
            )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="eval_stats.py",
        description=(
            "Multi-round eval statistics: per-case Wilson 95% CI verdicts and "
            "judge-fix replay significance tests (Mann-Whitney U + Fisher exact)."
        ),
        epilog=(
            "examples: eval_stats.py iteration-1/result.json iteration-2/result.json "
            "--json; eval_stats.py --replay-before 1,1,0,0 --replay-after 1,1,1,1"
        ),
    )
    parser.add_argument(
        "files", nargs="*",
        help="round files: skill-up result.json (one per round) or NDJSON",
    )
    parser.add_argument(
        "--min-samples", type=int, default=3,
        help="minimum samples before a case can leave trending (default: 3)",
    )
    parser.add_argument(
        "--alpha", type=float, default=0.05,
        help="significance level for replay tests (default: 0.05)",
    )
    parser.add_argument(
        "--replay-before", metavar="NUMS",
        help="comma-separated series before the judge fix (e.g. per-round PASS counts)",
    )
    parser.add_argument(
        "--replay-after", metavar="NUMS",
        help="comma-separated series after the judge fix",
    )
    parser.add_argument(
        "--fisher-table", metavar="A,B,C,D",
        help="explicit 2x2 PASS-count table for Fisher (overrides derivation)",
    )
    parser.add_argument(
        "--json", action="store_true", help="machine-readable JSON output"
    )
    args = parser.parse_args(argv)

    if args.min_samples < 1:
        return _fail("--min-samples must be >= 1")
    if not (0.0 < args.alpha < 1.0):
        return _fail("--alpha must be in (0, 1)")

    has_before = args.replay_before is not None
    has_after = args.replay_after is not None
    if has_before != has_after:
        return _fail("--replay-before and --replay-after must be given together")
    if not args.files and not has_before:
        return _fail("no input: pass round files or --replay-before/--replay-after")

    formats = set()
    rounds_meta = []
    per_case = {}
    for path in args.files:
        if not Path(path).is_file():
            return _fail(f"input file not found: {path}")
        try:
            parsed = parse_rounds_file(path)
        except FormatError as exc:
            return _fail(str(exc))
        formats.add(parsed["format"])
        for rec in parsed["records"]:
            stats = per_case.setdefault(rec["case"], {"pass": 0, "total": 0})
            stats["total"] += 1
            if rec["status"] == "PASS":
                stats["pass"] += 1
        rounds_meta.append({
            "file": str(path),
            "format": parsed["format"],
            "cases": len(parsed["records"]),
            "pass": sum(1 for r in parsed["records"] if r["status"] == "PASS"),
            "fail": sum(1 for r in parsed["records"] if r["status"] == "FAIL"),
            "error": sum(1 for r in parsed["records"] if r["status"] == "ERROR"),
        })

    cases = []
    for name in sorted(per_case):
        stats = per_case[name]
        interval = wilson_ci(stats["pass"], stats["total"])
        low, high = interval if interval else (None, None)
        cases.append({
            "case": name,
            "pass": stats["pass"],
            "total": stats["total"],
            "rate": (stats["pass"] / stats["total"]) if stats["total"] else None,
            "wilson_low": low,
            "wilson_high": high,
            "verdict": classify_verdict(low, high, stats["total"], args.min_samples),
        })

    payload = {
        "formats": sorted(formats),
        "rounds": rounds_meta,
        "min_samples": args.min_samples,
        "alpha": args.alpha,
        "cases": cases,
    }

    if has_before:
        try:
            before = _parse_numeric_series(args.replay_before, "--replay-before")
            after = _parse_numeric_series(args.replay_after, "--replay-after")
        except FormatError as exc:
            return _fail(str(exc))
        try:
            mw = mann_whitney_u(before, after, alpha=args.alpha)
        except ValueError as exc:
            return _fail(str(exc))
        fisher = None
        if args.fisher_table is not None:
            try:
                a, b, c, d = _parse_fisher_table(args.fisher_table)
            except FormatError as exc:
                return _fail(str(exc))
            fisher = fisher_exact(a, b, c, d, alpha=args.alpha)
        elif all(v in (0.0, 1.0) for v in before + after):
            fisher = fisher_exact(
                int(sum(before)), int(len(before) - sum(before)),
                int(sum(after)), int(len(after) - sum(after)),
                alpha=args.alpha,
            )
        payload["replay"] = {
            "before": before,
            "after": after,
            "mann_whitney": mw,
            "fisher": fisher,
        }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        sys.stdout.write(_text_report(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
