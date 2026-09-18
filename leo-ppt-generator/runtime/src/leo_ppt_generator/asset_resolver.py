"""asset_resolver/v1：模板库统一身份、路径、scope、依赖与修订解析（KTD6）。

唯一方案 docs/plans/2026-09-08-001 §5–§6。职责边界：
  - 只做身份/路径/scope/依赖/revision 解析；
  - 不推荐风格、不决定行业规则、不持久化任务、不写安装目录。

根定位：LEO_PPT_BUNDLE → bundle_root 标记 → 仓内 parents 布局；只认
template-library/library.json。路径必须在显式可信根内：拒绝 traversal、
符号链接越界、类型错误与用户 manifest 冒充 builtin。

catalog 读取：catalog/current.json 一次读入并固定 generation（不逐文件重读
current）；current 缺失时可从 canonical 只读重建内存视图（execute 缺索引路径，
不改安装目录）。用户 overlay 本地合并，不回写内置 catalog。
"""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
from functools import wraps
import hashlib
import json
import os
import re
from pathlib import Path

ASSET_ID_RE = re.compile(
    r"^(?P<scope>builtin|user):(?P<kind>style|theme|layout|template|recipe|component|axis|brand|preset|font|ornament):(?P<slug>[A-Za-z0-9\-\u4e00-\u9fff]+)$")
KIND_ENTITY_FILE = {
    "style": "brief.json",
    "theme": "theme.json",
    "layout": "layout.json",
    "template": "template.json",
    "recipe": "recipe.json",
    "brand": "brand.json",
    "preset": "preset.json",
    "font": "manifest.json",
    "ornament": "manifest.json",
    "axis": "manifest.json",
    "component": "component.json",
}
# canonical/<目录> 与 kind 的对应；qa-profile 属治理区规则。
KIND_CANONICAL_DIR = {
    "style": "styles", "theme": "themes", "layout": "layouts",
    "template": "templates", "component": "components", "axis": "axes",
    "recipe": "executable/recipes",
    "brand": "brands", "preset": "presets", "font": "fonts", "ornament": "ornaments",
}


class ResolverError(ValueError):
    """稳定 reason code；CLI 层负责中文说明。"""

    reason_code = "resolver_error"


class LibraryMissingError(ResolverError):
    reason_code = "library_missing"


class AssetNotFoundError(ResolverError):
    reason_code = "asset_not_found"


class AmbiguousNameError(ResolverError):
    reason_code = "ambiguous_name"


class DuplicateIdError(ResolverError):
    reason_code = "duplicate_id"


class DependencyMissingError(ResolverError):
    reason_code = "dependency_missing"


class ScopeViolationError(ResolverError):
    reason_code = "scope_violation"


class StaleCatalogError(ResolverError):
    reason_code = "stale_catalog"


class UnsupportedSchemaError(ResolverError):
    reason_code = "unsupported_schema"


def revision_of(data) -> str:
    """内容修订：规范 JSON 前 16 hex。"""
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# 库根定位
# --------------------------------------------------------------------------- #

def _marker_bundle_root() -> Path | None:
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


def _candidate_bundle_roots() -> list[Path]:
    roots: list[Path] = []
    override = os.environ.get("LEO_PPT_BUNDLE")
    if override and override.strip():
        roots.append(Path(override).expanduser())
    marked = _marker_bundle_root()
    if marked is not None:
        roots.append(marked)
    roots.append(Path(__file__).resolve().parents[3])
    return roots


def builtin_library_root() -> Path:
    """返回内置模板库根（含 template-library/library.json 的 bundle 根下的库目录）。

    只认新库声明文件；找不到即 LibraryMissingError，不回退旧 references/styles 树。
    """
    for bundle_root in _candidate_bundle_roots():
        library = bundle_root / "template-library"
        if (library / "library.json").is_file():
            return library
    raise LibraryMissingError("library_missing: 未找到 template-library/library.json")


def user_library_root(home: Path | None = None) -> Path | None:
    # Standalone tooling may provide an explicit home without installing the
    # optional runtime-config dependencies.  Only the default-home path needs
    # to import runtime configuration.
    if home is None:
        from .config.runtime_config import default_home
        home = default_home()
    root = home / "template-library"
    return root if (root / "library.json").is_file() else None


def _validate_library_declaration(library: Path) -> dict:
    try:
        declaration = json.loads((library / "library.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LibraryMissingError(f"library_missing: library.json 不可读 ({library})") from exc
    if declaration.get("kind") != "template-library":
        raise LibraryMissingError("library_missing: library.json kind 不符")
    return declaration


# --------------------------------------------------------------------------- #
# registry 加载（current 指针固定 generation；缺失时 canonical 只读重建）
# --------------------------------------------------------------------------- #

def _load_registry_from_catalog(library: Path) -> dict | None:
    pointer_path = library / "catalog" / "current.json"
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    generation = pointer.get("generation")
    if not isinstance(generation, str):
        raise StaleCatalogError("stale_catalog: current.json 缺 generation")
    generations_root = (library / "catalog" / "generations").resolve()
    generation_path = Path(generation)
    if (not generation.strip() or generation_path.is_absolute()
            or any(part in {"", ".", ".."} for part in generation_path.parts)):
        raise StaleCatalogError("stale_catalog: generation 路径非法")
    registry_path = (generations_root / generation_path / "registry.json").resolve()
    if not registry_path.is_relative_to(generations_root):
        raise StaleCatalogError("stale_catalog: generation 越出 generations 目录")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StaleCatalogError(
            f"stale_catalog: generation {generation} registry 不可读") from exc
    if registry.get("generation") != generation:
        raise StaleCatalogError("stale_catalog: registry generation 与指针不一致")
    entities = registry.get("entities")
    if not isinstance(entities, list) or any(not isinstance(entity, dict) for entity in entities):
        raise StaleCatalogError("stale_catalog: registry entities 结构非法")
    return registry


def _scan_canonical(library: Path) -> list[dict]:
    """从 canonical 只读重建实体视图（缺索引路径；不写安装目录）。"""
    entities: list[dict] = []
    canonical = library / "canonical"
    if not canonical.is_dir():
        return entities
    for kind, dirname in sorted(KIND_CANONICAL_DIR.items()):
        base = canonical / dirname
        if not base.is_dir():
            continue
        entity_file = KIND_ENTITY_FILE[kind]
        # Axis entities are grouped by axis family before the entity slug.
        pattern = f"*/*/{entity_file}" if kind == "axis" else f"*/{entity_file}"
        for manifest_path in sorted(base.glob(pattern)):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            asset_id = data.get("asset_id")
            if not isinstance(asset_id, str):
                continue
            entities.append({
                "asset_id": asset_id,
                "kind": kind,
                "path": manifest_path.relative_to(library).as_posix(),
                "revision": revision_of(data),
                "name": data.get("name") or asset_id.rsplit(":", 1)[-1],
                "aliases": data.get("aliases", []) if isinstance(data.get("aliases"), list) else [],
                "lifecycle": data.get("lifecycle", "draft"),
                "dependencies": _declared_dependencies(data),
            })
    return entities


def _declared_dependencies(data: dict) -> list[str]:
    deps: set[str] = set()
    for key in ("dependencies", "layout_profiles"):
        value = data.get(key)
        if isinstance(value, list):
            deps.update(item for item in value if isinstance(item, str))
    bindings = data.get("bindings")
    if isinstance(bindings, dict):
        theme = bindings.get("theme_default")
        if isinstance(theme, str):
            deps.add(theme)
        routes = bindings.get("layout_routes")
        if isinstance(routes, list):
            for route in routes:
                if isinstance(route, dict):
                    for key in ("preferred", "discouraged"):
                        values = route.get(key)
                        if isinstance(values, list):
                            deps.update(v for v in values if isinstance(v, str))

    ornaments = data.get("ornaments")
    if isinstance(ornaments, list):
        deps.update(v for v in ornaments if isinstance(v, str))
    return sorted(deps)


def _library_read(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.library_session():
            return method(self, *args, **kwargs)
    return guarded


class AssetResolver:
    """统一 resolver：一次绑定库根集合（builtin + 可选 user overlay）。"""

    def __init__(self, *, home: Path | None = None, library: Path | None = None, context=None):
        from .template_catalog import LibraryContext
        if context is not None and (not isinstance(context, LibraryContext) or library is not None or home is not None):
            raise ResolverError("library_context_invalid")
        self.builtin_root = (context.root if context else Path(library) if library is not None else builtin_library_root()).absolute()
        from .library_migration import require_available
        require_available(self.builtin_root)
        if not self.builtin_root.is_dir():
            raise LibraryMissingError("library_missing: 库目录不存在")
        from .library_migration import library_operation
        with library_operation(self.builtin_root):
            declaration = _validate_library_declaration(self.builtin_root)
            if context is None and declaration.get("schema_version") == 2:
                context = LibraryContext(self.builtin_root, user_root=user_library_root(home))
            self.context = context
            self.execution_allowed = context is None or context.mode == "execution"
            self.user_root = context.user_root if context else user_library_root(home)
            if self.user_root is not None:
                self.user_root = Path(self.user_root).absolute()
            self._require_available()
            self._entities: list[dict] | None = None
            self._by_id: dict[str, dict] | None = None
            self._registry_source: str | None = None
            self._generation: str | None = None

    # -- 实体索引 ---------------------------------------------------------- #

    @contextmanager
    def library_session(self):
        """固定一次完整操作涉及的库根，包含用户库与任务内可信根。"""
        from .library_migration import library_operation
        roots = {self.builtin_root, self.user_root}
        roots.update(row["trusted_root"] for row in (self._entities or []))
        with ExitStack() as stack:
            for root in sorted({Path(root).absolute() for root in roots if root is not None}):
                stack.enter_context(library_operation(root))
            yield

    def _require_available(self) -> None:
        from .library_migration import require_available
        require_available(self.builtin_root)
        if self.user_root is not None:
            require_available(self.user_root)

    @property
    @_library_read
    def entities(self) -> list[dict]:
        self._require_available()
        if self._entities is None:
            self._load()
        return list(self._entities)

    @_library_read
    def _load(self) -> None:
        self._require_available()
        if self.context is not None:
            from .template_catalog import LibraryContext, read_catalog
            registry = read_catalog(self.context)
            combined = [{**row, "origin_scope": "builtin", "trusted_root": str(self.builtin_root)} for row in registry["entities"]]
            if self.user_root is not None:
                user = read_catalog(LibraryContext(self.user_root, mode=self.context.mode))
                combined.extend({**row, "origin_scope": "user", "trusted_root": str(self.user_root)} for row in user["entities"])
            for row in combined:
                if row["asset_id"].split(":")[0] != row["origin_scope"]:
                    raise ScopeViolationError("scope_violation: catalog scope 不符")
            if len({row["asset_id"] for row in combined}) != len(combined):
                raise DuplicateIdError("duplicate_id")
            self._entities = combined
            self._by_id = {row["asset_id"]: row for row in combined}
            self._generation = registry["catalog_generation"]
            self._registry_source = "diagnostic" if registry.get("diagnostic") else "catalog"
            return
        builtin_registry = _load_registry_from_catalog(self.builtin_root)
        self._generation = (builtin_registry or {}).get("generation")
        combined: list[dict] = []
        seen_ids: dict[str, dict] = {}
        for scope_root, scope in ((self.builtin_root, "builtin"), (self.user_root, "user")):
            if scope_root is None:
                continue
            if scope == "builtin" and builtin_registry is not None:
                entities = [
                    {**entity, "origin_scope": "builtin",
                     "trusted_root": str(self.builtin_root)}
                    for entity in builtin_registry.get("entities", [])]
                self._registry_source = "catalog"
            else:
                entities = [
                    {**entity, "origin_scope": scope, "trusted_root": str(scope_root)}
                    for entity in _scan_canonical(scope_root)]
                if self._registry_source is None:
                    self._registry_source = "canonical-rebuild"
            for entity in entities:
                asset_id = entity["asset_id"]
                declared_scope = asset_id.split(":", 1)[0]
                if declared_scope != scope:
                    # 用户 manifest 冒充 builtin / 内置冒充 user 均拒绝。
                    raise ScopeViolationError(
                        f"scope_violation: {asset_id} 声明 {declared_scope}，实际根为 {scope}")
                if asset_id in seen_ids:
                    other = seen_ids[asset_id]
                    # 用户覆盖内置：有效身份为 (origin_scope, asset_id)，
                    # 同一库根内重复才是 duplicate_id。
                    if other["origin_scope"] == scope:
                        raise DuplicateIdError(f"duplicate_id: {asset_id}")
                    continue  # user 覆盖生效，builtin 同 ID 条目让位
                seen_ids[asset_id] = entity
                combined.append(entity)
        self._entities = combined
        self._by_id = {entity["asset_id"]: entity for entity in combined}

    def reload(self) -> None:
        self._entities = None
        self._by_id = None
        self._registry_source = None
        self._generation = None

    @property
    @_library_read
    def generation(self) -> str | None:
        self._require_available()
        if self._entities is None:
            self._load()
        return self._generation

    @_library_read
    def fingerprint(self, asset_id: str) -> dict:
        """固定实际消费字节；模板除 manifest 外还覆盖整个同目录资源。"""
        entity = self.resolve(asset_id)
        root = Path(entity["trusted_root"]).resolve()
        manifest = Path(entity["path"])
        files = [manifest]
        if entity["kind"] in {"template", "font"}:
            files = sorted(manifest.parent.rglob("*"))
            if entity["data"].get("lane") == "render:html" and not manifest.with_name("page.html").is_file():
                raise AssetNotFoundError(f"asset_not_found: {asset_id} 缺 page.html")
        hashes = {}
        for path in files:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ScopeViolationError(f"scope_violation: {asset_id} 资源路径非法")
            if path.is_dir():
                continue
            if not path.is_file():
                raise AssetNotFoundError(f"asset_not_found: {asset_id} 资源不可读")
            hashes[path.relative_to(Path(entity["trusted_root"])).as_posix()] = sha256_file(path)
        return {"asset_id": asset_id, "origin_scope": entity["origin_scope"],
                "revision": entity["revision"], "files": hashes}

    @classmethod
    def from_snapshot(cls, snapshot: Path) -> "AssetResolver":
        """仅使用 run 的固定资产；缺失快照绝不回退安装库或用户活动库。"""
        marker = Path(snapshot) / "asset-snapshot.json"
        if marker.exists() or marker.is_symlink():
            from .qualification import read_evidence_bytes, digest
            from .template_catalog import LibraryContext
            body = json.loads(read_evidence_bytes(snapshot, "asset-snapshot.json"))
            if (set(body) != {"schema_version", "kind", "catalog_generation", "scopes", "pins", "snapshot_digest"}
                    or body["schema_version"] != 2 or body["kind"] != "asset-snapshot"
                    or body["snapshot_digest"] != digest({k: v for k, v in body.items() if k != "snapshot_digest"})):
                raise StaleCatalogError("asset_snapshot_schema_mismatch")
            frozen = cls(context=LibraryContext(Path(snapshot) / "builtin"))
            entities = []
            for scope, records in body["scopes"].items():
                if scope not in {"builtin", "user"}:
                    raise ScopeViolationError("scope_violation: snapshot scope")
                root = Path(snapshot) / ("builtin" if scope == "builtin" else "user/template-library")
                for row in records:
                    if row["asset_id"].split(":")[0] != scope:
                        raise ScopeViolationError("scope_violation: snapshot identity")
                    entities.append({**row, "trusted_root": str(root), "origin_scope": scope})
            if len({row["asset_id"] for row in entities}) != len(entities):
                raise DuplicateIdError("duplicate_id: snapshot")
            frozen._entities = entities
            frozen._by_id = {row["asset_id"]: row for row in entities}
            frozen._generation = body["catalog_generation"]
            frozen._registry_source = "catalog"
            if {row["asset_id"] for row in entities} != {pin["asset_id"] for pin in body["pins"]}:
                raise StaleCatalogError("asset_snapshot_pin_set_mismatch")
            for pin in body["pins"]:
                if frozen.fingerprint(pin["asset_id"]) != pin:
                    raise StaleCatalogError("asset_snapshot_pin_mismatch")
            return frozen
        return cls(library=Path(snapshot) / "builtin", home=Path(snapshot) / "user")

    @_library_read
    def freeze_assets(self, snapshot: Path, pins: list[dict]) -> "AssetResolver":
        """原子写入选中资产字节。已有快照只校验，不能静默覆盖。"""
        self._require_available()
        if not self.execution_allowed:
            raise ResolverError("diagnostic_resolver_not_executable")
        import shutil
        import tempfile

        snapshot = Path(snapshot)
        by_id = {}
        for pin in pins:
            identity = pin["asset_id"]
            if identity in by_id and by_id[identity] != pin:
                raise StaleCatalogError(f"stale_catalog: 绑定资产冲突 {identity}")
            by_id[identity] = pin
        if not by_id:
            raise StaleCatalogError("stale_catalog: 不能冻结空资产集")

        def checked(root):
            frozen = self.from_snapshot(root)
            for identity, pin in by_id.items():
                if frozen.fingerprint(identity) != pin:
                    raise StaleCatalogError(f"stale_catalog: 快照不匹配 {identity}")
            return frozen

        if snapshot.is_symlink():
            raise ScopeViolationError("scope_violation: 快照不能是符号链接")
        if snapshot.exists():
            return checked(snapshot)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".asset-snapshot-", dir=snapshot.parent))
        try:
            scope_entities = {"builtin": [], "user": []}
            for identity, pin in sorted(by_id.items()):
                if self.fingerprint(identity) != pin:
                    raise StaleCatalogError(f"stale_catalog: 冻结前资产漂移 {identity}")
                entity = self.resolve(identity)
                scope = entity["origin_scope"]
                destination = stage / ("builtin" if scope == "builtin" else "user/template-library")
                source_root = Path(entity["trusted_root"])
                for relative, expected in pin["files"].items():
                    source = source_root / relative
                    if source.is_symlink() or not source.resolve().is_relative_to(source_root.resolve()):
                        raise ScopeViolationError("scope_violation: 冻结源路径非法")
                    raw = source.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != expected:
                        raise StaleCatalogError(f"stale_catalog: 复制时资产漂移 {identity}")
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                scope_entities[scope].append({
                    **self._by_id[identity], "path": entity["relative_path"],
                    "revision": entity["revision"],
                })
            for scope, entities in scope_entities.items():
                if not entities and scope == "user":
                    continue
                directory = stage / ("builtin" if scope == "builtin" else "user/template-library")
                directory.mkdir(parents=True, exist_ok=True)
                if self.context is not None:
                    from .storage import atomic_write_json
                    atomic_write_json(directory / "library.json", {"kind": "template-library", "schema_version": 2,
                        "library_id": scope, "protocol": {"resolver": "asset_resolver/v2", "builder": "capability_manifest/template-registry/v2",
                                                           "asset_id_pattern": ASSET_ID_RE.pattern}})
                    for entity in entities:
                        entity.pop("trusted_root", None)
                        entity.pop("origin_scope", None)
                    continue
                (directory / "library.json").write_text(json.dumps({"kind": "template-library", "schema_version": 1}))
                # builtin registry 保留原 generation；user 仍由其 canonical 文件解析。
                if scope == "builtin":
                    generation = self.generation or "frozen-canonical"
                    catalog = directory / "catalog"
                    registry_dir = catalog / "generations" / generation
                    registry_dir.mkdir(parents=True)
                    for entity in entities:
                        entity.pop("trusted_root", None)
                        entity.pop("origin_scope", None)
                    (registry_dir / "registry.json").write_text(json.dumps({"generation": generation, "entities": entities}))
                    (catalog / "current.json").write_text(json.dumps({"generation": generation}))
            if self.context is not None:
                from .qualification import digest
                marker = {"schema_version": 2, "kind": "asset-snapshot", "catalog_generation": self.generation,
                          "scopes": scope_entities, "pins": list(by_id.values())}
                marker["snapshot_digest"] = digest(marker)
                atomic_write_json(stage / "asset-snapshot.json", marker)
            checked(stage)
            try:
                stage.rename(snapshot)
            except OSError:
                if not snapshot.exists():
                    raise
                return checked(snapshot)
            return checked(snapshot)
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    @property
    @_library_read
    def registry_source(self) -> str:
        self._require_available()
        if self._entities is None:
            self._load()
        return self._registry_source or "empty"

    # -- lookup / resolve -------------------------------------------------- #

    @_library_read
    def lookup(self, query: str, *, scope: str = "any", kind: str | None = None) -> list[dict]:
        """名称/别名/完整 ID 查询：返回全部命中与消歧信息（不自动挑第一个）。"""
        query = query.strip()
        if not query:
            raise ResolverError("resolver_error: 空查询")
        if self._by_id is None:
            self._load()
        # Apply scope/kind before name-vs-alias precedence. Otherwise a
        # same-name entity in another kind can shadow the requested alias and
        # be removed only after the winning entity is chosen.
        candidates = self.entities
        if scope != "any":
            wanted = {"builtin": "builtin", "user": "user"}[scope]
            candidates = [e for e in candidates if e["origin_scope"] == wanted]
        if kind is not None:
            candidates = [e for e in candidates if e["asset_id"].split(":")[1] == kind]
        match = ASSET_ID_RE.fullmatch(query)
        hits: list[dict] = []
        if match:
            entity = self._by_id.get(query)
            if entity is not None and entity in candidates:
                hits.append(entity)
        else:
            lowered = query.casefold()
            name_hits: list[dict] = []
            for entity in candidates:
                names = {entity["name"], *(entity.get("aliases") or []),
                         entity["asset_id"].rsplit(":", 1)[-1]}
                if lowered in {str(n).strip().casefold() for n in names}:
                    hits.append(entity)
                if lowered == str(entity["name"]).strip().casefold():
                    name_hits.append(entity)
            # 名称精确命中优先于别名命中（R-66 家族合并后，主风格会把变体名
            # 留作别名，而变体名本身仍是独立风格：与旧加载器「精确名优先」
            # 语义一致）。同名命中里用户 overlay 优先（方案 §5「名称查询保持
            # 用户同名优先」：user:style:<slug> 与 builtin 同名共存时内置让位）。
            # 纯别名多命中仍完整消歧，不自动挑第一个。
            if name_hits:
                user_hits = [hit for hit in name_hits
                             if hit["origin_scope"] == "user"]
                hits = user_hits or name_hits
        return hits

    @_library_read
    def resolve(self, asset_id: str, *, context: dict | None = None) -> dict:
        """返回实际 ID、可信根、类型、相对路径、revision、依赖与资格。"""
        from .library_migration import require_available
        self._require_available()
        if self._by_id is None:
            self._load()
        match = ASSET_ID_RE.fullmatch(asset_id)
        if not match:
            raise AssetNotFoundError(f"asset_not_found: {asset_id!r} 不是合法 asset_id")
        entity = self._by_id.get(asset_id)
        if entity is None:
            raise AssetNotFoundError(f"asset_not_found: {asset_id}")
        root = Path(entity["trusted_root"])
        require_available(root)
        path = root / entity["path"]
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise ScopeViolationError(f"scope_violation: {entity['path']} 越出可信根")
        if not path.is_file():
            raise AssetNotFoundError(f"asset_not_found: {entity['path']} 文件缺失")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AssetNotFoundError(
                f"asset_not_found: {entity['path']} 不可读") from exc
        revision = revision_of(data)
        if revision != entity["revision"] and self.registry_source == "catalog":
            raise StaleCatalogError(
                f"stale_catalog: {asset_id} 内容与 registry revision 不一致")
        return {
            "asset_id": asset_id,
            "kind": entity["kind"],
            "origin_scope": entity["origin_scope"],
            "trusted_root": str(root),
            "relative_path": entity["path"],
            "path": str(path),
            "revision": revision,
            "name": entity.get("name"),
            "aliases": entity.get("aliases", []),
            "lifecycle": entity.get("lifecycle", "draft"),
            "dependencies": entity.get("dependencies", []),
            "static_eligibility": {
                "loadable": entity.get("lifecycle") in {"active", "draft"},
                "execution_ready": entity.get("lifecycle") == "active",
            },
            "data": data,
        }

    @_library_read
    def resolve_dependencies(self, asset_id: str) -> list[dict]:
        """依赖闭包（含自身），循环依赖拒绝。"""
        resolved_all: dict[str, dict] = {}
        done: set[str] = set()
        visiting: list[str] = []

        def walk(current: str) -> None:
            if current in done:
                return
            if current in visiting:
                raise ResolverError(
                    "resolver_error: 循环依赖 " + " -> ".join([*visiting, current]))
            visiting.append(current)
            entity = self.resolve(current)
            for dep in entity["dependencies"]:
                if self._by_id is not None and dep not in self._by_id:
                    raise DependencyMissingError(
                        f"dependency_missing: {current} 引用 {dep}")
                walk(dep)
            visiting.pop()
            done.add(current)
            resolved_all[current] = entity

        walk(asset_id)
        return list(resolved_all.values())

    @_library_read
    def require(self, query: str, *, kind: str | None = None, scope: str = "any") -> dict:
        """lookup + 唯一性检查 + resolve 的便捷入口；歧义报 ambiguous_name。"""
        hits = self.lookup(query, scope=scope, kind=kind)
        if not hits:
            raise AssetNotFoundError(f"asset_not_found: {query!r}")
        if len(hits) > 1:
            raise AmbiguousNameError(
                "ambiguous_name: " + query + " -> " +
                ", ".join(sorted(hit["asset_id"] for hit in hits)))
        return self.resolve(hits[0]["asset_id"])
