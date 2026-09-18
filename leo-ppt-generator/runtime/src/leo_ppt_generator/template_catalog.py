"""v2 位置合同、无环派生 catalog 与不可变 generation 发布。"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile

from .qualification import asset_generation, digest, environment_fingerprint, file_reference, read_evidence_bytes, verify_reference
from .storage import atomic_write_json, canonical_json_bytes, fsync_directory

LOCATIONS = "governance/rules/asset-locations-v2.json"
POLICY = "capability_manifest/template-registry/v2"


class CatalogError(ValueError):
    def __init__(self, reason_code, detail=""):
        super().__init__(reason_code + (":" + detail if detail else ""))
        self.reason_code = reason_code


@dataclass(frozen=True)
class LibraryContext:
    root: Path
    mode: str = "execution"
    user_root: Path | None = None

    def __post_init__(self):
        if self.mode not in {"execution", "diagnostic"}:
            raise CatalogError("library_context_mode_invalid")
        object.__setattr__(self, "root", Path(self.root).absolute())
        if self.user_root is not None:
            object.__setattr__(self, "user_root", Path(self.user_root).absolute())


def _json(root, relative):
    return json.loads(read_evidence_bytes(root, relative))


def validate_library(root):
    root = Path(root)
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise CatalogError("scope_violation")
    try:
        declaration = _json(root, "library.json")
    except (OSError, ValueError) as exc:
        raise CatalogError("library_missing") from exc
    protocol = declaration.get("protocol", {})
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).parent / "schemas/template-library-v2.schema.json").read_text())
    if list(Draft202012Validator(schema).iter_errors(declaration)):
        raise CatalogError("unsupported_schema", "从来源重建 v2 库")
    if (declaration.get("schema_version") != 2 or declaration.get("kind") != "template-library"
            or declaration.get("library_id") not in {"builtin", "user"}
            or protocol.get("resolver") != "asset_resolver/v2" or protocol.get("builder") != POLICY):
        raise CatalogError("unsupported_schema", "从来源重建 v2 库")
    return declaration


def location_rules(root):
    rules = _json(root, LOCATIONS)
    if rules.get("schema_version") != 2 or rules.get("rule_id") != "asset-locations-v2" or not rules.get("entities"):
        raise CatalogError("asset_locations_invalid")
    seen = set()
    for row in rules["entities"]:
        pattern = row["pattern"]
        if (pattern in seen or "**" in pattern or pattern.count("*") != 1
                or not pattern.startswith("canonical/") or row["kind"] == "qa-profile"):
            raise CatalogError("asset_locations_invalid")
        seen.add(pattern)
    return rules


def _matches(pattern, value):
    return re.fullmatch(re.escape(pattern).replace(r"\*", "[^/]+"), value) is not None


def scan_records(root):
    """scanner/builder/resolver 共用同一精确模式；附属字节必须隶属唯一实体目录。"""
    from .library_migration import library_operation
    with library_operation(root):
        from .asset_resolver import revision_of, _declared_dependencies, ASSET_ID_RE
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
        root = Path(root)
        declaration, rules = validate_library(root), location_rules(root)
        resources = []
        for path in sorted((root / "governance/schemas").glob("*.schema.json")):
            data = _json(root, path.relative_to(root).as_posix())
            if "$id" in data:
                resources.append((data["$id"], Resource.from_contents(data)))
        registry = Registry().with_resources(resources)
        records, references, seen, owners, all_files = [], [], set(), [], []
        for path in sorted((root / "canonical").rglob("*")):
            if path.is_symlink():
                raise CatalogError("scope_violation", path.relative_to(root).as_posix())
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            all_files.append(relative)
            matched = [rule for rule in rules["entities"] if _matches(rule["pattern"], relative)]
            if len(matched) > 1:
                raise CatalogError("asset_location_conflict", relative)
            if not matched:
                continue
            rule = matched[0]
            slug = path.parent.name
            if slug in rule["exclude_segments"]:
                raise CatalogError("reserved_entity_directory", relative)
            data = _json(root, relative)
            identity = data.get("asset_id", "")
            if (not ASSET_ID_RE.fullmatch(identity) or identity.split(":")[:2] != [declaration["library_id"], rule["kind"]]
                    or identity in seen or (rule["kind"] == "axis" and data.get("kind") != rule["family"])):
                raise CatalogError("asset_identity_invalid", identity)
            seen.add(identity)
            if rule["schema"] is not None:
                schema = _json(root, "governance/schemas/" + rule["schema"])
                errors = list(Draft7Validator(schema, registry=registry).iter_errors(data))
                if errors:
                    raise CatalogError("asset_schema_invalid", relative + ":" + errors[0].message)
            elif rule["kind"] == "component" and data.get("entity") != "component":
                raise CatalogError("component_schema_unavailable", relative)
            record = {"asset_id": identity, "kind": rule["kind"], "path": relative,
                "revision": revision_of(data), "name": data.get("name") or slug,
                "aliases": data.get("aliases", []), "lifecycle": data.get("lifecycle", "draft"),
                "catalog_status": rule["catalog"], "dependencies": _declared_dependencies(data)}
            (references if rule["catalog"] == "reference-only" else records).append(record)
            owners.append(path.parent.relative_to(root).as_posix() + "/")
        for relative in all_files:
            if sum(relative.startswith(owner) for owner in owners) != 1:
                raise CatalogError("unclassified_canonical_file", relative)
        for record in records:
            for dependency in record["dependencies"]:
                if dependency not in seen:
                    raise CatalogError("dependency_missing", record["asset_id"] + "->" + dependency)
        return sorted(records, key=lambda r: r["asset_id"]), sorted(references, key=lambda r: r["asset_id"])


def catalog_inputs(root):
    files = {}
    for path in sorted((Path(root) / "evidence").rglob("*")):
        if path.is_symlink():
            raise CatalogError("scope_violation")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            files[relative] = file_reference(root, relative)["sha256"]
    package = Path(__file__).parent
    policy = {name: file_reference(package, name)["sha256"] for name in ("template_catalog.py", "asset_resolver.py", "qualification.py", "execution_pairing.py")}
    return {"asset_generation": asset_generation(root), "evidence_set_digest": digest(files),
            "policy_digest": digest({"policy": POLICY, "owners": policy, "environment": environment_fingerprint()})}


def build_catalog(root):
    """先资产代，再 evidence 集，再 catalog 代；不读取/修改 current。"""
    from .library_migration import library_operation
    with library_operation(root):
        from .asset_resolver import AssetResolver
        from .qualification import derive_qualification, layout_capability_contract, load_receipts
        from .execution_pairing import derive_execution_pairings
        root = Path(root)
        records, references = scan_records(root)
        inputs = catalog_inputs(root)
        generation = digest(inputs)
        resolver = AssetResolver(context=LibraryContext(root, mode="diagnostic"))
        receipts, qualifications = load_receipts(root), []
        environment = environment_fingerprint()
        for record in records:
            if record["kind"] != "layout":
                continue
            asset = resolver.resolve(record["asset_id"])
            contract, _ = layout_capability_contract(asset, resolver=resolver)
            dependencies = {lane: layout_capability_contract(asset, resolver=resolver, lane=lane)[1] for lane in contract["lanes"]}
            qualifications.append(derive_qualification(contract, asset_generation=inputs["asset_generation"], evidence_receipts=receipts,
                library_root=root, expected_dependencies=dependencies, environment=environment))
        pairing = derive_execution_pairings(
            [resolver.resolve(row["asset_id"]) for row in records if row["kind"] == "layout"],
            [resolver.resolve(row["asset_id"]) for row in records if row["kind"] in {"template", "recipe"}],
            {row["asset_id"]: row for row in qualifications}, catalog_generation=generation)
        result = {"registry.json": {"kind": "template-registry", "schema_version": 2, "catalog_generation": generation,
            **inputs, "entities": records, "references": references},
            "views/execution-pairings.json": pairing,
            "views/relation-capabilities.json": {"schema_version": 1, "kind": "qualification-manifest",
                **inputs, "catalog_generation": generation, "qualifications": qualifications},
            "views/visual.json": {"schema_version": 2, "catalog_generation": generation,
                "entities": [row for row in records if row["catalog_status"] == "visual"]}}
        if catalog_inputs(root) != inputs:
            raise CatalogError("catalog_inputs_changed_during_build")
        result["build-manifest.json"] = {"kind": "template-registry-build", "schema_version": 2,
            "catalog_generation": generation, **inputs, "output_hashes": {path: digest(value) for path, value in result.items()}}
        return result


def publish_catalog(root, outputs, *, checkpoint=None):
    """唯一 current 切换；同代不同字节拒绝，不能原地刷新已存在的一代。"""
    from .library_migration import library_operation
    with library_operation(root):
        from filelock import FileLock
        from .library_migration import safe_path, require_available
        root = Path(root).absolute()
        require_available(root)
        generation = outputs["registry.json"]["catalog_generation"]
        if outputs != build_catalog(root):
            raise CatalogError("stale_catalog")
        catalog = safe_path(root, "catalog")
        catalog.mkdir(parents=True, exist_ok=True)
        lock = safe_path(root, "catalog/.publish.lock")
        with FileLock(str(lock)):
            target = safe_path(root, "catalog/generations/" + generation)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                actual_paths = {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()}
                if actual_paths != set(outputs) or any(read_evidence_bytes(target, name) != canonical_json_bytes(data) for name, data in outputs.items()):
                    raise CatalogError("catalog_generation_conflict")
            else:
                with tempfile.TemporaryDirectory(prefix=".catalog-generation-", dir=catalog) as temporary:
                    staging = Path(temporary)
                    for name, data in outputs.items():
                        path = staging / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with path.open("xb") as handle:
                            handle.write(canonical_json_bytes(data)); handle.flush(); os.fsync(handle.fileno())
                    fsync_directory(staging)
                    if checkpoint:
                        checkpoint("before_generation")
                    staging.rename(target)
                    fsync_directory(target.parent)
            if checkpoint:
                checkpoint("before_pointer")
            atomic_write_json(catalog / "current.json", {"kind": "template-catalog-pointer", "schema_version": 2, "generation": generation})
        return {"generation": generation, "published": True}


def read_catalog(context):
    """execution 拒绝缺失/损坏/stale；只有 diagnostic 可以扫描 canonical。"""
    from .library_migration import library_operation
    with library_operation(context.root):
        root = context.root
        from .library_migration import require_available
        require_available(root)
        validate_library(root)
        if context.mode == "diagnostic":
            records, references = scan_records(root)
            return {"entities": records, "references": references, "catalog_generation": asset_generation(root), "diagnostic": True}
        try:
            pointer = _json(root, "catalog/current.json")
        except (OSError, ValueError) as exc:
            if not (root / "catalog/current.json").exists():
                raise CatalogError("catalog_missing") from exc
            raise CatalogError("catalog_invalid") from exc
        generation = pointer.get("generation", "")
        if pointer.get("schema_version") != 2 or not re.fullmatch(r"[0-9a-f]{64}", generation):
            raise CatalogError("catalog_invalid")
        prefix = "catalog/generations/" + generation + "/"
        try:
            build = _json(root, prefix + "build-manifest.json")
            if set(build["output_hashes"]) != {"registry.json", "views/execution-pairings.json", "views/relation-capabilities.json", "views/visual.json"}:
                raise CatalogError("catalog_invalid")
            for relative, sha in build["output_hashes"].items():
                verify_reference(root, {"path": prefix + relative, "sha256": sha})
            registry = _json(root, prefix + "registry.json")
        except (OSError, ValueError, KeyError) as exc:
            raise CatalogError("catalog_invalid") from exc
        expected = catalog_inputs(root)
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).parent / "schemas/template-registry-v2.schema.json").read_text())
        if list(Draft202012Validator(schema).iter_errors(registry)):
            raise CatalogError("catalog_invalid")
        if (registry.get("catalog_generation") != generation or build.get("catalog_generation") != generation
                or registry.get("schema_version") != 2 or build.get("schema_version") != 2):
            raise CatalogError("catalog_invalid")
        if any(registry.get(key) != value or build.get(key) != value for key, value in expected.items()) or digest(expected) != generation:
            raise CatalogError("stale_catalog")
        derived = build_catalog(root)
        if any(read_evidence_bytes(root, prefix + path) != canonical_json_bytes(value) for path, value in derived.items()):
            raise CatalogError("catalog_invalid", "派生内容与同代输入不符")
        return registry
