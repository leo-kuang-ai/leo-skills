#!/usr/bin/env python3
"""按冻结用例运行真实关系探针；只写证据，不自动发布 catalog 或授予资格。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from leo_ppt_generator.capability_probes import run_probes, image_probe_inputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--out", help="库内 evidence/probes/<name> 相对路径")
    parser.add_argument("--prepare-image-inputs", action="store_true", help="只输出冻结recipe探针输入，不调用Provider")
    parser.add_argument("--image-evidence", type=Path, help="case_id到正反Provider收据与raster_review引用的JSON")
    args = parser.parse_args(argv)
    try:
        cases = json.loads(args.cases.read_text())
        if args.prepare_image_inputs:
            import hashlib
            from leo_ppt_generator.qualification import environment_fingerprint
            from leo_ppt_generator.storage import json_document_bytes
            environment = environment_fingerprint()
            print(json.dumps({"status": "not_run", "environment": environment,
                "environment_sha256": hashlib.sha256(json_document_bytes(environment)).hexdigest(),
                "inputs": image_probe_inputs(library_root=args.library_root, cases=cases)}, ensure_ascii=False))
            return 0
        if not args.out:
            parser.error("执行探针必须指定 --out")
        result = run_probes(library_root=args.library_root, cases=cases, output=args.out,
                            image_evidence=json.loads(args.image_evidence.read_text()) if args.image_evidence else None)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] == "passed" else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
