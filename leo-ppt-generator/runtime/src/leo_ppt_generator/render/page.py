"""D1-T3 ``render page``：HTML 模板 → 2560×1440 PNG 的确定性渲染。

执行流程（设计 §3.1.3）：

1. 模板定位（缺失 → ``render_template_not_found``）。
2. 本地 HTTP 资产/字体服务（见 ``fonts.py``；模板内禁止 ``file://`` 直引）。
3. chromium 启动（playwright-python；``LEO_PPT_RENDER_CHROMIUM`` 可覆盖）。
4. ``new_context(viewport=1280x720, device_scale_factor=<scale>)``。
5. ``goto(<server>/<id>.html?leo_render=1, wait_until="networkidle")``。
6. ``window.__LEO_SLIDE_DATA__ = <slide.json 原文>`` 注入（+ themeVariables）。
7. 主门 ``wait_for_selector("html[data-leo-ready='1']")``；超时走
   ``document.fonts.ready`` + 800ms 回退并记 WARN
   （``ready_signal_missing_fallback_wait``）。
8. ``document.fonts.ready`` 兜底后再截图（clip 0,0,1280,720）。
9. 读 PNG 头断言实际像素 == 请求档；不符 → ``render_size_mismatch``，
   不留产物。
10. 写 ``<out>.render.json`` provenance sidecar（见 ``provenance.py``）。

确定性合同：同输入两次渲染像素 diff ≤ 容差（跨版本抗锯齿微差不承诺位级；
位级承诺只属于 SVG/resvg 链路，见 render-contract.md）。浏览器实例可复用，
但每次渲染独立 context（防状态泄漏）。
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage import sha256_file
from .assets import template_path
from .errors import RenderError
from .fonts import RenderAssetServer
from .readiness import _apply_browsers_path

LOGICAL_WIDTH = 1280
LOGICAL_HEIGHT = 720
DEFAULT_SIZE = (2560, 1440)
READY_SELECTOR = "html[data-leo-ready='1']"
READY_FALLBACK_WAIT_MS = 800
DEFAULT_TIMEOUT_MS = 60_000
RENDERER_NAME = "playwright-chromium"

_SIZE_RE = re.compile(r"^(\d{3,5})x(\d{3,5})$")


class RenderSizeError(RenderError):
    def __init__(self, detail: str) -> None:
        super().__init__("render_size_mismatch", detail)


def parse_size(value: str | None) -> tuple[int, int]:
    """``--size 2560x1440`` → (2560, 1440)；缺省交付档。仅接受 16:9。"""

    if not value:
        return DEFAULT_SIZE
    match = _SIZE_RE.match(value.strip())
    if not match:
        raise RenderError("render_size_mismatch", f"invalid --size: {value}")
    size = (int(match.group(1)), int(match.group(2)))
    if size[0] / size[1] != 16 / 9:
        raise RenderError("render_size_mismatch", f"--size must be 16:9, got {value}")
    return size


def _device_scale_factor(size: tuple[int, int]) -> int:
    scale, remainder = divmod(size[0], LOGICAL_WIDTH)
    if remainder != 0 or size[1] != LOGICAL_HEIGHT * scale or scale not in (1, 2):
        raise RenderSizeError(
            f"unsupported size {size[0]}x{size[1]}: logical canvas is "
            f"{LOGICAL_WIDTH}x{LOGICAL_HEIGHT}, scale must be 1 or 2"
        )
    return scale


def _png_dimensions(path: Path) -> tuple[int, int]:
    import struct

    header = path.read_bytes()[:33]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RenderError("render_output_invalid", "screenshot is not a PNG")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def _playwright_version() -> str:
    import importlib.metadata as metadata

    try:
        return metadata.version("playwright")
    except Exception:  # pragma: no cover
        return "unknown"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def render_page(
    template_id: str,
    data_path: str | Path,
    out_path: str | Path,
    *,
    size: tuple[int, int] = DEFAULT_SIZE,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    theme_variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """渲染单页并返回 provenance/度量字段；产物与 sidecar 落盘。"""

    scale = _device_scale_factor(size)
    try:
        template_file = template_path(template_id)
    except ValueError as exc:
        raise RenderError("render_template_not_found", str(exc)) from exc
    if not template_file.is_file():
        raise RenderError(
            "render_template_not_found",
            f"template '{template_id}' not found under assets/render-templates/",
        )

    data_file = Path(data_path)
    try:
        data_text = data_file.read_text(encoding="utf-8")
        json.loads(data_text)
    except OSError as exc:
        raise RenderError("render_data_invalid", f"slide data unreadable: {exc}") from exc
    except ValueError as exc:
        raise RenderError("render_data_invalid", f"slide data is not JSON: {exc}") from exc

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    _apply_browsers_path()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RenderError(
            "render_backend_missing",
            f"playwright unavailable: {exc}; see references/first-use.md render 节",
        ) from exc

    executable = os.environ.get("LEO_PPT_RENDER_CHROMIUM") or None
    warnings: list[str] = []
    started = time.monotonic()

    with RenderAssetServer() as server:
        with sync_playwright() as playwright:
            launch_kwargs: dict[str, Any] = {"headless": True, "timeout": timeout_ms}
            if executable:
                launch_kwargs["executable_path"] = executable
            try:
                browser = playwright.chromium.launch(**launch_kwargs)
            except Exception as exc:
                raise RenderError(
                    "render_backend_missing", f"chromium launch failed: {exc}"
                ) from exc
            try:
                context = browser.new_context(
                    viewport={"width": LOGICAL_WIDTH, "height": LOGICAL_HEIGHT},
                    device_scale_factor=scale,
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    reduced_motion="reduce",
                )
                # 注入必须在页面脚本执行前完成（add_init_script），否则模板
                # 内联脚本读到空数据——竞态产物是"干净空页"，只有像素闸门
                # 能抓住。数据以 JSON 字面量内嵌，"</" 转义防提前闭合。
                data_literal = json.dumps(json.loads(data_text), ensure_ascii=False).replace("</", "<\\/")
                theme_literal = json.dumps(theme_variables or {}, ensure_ascii=False).replace("</", "<\\/")
                context.add_init_script(
                    f"window.__LEO_SLIDE_DATA__ = {data_literal};"
                    f"window.__LEO_THEME_VARIABLES__ = {theme_literal};"
                )
                page = context.new_page()
                page.set_default_timeout(timeout_ms)
                url = server.url(f"{template_id}.html?leo_render=1")
                try:
                    page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                except Exception as exc:
                    raise RenderError("render_timeout", f"goto/networkidle: {exc}") from exc

                page.evaluate("() => window.__LEO_SLIDE_DATA__")

                ready_signal = "data-leo-ready"
                try:
                    page.wait_for_selector(
                        READY_SELECTOR,
                        state="attached",
                        timeout=max(1000, timeout_ms // 2),
                    )
                except Exception:
                    ready_signal = "fallback_wait"
                    warnings.append("ready_signal_missing_fallback_wait")

                try:
                    page.evaluate("() => document.fonts.ready")
                    if ready_signal == "fallback_wait":
                        page.wait_for_timeout(READY_FALLBACK_WAIT_MS)
                except Exception as exc:
                    raise RenderError("render_timeout", f"fonts.ready: {exc}") from exc

                try:
                    page.screenshot(
                        path=str(out),
                        full_page=False,
                        clip={"x": 0, "y": 0, "width": LOGICAL_WIDTH, "height": LOGICAL_HEIGHT},
                    )
                except Exception as exc:
                    raise RenderError("render_timeout", f"screenshot: {exc}") from exc
                context.close()
            finally:
                browser.close()

    try:
        actual = _png_dimensions(out)
    except RenderError:
        out.unlink(missing_ok=True)
        raise
    if actual != size:
        out.unlink(missing_ok=True)
        raise RenderSizeError(
            f"PNG header {actual[0]}x{actual[1]} != requested {size[0]}x{size[1]}"
        )

    render_ms = int((time.monotonic() - started) * 1000)
    renderer = f"{RENDERER_NAME}@{_playwright_version()}"
    provenance = {
        "schema_version": 1,
        "kind": "render_provenance",
        "backend": "render:html",
        "template_id": template_id,
        "template_sha256": sha256_file(template_file),
        "data_sha256": sha256_file(data_file),
        "dialect": None,
        "renderer": renderer,
        "out": str(out.resolve()),
        "out_sha256": sha256_file(out),
        "width": size[0],
        "height": size[1],
        "device_scale_factor": scale,
        "ready_signal": ready_signal,
        "render_ms": render_ms,
        "rendered_at": _utc_now(),
        "warnings": warnings,
    }
    sidecar = out.with_name(out.name + ".render.json")
    sidecar.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        **provenance,
        "sidecar": str(sidecar),
    }
