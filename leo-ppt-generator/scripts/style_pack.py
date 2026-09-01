#!/usr/bin/env python3
"""风格包导入导出（R-33）：团队/跨机风格迁移通道，不做中心化市场。

上游原型：file-github/md `themeExporter.ts`（导出＝变量 + 基础主题 + 自定义
合并为一个带说明头的可下载文件），经 leo 化为「brief + 主题 token sidecar +
画廊缩略图 + manifest」的目录约定；导入侧过治理门后入位。

用法::

    python3 scripts/style_pack.py export <风格名> --out DIR [--root ROOT]
    python3 scripts/style_pack.py import DIR [--target <子家族目录>] [--root ROOT]

``export`` 打包：brief（同名 ``.md``）+ 主题 token sidecar（同名
``.layouts.json``，若有）+ 画廊缩略图（``samples/style-gallery/<风格名>/
thumb-*.png``，若在）+ ``manifest.json``（sha256 清单，不含时间戳——导出
确定性）。风格名在顶层内置与 01/02/03/05 参考轴中解析，须唯一。

``import`` 校验（全过才入位，任一失败拒收并报清单，exit 1）：

1. **manifest 完整**：``pack_version==1``、``style_name`` 非空、``files``
   非空且含恰好一项 ``role=brief``；声明的每个文件存在且 sha256 匹配
   （声明了却缺文件 → 拒收报缺失清单，AE-43）；
2. **brief 过 lint**：经 ``lint_style_briefs._lint_one`` 单文件校验
   （required 键 / HEX 锚点 / 身份字族 / 负面提示词与插画配对形状）；
3. **名称冲突**：``style_name`` 与库内既有风格同名 → 拒收；
4. **同板预检**：导入 brief（无 ``variant_of``）色板指纹与既有顶层风格
   相同 → ``family_duplicate`` 拒收（R-66 同板须走家族变体）。

入位：``--target``（如 ``01_通用母版/商务专业``）优先；否则按 manifest
``source_rel`` 的子目录路径放回；顶层位置不可 import（需 ``--target``）。
入位后须同步 ``_INDEX.md`` 计数与 ``视觉风格配对.md`` 配对行，四条治理
lint 全绿才算完成入位（脚本末尾打印提示）。

退出码：0 = 成功；1 = 校验失败/拒收；2 = 用法错误（风格名不存在/目录
缺失/参数不全）。纯 stdlib、确定性（sha256 + 排序遍历，无时间戳）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))
import lint_style_briefs as lsb  # noqa: E402

PACK_VERSION = 1
BRIEF_DIRS = ("01_通用母版", "02_行业内容域", "03_场景用途结构",
              "05_来源_awesome-gpt-image-2")
# Import targets must be reference sub-family dirs, never the top level
# (top-level slots demand a same-stem .layouts.json routing view).
IMPORTABLE_PREFIXES = ("01_通用母版", "02_行业内容域", "03_场景用途结构",
                       "05_来源_awesome-gpt-image-2")
_JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _styles_root(root: Path) -> Path:
    return root / "references" / "styles"


def _find_style_brief(root: Path, style_name: str) -> Path | None:
    """Resolve a style by file stem over top level + reference axes.

    A stem collision across axes is ambiguous and refuses to export.
    """
    styles = _styles_root(root)
    candidates: list[Path] = [p for p in styles.glob("*.md") if p.stem == style_name]
    for d in BRIEF_DIRS:
        candidates += [p for p in (styles / d).rglob("*.md") if p.stem == style_name]
    if len(candidates) > 1:
        return None  # ambiguous: caller reports the collision
    return candidates[0] if candidates else None


def _iter_library_briefs(root: Path):
    """Yield every parseable brief file under the styles root (sorted)."""
    yield from lsb._brief_files(_styles_root(root))


def _parse_brief(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def cmd_export(style_name: str, out_dir: Path, root: Path) -> int:
    src = _find_style_brief(root, style_name)
    if src is None:
        # Distinguish "not found" vs "ambiguous stem" for the error message.
        styles = _styles_root(root)
        hits = [p for p in styles.rglob(f"{style_name}.md")]
        if len(hits) > 1:
            print(f"style_name_ambiguous: {style_name} 命中 {len(hits)} 份 brief，"
                  " refusing export", file=sys.stderr)
        else:
            print(f"style_not_found: {style_name}（顶层内置 + 01/02/03/05 参考轴"
                  " 中未找到）", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []

    brief_dest = out_dir / "brief.md"
    brief_dest.write_bytes(src.read_bytes())
    entries.append({"path": "brief.md", "role": "brief", "sha256": _sha256(brief_dest)})

    # Token sidecar: same-stem .layouts.json next to the brief, if any.
    sidecar = src.with_name(f"{src.stem}.layouts.json")
    if sidecar.is_file():
        sc_dest = out_dir / sidecar.name
        sc_dest.write_bytes(sidecar.read_bytes())
        entries.append({"path": sidecar.name, "role": "token_sidecar",
                        "sha256": _sha256(sc_dest)})

    # Gallery thumbnails, if rendered for this style.
    gallery = root / "samples" / "style-gallery" / style_name
    thumbs = sorted(p for p in gallery.glob("thumb-*.png")) if gallery.is_dir() else []
    for thumb in thumbs:
        dest = out_dir / "thumbs" / thumb.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(thumb.read_bytes())
        rel = str(dest.relative_to(out_dir))
        entries.append({"path": rel, "role": "thumbnail", "sha256": _sha256(dest)})

    manifest = {
        "pack_version": PACK_VERSION,
        "exported_by": "leo-ppt-generator style_pack",
        "style_name": style_name,
        "source_rel": str(src.relative_to(root)),
        "files": sorted(entries, key=lambda e: e["path"]),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    roles = [e["role"] for e in entries]
    print(f"exported: {style_name} -> {out_dir} "
          f"(brief=1, sidecar={roles.count('token_sidecar')}, "
          f"thumbs={roles.count('thumbnail')})")
    return 0


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------
def _check_manifest(out: list[str], pack_dir: Path) -> tuple[dict, list[dict]] | None:
    """Validate manifest completeness + file presence; return (manifest, entries)."""
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.is_file():
        out.append("manifest_missing: 包内缺 manifest.json")
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        out.append(f"manifest_invalid: manifest.json 不可解析（{exc}）")
        return None
    if not isinstance(manifest, dict):
        out.append("manifest_invalid: manifest.json 须为 JSON 对象")
        return None
    if manifest.get("pack_version") != PACK_VERSION:
        out.append(f"manifest_pack_version: 须为 {PACK_VERSION}，"
                   f"got {manifest.get('pack_version')!r}")
    name = manifest.get("style_name")
    if not isinstance(name, str) or not name.strip():
        out.append("manifest_style_name: style_name 缺失或为空")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        out.append("manifest_files: files 缺失或为空")
        return None if out else (manifest, [])
    brief_roles = [f for f in files if isinstance(f, dict) and f.get("role") == "brief"]
    if len(brief_roles) != 1:
        out.append(f"manifest_brief_role: files 须含恰好一项 role=brief，"
                   f"got {len(brief_roles)}")
    for entry in files:
        if not isinstance(entry, dict):
            out.append("manifest_file_entry: files 条目须为对象")
            continue
        rel = entry.get("path")
        if not isinstance(rel, str) or not rel:
            out.append("manifest_file_path: 条目缺 path")
            continue
        target = (pack_dir / rel).resolve()
        # Path-boundary check via relative_to: str.startswith would let a
        # sibling directory (pack-evil next to pack) pass the prefix test.
        try:
            target.relative_to(pack_dir.resolve())
        except ValueError:
            out.append(f"path_escape: {rel} 逃逸包目录")
            continue
        if not target.is_file():
            out.append(f"file_missing: {rel}（manifest 声明但包内缺失）")
            continue
        digest = entry.get("sha256")
        if isinstance(digest, str) and digest and _sha256(target) != digest:
            out.append(f"sha256_mismatch: {rel}")
    return (manifest, files) if not out else None


def cmd_import(pack_dir: Path, target: str | None, root: Path) -> int:
    problems: list[str] = []
    checked = _check_manifest(problems, pack_dir)
    if checked is None:
        for item in problems:
            print(f"  ✗ {item}")
        print(f"import REJECTED: manifest 校验失败 {len(problems)} 项")
        return 1
    manifest, files = checked
    style_name = str(manifest.get("style_name") or "").strip()

    brief_entry = next(f for f in files if f.get("role") == "brief")
    brief_path = pack_dir / brief_entry["path"]

    # Gate 2: single-file lint (reference-style profile, non-builtin).
    schema = lsb._load_schema()
    errors, _warnings = lsb._lint_one(
        brief_path, schema, is_builtin=False, rel_to=pack_dir
    )
    for item in errors:
        problems.append(item)

    # Gate 3+4: name collision and same-palette family_duplicate pre-check
    # against the destination library.
    existing_names: dict[str, str] = {}
    existing_fingerprints: dict[frozenset, list[str]] = {}
    incoming = _parse_brief(brief_path)
    if incoming is None:
        problems.append("brief_json_invalid: 包内 brief 缺可解析 JSON 块")
    for path in _iter_library_briefs(root):
        brief = _parse_brief(path)
        if not brief:
            continue
        name = str(brief.get("style_name") or "")
        if name:
            existing_names[name] = str(path.relative_to(root))
        if brief.get("variant_of") is None:
            fp = lsb._palette_fingerprint(brief)
            if fp:
                existing_fingerprints.setdefault(fp, []).append(name)
    if style_name and style_name in existing_names:
        problems.append(
            f"name_conflict: {style_name} 已存在（{existing_names[style_name]}）"
        )
    if incoming is not None and incoming.get("variant_of") is None:
        fp = lsb._palette_fingerprint(incoming)
        clash = existing_fingerprints.get(fp, []) if fp else []
        if clash:
            problems.append(
                f"family_duplicate: 色板指纹与既有顶层风格 {sorted(clash)} 相同——"
                "同板场景须以 variant_of 归属家族主风格（R-66）"
            )

    if problems:
        for item in problems:
            print(f"  ✗ {item}")
        print(f"import REJECTED: 校验失败 {len(problems)} 项（{style_name}）")
        return 1

    # Resolve destination: --target wins, else manifest source_rel sub-family.
    styles = _styles_root(root)
    source_rel = str(manifest.get("source_rel") or "")
    source_sub = source_rel[len("references/styles/"):] if source_rel.startswith(
        "references/styles/") else ""
    rel_dir = target or (source_sub if source_sub.startswith(IMPORTABLE_PREFIXES) else "")
    if not rel_dir:
        print("usage: import 顶层位置不可入位，须 --target <参考轴子家族目录>"
              "（如 01_通用母版/商务专业）", file=sys.stderr)
        return 2
    dest_dir = (styles / rel_dir).resolve()
    # Same relative_to boundary as the manifest check: startswith would let
    # "../"-style targets land in a styles-prefixed sibling directory.
    try:
        dest_dir.relative_to(styles.resolve())
    except ValueError:
        print(f"usage: --target 逃逸风格库根：{rel_dir}", file=sys.stderr)
        return 2

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_brief = dest_dir / f"{style_name}.md"
    if dest_brief.exists():
        print(f"name_conflict: 目标文件已存在 {dest_brief.relative_to(root)}",
              file=sys.stderr)
        return 1
    dest_brief.write_bytes(brief_path.read_bytes())
    sidecars = [f for f in files if f.get("role") == "token_sidecar"]
    for entry in sidecars:
        src_file = pack_dir / entry["path"]
        (dest_dir / src_file.name).write_bytes(src_file.read_bytes())

    print(f"imported: {style_name} -> {dest_brief.relative_to(root)}"
          + (f"（+{len(sidecars)} sidecar）" if sidecars else ""))
    print("入位后续动作：_INDEX.md 顶行计数与对应小节表格 +1、"
          "视觉风格配对.md 补配对行；四条治理 lint 全绿才算完成入位。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_export = sub.add_parser("export", help="导出风格包（brief/sidecar/缩略图/manifest）")
    p_export.add_argument("style_name", help="风格名（顶层内置或 01/02/03/05 参考）")
    p_export.add_argument("--out", required=True, help="输出目录（不存在则创建）")
    p_import = sub.add_parser("import", help="导入风格包（过治理门后入位）")
    p_import.add_argument("pack_dir", help="风格包目录（含 manifest.json）")
    p_import.add_argument("--target", help="目标子家族目录"
                          "（如 01_通用母版/商务专业；顶层不可入位）")
    for p in (p_export, p_import):
        p.add_argument("--root", help="技能根目录覆盖（默认脚本所在仓库；供单测）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else SKILL_DIR

    if args.command == "export":
        out_dir = Path(args.out)
        if out_dir.exists() and not out_dir.is_dir():
            print(f"usage: --out 不是目录：{out_dir}", file=sys.stderr)
            return 2
        return cmd_export(args.style_name, out_dir, root)

    pack_dir = Path(args.pack_dir)
    if not pack_dir.is_dir():
        print(f"usage: 包目录不存在：{pack_dir}", file=sys.stderr)
        return 2
    return cmd_import(pack_dir, args.target, root)


if __name__ == "__main__":
    sys.exit(main())
