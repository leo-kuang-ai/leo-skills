"""可执行的内置/用户风格库合同（v2：template-library 新协议，KTD6）。

旧 MD 内嵌 JSON 树已退役（U1 账本 + reference/sources/retired-styles-tree
归档）。本模块是语义入口：身份/路径/依赖解析全部委托 asset_resolver，
不自行扫描目录。用户库为 ${LEO_PPT_HOME}/template-library/。
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from .asset_resolver import AssetResolver, ResolverError, revision_of
from .storage import atomic_write_bytes, sha256_bytes


class StyleStoreError(ValueError):
    reason_code = "style_store_error"


class StyleSelectionChanged(StyleStoreError):
    reason_code = "style_selection_changed"


class StyleSelectionInvalid(StyleStoreError):
    reason_code = "style_selection_invalid"


class StyleNotFound(StyleStoreError):
    reason_code = "style_not_found"


class StyleCatalogStale(StyleStoreError):
    """Catalog evidence is stale; never present a partial ready list."""

    reason_code = "stale_catalog"


class StyleCatalogIncomplete(StyleStoreError):
    """A catalog entity cannot be materialized; never return a partial list."""

    reason_code = "style_catalog_incomplete"


_NAME = re.compile(r"^[\w\-\u4e00-\u9fff]{1,80}$", re.UNICODE)
_SECRET = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|secret|password|bearer\s+[a-z0-9._-]+)"
)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_JSON_BLOCK = re.compile(r"```json[ \t]*\r?\n(.*?)\r?\n```", re.S)
ASSET_ROLES = {"style", "layout", "axis", "rule", "pool", "reference", "unknown"}


def default_home() -> Path:
    from .config.runtime_config import default_home as configured_home

    return configured_home()


# --------------------------------------------------------------------------- #
# 旧合同解析工具（迁移/审计工具与历史 fixture 消费；不再用于活动加载）
# --------------------------------------------------------------------------- #

def parse_style_document(text: str) -> dict:
    """旧 MD 合同解析：供迁移与历史审计使用，活动加载不走此函数。"""
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
    """旧树 brief 发现（仅迁移工具使用；旧树已归档时产出为空）。"""
    root = Path(root)
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.md")):
        if any(part in {"generated", "generated.previous"} or part.startswith(".style-index-") for part in path.relative_to(root).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        brief = parse_style_document(text)["brief"]
        if brief is not None:
            yield path, text, brief


# --------------------------------------------------------------------------- #
# 新协议：list / load / save / summary
# --------------------------------------------------------------------------- #

def _resolver(home: Path | None = None) -> AssetResolver:
    try:
        return AssetResolver(home=home)
    except ResolverError as exc:
        raise StyleStoreError(f"style_library_missing: {exc}") from exc


def list_styles(*, home: Path | None = None) -> list[dict]:
    """新协议枚举：用户同名覆盖内置；来源按 origin_scope。"""
    return list_styles_with_source(home=home)["styles"]


def list_styles_with_source(*, home: Path | None = None) -> dict:
    """用同一个 resolver 快照返回列表和来源，空列表也保留来源。"""
    resolver = _resolver(home)
    by_name: dict[str, dict] = {}
    try:
        entities = resolver.entities
    except ResolverError as exc:
        if getattr(exc, "reason_code", "") == "stale_catalog":
            raise StyleCatalogStale(str(exc)) from exc
        raise StyleStoreError(f"style_library_unavailable: {exc}") from exc
    for entity in entities:  # user 覆盖已在 resolver 内生效
        if entity["kind"] != "style":
            continue
        by_name[entity["name"]] = {
            "name": entity["name"],
            "aliases": list(entity.get("aliases") or []),
            "source": entity["origin_scope"],
            "path": str(Path(entity["trusted_root"]) / entity["path"]),
            "registry_source": resolver.registry_source,
        }
    return {"styles": [by_name[name] for name in sorted(by_name)],
            "registry_source": resolver.registry_source}


def load_style(name: str, *, home: Path | None = None, enforce_scope: bool = False) -> dict:
    """按名称/别名/完整 ID 加载风格；返回新协议 content（含 brief 与 legacy_payload）。"""
    resolver = _resolver(home)
    try:
        resolved = resolver.require(name, kind="style")
    except ResolverError as exc:
        if getattr(exc, "reason_code", "") == "stale_catalog":
            raise StyleCatalogStale(str(exc)) from exc
        raise StyleNotFound(f"style_not_found: {name} ({exc.reason_code})") from exc
    brief = resolved["data"]
    # 兼容旧 content 消费者：重建旧形状 brief（legacy_payload 优先）。
    legacy = brief.get("legacy_payload") or {}
    compat_brief = {"style_name": brief.get("name") or resolved["name"], **legacy}
    document = {
        "name": brief.get("name") or resolved["name"],
        "source": resolved["origin_scope"],
        "path": resolved["path"],
        "content": json.dumps(compat_brief, ensure_ascii=False),
        "brief": brief,
        "asset_id": resolved["asset_id"],
        "revision": resolved["revision"],
        "lifecycle": resolved["lifecycle"],
        "sha256": sha256_bytes(json.dumps(brief, ensure_ascii=False, sort_keys=True).encode("utf-8")),
    }
    return document


def selection_fingerprint(loaded: dict, *, home: Path | None = None) -> str:
    identity = {"scope": loaded["source"], "asset_id": loaded.get("asset_id"),
                "name": loaded["name"], "revision": loaded.get("revision") or loaded["sha256"]}
    return sha256_bytes(json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


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


def user_style_dir(*, home: Path | None = None) -> Path:
    return (home or default_home()) / "template-library" / "canonical" / "styles"


def _ensure_user_library(home: Path) -> None:
    """确保用户库声明存在（resolver 只认 template-library/library.json）。

    首次 save_style 时创建最小 user 声明；已存在则不动（用户可自定义 zones
    描述）。缺声明时用户 overlay 对 resolver 完全不可见——那会让「保存成功
    但加载回落内置」静默发生，违反用户同名覆盖合同。
    """
    library = home / "template-library"
    declaration = library / "library.json"
    if declaration.is_file():
        return
    library.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "kind": "template-library",
        "library_id": "user",
        "name": "用户模板库",
        "protocol": {"resolver": "asset_resolver/v1"},
        "zones": {"canonical": "作者真值", "reference": "参考", "governance": "治理",
                  "catalog": "自动生成", "evidence": "验证"},
        "reserved_directory_names": ["generated", "generations", "staging", "revocations"],
        "note": "由 save_style 首次保存时自动创建；用户风格保存在 canonical/styles/。",
    }
    atomic_write_bytes(declaration, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")


def user_style_path(name: str, *, home: Path | None = None) -> Path:
    """新协议用户风格路径：${LEO_PPT_HOME}/template-library/canonical/styles/<slug>/brief.json。"""
    slug = _slugify(_validate_name(name))
    return user_style_dir(home=home) / slug / "brief.json"


def _slugify(name: str) -> str:
    return re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", name.strip()).strip("-")


def save_style(
    name: str,
    content: str,
    *,
    home: Path | None = None,
    overwrite: bool = False,
    rename: str | None = None,
) -> dict:
    """保存用户风格：接受含 ```json brief 的内容（旧输入离线转换语义）或纯 JSON。"""
    home = home or default_home()
    _ensure_user_library(home)
    target = user_style_path(rename or name, home=home)
    if target.exists() and not overwrite:
        raise StyleStoreError("style_name_conflict")
    body = _sanitize(content)
    parsed = parse_style_document(body)
    brief = parsed["brief"]
    if brief is None:
        try:
            brief = json.loads(body)
        except ValueError as exc:
            raise StyleStoreError("style_content_not_brief") from exc
    brief_name = _validate_name(str(brief.get("style_name") or (rename or name)))
    slug = _slugify(brief_name)
    document = {
        "schema_version": 2,
        "entity": "style-brief",
        "asset_id": f"user:style:{slug}",
        "name": brief_name,
        "aliases": brief.get("aliases") or [],
        "variant_of": None,
        "lifecycle": "draft",
        "source": {"origin": "user-imported"},
        "taxonomy": {"families": ["未分类"]},
        "visual_language": {"direction": (str(brief.get("visual_direction") or "imported-style-pending-review")[:400])},
        "bindings": {},
        "adaptation_gaps": ["theme_not_extracted", "user_import_pending_review"],
        "content_review": {"reviewed": False, "disposition": "draft"},
        "legacy_payload": {k: v for k, v in brief.items() if k not in {"style_name", "type"}},
    }
    payload = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
    atomic_write_bytes(target, payload)
    return {
        "name": brief_name,
        "source": "user",
        "path": str(target),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "asset_id": document["asset_id"],
    }


def style_display(brief: dict) -> dict:
    def field(value, source: str, limit: int) -> dict:
        present = isinstance(value, str) and bool(value.strip())
        normalized = " ".join(value.split()) if present else ""
        return {"value": normalized[:limit] if present else None, "source_field": source,
                "present": present, "truncated": len(normalized) > limit}

    features = (brief.get("visual_language") or {})
    legacy = brief.get("legacy_payload") or {}
    recommendation = brief.get("recommendation_features") or {}
    return {
        "suitable_for": field(" ".join((brief.get("taxonomy") or {}).get("scenarios") or [])
                              or legacy.get("best_for"), "scenarios|best_for", 120),
        "visual_character": field(features.get("direction") or legacy.get("visual_direction"),
                                  "visual_language.direction", 160),
        "density": field(recommendation.get("density") or (legacy.get("canvas") or {}).get("density"),
                         "recommendation_features.density", 60),
        "lifecycle": brief.get("lifecycle"),
        "adaptation_gaps": brief.get("adaptation_gaps", []),
    }


def style_summary(name: str, *, home: Path | None = None) -> dict:
    loaded = load_style(name, home=home, enforce_scope=True)
    brief = loaded["brief"]
    result = {
        "kind": "style-summary", "schema_version": 2,
        "name": loaded["name"], "asset_id": loaded["asset_id"],
        "source": loaded["source"], "lifecycle": loaded["lifecycle"],
        "aliases": brief.get("aliases") or [],
        "path": loaded["path"], "revision": loaded["revision"],
        "display": style_display(brief),
        "compatibility": {"legacy_callable": loaded["lifecycle"] in {"active", "draft"}},
        "verification": {key: {"status": "not-run", "evidence_ref": None, "digest": None}
                         for key in ("schema", "layout", "visual")},
        "selection_fingerprint": selection_fingerprint(loaded, home=home),
    }
    if len(json.dumps(result, ensure_ascii=False).encode()) > 12 * 1024:
        raise StyleStoreError("style_summary_too_large")
    return result


def list_style_summaries(*, home: Path | None = None, needle: str = "", limit: int = 20, offset: int = 0) -> dict:
    if isinstance(limit, bool) or not 1 <= limit <= 40 or offset < 0:
        raise StyleStoreError("style_summary_pagination_invalid")
    needle = needle.strip().casefold()
    items = []
    problems = []
    listing = list_styles_with_source(home=home)
    entries = listing["styles"]
    for entry in entries:
        try:
            summary = style_summary(entry["name"], home=home)
        except StyleStoreError as exc:
            detail = str(exc)
            nested_reason = "stale_catalog" if "stale_catalog" in detail else None
            if nested_reason:
                raise StyleCatalogStale(detail) from exc
            problems.append({
                "name": entry["name"],
                "reason_code": nested_reason or getattr(exc, "reason_code", "style_summary_unavailable"),
            })
            continue
        names = {summary["name"].strip().casefold(),
                 *(alias.strip().casefold() for alias in summary["aliases"])}
        if needle and needle not in names:
            continue
        items.append(summary)
    if problems:
        details = "; ".join(
            f"{problem['name']}:{problem['reason_code']}"
            for problem in problems
        )
        raise StyleCatalogIncomplete(
            "style_catalog_incomplete: " + details
        )
    registry_source = listing["registry_source"]
    match_kind = "browse"
    if needle:
        exact = [item for item in items if item["name"].strip().casefold() == needle]
        exact_alias = [item for item in items if needle in
                       {alias.strip().casefold() for alias in item["aliases"]}]
        if exact:
            items, match_kind = exact, "exact-name"
        elif exact_alias:
            items, match_kind = exact_alias, "exact-alias"
        else:
            match_kind = "partial" if items else "none"
    return {"kind": "style-summary-list", "schema_version": 2, "total": len(items),
            "match_kind": match_kind,
            "items": items[offset:offset + limit], "offset": offset,
            "next_offset": offset + limit if offset + limit < len(items) else None,
            "registry_source": registry_source,
            "problems": problems}


# --------------------------------------------------------------------------- #
# 旧合同审计函数（迁移/账本工具消费；新协议加载不走此面）
# --------------------------------------------------------------------------- #

def validate_style_metadata(brief: dict, schema: dict | None = None) -> list[str]:
    """旧 v1 可选元数据（source/taxonomy）子集校验。

    消费面：lint_style_briefs / style_pack / 迁移对账工具（旧树退役前仍在
    服务）；新协议 v2 brief 的治理校验由 template-library/governance 的
    style-brief-v2 schema 拥有，不走此函数。
    """
    if schema is None:
        schema = json.loads((Path(__file__).parent / "schemas" / "style-brief-v1.schema.json").read_text())
    errors: list[str] = []

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

    if not isinstance(brief, dict):
        return ["brief_not_object"]
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
    """旧树资产摘要（冻结脚本/审计工具消费；对归档树运行）。"""
    root = Path(root).absolute()
    path = Path(path).absolute()
    rel = path.relative_to(root).as_posix()
    result = {"path": rel, "scope": scope, "name": path.stem, "load_name": path.stem,
              "aliases": [], "asset_role": "unknown", "role_basis": "retired-tree",
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
    except OSError:
        result["diagnostics"].append("asset_unreadable")
        return result
    return result


def style_asset_inventory(root: Path) -> list[dict]:
    root = Path(root).absolute()
    if not root.is_dir():
        return []
    return [describe_style_asset(path, root) for path in sorted(root.rglob("*"))
            if path.is_file() and not any(part in {"generated", "generated.previous"}
                                          or part.startswith(".style-index-")
                                          for part in path.relative_to(root).parts)]


def style_reference_problems(entries: list[dict], *, members: dict | None = None) -> list[dict]:
    """旧名称/变体检查（归档对账用）。"""
    problems: list[dict] = []
    by_name: dict[str, list[dict]] = {}
    for entry in entries:
        if entry.get("compatibility", {}).get("legacy_callable"):
            by_name.setdefault(entry["name"], []).append(entry)
    for name, matches in sorted(by_name.items()):
        if len(matches) > 1:
            problems.append({"code": "duplicate_style_name", "name": name,
                             "paths": [m["path"] for m in matches]})
    return problems
