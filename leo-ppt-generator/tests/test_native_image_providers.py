"""原生协议渠道适配器聚焦测试（gemini/minimax/ideogram，2026-09 接入批）。

Mock HTTP 层验证协议转换与错误路径；真实端点行为由渠道健康检查与现场
抽样覆盖（见 provider-catalog.md 贡献流程）。
"""

from __future__ import annotations

import sys
import unittest
from unittest import mock

SKILL_DIR = __import__("pathlib").Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator._vendor.codex_ppt.image_providers.factory import (
    create_image_provider,
)
from leo_ppt_generator._vendor.codex_ppt.image_providers.native import (
    GeminiImageProvider,
    IdeogramImageProvider,
    MiniMaxImageProvider,
)
from leo_ppt_generator._vendor.codex_ppt.image_providers.openai_compatible import (
    OpenAICompatibleImageProvider,
)

NATIVE_MODULE = "leo_ppt_generator._vendor.codex_ppt.image_providers.native"


class FactoryDispatchTests(unittest.TestCase):
    def test_native_hostnames_dispatch_to_native_providers(self):
        cases = [
            ("https://generativelanguage.googleapis.com/v1beta", GeminiImageProvider),
            ("https://api.minimaxi.com/v1", MiniMaxImageProvider),
            ("https://api.minimax.io/v1", MiniMaxImageProvider),
            ("https://api.ideogram.ai/v1", IdeogramImageProvider),
        ]
        for base_url, expected in cases:
            with self.subTest(base_url=base_url):
                provider = create_image_provider(api_key="k", base_url=base_url)
                self.assertIsInstance(provider, expected)

    def test_unknown_host_falls_back_to_openai_compatible(self):
        provider = create_image_provider(api_key="k", base_url="https://api.example.com/v1")
        self.assertIsInstance(provider, OpenAICompatibleImageProvider)

    def test_atlascloud_dispatch_still_wins(self):
        from leo_ppt_generator._vendor.codex_ppt.image_providers.atlascloud import (
            AtlasCloudImageProvider,
        )

        provider = create_image_provider(api_key="k", base_url="https://api.atlascloud.ai/v1")
        self.assertIsInstance(provider, AtlasCloudImageProvider)


class GeminiProviderTests(unittest.TestCase):
    def _provider(self):
        return GeminiImageProvider(
            api_key="g-key", base_url="https://generativelanguage.googleapis.com/v1beta"
        )

    def test_generate_maps_size_to_nearest_aspect_ratio(self):
        provider = self._provider()
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "ok"},
                            {"inlineData": {"mimeType": "image/png", "data": "QUJD"}},
                        ]
                    }
                }
            ]
        }
        with mock.patch(f"{NATIVE_MODULE}._post_json", return_value=response) as post:
            images = provider.generate(
                {"model": "gemini-2.5-flash-image", "prompt": "poster", "size": "1792x1024"}
            )
        self.assertEqual(images, ["QUJD"])
        url, kwargs = post.call_args[0][0], post.call_args[1]
        self.assertEqual(
            url,
            "https://generativelanguage.googleapis.com/v1beta"
            "/models/gemini-2.5-flash-image:generateContent",
        )
        self.assertEqual(kwargs["headers"], {"x-goog-api-key": "g-key"})
        image_config = kwargs["body"]["generationConfig"]["imageConfig"]
        self.assertEqual(image_config["aspectRatio"], "16:9")

    def test_generate_without_image_data_fails_clearly(self):
        provider = self._provider()
        with mock.patch(f"{NATIVE_MODULE}._post_json", return_value={"candidates": []}):
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate({"model": "m", "prompt": "p"})
        self.assertIn("gemini_image_missing", str(ctx.exception))

    def test_edit_is_unsupported(self):
        with self.assertRaises(RuntimeError):
            self._provider().edit({"model": "m"}, [], None)


class MiniMaxProviderTests(unittest.TestCase):
    def _provider(self):
        return MiniMaxImageProvider(api_key="mm-key", base_url="https://api.minimaxi.com/v1")

    def test_generate_downloads_image_urls(self):
        provider = self._provider()
        response = {"data": {"image_urls": ["https://img/1.png"]}}
        with mock.patch(f"{NATIVE_MODULE}._post_json", return_value=response) as post, \
                mock.patch(f"{NATIVE_MODULE}._download_image_b64", return_value="YjY0") as dl:
            images = provider.generate({"model": "image-01", "prompt": "p", "size": "1600x900"})
        self.assertEqual(images, ["YjY0"])
        dl.assert_called_once_with("https://img/1.png")
        url, kwargs = post.call_args[0][0], post.call_args[1]
        self.assertEqual(url, "https://api.minimaxi.com/v1/image_generation")
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer mm-key"})
        self.assertEqual(kwargs["body"]["aspect_ratio"], "16:9")

    def test_nested_data_payload_is_accepted(self):
        provider = self._provider()
        response = {"data": {"data": {"image_urls": ["https://img/2.png"]}}}
        with mock.patch(f"{NATIVE_MODULE}._post_json", return_value=response), \
                mock.patch(f"{NATIVE_MODULE}._download_image_b64", return_value="Yg=="):
            images = provider.generate({"model": "image-01", "prompt": "p"})
        self.assertEqual(images, ["Yg=="])

    def test_base_resp_error_raises(self):
        provider = self._provider()
        response = {"base_resp": {"status_code": 1004, "status_msg": "invalid key"}}
        with mock.patch(f"{NATIVE_MODULE}._post_json", return_value=response):
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate({"model": "image-01", "prompt": "p"})
        self.assertIn("minimax_api_error", str(ctx.exception))


class IdeogramProviderTests(unittest.TestCase):
    def _provider(self):
        return IdeogramImageProvider(api_key="id-key", base_url="https://api.ideogram.ai/v1")

    def test_generate_posts_multipart_with_x_ratio(self):
        provider = self._provider()
        response = {"data": [{"url": "https://img/a.png"}]}
        with mock.patch(f"{NATIVE_MODULE}._post_multipart", return_value=response) as post, \
                mock.patch(f"{NATIVE_MODULE}._download_image_b64", return_value="aWQ=") as dl:
            images = provider.generate(
                {"model": "ideogram-v3-turbo", "prompt": "typography poster", "size": "1920x1080"}
            )
        self.assertEqual(images, ["aWQ="])
        dl.assert_called_once_with("https://img/a.png")
        url, kwargs = post.call_args[0][0], post.call_args[1]
        self.assertEqual(url, "https://api.ideogram.ai/v1/ideogram-v3/generate")
        self.assertEqual(kwargs["headers"], {"Api-Key": "id-key"})
        self.assertEqual(kwargs["fields"]["aspect_ratio"], "16x9")
        self.assertEqual(kwargs["fields"]["model"], "ideogram-v3-turbo")

    def test_missing_data_fails_clearly(self):
        provider = self._provider()
        with mock.patch(f"{NATIVE_MODULE}._post_multipart", return_value={"data": []}):
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate({"model": "ideogram-v3-turbo", "prompt": "p"})
        self.assertIn("ideogram_image_missing", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
