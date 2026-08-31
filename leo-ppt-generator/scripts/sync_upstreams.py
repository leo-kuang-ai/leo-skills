#!/usr/bin/env python3
"""Verify the vendored tree against vendor-lock.json and the release lock."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = SKILL_ROOT / "runtime/src/leo_ppt_generator/_vendor"
LOCK_PATH = SKILL_ROOT / "vendor-lock.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory() -> dict:
    files = {}
    for path in sorted(VENDOR_ROOT.rglob("*")):
        if not path.is_file() or path.suffix in {".pyc", ".pyo"} or "__pycache__" in path.parts:
            continue
        files[path.relative_to(SKILL_ROOT).as_posix()] = sha256_file(path)
    return {"schema_version": 1, "files": files}


def validate_metadata() -> list[str]:
    errors = []
    constraints = list((SKILL_ROOT / "runtime/constraints").glob("*.txt"))
    if not constraints:
        errors.append("runtime:missing_dependency_lock")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write-lock", action="store_true")
    args = parser.parse_args(argv)
    current = inventory()
    if args.write_lock:
        LOCK_PATH.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "written", "path": str(LOCK_PATH), "files": len(current["files"])}))
        return 0
    errors = validate_metadata()
    if not LOCK_PATH.is_file():
        errors.append("vendor:missing_lock")
    else:
        locked = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        if locked != current:
            errors.append("vendor:tree_hash_drift")
    report = {"schema_version": 1, "status": "passed" if not errors else "failed", "files": len(current["files"]), "errors": errors}
    print(json.dumps(report, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
