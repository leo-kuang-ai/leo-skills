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
from .fonts import RenderAssetServer, theme_font_assets
from .readiness import _apply_browsers_path
from .svg_policy import sanitize_svg
from ..template_inputs import load_template_json, validate_template_data

LOGICAL_WIDTH = 1280
LOGICAL_HEIGHT = 720
DEFAULT_SIZE = (2560, 1440)
READY_SELECTOR = "html[data-leo-ready='1']"
READY_FALLBACK_WAIT_MS = 800
DEFAULT_TIMEOUT_MS = 60_000
RENDERER_NAME = "playwright-chromium"
OVERFLOW_TOLERANCE_PX = 1.0

# 溢出哨兵（模板合同第七条）：全部 data-leo-block 必须完整落在逻辑画幅内，
# 且块自身内容不超出其盒（D-CHART-01 类缺陷从视觉 QA 前移到渲染期拦截）。
# LEO_PPT_RENDER_OVERFLOW=warn 时降级为 sidecar 警告（观察模式），不拒产。
_OVERFLOW_CHECK_JS = """
() => {
  const tol = 1.0;
  const vw = window.innerWidth, vh = window.innerHeight;
  const violations = [];
  document.querySelectorAll('[data-leo-block], [data-leo-block-item], [data-leo-region]').forEach((el) => {
    if (!el.getClientRects().length) return;
    const v = { block: el.getAttribute('data-leo-block') || el.getAttribute('data-leo-block-item') || el.getAttribute('data-leo-region') };
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    // 自动行盒可露出字体上升部；固定区域与裁剪盒才有内部容量边界。
    const constrained = el.hasAttribute('data-leo-region') || el.hasAttribute('data-leo-block-item');
    if (r.bottom > vh + tol) v.bottom_px = +(r.bottom - vh).toFixed(1);
    if (r.right > vw + tol) v.right_px = +(r.right - vw).toFixed(1);
    if (r.top < -tol) v.top_px = +(-r.top).toFixed(1);
    if (r.left < -tol) v.left_px = +(-r.left).toFixed(1);
    if (el.clientWidth > 0 && (constrained || ['hidden', 'clip'].includes(style.overflowX))
        && el.scrollWidth > el.clientWidth + tol)
      v.inner_width_px = +(el.scrollWidth - el.clientWidth).toFixed(1);
    if (el.clientHeight > 0 && ((constrained && (el.hasAttribute('data-leo-region') || el.childElementCount > 0)) || ['hidden', 'clip'].includes(style.overflowY))
        && el.scrollHeight > el.clientHeight + tol)
      v.inner_height_px = +(el.scrollHeight - el.clientHeight).toFixed(1);
    if (Object.keys(v).length > 1) violations.push(v);
  });
  return violations;
}
"""

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


def _prepare_slide_data(data_text: str) -> Any:
    """Parse slide data and sanitize an optional chart SVG before browser injection."""

    payload = load_template_json(data_text)
    if isinstance(payload, dict):
        chart_svg = payload.get("chart_svg")
        if isinstance(chart_svg, str) and "<svg" in chart_svg:
            try:
                payload = dict(payload)
                payload["chart_svg"] = sanitize_svg(chart_svg)
            except Exception as exc:
                raise RenderError(
                    "render_data_invalid", f"chart SVG policy rejected output: {exc}"
                ) from exc
    return payload


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
    except (ValueError, FileNotFoundError) as exc:
        raise RenderError("render_template_not_found", str(exc)) from exc
    if not template_file.is_file():
        raise RenderError(
            "render_template_not_found",
            f"template '{template_id}' not found under template-library/canonical/templates/",
        )

    data_file = Path(data_path)
    try:
        data_text = data_file.read_text(encoding="utf-8")
        data_payload = _prepare_slide_data(data_text)
        manifest = json.loads(template_file.with_name("template.json").read_text(encoding="utf-8"))
        errors = validate_template_data(manifest, data_payload)
        if errors:
            raise RenderError("render_data_invalid", "; ".join(errors)[:1000])
    except OSError as exc:
        raise RenderError("render_data_invalid", f"slide data unreadable: {exc}") from exc
    except ValueError as exc:
        raise RenderError("render_data_invalid", f"slide data is not JSON: {exc}") from exc

    if not (theme_variables or {}).get("geometry") and manifest.get("layout_profiles"):
        from ..asset_resolver import AssetResolver
        from .layout import LayoutProfileError, compile_geometry

        try:
            profile = AssetResolver().resolve(manifest["layout_profiles"][0])["data"]
            theme_variables = dict(theme_variables or {})
            theme_variables["geometry"] = compile_geometry(
                profile, theme_variables,
                column_count=len(data_payload["columns"]) if "columns" in data_payload else None)
        except LayoutProfileError as exc:
            raise RenderError("layout_profile_invalid", str(exc)) from exc

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

    font_dirs, font_css = theme_font_assets(theme_variables or {})
    with RenderAssetServer(extra_font_dirs=font_dirs) as server:
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
                data_literal = json.dumps(data_payload, ensure_ascii=False).replace("</", "<\\/")
                theme_literal = json.dumps(theme_variables or {}, ensure_ascii=False).replace("</", "<\\/")
                context.add_init_script(
                    f"window.__LEO_SLIDE_DATA__ = {data_literal};"
                    f"window.__LEO_THEME_VARIABLES__ = {theme_literal};"
                )
                page = context.new_page()
                script_errors = []
                page.on("pageerror", lambda error: script_errors.append(str(error)))
                page.set_default_timeout(timeout_ms)
                url = server.url(f"{template_id}.html?leo_render=1")
                try:
                    page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                except Exception as exc:
                    raise RenderError("render_timeout", f"goto/networkidle: {exc}") from exc

                page.evaluate("() => window.__LEO_SLIDE_DATA__")
                if script_errors:
                    raise RenderError("render_script_error", "; ".join(script_errors)[:1000])
                requested_fonts = []
                if font_css:
                    page.add_style_tag(content=font_css)
                    requested_fonts = sorted({
                        (str(defn.get("family")), int(defn.get("weight", 400)))
                        for defn in (theme_variables or {}).get("fonts", {}).values()
                        if isinstance(defn, dict) and defn.get("family")
                    })
                    if requested_fonts:
                        font_probe = page.evaluate(
                            """async (requests) => {
                              const result = [];
                              for (const [family, weight] of requests) {
                                try {
                                  const loaded = await document.fonts.load(`${weight} 16px ${JSON.stringify(family)}`);
                                  result.push({family, weight, loaded: loaded.length > 0,
                                               check: document.fonts.check(`${weight} 16px ${JSON.stringify(family)}`)});
                                } catch (error) {
                                  result.push({family, weight, loaded: false, check: false, error: String(error)});
                                }
                              }
                              return result;
                            }""",
                            requested_fonts,
                        )
                        if any(not item.get("loaded") or not item.get("check") for item in font_probe):
                            raise RenderError(
                                "render_font_missing",
                                "主题字体未成功加载: " + json.dumps(font_probe, ensure_ascii=False),
                            )

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

                # 溢出哨兵：截图前确定性断言（warn 模式降级为 sidecar 警告）。
                if script_errors:
                    raise RenderError("render_script_error", "; ".join(script_errors)[:1000])
                overflow_mode = os.environ.get("LEO_PPT_RENDER_OVERFLOW", "enforce").strip().lower()
                try:
                    overflow_violations = page.evaluate(_OVERFLOW_CHECK_JS) or []
                except Exception as exc:
                    raise RenderError("render_timeout", f"overflow sentinel: {exc}") from exc
                if overflow_violations and overflow_mode not in ("warn", "off"):
                    raise RenderError(
                        "render_overflow",
                        "data-leo-block 越界（模板合同第七条）："
                        + json.dumps(overflow_violations, ensure_ascii=False)[:400],
                    )
                if overflow_violations:
                    warnings.append(
                        "overflow_observed:" + json.dumps(overflow_violations, ensure_ascii=False)[:200]
                    )
                overflow_check = "warn" if overflow_violations else "pass"

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
        "overflow_check": overflow_check,
        "render_ms": render_ms,
        "rendered_at": _utc_now(),
        "warnings": warnings,
        "fonts_checked": requested_fonts,
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
