#!/usr/bin/env python3
"""Pre-dispatch token/cost estimator for image-deck runs.

Reads historical ``backend_stats.jsonl`` (see references/backend-selection.md
"backend × 页型路由") when available and produces a per-page-type token band
for a planned deck. With no usable history it falls back to conservative
assumed defaults and flags the basis so the estimate is never mistaken for a
measurement. Deterministic: same inputs produce byte-identical output.

Estimation model (approximation, documented here as the single source):
  per-page expected tokens(page_type) = mean(tokens per recorded attempt)
                                        x mean(attempts per page of that type)
  deck band = [estimate, estimate x headroom], headroom = 1.5 with history
  and 2.0 on assumed defaults (rework variance is higher when unmeasured).

Exit codes: 0 = estimate produced; 2 = invalid input or unreadable stats file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PAGE_TYPES = ("chart", "text-heavy", "image")
# Conservative placeholder bands when no history exists. These are disclosed
# assumptions, not measurements; keep in sync with backend-selection.md.
DEFAULT_PER_PAGE_TOKENS = {
    "chart": 9000,
    "text-heavy": 7000,
    "image": 5000,
    "default": 6000,
}
HISTORY_HEADROOM = 1.5
ASSUMED_HEADROOM = 2.0
TOKENS_NOT_RECORDED = "not-recorded"


def fail(message: str) -> "None":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_history(path: Path) -> list[dict]:
    records: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    fail(f"{path}:{line_no} is not valid JSON: {exc}")
    except OSError as exc:
        fail(f"cannot read stats file {path}: {exc}")
    return records


def per_type_stats(records: list[dict]) -> dict[str, dict]:
    """Aggregate records into per-page-type attempt/token statistics.

    ``tokens`` may be an int or the literal ``not-recorded``; unrecorded
    attempts still count toward the rework factor but not the token mean.
    """
    grouped: dict[str, dict] = {}
    for record in records:
        page_type = str(record.get("page_type", "")).strip()
        if page_type not in PAGE_TYPES:
            continue
        bucket = grouped.setdefault(
            page_type, {"pages": set(), "attempts": 0, "token_sum": 0, "token_records": 0}
        )
        slide = record.get("slide")
        if slide is not None:
            bucket["pages"].add(str(slide))
        attempts = record.get("attempts")
        bucket["attempts"] += attempts if isinstance(attempts, int) and attempts > 0 else 1
        tokens = record.get("tokens")
        if isinstance(tokens, int) and tokens >= 0:
            bucket["token_sum"] += tokens
            bucket["token_records"] += 1
    return grouped


def expected_tokens_per_page(stats: dict) -> "tuple[float | None, float]":
    """Return (mean tokens per recorded attempt, mean attempts per page)."""
    pages = max(len(stats["pages"]), 1)
    mean_attempts = stats["attempts"] / pages
    if stats["token_records"] == 0:
        return None, mean_attempts
    mean_tokens = stats["token_sum"] / stats["token_records"]
    return mean_tokens, mean_attempts


def build_estimate(args: argparse.Namespace) -> dict:
    counts = {"chart": args.chart, "text-heavy": args.text_heavy, "image": args.image}
    typed_pages = sum(counts.values())
    untyped_pages = max(args.pages - typed_pages, 0)
    if typed_pages > args.pages:
        fail(
            f"page-type counts ({typed_pages}) exceed --pages ({args.pages}); "
            "chart + text-heavy + image must be <= pages"
        )

    history: dict[str, dict] = {}
    if args.stats:
        records = load_history(Path(args.stats))
        history = per_type_stats(records)

    lines: list[dict] = []
    total_low = 0
    total_high = 0
    history_lines = 0
    estimated_lines = 0
    for page_type in PAGE_TYPES + ("default",):
        count = untyped_pages if page_type == "default" else counts[page_type]
        if count <= 0:
            continue
        stats = history.get(page_type) if page_type != "default" else None
        mean_tokens, mean_attempts = (
            expected_tokens_per_page(stats) if stats else (None, 1.0)
        )
        if mean_tokens is not None and stats and stats["token_records"] > 0:
            basis = "history"
            headroom = HISTORY_HEADROOM
            per_page = mean_tokens * max(mean_attempts, 1.0)
        else:
            basis = "assumed-default"
            headroom = ASSUMED_HEADROOM
            per_page = float(DEFAULT_PER_PAGE_TOKENS[page_type])
        history_lines += 1 if basis == "history" else 0
        estimated_lines += 1
        low = int(round(per_page * count))
        high = int(round(per_page * count * headroom))
        total_low += low
        total_high += high
        lines.append(
            {
                "page_type": page_type,
                "pages": count,
                "tokens_low": low,
                "tokens_high": high,
                "basis": basis,
            }
        )

    if history_lines and history_lines < estimated_lines:
        deck_basis = "mixed"
    elif history_lines:
        deck_basis = "history"
    else:
        deck_basis = "assumed-default"
    estimate = {
        "pages": args.pages,
        "tokens_low": total_low,
        "tokens_high": total_high,
        "basis": deck_basis,
        "lines": lines,
    }
    if args.price_per_1k is not None:
        estimate["cost_low"] = round(total_low / 1000 * args.price_per_1k, 2)
        estimate["cost_high"] = round(total_high / 1000 * args.price_per_1k, 2)
        estimate["price_per_1k"] = args.price_per_1k
    return estimate


def render_text(estimate: dict) -> str:
    basis_labels = {
        "history": "历史 backend_stats 均值 × 重试系数",
        "mixed": "历史均值与保守假设混合(逐行见括号)",
        "assumed-default": "保守假设区间(无历史数据)",
    }
    parts = [
        f"pages: {estimate['pages']}",
        f"tokens: {estimate['tokens_low']}–{estimate['tokens_high']}",
        f"basis: {basis_labels[estimate['basis']]}",
    ]
    if "cost_low" in estimate:
        parts.append(
            f"cost: {estimate['cost_low']}–{estimate['cost_high']}"
            f" (price {estimate['price_per_1k']}/1k tokens)"
        )
    for line in estimate["lines"]:
        parts.append(
            f"  {line['page_type']}: {line['pages']} 页 × "
            f"{line['tokens_low'] // max(line['pages'], 1)}"
            f"→ {line['tokens_high'] // max(line['pages'], 1)} tokens/页 ({line['basis']})"
        )
    parts.append("estimates are bands, not guarantees; reconcile with backend report after delivery")
    return "\n".join(parts)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Estimate the token/cost band of a planned image-deck run before dispatch."
    )
    parser.add_argument("--pages", type=int, required=True, help="total pages in the planned deck")
    parser.add_argument("--chart", type=int, default=0, help="pages of type chart")
    parser.add_argument("--text-heavy", type=int, default=0, help="pages of type text-heavy")
    parser.add_argument("--image", type=int, default=0, help="pages of type image")
    parser.add_argument(
        "--stats",
        help="optional backend_stats.jsonl (or run dir containing observability/) used as history",
    )
    parser.add_argument(
        "--price-per-1k", type=float, default=None, help="optional price per 1k tokens for a cost band"
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of text")
    args = parser.parse_args(argv)

    if args.pages <= 0:
        fail("--pages must be a positive integer")
    if min(args.chart, args.text_heavy, args.image) < 0:
        fail("page-type counts must be >= 0")
    if args.price_per_1k is not None and args.price_per_1k < 0:
        fail("--price-per-1k must be >= 0")

    stats_path = args.stats
    if stats_path:
        candidate = Path(stats_path)
        if candidate.is_dir():
            candidate = candidate / "observability" / "backend_stats.jsonl"
        if not candidate.is_file():
            fail(f"stats file not found: {candidate}")
        args.stats = str(candidate)

    estimate = build_estimate(args)
    if args.json:
        print(json.dumps(estimate, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(estimate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
