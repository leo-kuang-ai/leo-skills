"""config ui 控制台 HTTP API 的集成测试。

以真实 ThreadingHTTPServer（127.0.0.1 随机端口）+ 假 ConfigService 起
服，覆盖计划 U2：token/Host/body 加固、overview/channels 读面、
configure 四种凭据模式（含零回显断言）、终态会话三终态与单例互斥、
治理端点路由。U3 的页面静态断言也挂在本文件（见 StaticAssetTests）。
"""

from __future__ import annotations

import copy
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))
TESTS_DIR = SKILL_DIR / "tests"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from leo_ppt_generator.config.models import ProviderName  # noqa: E402
from leo_ppt_generator.credentials import CredentialInputChannel  # noqa: E402
from leo_ppt_generator.config.service import ConfigServiceError  # noqa: E402
from leo_ppt_generator.config.web import (  # noqa: E402
    TerminalEntryCoordinator,
    _read_html_asset,
    create_config_ui_server,
)
from leo_ppt_generator.runs_console import RunScanner  # noqa: E402
from runs_fixture import make_run  # noqa: E402

ASSET_PATH = RUNTIME_SRC / "leo_ppt_generator" / "config" / "assets" / "config-ui.html"
JS_ASSET_PATH = RUNTIME_SRC / "leo_ppt_generator" / "config" / "assets" / "config-ui.js"
PYPROJECT_PATH = SKILL_DIR / "runtime" / "pyproject.toml"


def _report(status="configured_unverified", reason="provider_verification_not_run"):
    return SimpleNamespace(
        status=SimpleNamespace(value=status),
        reason_code=reason,
        to_dict=lambda: {"status": status, "reason_code": reason},
    )


class FakeService:
    def __init__(self, profiles=None):
        self.calls: list[tuple] = []
        self.profiles = profiles or {}
        self.raise_on_configure: Exception | None = None
        self._overview = {
            "report": {
                "status": "configured_unverified",
                "reason_code": "provider_verification_not_run",
                "providers": [
                    {
                        "provider": "zhipu",
                        "verification": {"status": "not_run"},
                    }
                ],
            },
            "selection": {
                "provider": "zhipu",
                "source": "config",
                "priority": 10,
                "config_digest": "digest",
                "mode": "automatic",
            },
            "selection_error": None,
            "mode": "automatic",
            "providers": [
                {
                    "provider": "zhipu",
                    "configured": True,
                    "enabled": True,
                    "priority": 10,
                    "credential_available": True,
                    "selected": True,
                    "reason_code": "provider_verification_not_run",
                    "model": "cogview-4",
                }
            ],
            "actions": ["edit_selected", "add_provider", "reorder", "prefer"],
        }

    def overview(self, request, **kwargs):
        self.calls.append(("overview",))
        return SimpleNamespace(to_dict=lambda: copy.deepcopy(self._overview))

    def set_preferred_provider(self, request, *, provider, operation_id):
        self.calls.append(("prefer", str(provider), operation_id))
        return _report()

    def clear_preferred_provider(self, request, *, operation_id):
        self.calls.append(("auto", operation_id))
        return _report()

    def reorder_provider_priorities(self, providers):
        self.calls.append(("reorder", [str(item) for item in providers]))

    def remove_provider(self, provider, *, operation_id):
        self.calls.append(("remove", str(provider), operation_id))
        return "provider_removed"

    def set_provider_enabled(self, provider, *, enabled):
        self.calls.append(("enabled", str(provider), enabled))

    def set_provider_priority(self, provider, *, priority):
        self.calls.append(("priority", str(provider), priority))

    def configure(self, request):
        self.calls.append(("configure", request))
        if self.raise_on_configure is not None:
            raise self.raise_on_configure
        return _report()

    @property
    def config_store(self):
        service = self

        class _Store:
            def read(self):
                return SimpleNamespace(
                    values={"provider_profiles": service.profiles},
                    document={"provider_profiles": service.profiles},
                    canonical_digest="digest",
                )

        return _Store()


def _wait_for(predicate, timeout=2.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return predicate()


class ConsoleServerTestCase(unittest.TestCase):
    def setUp(self):
        self.service = FakeService()
        self._getpass_hook = None
        self._runs_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._runs_tmp.cleanup)
        self.runs_home = Path(self._runs_tmp.name)
        self.server, self.token, self.url = create_config_ui_server(
            self.service,
            tty_probe=lambda: True,
            getpass_fn=self._getpass,
            run_scanner=RunScanner(self.runs_home),
        )
        self.port = self.server.server_port
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def _getpass(self, prompt):
        if self._getpass_hook is not None:
            return self._getpass_hook(prompt)
        return "sk-test-injected"

    def request(self, method, path, body=None, *, token="default", host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if token == "default":
            token = self.token
        if token:
            headers["X-Leo-UI-Token"] = token
        if host is not None:
            conn.putrequest(method, path, skip_host=True)
            conn.putheader("Host", host)
            for key, value in headers.items():
                conn.putheader(key, value)
            conn.endheaders(payload)
        else:
            conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        parsed = None
        if data.startswith(b"{"):
            parsed = json.loads(data)
        return response, parsed, data

    def configure_body(self, provider="zhipu", **overrides):
        body = {
            "provider": provider,
            "model": "cogview-4",
            "credential": {"mode": "env"},
        }
        body.update(overrides)
        return body

    def configure_calls(self):
        return [call for call in self.service.calls if call[0] == "configure"]

    # ------------------------------------------------------------- 加固
    def test_every_post_endpoint_requires_token(self):
        endpoints = [
            ("/api/prefer", {"provider": "zhipu"}),
            ("/api/auto", {}),
            ("/api/provider/configure", self.configure_body()),
            ("/api/provider/enabled", {"provider": "zhipu", "value": False}),
            ("/api/provider/remove", {"provider": "zhipu"}),
            ("/api/provider/reorder", {"providers": ["zhipu"]}),
        ]
        for path, body in endpoints:
            with self.subTest(path=path):
                response, payload, _ = self.request("POST", path, body, token="")
                self.assertEqual(response.status, 403, path)
                self.assertEqual(payload.get("reason_code"), "forbidden")

    def test_terminal_poll_requires_token(self):
        response, payload, _ = self.request(
            "GET", "/api/credential/session/whatever", token=""
        )
        self.assertEqual(response.status, 403)
        self.assertEqual(payload.get("reason_code"), "forbidden")

    def test_bad_host_header_is_rejected(self):
        response, payload, _ = self.request(
            "GET", "/api/overview", host="evil.example"
        )
        self.assertEqual(response.status, 403)
        self.assertEqual(payload.get("reason_code"), "host_forbidden")

    def test_oversized_body_is_rejected(self):
        body = {
            "provider": "zhipu",
            "credential": {"mode": "web", "secret": "x" * (64 * 1024 + 256)},
        }
        response, payload, _ = self.request("POST", "/api/provider/configure", body)
        self.assertEqual(response.status, 413)
        self.assertEqual(payload.get("reason_code"), "request_body_too_large")
        self.assertEqual(self.configure_calls(), [])

    # ------------------------------------------------------------- 读面
    def test_overview_returns_full_payload_and_capabilities(self):
        response, payload, _ = self.request("GET", "/api/overview")
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["mode"], "automatic")
        self.assertTrue(payload["providers"][0]["configured"])
        self.assertIn("add_provider", payload["actions"])
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        self.assertTrue(payload["capabilities"]["terminal_entry"])

    def test_overview_preserves_nested_verification_contract(self):
        # 后端契约：ProviderReport.to_dict() 把验证状态序列化为嵌套
        # verification.status；页面 verificationOf() 按此键读取。
        response, payload, _ = self.request("GET", "/api/overview")
        entry = payload["report"]["providers"][0]
        self.assertEqual(entry["verification"]["status"], "not_run")

    def test_channels_payload_lists_featured_first_and_public_fields_only(self):
        response, payload, _ = self.request("GET", "/api/channels")
        self.assertEqual(response.status, 200)
        channels = payload["channels"]
        self.assertTrue(channels[0]["featured"])
        self.assertEqual(channels[0]["id"], "qianxing")
        by_id = {item["id"]: item for item in channels}
        zhipu = by_id["zhipu"]
        self.assertEqual(zhipu["credential_environment"], "ZHIPU_API_KEY")
        self.assertIn("cogview-4", zhipu["models"])
        for item in channels:
            self.assertNotIn("secret", item)
            self.assertNotIn("api_key", item)
        compatible = {
            item["id"]: item for item in payload["builtin"]
        }["openai-compatible"]
        self.assertTrue(compatible["requires_endpoint"])

    def test_index_serves_html_and_sets_cookie_on_token_bootstrap(self):
        response, _, data = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/html; charset=utf-8")
        self.assertIn(b"<html", data[:200])
        # 首屏注入行为断言：服务端把初始状态写成 window.__LEO_INITIAL__= 赋值。
        self.assertIn(b"window.__LEO_INITIAL__=", data)
        self.assertIsNone(response.getheader("Set-Cookie"))
        response, _, _ = self.request(
            "GET", f"/?token={self.token}", token=""
        )
        cookie = response.getheader("Set-Cookie") or ""
        self.assertIn("leo_ui_token=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)

    # ------------------------------------------------- configure：四种模式
    def test_configure_web_mode_writes_secret_and_never_echoes_it(self):
        secret = "sk-live-web-9f31aa"
        response, payload, raw = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "web", "secret": secret}),
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["provider"], "zhipu")
        self.assertNotIn("credential", payload)
        self.assertNotIn(secret, raw.decode("utf-8"))
        calls = self.configure_calls()
        self.assertEqual(len(calls), 1)
        request = calls[0][1]
        self.assertIs(request.credential.channel, CredentialInputChannel.EXPLICIT_STDIN)
        self.assertIsNotNone(request.credential.secret)
        self.assertEqual(request.credential.secret.reveal_text(), secret)
        self.assertFalse(request.overwrite_credential)

    def test_configure_web_mode_replaces_os_store_with_overwrite(self):
        self.service.profiles = {
            "zhipu": {"credential_source": "os-store-reference", "credential_ref": "zhipu@1"}
        }
        response, payload, _ = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "web", "secret": "sk-new-1"}),
        )
        self.assertEqual(response.status, 200)
        request = self.configure_calls()[0][1]
        self.assertTrue(request.overwrite_credential)

    def test_configure_web_mode_requires_non_empty_secret(self):
        for secret in ("", None, "   "):
            with self.subTest(secret=secret):
                response, payload, _ = self.request(
                    "POST",
                    "/api/provider/configure",
                    self.configure_body(credential={"mode": "web", "secret": secret}),
                )
                self.assertEqual(response.status, 400)
                self.assertEqual(payload.get("reason_code"), "credential_secret_missing")
        self.assertEqual(self.configure_calls(), [])

    def test_configure_env_mode_uses_channel_environment_reference(self):
        response, payload, _ = self.request(
            "POST", "/api/provider/configure", self.configure_body()
        )
        self.assertEqual(response.status, 200)
        request = self.configure_calls()[0][1]
        self.assertIs(request.credential.channel, CredentialInputChannel.ENVIRONMENT)
        self.assertEqual(request.credential.credential_ref, "env:ZHIPU_API_KEY")
        self.assertIsNone(request.credential.secret)

    def test_configure_unknown_provider_is_rejected(self):
        response, payload, _ = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(provider="nope"),
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(payload.get("reason_code"), "unknown_provider")

    def test_configure_surfaces_service_validation_reason(self):
        self.service.raise_on_configure = ConfigServiceError(
            "provider_profile_invalid:endpoint_origin"
        )
        response, payload, _ = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(
                endpoint_origin="https://bad.example/path?q=1"
            ),
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(payload.get("reason_code"), "provider_profile_invalid:endpoint_origin")

    def test_configure_keep_mode_reuses_existing_reference(self):
        self.service.profiles = {
            "zhipu": {
                "credential_source": "environment-reference",
                "credential_ref": "ZHIPU_API_KEY",
            }
        }
        response, payload, _ = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "keep"}),
        )
        self.assertEqual(response.status, 200)
        request = self.configure_calls()[0][1]
        self.assertIs(request.credential.channel, CredentialInputChannel.ENVIRONMENT)
        self.assertEqual(request.credential.credential_ref, "ZHIPU_API_KEY")

    def test_configure_keep_mode_requires_existing_credential(self):
        response, payload, _ = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "keep"}),
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(payload.get("reason_code"), "credential_input_channel_unavailable")

    def test_configure_failure_closes_secret_buffer(self):
        self.service.raise_on_configure = ConfigServiceError(
            "provider_profile_invalid:endpoint_origin"
        )
        response, payload, _ = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(
                endpoint_origin="https://bad.example/p?q=1",
                credential={"mode": "web", "secret": "sk-should-close"},
            ),
        )
        self.assertEqual(response.status, 400)
        secret = self.configure_calls()[0][1].credential.secret
        self.assertTrue(secret.closed)

    # ------------------------------------------------- 终态会话三终态
    def test_terminal_entry_unavailable_without_tty(self):
        service = FakeService()
        server, token, _ = create_config_ui_server(
            service, tty_probe=lambda: False, getpass_fn=lambda prompt: "sk-x"
        )
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request(
            "POST",
            "/api/provider/configure",
            body=json.dumps(
                self.configure_body(credential={"mode": "terminal"})
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Leo-UI-Token": token,
            },
        )
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
        self.assertEqual(response.status, 409)
        self.assertEqual(payload.get("reason_code"), "terminal_entry_unavailable")
        self.assertEqual(service.calls, [])

    def test_terminal_session_eof_fails_without_configure(self):
        def hook(prompt):
            raise EOFError

        self._getpass_hook = hook
        response, payload, _ = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "terminal"}),
        )
        self.assertEqual(response.status, 202)
        session_id = payload["session"]["id"]
        result = _wait_for(
            lambda: self.request(
                "GET", f"/api/credential/session/{session_id}"
            )[1].get("state")
            == "error"
        )
        self.assertTrue(result)
        _, polled, _ = self.request("GET", f"/api/credential/session/{session_id}")
        self.assertEqual(polled["reason_code"], "credential_input_cancelled_or_eof")
        self.assertEqual(self.configure_calls(), [])

    def test_terminal_session_completes_with_injected_secret(self):
        self._getpass_hook = lambda prompt: "sk-live-terminal-77c1"
        response, payload, raw = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "terminal"}),
        )
        self.assertEqual(response.status, 202)
        session_id = payload["session"]["id"]
        _wait_for(
            lambda: self.request(
                "GET", f"/api/credential/session/{session_id}"
            )[1].get("state")
            == "completed"
        )
        _, polled, poll_raw = self.request(
            "GET", f"/api/credential/session/{session_id}"
        )
        self.assertEqual(polled["state"], "completed")
        self.assertNotIn("sk-live-terminal-77c1", poll_raw.decode("utf-8"))
        calls = self.configure_calls()
        self.assertEqual(len(calls), 1)
        request = calls[0][1]
        self.assertEqual(request.credential.secret.reveal_text(), "sk-live-terminal-77c1")

    def test_terminal_session_is_singleton_while_pending(self):
        release = threading.Event()

        def hook(prompt):
            release.wait(timeout=5)
            return "sk-live-terminal-single"

        self._getpass_hook = hook
        first = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "terminal"}),
        )
        second = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "terminal"}),
        )
        self.assertEqual(first[0].status, 202)
        self.assertEqual(second[0].status, 202)
        self.assertEqual(
            second[1]["session"]["id"], first[1]["session"]["id"]
        )
        release.set()
        session_id = first[1]["session"]["id"]
        _wait_for(
            lambda: self.request(
                "GET", f"/api/credential/session/{session_id}"
            )[1].get("state")
            == "completed"
        )
        self.assertEqual(len(self.configure_calls()), 1)

    def test_terminal_cancel_discards_late_secret(self):
        release = threading.Event()

        def hook(prompt):
            release.wait(timeout=5)
            return "sk-late-after-cancel"

        self._getpass_hook = hook
        response, payload, _ = self.request(
            "POST",
            "/api/provider/configure",
            self.configure_body(credential={"mode": "terminal"}),
        )
        session_id = payload["session"]["id"]
        response, cancelled, _ = self.request(
            "POST", f"/api/credential/session/{session_id}/cancel", {}
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(cancelled["state"], "error")
        self.assertEqual(cancelled["reason_code"], "terminal_session_cancelled")
        release.set()
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and not self.configure_calls():
            time.sleep(0.02)
        self.assertEqual(self.configure_calls(), [])

    # ------------------------------------------------------------- 治理
    def test_page_image_serves_etag_and_304(self):
        run_id = "a3f2c1d4e5b64708901234567890abcd"
        make_run(self.runs_home, run_id=run_id)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/api/runs/{run_id}/pages/1.png")
        first = conn.getresponse()
        first.read()
        etag = first.getheader("ETag")
        self.assertEqual(first.status, 200)
        self.assertIsNotNone(etag)
        self.assertIn("private", first.getheader("Cache-Control"))
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/api/runs/{run_id}/pages/1.png", headers={"If-None-Match": etag})
        second = conn.getresponse()
        body = second.read()
        conn.close()
        self.assertEqual(second.status, 304)
        self.assertEqual(len(body), 0)

    def test_governance_endpoints_route_to_service(self):
        response, payload, _ = self.request(
            "POST", "/api/prefer", {"provider": "zhipu"}
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["reason_code"], "provider_preferred")
        self.assertEqual(self.service.calls[-1][0], "prefer")

        response, payload, _ = self.request("POST", "/api/auto", {})
        self.assertEqual(payload["reason_code"], "provider_auto_selection_enabled")

        response, payload, _ = self.request(
            "POST", "/api/provider/enabled", {"provider": "zhipu", "value": False}
        )
        self.assertEqual(payload["reason_code"], "provider_preference_updated")
        self.assertEqual(self.service.calls[-1], ("enabled", "zhipu", False))

        response, payload, _ = self.request(
            "POST", "/api/provider/remove", {"provider": "zhipu"}
        )
        self.assertEqual(payload["reason_code"], "provider_removed")

        response, payload, _ = self.request(
            "POST", "/api/provider/reorder", {"providers": ["zhipu", "ark"]}
        )
        self.assertEqual(payload["reason_code"], "provider_priority_reordered")
        self.assertEqual(self.service.calls[-1], ("reorder", ["zhipu", "ark"]))

    def test_enabled_rejects_missing_value(self):
        response, payload, _ = self.request(
            "POST", "/api/provider/enabled", {"provider": "zhipu"}
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(payload.get("reason_code"), "provider_profile_invalid")

    def test_priority_endpoint_routes_to_service(self):
        response, payload, _ = self.request(
            "POST", "/api/provider/priority", {"provider": "zhipu", "priority": 5}
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["reason_code"], "provider_priority_updated")
        self.assertEqual(self.service.calls[-1], ("priority", "zhipu", 5))

    def test_priority_endpoint_rejects_invalid_values(self):
        for bad in (0, 1001, "10", True, None):
            with self.subTest(bad=bad):
                response, payload, _ = self.request(
                    "POST", "/api/provider/priority", {"provider": "zhipu", "priority": bad}
                )
                self.assertEqual(response.status, 400)
                self.assertEqual(payload.get("reason_code"), "provider_priority_invalid")

    def test_legacy_status_endpoint_stays_compatible(self):
        response, payload, _ = self.request("GET", "/api/status")
        self.assertEqual(response.status, 200)
        self.assertIn("status_text", payload)
        self.assertIn("providers", payload)

    # ------------------------------------------------------- 运行任务端点
    def test_runs_endpoints_serve_fixture_run(self):
        run_id = "a3f2c1d4e5b64708901234567890abcd"
        make_run(self.runs_home, run_id=run_id)
        response, payload, _ = self.request("GET", "/api/runs")
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["runs"][0]["run_id"], run_id)

        response, detail, _ = self.request("GET", f"/api/runs/{run_id}")
        self.assertEqual(response.status, 200)
        self.assertEqual(len(detail["pages"]), 12)
        self.assertEqual(detail["events_window"]["bad_lines"], 0)
        self.assertIn(response.getheader("Cache-Control"), ("no-store",))

        response, _, png_data = self.request("GET", f"/api/runs/{run_id}/pages/1.png")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "image/png")
        self.assertGreater(len(png_data), 100)

    def test_runs_endpoints_404_and_reject_sandbox(self):
        run_id = "a3f2c1d4e5b64708901234567890abcd"
        make_run(
            self.runs_home,
            run_id=run_id,
            total=4,
            recorded=2,
            artifact_override={1: "../../evil.png"},
        )
        response, payload, _ = self.request("GET", "/api/runs/" + "f" * 32)
        self.assertEqual(response.status, 404)
        self.assertEqual(payload.get("reason_code"), "run_not_found")
        response, payload, _ = self.request("GET", f"/api/runs/{run_id}/pages/1.png")
        self.assertEqual(response.status, 404)
        self.assertEqual(payload.get("reason_code"), "preview_not_found")
        response, payload, _ = self.request("GET", f"/api/runs/{run_id}/pages/9.png")
        self.assertEqual(response.status, 404)
        # E-R1#4/#9：路由契约负路径——中间段非 pages、int 失败、多余段。
        response, payload, _ = self.request("GET", f"/api/runs/{run_id}/evil/1.png")
        self.assertEqual(response.status, 404)
        response, payload, _ = self.request("GET", f"/api/runs/{run_id}/pages/1x.png")
        self.assertEqual(response.status, 404)
        response, payload, _ = self.request("GET", f"/api/runs/{run_id}/pages/1.png/extra")
        self.assertEqual(response.status, 404)

    def test_runs_detail_survives_bad_number_types(self):
        # E-R1#1：jobs 中 number 为字符串时不得 5xx/断连。
        run_id = "a3f2c1d4e5b64708901234567890abcd"
        run_dir = make_run(self.runs_home, run_id=run_id, total=4, recorded=2)
        jobs_path = run_dir / "image-deck" / "slide_jobs.json"
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
        jobs["slides"][3]["number"] = "4"
        jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
        response, detail, _ = self.request("GET", f"/api/runs/{run_id}")
        self.assertEqual(response.status, 200)
        self.assertEqual(len(detail["pages"]), 4)

    def test_runs_events_pagination_parameter(self):
        run_id = "a3f2c1d4e5b64708901234567890abcd"
        make_run(self.runs_home, run_id=run_id)
        _, detail, _ = self.request("GET", f"/api/runs/{run_id}")
        first_seq = detail["events_window"]["events"][0]["seq"]
        response, earlier, _ = self.request(
            "GET", f"/api/runs/{run_id}?events_before={first_seq}"
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(earlier["events_window"]["events"], [])
        response, payload, _ = self.request(
            "GET", f"/api/runs/{run_id}?events_before=abc"
        )
        self.assertEqual(response.status, 400)

    def test_index_injection_escapes_script_tag(self):
        # PRD FR11：首屏注入的列表字段含磁盘可控字符串（项目目录名可含 "<script>"
        # 开标签——POSIX 目录名仅禁 "/"）；注入必须把 < 转义为 \u003c，
        # 防止内联 script 上下文被拼接逃逸。
        make_run(self.runs_home, project="x<script>alert(1)y")
        response, _, data = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        text = data.decode("utf-8")
        self.assertIn("window.__LEO_INITIAL__=", text)
        self.assertNotIn("<script>alert(1)", text)
        self.assertIn("\\u003cscript\\u003ealert(1)", text)

    def test_serves_js_asset(self):
        # /config-ui.js：与 HTML 同源分发页面脚本（拆分后独立资源）。
        response, _, data = self.request("GET", "/config-ui.js")
        self.assertEqual(response.status, 200)
        self.assertEqual(
            response.getheader("Content-Type"), "application/javascript; charset=utf-8"
        )
        self.assertIn("function boot()", data.decode("utf-8"))


class TerminalTimeoutTests(unittest.TestCase):
    def test_lazy_timeout_discards_late_secret(self):
        service = FakeService()

        def slow_getpass(prompt):
            time.sleep(0.12)
            return "sk-late"

        coordinator = TerminalEntryCoordinator(
            service,
            tty_probe=lambda: True,
            getpass_fn=slow_getpass,
            timeout_seconds=0.03,
        )
        session, error = coordinator.start_or_join(
            provider=ProviderName.ZHIPU,
            model=None,
            endpoint_origin=None,
            request=None,
        )
        self.assertIsNone(error)
        result = _wait_for(
            lambda: coordinator.poll(session["id"])["state"] == "error"
        )
        self.assertTrue(result)
        polled = coordinator.poll(session["id"])
        self.assertEqual(polled["reason_code"], "terminal_session_timeout")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and not service.calls:
            time.sleep(0.02)
        self.assertEqual(
            [call for call in service.calls if call[0] == "configure"], []
        )


class StaticAssetTests(unittest.TestCase):
    """U3 静态断言：页面结构与安全纪律锚点（浏览器行为由人工冒烟覆盖）。"""

    def test_asset_exists_and_is_served_skeleton_contract(self):
        self.assertTrue(ASSET_PATH.is_file())
        self.assertTrue(JS_ASSET_PATH.is_file())

    def test_html_references_external_js(self):
        # 拆分契约：HTML 只保留骨架 + 外链脚本（无内联逻辑）。
        html = ASSET_PATH.read_text(encoding="utf-8")
        self.assertIn('<script src="/config-ui.js"></script>', html)
        self.assertNotIn("function boot()", html)

    def test_asset_resolves_inside_package_not_source_tree(self):
        # 回归：安装态（受管 venv）没有技能根 assets/ 目录，页面资产必须
        # 从包内解析（providers.yaml 同范式），否则 GET / 返回
        # config_ui_asset_missing（用户实测缺陷）。
        text = _read_html_asset()
        self.assertIn("<!doctype html>", text[:40].lower())
        self.assertIn("LEO_INITIAL_STATE", text)

    def test_pyproject_declares_config_asset_package_data(self):
        # 打包防回退：package-data 必须覆盖 config/assets/*（html+js），
        # 否则 pip 安装态不随包分发页面资产。
        text = PYPROJECT_PATH.read_text(encoding="utf-8")
        self.assertIn('"config/assets/*"', text)

    def test_add_section_shows_all_channels_with_reconfigure(self):
        # 添加区展示 CLI 支持的全量渠道：已配置的标「已配置」并提供
        # "重新配置"（换密钥入口），不再隐藏（用户实测：已配置渠道
        # 从添加区消失，误以为页面目录缺渠道且无从换密钥）。
        js = JS_ASSET_PATH.read_text(encoding="utf-8")
        self.assertIn("已配置 ✓", js)
        self.assertIn("重新配置", js)
        self.assertIn("card-configured", js)
        self.assertIn("openWizard(providerId, isConfigured)", js)
        # 渲染循环不得再按 configured 跳过（防回退到隐藏模式）。
        self.assertNotIn("if (configured.has(channel.id)) return", js)
        self.assertNotIn("if (configured.has(providerId)) return", js)

    def test_web_channel_catalog_matches_cli_wizard_providers(self):
        # 契约：web 添加区渠道全集 == CLI 向导可选 provider 全集
        # （channel_catalog + 内置三项）。两侧同源，此测试防未来漂移
        # 导致"页面缺渠道"。BUILTIN_IMAGEGEN 是宿主内置非用户配置项，
        # 不在 CLI 选择菜单。
        import re as _re

        from leo_ppt_generator.config import channel_catalog
        from leo_ppt_generator.config.web import _BUILTIN_PROVIDER_LABELS, _channels_payload

        payload = _channels_payload()
        web_ids = {c["id"] for c in payload["channels"]} | {b["id"] for b in payload["builtin"]}
        wizard_src = (
            RUNTIME_SRC / "leo_ppt_generator" / "config" / "wizard.py"
        ).read_text(encoding="utf-8")
        cli_builtin = {
            name.lower().replace("_", "-")
            for name in _re.findall(r"ProviderName\.([A-Z_]+)\b", wizard_src)
            if name != "BUILTIN_IMAGEGEN"
        }
        cli_ids = {channel.id for channel in channel_catalog.channels()} | cli_builtin
        self.assertEqual(web_ids, cli_ids)
        self.assertEqual(
            set(_BUILTIN_PROVIDER_LABELS),
            {"openai", "openai-compatible", "atlascloud"},
        )

    def test_asset_has_no_alert_and_no_inline_dynamic_handlers(self):
        for path in (ASSET_PATH, JS_ASSET_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("alert(", text)
            self.assertNotIn("onclick=", text)

    def test_asset_has_security_anchors(self):
        # 密钥输入由 JS 构造：断言构造参数而非 HTML 属性字面量。
        js = JS_ASSET_PATH.read_text(encoding="utf-8")
        html = ASSET_PATH.read_text(encoding="utf-8")
        self.assertIn('type: "password"', js)
        self.assertIn('autocomplete: "off"', js)
        self.assertIn("noopener noreferrer", js)
        self.assertIn("textContent", js)
        self.assertIn("no-referrer", html)
        # 验证徽标读取嵌套契约键，防止回退到扁平键导致徽标静默消失。
        self.assertIn("entry.verification.status", js)
        self.assertNotIn("entry.verification_state", js)
        # 添加区/猜测首个可加渠道的排除集必须过滤 configured:true
        # （overview.providers 是全量名册），否则空配置时添加区误判空。
        self.assertGreaterEqual(
            js.count(".filter((item) => item.configured)"), 3
        )
        # 权重直接配置（自动模式）：数字输入 + 专用端点。
        self.assertIn('type: "number"', js)
        self.assertIn("/api/provider/priority", js)
        self.assertIn("权重 ", js)
        # 当前使用渠道的卡片级强调：专属样式 + 实底徽标。
        self.assertIn("chan current", js)
        self.assertIn("● 当前使用", js)
        self.assertIn(".tag.current", html)

    def test_event_labels_align_with_writer_kinds(self):
        # 架构评审#4b：前端 EVENT_LABELS 的键必须与写侧（cli.py + run_index.py）
        # 实际发射的事件 kind 全集一致；ignore 为阶段名/命令/文件名字面量噪声。
        import re as _re

        source = (
            RUNTIME_SRC / "leo_ppt_generator" / "cli.py"
        ).read_text(encoding="utf-8") + (
            RUNTIME_SRC / "leo_ppt_generator" / "application" / "run_index.py"
        ).read_text(encoding="utf-8")
        extracted = set(
            _re.findall(r'["\']((?:run|image|editable|upgrade)\.[a-z_]+)["\']', source)
        )
        ignore = {
            "editable.dispatch", "editable.finalize", "image.dispatch",
            "image.finalize", "image.inspect", "run.cancel", "run.json",
        }
        writer_kinds = extracted - ignore
        js = JS_ASSET_PATH.read_text(encoding="utf-8")
        block = js.split("const EVENT_LABELS = {", 1)[1].split("};", 1)[0]
        frontend_kinds = set(_re.findall(r'^\s{2}"([^"]+)":', block, _re.MULTILINE))
        self.assertEqual(frontend_kinds, writer_kinds)

    def test_asset_has_runs_console_anchors(self):
        js = JS_ASSET_PATH.read_text(encoding="utf-8")
        html = ASSET_PATH.read_text(encoding="utf-8")
        # 双 Tab 与任务视图容器（HTML id）。
        for anchor in ("tab-channels", "tab-runs", "runs-view", "runs-list", "run-detail"):
            self.assertIn(anchor, html)
        # a11y：aria-live 离屏区、双重编码图标、lightbox 对话框与键盘翻页。
        self.assertIn('aria-live="polite"', html)
        self.assertIn("PAGE_STATE_ICONS", js)
        self.assertIn("page-lightbox", html)
        self.assertIn("ArrowLeft", js)
        # 轮询礼仪：不可见暂停 + visibilitychange 恢复拉取。
        self.assertIn("document.hidden", js)
        self.assertIn("visibilitychange", js)
        # 渲染纪律：任务视图沿用 textContent（无 innerHTML）。
        self.assertNotIn("innerHTML", js)

    def test_asset_has_structure_anchors(self):
        text = ASSET_PATH.read_text(encoding="utf-8")
        for anchor in (
            "configured-list",
            "add-list",
            "config-wizard",
            "confirm-remove",
            "toast",
            "LEO_INITIAL",
        ):
            self.assertIn(anchor, text)


if __name__ == "__main__":
    unittest.main()
