"""D1-T4 本地 HTTP 字体与静态资产服务。

frontend-slides ``export-pdf.sh`` 的工程教训（MIT，机制引用见
references/render-contract.md）：``@font-face`` 走 ``file://`` 直引在
headless chromium 下不可靠（字体加载静默失败），必须经本地 HTTP 服务供给。
本模块用标准库 ``http.server`` 在 127.0.0.1 随机端口起服务：

- ``/leo-fonts/<file>``   → 内置 ``assets/render-fonts/`` 及追加目录首个命中
- ``/<template>.html``    → ``template_path`` canonical page.html
- ``/leo-vendor/<file>``  → ``assets/render-vendor/``（vendored 运行时）

服务生命周期＝渲染生命周期：``with RenderAssetServer(...) as url:`` 退出即关。
仅绑定回环地址，不进任何持久状态。
"""

from __future__ import annotations

import socket
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from .assets import fonts_dir, template_http_entry, templates_dir, vendor_dir


def _handler(root_map: dict[str, Path], allowed: set[str] | None = None):
    """``allowed`` 为按次冻结依赖白名单（F2）：非空时只放行名单内相对路径。"""

    class _AssetHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root_map["/"]), **kwargs)

        def translate_path(self, path: str) -> str:
            from urllib.parse import unquote, urlsplit

            relative = unquote(urlsplit(path).path).lstrip("/")
            # 模板入口统一走 canonical template_path；不允许旧平铺目录回退。
            if relative.endswith(".html"):
                entry = template_http_entry(relative)
                if entry is not None and self._allowed(relative):
                    return str(entry)
            if relative.startswith("leo-fonts/"):
                name = relative[len("leo-fonts/"):]
                if ".." in name or name.startswith("/"):
                    return str(root_map["/"] / "__missing__")
                for fonts_root in root_map["fonts"]:
                    candidate = (fonts_root / name).resolve()
                    if (candidate.is_file() and candidate.parent == fonts_root.resolve()
                            and self._allowed(f"leo-fonts/{name}")):
                        return str(candidate)
                return str(root_map["/"] / "__missing__")
            if relative.startswith("leo-vendor/"):
                name = relative[len("leo-vendor/"):]
                if ".." in name or name.startswith("/"):
                    return str(root_map["/"] / "__missing__")
                candidate = (vendor_dir() / name).resolve()
                if (candidate.is_file() and candidate.parent == vendor_dir().resolve()
                        and self._allowed(f"leo-vendor/{name}")):
                    return str(candidate)
                return str(root_map["/"] / "__missing__")
            if not self._allowed(relative):
                return str(root_map["/"] / "__missing__")
            return super().translate_path(path)

        def _allowed(self, relative: str) -> bool:
            return allowed is None or relative in allowed

        def log_message(self, *args) -> None:  # 渲染服务静默，避免污染 stderr 合同
            return

    return _AssetHandler


class RenderAssetServer:
    """渲染期临时 HTTP 服务；上下文管理器形态保证结束即关。"""

    def __init__(self, *, extra_font_dirs: list[Path] | None = None,
                 allowed: set[str] | None = None) -> None:
        font_roots = [fonts_dir(), *(extra_font_dirs or [])]
        existing = [root for root in font_roots if root.is_dir()] or [fonts_dir()]
        handler = _handler({"/": templates_dir(), "fonts": existing}, allowed=allowed)
        self._httpd = HTTPServer(("127.0.0.1", 0), handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self.port = self._httpd.server_address[1]

    def url(self, path: str = "") -> str:
        return f"http://127.0.0.1:{self.port}/{path.lstrip('/')}"

    def __enter__(self) -> "RenderAssetServer":
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


def free_port_available() -> bool:
    """探测本机能否绑定回环随机端口（readiness 诊断用）。"""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except OSError:
            return False
        return True
