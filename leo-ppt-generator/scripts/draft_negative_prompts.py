#!/usr/bin/env python3
"""从 current 风格实体确定性起草 constraints.negative；默认仅预览。

使用 visual_language 中的显式禁止句，可用 --pool 叠加同库治理词条。
家族匹配只消费 taxonomy.families；--limit 同时限制预览和写入候选数。
--apply 必须显式指定 --library-root 到 v2 库，通过既有 CAS 事务同步发布
brief 与 catalog。当前库已有足够约束时不修改资产；不读取历史 Markdown。
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime/src"))
from leo_ppt_generator.asset_resolver import AssetResolver, builtin_library_root
from leo_ppt_generator.library_migration import file_state, library_operation, safe_path
from leo_ppt_generator.qualification import read_evidence_bytes
from leo_ppt_generator.user_library import json_bytes, publish_user_library, user_library_writer

DEFAULT_POOL = Path("governance/authoring/index/负面语料参考池.md")
_SPLIT = re.compile(r"[；;。]\s*|\s*[、，]\s*(?=不要|禁|避免|不)")
_NEGATIVE_HINT = re.compile(r"不要|禁|避免|不得|不用|不使用|不出现|拒绝|严禁|≤|不超过")


def _candidates(brief: dict) -> list[str]:
    language = brief.get("visual_language") or {}
    sources = [language.get("direction", ""), *language.get("features", []),
               *language.get("composition_discipline", []),
               *(language.get("continuity") or {}).values()]
    seen: list[str] = []
    for source in sources:
        if not isinstance(source, str):
            continue
        for raw in _SPLIT.split(source):
            text = raw.strip().strip("；;。，, ")
            if len(text) < 6 or not _NEGATIVE_HINT.search(text):
                continue
            if text not in seen and not any(text in kept for kept in seen):
                seen.append(text)
    return seen


def _load_pool(path: Path, *, root: Path | None = None) -> dict[str, list[str]]:
    path = Path(path).absolute()
    root = Path(root).absolute() if root is not None else path.parent
    if not path.is_relative_to(root):
        raise ValueError("negative_pool_outside_library")
    body = read_evidence_bytes(root, path.relative_to(root).as_posix()).decode("utf-8")
    groups: dict[str, list[str]] = {}
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            current = None if name == "选用指引" else groups.setdefault(name, [])
        elif current is not None and line.startswith("- "):
            item = line[2:].strip()
            if len(item) >= 6:
                current.append(item)
    if not groups or not any(groups.values()):
        raise ValueError("negative_pool_empty")
    return groups


def _pool_candidates(groups: dict[str, list[str]], families: set[str]) -> list[str]:
    return [item for name, items in groups.items() if name == "通用" or name in families
            for item in items]


def _resolver(root):
    # 显式库根不能叠加调用机器上的个人风格；缺 current 也不能降级扫描旧树。
    read_evidence_bytes(root, "catalog/current.json")
    resolver = AssetResolver(library=root, home=root / ".negative-no-user-home")
    if resolver.user_root is not None:
        raise ValueError("negative_user_overlay_forbidden")
    if resolver.registry_source != "catalog":
        raise ValueError("negative_catalog_required")
    return resolver


def run(library_root: Path | None = None, *, apply=False, limit=0, pool: Path | None = None):
    if apply and library_root is None:
        raise ValueError("negative_explicit_library_required")
    if limit < 0:
        raise ValueError("negative_limit_invalid")
    root = Path(library_root or builtin_library_root()).absolute()
    declaration_path = safe_path(root, "library.json")
    declaration = json.loads(read_evidence_bytes(root, declaration_path.relative_to(root).as_posix()))
    if apply and declaration.get("schema_version") != 2:
        raise ValueError("negative_library_migration_required")
    with library_operation(root), (user_library_writer(root) if apply else nullcontext()):
        resolver = _resolver(root)
        generation = resolver.generation
        frozen = {relative: file_state(root, relative) for relative in ("library.json", "catalog/current.json")}
        groups, guards = {}, {}
        if pool is not None:
            path = Path(pool).absolute()
            if not path.is_relative_to(root):
                raise ValueError("negative_pool_outside_library")
            relative = path.relative_to(root).as_posix()
            if not relative.startswith("governance/authoring/") or path.suffix != ".md":
                raise ValueError("negative_pool_owner_invalid")
            frozen[relative] = file_state(root, relative)
            groups = _load_pool(path, root=root)
            guards[relative] = frozen[relative]["sha256"]
        entities = sorted((row for row in resolver.entities if row["kind"] == "style"),
                          key=lambda row: row["asset_id"])
        if not entities:
            raise ValueError("negative_styles_empty")
        rows, writes, expected = [], {}, {}
        for entity in entities:
            resolved = resolver.resolve(entity["asset_id"])
            if Path(resolved["trusted_root"]) != root:
                raise ValueError("negative_style_outside_library")
            brief = resolved["data"]
            existing = brief.get("constraints", {}).get("negative", [])
            if len(existing) >= 3:
                continue
            relative = resolved["relative_path"]
            frozen[relative] = file_state(root, relative)
            candidates = _candidates(brief) + _pool_candidates(groups, set(brief["taxonomy"]["families"]))
            added = list(dict.fromkeys(item for item in candidates if item not in existing))[:3 - len(existing)]
            rows.append({"asset_id": resolved["asset_id"], "path": relative,
                         "existing": len(existing), "added": added,
                         "remaining": max(0, 3 - len(existing) - len(added))})
            if added:
                updated = deepcopy(brief)
                updated.setdefault("constraints", {})["negative"] = existing + added
                writes[relative] = json_bytes(updated)
                expected[resolved["asset_id"]] = updated
            if limit and len(rows) >= limit:
                break

        def check_frozen():
            for relative, state in frozen.items():
                if file_state(root, relative) != state:
                    raise ValueError("negative_input_drift:" + relative)
            if _resolver(root).generation != generation:
                raise ValueError("negative_catalog_drift")

        check_frozen()
        if apply and writes:
            first_check = True
            def validate():
                nonlocal first_check
                # 写后旧 brief/pointer 摘要必然改变，只在首个 CAS 前校验冻结输入。
                if first_check:
                    check_frozen()
                    first_check = False
            def verify():
                current = _resolver(root)
                for identity, data in expected.items():
                    if current.resolve(identity)["data"] != data:
                        raise ValueError("negative_postwrite_mismatch:" + identity)
            publish_user_library(root, writes, guards=guards, validator=validate,
                                 verifier=verify, overwrite=set(writes))
        return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--library-root", type=Path, help="明确目标库；--apply 必填且必须为 v2")
    parser.add_argument("--apply", action="store_true", help="事务写入缺少约束的 current brief 并发布 catalog")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个候选（0=全部，预览同样生效）")
    parser.add_argument("--pool", type=Path, nargs="?", const=DEFAULT_POOL,
                        help="同库治理词条池；裸 --pool 读取目标库内置池")
    args = parser.parse_args(argv)
    root = Path(args.library_root or builtin_library_root()).absolute()
    pool = root / DEFAULT_POOL if args.pool == DEFAULT_POOL else args.pool
    try:
        rows = run(args.library_root, apply=args.apply, limit=args.limit, pool=pool)
    except (ValueError, OSError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    for row in rows:
        print(f"{row['asset_id']}: 现有 {row['existing']} 条 → 补 {len(row['added'])} 条；仍缺 {row['remaining']} 条")
        for item in row["added"]:
            print("  + " + item)
    mode = "已执行事务写入" if args.apply else "dry-run"
    print(f"{mode}；候选 {len(rows)}；变更 {sum(bool(row['added']) for row in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
