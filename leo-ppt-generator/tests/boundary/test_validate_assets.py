#!/usr/bin/env python3
"""validate_assets.py 行为测试：本地存在性 / 假 URL 闭环 / https-only /
缓存 diff / offline 不联网。URL 探测语义用进程内 monkeypatch 覆盖（200/404/405），
CLI 契约用子进程断言退出码，不依赖外网。"""
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_assets.py"


def _png_bytes(color):
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 36), color).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_BYTES = _png_bytes((200, 200, 200))
PNG_BYTES_ALT = _png_bytes((10, 10, 10))


def run(args):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )
    return result.returncode, result.stdout + result.stderr


def load_module():
    spec = importlib.util.spec_from_file_location("validate_assets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_manifest(root: Path, visuals):
    manifest = {
        "schema_version": 1,
        "manifest_kind": "visual-sources",
        "route": "generate",
        "pages": [{"page_id": "slide_01", "visuals": visuals}],
    }
    path = root / "content" / "sources-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


class LocalAssetTest(unittest.TestCase):
    def test_missing_local_asset_fails(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = write_manifest(
                root,
                [
                    {
                        "visual_id": "v1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "source_ref": "sources/missing.png",
                        "source_sha256": None,
                        "backend": "user",
                    }
                ],
            )
            code, out = run([str(path), "--no-cache"])
            self.assertEqual(code, 1, out)
            self.assertIn("missing", out)

    def test_local_png_with_matching_sha_passes(self):
        import hashlib

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "sources").mkdir()
            (root / "sources" / "fig.png").write_bytes(PNG_BYTES)
            path = write_manifest(
                root,
                [
                    {
                        "visual_id": "v1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "source_ref": "sources/fig.png",
                        "source_sha256": hashlib.sha256(PNG_BYTES).hexdigest(),
                        "backend": "user",
                    }
                ],
            )
            code, out = run([str(path), "--no-cache"])
            self.assertEqual(code, 0, out)

    def test_sha_mismatch_fails(self):
        import hashlib

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "sources").mkdir()
            (root / "sources" / "fig.png").write_bytes(PNG_BYTES)
            path = write_manifest(
                root,
                [
                    {
                        "visual_id": "v1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "source_ref": "sources/fig.png",
                        "source_sha256": hashlib.sha256(b"other").hexdigest(),
                        "backend": "user",
                    }
                ],
            )
            code, out = run([str(path), "--no-cache"])
            self.assertEqual(code, 1, out)
            self.assertIn("sha_mismatch", out)

    def test_not_an_image_fails(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "sources").mkdir()
            (root / "sources" / "note.txt").write_text("不是图片", encoding="utf-8")
            path = write_manifest(
                root,
                [
                    {
                        "visual_id": "v1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "source_ref": "sources/note.txt",
                        "source_sha256": None,
                        "backend": "user",
                    }
                ],
            )
            code, out = run([str(path), "--no-cache"])
            self.assertEqual(code, 1, out)
            self.assertIn("not_image", out)


class UrlSchemeTest(unittest.TestCase):
    def test_http_scheme_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = write_manifest(
                root,
                [
                    {
                        "visual_id": "v1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "source_ref": "http://example.com/fig.png",
                        "source_sha256": None,
                        "backend": "user",
                    }
                ],
            )
            code, out = run([str(path), "--no-cache"])
            self.assertEqual(code, 1, out)
            self.assertIn("bad_scheme", out)

    def test_fabricated_domain_fails_closed(self):
        """编造 URL（RFC2606 .invalid 不可解析域）必须判不可达，不编造可达结论。"""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = write_manifest(
                root,
                [
                    {
                        "visual_id": "v1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "source_ref": "https://q3-growth.example.invalid/chart.png",
                        "source_sha256": None,
                        "backend": "user",
                    }
                ],
            )
            code, out = run([str(path), "--no-cache"])
            self.assertEqual(code, 1, out)
            self.assertIn("unreachable", out)


class OfflineModeTest(unittest.TestCase):
    def test_offline_skips_urls_quickly_without_network(self):
        """offline 模式完全不联网：黑洞地址若真发起请求会耗满 10s 超时。"""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = write_manifest(
                root,
                [
                    {
                        "visual_id": "v1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "source_ref": "https://10.255.255.1/chart.png",
                        "source_sha256": None,
                        "backend": "user",
                    }
                ],
            )
            started = time.monotonic()
            code, out = run([str(path), "--offline", "--no-cache"])
            elapsed = time.monotonic() - started
            self.assertEqual(code, 2, out)
            self.assertIn("skipped_offline", out)
            self.assertLess(elapsed, 5, f"offline 模式疑似发起了网络请求（{elapsed:.1f}s）")


class CacheDiffTest(unittest.TestCase):
    def test_cache_diff_reports_replacement(self):
        import hashlib

        visuals_ok = [
            {
                "visual_id": "v1",
                "kind": "figure",
                "source_class": "user-material",
                "tier": "引用",
                "source_ref": "sources/fig.png",
                "source_sha256": None,
                "backend": "user",
            }
        ]
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "sources").mkdir()
            (root / "sources" / "fig.png").write_bytes(PNG_BYTES)
            path = write_manifest(root, visuals_ok)
            cache = root / "cache.json"
            code, out = run([str(path), "--cache", str(cache)])
            self.assertEqual(code, 0, out)
            first = json.loads(cache.read_text(encoding="utf-8"))
            self.assertEqual(first["sources/fig.png"]["status"], "ok")
            # 素材被替换为缺失 → 重验输出替换前后状态 diff，退出 1。
            (root / "sources" / "fig.png").unlink()
            code, out = run([str(path), "--cache", str(cache)])
            self.assertEqual(code, 1, out)
            self.assertIn("missing", out)
            self.assertIn("ok -> missing", out.replace(" ", " "))
            self.assertIn("替换/变化", out)

    def test_cache_is_not_a_pass_substitute(self):
        """缓存记 ok 后素材损坏，重跑仍须失败（缓存永不替代实测）。"""
        import hashlib

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "sources").mkdir()
            (root / "sources" / "fig.png").write_bytes(PNG_BYTES)
            path = write_manifest(
                root,
                [
                    {
                        "visual_id": "v1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "source_ref": "sources/fig.png",
                        "source_sha256": hashlib.sha256(PNG_BYTES).hexdigest(),
                        "backend": "user",
                    }
                ],
            )
            cache = root / "cache.json"
            self.assertEqual(run([str(path), "--cache", str(cache)])[0], 0)
            (root / "sources" / "fig.png").write_bytes(PNG_BYTES_ALT)
            code, out = run([str(path), "--cache", str(cache)])
            self.assertEqual(code, 1, out)


class CheckUrlSemanticsTest(unittest.TestCase):
    """进程内覆盖 URL 探测分支：200 ok / 404 fail / 405 降级 GET。"""

    def setUp(self):
        self.module = load_module()

    def _patch(self, statuses):
        import urllib.request

        calls = []

        class FakeResponse:
            def __init__(self, status, url, headers):
                self.status = status
                self._url = url
                self.headers = headers

            def geturl(self):
                return self._url

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=None):
            calls.append(request.get_method())
            status, headers = statuses.pop(0)
            return FakeResponse(status, request.full_url, headers)

        self._orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", self._orig)
        return calls

    def test_200_head_is_ok(self):
        import email.message

        calls = self._patch([(200, email.message.Message())])
        original_target_check = self.module._unsafe_url_target
        self.module._unsafe_url_target = lambda ref: None
        self.addCleanup(setattr, self.module, "_unsafe_url_target", original_target_check)
        result = self.module.check_url("https://example.com/a.png")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(calls, ["HEAD"])

    def test_404_fails_closed(self):
        import urllib.error

        import urllib.request

        orig = urllib.request.urlopen

        def fake_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, io.BytesIO(b""))

        urllib.request.urlopen = fake_urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", orig)
        original_target_check = self.module._unsafe_url_target
        self.module._unsafe_url_target = lambda ref: None
        self.addCleanup(setattr, self.module, "_unsafe_url_target", original_target_check)
        result = self.module.check_url("https://example.com/a.png")
        self.assertEqual(result["status"], "unreachable")
        self.assertIn("404", result["detail"])

    def test_405_falls_back_to_ranged_get(self):
        import email.message
        import urllib.error

        import urllib.request

        calls = []

        class FakeResponse:
            def __init__(self, status, url):
                self.status = status
                self._url = url
                self.headers = email.message.Message()

            def geturl(self):
                return self._url

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=None):
            calls.append(request.get_method())
            if request.get_method() == "HEAD":
                raise urllib.error.HTTPError(
                    request.full_url, 405, "Method Not Allowed", None, io.BytesIO(b"")
                )
            return FakeResponse(206, request.full_url)

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", orig)
        original_target_check = self.module._unsafe_url_target
        self.module._unsafe_url_target = lambda ref: None
        self.addCleanup(setattr, self.module, "_unsafe_url_target", original_target_check)
        result = self.module.check_url("https://example.com/a.png")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(calls, ["HEAD", "GET"])

    def test_private_literal_target_is_rejected_before_request(self):
        with mock.patch.object(self.module.urllib.request, "urlopen") as urlopen:
            result = self.module.check_url("https://127.0.0.1/chart.png")
        self.assertEqual(result["status"], "unreachable")
        self.assertIn("私网/回环/本机", result["detail"])
        urlopen.assert_not_called()

    def test_private_redirect_target_is_rejected(self):
        import email.message

        class FakeResponse:
            status = 302
            headers = email.message.Message()

            def geturl(self):
                return "https://127.0.0.1/internal.png"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        original_target_check = self.module._unsafe_url_target
        def allow_initial(ref):
            return None if "example.com" in ref else original_target_check(ref)
        with mock.patch.object(self.module.urllib.request, "urlopen", return_value=FakeResponse()):
            with mock.patch.object(self.module, "_unsafe_url_target", side_effect=allow_initial):
                result = self.module.check_url("https://example.com/chart.png")
        self.assertEqual(result["status"], "unreachable")
        self.assertIn("重定向后的 URL 被拒绝", result["detail"])

    def test_hostname_resolving_to_private_address_is_rejected(self):
        with mock.patch.object(
            self.module.socket,
            "getaddrinfo",
            return_value=[(self.module.socket.AF_INET, self.module.socket.SOCK_STREAM,
                           6, "", ("10.10.0.8", 443))],
        ) as resolver, mock.patch.object(self.module.urllib.request, "urlopen") as urlopen:
            result = self.module.check_url("https://public-looking.example/chart.png")
        self.assertEqual(result["status"], "unreachable")
        self.assertIn("主机名解析到私网", result["detail"])
        resolver.assert_called_once()
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
