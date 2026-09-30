"""模板迁移的文件事务与收据校验；所有路径显式相对交付根或证据根。"""
from __future__ import annotations

from contextlib import contextmanager
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import shutil

from .qualification import digest, file_reference, read_evidence_bytes, verify_reference
from .storage import atomic_write_json, json_document_bytes

RECEIPT_KIND = "template-library-migration-receipt"
PLAN_KIND = "template-library-migration-plan"
CURRENT = "leo-ppt-generator/template-library/catalog/current.json"
PUBLICATION_IDENTITY = ("transaction_id", "base_revision", "plan_digest")
STRUCTURAL_GATES = {"asset-bytes", "identity-reference", "probe", "v2-catalog", "consumer-closure", "bundle", "manifest-hashes"}
CLOSURE_ROOTS = ("leo-ppt-generator/runtime/src", "leo-ppt-generator/scripts", "leo-ppt-generator/tests",
    "leo-ppt-generator/evals", "leo-ppt-generator/SKILL.md", "leo-ppt-generator/references",
    "leo-ppt-generator/prompts", "docs/plans", "docs/prd", "docs/leo-ppt-generator", "CHANGELOG.md")
CLOSURE_FILES = {"leo-ppt-generator/SKILL.md", "CHANGELOG.md"}
# 这些脚本只读取退役来源或生成迁移基线，不参与生产解析、候选选择或物化。
# 逐文件登记，不能把整个 scripts/ 根目录豁免为 migration-only。
MIGRATION_ONLY_CONSUMERS = {
    "leo-ppt-generator/scripts/freeze_template_rebuild_baseline.py",
    "leo-ppt-generator/scripts/generate_capacity_draft.py",
    "leo-ppt-generator/scripts/migrate_style_aliases.py",
    "leo-ppt-generator/scripts/audit_style_families.py",
}
LEGACY_SIGNATURES = (
    r"references/styles", r"canonical/(?:styles|themes|brands|fonts|ornaments|layouts|templates|components|axes|presets)(?=[/\s\"']|$)",
    r"[\"']canonical[\"']\s*/\s*[\"'](?:styles|themes|brands|fonts|ornaments|layouts|templates|components|axes|presets)[\"']",
    r"\$\{?LEO_PPT_HOME\}?/brands(?=[/\s\"']|$)",
    r"(?:asset_resolver|template-registry|page-type-regime)[/-]v1",
    r"(?<![A-Za-z0-9_-])qa-profile(?![A-Za-z0-9_-])", r"retired-styles-tree")
LEGACY_FOLDERS = {"styles": "visual/styles", "themes": "visual/themes", "brands": "visual/brands",
    "fonts": "visual/fonts", "ornaments": "visual/ornaments", "layouts": "executable/layouts",
    "templates": "executable/templates", "components": "executable/components", "presets": "collections/presets"}
AXIS_FOLDERS = {"argument": "semantic/argument-modes", "page-semantics": "semantic/page-types",
    "chart": "semantic/guides/chart", "infographic": "semantic/guides/infographic",
    "structure": "executable/layouts/guides", "rendering": "executable/renderers/guides"}


class MigrationError(ValueError):
    pass


def _closure_literal_dictionary(tree, symbol):
    """只读取唯一顶层字面表；重绑定、别名逃逸与方法写入均保持未知。"""
    candidates = []
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == symbol:
            parent = parents.get(node)
            if isinstance(node.ctx, ast.Store):
                if (not isinstance(parent, (ast.Assign, ast.AnnAssign))
                        or parents.get(parent) is not tree
                        or isinstance(parent, ast.Assign) and len(parent.targets) != 1):
                    return None
                candidates.append(parent.value)
            elif isinstance(node.ctx, ast.Load):
                call = parents.get(parent)
                if (not isinstance(parent, ast.Attribute) or parent.attr != "items"
                        or not isinstance(call, ast.Call) or call.func is not parent
                        or call.args or call.keywords):
                    return None
            else:
                return None
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            return None
        elif isinstance(node, ast.arg) and node.arg == symbol:
            return None
        elif isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                (alias.asname or alias.name.split(".")[0]) == symbol for alias in node.names):
            return None
    if len(candidates) != 1:
        return None
    value = candidates[0]
    if (not isinstance(value, ast.Dict) or not 0 < len(value.keys) <= 64
            or any(not isinstance(item, ast.Constant) or not isinstance(item.value, str)
                   for item in [*value.keys, *value.values])):
        return None
    return value


def _python_closure_context(body, *, imported_literal=None, module_name=None):
    """只由 AST 证明拒绝范围与 canonical 根；命名、注释和相邻断言不授予豁免。"""
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return [], [], []
    lines = body.splitlines(keepends=True)
    starts, total = [], 0
    for line in lines:
        starts.append(total)
        total += len(line)

    def span(node):
        def offset(line, column):
            return starts[line - 1] + len(lines[line - 1].encode("utf-8")[:column].decode("utf-8"))
        return offset(node.lineno, node.col_offset), offset(node.end_lineno, node.end_col_offset)

    def raises_call(node):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and (node.func.attr in {"assertRaises", "assertRaisesRegex"}
                     or node.func.attr == "raises" and isinstance(node.func.value, ast.Name)
                     and node.func.value.id == "pytest"))

    negatives, rejections = [], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)) and any(raises_call(item.context_expr) for item in node.items):
            negatives.append(span(node))
        elif raises_call(node):
            negatives.append(span(node))
        if (isinstance(node, ast.If) and len(node.body) == 1 and isinstance(node.body[0], ast.Raise)
                and isinstance(node.test, ast.Compare) and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], (ast.Eq, ast.In))
                and isinstance(node.test.left, (ast.Name, ast.Attribute))
                and isinstance(node.test.comparators[0], (ast.Constant, ast.Set, ast.Tuple, ast.List))
                and not any(isinstance(value, ast.Call) for value in ast.walk(node.test))):
            rejections.append(span(node.test))
    # 各作用域分别收集绑定；保留分支候选，不以同名变量冲突换取零命中。
    scopes, parents, contexts, imports = {}, {}, [], {}

    def scope(parent=None, kind="module"):
        context = {"parent": parent, "kind": kind, "definitions": {}, "global": set(), "nonlocal": set()}
        contexts.append(context)
        return context

    def bind(context, target, value=None):
        if isinstance(target, ast.Name):
            context["definitions"].setdefault(target.id, []).append(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = value.elts if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts) else [None] * len(target.elts)
            for item, expression in zip(target.elts, values):
                bind(context, item, expression)

    def bind_iteration(context, target, iterable, positions=()):
        if isinstance(target, ast.Name):
            context["definitions"].setdefault(target.id, []).append((iterable, positions))
        elif isinstance(target, (ast.Tuple, ast.List)):
            for position, item in enumerate(target.elts):
                bind_iteration(context, item, iterable, (*positions, (position, len(target.elts))))

    def index(node, context, parent=None):
        scopes[node], parents[node] = context, parent
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            if not isinstance(node, ast.Lambda):
                context["definitions"].setdefault(node.name, []).append(None)
            enclosing = context
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                while enclosing["kind"] == "class":
                    enclosing = enclosing["parent"]
            child = scope(enclosing, "class" if isinstance(node, ast.ClassDef) else "function")
            if hasattr(node, "args"):
                args = node.args
                for argument in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
                    if argument is not None:
                        child["definitions"][argument.arg] = [None]
                positional = [*args.posonlyargs, *args.args]
                defaults = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
                defaults.extend(zip(args.kwonlyargs, args.kw_defaults))
                for argument, default in defaults:
                    if default is not None:
                        child["definitions"][argument.arg].append(default)
            for field, value in ast.iter_fields(node):
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, ast.AST):
                        index(item, child if field == "body" else context, node)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            child = scope(context, "comprehension")
            for generator in node.generators:
                bind(child, generator.target)
            for item in ast.iter_child_nodes(node):
                index(item, child, node)
            return
        if isinstance(node, ast.Global):
            context["global"].update(node.names)
        elif isinstance(node, ast.Nonlocal):
            context["nonlocal"].update(node.names)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                bind(context, target, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bind_iteration(context, node.target, node.iter)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                bind(context, item.optional_vars)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                value = imported_literal(node, alias.name) if imported_literal and isinstance(node, ast.ImportFrom) else None
                context["definitions"].setdefault(name, []).append(value)
                imports.setdefault((id(context), name), []).append(node)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            context["definitions"].setdefault(node.name, []).append(None)
        elif isinstance(node, ast.AugAssign):
            bind(context, node.target)
        for item in ast.iter_child_nodes(node):
            index(item, context, node)

    index(tree, scope())
    # 闭包内的显式外层写入也进入外层候选集，不能沿用被修改前的安全根。
    for context in contexts:
        for name in context["global"] | context["nonlocal"]:
            outer = context["parent"]
            if outer is None:
                continue
            if name in context["global"]:
                while outer["parent"] is not None:
                    outer = outer["parent"]
            else:
                while outer is not None and name not in outer["definitions"]:
                    outer = outer["parent"]
            if outer is not None:
                outer["definitions"].setdefault(name, []).extend(context["definitions"].get(name, []))
    unknown = "\0"
    folders = {*LEGACY_FOLDERS, "axes"}

    def defining_context(node):
        context = scopes[node]
        if node.id in context["global"]:
            while context["parent"] is not None:
                context = context["parent"]
        elif node.id in context["nonlocal"]:
            context = context["parent"]
        while context is not None and node.id not in context["definitions"]:
            context = context["parent"]
        return context

    def literal_dictionaries(node, resolving):
        if isinstance(node, ast.Dict):
            if (0 < len(node.keys) <= 64 and all(isinstance(item, ast.Constant) and isinstance(item.value, str)
                    for item in [*node.keys, *node.values])):
                return [node]
            return [None]
        if not isinstance(node, ast.Name):
            return [None]
        context = defining_context(node)
        key = (id(context), node.id)
        if context is None or key in resolving or len(context["definitions"][node.id]) != 1:
            return [None]
        # 只有 .items() 读取可证明该表没有通过本模块别名或调用发生写入。
        for reference in ast.walk(tree):
            if not isinstance(reference, ast.Name) or reference.id != node.id or not isinstance(reference.ctx, ast.Load):
                continue
            if defining_context(reference) is not context:
                continue
            parent = parents.get(reference)
            call = parents.get(parent)
            if (not isinstance(parent, ast.Attribute) or parent.attr != "items"
                    or not isinstance(call, ast.Call) or call.func is not parent or call.args or call.keywords):
                return [None]
        return literal_dictionaries(context["definitions"][node.id][0], resolving | {key})

    def iteration_rows(node, resolving):
        if isinstance(node, (ast.Tuple, ast.List)):
            return node.elts if 0 < len(node.elts) <= 64 else [None]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sorted"
                and len(node.args) == 1 and not node.keywords):
            context = defining_context(node.func)
            return iteration_rows(node.args[0], resolving) if context is None else [None]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "items"
                and not node.args and not node.keywords):
            rows = []
            for dictionary in literal_dictionaries(node.func.value, resolving):
                if dictionary is None:
                    rows.append(None)
                else:
                    rows.extend(ast.Tuple(elts=[key, value]) for key, value in zip(dictionary.keys, dictionary.values))
            return rows
        return [None]

    def default_home_call(node):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.args and not node.keywords):
            return False
        context = defining_context(node.func)
        sources = imports.get((id(context), node.func.id), [])
        if context is None or len(context["definitions"][node.func.id]) != 1 or len(sources) != 1:
            return False
        source = sources[0]
        return (isinstance(source, ast.ImportFrom)
                and ((source.level == 0 and source.module == "leo_ppt_generator.config.runtime_config")
                     or (source.level == 1 and source.module == "config.runtime_config"
                         and module_name and module_name.startswith("leo_ppt_generator.")))
                and any(alias.name == "default_home" and (alias.asname or alias.name) == node.func.id for alias in source.names))

    def path_call(node):
        return isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name) and node.func.id in {"Path", "PurePosixPath"}
            or isinstance(node.func, ast.Attribute) and node.func.attr in {"Path", "PurePosixPath", "joinpath"})

    def path_expression(node):
        return path_call(node) or isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add))

    def joined(left, right):
        return right if right.startswith("/") else left.rstrip("/") + "/" + right

    def values(node, resolving, uncertain):
        if node is None:
            return {unknown}
        if isinstance(node, tuple):
            iterable, positions = node
            result = set()
            for row in iteration_rows(iterable, resolving):
                for position, length in positions:
                    row = row.elts[position] if isinstance(row, (ast.Tuple, ast.List)) and len(row.elts) == length else None
                result.update(values(row, resolving, uncertain))
            return result or {unknown}
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.Name):
            context = defining_context(node)
            key = (id(context), node.id)
            if context is None or key in resolving:
                return {unknown}
            result = set()
            for expression in context["definitions"][node.id]:
                result.update(values(expression, resolving | {key}, uncertain))
                if len(result) > 64:
                    uncertain.append(True)
                    return {unknown}
            return result
        if isinstance(node, ast.IfExp):
            return values(node.body, resolving, uncertain) | values(node.orelse, resolving, uncertain)
        if isinstance(node, ast.BoolOp):
            return set().union(*(values(item, resolving, uncertain) for item in node.values))
        if default_home_call(node):
            return {"$LEO_PPT_HOME"}
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
            expressions = [node.left, node.right]
            combine = joined if isinstance(node.op, ast.Div) else lambda a, b: a + b
        elif path_call(node):
            expressions = list(node.args)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath":
                expressions.insert(0, node.func.value)
            combine = joined
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"resolve", "absolute"}:
            return values(node.func.value, resolving, uncertain)
        elif isinstance(node, ast.JoinedStr):
            expressions = [item.value if isinstance(item, ast.FormattedValue) else item for item in node.values]
            combine = lambda a, b: a + b
        else:
            return {unknown}
        if not expressions:
            return {unknown}
        result = values(expressions[0], resolving, uncertain)
        for expression in expressions[1:]:
            right = values(expression, resolving, uncertain)
            if len(result) * len(right) > 64:
                uncertain.append(True)
                return {unknown}
            result = {combine(a, b) for a in result for b in right}
        return result

    def status(value):
        parts = PurePosixPath(value).parts
        if any(left == "$LEO_PPT_HOME" and right == "brands" for left, right in zip(parts, parts[1:])):
            return "legacy"
        if any(left == "canonical" and right in folders for left, right in zip(parts, parts[1:])):
            return "legacy"
        for position, part in enumerate(parts):
            if part == "canonical" and position + 1 < len(parts) and unknown in parts[position + 1]:
                return "unknown"
            if part in folders and position and unknown in parts[position - 1]:
                return "unknown"
            if unknown in part and part.replace(unknown, ""):
                pattern = re.escape(part).replace(re.escape(unknown), ".*")
                if any(re.fullmatch(pattern, candidate) for candidate in {"canonical", *folders}):
                    return "unknown"
        return None

    joins = []
    for node in ast.walk(tree):
        if not path_expression(node) or path_expression(parents.get(node)):
            continue
        uncertain = []
        outcomes = {status(value) for value in values(node, frozenset(), uncertain)}
        if "legacy" in outcomes or "unknown" in outcomes or uncertain:
            start, end = span(node)
            # 已有字面签名由同一个 scanner 记录，避免同一表达式重复计数。
            if any(re.search(signature, body[start:end]) for signature in LEGACY_SIGNATURES):
                continue
            joins.append((start, body[start:end], "legacy" not in outcomes))
    return negatives, rejections, joins


def scan_consumer_closure(root):
    """固定 roots 的逐命中账本；旧迁移输入与历史证据不冒充活动消费者。"""
    return _scan_consumer_closure(root)


def _scan_consumer_closure(root, replacements=None):
    root = Path(root).absolute()
    replacements = replacements or {}
    hits, roots, source_trees = [], [], {}
    runtime_prefix = "leo-ppt-generator/runtime/src/"

    def module_name(path):
        if not path.startswith(runtime_prefix) or not path.endswith(".py"):
            return None
        return path[len(runtime_prefix):-3].replace("/", ".").removesuffix(".__init__")

    def imported_literal(importer, node, symbol):
        # 只读本次扫描树中的单层模块；不 import，也不借用已安装运行时的常量。
        module = node.module or ""
        if node.level:
            owner = module_name(importer)
            if owner is None:
                return None
            package = owner.split(".") if importer.endswith("/__init__.py") else owner.split(".")[:-1]
            if node.level > len(package):
                return None
            module = ".".join([*package[:len(package) - node.level + 1], *module.split(".")])
        if (not module.startswith("leo_ppt_generator.")
                or not all(part.isidentifier() for part in module.split(".")) or not symbol.isidentifier()):
            return None
        relative = runtime_prefix + module.replace(".", "/") + ".py"
        source = safe_path(root, relative)
        if relative not in replacements and (not source.is_file() or source.stat().st_size > 1024 * 1024):
            return None
        if relative not in source_trees:
            raw = replacements[relative] if relative in replacements else read_evidence_bytes(root, relative, max_bytes=1024 * 1024)
            if len(raw) > 1024 * 1024:
                return None
            try:
                candidate = ast.parse(raw.decode("utf-8"))
            except (SyntaxError, UnicodeError, RecursionError):
                candidate = None
            if candidate is not None and sum(1 for _ in ast.walk(candidate)) > 50000:
                candidate = None
            source_trees[relative] = candidate
        tree = source_trees[relative]
        return _closure_literal_dictionary(tree, symbol) if tree is not None else None
    migration_owners = {"leo-ppt-generator/scripts/migrate_template_library.py",
                        "leo-ppt-generator/runtime/src/leo_ppt_generator/library_migration.py"}
    for relative in CLOSURE_ROOTS:
        base = safe_path(root, relative)
        roots.append({"path": relative, "exists": base.is_file() if relative in CLOSURE_FILES else base.is_dir()})
        paths = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
        for path in paths:
            if path.is_symlink():
                raise MigrationError("migration_closure_symlink:" + path.relative_to(root).as_posix())
            if not path.is_file() or path.suffix.lower() not in {".py", ".json", ".md", ".txt", ".yaml", ".yml", ".sh", ".js", ".html", ".toml"}:
                continue
            name = path.relative_to(root).as_posix()
            body = (replacements[name] if name in replacements else read_evidence_bytes(root, name)).decode("utf-8")
            classification, disposition = "active-consumer", "migrate"
            if name in migration_owners:
                classification, disposition = "migration-input", "retain-migration-only"
            elif name in MIGRATION_ONLY_CONSUMERS or (
                    name.startswith("leo-ppt-generator/scripts/intake_")
                    and name.endswith(".py")):
                classification, disposition = "migration-input", "retain-migration-only"
            elif name == "CHANGELOG.md":
                classification, disposition = "provenance", "retain-changelog-history"
            elif name.startswith(("docs/plans/", "docs/prd/")):
                classification, disposition = "plan-control", "retain-control"
            elif "/evidence/" in name or "/reviews/" in name:
                classification, disposition = "provenance", "retain-read-only"
            elif name.startswith("docs/leo-ppt-generator/") and path.suffix == ".md":
                # 只读历史记录仍进入逐命中账本；不能按旧日期把活动指引一概排除。
                if (body.startswith("---\n") and re.search(r"(?m)^status: historical-reference$", body.split("\n---", 1)[0])):
                    classification, disposition = "provenance", "retain-explicit-historical-reference"
                elif name.startswith("docs/leo-ppt-generator/tech-plans/") and "性质：技术方案（HOW）" in body:
                    classification, disposition = "plan-control", "retain-tech-plan-requiring-spec-plan"
                elif name.startswith("docs/leo-ppt-generator/evals/") and re.match(r"# .+测试报告[（(]\d{4}-\d{2}-\d{2}[）)]", body):
                    classification, disposition = "provenance", "retain-dated-evaluation-report"
                elif (name == "docs/leo-ppt-generator/template-rebuild-baseline.md"
                      and "本文是 U1 的冻结记录与摘要" in body):
                    classification, disposition = "provenance", "retain-frozen-baseline-record"
                elif (name == "docs/leo-ppt-generator/template-rebuild-verification.md"
                      and re.search(r"本登记截至 \d{4}-\d{2}-\d{2} 本实施批", body)):
                    classification, disposition = "provenance", "retain-bounded-verification-record"
            negatives, rejections, joins = _python_closure_context(body,
                imported_literal=lambda node, symbol: imported_literal(name, node, symbol),
                module_name=module_name(name)) if path.suffix == ".py" else ([], [], [])
            matches = {(match.start(), match.group(), False) for signature in LEGACY_SIGNATURES for match in re.finditer(signature, body)}
            matches.update(joins)
            for offset, signature, unresolved in sorted(matches):
                hit_classification, hit_disposition = classification, disposition
                if unresolved and hit_disposition == "migrate":
                    hit_disposition = "classify-dynamic-path"
                if name.startswith("leo-ppt-generator/tests/") and any(start <= offset < end for start, end in negatives):
                    hit_classification, hit_disposition = "test-fixture", "retain-negative-contract"
                elif any(start <= offset < end for start, end in rejections):
                    hit_disposition = "retain-explicit-rejection-contract"
                hits.append({"path": name, "line": body.count("\n", 0, offset) + 1,
                    "signature": signature, "classification": hit_classification,
                    "owner": name, "disposition": hit_disposition})
    hits.sort(key=lambda row: (row["path"], row["line"], row["signature"]))
    return {"roots": roots, "signatures": list(LEGACY_SIGNATURES), "hits": hits,
        "unclassified_hits": sum(not row["classification"] or row["disposition"] == "classify-dynamic-path" for row in hits),
        "active_legacy_hits": sum(row["disposition"] == "migrate" for row in hits)}


def verify_consumer_closure(root):
    """零命中须覆盖十个消费者根及强制 CHANGELOG 文件，且类型全部正确。"""
    closure = scan_consumer_closure(root)
    missing = [row["path"] for row in closure["roots"] if not row["exists"]]
    if missing:
        raise MigrationError("migration_closure_roots_incomplete:" + ",".join(missing))
    if closure["active_legacy_hits"] or closure["unclassified_hits"]:
        raise MigrationError("migration_consumer_closure_not_zero:" + str(closure["active_legacy_hits"]))
    return closure


def mapped_library_path(relative):
    parts = PurePosixPath(relative).parts
    if relative == "canonical/templates/README.md":
        return "governance/authoring/templates.md"
    if relative == "canonical/layouts/manifest.json":
        return "governance/migration/provenance/layout-manifest-v1.json"
    if relative == "canonical/components/chart-palettes/pool.json":
        return "reference/pools/chart-palettes/pool.json"
    if relative.startswith("canonical/presets/scene-presets/"):
        return "reference/sources/scene-presets/" + relative.removeprefix("canonical/presets/scene-presets/")
    if len(parts) > 2 and parts[0] == "canonical":
        if parts[1] == "axes":
            if len(parts) < 5 or parts[2] not in AXIS_FOLDERS:
                raise MigrationError("migration_unknown_axis_path:" + relative)
            return "canonical/" + AXIS_FOLDERS[parts[2]] + "/" + "/".join(parts[3:])
        if parts[1] in LEGACY_FOLDERS:
            return "canonical/" + LEGACY_FOLDERS[parts[1]] + "/" + "/".join(parts[2:])
        if parts[1] not in {"semantic", "visual", "executable", "collections"}:
            raise MigrationError("migration_unknown_canonical_path:" + relative)
    return relative


def transformed_library_bytes(relative, body):
    if relative != "library.json":
        return body
    from .storage import canonical_json_bytes
    declaration = json.loads(body)
    declaration["schema_version"] = 2
    declaration["protocol"].update(resolver="asset_resolver/v2", builder="capability_manifest/template-registry/v2")
    from .asset_resolver import ASSET_ID_RE
    declaration["protocol"]["asset_id_pattern"] = ASSET_ID_RE.pattern
    return canonical_json_bytes(declaration)


def materialize_shadow_library(source, target):
    """仅供 stage 的字节转换器；不授予 stage/发布资格，不改来源库。"""
    source, target = Path(source).absolute(), Path(target).absolute()
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise MigrationError("migration_shadow_not_isolated")
    if target.exists() and any(target.iterdir()):
        raise MigrationError("migration_shadow_not_empty")
    target.mkdir(parents=True, exist_ok=True)
    mapping, seen = [], set()
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source).as_posix()
        if path.is_symlink():
            raise MigrationError("migration_symlink_rejected:" + relative)
        if not path.is_file() or relative.startswith("catalog/") or path.name.startswith(".maintenance"):
            continue
        destination = mapped_library_path(relative)
        if destination in seen:
            raise MigrationError("migration_target_collision:" + destination)
        seen.add(destination)
        before = file_state(source, relative)
        body = transformed_library_bytes(relative, read_evidence_bytes(source, relative))
        if file_state(source, relative) != before:
            raise MigrationError("migration_source_drift:" + relative)
        out = safe_path(target, destination)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("xb") as handle:
            handle.write(body)
            os.fchmod(handle.fileno(), before["mode"])
        mapping.append({"source": relative, "target": destination, "source_state": before,
                        "target_state": file_state(target, destination)})
    return mapping


def git_state(root):
    root = Path(root).absolute()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    raw = subprocess.check_output(["git", "status", "--porcelain=v1", "--no-renames", "-z", "--untracked-files=all"], cwd=root).decode()
    dirty = {}
    for entry in raw.split("\0"):
        if entry:
            path = entry[3:]
            if path in {"leo-ppt-generator/template-library/.maintenance.json", "leo-ppt-generator/template-library/.maintenance.lock"}:
                continue
            dirty[path] = {"status": entry[:2], "state": file_state(root, path)}
    return {"head": head, "dirty": dirty}


def _check_source(plan):
    state = git_state(plan["source_root"])
    if state["head"] != plan["base_revision"] or state["dirty"] != plan["dirty_snapshot"]:
        raise MigrationError("migration_delivery_head_or_dirty_drift")
    for path, expected in plan["source_snapshot"].items():
        if file_state(plan["source_root"], path) != expected:
            raise MigrationError("migration_source_drift:" + path)
    expected_paths = {path for path, row in plan["source_snapshot"].items() if row["type"] == "file"}
    if _migration_file_paths(plan["source_root"]) != expected_paths:
        raise MigrationError("migration_source_file_set_drift")


def _migration_file_paths(root):
    """与 preview 相同的完整交付集合；库内附属字节不能由 gitignore 隐藏。"""
    root = Path(root).absolute()
    listed = subprocess.check_output(["git", "ls-files", "-c", "-o", "--exclude-standard", "-z",
        "--", "leo-ppt-generator", "CHANGELOG.md"], cwd=root).decode().split("\0")
    candidates = {path for path in listed if path}
    library = safe_path(root, "leo-ppt-generator/template-library")
    if library.exists():
        for path in library.rglob("*"):
            if path.is_symlink() or not path.is_dir():
                candidates.add(path.relative_to(root).as_posix())
    candidates -= {"leo-ppt-generator/template-library/.maintenance.json",
                   "leo-ppt-generator/template-library/.maintenance.lock"}
    return {path for path in candidates if file_state(root, path)["type"] != "absent"}


def _check_work_root(source, work):
    source, work = Path(source).absolute(), Path(work).absolute()
    if any(path.is_symlink() for path in (work, *work.parents)):
        raise MigrationError("migration_work_root_symlink")
    if work == source:
        raise MigrationError("migration_work_root_is_delivery")
    if work.is_relative_to(source):
        result = subprocess.run(["git", "check-ignore", "-q", "--no-index", str(work.relative_to(source)) + "/"], cwd=source)
        if result.returncode:
            raise MigrationError("migration_work_root_must_be_ignored")
    return work


def _write_sealed(path, body, field="receipt_digest"):
    body = {key: value for key, value in body.items() if key != field}
    body[field] = digest(body)
    if path.exists():
        if json.loads(read_evidence_bytes(path.parent, path.name)) != body:
            raise MigrationError("migration_immutable_artifact_conflict:" + path.name)
    else:
        atomic_write_json(path, body)
        fsync_directory(path.parent)
    return body


def verify_value_gate(root, reference):
    """预迁移门必须引用真实双 lane 导出及旧链；缺失不会降级为成功。"""
    from .quality_replay import verify_legacy_baseline
    from .application.expression_pipeline import load_committed_input
    from .quality_metrics import deck_quality_for_run
    value = sealed(load_document(root, reference), "receipt_digest")
    if value.get("kind") != "expression-pre-migration-value" or value.get("status") != "passed":
        raise MigrationError("migration_pre_value_gate_missing")
    verify_legacy_baseline(root, value["baseline"])
    relations, joins = {}, set()
    for row in value["cases"]:
        run = safe_path(root, row["run"])
        committed = load_committed_input(run)
        page = next(page for page in committed["payload"]["pack"]["pages"] if page["page_id"] == row["page_id"])
        quality = deck_quality_for_run(run, include_visual=False)
        if any(status != "passed" for status in quality["channels"].values()):
            raise MigrationError("migration_pre_value_export_failed")
        exported = quality["lanes"][row["lane"]]["pages"][row["page_id"]]
        actual = file_reference(root, (run / exported["artifact"]).relative_to(root).as_posix())
        if row["artifact"] != actual or exported["status"] != "passed" or row["relation"] != page["expression"]["relation"]["kind"]:
            raise MigrationError("migration_pre_value_artifact_mismatch")
        review = load_document(root, row["review"])
        if (review.get("artifact") != actual or not review.get("reviewer") or not review.get("rationale")
                or review.get("severe_defects") != 0 or review.get("relation_verified") is not True):
            raise MigrationError("migration_pre_value_review_missing")
        identity = (row["run"], row["page_id"], row["lane"])
        if identity in joins:
            raise MigrationError("migration_pre_value_duplicate_page")
        joins.add(identity)
        relations.setdefault(row["relation"], set()).add(row["lane"])
    if len([lanes for lanes in relations.values() if lanes == {"image", "render:html"}]) < 3:
        raise MigrationError("migration_pre_value_dual_lane_incomplete")
    return value


def _replacement_scope(path):
    """仅替换当前授权包内的活动消费者；事务执行 owner 在同一批内保持不变。"""
    allowed = path == "CHANGELOG.md" or any(
        path == root if root in CLOSURE_FILES else path.startswith(root + "/")
        for root in CLOSURE_ROOTS if root.startswith("leo-ppt-generator/")
    )
    if not allowed or Path(path).suffix.lower() not in {".py", ".json", ".md", ".txt", ".yaml", ".yml", ".sh", ".js", ".html", ".toml"}:
        raise MigrationError("migration_consumer_replacement_scope_invalid:" + path)
    prefix = "leo-ppt-generator/runtime/src/leo_ppt_generator/"
    if path.startswith(prefix):
        relative = path[len(prefix):]
        if relative in {"library_migration.py", "schemas/migration-plan-v2.schema.json", "storage.py"}:
            raise MigrationError("migration_transaction_owner_replacement_forbidden:" + path)


def _replacement_bytes(row, *, require_text=True):
    import base64
    try:
        body = base64.b64decode(row["payload"], validate=True)
        if require_text:
            body.decode("utf-8")
    except (ValueError, UnicodeError, TypeError, KeyError) as exc:
        raise MigrationError("migration_consumer_payload_invalid") from exc
    if hashlib.sha256(body).hexdigest() != row["sha256"]:
        raise MigrationError("migration_consumer_payload_hash_mismatch")
    return body


def _target_evidence_manifest(source, work, reference):
    if reference is None:
        return {}, None
    document = load_document(work, reference)
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).parent / "schemas/migration-plan-v2.schema.json").read_text())
    validator = Draft202012Validator({"$ref": "#/$defs/target_evidence", "$defs": schema["$defs"]})
    if next(validator.iter_errors(document), None) is not None:
        raise MigrationError("migration_target_evidence_manifest_invalid")
    result, seen = {}, set()
    prefix = "leo-ppt-generator/template-library/evidence/"
    for row in document["files"]:
        if not isinstance(row, dict) or set(row) != {"path", "expected", "target"}:
            raise MigrationError("migration_target_evidence_manifest_invalid")
        path = row["path"]
        safe_path(source, path)
        if path in seen or not path.startswith(prefix):
            raise MigrationError("migration_target_evidence_scope_invalid:" + str(path))
        seen.add(path)
        expected = row["expected"]
        target = row["target"]
        if (not isinstance(expected, dict) or set(expected) != {"type", "sha256", "mode"}
                or expected["type"] not in {"file", "absent"}
                or not isinstance(target, dict) or set(target) != {"payload", "sha256", "mode"}):
            raise MigrationError("migration_target_evidence_manifest_invalid")
        _replacement_bytes(target, require_text=False)
        if file_state(source, path) != expected:
            raise MigrationError("migration_target_evidence_source_drift:" + path)
        result[path] = {"operation": "evidence", "source": path, "expected": expected, **target}
    if prefix + "capability-receipts.json" not in result:
        raise MigrationError("migration_target_evidence_active_index_missing")
    return result, document


def _apply_target_evidence(target, evidence):
    for path, row in evidence.items():
        relative = path[len("leo-ppt-generator/template-library/"):]
        destination = safe_path(target, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_replacement_bytes(row, require_text=False))
        destination.chmod(row["mode"])


def _consumer_replacements(source, work, reference):
    if reference is None:
        return {}
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).parent / "schemas/migration-plan-v2.schema.json").read_text())
    document = load_document(work, reference)
    validator = Draft202012Validator({"$ref": "#/$defs/consumer_replacements", "$defs": schema["$defs"]})
    if next(validator.iter_errors(document), None) is not None:
        raise MigrationError("migration_consumer_replacements_schema_mismatch")
    result = {}
    for row in document["replacements"]:
        path = row["path"]
        safe_path(source, path)
        _replacement_scope(path)
        if path in result:
            raise MigrationError("migration_consumer_replacement_duplicate:" + path)
        if row["expected"]["type"] != "file" or file_state(source, path) != row["expected"]:
            raise MigrationError("migration_consumer_source_drift:" + path)
        _replacement_bytes(row["target"])
        result[path] = {"operation": "replace", "source": path, "expected": row["expected"], **row["target"]}
    return result


def _catalog_subprocess(package, action, *arguments):
    """显式导入目标源码；stdout 只接受完整结果，不沿用宿主进程模块缓存。"""
    package = Path(package).absolute()
    code = """
import hashlib, json, os, sys
from pathlib import Path
import leo_ppt_generator
package = Path(os.environ['LEO_PPT_BUNDLE'])
expected = package / 'runtime/src/leo_ppt_generator'
if Path(leo_ppt_generator.__file__).resolve().parent != expected.resolve():
    raise ValueError('migration_target_runtime_import_mismatch')
from leo_ppt_generator.template_catalog import build_catalog, publish_catalog, read_catalog, scan_records, LibraryContext
from leo_ppt_generator.library_migration import verify_catalog_files
from leo_ppt_generator.qualification import environment_fingerprint
library = package / 'template-library'
if sys.argv[1] == 'build':
    result = build_catalog(library)
    # The isolated target must have a readable current pointer before evidence
    # checks. This publication is confined to the temporary target tree.
    publish_catalog(library, result)
elif sys.argv[1] == 'inspect':
    registry = read_catalog(LibraryContext(library))
    pairings = json.loads((library / 'catalog/generations' / registry['catalog_generation'] / 'views/execution-pairings.json').read_text())
    result = {'registry': registry, 'records': scan_records(library), 'pairings': pairings, 'catalog': verify_catalog_files(library)}
elif sys.argv[1] == 'verify-files':
    result = verify_catalog_files(library)
elif sys.argv[1] == 'evidence-check':
    from leo_ppt_generator.asset_resolver import AssetResolver
    from leo_ppt_generator.qualification import asset_generation, layout_capability_contract, load_receipts, verify_capability_evidence, file_reference, RECEIPTS_PATH
    resolver = AssetResolver(context=LibraryContext(library))
    generation = asset_generation(library)
    if generation != sys.argv[2]:
        raise ValueError('migration_target_evidence_generation_mismatch')
    receipts = load_receipts(library)
    required = set(json.loads(sys.argv[3]))
    seen = {row.get('asset_id') for row in receipts}
    if not required or required != seen:
        raise ValueError('migration_target_evidence_asset_scope_mismatch')
    verified, identities = [], set()
    environment = environment_fingerprint()
    for receipt in receipts:
        if receipt.get('receipt_id') in identities:
            raise ValueError('migration_target_evidence_duplicate_receipt')
        identities.add(receipt.get('receipt_id'))
        layout = resolver.resolve(receipt['asset_id'])
        contract, dependencies = layout_capability_contract(layout, resolver=resolver, lane=receipt['lane'])
        if (receipt['lane'] not in contract['lanes'] or receipt['relation'] not in contract['relations']
                or contract['gaps'].get(receipt['lane'])):
            raise ValueError('migration_target_evidence_owner_contract_mismatch')
        qualification = verify_capability_evidence(receipt, library_root=library, asset_generation=generation,
            expected_dependencies=dependencies, environment=environment)
        verified.append({'receipt_id': receipt['receipt_id'], 'evidence_digest': receipt['evidence_digest'],
                         'qualification': qualification})
    result = {'asset_generation': generation, 'active_index': file_reference(library, RECEIPTS_PATH),
              'verified_receipts': sorted(verified, key=lambda row: row['receipt_id'])}
elif sys.argv[1] == 'quality-replay':
    from leo_ppt_generator.quality_replay import evaluate_quality_replay
    result = evaluate_quality_replay(Path(sys.argv[2]), json.loads(sys.argv[3]))
else:
    raise ValueError('migration_target_catalog_action_invalid')
owners = {name: hashlib.sha256((expected / name).read_bytes()).hexdigest() for name in
          ('template_catalog.py', 'asset_resolver.py', 'qualification.py', 'execution_pairing.py')}
print(json.dumps({'result': result, 'environment': environment_fingerprint(), 'owners': owners}, ensure_ascii=False, sort_keys=True))
"""
    environment = dict(os.environ, PYTHONPATH=str(package / "runtime/src"),
                       LEO_PPT_BUNDLE=str(package), PYTHONDONTWRITEBYTECODE="1")
    try:
        process = subprocess.run([sys.executable, "-c", code, action, *arguments], cwd=package,
                                 env=environment, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired as exc:
        raise MigrationError("migration_target_catalog_timeout:" + action) from exc
    if process.returncode != 0:
        raise MigrationError("migration_target_catalog_" + action + "_failed:" + process.stderr[-1000:])
    try:
        document = json.loads(process.stdout)
        if set(document) != {"result", "environment", "owners"}:
            raise ValueError("fields")
        root = package / "runtime/src/leo_ppt_generator"
        if document["owners"] != {name: file_reference(root, name)["sha256"] for name in
                ("template_catalog.py", "asset_resolver.py", "qualification.py", "execution_pairing.py")}:
            raise ValueError("owners")
    except (TypeError, ValueError, KeyError) as exc:
        raise MigrationError("migration_target_catalog_output_invalid") from exc
    return document


def _uses_target_runtime(plan):
    return bool(plan.get("target_evidence")) or any(row["operation"] == "replace" and path.startswith("leo-ppt-generator/runtime/src/leo_ppt_generator/")
               for path, row in plan["mapping"].items())


def _verify_target_evidence(plan, root):
    manifest = plan.get("target_evidence")
    if manifest is None:
        return None
    return _catalog_subprocess(Path(root) / "leo-ppt-generator", "evidence-check",
        manifest["asset_generation"], json.dumps(manifest["required_assets"], ensure_ascii=False))


def _migration_catalog_details(plan, root):
    package = Path(root) / "leo-ppt-generator"
    _verify_target_evidence(plan, root)
    if _uses_target_runtime(plan):
        return _catalog_subprocess(package, "inspect")["result"]
    from .template_catalog import LibraryContext, read_catalog, scan_records
    library = package / "template-library"
    registry = read_catalog(LibraryContext(library))
    prefix = "catalog/generations/" + registry["catalog_generation"] + "/"
    return {"registry": registry, "records": scan_records(library),
            "pairings": json.loads(read_evidence_bytes(library, prefix + "views/execution-pairings.json")),
            "catalog": verify_catalog_files(library)}


def _migration_catalog_files(plan, root):
    package = Path(root) / "leo-ppt-generator"
    _verify_target_evidence(plan, root)
    if _uses_target_runtime(plan):
        return _catalog_subprocess(package, "verify-files")["result"]
    return verify_catalog_files(package / "template-library")


def _migration_visual_replay(plan, staging, work, reference):
    if _uses_target_runtime(plan):
        return _catalog_subprocess(Path(staging) / "leo-ppt-generator", "quality-replay", str(work),
                                   json.dumps(reference))["result"]
    from .quality_replay import evaluate_quality_replay
    return evaluate_quality_replay(work, reference)


def _build_catalog_in_target_runtime(source, target_library, replacements, paths, evidence_manifest=None):
    """在替换后的目标 runtime 子进程中派生 catalog；不信任 delivery 旧 owner。"""
    package = Path(source) / "leo-ppt-generator"
    if not (package / "runtime/src").is_dir() or not (package / "assets").is_dir():
        raise MigrationError("migration_target_runtime_unavailable")
    target_root = Path(tempfile.mkdtemp(prefix="leo-migration-target-runtime-")).resolve()
    target_package = target_root / "leo-ppt-generator"
    try:
        for relative in sorted(paths):
            if not relative.startswith(("leo-ppt-generator/runtime/src/", "leo-ppt-generator/assets/")):
                continue
            before = file_state(source, relative)
            body = read_evidence_bytes(source, relative)
            if file_state(source, relative) != before:
                raise MigrationError("migration_source_drift:" + relative)
            destination = safe_path(target_root, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
            destination.chmod(before["mode"])
        shutil.copytree(target_library, target_package / "template-library")
        for path, row in replacements.items():
            if not path.startswith("leo-ppt-generator/runtime/src/"):
                continue
            destination = safe_path(target_root, path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(_replacement_bytes(row))
            destination.chmod(row["mode"])
        result = _catalog_subprocess(target_package, "build")
        if evidence_manifest:
            registry = result["result"]["registry.json"]
            evidence = _catalog_subprocess(target_package, "evidence-check", registry["asset_generation"],
                                            json.dumps(evidence_manifest["required_assets"], ensure_ascii=False))["result"]
            if evidence["asset_generation"] != evidence_manifest["asset_generation"]:
                raise MigrationError("migration_target_evidence_generation_mismatch")
        from .qualification import environment_fingerprint
        source_environment = environment_fingerprint()
        if {key: value for key, value in result["environment"].items() if key != "execution_source_digest"} != {
                key: value for key, value in source_environment.items() if key != "execution_source_digest"}:
            raise MigrationError("migration_target_environment_mismatch")
        return result["result"]
    finally:
        shutil.rmtree(target_root, ignore_errors=True)


def preview_migration(source_root, out_plan, *, prerequisite=None, consumer_replacements=None, target_evidence=None):
    """只写唯一计划；临时转换用来计算真实目标 hash，不触碰 delivery。"""
    import base64
    from .template_catalog import build_catalog
    from .storage import canonical_json_bytes
    source = Path(source_root).absolute()
    out = Path(out_plan).absolute()
    work = _check_work_root(source, out.parent)
    if out.name != "migration-plan.json":
        raise MigrationError("migration_unique_plan_name_required")
    state = git_state(source)
    replacements = _consumer_replacements(source, work, consumer_replacements)
    evidence, evidence_manifest = _target_evidence_manifest(source, work, target_evidence)
    library = source / "leo-ppt-generator/template-library"
    paths = _migration_file_paths(source)
    descriptors = {}
    with tempfile.TemporaryDirectory(prefix="leo-migration-preview-") as temporary:
        target = Path(temporary).resolve() / "library"
        rows = materialize_shadow_library(library, target)
        _apply_target_evidence(target, evidence)
        for row in rows:
            before, after = "leo-ppt-generator/template-library/" + row["source"], "leo-ppt-generator/template-library/" + row["target"]
            descriptors[after] = {"operation": "normalize" if row["source"] == "library.json" else "copy",
                "source": before, "source_relative_to_library": row["source"], "sha256": row["target_state"]["sha256"],
                "mode": row["target_state"]["mode"]}
            paths.add(before)
        outputs = (_build_catalog_in_target_runtime(source, target, {**replacements, **evidence}, paths, evidence_manifest)
                   if evidence_manifest or any(path.startswith("leo-ppt-generator/runtime/src/leo_ppt_generator/") for path in replacements)
                   else build_catalog(target))
        generation = outputs["registry.json"]["catalog_generation"]
        catalog = {"catalog/generations/" + generation + "/" + path: value for path, value in outputs.items()}
        catalog["catalog/current.json"] = {"kind": "template-catalog-pointer", "schema_version": 2, "generation": generation}
        for path, body in catalog.items():
            raw = canonical_json_bytes(body)
            descriptors["leo-ppt-generator/template-library/" + path] = {"operation": "derived", "sha256": hashlib.sha256(raw).hexdigest(),
                "mode": 0o644, "payload": base64.b64encode(raw).decode()}
    for path in sorted(paths):
        if not path.startswith("leo-ppt-generator/template-library/"):
            before = file_state(source, path)
            descriptors[path] = {"operation": "copy", "source": path, "sha256": before["sha256"], "mode": before["mode"]}
    if set(replacements) - paths:
        raise MigrationError("migration_consumer_source_not_in_snapshot")
    descriptors.update(replacements)
    descriptors.update(evidence)
    touched = paths | set(descriptors)
    snapshot = {path: file_state(source, path) for path in sorted(touched)}
    deletes = [{"path": path, "expected": snapshot[path], "after_publish": snapshot[path], "already_absent": "only-after-journaled-delete"}
               for path in sorted(paths - set(descriptors)) if snapshot[path]["type"] == "file"]
    gap = "migration_pre_value_gate_missing"
    if prerequisite is not None:
        verify_value_gate(work, prerequisite)
        gap = None
    closure = scan_consumer_closure(source)
    target_closure = _scan_consumer_closure(source, {path: _replacement_bytes(row) for path, row in replacements.items()})
    plan = {"schema_version": 2, "kind": PLAN_KIND, "phase": "preview", "gate": "U7-A" if gap else "U7-B",
        "source_root": str(source), "base_revision": state["head"], "dirty_snapshot": state["dirty"],
        "source_snapshot": snapshot, "closure": closure, "target_closure": target_closure,
        "target_closure_digest": digest(target_closure), "mapping": descriptors,
        "target_hashes": {path: row["sha256"] for path, row in sorted(descriptors.items())},
        "delete_allowlist": deletes, "allowlist_digest": digest(deletes), "prerequisite": prerequisite,
        "gaps": [gap] if gap else [], "target_evidence": evidence_manifest,
        "target_evidence_digest": digest(evidence_manifest) if evidence_manifest else None,
        "owner_sha256": file_reference(Path(__file__).parent, Path(__file__).name)["sha256"]}
    if evidence_manifest:
        expected_generation = evidence_manifest["asset_generation"]
        actual_generation = None
        # 生成 registry 是目标资产代的唯一权威输入。
        for path, row in descriptors.items():
            if path.endswith("/registry.json") and row.get("operation") == "derived":
                body = _target_bytes(plan, path)
                actual_generation = json.loads(body)["asset_generation"]
                break
        if actual_generation != expected_generation:
            raise MigrationError("migration_target_evidence_generation_mismatch")
    if git_state(source) != state or any(file_state(source, path) != before for path, before in snapshot.items()):
        raise MigrationError("migration_source_changed_during_preview")
    plan["plan_digest"] = digest(plan)
    validate_plan_contract(plan)
    return _write_sealed(out, plan, "plan_digest")


def _target_bytes(plan, path):
    import base64
    row = plan["mapping"][path]
    if row["operation"] in {"replace", "evidence"}:
        body = _replacement_bytes(row, require_text=row["operation"] == "replace")
    elif row["operation"] == "derived":
        body = base64.b64decode(row["payload"], validate=True)
    elif row["operation"] in {"copy", "normalize"}:
        body = read_evidence_bytes(plan["source_root"], row["source"])
        if row["operation"] == "normalize":
            body = transformed_library_bytes(row["source_relative_to_library"], body)
    else:
        raise MigrationError("migration_operation_invalid")
    if hashlib.sha256(body).hexdigest() != plan["target_hashes"][path]:
        raise MigrationError("migration_target_hash_mismatch:" + path)
    return body


def stage_migration(plan_path, staging_root, *, checkpoint=None):
    """完整独立 worktree 只接收执行快照；有外部 dirty 的 shadow 不可覆盖。"""
    plan_path = Path(plan_path).absolute()
    work = plan_path.parent
    plan_ref = file_reference(work, plan_path.name)
    plan = validate_plan(load_document(work, plan_ref))
    verify_value_gate(work, plan["prerequisite"])
    if plan["owner_sha256"] != file_reference(Path(__file__).parent, Path(__file__).name)["sha256"]:
        raise MigrationError("migration_owner_changed")
    _check_source(plan)
    staging = _check_work_root(plan["source_root"], staging_root)
    if staging == Path(plan["source_root"]) or Path(plan["source_root"]).is_relative_to(staging):
        raise MigrationError("migration_shadow_not_isolated")
    state_path = work / "stage-journal.json"
    if not (staging / ".git").exists():
        if staging.exists() and any(staging.iterdir()):
            raise MigrationError("migration_shadow_not_empty")
        subprocess.run(["git", "worktree", "add", "--detach", str(staging), plan["base_revision"]], cwd=plan["source_root"], check=True, capture_output=True)
    top = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=staging, text=True).strip()
    if Path(top).absolute() != staging:
        raise MigrationError("migration_shadow_not_worktree")
    if state_path.exists():
        journal = sealed(json.loads(read_evidence_bytes(work, state_path.name)), "journal_digest")
        if journal["plan_digest"] != plan["plan_digest"] or journal["staging_root"] != str(staging):
            raise MigrationError("migration_stage_journal_conflict")
    else:
        state = git_state(staging)
        if state["head"] != plan["base_revision"] or state["dirty"]:
            raise MigrationError("migration_shadow_dirty")
        journal = {"phase": "stage", "plan_digest": plan["plan_digest"], "staging_root": str(staging), "files": {},
            "before": {path: file_state(staging, path) for path in plan["source_snapshot"]}}
    if set(git_state(staging)["dirty"]) - set(plan["source_snapshot"]):
        raise MigrationError("migration_shadow_foreign_dirty")
    for path in sorted(plan["target_hashes"], key=lambda name: (name == CURRENT, name)):
        row = plan["mapping"][path]
        desired = {"type": "file", "sha256": row["sha256"], "mode": row["mode"]}
        actual = file_state(staging, path)
        if journal.get("pending") == {"path": path, "state": desired} and actual == desired:
            journal["files"][path] = desired
        if path in journal["files"]:
            if actual != desired:
                raise MigrationError("migration_stage_external_drift:" + path)
            continue
        if actual != journal["before"][path]:
            raise MigrationError("migration_stage_external_drift:" + path)
        journal["pending"] = {"path": path, "state": desired}
        journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
        atomic_write_json(state_path, journal)
        compare_and_swap_file(staging, path, expected=actual, body=_target_bytes(plan, path), mode=row["mode"], checkpoint=checkpoint)
        journal["files"][path] = desired
        journal.pop("pending", None)
        journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
        atomic_write_json(state_path, journal)
    for row in plan["delete_allowlist"]:
        path = row["path"]
        actual = file_state(staging, path)
        absent = {"type": "absent", "sha256": None, "mode": None}
        if journal.get("pending") == {"path": path, "state": absent} and actual == absent:
            journal["files"][path] = absent
        if actual["type"] == "absent" and journal["files"].get(path, {}).get("type") == "absent":
            continue
        if actual != journal["before"][path]:
            raise MigrationError("migration_stage_delete_drift:" + path)
        journal["pending"] = {"path": path, "state": absent}
        journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
        atomic_write_json(state_path, journal)
        if actual["type"] == "file":
            _unlink_cas(staging, path, actual, checkpoint=checkpoint)
        journal["files"][path] = {"type": "absent", "sha256": None, "mode": None}
        journal.pop("pending", None)
        journal["journal_digest"] = digest({k: v for k, v in journal.items() if k != "journal_digest"})
        atomic_write_json(state_path, journal)
    _check_source(plan)
    _verify_target_closure(plan, staging)
    _verify_target_evidence(plan, staging)
    return _write_sealed(work / "stage-receipt.json", {"schema_version": 2, "kind": RECEIPT_KIND,
        "phase": "stage", "status": "passed", "plan": plan_ref, "plan_digest": plan["plan_digest"],
        "staging_root": str(staging), "staging_hashes": _staged_hashes(plan, staging),
        "journal": file_reference(work, state_path.name)})


def _staged_hashes(plan, staging):
    for row in plan["delete_allowlist"]:
        if file_state(staging, row["path"])["type"] != "absent":
            raise MigrationError("migration_staging_legacy_file_remains:" + row["path"])
    return _converged_hashes(plan, staging)


def _verify_target_closure(plan, root):
    closure = scan_consumer_closure(root)
    if closure != plan["target_closure"] or digest(closure) != plan["target_closure_digest"]:
        raise MigrationError("migration_target_closure_mismatch")
    return closure


def _converged_hashes(plan, root):
    actual_paths = _migration_file_paths(root)
    expected_paths = set(plan["target_hashes"])
    if actual_paths != expected_paths:
        raise MigrationError("migration_convergence_file_set_mismatch:" + json.dumps({
            "extra": sorted(actual_paths - expected_paths), "missing": sorted(expected_paths - actual_paths)}))
    hashes = {}
    for path in sorted(actual_paths):
        state = file_state(root, path)
        expected = {"type": "file", "sha256": plan["target_hashes"][path], "mode": plan["mapping"][path]["mode"]}
        if state != expected:
            raise MigrationError("migration_convergence_file_state_mismatch:" + path)
        hashes[path] = state["sha256"]
    return hashes


def verify_migration(plan_path, staging_root, out_receipt, *, visual_receipt=None):
    """结构验证与真实 U6-A 共同签发 publication-ready；缺一路保持 blocked。"""
    import uuid
    work, staging = Path(plan_path).absolute().parent, Path(staging_root).absolute()
    output = Path(out_receipt).absolute()
    if output.parent != work:
        raise MigrationError("migration_receipt_root_mismatch")
    plan_ref = file_reference(work, Path(plan_path).name)
    plan = validate_plan(load_document(work, plan_ref))
    staged_ref = file_reference(work, "stage-receipt.json")
    stage = receipt_document(work, staged_ref, "stage", plan_digest=plan["plan_digest"])
    if stage["staging_root"] != str(staging) or stage["plan"] != plan_ref:
        raise MigrationError("migration_stage_receipt_mismatch")
    _check_source(plan)
    attempt = work / "verify-attempts" / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    checks, gaps = {}, []
    hashes = None

    def check(name, action):
        try:
            details = action()
            evidence = {"status": "passed", "details": details}
        except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
            evidence = {"status": "failed", "reason": str(exc)}
            gaps.append(name + ":" + str(exc))
        evidence.update(plan_digest=plan["plan_digest"], gate=name, inputs_digest=digest(plan["target_hashes"]))
        path = attempt / (name + ".json")
        atomic_write_json(path, evidence)
        checks[name] = {"status": evidence["status"], "evidence": file_reference(work, path.relative_to(work).as_posix())}
        return evidence

    catalog_details = None

    def current_catalog():
        nonlocal catalog_details
        if catalog_details is None:
            catalog_details = _migration_catalog_details(plan, staging)
        return catalog_details

    library = staging / "leo-ppt-generator/template-library"
    check("asset-bytes", lambda: {"files": _staged_hashes(plan, staging)})
    check("identity-reference", lambda: {"records": current_catalog()["records"]})
    check("v2-catalog", lambda: {"catalog_generation": current_catalog()["registry"]["catalog_generation"]})

    def probe():
        view = current_catalog()["pairings"]
        if not view["candidates"] or {row["identity"]["lane"] for row in view["candidates"]} != {"render:html", "image"}:
            raise MigrationError("migration_real_probe_qualification_incomplete")
        return view

    check("probe", probe)

    check("consumer-closure", lambda: (_verify_target_closure(plan, staging), verify_consumer_closure(staging))[1])

    def bundle_check():
        package = staging / "leo-ppt-generator"
        command = [str(Path(plan["source_root"]) / "leo-ppt-generator/runtime/.venv/bin/python"), "-m", "unittest", "tests.test_library_bundle"]
        log = attempt / "bundle.log"
        with log.open("wb") as handle:
            process = subprocess.run(command, cwd=package, env=dict(os.environ, PYTHONPATH="runtime/src", LEO_PPT_BUNDLE=str(package)),
                                     stdout=handle, stderr=subprocess.STDOUT)
        text = log.read_text()
        if process.returncode != 0 or not re.search(r"Ran [1-9][0-9]* tests", text) or not re.search(r"^OK(?:\s|$)", text, re.M):
            raise MigrationError("migration_bundle_validation_failed:" + str(process.returncode))
        return {"command": command, "exit_code": process.returncode, "log": file_reference(work, log.relative_to(work).as_posix())}

    check("bundle", bundle_check)
    check("manifest-hashes", lambda: {"files": _staged_hashes(plan, staging), "catalog": _migration_catalog_files(plan, staging)})
    visual_status = "blocked"
    if visual_receipt is None:
        gaps.append("migration_u6a_receipt_missing")
    else:
        visual = sealed(load_document(work, visual_receipt), "receipt_digest")
        live = _migration_visual_replay(plan, staging, work, visual["plan"])
        if (visual == live and live["status"] == "passed" and live["phase"] == "U6-A" and live["publication_ready"]):
            visual_status = "passed"
        else:
            gaps.append("migration_u6a_not_passed_or_stale")
    hashes = _staged_hashes(plan, staging)
    result = {"schema_version": 2, "kind": RECEIPT_KIND, "phase": "verify", "status": "passed" if not gaps else "blocked",
        "publication_ready": not gaps, "plan": plan_ref, "plan_digest": plan["plan_digest"], "stage": staged_ref,
        "staging_root": str(staging), "staging_hashes": hashes, "checks": checks,
        "visual_receipt": visual_receipt, "visual_status": visual_status, "gaps": gaps}
    return _write_sealed(output, result)


def _verified_for_publication(work, plan_ref, verified_ref):
    plan = validate_plan(load_document(work, plan_ref))
    if plan["owner_sha256"] != file_reference(Path(__file__).parent, Path(__file__).name)["sha256"]:
        raise MigrationError("migration_owner_changed")
    verify_value_gate(work, plan["prerequisite"])
    receipt = receipt_document(work, verified_ref, "verify", plan_digest=plan["plan_digest"])
    if (receipt.get("plan") != plan_ref or receipt.get("publication_ready") is not True
            or set(receipt.get("checks", {})) != STRUCTURAL_GATES
            or any(row["status"] != "passed" for row in receipt["checks"].values())):
        raise MigrationError("migration_publication_not_verified")
    for gate, row in receipt["checks"].items():
        evidence = load_document(work, row["evidence"])
        if (evidence.get("gate") != gate or evidence.get("status") != "passed" or evidence.get("plan_digest") != plan["plan_digest"]
                or evidence.get("inputs_digest") != digest(plan["target_hashes"])):
            raise MigrationError("migration_verification_evidence_stale")
        if gate == "bundle":
            details = evidence["details"]
            log = verify_reference(work, details["log"]).decode()
            if details["exit_code"] != 0 or not re.search(r"Ran [1-9][0-9]* tests", log) or not re.search(r"^OK(?:\s|$)", log, re.M):
                raise MigrationError("migration_bundle_receipt_invalid")
    staging = Path(receipt["staging_root"])
    if receipt["staging_hashes"] != _staged_hashes(plan, staging):
        raise MigrationError("migration_verified_manifest_mismatch")
    verify_consumer_closure(staging)
    _verify_target_closure(plan, staging)
    _migration_catalog_details(plan, staging)
    visual = sealed(load_document(work, receipt["visual_receipt"]), "receipt_digest")
    live = _migration_visual_replay(plan, staging, work, visual["plan"])
    if visual != live or live["status"] != "passed" or live["phase"] != "U6-A" or not live["publication_ready"]:
        raise MigrationError("migration_u6a_not_passed_or_stale")
    return plan, receipt


def _check_untouched(plan):
    state = git_state(plan["source_root"])
    if state["head"] != plan["base_revision"]:
        raise MigrationError("migration_delivery_head_drift")
    touched = set(plan["source_snapshot"])
    outside = lambda rows: {path: value for path, value in rows.items() if path not in touched}
    if outside(state["dirty"]) != outside(plan["dirty_snapshot"]):
        raise MigrationError("migration_external_dirty_drift")


def _save_original(work, delivery, path, state):
    if state["type"] == "absent":
        return None
    backup = "backups/" + digest({"path": path, "state": state}) + ".bin"
    target = safe_path(work, backup)
    body = read_evidence_bytes(delivery, path)
    if hashlib.sha256(body).hexdigest() != state["sha256"]:
        raise MigrationError("migration_backup_source_drift:" + path)
    if target.exists():
        if read_evidence_bytes(work, backup) != body:
            raise MigrationError("migration_backup_conflict:" + path)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        fsync_directory(work)
        with target.open("xb") as handle:
            handle.write(body); handle.flush(); os.fsync(handle.fileno())
        fsync_directory(target.parent)
    return file_reference(work, backup)


def fsync_directory(path):
    """迁移持久化屏障不能把目录同步失败降级为成功。"""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_journal(path, journal):
    if journal.get("phase") == "publish":
        journal["journal_generation"] += 1
    journal["journal_digest"] = digest({key: value for key, value in journal.items() if key != "journal_digest"})
    atomic_write_json(path, journal)
    fsync_directory(path.parent)


def _publication_identity(plan):
    return {"plan_digest": plan["plan_digest"], "base_revision": plan["base_revision"],
            "transaction_id": digest({"plan": plan["plan_digest"], "base": plan["base_revision"],
                                      "delivery": str(Path(plan["source_root"]).absolute())})}


def _check_publication_journal(plan, journal):
    sealed(journal, "journal_digest")
    if (journal.get("schema_version") != 2 or journal.get("phase") != "publish"
            or any(journal.get(key) != value for key, value in _publication_identity(plan).items())
            or type(journal.get("journal_generation")) is not int or journal["journal_generation"] < 1
            or journal.get("status") not in {"running", "passed", "restoring", "restored", "blocked"}
            or not isinstance(journal.get("files"), list)):
        raise MigrationError("migration_publication_identity_mismatch")
    seen = set()
    for row in journal.get("files", []):
        if not isinstance(row, dict):
            raise MigrationError("migration_publication_journal_state_mismatch")
        path = row.get("path")
        if path in seen or path not in plan["target_hashes"]:
            raise MigrationError("migration_publication_journal_scope_mismatch")
        seen.add(path)
        expected = {"type": "file", "sha256": plan["target_hashes"][path], "mode": plan["mapping"][path]["mode"]}
        before = plan["source_snapshot"][path]
        backup = row.get("backup")
        if (row.get("before") != before or row.get("after") != expected
                or row.get("target_sha256") != expected["sha256"]
                or row.get("status") not in {"prepared", "replaced", "restored", "external-drift"}
                or (before["type"] == "absent" and backup is not None)
                or (before["type"] == "file" and (not isinstance(backup, dict) or backup != {
                    "path": "backups/" + digest({"path": path, "state": before}) + ".bin", "sha256": before["sha256"]}))):
            raise MigrationError("migration_publication_journal_state_mismatch")
    return journal


def _publication_marker(work, plan, journal, *, confirmed=False):
    path = Path(work) / "publication-marker.json"
    if not path.is_file() or path.is_symlink():
        raise MigrationError("migration_publication_marker_unconfirmed")
    marker = sealed(json.loads(read_evidence_bytes(work, path.name)), "marker_digest")
    if (marker.get("schema_version") != 2
            or any(marker.get(key) != value for key, value in _publication_identity(plan).items())
            or marker.get("state") not in {"prepared", "current-switched"}
            or type(marker.get("journal_generation")) is not int
            or not 1 <= marker["journal_generation"] <= journal["journal_generation"]):
        raise MigrationError("migration_publication_marker_unconfirmed")
    if confirmed and (marker["state"] != "current-switched"
            or marker["journal_generation"] != journal["journal_generation"]
            or marker.get("journal_digest") != journal["journal_digest"]
            or marker.get("current_sha256") != plan["target_hashes"].get(CURRENT)):
        raise MigrationError("migration_publication_marker_unconfirmed")
    return marker


def _confirm_publication(work, plan, journal, state):
    marker = {"schema_version": 2, **_publication_identity(plan), "state": state,
              "journal_generation": journal["journal_generation"], "journal_digest": journal["journal_digest"],
              "current_sha256": plan["target_hashes"][CURRENT]}
    marker["marker_digest"] = digest(marker)
    atomic_write_json(Path(work) / "publication-marker.json", marker)
    fsync_directory(work)
    return marker


def _verify_publication_confirmation(work, plan, published=None):
    journal = _check_publication_journal(plan, json.loads(read_evidence_bytes(work, "publication-progress.json")))
    if published is not None and any(published.get(key) != journal[key]
                                     for key in (*PUBLICATION_IDENTITY, "journal_generation")):
        raise MigrationError("migration_publication_receipt_stale")
    marker = _publication_marker(work, plan, journal, confirmed=True)
    if (journal["status"] != "passed" or journal.get("current_switched") is not True
            or {row["path"]: row["target_sha256"] for row in journal["files"]} != plan["target_hashes"]
            or any(row["status"] != "replaced" for row in journal["files"])):
        raise MigrationError("migration_publication_journal_incomplete")
    if published is not None:
        if (load_document(work, published["journal"]) != journal
                or load_document(work, published["marker"]) != marker):
            raise MigrationError("migration_publication_receipt_stale")
    return journal


def _recover_publication(work, plan):
    progress = Path(work) / "publication-progress.json"
    if not progress.exists():
        if (Path(work) / "publication-marker.json").exists():
            raise MigrationError("migration_publication_journal_missing")
        return 0
    journal = _check_publication_journal(plan, json.loads(read_evidence_bytes(work, progress.name)))
    _publication_marker(work, plan, journal)
    conflicts = _restore_entries(work, plan["source_root"], journal["files"])
    journal.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
    _write_journal(progress, journal)
    if conflicts:
        raise MigrationError("migration_restore_external_drift")
    return journal["journal_generation"]


def _unlink_cas(root, relative, expected, *, checkpoint=None):
    path = safe_path(root, relative)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if checkpoint:
            checkpoint("before_delete", relative)
        if file_state(root, relative) != expected:
            raise MigrationError("migration_cleanup_drift:" + relative)
        parent = os.stat(path.parent, follow_symlinks=False)
        pinned = os.fstat(fd)
        if (parent.st_dev, parent.st_ino) != (pinned.st_dev, pinned.st_ino):
            raise MigrationError("migration_parent_changed:" + relative)
        os.unlink(path.name, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)


def _restore_entries(work, delivery, entries):
    """只恢复仍等于本批目标状态的文件；外部改写留下并明确阻断。"""
    conflicts = []
    for row in reversed(entries):
        try:
            current = file_state(delivery, row["path"])
            if current == row["before"]:
                row["status"] = "restored"
                continue
            if current != row["after"]:
                raise MigrationError("migration_restore_external_drift")
            if row["before"]["type"] == "absent":
                _unlink_cas(delivery, row["path"], current)
            else:
                body = verify_reference(work, row["backup"])
                if hashlib.sha256(body).hexdigest() != row["before"]["sha256"]:
                    raise MigrationError("migration_backup_hash_mismatch")
                compare_and_swap_file(delivery, row["path"], expected=current, body=body, mode=row["before"]["mode"])
            row["status"] = "restored"
        except (ValueError, OSError) as exc:
            row["status"] = "external-drift"
            conflicts.append({"path": row["path"], "reason": str(exc)})
    return conflicts


def publish_targets(work, plan, staging, *, checkpoint=None):
    """受上层 verified gate 保护的文件事务；供真实故障注入测试单独观察。"""
    work, staging, delivery = Path(work), Path(staging), Path(plan["source_root"])
    journal_path = work / "publication-progress.json"
    if CURRENT not in plan["target_hashes"]:
        raise MigrationError("migration_current_target_missing")
    _check_untouched(plan)
    if journal_path.exists():
        old = _check_publication_journal(plan, json.loads(read_evidence_bytes(work, journal_path.name)))
        if old["status"] == "passed":
            try:
                confirmed = _verify_publication_confirmation(work, plan)
            except MigrationError as exc:
                if str(exc) != "migration_publication_marker_unconfirmed":
                    raise
            else:
                if all(file_state(delivery, row["path"]) == row["after"] for row in confirmed["files"]):
                    return confirmed
    generation = _recover_publication(work, plan)
    journal = {"schema_version": 2, "phase": "publish", **_publication_identity(plan),
               "journal_generation": generation, "status": "running", "current_switched": False, "files": []}
    _write_journal(journal_path, journal)
    _confirm_publication(work, plan, journal, "prepared")
    try:
        if checkpoint:
            checkpoint("after_prepared_marker", CURRENT)
        for path in sorted(plan["target_hashes"], key=lambda name: (name == CURRENT, name)):
            before = plan["source_snapshot"][path]
            if file_state(delivery, path) != before:
                raise MigrationError("migration_delivery_drift:" + path)
            body = read_evidence_bytes(staging, path)
            if hashlib.sha256(body).hexdigest() != plan["target_hashes"][path]:
                raise MigrationError("migration_staging_drift:" + path)
            after = {"type": "file", "sha256": plan["target_hashes"][path], "mode": plan["mapping"][path]["mode"]}
            row = {"path": path, "before": before, "after": after, "target_sha256": after["sha256"],
                   "backup": _save_original(work, delivery, path, before), "status": "prepared"}
            journal["files"].append(row)
            _write_journal(journal_path, journal)
            compare_and_swap_file(delivery, path, expected=before, body=body, mode=after["mode"], checkpoint=checkpoint)
            row["status"] = "replaced"
            journal["current_switched"] = journal["current_switched"] or path == CURRENT
            _write_journal(journal_path, journal)
            if checkpoint:
                checkpoint("after_replace", path)
        _check_untouched(plan)
        journal["status"] = "passed"
        _write_journal(journal_path, journal)
        if checkpoint:
            checkpoint("before_current_confirmation", CURRENT)
        _confirm_publication(work, plan, journal, "current-switched")
        if checkpoint:
            checkpoint("after_current_confirmation", CURRENT)
        return journal
    except BaseException:
        conflicts = _restore_entries(work, delivery, journal["files"])
        journal.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
        _write_journal(journal_path, journal)
        raise


def _seal_publication_receipt(work, plan, body, *, expected):
    """保留不可变分代凭证；根收据只以 CAS 更新到最新已确认的一代。"""
    journal = _verify_publication_confirmation(work, plan)
    marker = _publication_marker(work, plan, journal, confirmed=True)
    _check_untouched(plan)
    if any(file_state(plan["source_root"], row["path"]) != row["after"] for row in journal["files"]):
        raise MigrationError("migration_publication_delivery_drift")
    relative = "publications/" + journal["transaction_id"] + "/" + str(journal["journal_generation"])
    folder = safe_path(work, relative)
    folder.mkdir(parents=True, exist_ok=True)
    for directory in (folder, folder.parent, folder.parent.parent, Path(work)):
        fsync_directory(directory)
    _write_sealed(folder / "journal.json", journal, "journal_digest")
    _write_sealed(folder / "marker.json", marker, "marker_digest")
    result = _write_sealed(folder / "receipt.json", {**body,
        **{key: journal[key] for key in (*PUBLICATION_IDENTITY, "journal_generation")},
        "journal": file_reference(work, relative + "/journal.json"),
        "marker": file_reference(work, relative + "/marker.json")})
    compare_and_swap_file(work, "publication-receipt.json", expected=expected, body=json_document_bytes(result))
    return result


def publish_migration(plan_path, receipt_path, delivery_root, *, checkpoint=None):
    work = Path(plan_path).absolute().parent
    plan_ref = file_reference(work, Path(plan_path).name)
    receipt_ref = file_reference(work, Path(receipt_path).absolute().relative_to(work).as_posix())
    plan, verified = _verified_for_publication(work, plan_ref, receipt_ref)
    delivery = Path(delivery_root).absolute()
    if delivery != Path(plan["source_root"]).absolute():
        raise MigrationError("migration_delivery_root_mismatch")
    with locked_publication(delivery, plan_digest=plan["plan_digest"]):
        publication_path = work / "publication-receipt.json"
        expected_receipt = file_state(work, publication_path.name)
        if publication_path.exists():
            previous = receipt_document(work, file_reference(work, publication_path.name), "publish", plan_digest=plan["plan_digest"])
            if previous["verified"] != receipt_ref:
                raise MigrationError("migration_publication_receipt_conflict")
            _check_untouched(plan)
            try:
                journal = _verify_publication_confirmation(work, plan, previous)
            except MigrationError as exc:
                if str(exc) not in {"migration_publication_receipt_stale", "migration_publication_marker_unconfirmed",
                                    "migration_publication_journal_incomplete"}:
                    raise
            else:
                if all(file_state(delivery, row["path"]) == row["after"] for row in journal["files"]):
                    return previous
            # cleanup 的回滚不改不可变发布收据；只按原 journal 恢复后重放同一批。
            _recover_cleanup_rollback(work, plan, previous)
        _recover_publication(work, plan)
        _check_source(plan)
        publish_targets(work, plan, verified["staging_root"], checkpoint=checkpoint)
        return _seal_publication_receipt(work, plan, {"schema_version": 2, "kind": RECEIPT_KIND,
            "phase": "publish", "status": "passed", "plan": plan_ref, "plan_digest": plan["plan_digest"],
            "verified": receipt_ref, "delivery_root": str(delivery), "base_revision": plan["base_revision"],
            "dirty_before": plan["dirty_snapshot"]}, expected=expected_receipt)


def cleanup_migration(plan_path, publication_path, delivery_root, *, checkpoint=None):
    work, delivery = Path(plan_path).absolute().parent, Path(delivery_root).absolute()
    plan_ref = file_reference(work, Path(plan_path).name)
    plan = validate_plan(load_document(work, plan_ref))
    published_ref = file_reference(work, Path(publication_path).absolute().relative_to(work).as_posix())
    published = receipt_document(work, published_ref, "publish", plan_digest=plan["plan_digest"])
    if published.get("plan") != plan_ref or published["delivery_root"] != str(delivery) or plan["source_root"] != str(delivery):
        raise MigrationError("migration_cleanup_root_mismatch")
    plan, verified = _verified_for_publication(work, plan_ref, published["verified"])
    final_path = work / "cleanup-receipt.json"
    with locked_publication(delivery, plan_digest=plan["plan_digest"]) as marker:
        _verify_publication_confirmation(work, plan, published)
        if final_path.exists():
            final = _verify_final_state(work, file_reference(work, final_path.name), stage_receipt=verified["visual_receipt"])
            _release_cleanup_maintenance(work, final_path, marker, final)
            return final
        _check_untouched(plan)
        if any(file_state(delivery, path)["sha256"] != sha for path, sha in plan["target_hashes"].items()):
            raise MigrationError("migration_cleanup_delivery_drift")
        progress_path = work / "cleanup-progress.json"
        binding = {key: published[key] for key in (*PUBLICATION_IDENTITY, "journal_generation")}
        journal = {"schema_version": 2, "phase": "cleanup", **binding, "status": "running", "files": []}
        if progress_path.exists():
            previous = _check_cleanup_journal(plan, json.loads(read_evidence_bytes(work, progress_path.name)))
            if any(previous.get(key) != value for key, value in binding.items()):
                if (any(previous.get(key) != binding[key] for key in PUBLICATION_IDENTITY)
                        or previous.get("status") != "restored"
                        or any(file_state(delivery, row["path"]) != row["before"] for row in previous["files"])):
                    raise MigrationError("migration_cleanup_journal_stale")
            else:
                journal = previous
        entries = {row["path"]: row for row in journal["files"]}
        absent = {"type": "absent", "sha256": None, "mode": None}
        try:
            for allowed in plan["delete_allowlist"]:
                path = allowed["path"]
                state = file_state(delivery, path)
                if (state == absent and path in entries and entries[path]["before"] == allowed["expected"]
                        and entries[path].get("status") in {"prepared", "deleted"}):
                    entries[path]["status"] = "deleted"
                    continue
                if state != allowed["expected"]:
                    raise MigrationError("migration_cleanup_drift:" + path)
                row = {"path": path, "before": state, "after": absent, "backup": _save_original(work, delivery, path, state), "status": "prepared"}
                entries[path] = row
                journal["files"] = list(entries.values())
                _write_journal(progress_path, journal)
                _unlink_cas(delivery, path, state, checkpoint=checkpoint)
                row["status"] = "deleted"
                _write_journal(progress_path, journal)
                if checkpoint:
                    checkpoint("after_delete", path)
            staging_hashes = _staged_hashes(plan, Path(verified["staging_root"]))
            actual = _converged_hashes(plan, delivery)
            if actual != staging_hashes:
                raise MigrationError("migration_final_hash_convergence_failed")
            closure = verify_consumer_closure(delivery)
            _migration_catalog_files(plan, delivery)
            _check_untouched(plan)
            journal["status"] = "passed"
            _write_journal(progress_path, journal)
            result = {"schema_version": 2, "kind": RECEIPT_KIND, "phase": "cleanup", "status": "passed",
                "plan": plan_ref, **binding, "publication": published_ref, "delivery_root": str(delivery),
                "staging_hashes": staging_hashes, "delivery_hashes": actual, "closure": closure,
                "deleted": journal["files"], "journal": file_reference(work, progress_path.name)}
            with tempfile.TemporaryDirectory(prefix=".final-verify-", dir=work) as temporary:
                candidate = Path(temporary) / "cleanup-receipt.json"
                _write_sealed(candidate, result)
                final = _verify_final_state(work, file_reference(work, candidate.relative_to(work).as_posix()), stage_receipt=verified["visual_receipt"])
                if final_path.exists():
                    raise MigrationError("migration_final_receipt_conflict")
                candidate.rename(final_path)
                fsync_directory(work)
                if checkpoint:
                    checkpoint("after_final_receipt", final_path.name)
                _release_cleanup_maintenance(work, final_path, marker, final)
                return final
        except BaseException:
            # 最终收据已经持久化时只保留 maintenance，重试重新校验后解除。
            # 此处再回滚文件会使不可变最终收据指向不存在的状态。
            if final_path.exists():
                raise
            journal["status"] = "restoring"
            _write_journal(progress_path, journal)
            cleanup_conflicts = _restore_entries(work, delivery, journal["files"])
            publication = sealed(load_document(work, published["journal"]), "journal_digest")
            conflicts = cleanup_conflicts + _restore_entries(work, delivery, publication["files"])
            journal.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
            _write_journal(progress_path, journal)
            publication.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
            _write_journal(work / "publication-progress.json", publication)
            if not marker.exists():
                atomic_write_json(marker, {"schema_version": 1, "plan_digest": plan["plan_digest"]})
            raise


def _check_cleanup_journal(plan, journal):
    sealed(journal, "journal_digest")
    if (journal.get("phase") != "cleanup"
            or any(journal.get(key) != value for key, value in _publication_identity(plan).items())
            or type(journal.get("journal_generation")) is not int or journal["journal_generation"] < 1
            or journal.get("status") not in {"running", "passed", "restoring", "restored", "blocked"}
            or not isinstance(journal.get("files"), list)):
        raise MigrationError("migration_cleanup_journal_stale")
    allowlist = {row["path"]: row["expected"] for row in plan.get("delete_allowlist", [])}
    seen = set()
    for row in journal["files"]:
        if not isinstance(row, dict) or row.get("path") in seen or row.get("path") not in allowlist:
            raise MigrationError("migration_cleanup_journal_scope_mismatch")
        path = row["path"]
        seen.add(path)
        before = allowlist[path]
        if (row.get("before") != before or row.get("after") != {"type": "absent", "sha256": None, "mode": None}
                or row.get("status") not in {"prepared", "deleted", "restored", "external-drift"}
                or row.get("backup") != {"path": "backups/" + digest({"path": path, "state": before}) + ".bin",
                                          "sha256": before["sha256"]}):
            raise MigrationError("migration_cleanup_journal_state_mismatch")
    return journal


def _recover_cleanup_rollback(work, plan, published):
    progress = work / "cleanup-progress.json"
    if not progress.exists():
        raise MigrationError("migration_published_delivery_drift")
    cleanup = _check_cleanup_journal(plan, json.loads(read_evidence_bytes(work, progress.name)))
    if (any(cleanup.get(key) != published.get(key) for key in (*PUBLICATION_IDENTITY, "journal_generation"))
            or cleanup.get("status") not in {"restoring", "restored", "blocked"}):
        raise MigrationError("migration_published_delivery_drift")
    publication = _check_publication_journal(plan, load_document(work, published["journal"]))
    if (publication.get("status") != "passed" or any(publication.get(key) != published.get(key)
            for key in (*PUBLICATION_IDENTITY, "journal_generation"))):
        raise MigrationError("migration_publication_journal_conflict")
    live = _check_publication_journal(plan, json.loads(read_evidence_bytes(work, "publication-progress.json")))
    _publication_marker(work, plan, live)
    conflicts = _restore_entries(work, plan["source_root"], cleanup["files"])
    conflicts += _restore_entries(work, plan["source_root"], publication["files"])
    cleanup.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
    _write_journal(progress, cleanup)
    publication.update(status="blocked" if conflicts else "restored", restore_conflicts=conflicts)
    publication["journal_generation"] = max(publication["journal_generation"], live["journal_generation"])
    _write_journal(work / "publication-progress.json", publication)
    if conflicts:
        raise MigrationError("migration_restore_external_drift")


def _release_cleanup_maintenance(work, final_path, marker, final):
    """先有可重读的最终收据，再解除维护；断点重试不依赖内存通过状态。"""
    on_disk = receipt_document(work, file_reference(work, final_path.relative_to(work).as_posix()), "cleanup",
                               plan_digest=final["plan_digest"])
    if on_disk != final:
        raise MigrationError("migration_final_receipt_conflict")
    owner = json.loads(read_evidence_bytes(marker.parent, marker.name))
    if owner.get("plan_digest") != final["plan_digest"]:
        raise MigrationError("migration_maintenance_owner_conflict")
    marker.unlink()
    fsync_directory(marker.parent)


def safe_path(root, relative):
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or PurePosixPath(relative).is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise MigrationError("migration_path_invalid")
    root = Path(root).absolute()
    path = root / relative
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise MigrationError("migration_symlink_rejected:" + relative)
    return path


def file_state(root, relative):
    path = safe_path(root, relative)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"type": "absent", "sha256": None, "mode": None}
    if not stat.S_ISREG(metadata.st_mode):
        raise MigrationError("migration_file_type_invalid:" + relative)
    body = read_evidence_bytes(root, relative)
    after = path.lstat()
    if (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise MigrationError("migration_file_changed_during_read:" + relative)
    return {"type": "file", "sha256": hashlib.sha256(body).hexdigest(), "mode": stat.S_IMODE(metadata.st_mode)}


def sealed(document, field):
    if not isinstance(document, dict) or document.get(field) != digest({k: v for k, v in document.items() if k != field}):
        raise MigrationError("migration_" + field + "_mismatch")
    return document


def load_document(root, reference):
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise MigrationError("migration_reference_invalid")
    return json.loads(verify_reference(root, reference))


def validate_plan_contract(plan):
    from jsonschema import Draft202012Validator
    sealed(plan, "plan_digest")
    schema = json.loads((Path(__file__).parent / "schemas/migration-plan-v2.schema.json").read_text())
    if next(Draft202012Validator(schema).iter_errors(plan), None) is not None:
        raise MigrationError("migration_plan_schema_mismatch")
    if not Path(plan["source_root"]).is_absolute():
        raise MigrationError("migration_source_root_invalid")
    if [row["path"] for row in plan["closure"]["roots"]] != list(CLOSURE_ROOTS):
        raise MigrationError("migration_closure_roots_mismatch")
    if (plan["target_closure_digest"] != digest(plan["target_closure"])
            or plan["target_closure"]["roots"] != plan["closure"]["roots"]
            or plan["target_closure"]["signatures"] != plan["closure"]["signatures"]):
        raise MigrationError("migration_target_closure_mismatch")
    manifest = plan["target_evidence"]
    expected_evidence = {row["path"]: {"operation": "evidence", "source": row["path"],
                         "expected": row["expected"], **row["target"]}
                         for row in manifest["files"]} if manifest else {}
    actual_evidence = {path: row for path, row in plan["mapping"].items() if row["operation"] == "evidence"}
    if (plan["target_evidence_digest"] != (digest(manifest) if manifest else None)
            or actual_evidence != expected_evidence
            or manifest and len(expected_evidence) != len(manifest["files"])
            or manifest and "leo-ppt-generator/template-library/evidence/capability-receipts.json" not in expected_evidence):
        raise MigrationError("migration_target_evidence_mapping_invalid")
    if manifest:
        registries = [json.loads(_target_bytes(plan, path)) for path, row in plan["mapping"].items()
                      if path.endswith("/registry.json") and row["operation"] == "derived"]
        if len(registries) != 1 or registries[0].get("asset_generation") != manifest["asset_generation"]:
            raise MigrationError("migration_target_evidence_generation_mismatch")
    for path in plan["source_snapshot"]:
        safe_path(plan["source_root"], path)
        if not path.startswith("leo-ppt-generator/") and path != "CHANGELOG.md":
            raise MigrationError("migration_write_scope_invalid")
    for path, row in plan["mapping"].items():
        safe_path(plan["source_root"], path)
        if row["sha256"] != plan["target_hashes"].get(path):
            raise MigrationError("migration_mapping_hash_mismatch")
        if row["operation"] == "evidence":
            if (not path.startswith("leo-ppt-generator/template-library/evidence/")
                    or row["source"] != path or row["expected"] != plan["source_snapshot"].get(path)
                    or row["expected"]["type"] not in {"file", "absent"}):
                raise MigrationError("migration_target_evidence_mapping_invalid")
            _replacement_bytes(row, require_text=False)
        elif row["operation"] == "replace":
            _replacement_scope(path)
            if (row["source"] != path or row["expected"].get("type") != "file"
                    or row["expected"] != plan["source_snapshot"].get(path)):
                raise MigrationError("migration_consumer_mapping_source_mismatch")
            _replacement_bytes(row)
        elif row["operation"] == "derived":
            if not path.startswith("leo-ppt-generator/template-library/catalog/"):
                raise MigrationError("migration_derived_scope_invalid")
        else:
            if row["source"] not in plan["source_snapshot"] or plan["source_snapshot"][row["source"]]["type"] != "file":
                raise MigrationError("migration_mapping_source_invalid")
            safe_path(plan["source_root"], row["source"])
            if row["operation"] == "normalize" and (row.get("source_relative_to_library") != "library.json"
                    or row["source"] != "leo-ppt-generator/template-library/library.json"
                    or path != row["source"]):
                raise MigrationError("migration_normalization_scope_invalid")
            if row["operation"] == "copy":
                prefix = "leo-ppt-generator/template-library/"
                expected = prefix + mapped_library_path(row["source"][len(prefix):]) if row["source"].startswith(prefix) else row["source"]
                if path != expected:
                    raise MigrationError("migration_mapping_destination_invalid")
    return plan


def validate_plan(plan):
    validate_plan_contract(plan)
    if (plan.get("schema_version") != 2 or plan.get("kind") != PLAN_KIND or plan.get("phase") != "preview"
            or plan.get("gate") != "U7-B" or not re.fullmatch(r"[0-9a-f]{40}", plan.get("base_revision", ""))):
        raise MigrationError("migration_execution_plan_required")
    if (not isinstance(plan.get("source_snapshot"), dict) or not plan["source_snapshot"]
            or not isinstance(plan.get("target_hashes"), dict) or not plan["target_hashes"]):
        raise MigrationError("migration_snapshot_empty")
    if set(plan.get("mapping", {})) != set(plan["target_hashes"]):
        raise MigrationError("migration_mapping_incomplete")
    for path, sha in plan["target_hashes"].items():
        safe_path(plan["source_root"], path)
        if (not path.startswith("leo-ppt-generator/") and path != "CHANGELOG.md") or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise MigrationError("migration_write_scope_invalid")
        if plan["mapping"][path].get("sha256") != sha or path not in plan["source_snapshot"]:
            raise MigrationError("migration_mapping_hash_mismatch")
    deletes = plan.get("delete_allowlist")
    if not isinstance(deletes, list) or len({row["path"] for row in deletes}) != len(deletes):
        raise MigrationError("migration_delete_allowlist_invalid")
    for row in deletes:
        safe_path(plan["source_root"], row["path"])
        if (set(row) != {"path", "expected", "after_publish", "already_absent"}
                or row["path"] in plan["target_hashes"] or not row["path"].startswith("leo-ppt-generator/")
                or row["expected"] != plan["source_snapshot"].get(row["path"])
                or row["expected"].get("type") != "file" or row["after_publish"] != row["expected"]
                or row["already_absent"] != "only-after-journaled-delete"):
            raise MigrationError("migration_delete_allowlist_invalid")
    if plan.get("allowlist_digest") != digest(deletes):
        raise MigrationError("migration_allowlist_digest_mismatch")
    return plan


def receipt_document(root, reference, phase, *, plan_digest=None):
    receipt = sealed(load_document(root, reference), "receipt_digest")
    if (receipt.get("schema_version") != 2 or receipt.get("kind") != RECEIPT_KIND
            or receipt.get("phase") != phase or receipt.get("status") != "passed"
            or (plan_digest is not None and receipt.get("plan_digest") != plan_digest)):
        raise MigrationError("migration_" + phase + "_receipt_invalid")
    return receipt


def verify_catalog_files(library):
    """验证 current 指向完整不可变 v2 generation，含每个派生 view 的字节。"""
    library = Path(library)
    pointer = json.loads(read_evidence_bytes(library, "catalog/current.json"))
    generation = pointer.get("generation", "")
    if pointer.get("schema_version") != 2 or not re.fullmatch(r"[0-9a-f]{64}", generation):
        raise MigrationError("migration_v2_current_required")
    prefix = "catalog/generations/" + generation + "/"
    build = json.loads(read_evidence_bytes(library, prefix + "build-manifest.json"))
    if (build.get("schema_version") != 2 or build.get("catalog_generation") != generation
            or set(build.get("output_hashes", {})) != {"registry.json", "views/execution-pairings.json",
                "views/relation-capabilities.json", "views/visual.json"}):
        raise MigrationError("migration_v2_build_invalid")
    for path, sha in build["output_hashes"].items():
        verify_reference(library, {"path": prefix + path, "sha256": sha})
    registry = json.loads(read_evidence_bytes(library, prefix + "registry.json"))
    if (registry.get("schema_version") != 2 or registry.get("catalog_generation") != generation
            or not registry.get("asset_generation") or not registry.get("evidence_set_digest")):
        raise MigrationError("migration_v2_registry_invalid")
    from .template_catalog import catalog_inputs, validate_library
    from jsonschema import Draft202012Validator
    validate_library(library)
    schema = json.loads((Path(__file__).parent / "schemas/template-registry-v2.schema.json").read_text())
    if list(Draft202012Validator(schema).iter_errors(registry)):
        raise MigrationError("migration_v2_registry_invalid")
    expected = catalog_inputs(library)
    if digest(expected) != generation or any(registry.get(key) != value or build.get(key) != value for key, value in expected.items()):
        raise MigrationError("migration_v2_source_stale")
    return {"generation": generation, "current": file_reference(library, "catalog/current.json")}


def verify_final_receipt(root, reference, *, stage_receipt):
    """U6-B 必须重核正式 cleanup→publish→verify→plan 链，手填 hash 字典无效。"""
    receipt = receipt_document(root, reference, "cleanup")
    marker = maintenance_path(receipt["delivery_root"])
    if marker.exists() or marker.is_symlink():
        raise MigrationError("migration_delivery_in_maintenance")
    with library_operation(marker.parent):
        return _verify_final_state(root, reference, stage_receipt=stage_receipt)


def _verify_final_state(root, reference, *, stage_receipt):
    """供持锁 cleanup 检查最终字节；公开验证仍要求 maintenance 已解除。"""
    final = receipt_document(root, reference, "cleanup")
    plan = validate_plan(load_document(root, final["plan"]))
    if final.get("plan_digest") != plan["plan_digest"]:
        raise MigrationError("migration_final_plan_mismatch")
    published = receipt_document(root, final["publication"], "publish", plan_digest=plan["plan_digest"])
    verified = receipt_document(root, published["verified"], "verify", plan_digest=plan["plan_digest"])
    # 正式 verify gate 会重算 staged catalog、bundle 日志和 U6-A；拒绝自签摘要字典。
    _verified_for_publication(root, final["plan"], published["verified"])
    if (published.get("plan") != final["plan"] or verified.get("plan") != final["plan"]
            or verified.get("visual_receipt") != stage_receipt or not verified.get("publication_ready")
            or set(verified.get("checks", {})) != STRUCTURAL_GATES
            or any(row.get("status") != "passed" for row in verified["checks"].values())):
        raise MigrationError("migration_verification_chain_incomplete")
    for row in verified["checks"].values():
        evidence = load_document(root, row["evidence"])
        if evidence.get("status") != "passed" or evidence.get("plan_digest") != plan["plan_digest"]:
            raise MigrationError("migration_structural_evidence_invalid")
    staging = Path(verified["staging_root"])
    delivery = Path(published["delivery_root"])
    if (delivery.absolute() != Path(plan["source_root"]).absolute() or delivery.absolute() == staging.absolute()
            or final.get("delivery_root") != published["delivery_root"]
            or final.get("staging_hashes") != verified.get("staging_hashes")
            or final.get("staging_hashes") != plan["target_hashes"]
            or final.get("delivery_hashes") != plan["target_hashes"]):
        raise MigrationError("migration_convergence_manifest_mismatch")
    for directory in (staging, delivery):
        _converged_hashes(plan, directory)
    journal = _verify_publication_confirmation(root, plan, published)
    if (journal.get("plan_digest") != plan["plan_digest"] or journal.get("phase") != "publish"
            or journal.get("status") != "passed" or journal.get("current_switched") is not True
            or {row["path"]: row.get("target_sha256") for row in journal.get("files", [])} != plan["target_hashes"]
            or any(row.get("status") != "replaced" for row in journal.get("files", []))):
        raise MigrationError("migration_publication_journal_incomplete")
    deleted = {row["path"]: row for row in final.get("deleted", [])}
    cleanup_journal = _check_cleanup_journal(plan, load_document(root, final["journal"]))
    if (any(final.get(key) != published.get(key) or cleanup_journal.get(key) != published.get(key)
            for key in (*PUBLICATION_IDENTITY, "journal_generation"))
            or cleanup_journal.get("phase") != "cleanup" or cleanup_journal.get("status") != "passed"
            or cleanup_journal.get("plan_digest") != plan["plan_digest"]
            or cleanup_journal.get("files") != final.get("deleted")
            or any(row.get("status") != "deleted" for row in final.get("deleted", []))):
        raise MigrationError("migration_cleanup_journal_incomplete")
    if set(deleted) != {row["path"] for row in plan["delete_allowlist"]}:
        raise MigrationError("migration_cleanup_manifest_incomplete")
    for row in plan["delete_allowlist"]:
        if deleted[row["path"]].get("before") != row["expected"] or file_state(delivery, row["path"])["type"] != "absent":
            raise MigrationError("migration_cleanup_drift:" + row["path"])
    closure = verify_consumer_closure(delivery)
    _verify_target_closure(plan, delivery)
    if final.get("closure") != closure:
        raise MigrationError("migration_final_consumer_closure_failed")
    _migration_catalog_files(plan, delivery)
    _migration_catalog_files(plan, staging)
    return final


def maintenance_path(delivery):
    return Path(delivery) / "leo-ppt-generator/template-library/.maintenance.json"


def require_available(library):
    path = Path(library) / ".maintenance.json"
    if path.exists() or path.is_symlink():
        raise MigrationError("library_in_maintenance")


@contextmanager
def _library_lock(library, *, exclusive=False):
    """锁住库目录本身；只读安装也能参与互斥，不创建或替换锁文件。"""
    import fcntl
    root = Path(library).absolute()
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            code = "migration_maintenance_lock_busy" if exclusive else "library_in_maintenance"
            raise MigrationError(code) from exc
        current, pinned = os.stat(root, follow_symlinks=False), os.fstat(fd)
        if (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino):
            raise MigrationError("migration_library_root_changed")
        yield
    finally:
        os.close(fd)


@contextmanager
def library_operation(library):
    """消费者在完整读写期间持共享锁；发布前的检查与操作不能分离。"""
    require_available(library)
    with _library_lock(library):
        require_available(library)
        yield


@contextmanager
def locked_publication(delivery, *, plan_digest):
    """进程锁与持久 maintenance 分离；中断后仍阻止普通消费者执行。"""
    import fcntl
    marker = maintenance_path(delivery)
    safe_path(delivery, marker.relative_to(delivery).as_posix())
    marker.parent.mkdir(parents=True, exist_ok=True)
    with _library_lock(marker.parent, exclusive=True):
        lock = marker.with_name(".maintenance.lock")
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MigrationError("migration_maintenance_lock_busy") from exc
            if marker.exists():
                current = json.loads(read_evidence_bytes(marker.parent, marker.name))
                if current.get("plan_digest") != plan_digest:
                    raise MigrationError("migration_maintenance_owner_conflict")
            else:
                atomic_write_json(marker, {"schema_version": 1, "plan_digest": plan_digest})
                fsync_directory(marker.parent)
            yield marker
        finally:
            os.close(fd)


def compare_and_swap_file(root, relative, *, expected, body, mode=0o644, checkpoint=None):
    """固定目录描述符后核对旧字节；仅替换明确绑定的单个普通文件。"""
    path = safe_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = None
    try:
        if file_state(root, relative) != expected:
            raise MigrationError("migration_cas_mismatch:" + relative)
        fd, temporary = tempfile.mkstemp(prefix=".migration-", dir=path.parent)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body); handle.flush()
            os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
        if checkpoint:
            checkpoint("before_cas", relative)
        if file_state(root, relative) != expected:
            raise MigrationError("migration_cas_mismatch:" + relative)
        # 父目录被交换时不把写入悄悄落到另一棵树。
        current_parent = os.stat(path.parent, follow_symlinks=False)
        pinned_parent = os.fstat(parent_fd)
        if (current_parent.st_dev, current_parent.st_ino) != (pinned_parent.st_dev, pinned_parent.st_ino):
            raise MigrationError("migration_parent_changed:" + relative)
        os.replace(Path(temporary).name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        temporary = None
        os.fsync(parent_fd)
        actual = file_state(root, relative)
        if actual != {"type": "file", "sha256": hashlib.sha256(body).hexdigest(), "mode": mode}:
            raise MigrationError("migration_cas_postwrite_drift:" + relative)
        return actual
    finally:
        if temporary is not None:
            try:
                os.unlink(Path(temporary).name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)
