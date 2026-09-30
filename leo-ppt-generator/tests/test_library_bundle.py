"""U8：模板库 bundle 安装完整性与恢复/拒绝（方案 v4 §U8）。

覆盖：完整安装（隔离副本）、链接安装（真实 bundle symlink）、
canonical 篡改检出（library-check 非 zero）、断写 current.json 拒绝、
冻结设计恢复校验（fresh ↔ stale；stale 即旧 run 拒绝续跑）。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.asset_resolver import (AssetResolver,
                                              StaleCatalogError)
from leo_ppt_generator.templates import (compose_design,
                                         verify_design_freshness)
from leo_ppt_generator.library_migration import materialize_shadow_library
from leo_ppt_generator.template_catalog import LibraryContext, build_catalog, publish_catalog, CatalogError

BASELINE_ENTITIES = 443  # v2 执行实体含新增规格表 recipe；124 个指南仍不进入执行池


_INSTALL_PROCESS = r"""
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path

from runtime_manager import RuntimeManager

# 复用安装器的 bundle 边界规范化；库内部路径仍交给生产 resolver 校验。
manager = RuntimeManager(Path(os.environ['LEO_PPT_BUNDLE']),
                         Path(os.environ['LEO_PPT_HOME']))
os.environ['LEO_PPT_BUNDLE'] = str(manager.bundle_root)
mode = sys.argv[1]
if mode == 'cli':
    from leo_ppt_generator.cli import main
    raise SystemExit(main(sys.argv[2:]))
if mode == 'library-check':
    script = manager.bundle_root / 'scripts/capability_manifest.py'
    sys.argv = [str(script), '--template-library', '--library-check']
    runpy.run_path(str(script), run_name='__main__')
    raise SystemExit(0)

import leo_ppt_generator
from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.render.assets import template_http_entry, template_path

try:
    resolver = AssetResolver()
    assets = []
    for identity in ('builtin:style:finance-navy', 'builtin:recipe:p25-spec-table',
                     'builtin:template:spec-table'):
        resolved = resolver.resolve(identity)
        assets.append({key: resolved[key] for key in
                       ('asset_id', 'kind', 'origin_scope', 'trusted_root',
                        'relative_path', 'path', 'revision')})
        assets[-1]['sha256'] = hashlib.sha256(Path(resolved['path']).read_bytes()).hexdigest()
    recipe = resolver.resolve('builtin:recipe:p25-spec-table')['data']
    print(json.dumps({'bundle_root': str(manager.bundle_root),
        'package_source': str(Path(leo_ppt_generator.__file__).resolve()),
        'cwd': str(Path.cwd()), 'entity_count': len(resolver.entities),
        'generation': resolver.generation, 'assets': assets,
        'recipe_layouts': recipe['layout_profiles'],
        'recipe_cell_input': recipe['slot_map']['cell']['input_path'],
        'template_path': str(template_path('spec-table', resolver=resolver)),
        'http_entry': str(template_http_entry('cover-basic.html', resolver=resolver))}))
except Exception as error:
    print(json.dumps({'error_type': type(error).__name__,
                      'reason_code': getattr(error, 'reason_code', None),
                      'detail': str(error)}), file=sys.stderr)
    raise SystemExit(2)
"""


def _installation_process(bundle_entry: Path, cwd: Path, *command: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, LEO_PPT_BUNDLE=str(bundle_entry),
               LEO_PPT_HOME=str(cwd / 'home'), PYTHONNOUSERSITE='1',
               PYTHONPATH=os.pathsep.join(str(bundle_entry / part)
                                         for part in ('runtime/src', 'scripts')))
    return subprocess.run([sys.executable, '-c', _INSTALL_PROCESS, *command],
                          cwd=cwd, env=env, capture_output=True, text=True, timeout=120)


def _make_install_bundle(tmp: str) -> tuple[Path, Path]:
    library = _make_library_copy(tmp)
    bundle = library.parent
    shutil.copytree(SKILL / 'runtime/src', bundle / 'runtime/src',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(SKILL / 'assets', bundle / 'assets')
    (bundle / 'scripts').mkdir()
    for name in ('runtime_manager.py', 'capability_manifest.py'):
        shutil.copy2(SKILL / 'scripts' / name, bundle / 'scripts' / name)
    cwd = Path(tmp).resolve() / 'unrelated-working-directory'
    cwd.mkdir()
    return bundle, cwd


class IsolatedInstallTest(unittest.TestCase):
    def _probe(self, entry: Path, cwd: Path) -> dict:
        process = _installation_process(entry, cwd, 'probe')
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        return json.loads(process.stdout)

    def _assert_install(self, report: dict, bundle: Path, cwd: Path) -> None:
        library = bundle / 'template-library'
        self.assertEqual(report['bundle_root'], str(bundle))
        self.assertEqual(report['cwd'], str(cwd))
        self.assertEqual(report['package_source'],
                         str(bundle / 'runtime/src/leo_ppt_generator/__init__.py'))
        self.assertEqual(report['entity_count'], BASELINE_ENTITIES)
        self.assertEqual(report['generation'],
                         json.loads((library / 'catalog/current.json').read_text())['generation'])
        self.assertEqual(report['recipe_layouts'], ['builtin:layout:p25-spec-table'])
        self.assertEqual(report['recipe_cell_input'], 'rows.*.*')
        self.assertEqual(report['template_path'],
                         str(library / 'canonical/executable/templates/spec-table/page.html'))
        self.assertEqual(report['http_entry'],
                         str(library / 'canonical/executable/templates/cover-basic/page.html'))
        for asset in report['assets']:
            self.assertEqual(asset['origin_scope'], 'builtin')
            self.assertEqual(asset['trusted_root'], str(library))
            self.assertEqual(asset['path'], str(library / asset['relative_path']))
            self.assertEqual(asset['sha256'],
                             hashlib.sha256(Path(asset['path']).read_bytes()).hexdigest())

    def _assert_cli_and_check(self, entry: Path, cwd: Path, report: dict) -> None:
        cli = _installation_process(entry, cwd, 'cli', 'style', 'load',
                                    'builtin:style:finance-navy', '--summary')
        self.assertEqual(cli.returncode, 0, cli.stderr or cli.stdout)
        loaded = json.loads(cli.stdout)
        self.assertEqual(loaded['reason_code'], 'style_summary_loaded')
        for key in ('asset_id', 'path', 'revision'):
            self.assertEqual(loaded['style'][key], report['assets'][0][key])
        process = _installation_process(entry, cwd, 'library-check')
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        self.assertEqual(json.loads(process.stdout)['reason_code'], 'ok')

    def test_full_copy_install_resolves_and_checks_green(self) -> None:
        """复制的 runtime 从无关 cwd 消费复制的库，CLI 和 library-check 同源。"""

        with tempfile.TemporaryDirectory() as tmp:
            bundle, cwd = _make_install_bundle(tmp)
            report = self._probe(bundle, cwd)
            self._assert_install(report, bundle, cwd)
            self._assert_cli_and_check(bundle, cwd, report)
            self.assertTrue((bundle / "assets" / "render-fonts").is_dir())

    def test_linked_install_points_at_source_of_truth(self) -> None:
        """真实 symlink 经安装器规范化后，进程结果与直接安装逐字段等价。"""

        with tempfile.TemporaryDirectory() as tmp:
            bundle, cwd = _make_install_bundle(tmp)
            entry = Path(tmp).resolve() / 'linked-install'
            entry.symlink_to(bundle, target_is_directory=True)
            self.assertTrue(entry.is_symlink())
            copied = self._probe(bundle, cwd)
            linked = self._probe(entry, cwd)
            self._assert_install(linked, bundle, cwd)
            self.assertEqual(linked, copied)
            self._assert_cli_and_check(entry, cwd, linked)

    def test_linked_bundle_still_rejects_symlink_inside_library(self) -> None:
        """bundle 链接可用不放宽 canonical；库内和库外目标均拒绝。"""

        with tempfile.TemporaryDirectory() as tmp:
            bundle, cwd = _make_install_bundle(tmp)
            entry = Path(tmp).resolve() / 'linked-install'
            entry.symlink_to(bundle, target_is_directory=True)
            self._assert_install(self._probe(entry, cwd), bundle, cwd)
            relative = 'canonical/visual/styles/finance-navy/brief.json'
            asset = bundle / 'template-library' / relative
            body = asset.read_bytes()
            for target in (cwd / 'same-bytes.json',
                           bundle / 'template-library/governance/same-bytes.json'):
                with self.subTest(target=target.relative_to(Path(tmp).resolve())):
                    target.write_bytes(body)
                    asset.unlink()
                    asset.symlink_to(target)
                    process = _installation_process(entry, cwd, 'probe')
                    self.assertEqual(process.returncode, 2, process.stdout or process.stderr)
                    self.assertEqual(process.stdout, '')
                    error = json.loads(process.stderr)
                    self.assertEqual(error['error_type'], 'QualificationError')
                    self.assertEqual(error['detail'], 'evidence_file_unavailable: ' + relative)


def _make_library_copy(tmp: str) -> Path:
    library = Path(tmp).resolve() / "bundle/template-library"
    materialize_shadow_library(SKILL / "template-library", library)
    publish_catalog(library, build_catalog(library))
    return library


class TamperAndInterruptionTest(unittest.TestCase):
    def test_canonical_tamper_is_detected_not_silent(self) -> None:
        """篡改 canonical 文件 → resolver 拒绝加载该资产（StaleCatalogError）。

        revision 是内容摘要：绕过 builder 改文件必然漂移；library-check
        只校验发布产物自洽，内容漂移的运行时闸门是 resolver。
        """

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            target = library / "canonical/visual/styles/finance-navy/brief.json"
            data = json.loads(target.read_text(encoding="utf-8"))
            data["name"] = (data.get("name") or "") + "（篡改）"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            resolver = AssetResolver(context=LibraryContext(library))
            with self.assertRaisesRegex(CatalogError, "stale_catalog"):
                resolver.resolve("builtin:style:finance-navy")

    def test_interrupted_catalog_pointer_is_rejected(self) -> None:
        """断写：current.json 缺 generation → resolver 拒绝加载（不回落猜测）。"""

        with tempfile.TemporaryDirectory() as tmp:
            library = _make_library_copy(tmp)
            pointer = library / "catalog" / "current.json"
            pointer.write_text(json.dumps({"generation": None}), encoding="utf-8")
            with self.assertRaisesRegex(CatalogError, "catalog_invalid"):
                AssetResolver(context=LibraryContext(library)).entities


class DesignFreshnessResumeTest(unittest.TestCase):
    """旧 run 恢复/拒绝：冻结设计的依赖摘要是续跑的唯一准入。"""

    PAGES = [{"page_no": 1, "page_role": "cover",
              "layout": "builtin:layout:cover-basic", "content_ref": "c"},
             {"page_no": 2, "page_role": "data",
              "layout": "builtin:layout:p25-spec-table", "content_ref": "d",
              "slots": {"rows": [["a", "b", "c"]], "columns": ["x", "y", "z"]}}]

    def _compose_in(self, resolver) -> dict:
        from leo_ppt_generator.application.expression_pipeline import PipelineRequest, load_committed_input
        from leo_ppt_generator.application.routes import generate
        from leo_ppt_generator.templates import resolve_design_context
        from tests.expression_test_support import real_validation_inputs_v2
        pack, _, _ = real_validation_inputs_v2()
        context = resolve_design_context("clean-professional", resolver=resolver)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        run = Path(temporary.name).resolve() / "run"
        result = generate(PipelineRequest(pack, context, resolver.generation,
            {page["page_id"]: ["render:html"] for page in pack["pages"]},
            str(run), "v2-bundle-validation", str(resolver.builtin_root), purpose="validation"), resolver=resolver)
        self.assertEqual(result["status"], "html_validated")
        return load_committed_input(run)["payload"]["designs"]["render:html"]

    def test_fresh_design_resumes(self) -> None:
        from tests.expression_test_support import real_validation_inputs_v2
        _, resolver, _ = real_validation_inputs_v2()
        report = verify_design_freshness(self._compose_in(resolver), resolver)
        self.assertEqual(report["status"], "fresh")
        self.assertGreater(report["checked"], 0)

    def test_stale_dependency_rejects_resume(self) -> None:
        """依赖漂移（资产修订并重发布）→ stale + 波及面；旧 run 拒绝续跑。"""

        with tempfile.TemporaryDirectory() as tmp:
            from tests.expression_test_support import real_validation_inputs_v2
            _, original, _ = real_validation_inputs_v2()
            library = Path(tmp).resolve() / "bundle/template-library"
            shutil.copytree(original.builtin_root, library)
            resolver = AssetResolver(context=LibraryContext(library))
            frozen = self._compose_in(resolver)
            self.assertEqual(verify_design_freshness(frozen,
                resolver)["status"], "fresh")
            # 模拟库演进：修订一个依赖并重发布 catalog
            theme = Path(resolver.resolve(frozen["selection"]["theme"]["asset_id"])["path"])
            data = json.loads(theme.read_text(encoding="utf-8"))
            data["name"] = (data.get("name") or "x") + " rev2"
            theme.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            publish_catalog(library, build_catalog(library))
            report = verify_design_freshness(frozen,
                                             AssetResolver(context=LibraryContext(library)))
            self.assertEqual(report["status"], "stale")
            self.assertTrue(any(m["asset_id"] == frozen["selection"]["theme"]["asset_id"]
                                for m in report["mismatches"]),
                            f"波及面须点名被修订资产: {report['mismatches']}")

    def test_non_design_input_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            verify_design_freshness({"entity": "not-a-design"})


if __name__ == "__main__":
    unittest.main()
