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
def _real_html_run():
    from leo_ppt_generator.application.expression_pipeline import PipelineRequest
    from leo_ppt_generator.application.routes import generate
    temporary = tempfile.TemporaryDirectory()
    atexit.register(temporary.cleanup)
    root = Path(temporary.name).resolve() / "run"
    pack, resolver, context = real_validation_inputs()
    request = PipelineRequest(pack, context, resolver.generation,
        {page["page_id"]: ["render:html"] for page in pack["pages"]},
        str(root), "receipt-integration", str(resolver.builtin_root), purpose="validation")
    result = generate(request, resolver=resolver)
    if result["status"] != "html_validated":
        raise AssertionError(result)
    return root


def copy_real_html_run(root):
    """复用同一真实浏览器导出的不可变字节，逐个测试在独立副本中注入漂移。"""
    source = _real_html_run()
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
