#!/usr/bin/env python3
"""表达优先模板迁移：preview → stage → verify → publish → cleanup。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime/src"))
from leo_ppt_generator.library_migration import (
    preview_migration, stage_migration, verify_migration, publish_migration, cleanup_migration,
)
from leo_ppt_generator.qualification import file_reference


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    phases = parser.add_subparsers(dest="phase", required=True)
    preview = phases.add_parser("preview")
    preview.add_argument("--source-root", required=True, type=Path)
    preview.add_argument("--out-plan", required=True, type=Path)
    preview.add_argument("--prerequisite", type=Path, help="同一证据根内的真实预迁移价值收据；缺失仅生成 U7-A 计划")
    stage = phases.add_parser("stage")
    stage.add_argument("--plan", required=True, type=Path)
    stage.add_argument("--staging-root", required=True, type=Path)
    verify = phases.add_parser("verify")
    verify.add_argument("--plan", required=True, type=Path)
    verify.add_argument("--staging-root", required=True, type=Path)
    verify.add_argument("--out-receipt", required=True, type=Path)
    verify.add_argument("--visual-receipt", type=Path, help="同一证据根内的 U6-A 收据；缺失不可发布")
    publish = phases.add_parser("publish")
    publish.add_argument("--plan", required=True, type=Path)
    publish.add_argument("--receipt", required=True, type=Path)
    publish.add_argument("--delivery-root", required=True, type=Path)
    cleanup = phases.add_parser("cleanup")
    cleanup.add_argument("--plan", required=True, type=Path)
    cleanup.add_argument("--publication-receipt", required=True, type=Path)
    cleanup.add_argument("--delivery-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.phase == "preview":
            root = args.out_plan.absolute().parent
            reference = file_reference(root, args.prerequisite.absolute().relative_to(root).as_posix()) if args.prerequisite else None
            result = preview_migration(args.source_root, args.out_plan, prerequisite=reference)
        elif args.phase == "stage":
            result = stage_migration(args.plan, args.staging_root)
        elif args.phase == "verify":
            root = args.plan.absolute().parent
            reference = file_reference(root, args.visual_receipt.absolute().relative_to(root).as_posix()) if args.visual_receipt else None
            result = verify_migration(args.plan, args.staging_root, args.out_receipt, visual_receipt=reference)
        elif args.phase == "publish":
            result = publish_migration(args.plan, args.receipt, args.delivery_root)
        else:
            result = cleanup_migration(args.plan, args.publication_receipt, args.delivery_root)
        print(json.dumps({key: value for key, value in result.items() if key in {
            "phase", "gate", "status", "plan_digest", "receipt_digest", "gaps", "publication_ready"}}, ensure_ascii=False, indent=2))
        return 0 if result.get("status", "passed") == "passed" else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"phase": args.phase, "status": "blocked", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
