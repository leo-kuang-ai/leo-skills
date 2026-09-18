"""共享会话成功、异常和外网拒绝后清理页级 context。"""
import json
from pathlib import Path
import tempfile
from tests.render.helpers import browser_test_case
from leo_ppt_generator.render.page import RenderSession, render_page


class RenderSessionTests(browser_test_case()):
    def test_pages_share_browser_and_server_with_isolated_contexts(self):
        with tempfile.TemporaryDirectory() as tmp, RenderSession() as session:
            browser = session.browser
            data = Path(tmp) / 'data.json'
            for n in range(2):
                data.write_text(json.dumps({'title': f'会话第 {n+1} 页', 'bullets': ['内容独立', '浏览器复用']}))
                result = render_page('body-basic', data, Path(tmp) / f'{n}.png', session=session)
                self.assertEqual(result['overflow_check'], 'pass')
                self.assertIs(session.browser, browser)
                self.assertEqual(len(browser.contexts), 0)
            self.assertEqual(len(session._servers), 1)
        self.assertIsNone(session.browser)
        self.assertFalse(browser.is_connected())

    def test_exception_closes_context_and_external_requests_are_blocked(self):
        with RenderSession() as session:
            server = session.asset_server([], None)
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                with session.page_context(1, server.url()) as (context, rejected):
                    raise RuntimeError('injected')
            self.assertEqual(session.browser.contexts, [])
            with session.page_context(1, server.url()) as (context, rejected):
                page = context.new_page()
                try:
                    page.goto('https://example.invalid/external', timeout=1500)
                except Exception:
                    pass
                self.assertEqual(rejected, ['https://example.invalid'])
            self.assertEqual(session.browser.contexts, [])
