#!/usr/bin/env python3
"""用户素材库登记器（R-04，借鉴 Beav 目录式素材库 + catalog.json 登记机制）。

库根目录约定为 `${LEO_PPT_HOME}/library/`（脚本不读环境变量，--root 显式传路径）：

    <root>/
      assets/<sha12>-<原名>     素材本体（内容寻址，sha256 前 12 位 + 原文件名）
      catalog.json              登记清单（sha256 + 来源元数据 + 标签 + 入库时间）

子命令：
  add FILE [--tags a,b] [--source URL|路径] [--note ...]
      计算素材 sha256，本体复制为 assets/<sha12>-<原名>，元数据写入 catalog.json。
      同 sha256 重复 add 幂等：打 WARN、不重复登记、不重复复制，exit 0。
  list [--tag a[,b]]
      列出登记条目；--tag 按标签过滤（逗号分隔，任一命中即入选）。
  remove SHA_PREFIX | --all
      清理入口：删除单条登记与对应资产（SHA 支持完整 64 位或 >=8 位唯一前缀），
      --all 清空整库。前缀无匹配或多义均 exit 2。
  export-manifest
      整库导出：输出与 references/sources-manifest-schema.md 兼容的 visual-sources
      JSON（逐条含 sha256/来源），最佳努力作为 `image prepare --sources` 输入。
      占位差异在 stderr 打 WARN（见下）。

数据边界（PRD R-04）：入库属用户主动动作，存储素材本体并以 sha256 + 来源元数据 +
标签登记；库仅存本地、随 LEO_PPT_HOME 数据目录管理（不入技能同步面）、提供整库导出
（export-manifest）与清理入口（remove / remove --all）；母版视觉行引用库内素材时
自动携带出处，sources-manifest 从库登记派生；与交付档案的边界——档案只存偏好字段，
素材库存用户主动入库的素材本体。

确定性：catalog.json 以 canonical 键序写盘，entries 按 sha256 排序、tags 排序去重；
list / export-manifest 输出固定排序；export-manifest 为纯派生（不含时间戳），
同一库状态导出 byte-identical。

export-manifest 的 WARN 项（与 sources-manifest 必填字段的如实差异）：
  - pages[].page_id 为占位 slide_01：库不知道页集合，接入真实 run 前须按
    slide_jobs.json 页集合改写（页集合覆盖校验是 run 级语义）；
  - source_ref 为库内绝对路径：strict 回溯可直接解析并核 sha256，冻结进 run 时
    由 image prepare 归一为 run 内相对路径；
  - review_status 固定 metadata-reviewed：库只登记元数据，未做视觉审查。

敏感纪律：--source / --note 按 check_sources_manifest.py 同款正则扫描，命中
（api_key/access_token/password/authorization/bearer/secret，大小写不敏感）拒绝
登记，exit 2——凭据不入库。

用法：脚本自包含（stdlib only），从技能目录内执行：
  python3 scripts/library_catalog.py --root <dir> add <file> ...

Exit codes: 0 成功（含幂等 WARN）；2 用法/输入错误（文件缺失、SHA 无匹配/多义、
空库导出、敏感命中）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
CATALOG_KIND = "library-catalog"
CATALOG_NAME = "catalog.json"
ASSETS_DIR = "assets"

# Mirrors SENSITIVE_RE in check_sources_manifest.py: credentials never enter the catalog.
SENSITIVE_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|password|authorization|bearer|secret)"
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UNSAFE_FILENAME_RE = re.compile(r"[^0-9A-Za-z._-]+")
MAX_NAME_LEN = 64
MIN_SHA_PREFIX = 8

# sources-manifest mapping constants (schema: references/sources-manifest-schema.md)
MANIFEST_KIND = "visual-sources"
EXPORT_PLACEHOLDER_PAGE = "slide_01"
EXPORT_REVIEW_STATUS = "metadata-reviewed"


class UsageError(Exception):
    """Input/usage error -> exit 2."""


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def warn(message: str) -> None:
    print(f"WARN {message}", file=sys.stderr)


def safe_stem(name: str) -> str:
    """Filesystem-safe stem for the content-addressed asset filename."""
    stem = UNSAFE_FILENAME_RE.sub("-", Path(name).name).strip("-.")
    stem = stem[:MAX_NAME_LEN].rstrip("-.")
    return stem or "asset"


def catalog_path(root: Path) -> Path:
    return root / CATALOG_NAME


def load_catalog(root: Path) -> dict | None:
    """Return catalog dict, or None when the library has not been initialized yet."""
    path = catalog_path(root)
    if not path.is_file():
        return None
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UsageError(f"{path}: catalog.json 无法读取或解析（{exc}）") from exc
    if not isinstance(catalog, dict) or not isinstance(catalog.get("entries"), list):
        raise UsageError(f"{path}: catalog.json 结构非法（缺 entries 数组）")
    return catalog


def save_catalog(root: Path, catalog: dict) -> None:
    # Deterministic write: canonical key order, entries sorted by sha256.
    catalog["entries"].sort(key=lambda entry: entry["sha256"])
    root.mkdir(parents=True, exist_ok=True)
    (root / ASSETS_DIR).mkdir(parents=True, exist_ok=True)
    path = catalog_path(root)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def parse_tags(raw: str | None) -> list[str]:
    """Split comma-separated tags; keep inner spaces, dedupe, sort."""
    if not raw:
        return []
    tags = [tag.strip() for tag in raw.split(",")]
    return sorted({tag for tag in tags if tag})


def cmd_add(args, root: Path) -> int:
    src = Path(args.file)
    if not src.is_file():
        raise UsageError(f"{src}: 素材文件不存在（add 需要一个普通文件）")

    if args.source and SENSITIVE_RE.search(args.source):
        raise UsageError("--source 命中敏感字段（凭据不入库），拒绝登记")
    if args.note and SENSITIVE_RE.search(args.note):
        raise UsageError("--note 命中敏感字段（凭据不入库），拒绝登记")

    digest = sha256_file(src)
    catalog = load_catalog(root) or {
        "schema_version": SCHEMA_VERSION,
        "kind": CATALOG_KIND,
        "entries": [],
    }
    existing = {
        entry["sha256"]: entry
        for entry in catalog["entries"]
        if isinstance(entry, dict) and isinstance(entry.get("sha256"), str)
    }
    if digest in existing:
        hit = existing[digest]
        warn(f"{src.name}: 已登记（sha256 {digest[:12]}，资产 {hit['asset_path']}），幂等跳过")
        if args.json:
            print(json.dumps({"action": "noop", "entry": hit}, ensure_ascii=False, indent=2))
        else:
            print(f"已登记: {hit['asset_path']}（{digest[:12]}）")
        return 0

    original_name = src.name
    asset_rel = f"{ASSETS_DIR}/{digest[:12]}-{safe_stem(original_name)}"
    asset_abs = root / asset_rel
    root.mkdir(parents=True, exist_ok=True)
    (root / ASSETS_DIR).mkdir(parents=True, exist_ok=True)
    if not asset_abs.is_file():
        shutil.copyfile(src, asset_abs)

    entry = {
        "sha256": digest,
        "asset_path": asset_rel,
        "original_name": original_name,
        "source": args.source or None,
        "added_at": now_iso(),
        "tags": parse_tags(args.tags),
        "note": args.note or None,
    }
    catalog["entries"].append(entry)
    save_catalog(root, catalog)
    if args.json:
        print(json.dumps({"action": "add", "entry": entry}, ensure_ascii=False, indent=2))
    else:
        tags = ",".join(entry["tags"]) or "-"
        print(f"已入库: {asset_rel}  sha256={digest[:12]}  tags={tags}")
    return 0


def cmd_list(args, root: Path) -> int:
    catalog = load_catalog(root)
    entries = sorted(
        (e for e in (catalog or {}).get("entries", []) if isinstance(e, dict)),
        key=lambda entry: entry.get("sha256", ""),
    )
    if args.tag:
        wanted = {tag.strip() for tag in args.tag.split(",") if tag.strip()}
        entries = [e for e in entries if wanted & set(e.get("tags") or [])]
    if args.json:
        print(json.dumps({"count": len(entries), "entries": entries},
                         ensure_ascii=False, indent=2))
        return 0
    if not entries:
        print("(空) 0 条登记")
        return 0
    for entry in entries:
        tags = ",".join(entry.get("tags") or []) or "-"
        source = entry.get("source") or "-"
        print(f"{entry['sha256'][:12]}  {entry['asset_path']}  tags={tags}  source={source}")
    print(f"共 {len(entries)} 条")
    return 0


def cmd_remove(args, root: Path) -> int:
    catalog = load_catalog(root)
    if catalog is None:
        raise UsageError(f"{catalog_path(root)}: catalog.json 不存在（空库无需清理）")

    entries = [e for e in catalog["entries"] if isinstance(e, dict)]
    if args.all:
        removed = entries
    else:
        prefix = args.sha.strip().lower()
        if not re.fullmatch(r"[0-9a-f]+", prefix):
            raise UsageError(f"SHA 前缀非法（{prefix}），应为十六进制")
        if len(prefix) < MIN_SHA_PREFIX:
            raise UsageError(f"SHA 前缀过短（{prefix}），至少 {MIN_SHA_PREFIX} 位")
        removed = [e for e in entries if str(e.get("sha256", "")).startswith(prefix)]
        if not removed:
            raise UsageError(f"无匹配登记（sha256 前缀 {prefix}）")
        if len(removed) > 1:
            candidates = ", ".join(e["sha256"][:12] for e in removed)
            raise UsageError(f"SHA 前缀多义（{prefix}）: {candidates}")

    root_resolved = root.resolve()
    for entry in removed:
        asset_rel = entry.get("asset_path")
        if not isinstance(asset_rel, str) or not asset_rel:
            raise UsageError(
                f"asset_path 缺失或非法（sha256 "
                f"{str(entry.get('sha256', ''))[:12]}），拒绝删除")
        # Hand-edited catalogs must not turn remove into an arbitrary unlink:
        # resolve and confine the target inside the library root first.
        try:
            asset_abs = (root / asset_rel).resolve()
            asset_abs.relative_to(root_resolved)
        except ValueError:
            raise UsageError(
                f"asset_path 越界（{asset_rel}），拒绝删除——库外文件不可经 "
                "remove 删除，请手工核对 catalog.json") from None
        if asset_abs.is_file():
            asset_abs.unlink()
    keep = [e for e in catalog["entries"] if e not in removed]
    catalog["entries"] = keep
    save_catalog(root, catalog)
    if args.json:
        print(json.dumps({"action": "remove", "removed": removed}, ensure_ascii=False, indent=2))
    else:
        for entry in removed:
            print(f"已移除: {entry['asset_path']}（{entry['sha256'][:12]}）")
        print(f"共移除 {len(removed)} 条")
    return 0


def build_export_manifest(root: Path, catalog: dict) -> dict:
    """Derive a sources-manifest-compatible projection from catalog entries."""
    entries = sorted(
        (e for e in catalog["entries"] if isinstance(e, dict)),
        key=lambda entry: entry.get("sha256", ""),
    )
    visuals = []
    for index, entry in enumerate(entries, start=1):
        visuals.append(
            {
                "visual_id": f"v{index}",
                "figure_id": f"F{index}",
                "kind": "figure",
                "source_class": "user-material",
                "tier": "引用",
                "handling_mode": "preserve",
                "review_status": EXPORT_REVIEW_STATUS,
                # Absolute library path: strict traceability resolves it directly
                # and can re-verify sha256; image prepare normalizes on freeze.
                "source_ref": str((root / entry["asset_path"]).resolve()),
                "source_sha256": entry["sha256"],
                "backend": "user",
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "route": "generate",
        "run_ref": None,
        "generated_from": str(catalog_path(root).resolve()),
        "pages": [{"page_id": EXPORT_PLACEHOLDER_PAGE, "visuals": visuals}],
        "contents_sha256": None,
    }
    payload = {key: value for key, value in manifest.items() if key != "contents_sha256"}
    manifest["contents_sha256"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return manifest


def cmd_export_manifest(args, root: Path) -> int:
    catalog = load_catalog(root)
    entries = [e for e in (catalog or {}).get("entries", []) if isinstance(e, dict)]
    if not entries:
        raise UsageError(
            "空库无法导出（sources-manifest 要求 pages 非空；先 add 素材或检查 --root）"
        )
    manifest = build_export_manifest(root, catalog)
    warn("page_id 为占位 slide_01：接入真实 run 前须按 slide_jobs.json 页集合改写")
    warn("source_ref 为库内绝对路径：冻结进 run 时由 image prepare 归一为相对路径")
    warn("review_status=metadata-reviewed：库只登记元数据，未做视觉审查")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    # --json lives on each subparser (argparse subcommands do not inherit
    # parent flags when placed after the subcommand token).
    json_flag = argparse.ArgumentParser(add_help=False)
    json_flag.add_argument("--json", action="store_true", help="机器可读 JSON 输出")

    parser = argparse.ArgumentParser(
        prog="library_catalog.py",
        description="用户素材库登记器（R-04）：assets/ 内容寻址存储 + catalog.json 登记 + sources-manifest 派生导出",
    )
    parser.add_argument("--root", required=True,
                        help="库根目录（约定 ${LEO_PPT_HOME}/library/，显式传路径）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", parents=[json_flag],
                           help="素材入库（sha256+元数据登记，本体复制进 assets/）")
    p_add.add_argument("file", help="素材文件路径")
    p_add.add_argument("--tags", default=None, help="逗号分隔标签（可含空格）")
    p_add.add_argument("--source", default=None, help="来源 URL 或路径")
    p_add.add_argument("--note", default=None, help="备注")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", parents=[json_flag], help="列出登记条目")
    p_list.add_argument("--tag", default=None, help="按标签过滤（逗号分隔，任一命中）")
    p_list.set_defaults(func=cmd_list)

    p_remove = sub.add_parser("remove", parents=[json_flag],
                              help="移除登记与资产（清理入口）")
    p_remove.add_argument("sha", nargs="?", default=None,
                          help="sha256 完整值或 >=8 位唯一前缀")
    p_remove.add_argument("--all", action="store_true", help="清空整库")
    p_remove.set_defaults(func=cmd_remove)

    p_export = sub.add_parser("export-manifest", parents=[json_flag],
                              help="导出 sources-manifest 兼容 JSON")
    p_export.set_defaults(func=cmd_export_manifest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "remove" and not args.all and not args.sha:
        parser.error("remove 需要 SHA 前缀或 --all")
    root = Path(args.root)
    try:
        return args.func(args, root)
    except UsageError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
