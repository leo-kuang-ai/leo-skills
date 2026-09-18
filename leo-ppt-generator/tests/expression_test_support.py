"""用真实浏览器建立当前环境的非发布资格；不能作为用户任务或视觉收益证据。"""
from functools import lru_cache
import atexit
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.content_pack import compile_content_pack
from leo_ppt_generator.content_projection import precompile_binding
from leo_ppt_generator.qualification import ORACLE_PATH, RECEIPTS_PATH
from leo_ppt_generator.templates import resolve_design_context

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def real_validation_inputs():
    temporary = tempfile.TemporaryDirectory()
    atexit.register(temporary.cleanup)
    source = AssetResolver(library=ROOT / "template-library")
    pack = compile_content_pack((ROOT / "evals/fixtures/expression-first-validation-master.md").read_text(),
                                master_path="evals/fixtures/expression-first-validation-master.md")
    context = resolve_design_context("清爽专业风", resolver=source)
    seed = precompile_binding(pack["pages"][0], context, "builtin:layout:body-basic",
        content_digest=pack["content_digest"], numbers=pack["numbers"], resolver=source)
    pins = {pin["asset_id"]: pin for pin in seed["effective"]["assets"]}
    for identity in list(pins):
        for dependency in source.resolve_dependencies(identity):
            pins[dependency["asset_id"]] = source.fingerprint(dependency["asset_id"])
    resolver = source.freeze_assets(Path(temporary.name).resolve() / "snapshot", list(pins.values()))
    library = resolver.builtin_root
    (library / ORACLE_PATH).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "template-library" / ORACLE_PATH, library / ORACLE_PATH)
    spec = importlib.util.spec_from_file_location("relation_probe_runner", ROOT / "scripts/probe_relation_capabilities.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())
    cases["cases"] = [case for case in cases["cases"] if case["relation"] == "independent"]
    report = module.run_probes(library_root=library, cases=cases, output="evidence/probes/transaction-test")
    html = [row for row in report["results"] if row["lane"] == "render:html"]
    if len(html) != 1 or html[0]["status"] != "passed" or html[0]["owner_gaps"]:
        raise AssertionError(html)
    shutil.copyfile(library / "evidence/probes/transaction-test/capability-receipts.json", library / RECEIPTS_PATH)
    context = resolve_design_context("builtin:style:clean-professional", resolver=resolver)
    return pack, resolver, context


@lru_cache(maxsize=1)
def real_validation_inputs_v2():
    """将当前真实资产隔离转换为 v2，再由相同浏览器探针取得新位置的证据。"""
    from leo_ppt_generator.library_migration import materialize_shadow_library
    from leo_ppt_generator.template_catalog import build_catalog, publish_catalog, LibraryContext
    from leo_ppt_generator.capability_probes import run_probes
    pack, previous, _ = real_validation_inputs()
    temporary = tempfile.TemporaryDirectory()
    atexit.register(temporary.cleanup)
    root = Path(temporary.name).resolve()
    source, library = root / "source", root / "library"
    shutil.copytree(previous.builtin_root, source)
    shutil.copyfile(ROOT / "template-library/library.json", source / "library.json")
    shutil.copytree(ROOT / "template-library/governance", source / "governance", dirs_exist_ok=True)
    materialize_shadow_library(source, library)
    publish_catalog(library, build_catalog(library))
    cases = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())
    cases["cases"] = [case for case in cases["cases"] if case["relation"] == "independent"]
    report = run_probes(library_root=library, cases=cases, output="evidence/probes/transaction-v2")
    html = [row for row in report["results"] if row["lane"] == "render:html"]
    if len(html) != 1 or html[0]["status"] != "passed" or html[0]["owner_gaps"]:
        raise AssertionError(html)
    shutil.copyfile(library / "evidence/probes/transaction-v2/capability-receipts.json", library / RECEIPTS_PATH)
    publish_catalog(library, build_catalog(library))
    resolver = AssetResolver(context=LibraryContext(library))
    return pack, resolver, resolve_design_context("builtin:style:clean-professional", resolver=resolver)


@lru_cache(maxsize=2)
def _real_html_run(request_index=False):
    from leo_ppt_generator.application.expression_pipeline import PipelineRequest
    from leo_ppt_generator.application.routes import generate
    from leo_ppt_generator.content_preview import render_run_preview
    temporary = tempfile.TemporaryDirectory()
    atexit.register(temporary.cleanup)
    root = Path(temporary.name).resolve() / "run"
    pack, resolver, context = real_validation_inputs()
    run_id = "receipt-integration"
    if request_index:
        from leo_ppt_generator.application.run_index import RunIndex
        from leo_ppt_generator.config.backend_contract import BackendRegistry
        backend = root.parent / "backend.json"
        backend.write_text(json.dumps(BackendRegistry.default().create_contract("render-lane", mode="generate")))
        created = RunIndex.create_from_request(root, route="generate",
            input_path=ROOT / "evals/fixtures/expression-first-validation-master.md",
            backend_contract_path=backend, runtime_identity="expression-policy-v1")
        run_id = created.index.snapshot()["run_id"]
    request = PipelineRequest(pack, context, resolver.generation,
        {page["page_id"]: ["render:html"] for page in pack["pages"]},
        str(root), run_id, str(resolver.builtin_root), purpose="validation")
    result = generate(request, resolver=resolver)
    if result["status"] != "html_validated":
        raise AssertionError(result)
    preview = render_run_preview(root)
    if any(page["status"] != "ready" for page in preview["pages"]):
        raise AssertionError(preview)
    return root


def copy_real_html_run(root, *, request_index=False):
    """复用同一真实浏览器导出的不可变字节，逐个测试在独立副本中注入漂移。"""
    source = _real_html_run(request_index)
    root = Path(root).resolve()
    shutil.copytree(source, root, dirs_exist_ok=True)
    result_path = root / "pipeline-result.json"
    result = json.loads(result_path.read_text())
    for rows in result["receipt_refs"].values():
        for row in rows.values():
            for key in ("artifact", "receipt"):
                row[key] = Path(row[key]).relative_to(source).as_posix()
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def slides_for_run(root):
    from leo_ppt_generator.application.expression_pipeline import load_committed_input
    pack = load_committed_input(root)["payload"]["pack"]
    return [{"page_id": page["page_id"], "number": page["number"], "title": page["claim"],
             "required_text": page["required_text"], "notes": ""} for page in pack["pages"]]


@lru_cache(maxsize=4)
def real_allocation_inputs(hero_limit=1, alt_limit=0, prefer_b=False):
    """从真实模板复制受控布局变体；每次声明变化重新运行实际浏览器正反例。"""
    from copy import deepcopy
    from leo_ppt_generator.capability_probes import run_probes
    from leo_ppt_generator.page_intent import analyze_page_intent
    temporary = tempfile.TemporaryDirectory()
    atexit.register(temporary.cleanup)
    root = Path(temporary.name).resolve()
    library = root / "library"
    shutil.copytree(ROOT / "template-library", library,
                    ignore=lambda path, names: [n for n in names if n in {"catalog", "evidence"}])
    (library / ORACLE_PATH).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "template-library" / ORACLE_PATH, library / ORACLE_PATH)
    original = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())
    independent = next(case for case in original["cases"] if case["relation"] == "independent")
    cases = []
    for name in ("hero", "cover-alt", "cover-third", "bullets-a", "bullets-b"):
        base = "body-basic"
        is_cover = name in {"hero", "cover-alt", "cover-third"}
        layout_dir = library / "canonical/layouts" / name
        template_dir = library / "canonical/templates" / name
        shutil.copytree(library / "canonical/layouts" / base, layout_dir)
        shutil.copytree(library / "canonical/templates" / base, template_dir)
        layout = json.loads((layout_dir / "layout.json").read_text())
        template = json.loads((template_dir / "template.json").read_text())
        layout.update(asset_id="builtin:layout:" + name, name=name, aliases=[name],
                      renderer_support={"render:html": "builtin:template:" + name})
        layout.pop("image_recipe", None)
        if is_cover:
            # 分配测试只改变页角色与合法输入容量；不伪造 cover-basic 的渲染通过。
            layout["page_role"] = "cover"
            layout["slots"]["bullets"]["count_min"] = 1
            for field in template["input_fields"]:
                if field["name"] == "bullets":
                    field["count_min"] = 1
        layout["structure"].setdefault("groups", []).append(
            {"name": "独立内容", "members": ["subtitle" if base == "cover-basic" else "bullets"], "relation": "group"})
        limit = hero_limit if name == "hero" else alt_limit if name == "cover-alt" else 0
        if limit:
            layout.update(reuse_friendly=False, max_per_deck=limit)
        else:
            layout.update(reuse_friendly=True)
            layout.pop("max_per_deck", None)
        if prefer_b and name == "bullets-b":
            layout["aliases"].insert(0, analyze_page_intent({"semantic_structure": "independent", "points": 3})["preferred_layouts"][0])
        template.update(asset_id="builtin:template:" + name, name=name,
                        layout_profiles=[layout["asset_id"]])
        (layout_dir / "layout.json").write_text(json.dumps(layout, ensure_ascii=False))
        (template_dir / "template.json").write_text(json.dumps(template, ensure_ascii=False))
        case = deepcopy(independent)
        case.update(case_id=name, layout_id=layout["asset_id"])
        cases.append(case)
    cases.append(deepcopy(next(case for case in original["cases"] if case["relation"] == "comparison")))
    from leo_ppt_generator.library_migration import materialize_shadow_library
    from leo_ppt_generator.template_catalog import build_catalog, publish_catalog
    converted = root / "v2-library"
    materialize_shadow_library(library, converted)
    library = converted
    publish_catalog(library, build_catalog(library))
    report = run_probes(library_root=library, cases={**original, "cases": cases}, output="evidence/probes/allocation")
    html = [row for row in report["results"] if row["lane"] == "render:html"]
    if len(html) != len(cases) or any(row["status"] != "passed" or row["owner_gaps"] for row in html):
        raise AssertionError(html)
    shutil.copyfile(library / "evidence/probes/allocation/capability-receipts.json", library / RECEIPTS_PATH)
    publish_catalog(library, build_catalog(library))
    resolver = AssetResolver(library=library, home=root / "empty-home")
    return resolver, resolve_design_context("clean-professional", resolver=resolver)
