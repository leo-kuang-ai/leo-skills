"""用户 v2 库的最小初始化与逐文件 CAS 事务；调用方持同一写锁。"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path


def user_library_root(home):
    from .library_migration import safe_path
    root = Path(home).absolute()
    if root.is_symlink():
        raise ValueError("user_library_home_symlink")
    return safe_path(root.resolve(), "template-library")


@contextmanager
def user_library_writer(library):
    from filelock import FileLock
    from .library_migration import library_operation, safe_path
    library.mkdir(parents=True, exist_ok=True)
    with library_operation(library), FileLock(str(safe_path(library, ".style-import.lock"))):
        yield


def bootstrap_user_library(library):
    """已有库必须可执行地读取 v2；新库仅安装导入所需的合同闭包。"""
    from leo_ppt_generator.asset_resolver import ASSET_ID_RE, builtin_library_root
    from leo_ppt_generator.library_migration import file_state
    from leo_ppt_generator.qualification import read_evidence_bytes
    from leo_ppt_generator.template_catalog import LibraryContext, read_catalog
    if file_state(library, "library.json")["type"] != "absent":
        declaration = json.loads(read_evidence_bytes(library, "library.json"))
        if declaration.get("schema_version") != 2:
            raise ValueError("pack_library_migration_required")
        if declaration.get("library_id") != "user":
            raise ValueError("pack_library_scope_invalid")
        read_catalog(LibraryContext(library))
        return {}
    # 不把没有声明的旧资产树静默升级成 v2。
    if any((p.is_file() or p.is_symlink()) and p.relative_to(library).as_posix() not in {".style-import.lock", "catalog/.publish.lock"}
           for p in library.rglob("*")):
        raise ValueError("pack_library_migration_required")
    declaration = {
        "schema_version": 2, "kind": "template-library", "library_id": "user",
        "name": "用户模板库",
        "protocol": {"resolver": "asset_resolver/v2", "builder": "capability_manifest/template-registry/v2",
                     "asset_id_pattern": ASSET_ID_RE.pattern},
        "zones": {"canonical": "作者真值", "reference": "参考", "governance": "治理", "catalog": "自动生成", "evidence": "验证"},
        "reserved_directory_names": ["generated", "generations", "staging", "revocations"],
    }
    writes = {"library.json": json_bytes(declaration)}
    builtin = builtin_library_root()
    writes["governance/rules/asset-locations-v2.json"] = read_evidence_bytes(builtin, "governance/rules/asset-locations-v2.json")
    schema_sources = {}
    for path in sorted((builtin / "governance/schemas").glob("*.schema.json")):
        body = read_evidence_bytes(builtin, path.relative_to(builtin).as_posix())
        schema = json.loads(body)
        schema_sources[schema.get("$id")] = (path.name, body, schema)
    def include(schema_id):
        if schema_id not in schema_sources:
            raise ValueError("pack_schema_reference_missing:" + schema_id)
        name, body, schema = schema_sources[schema_id]
        relative = "governance/schemas/" + name
        if relative in writes:
            return
        writes[relative] = body
        def visit(value):
            if isinstance(value, dict):
                reference = value.get("$ref", "").split("#", 1)[0]
                if reference:
                    include(reference)
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        visit(schema)
    for schema_id in ("https://leo-ppt.invalid/schemas/style-brief/v2", "https://leo-ppt.invalid/schemas/executable-adoption/v1"):
        include(schema_id)
    return writes


def json_bytes(value):
    from leo_ppt_generator.storage import canonical_json_bytes
    return canonical_json_bytes(value)


def _tree_states(library):
    from leo_ppt_generator.library_migration import file_state
    ignored = {".style-import.lock", "catalog/.publish.lock"}
    return {p.relative_to(library).as_posix(): file_state(library, p.relative_to(library).as_posix())
            for p in sorted(library.rglob("*"))
            if (p.is_file() or p.is_symlink()) and p.relative_to(library).as_posix() not in ignored}


def publish_user_library(library, writes, *, guards=None, validator=None, verifier=None, overwrite=()):
    """源与派生 catalog 使用同一逐文件 CAS 事务，失败只恢复仍由本次拥有的字节。"""
    from filelock import FileLock
    from leo_ppt_generator.library_migration import safe_path
    lock = safe_path(library, "catalog/.publish.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(lock)):
        _publish_user_library_locked(library, writes, guards=guards, validator=validator, verifier=verifier, overwrite=overwrite)


def _publish_user_library_locked(library, writes, *, guards=None, validator=None, verifier=None, overwrite=()):
    from leo_ppt_generator.library_migration import file_state, compare_and_swap_file, _unlink_cas
    from leo_ppt_generator.qualification import read_evidence_bytes
    from leo_ppt_generator.template_catalog import build_catalog, LibraryContext, read_catalog
    baseline = _tree_states(library)
    expected_tree = dict(baseline)
    journal = []
    def put(relative, body, *, replace=False):
        previous = expected_tree.get(relative, {"type": "absent", "sha256": None, "mode": None})
        if file_state(library, relative) != previous:
            raise ValueError("pack_external_drift:" + relative)
        desired = {"type": "file", "sha256": hashlib.sha256(body).hexdigest(), "mode": 0o644}
        if previous == desired:
            return
        if previous["type"] != "absent" and not replace:
            raise ValueError("pack_target_conflict:" + relative)
        old_bytes = read_evidence_bytes(library, relative) if previous["type"] == "file" else None
        # CAS 可能已经 replace 后才报告故障；先登记回滚所需的精确新旧状态。
        journal.append((relative, previous, old_bytes, desired))
        compare_and_swap_file(library, relative, expected=previous, body=body)
        expected_tree[relative] = desired
    def check_tree():
        if _tree_states(library) != expected_tree:
            raise ValueError("pack_external_drift")
        for relative, expected_hash in (guards or {}).items():
            if file_state(library, relative).get("sha256") != expected_hash:
                raise ValueError("pack_guard_drift:" + relative)
        if validator:
            validator()
    try:
        check_tree()
        for relative, body in writes.items():
            put(relative, body, replace=relative in overwrite)
        check_tree()
        outputs = build_catalog(library)
        generation = outputs["registry.json"]["catalog_generation"]
        for relative, value in outputs.items():
            put("catalog/generations/" + generation + "/" + relative, json_bytes(value))
        check_tree()
        put("catalog/current.json", json_bytes({"kind": "template-catalog-pointer", "schema_version": 2,
                                               "generation": generation}), replace=True)
        check_tree()
        read_catalog(LibraryContext(library))
        if verifier:
            verifier()
        check_tree()
    except BaseException as exc:
        conflicts = []
        for relative, previous, old_bytes, desired in reversed(journal):
            try:
                current = file_state(library, relative)
                if current == previous:
                    continue
                if previous["type"] == "absent":
                    _unlink_cas(library, relative, desired)
                else:
                    compare_and_swap_file(library, relative, expected=desired, body=old_bytes, mode=previous["mode"])
            except (ValueError, OSError):
                conflicts.append(relative)
        if conflicts:
            raise ValueError("pack_rollback_external_drift:" + ",".join(conflicts)) from exc
        raise
