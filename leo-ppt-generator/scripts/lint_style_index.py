#!/usr/bin/env python3
"""派生风格索引与源文件一致性检查；不再维护第二套目录计数规则。"""
from __future__ import annotations

import json
from pathlib import Path

from capability_manifest import build_style_index, render_style_index, check_style_index
from lint_style_governance import check_document_links

SKILL_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        index = build_style_index(SKILL_DIR)
        files = render_style_index(index)
        report, code = check_style_index(index, files, SKILL_DIR / "references/styles/generated")
        documents = {"references/styles/generated/" + path: body.decode("utf-8")
                     for path, body in files.items() if path.endswith(".md")}
        for relative in ("references/styles/00_索引/_INDEX.md", "references/style-library.md",
                         "references/style-recommendation.md", "references/layout-dispatch.md"):
            documents[relative] = (SKILL_DIR / relative).read_text(encoding="utf-8")
        errors = check_document_links(documents, SKILL_DIR)
        if code:
            errors.insert(0, report["reason_code"])
        print(f"index_consistency errors={len(errors)}")
        for error in errors:
            print(error)
        return 2 if errors else 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"reason_code": "style_index_check_failed", "detail": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
