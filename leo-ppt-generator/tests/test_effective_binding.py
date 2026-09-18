"""有效绑定使用实际库字节，拒绝消费漂移输入。"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.content_projection import (
    ProjectionError, materialize_html, precompile_binding, verify_effective_binding,
)
from leo_ppt_generator.templates import resolve_design_context


class EffectiveBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        from tests.expression_test_support import real_validation_inputs
        pack, resolver, _ = real_validation_inputs()
        self.library = self.root / 'template-library'
        shutil.copytree(resolver.builtin_root, self.library)
        self.resolver = AssetResolver(library=self.library, home=self.root / 'empty-home')
        self.context = resolve_design_context('clean-professional', resolver=self.resolver)
        self.page = deepcopy(pack['pages'][0])
        self.binding = precompile_binding(self.page, self.context, 'body-basic',
            content_digest=pack['content_digest'], numbers=pack['numbers'], resolver=self.resolver, qualification_purpose='validation')
        self.assertTrue(self.binding['eligibility']['qualified'])

    def test_materialize_preserves_binding_and_actual_text(self):
        before = deepcopy(self.binding)
        data = materialize_html(self.binding, self.page, resolver=self.resolver)
        self.assertEqual(data['bullets'], [item['text'] for item in self.page['items'] if item['kind'] == 'point'])
        self.assertEqual(self.binding, before)
        self.assertEqual(self.binding['schema_version'], 2)
        pins = self.binding['effective']['assets']
        self.assertTrue(any(any(f.endswith('/page.html') for f in p['files']) for p in pins))
        self.assertTrue(any(p['asset_id'] == self.context['style']['asset_id'] for p in pins))

    def test_page_mutation_is_rejected_even_with_same_item_ids(self):
        changed = deepcopy(self.page)
        changed['items'][0]['text'] = '内容已被改写'
        with self.assertRaisesRegex(ProjectionError, 'content_changed'):
            materialize_html(self.binding, changed, resolver=self.resolver)

    def test_actual_html_mutation_is_rejected_with_unchanged_manifest(self):
        html = self.library / 'canonical/templates/body-basic/page.html'
        html.write_bytes(html.read_bytes() + b'\n<!-- changed -->')
        with self.assertRaisesRegex(ProjectionError, 'asset_changed'):
            materialize_html(self.binding, self.page, resolver=self.resolver)

    def test_eligibility_and_slot_tampering_are_rejected(self):
        for field in ('eligibility', 'slot_map'):
            binding = deepcopy(self.binding)
            binding[field] = {}
            with self.assertRaisesRegex(ProjectionError, 'digest_mismatch'):
                verify_effective_binding(binding, self.page, resolver=self.resolver)

    def test_unrelated_asset_change_does_not_invalidate_binding(self):
        pinned = {f for pin in self.binding['effective']['assets'] for f in pin['files']}
        unrelated = self.library / 'canonical/templates/unselected-proof/page.html'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('<div>Unselected asset</div>')
        unrelated.write_bytes(unrelated.read_bytes() + b'\n<!-- changed -->')
        verify_effective_binding(self.binding, self.page, resolver=self.resolver)

    def test_missing_template_file_is_rejected(self):
        (self.library / 'canonical/templates/body-basic/page.html').unlink()
        with self.assertRaisesRegex(ProjectionError, 'asset_unavailable'):
            verify_effective_binding(self.binding, self.page, resolver=self.resolver)

    def test_snapshot_survives_live_asset_replacement_and_rejects_snapshot_tamper(self):
        snapshot = self.root / 'run/input/asset-snapshot'
        frozen = self.resolver.freeze_assets(snapshot, self.binding['effective']['assets'])
        from leo_ppt_generator.qualification import freeze_qualification_evidence
        freeze_qualification_evidence(self.binding['eligibility']['checks']['qualification'],
            source_root=self.library, target_root=frozen.builtin_root)
        html = self.library / 'canonical/templates/body-basic/page.html'
        html.write_bytes(b'new generation')
        data = materialize_html(self.binding, self.page, resolver=frozen)
        self.assertEqual(data['title'], self.page['claim'])
        # 重试优先校验已有快照，不读取当前活动资产。
        self.resolver.freeze_assets(snapshot, self.binding['effective']['assets'])
        frozen_html = snapshot / 'builtin/canonical/templates/body-basic/page.html'
        frozen_html.write_bytes(b'tampered snapshot')
        with self.assertRaisesRegex(ProjectionError, 'asset_changed'):
            verify_effective_binding(self.binding, self.page, resolver=frozen)

    def test_bound_render_rejects_unbound_data_before_browser_launch(self):
        from leo_ppt_generator.render.page import render_page
        from leo_ppt_generator.render.errors import RenderError
        data = self.root / 'data.json'
        data.write_text(json.dumps({'title': '不属于此页', 'bullets': ['替换']}))
        with self.assertRaisesRegex(RenderError, 'effective_binding_render_data_mismatch'):
            render_page(self.binding['template_id'], data, self.root / 'out.png',
                        resolver=self.resolver, binding=self.binding, pack_page=self.page)
        self.assertFalse((self.root / 'out.png').exists())


if __name__ == '__main__':
    unittest.main()
