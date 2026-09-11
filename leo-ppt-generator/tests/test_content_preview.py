"""预览保持完整页集和绑定，不改变交付收据。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from leo_ppt_generator.content_preview import render_run_preview, PreviewError, _cached_page
from leo_ppt_generator.content_pack import compile_content_pack
from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.templates import resolve_design_context
from leo_ppt_generator.layout_selection import allocate_deck
from leo_ppt_generator.storage import atomic_write_json
from leo_ppt_generator.render.receipt import collect_fingerprints
from tests.render.helpers import browser_test_case


def make_preview_run(root, count=2, *, title='固定内容，再选择表达', first_title=None, bind=True):
    (root / 'input').mkdir(parents=True, exist_ok=True)
    master = '# 工程验证母版\ndecision_source: user-delegated\n'
    for n in range(1, count + 1):
        page_title = first_title if n == 1 and first_title is not None else title
        master += (f'\n## S{n} 预览\npage_id: pg-{n:08x}\n页面角色: 流程·路径\n'
                   f'- 标题：{page_title}\n- 要点 1：页级绑定保持一致\n- 要点 2：缺失证据显式报告\n')
    pack = compile_content_pack(master, master_path='fixture/master.md')
    atomic_write_json(root / 'input/page-content-pack.json', pack)
    if bind:
        resolver = AssetResolver()
        context = resolve_design_context('finance-navy', resolver=resolver)
        selection = allocate_deck(pack, context, candidates=['body-basic'], resolver=resolver)
        assert selection['status'] == 'complete', selection
        atomic_write_json(root / 'input/layout-selection.json', selection)
        pins = [pin for entry in selection['selection'].values() for pin in entry['binding']['effective']['assets']]
        resolver.freeze_assets(root / 'input/asset-snapshot', pins)
    return pack


class PreviewContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_missing_pack_fails_before_output_creation(self):
        with self.assertRaisesRegex(PreviewError, 'content_pack_missing'):
            render_run_preview(self.root)
        self.assertFalse((self.root / 'previews').exists())

    def test_missing_binding_is_page_failure(self):
        make_preview_run(self.root, bind=False)
        result = render_run_preview(self.root)
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(all(p['reason_code'] == 'preview_binding_missing' for p in result['pages']))

    def test_unknown_filter_does_not_silently_shrink_page_set(self):
        make_preview_run(self.root, bind=False)
        with self.assertRaisesRegex(PreviewError, 'page_selection_invalid'):
            render_run_preview(self.root, pages=['missing'])

    def test_output_override_and_symlink_are_rejected(self):
        make_preview_run(self.root, bind=False)
        with self.assertRaises(PreviewError):
            render_run_preview(self.root, output_dir=self.root / 'input')
        (self.root / 'previews').symlink_to(self.root / 'input', target_is_directory=True)
        with self.assertRaises(PreviewError):
            render_run_preview(self.root)

    def test_titles_are_escaped_in_single_file_overview(self):
        make_preview_run(self.root, bind=False, title='<script>alert(1)</script>')
        render_run_preview(self.root)
        html = (self.root / 'previews/index.html').read_text()
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('<summary>', html)

    def test_forged_cache_path_is_rejected(self):
        self.assertFalse(_cached_page({'status': 'ready', 'cache_key': 'key',
                                      'artifact': '../outside'}, 'key', self.root))

    def test_cli_preserves_partial_pages_and_output_link(self):
        from leo_ppt_generator.cli import build_parser, dispatch
        make_preview_run(self.root, bind=False)
        result = dispatch(build_parser().parse_args(['content', 'preview', str(self.root)]))
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(len(result['preview']['pages']), 2)
        self.assertTrue(Path(result['artifact_refs'][0]).is_file())


class PreviewBrowserTests(browser_test_case()):
    def test_edit_one_page_reuses_other_pixels_with_current_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_preview_run(root)
            first = render_run_preview(root)
            self.assertEqual(first['status'], 'ready', first)
            original = json.loads((root / 'previews' / first['pages'][1]['sidecar']).read_text())
            make_preview_run(root, first_title='先检查证据，再推进决策')
            current = render_run_preview(root)
            self.assertEqual(current['status'], 'ready', current)
            self.assertFalse(current['pages'][0]['cached'])
            self.assertTrue(current['pages'][1]['cached'])
            self.assertEqual(first['pages'][1]['artifact_sha256'], current['pages'][1]['artifact_sha256'])
            receipt = json.loads((root / 'previews' / current['pages'][1]['sidecar']).read_text())
            self.assertEqual(receipt['binding_digest'], current['pages'][1]['binding_digest'])
            self.assertEqual(receipt['content_digest'], current['content_digest'])
            self.assertEqual(receipt['preview_cache']['rendered_binding_digest'], original['binding_digest'])

    def test_real_preview_cache_corruption_and_receipt_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = make_preview_run(root)
            before = collect_fingerprints(root)
            first = render_run_preview(root)
            self.assertEqual(first['status'], 'ready', first)
            self.assertEqual(before, collect_fingerprints(root))
            with patch('leo_ppt_generator.content_preview.render_page', side_effect=AssertionError('unexpected rerender')):
                second = render_run_preview(root, pages=[pack['pages'][0]['page_id']])
            self.assertEqual(len(second['pages']), 2)
            self.assertTrue(all(p['cached'] for p in second['pages']))
            self.assertEqual(before, collect_fingerprints(root))
            (root / 'previews' / first['pages'][0]['artifact']).write_bytes(b'broken png')
            third = render_run_preview(root)
            self.assertFalse(third['pages'][0]['cached'])
            self.assertTrue(third['pages'][1]['cached'])
            self.assertEqual(third['status'], 'ready', third)
