"""本地控制台（渠道管理 + 生成任务可视化）。

只提供 localhost 控制面。凭据支持四种录入通道：

- ``web``：密钥在网页一次性提交，服务端立即包装 SecretBuffer 走
  ConfigService 原子事务写入系统钥匙串；明文密钥永不进入任何响应、
  页面、日志或 config.yaml（config.yaml 只存 credential_ref）。
- ``terminal``：终端 getpass 录入会话（页面触发、终端输入、轮询感知）；
  密钥字节不经过浏览器。
- ``env``：环境变量引用，零密钥流量。
- ``keep``：保留 profile 现有凭据引用（仅修改已有渠道时可用）。

CLI 命令始终是等效替代路径；本模块只做路由、鉴权与终态会话编排，
不持有任何 profile 写规则（ConfigService 是唯一编排 owner）。
"""

from __future__ import annotations

import json
import secrets
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from ..credentials import (
    PROVIDERS,
    CredentialInputChannel,
    CredentialInputSelection,
    SecretBuffer,
)
from ..runs_console import (
    PreviewLookupError,
    RunLookupError,
    RunScanner,
)
from . import channel_catalog
from .models import ProviderName
from .runtime_config import default_home
from .service import ConfigService, ConfigureRequest, StatusRequest

MAX_BODY_BYTES = 64 * 1024
TERMINAL_SESSION_TIMEOUT_SECONDS = 300
COOKIE_NAME = "leo_ui_token"
ASSET_INITIAL_MARKER = "<!--LEO_INITIAL_STATE-->"
_BUILTIN_PROVIDER_LABELS = {
    "openai": "OpenAI 官方",
    "openai-compatible": "自定义中转站（OpenAI 兼容）",
    "atlascloud": "AtlasCloud",
}


def _reason_of(exc: BaseException) -> str:
    reason = getattr(exc, "reason_code", None)
    if isinstance(reason, str) and reason:
        return reason
    text = str(exc).strip()
    return text or type(exc).__name__


def _default_tty_probe() -> bool:
    # 保守近似：getpass 实际绑定控制终端（/dev/tty），stdin 被重定向但
    # 控制终端可用的边角会被降级隐藏——属可接受的失败安全方向。
    try:
        return bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        return False


def _default_getpass(prompt: str) -> str:
    import getpass

    return getpass.getpass(prompt)


def _replacing_os_store(service: ConfigService, provider: ProviderName) -> bool:
    """网页/终态新密钥对已有 os-store 凭据即"更换密钥"。

    向导中用户显式选择输入新密钥视为覆盖确认；否则事务会以
    覆盖确认类 reason_code 拒绝。
    """

    try:
        snapshot = service.config_store.read()
    except Exception:
        return False
    profile = snapshot.values.get("provider_profiles", {}).get(provider.value)
    return isinstance(profile, dict) and profile.get("credential_source") == "os-store-reference"


class TerminalEntryCoordinator:
    """终端 getpass 录入会话：单活跃会话、轮询感知、懒超时。

    只负责触发、互斥、状态与失败传播；configure 事务由 ConfigService
    原子完成（密钥到位前不写任何 profile）。取消语义：页面"取消"即
    停止轮询放弃本次配置，服务端不中断 getpass，会话由超时/EOF/正常
    完成收束（状态机 pending → completed | error）。
    """

    def __init__(
        self,
        service: ConfigService,
        *,
        tty_probe: Callable[[], bool] | None = None,
        getpass_fn: Callable[[str], str] | None = None,
        timeout_seconds: float = TERMINAL_SESSION_TIMEOUT_SECONDS,
    ) -> None:
        self._service = service
        self._tty_probe = tty_probe or _default_tty_probe
        self._getpass = getpass_fn or _default_getpass
        self._timeout = timeout_seconds
        self._lock = threading.Lock()
        self._session: dict[str, Any] | None = None

    def entry_available(self) -> bool:
        return self._tty_probe()

    def start_or_join(
        self,
        *,
        provider: ProviderName,
        model: str | None,
        endpoint_origin: str | None,
        request: StatusRequest,
    ) -> tuple[dict[str, Any] | None, str | None]:
        with self._lock:
            if not self._tty_probe():
                return None, "terminal_entry_unavailable"
            pending = self._pending_locked()
            if pending is not None:
                return pending, None
            session: dict[str, Any] = {
                "id": secrets.token_urlsafe(16),
                "provider": provider,
                "model": model,
                "endpoint_origin": endpoint_origin,
                "request": request,
                "state": "pending",
                "reason_code": None,
                "created_at": time.monotonic(),
            }
            self._session = session
        threading.Thread(target=self._run, args=(session,), daemon=True).start()
        return session, None

    def poll(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._session
            if session is None or session.get("id") != session_id:
                return {"state": "unknown", "reason_code": "terminal_session_not_found"}
            self._expire_locked(session)
            return {
                "state": session["state"],
                "reason_code": session["reason_code"],
                "provider": session["provider"].value,
            }

    def cancel(self, session_id: str) -> dict[str, Any]:
        """页面取消：会话立即进入 error，worker 收到迟到输入后直接丢弃。"""

        with self._lock:
            session = self._session
            if session is None or session.get("id") != session_id:
                return {"state": "unknown", "reason_code": "terminal_session_not_found"}
            if session["state"] == "pending":
                session["state"] = "error"
                session["reason_code"] = "terminal_session_cancelled"
            return {
                "state": session["state"],
                "reason_code": session["reason_code"],
                "provider": session["provider"].value,
            }

    def _expire_locked(self, session: dict[str, Any]) -> None:
        if (
            session["state"] == "pending"
            and time.monotonic() - session["created_at"] > self._timeout
        ):
            # 懒超时：页面停止等待；迟到的 getpass 结果将被丢弃。
            session["state"] = "error"
            session["reason_code"] = "terminal_session_timeout"

    def _pending_locked(self) -> dict[str, Any] | None:
        session = self._session
        if session is not None and session["state"] == "pending":
            return session
        return None

    def _finish(self, session: dict[str, Any], state: str, reason: str) -> None:
        with self._lock:
            session["state"] = state
            session["reason_code"] = reason

    def _run(self, session: dict[str, Any]) -> None:
        try:
            secret_text = self._getpass(
                f"[config ui] {session['provider'].value} API Key（输入隐藏，回车提交）："
            )
        except (EOFError, KeyboardInterrupt):
            self._finish(session, "error", "credential_input_cancelled_or_eof")
            return
        except Exception as exc:  # getpass 环境异常统一收敛为会话失败
            self._finish(session, "error", _reason_of(exc))
            return
        with self._lock:
            self._expire_locked(session)
            abandoned = session["state"] != "pending"
        if abandoned:
            # 已被取消/超时的会话：迟到输入直接丢弃，不落任何配置。
            return
        if not secret_text or not secret_text.strip():
            self._finish(session, "error", "credential_secret_missing")
            return
        selection = CredentialInputSelection(
            channel=CredentialInputChannel.EXPLICIT_STDIN,
            reason_code="config-ui-terminal-entry",
            secret=SecretBuffer(secret_text),
        )
        try:
            self._service.configure(
                ConfigureRequest(
                    provider=session["provider"],
                    credential=selection,
                    model=session["model"],
                    endpoint_origin=session["endpoint_origin"],
                    status_request=session["request"],
                    operation_id=(
                        f"config-ui-terminal-{session['provider'].value}-{session['id']}"
                    ),
                    overwrite_credential=_replacing_os_store(
                        self._service, session["provider"]
                    ),
                )
            )
        except Exception as exc:
            # service.configure 正常路径的 finally 会关闭 selection；此处兜底
            # 覆盖进入事务块之前的早退 raise（SecretBuffer.close 幂等）。
            try:
                selection.close()
            except Exception:
                pass
            self._finish(session, "error", _reason_of(exc))
            return
        self._finish(session, "completed", "provider_configured")


def _channels_payload() -> dict[str, Any]:
    channels = []
    for channel in channel_catalog.channels():
        channels.append(
            {
                "id": channel.id,
                "display_name": channel.display_name,
                "portal": channel.portal,
                "key_page": channel.key_page,
                "credential_environment": channel.credential_environment,
                "endpoint_origin": channel.endpoint_origin,
                "default_model": channel.default_model,
                "models": list(channel.models),
                "notes": channel.notes,
                "featured": channel.featured,
            }
        )
    channels.sort(key=lambda item: not item["featured"])
    builtin = [
        {
            "id": provider_id,
            "display_name": label,
            "credential_environment": PROVIDERS.get(provider_id),
            "requires_endpoint": provider_id == "openai-compatible",
        }
        for provider_id, label in _BUILTIN_PROVIDER_LABELS.items()
    ]
    return {"channels": channels, "builtin": builtin}


_HTML_ASSET_CACHE: str | None = None
_JS_ASSET_CACHE: str | None = None


def _read_html_asset() -> str:
    # 资产随包分发（与 providers.yaml 同范式）：源码树与受管 venv 安装态
    # 都从包内解析；首次读取后缓存（资产随包不可变，且消除 runtime 切换后
    # 旧进程 GET / 半残态——运维评审#5）。
    global _HTML_ASSET_CACHE
    if _HTML_ASSET_CACHE is not None:
        return _HTML_ASSET_CACHE
    asset = Path(__file__).with_name("assets") / "config-ui.html"
    if not asset.is_file():
        raise FileNotFoundError("config_ui_asset_missing")
    _HTML_ASSET_CACHE = asset.read_text(encoding="utf-8")
    return _HTML_ASSET_CACHE


def _read_js_asset() -> str:
    # 页面脚本独立分发（config-ui.js）：与 HTML 同范式解析与缓存。
    global _JS_ASSET_CACHE
    if _JS_ASSET_CACHE is not None:
        return _JS_ASSET_CACHE
    asset = Path(__file__).with_name("assets") / "config-ui.js"
    if not asset.is_file():
        raise FileNotFoundError("config_ui_asset_missing")
    _JS_ASSET_CACHE = asset.read_text(encoding="utf-8")
    return _JS_ASSET_CACHE


def _escape_inline_json(payload: dict[str, Any]) -> str:
    """首屏 <script> 注入的逃逸防护（PRD FR11）。

    磁盘字符串（项目目录名等）可含 ``</script>``；json.dumps 不转义 ``<``，
    拼入内联 script 前必须转义为 \\u003c/\\u003e。
    """

    return json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")


def build_config_ui_handler(
    service: ConfigService,
    *,
    token: str,
    terminal: TerminalEntryCoordinator,
    runs: RunScanner | None = None,
) -> type[BaseHTTPRequestHandler]:
    owner = service

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_string, *args):
            # 精简访问日志（运维评审#4）：仅 method/path 到 stderr，供排障定位。
            import sys as _sys

            try:
                status = args[0] if args else ""
                _sys.stderr.write(
                    "[config-ui] %s %s %s\n" % (self.command, self.path, status)
                )
            except Exception:
                pass

        # ----------------------------------------------------------- plumbing
        def _json(self, payload: dict[str, Any], status: int = 200, headers: dict[str, str] | None = None):
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def _binary(self, data: bytes, content_type: str, status: int = 200, extra_headers: dict[str, str] | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def _host_allowed(self) -> bool:
            host = (self.headers.get("Host") or "").strip().lower()
            port = self.server.server_port  # type: ignore[attr-defined]
            return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def _cookie_token(self) -> str | None:
            raw = self.headers.get("Cookie") or ""
            for part in raw.split(";"):
                name, _, value = part.strip().partition("=")
                if name == COOKIE_NAME:
                    return value
            return None

        def _authorized(self, parsed) -> bool:
            supplied = (
                self.headers.get("X-Leo-UI-Token")
                or parse_qs(parsed.query).get("token", [None])[0]
                or self._cookie_token()
            )
            return supplied == token

        def _read_json(self) -> dict[str, Any] | None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length > MAX_BODY_BYTES:
                self._json({"reason_code": "request_body_too_large"}, 413)
                return None
            if length <= 0:
                self._json({"reason_code": "request_body_missing"}, 400)
                return None
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json({"reason_code": "request_body_invalid_json"}, 400)
                return None
            if not isinstance(payload, dict):
                self._json({"reason_code": "request_body_invalid_json"}, 400)
                return None
            return payload

        # ---------------------------------------------------------------- GET
        def do_GET(self):
            parsed = urlparse(self.path)
            if not self._host_allowed():
                return self._json({"reason_code": "host_forbidden"}, 403)
            path = parsed.path
            if path == "/":
                return self._serve_index(parsed)
            if path == "/config-ui.js":
                return self._serve_js_asset()
            if path == "/api/overview":
                overview = owner.overview(StatusRequest())
                payload = overview.to_dict()
                payload["capabilities"] = {"terminal_entry": terminal.entry_available()}
                return self._json(payload)
            if path == "/api/channels":
                return self._json(_channels_payload())
            if path == "/api/status":
                return self._json(self._legacy_status())
            if path.startswith("/api/credential/session/"):
                if not self._authorized(parsed):
                    return self._json({"reason_code": "forbidden"}, 403)
                session_id = path.rsplit("/", 1)[-1]
                return self._json(terminal.poll(session_id))
            if path == "/api/runs":
                if runs is None:
                    return self._json({"reason_code": "runs_unavailable"}, 503)
                try:
                    return self._json(runs.list_runs())
                except Exception:
                    return self._runs_internal_error(path)
            if path.startswith("/api/runs/"):
                if runs is None:
                    return self._json({"reason_code": "runs_unavailable"}, 503)
                try:
                    return self._serve_run(path, parsed)
                except Exception:
                    return self._runs_internal_error(path)
            return self._json({"reason_code": "not_found"}, 404)

        def _runs_internal_error(self, path):
            import sys
            import traceback

            traceback.print_exc(file=sys.stderr)
            sys.stderr.write("[config-ui] internal_error path=%s\n" % path)
            return self._json({"reason_code": "internal_error"}, 500)

        def _serve_run(self, path, parsed):
            remainder = path[len("/api/runs/"):]
            parts = remainder.split("/")
            if len(parts) == 3 and parts[1] == "pages" and parts[2].endswith(".png"):
                run_id = parts[0]
                page_part = parts[2][: -len(".png")]
                try:
                    number = int(page_part)
                except ValueError:
                    return self._json({"reason_code": "preview_not_found"}, 404)
                try:
                    payload, content_type = runs.page_image(run_id, number)
                except (RunLookupError, PreviewLookupError):
                    return self._json({"reason_code": "preview_not_found"}, 404)
                # 页图内容不可变（record 后 artifact 固定）：ETag + 私有缓存
                # 让重渲染走 304/缓存命中，消除 3s 轮询下的重传（运维评审#2）。
                # 内容哈希取 sha256 前 8 字节（跨进程重启稳定；对 retry
                # 重写 artifact 的场景内容变则 ETag 变，语义正确）。
                import hashlib as _hashlib

                etag = '"' + _hashlib.sha256(payload).digest()[:8].hex() + '"' 
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Cache-Control", "private, max-age=86400")
                    self.end_headers()
                    return None
                return self._binary(
                    payload,
                    content_type,
                    extra_headers={
                        "ETag": etag,
                        "Cache-Control": "private, max-age=86400",
                    },
                )
            if len(parts) == 1 and parts[0]:
                query = parse_qs(parsed.query)
                before_raw = query.get("events_before", [None])[0]
                limit_raw = query.get("events_limit", [None])[0]
                try:
                    before = int(before_raw) if before_raw is not None else None
                    limit = int(limit_raw) if limit_raw is not None else None
                except ValueError:
                    return self._json({"reason_code": "request_invalid"}, 400)
                try:
                    detail = runs.run_detail(
                        parts[0], events_before=before, events_limit=limit
                    )
                except RunLookupError:
                    return self._json({"reason_code": "run_not_found"}, 404)
                return self._json(detail)
            return self._json({"reason_code": "not_found"}, 404)

        def _serve_js_asset(self):
            # 页面脚本与 HTML 同源同权限（无敏感数据）；no-store 保证
            # runtime 刷新后浏览器立即取新脚本（与 HTML 策略一致）。
            try:
                text = _read_js_asset()
            except FileNotFoundError:
                return self._json({"reason_code": "config_ui_asset_missing"}, 500)
            return self._binary(
                text.encode("utf-8"), "application/javascript; charset=utf-8"
            )

        def _serve_index(self, parsed):
            query_token = parse_qs(parsed.query).get("token", [None])[0]
            headers = {}
            if query_token == token:
                headers["Set-Cookie"] = (
                    f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/"
                )
            initial_state: dict[str, Any] = {}
            try:
                overview = owner.overview(StatusRequest()).to_dict()
                overview["capabilities"] = {
                    "terminal_entry": terminal.entry_available()
                }
                initial_state["overview"] = overview
                initial_state["channels"] = _channels_payload()
            except Exception:
                pass  # 渠道首屏直出失败时该 Tab 退回客户端加载
            if runs is not None:
                try:  # runs 注入独立容错（方案 R2#8）：坏 run 不拖垮渠道 Tab
                    initial_state["runs"] = runs.list_runs()
                except Exception:
                    pass
            try:
                text = _read_html_asset()
            except FileNotFoundError:
                return self._json({"reason_code": "config_ui_asset_missing"}, 500)
            if initial_state and ASSET_INITIAL_MARKER in text:
                injection = (
                    "<script>window.__LEO_INITIAL__="
                    + _escape_inline_json(initial_state)
                    + ";</script>"
                )
                text = text.replace(ASSET_INITIAL_MARKER, injection, 1)
            data = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def _legacy_status(self):
            report = owner.overview(StatusRequest()).to_dict()
            providers = report.get("providers", [])
            selection = report.get("selection")
            inner = report.get("report", {})
            return {
                "status_text": "可以开始生成" if inner.get("status") == "ready" else "已配置，首次生成时验证",
                "selected_provider": selection.get("provider") if selection else None,
                "reason_code": inner.get("reason_code"),
                "providers": providers,
            }

        # --------------------------------------------------------------- POST
        def _respond(self, result):
            if isinstance(result, tuple):
                payload, status = result
            else:
                payload, status = result, 200
            return self._json(payload, status)

        def do_POST(self):
            parsed = urlparse(self.path)
            if not self._host_allowed():
                return self._json({"reason_code": "host_forbidden"}, 403)
            if not self._authorized(parsed):
                return self._json({"reason_code": "forbidden"}, 403)
            path = parsed.path
            if path == "/api/prefer":
                body = self._read_json()
                if body is None:
                    return None
                return self._respond(self._prefer(body))
            if path == "/api/auto":
                return self._respond(self._auto())
            if path == "/api/provider/configure":
                body = self._read_json()
                if body is None:
                    return None
                return self._respond(self._configure(body))
            if path == "/api/provider/enabled":
                body = self._read_json()
                if body is None:
                    return None
                return self._respond(self._enabled(body))
            if path == "/api/provider/priority":
                body = self._read_json()
                if body is None:
                    return None
                return self._respond(self._priority(body))
            if path == "/api/provider/remove":
                body = self._read_json()
                if body is None:
                    return None
                return self._respond(self._remove(body))
            if path == "/api/provider/reorder":
                body = self._read_json()
                if body is None:
                    return None
                return self._respond(self._reorder(body))
            if path.startswith("/api/credential/session/") and path.endswith("/cancel"):
                session_id = path[len("/api/credential/session/") : -len("/cancel")]
                return self._json(terminal.cancel(session_id))
            return self._json({"reason_code": "not_found"}, 404)

        # ------------------------------------------------------------ actions
        def _provider_arg(self, body: dict[str, Any]):
            try:
                return ProviderName(str(body.get("provider"))), None
            except ValueError:
                return None, ({"reason_code": "unknown_provider"}, 400)

        def _prefer(self, body):
            provider, error = self._provider_arg(body)
            if error:
                return error
            try:
                report = owner.set_preferred_provider(
                    StatusRequest(),
                    provider=provider,
                    operation_id=f"config-ui-prefer-{provider.value}",
                )
            except Exception as exc:
                return {"reason_code": _reason_of(exc)}, 400
            return {
                "reason_code": "provider_preferred",
                "status": report.status.value,
                "selection": {"mode": "fixed", "provider": provider.value},
            }

        def _auto(self):
            try:
                report = owner.clear_preferred_provider(
                    StatusRequest(), operation_id="config-ui-auto"
                )
            except Exception as exc:
                return {"reason_code": _reason_of(exc)}, 400
            return {
                "reason_code": "provider_auto_selection_enabled",
                "status": report.status.value,
                "selection": {"mode": "automatic"},
            }

        def _enabled(self, body):
            provider, error = self._provider_arg(body)
            if error:
                return error
            value = body.get("value")
            if not isinstance(value, bool):
                return {"reason_code": "provider_profile_invalid"}, 400
            try:
                owner.set_provider_enabled(provider, enabled=value)
            except Exception as exc:
                return {"reason_code": _reason_of(exc)}, 400
            return {"reason_code": "provider_preference_updated", "provider": provider.value, "enabled": value}

        def _priority(self, body):
            provider, error = self._provider_arg(body)
            if error:
                return error
            priority = body.get("priority")
            if (
                isinstance(priority, bool)
                or not isinstance(priority, int)
                or not 1 <= priority <= 1000
            ):
                return {"reason_code": "provider_priority_invalid"}, 400
            try:
                owner.set_provider_priority(provider, priority=priority)
            except Exception as exc:
                return {"reason_code": _reason_of(exc)}, 400
            return {
                "reason_code": "provider_priority_updated",
                "provider": provider.value,
                "priority": priority,
            }

        def _remove(self, body):
            provider, error = self._provider_arg(body)
            if error:
                return error
            try:
                result = owner.remove_provider(
                    provider, operation_id=f"config-ui-remove-{provider.value}"
                )
            except Exception as exc:
                return {"reason_code": _reason_of(exc)}, 400
            return {"reason_code": result, "provider": provider.value}

        def _reorder(self, body):
            providers = body.get("providers")
            if not isinstance(providers, list) or not providers:
                return {"reason_code": "provider_priority_order_invalid"}, 400
            try:
                owner.reorder_provider_priorities([str(item) for item in providers])
            except Exception as exc:
                return {"reason_code": _reason_of(exc)}, 400
            return {
                "reason_code": "provider_priority_reordered",
                "providers": [str(item) for item in providers],
            }

        def _build_selection(self, provider: ProviderName, mode, credential):
            if mode == "web":
                secret = credential.get("secret")
                if not isinstance(secret, str) or not secret.strip():
                    return None, "credential_secret_missing"
                return (
                    CredentialInputSelection(
                        channel=CredentialInputChannel.EXPLICIT_STDIN,
                        reason_code="config-ui-web-entry",
                        secret=SecretBuffer(secret),
                    ),
                    None,
                )
            if mode == "env":
                environment = PROVIDERS.get(provider.value)
                if not environment:
                    return None, "credential_input_channel_unavailable"
                return (
                    CredentialInputSelection(
                        channel=CredentialInputChannel.ENVIRONMENT,
                        reason_code="config-ui-env-reference",
                        credential_ref=f"env:{environment}",
                    ),
                    None,
                )
            if mode == "keep":
                try:
                    snapshot = owner.config_store.read()
                except Exception:
                    return None, "credential_input_channel_unavailable"
                profile = snapshot.values.get("provider_profiles", {}).get(
                    provider.value
                )
                if not isinstance(profile, dict):
                    return None, "credential_input_channel_unavailable"
                source = profile.get("credential_source")
                reference = profile.get("credential_ref")
                if source == "environment-reference" and reference:
                    return (
                        CredentialInputSelection(
                            channel=CredentialInputChannel.ENVIRONMENT,
                            reason_code="config-ui-keep-env",
                            credential_ref=reference,
                        ),
                        None,
                    )
                if source == "os-store-reference" and reference:
                    return (
                        CredentialInputSelection(
                            channel=CredentialInputChannel.EXISTING_STORE,
                            reason_code="config-ui-keep-store",
                            credential_ref=reference,
                        ),
                        None,
                    )
                return None, "credential_input_channel_unavailable"
            return None, "credential_input_channel_unavailable"

        def _configure(self, body):
            provider, error = self._provider_arg(body)
            if error:
                return error
            credential = body.get("credential")
            if not isinstance(credential, dict):
                return {"reason_code": "credential_input_channel_unavailable"}, 400
            mode = credential.get("mode")
            model = body.get("model")
            if model is not None and not isinstance(model, str):
                return {"reason_code": "provider_profile_invalid:model"}, 400
            endpoint_origin = body.get("endpoint_origin")
            if endpoint_origin is not None and not isinstance(endpoint_origin, str):
                return {"reason_code": "provider_profile_invalid:endpoint_origin"}, 400

            if mode == "terminal":
                session, start_error = terminal.start_or_join(
                    provider=provider,
                    model=model,
                    endpoint_origin=endpoint_origin,
                    request=StatusRequest(),
                )
                if start_error == "terminal_entry_unavailable":
                    return {"reason_code": start_error}, 409
                if session is None:
                    return {"reason_code": "terminal_entry_failed"}, 500
                return (
                    {
                        "reason_code": "terminal_session_started",
                        "session": {"id": session["id"], "state": session["state"]},
                    },
                    202,
                )

            selection, selection_error = self._build_selection(
                provider, mode, credential
            )
            if selection is None:
                return {"reason_code": selection_error}, 400
            try:
                report = owner.configure(
                    ConfigureRequest(
                        provider=provider,
                        credential=selection,
                        model=model,
                        endpoint_origin=endpoint_origin,
                        status_request=StatusRequest(),
                        operation_id=(
                            f"config-ui-{provider.value}-{uuid.uuid4().hex[:8]}"
                        ),
                        overwrite_credential=_replacing_os_store(owner, provider),
                    )
                )
            except Exception as exc:
                # service.configure 的 finally 覆盖事务路径；此处兜底关闭早退
                # raise（端点/模型校验在进入事务块之前）残留的 SecretBuffer。
                try:
                    selection.close()
                except Exception:
                    pass
                return {"reason_code": _reason_of(exc)}, 400
            return {
                "status": report.status.value,
                "reason_code": report.reason_code,
                "provider": provider.value,
                "report": report.to_dict(),
            }

    return Handler


def create_config_ui_server(
    service: ConfigService,
    *,
    port: int = 0,
    tty_probe: Callable[[], bool] | None = None,
    getpass_fn: Callable[[str], str] | None = None,
    run_scanner: RunScanner | None = None,
) -> tuple[ThreadingHTTPServer, str, str]:
    token = secrets.token_urlsafe(24)
    terminal = TerminalEntryCoordinator(
        service, tty_probe=tty_probe, getpass_fn=getpass_fn
    )
    if run_scanner is None:
        run_scanner = RunScanner(default_home())
    handler = build_config_ui_handler(
        service, token=token, terminal=terminal, runs=run_scanner
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_port}/?token={token}"
    return server, token, url


def serve_config_ui(service: ConfigService, *, port: int = 0, open_browser: bool = True) -> dict[str, Any]:
    server, token, url = create_config_ui_server(service, port=port)
    print(f"本地配置界面：{url}")
    if open_browser:
        threading.Timer(0.1, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {"status": "completed", "reason_code": "config_ui_closed", "url": url}
