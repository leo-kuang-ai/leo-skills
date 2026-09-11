#!/usr/bin/env python3
"""style_pack v2：新库风格包导出/导入（U8，方案 §7.3/【F2】）。

数据/代码分离：
  - 数据实体（brief/theme JSON）导入用户库 canonical；
  - 可执行内容（page.html/JS/CSS/SVG 活动内容）默认进入用户库
    reference/candidates 隔离区：可浏览、静态检查、转换，不能自动出样；
  - 采用为可执行模板须在用户库 governance/trust/ 落 executable-adoption-v1
    记录（绑定代码 digest + 实际审阅来源）；包内自报 trusted 一律无效。

Usage:
  python3 scripts/style_pack.py export <名> --out DIR
  python3 scripts/style_pack.py import DIR [--home DIR]
  python3 scripts/style_pack.py adopt DIR --reviewed-by <维护者> --basis <依据> [--home DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))

from leo_ppt_generator.styles import default_home, load_style  # noqa: E402

EXECUTABLE_SUFFIXES = {".html", ".js", ".css", ".svg", ".mjs"}


def _user_library(home: Path | None) -> Path:
    return (home or default_home()) / "template-library"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_export(name: str, out_dir: Path) -> int:
    loaded = load_style(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "brief.json").write_text(
        json.dumps(loaded["brief"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "kind": "leo-style-pack", "schema_version": 2,
        "asset_id": loaded["asset_id"], "name": loaded["name"],
        "lifecycle": loaded["lifecycle"],
        "files": {"brief.json": hashlib.sha256(
            (out_dir / "brief.json").read_bytes()).hexdigest()},
        "note": "数据导出（脱敏由导出方负责）；不含执行面内容",
    }
    _write_json(out_dir / "manifest.json", manifest)
    print(json.dumps({"exported": loaded["asset_id"], "out": str(out_dir)}, ensure_ascii=False))
    return 0


def cmd_import(pack_dir: Path, home: Path | None) -> int:
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.is_file():
        print("usage: 包缺 manifest.json", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "leo-style-pack" or manifest.get("schema_version") != 2:
        print("usage: 非 v2 风格包", file=sys.stderr)
        return 2
    # F2：包内自报信任/内置身份一律无效。
    if manifest.get("trusted") or str(manifest.get("asset_id", "")).startswith("builtin:"):
        print("usage: 包内信任声明无效（pack_trusted_claim_invalid）；"
              "builtin 身份不可由导入包冒充", file=sys.stderr)
        return 2
    library = _user_library(home)
    for name, expected in sorted((manifest.get("files") or {}).items()):
        source = pack_dir / name
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            print(f"usage: 文件缺失或 hash 不符：{name}", file=sys.stderr)
            return 2
        if source.suffix.lower() in EXECUTABLE_SUFFIXES:
            target = library / "reference" / "candidates" / manifest["name"] / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            print(json.dumps({"quarantined": name,
                              "to": str(target.relative_to(library)),
                              "reason": "executable_content_default_isolated"}, ensure_ascii=False))
            continue
        brief = json.loads(source.read_text(encoding="utf-8"))
        slug = str(brief.get("asset_id", "")).split(":", 2)[-1] or manifest["name"]
        brief["asset_id"] = f"user:style:{slug}"
        brief.setdefault("source", {})["origin"] = "user-imported"
        _write_json(library / "canonical" / "styles" / slug / "brief.json", brief)
        print(json.dumps({"imported": brief["asset_id"]}, ensure_ascii=False))
    return 0


def cmd_adopt(pack_dir: Path, reviewed_by: str, basis: str, home: Path | None) -> int:
    library = _user_library(home)
    adoption_dir = library / "governance" / "trust"
    candidates = library / "reference" / "candidates"
    if not candidates.is_dir():
        print("usage: 隔离区为空，先 import", file=sys.stderr)
        return 2
    code_digests: dict[str, str] = {}
    for path in sorted(candidates.rglob("*")):
        if path.is_file() and path.suffix.lower() in EXECUTABLE_SUFFIXES:
            code_digests[path.relative_to(candidates).as_posix()] = \
                hashlib.sha256(path.read_bytes()).hexdigest()
    if not code_digests:
        print("usage: 无可执行内容可采用", file=sys.stderr)
        return 2
    adoption = {
        "kind": "executable-adoption", "schema_version": 1,
        "adoption_id": f"adopt-{hashlib.sha256(json.dumps(code_digests, sort_keys=True).encode()).hexdigest()[:12]}",
        "template_asset_id": pack_dir.name, "scope": "user",
        "code_digests": code_digests,
        "review": {"reviewed_by": reviewed_by, "basis": basis},
        "adopted_from": str(pack_dir),
    }
    _write_json(adoption_dir / f"{adoption['adoption_id']}.json", adoption)
    print(json.dumps({"adopted": adoption["adoption_id"],
                      "bound_files": len(code_digests)}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="style_pack v2（新库数据/代码分离）")
    sub = parser.add_subparsers(dest="command", required=True)
    p_export = sub.add_parser("export")
    p_export.add_argument("name")
    p_export.add_argument("--out", required=True)
    p_import = sub.add_parser("import")
    p_import.add_argument("pack_dir")
    p_import.add_argument("--home")
    p_adopt = sub.add_parser("adopt")
    p_adopt.add_argument("pack_dir")
    p_adopt.add_argument("--reviewed-by", required=True)
    p_adopt.add_argument("--basis", required=True)
    p_adopt.add_argument("--home")
    args = parser.parse_args(argv)
    if args.command == "export":
        return cmd_export(args.name, Path(args.out).expanduser())
    if args.command == "import":
        return cmd_import(Path(args.pack_dir).expanduser(), Path(args.home).expanduser() if args.home else None)
    return cmd_adopt(Path(args.pack_dir).expanduser(), args.reviewed_by, args.basis,
                     Path(args.home).expanduser() if args.home else None)


if __name__ == "__main__":
    raise SystemExit(main())
