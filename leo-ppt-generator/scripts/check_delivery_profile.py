#!/usr/bin/env python3
"""Structural validator for delivery profiles (交付档案).

A profile is a small markdown file at ``${LEO_PPT_HOME}/profiles/<name>.md``
holding only preference fields that prefill the content contract. This script
checks the closed field set and warns on business-data heuristics (numbers
with business units outside the fields where numbers are legitimate). It never
reads or writes anything else; warnings do not block saving but must be shown
to the user before the profile is stored.

Exit codes: 0 = valid (warnings allowed); 2 = structural error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_FIELDS = (
    "audience",
    "scenario",
    "page_count_policy",
    "duration",
    "data_classification_default",
    "density",
)
OPTIONAL_FIELDS = ("preferred_style",)
# Numbers are legitimate in these fields (page arithmetic, talk length).
NUM_LEGIT_FIELDS = {"page_count_policy", "duration"}
BUSINESS_NUMBER = re.compile(r"\d+(?:\.\d+)?\s*(?:亿元|万元|亿元|亿|万|元|家|%|个亿)")
SECRET_LEVELS = ("机密", "绝密", "秘密")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_fields(text: str) -> "tuple[dict[str, str], list[str]]":
    fields: dict[str, str] = {}
    unknown: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        match = re.match(r"^([A-Za-z_]+)\s*[:：]\s*(.+)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key in REQUIRED_FIELDS or key in OPTIONAL_FIELDS:
            fields[key] = value
        else:
            unknown.append(key)
    return fields, unknown


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a delivery profile markdown file.")
    parser.add_argument("profile", help="path to the profile markdown file")
    args = parser.parse_args(argv)

    path = Path(args.profile)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read profile {path}: {exc}")

    fields, unknown = parse_fields(text)
    missing = [f for f in REQUIRED_FIELDS if f not in fields or not fields[f]]
    if missing:
        fail(f"missing or empty required fields: {', '.join(missing)}")
    if unknown:
        print(f"WARN: unknown fields ignored: {', '.join(unknown)}")

    warnings: list[str] = []
    for key, value in fields.items():
        if key in NUM_LEGIT_FIELDS:
            continue
        if BUSINESS_NUMBER.search(value):
            warnings.append(f"{key}:疑似业务数据({value[:30]})——档案只存偏好,请删除业务数字")
        if any(secret in value for secret in SECRET_LEVELS):
            warnings.append(f"{key}:涉密定级({value[:20]})不应作为默认偏好")
    for warning in warnings:
        print(f"WARN: {warning}")

    print(f"OK: {len(fields)} fields valid ({len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
