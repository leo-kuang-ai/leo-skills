"""可执行的内置/用户风格库合同。"""

from __future__ import annotations

import hashlib
import json
import os
import time
import re
from pathlib import Path

from .storage import atomic_write_bytes, sha256_bytes


class StyleStoreError(ValueError):
    reason_code = "style_store_error"


class StyleSelectionChanged(StyleStoreError):
    reason_code = "style_selection_changed"


class StyleSelectionInvalid(StyleStoreError):
    reason_code = "style_selection_invalid"


_NAME = re.compile(r"^[\w\-\u4e00-\u9fff]{1,80}$", re.UNICODE)
_SECRET = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|secret|password|bearer\s+[a-z0-9._-]+)"
)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_JSON_BLOCK = re.compile(r"```json[ \t]*\r?\n(.*?)\r?\n```", re.S)
ASSET_ROLES = {"style", "layout", "axis", "rule", "pool", "reference", "unknown"}


def default_home() -> Path:
    # 只读资产工具不应因未安装配置依赖而无法导入解析器。
    from .config.runtime_config import default_home as configured_home

    return configured_home()


def parse_style_document(text: str) -> dict:
    """只解析，不把可读取 JSON 自动判为可执行风格。"""
    parsed = []
    problems = []
    for block in _JSON_BLOCK.findall(text):
        try:
            parsed.append(json.loads(block))
        except (ValueError, RecursionError):
            problems.append("invalid_json")
    brief = next((item for item in parsed if isinstance(item, dict) and "style_name" in item), None)
    return {"brief": brief, "legacy_parseable": bool(parsed), "problems": problems,
            "first_block_is_brief": bool(brief is not None and parsed and parsed[0] is brief)}


def iter_brief_documents(root: Path):
    """共用 brief 发现口径；发布索引和链接外的内容不进入源集合。"""
    root = Path(root)
    for path in sorted(root.rglob("*.md")):
        if any(part in {"generated", "generated.previous"} or part.startswith(".style-index-") for part in path.relative_to(root).parts) or not path.resolve().is_relative_to(root.resolve()):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        brief = parse_style_document(text)["brief"]
        if brief is not None:
            yield path, text, brief


def _display_field(value, source_field: str, limit: int) -> dict:
    present = isinstance(value, str) and bool(value.strip())
    normalized = " ".join(value.split()) if present else ""
    return {"value": normalized[:limit] if present else None, "source_field": source_field,
            "present": present, "truncated": len(normalized) > limit}


def style_display(brief: dict) -> dict:
    canvas = brief.get("canvas") if isinstance(brief.get("canvas"), dict) else {}
    patterns = brief.get("layout_patterns")
    patterns = patterns if isinstance(patterns, list) else []
    return {
        "suitable_for": _display_field(brief.get("best_for"), "best_for", 120),
        "visual_character": _display_field(brief.get("visual_direction"), "visual_direction", 160),
        "density": _display_field(canvas.get("density"), "canvas.density", 60),
        "layout_hint": [_display_field(value, f"layout_patterns[{i}]", 80) for i, value in enumerate(patterns[:2])],
    }


def validate_style_metadata(brief: dict, schema: dict | None = None) -> list[str]:
    """校验 L0 子集，约束值只从已有 schema 读取。"""
    if schema is None:
        schema = json.loads((Path(__file__).parent / "schemas" / "style-brief-v1.schema.json").read_text())
    errors = []

    def check(value, definition, location):
        types = definition.get("type", [])
        types = [types] if isinstance(types, str) else types
        predicates = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
                      "string": lambda v: isinstance(v, str), "null": lambda v: v is None}
        if types and not any(predicates[kind](value) for kind in types):
            errors.append(f"{location}:type")
            return
        if "enum" in definition and value not in definition["enum"]:
            errors.append(f"{location}:enum")
        if isinstance(value, str):
            if len(value) < definition.get("minLength", 0):
                errors.append(f"{location}:minLength")
            if "pattern" in definition and re.search(definition["pattern"], value) is None:
                errors.append(f"{location}:pattern")
        if isinstance(value, dict):
            properties = definition.get("properties", {})
            for name in definition.get("required", []):
                if name not in value:
                    errors.append(f"{location}.{name}:required")
            for name, item in value.items():
                if name in properties:
                    check(item, properties[name], f"{location}.{name}")
                elif definition.get("additionalProperties") is False:
                    errors.append(f"{location}.{name}:unknown")
        if isinstance(value, list):
            if definition.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
                errors.append(f"{location}:duplicate")
            for i, item in enumerate(value):
                check(item, definition.get("items", {}), f"{location}[{i}]")

    for name in ("source", "taxonomy"):
        if name in brief:
            check(brief[name], schema["properties"][name], name)
    taxonomy = brief.get("taxonomy")
    if isinstance(taxonomy, dict) and "visual_family" in taxonomy:
        families = taxonomy.get("families")
        if not isinstance(families, list) or taxonomy["visual_family"] not in families:
            errors.append("taxonomy.visual_family:not_in_families")
    return errors


def describe_style_asset(path: Path, root: Path, *, scope: str = "builtin", body: bytes | None = None) -> dict:
    """生成可追溯摘要；不回写 authored 字段，也不推断视觉验收通过。"""
    root = Path(root).absolute()
    path = Path(path).absolute()
    rel = path.relative_to(root).as_posix()
    result = {"path": rel, "scope": scope, "name": path.stem, "load_name": path.stem,
              "aliases": [], "asset_role": "unknown", "role_basis": "unclassified",
              "compatibility": {"legacy_callable": False}, "diagnostics": [],
              "coverage": "name-only", "display": style_display({}),
              "verification": {key: {"status": "not-run", "evidence_ref": None, "digest": None}
                               for key in ("schema", "layout", "visual")}}
    if not path.resolve().is_relative_to(root.resolve()):
        result["diagnostics"].append("asset_outside_root")
        return result
    try:
        body = path.read_bytes() if body is None else body
        result["file_sha256"] = sha256_bytes(body)
        if path.suffix not in {".md", ".json"}:
            result.update(asset_role="reference", role_basis="non_document_asset")
            return result
        text = body.decode("utf-8")
    except (OSError, UnicodeError):
        result["diagnostics"].append("asset_unreadable")
        return result
    parsed = parse_style_document(text) if path.suffix == ".md" else {"brief": None, "legacy_parseable": False, "problems": []}
    brief = parsed["brief"] or {}
    result["diagnostics"].extend(parsed["problems"])
    if brief:
        result["diagnostics"].extend(validate_style_metadata(brief))
    if path.suffix == ".json":
        try:
            data = json.loads(text)
        except (ValueError, RecursionError):
            result["diagnostics"].append("invalid_json")
            return result
        entity = data.get("entity") if isinstance(data, dict) else None
        result.update(asset_role="layout" if entity in {"layout", "style-layout-bank"} else "reference",
                      role_basis=f"entity:{entity}" if entity else "json_reference")
        return result
    required = json.loads((Path(__file__).parent / "schemas" / "style-brief-v1.schema.json").read_text())["required"]
    complete = bool(brief) and all(key in brief for key in required) and parsed.get("first_block_is_brief", False)
    if brief and not parsed.get("first_block_is_brief", False):
        result["diagnostics"].append("style_brief_not_first_block")
    declared = brief.get("asset_role")
    pool = bool(re.search(r"^\*\*分类[:：]?\*\*[:：]?.*参考池|^\*\*适用场景[:：]?\*\*[:：]?\s*\n- 整池选用", text, re.M))
    if declared is not None and (not isinstance(declared, str) or declared not in ASSET_ROLES):
        result["diagnostics"].append("asset_role_invalid")
    elif pool and declared not in {None, "pool"}:
        result["diagnostics"].append("asset_role_conflict")
    elif declared:
        result.update(asset_role=declared, role_basis="brief.asset_role")
    elif pool:
        result.update(asset_role="pool", role_basis="explicit_pool_declaration")
    elif complete:
        result.update(asset_role="style", role_basis="complete_brief")
    elif brief:
        result["diagnostics"].append("brief_incomplete")
    elif not parsed["problems"]:
        # 轴/规则按文件自身声明识别；目录名称不承担推荐语义。
        title = text.splitlines()[0] if text.splitlines() else ""
        role = "rule" if re.search(r"规范|规则|原则|纪律", title) else "axis" if re.search(r"版式|论证模式|图片渲染|页面语义|品牌身份", title) else "reference"
        result.update(asset_role=role, role_basis="document_heading" if role != "reference" else "reference_document")
    if isinstance(brief.get("style_name"), str):
        result["name"] = brief["style_name"]
    aliases = brief.get("aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
        result["diagnostics"].append("aliases_invalid")
    else:
        result["aliases"] = list(dict.fromkeys(aliases))
    result["variant_of"] = brief.get("variant_of")
    variants = brief.get("variants", [])
    if not isinstance(variants, list):
        result["diagnostics"].append("variants_invalid")
        variants = []
    result["variants"] = variants
    result["authored_source"] = brief.get("source")
    result["taxonomy"] = brief.get("taxonomy")
    result["display"] = style_display(brief)
    display = result["display"]
    known = sum(display[key]["present"] for key in ("suitable_for", "visual_character", "density"))
    known += bool(display["layout_hint"]) and all(item["present"] for item in display["layout_hint"])
    result["coverage"] = "full" if known == 4 else "partial" if known else "name-only"
    result["style_content_digest"] = sha256_bytes((text.strip() + "\n").encode("utf-8"))
    result["compatibility"]["legacy_callable"] = bool(complete and parsed["legacy_parseable"])
    result["verification"] = {key: {"status": "not-run", "evidence_ref": None, "digest": None}
                              for key in ("schema", "layout", "visual")}
    return result


def style_asset_inventory(root: Path) -> list[dict]:
    root = Path(root).absolute()
    return [describe_style_asset(path, root) for path in sorted(root.rglob("*"))
            if path.is_file() and not any(part in {"generated", "generated.previous"} or part.startswith(".style-index-")
                                          for part in path.relative_to(root).parts)]


def style_reference_problems(entries: list[dict], *, members: dict | None = None) -> list[dict]:
    """名称/变体/成员表的引用检查；共享别名是集合，不是唯一键。"""
    problems = []
    by_name = {}
    for entry in entries:
        if entry.get("compatibility", {}).get("legacy_callable"):
            by_name.setdefault(entry["name"], []).append(entry)
    for name, matches in sorted(by_name.items()):
        if len(matches) > 1:
            problems.append({"code": "duplicate_style_name", "name": name, "paths": [m["path"] for m in matches]})
        for entry in matches:
            parent = entry.get("variant_of")
            if parent:
                parents = by_name.get(parent, []) if isinstance(parent, str) else []
                if len(parents) != 1:
                    problems.append({"code": "variant_parent_missing", "path": entry["path"]})
                elif parent == name or parents[0].get("variant_of"):
                    problems.append({"code": "variant_cycle_or_chain", "path": entry["path"]})
                elif not any(isinstance(v, str) and v.split(":", 1)[0].strip() == name for v in parents[0].get("variants", [])):
                    problems.append({"code": "variant_reverse_missing", "path": entry["path"]})
    for group, names in sorted((members or {}).items()):
        for name in sorted(set(names)):
            if name not in by_name:
                problems.append({"code": "style_member_missing", "group": group, "name": name})
    return problems


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME.fullmatch(name.strip()):
        raise StyleStoreError("style_name_invalid")
    return name.strip()


def _sanitize(content: str) -> str:
    if not isinstance(content, str) or not content.strip():
        raise StyleStoreError("style_content_empty")
    if _SECRET.search(content) or _EMAIL.search(content):
        raise StyleStoreError("style_sensitive_content_forbidden")
    return content.strip() + "\n"


def user_style_path(name: str, *, home: Path | None = None) -> Path:
    return (home or default_home()) / "styles" / f"{_validate_name(name)}.md"


def builtin_style_path(name: str) -> Path:
    return _builtin_styles_dir() / f"{_validate_name(name)}.md"


def _marker_bundle_root() -> Path | None:
    """定位 runtime_manager 安装时写入的技能包根标记。

    托管 venv 把包复制进 site-packages，``parents[3]`` 布局回不到 bundle 根；
    安装器在 runtime 目录（venv 的上级）写 ``bundle_root`` 标记文件，本函数
    从当前文件向上（至多 8 层，覆盖 site-packages→venv→runtime_dir 链）查找。
    """
    for parent in Path(__file__).resolve().parents[:8]:
        marker = parent / "bundle_root"
        try:
            text = marker.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            candidate = Path(text).expanduser()
            if candidate.is_dir():
                return candidate
    return None


def _builtin_styles_dir() -> Path:
    """Locate references/styles in both layouts: the installed launcher exports
    LEO_PPT_BUNDLE (the skill bundle root), while in-repo development falls back
    to the parents[3] relative layout."""
    override = os.environ.get("LEO_PPT_BUNDLE")
    if override and override.strip():
        candidate = Path(override).expanduser() / "references/styles"
        if candidate.is_dir():
            return candidate
    marked = _marker_bundle_root()
    if marked is not None:
        candidate = marked / "references/styles"
        if candidate.is_dir():
            return candidate
    return Path(__file__).resolve().parents[3] / "references/styles"


def _builtin_root() -> Path:
    return builtin_style_path("_placeholder").parent


def _is_style_md(path: Path) -> bool:
    """A style file carries a parseable GPT-Image-2 JSON brief; docs/axes don't.

    The reference library mixes two kinds of markdown: full style briefs
    (which embed a ```json``` block) and axis/rule documents (论证模式、信息图
    类型、图片渲染、版式库 etc., which are prose-only). Only the former are
    loadable styles; this predicate keeps the prose axes out of list_styles.
    A fenced json block that fails json.loads does not count, so a malformed
    or future non-brief format cannot silently appear/disappear from the list.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    for block in re.findall(r"```json\n(.*?)\n```", text, re.S):
        try:
            json.loads(block)
        except json.JSONDecodeError:
            continue
        return True
    return False


def _find_builtin_style(name: str) -> Path:
    """Top-level builtin first, then any subdirectory reference style."""
    top = builtin_style_path(name)
    if top.is_file():
        return top
    for path in sorted(_builtin_root().rglob(f"{_validate_name(name)}.md")):
        if path.is_file() and _is_style_md(path):
            return path
    return top


def save_style(
    name: str,
    content: str,
    *,
    home: Path | None = None,
    overwrite: bool = False,
    rename: str | None = None,
) -> dict:
    target = user_style_path(rename or name, home=home)
    if target.exists() and not overwrite:
        raise StyleStoreError("style_name_conflict")
    body = _sanitize(content).encode("utf-8")
    atomic_write_bytes(target, body)
    return {
        "name": target.stem,
        "source": "user",
        "path": str(target),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def _load_effective_style(name: str, *, home: Path | None = None, enforce_scope: bool = False) -> tuple[dict, bytes]:
    user = user_style_path(name, home=home)
    path = user if user.is_file() else _find_builtin_style(name)
    if not path.is_file():
        raise StyleStoreError("style_not_found")
    scope_root = user.parent if path == user else _builtin_root()
    if enforce_scope and not path.resolve().is_relative_to(scope_root.resolve()):
        raise StyleStoreError("style_outside_scope")
    try:
        try:
            body = path.read_bytes()
        except OSError:
            # 多 worker 并发高峰期的瞬态读失败（fd/资源压力）重试一次；
            # UnicodeError 是确定性损坏，不重试。
            time.sleep(0.05)
            body = path.read_bytes()
        content = body.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeError) as exc:
        raise StyleStoreError("style_unreadable") from exc
    content = _sanitize(content)
    if path == user:
        source = "user"
    elif path.parent == _builtin_root():
        source = "builtin"
    else:
        source = "reference"
    return {
        "name": path.stem,
        "source": source,
        "path": str(path),
        "content": content,
        "sha256": sha256_bytes(content.encode("utf-8")),
    }, body


def load_style(name: str, *, home: Path | None = None, enforce_scope: bool = False) -> dict:
    return _load_effective_style(name, home=home, enforce_scope=enforce_scope)[0]


def selection_fingerprint(loaded: dict, *, home: Path | None = None) -> str:
    scope = "user" if loaded["source"] == "user" else "builtin"
    root = (home or default_home()) / "styles" if scope == "user" else _builtin_root()
    path = Path(loaded["path"]).resolve()
    try:
        relative = path.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise StyleStoreError("style_outside_scope") from exc
    identity = {"scope": scope, "path": relative, "name": loaded["name"], "content": loaded["sha256"]}
    return sha256_bytes(json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def style_summary(name: str, *, home: Path | None = None) -> dict:
    home = Path(home or default_home()).resolve()
    loaded, body = _load_effective_style(name, home=home, enforce_scope=True)
    scope = "user" if loaded["source"] == "user" else "builtin"
    root = home / "styles" if scope == "user" else _builtin_root()
    result = describe_style_asset(Path(loaded["path"]), root, scope=scope, body=body)
    result.update(kind="style-summary", schema_version=1, source=loaded["source"],
                  style_content_digest=loaded["sha256"], selection_fingerprint=selection_fingerprint(loaded, home=home))
    if len(json.dumps(result, ensure_ascii=False).encode()) > 12 * 1024:
        raise StyleStoreError("style_summary_too_large")
    return result


def list_style_summaries(*, home: Path | None = None, needle: str = "", limit: int = 20, offset: int = 0) -> dict:
    if isinstance(limit, bool) or not 1 <= limit <= 40 or offset < 0:
        raise StyleStoreError("style_summary_pagination_invalid")
    home = Path(home or default_home()).resolve()
    needle = needle.strip().casefold()
    items = []
    problems = []
    # 与旧 list 相同的名称覆盖顺序；候选摘要读取实际文件，不使用 generated。
    for entry in sorted(list_styles(home=home), key=lambda e: e["name"]):
        try:
            summary = style_summary(entry["name"], home=home)
        except StyleStoreError:
            problems.append({"name": entry["name"], "reason_code": "style_summary_unavailable"})
            continue
        explicit_names = {summary["name"].strip().casefold(), summary["load_name"].casefold(),
                          *(alias.strip().casefold() for alias in summary["aliases"])}
        if summary["asset_role"] != "style" and not (needle and needle in explicit_names):
            continue
        if needle and needle not in summary["name"].casefold() and not any(needle in a.casefold() for a in summary["aliases"]):
            continue
        items.append(summary)
    match_kind = "browse"
    if needle:
        exact_names = [item for item in items if item["name"].strip().casefold() == needle]
        exact_aliases = [item for item in items if needle in {alias.strip().casefold() for alias in item["aliases"]}]
        if exact_names:
            items, match_kind = exact_names, "exact-name"
        elif exact_aliases:
            items, match_kind = exact_aliases, "exact-alias"
        else:
            match_kind = "partial" if items else "none"
    return {"kind": "style-summary-list", "schema_version": 1, "total": len(items),
            "match_kind": match_kind,
            "items": items[offset:offset + limit], "offset": offset,
            "next_offset": offset + limit if offset + limit < len(items) else None, "problems": problems}


def list_styles(*, home: Path | None = None) -> list[dict]:
    builtin_root = _builtin_root()
    names: dict[str, dict] = {}
    # Top-level builtins take precedence over same-named reference styles.
    for path in sorted(builtin_root.glob("*.md")):
        if not _is_style_md(path):
            continue
        names[path.stem] = {"name": path.stem, "source": "builtin", "path": str(path)}
    # Subdirectory reference styles; skip prose axis documents via _is_style_md.
    for path in sorted(builtin_root.rglob("*.md")):
        if path.parent == builtin_root:
            continue
        if not _is_style_md(path):
            continue
        if path.stem in names:
            continue
        names[path.stem] = {"name": path.stem, "source": "reference", "path": str(path)}
    user_root = (home or default_home()) / "styles"
    for path in sorted(user_root.glob("*.md")) if user_root.is_dir() else []:
        names[path.stem] = {"name": path.stem, "source": "user", "path": str(path)}
    return list(names.values())
