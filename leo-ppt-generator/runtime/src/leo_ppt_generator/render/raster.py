"""D3 SVG → PNG 栅格化（resvg 双路径，CI-6 Node 边界）。

- **首选**：Python 绑定 ``resvg-py``（零 Node）。
- **备选**：Node 绑定 ``@resvg/resvg-js``，经独立子进程
  ``scripts/render/rasterize_svg.mjs`` 隔离：stdin 一行 JSON
  ``{svg_path|svg_string, out_path, width, background, font_dirs,
  default_font_family}`` → stdout 一行 JSON ``{ok, out, width, height}``
  或 ``{ok:false, error}``。永不进 PPTX 组装路径。
- 两者皆不可用 → ``rasterizer_unavailable``。

确定性参数合同（设计 §3.3.2）：``skip_system_fonts/loadSystemFonts=false``
+ 显式 ``font_files/font_dirs`` + ``fitTo width`` + 显式背景色。同输入两次
栅格化 ``out_sha256`` 必须相等（进 tests/render 与 evals 断言；位级承诺
仅属于 SVG→resvg 链路，HTML/playwright 链路只承诺像素 diff ≤ 容差）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..storage import sha256_file
from .assets import font_dirs
from .errors import RenderError

RASTERIZE_SCRIPT = Path(__file__).resolve().parents[3] / "scripts/render/rasterize_svg.mjs"
DEFAULT_FONT_FAMILY = "Noto Sans SC"
NODE_TIMEOUT_SECONDS = 60


class RasterizerUnavailable(RenderError):
    def __init__(self, detail: str) -> None:
        super().__init__("rasterizer_unavailable", detail)


def _python_bindings_available() -> bool:
    try:
        import resvg_py  # noqa: F401
        return True
    except Exception:
        return False


def rasterizer_status() -> dict[str, Any]:
    """双路径探测（doctor/readiness 披露用）。"""

    node = shutil.which("node")
    return {
        "python_bindings": _python_bindings_available(),
        "node_subprocess": bool(node) and RASTERIZE_SCRIPT.is_file(),
        "node_path": node,
        "script": str(RASTERIZE_SCRIPT) if RASTERIZE_SCRIPT.is_file() else None,
    }


def _existing_font_files(dirs: list[Path]) -> list[str]:
    files: list[str] = []
    for root in dirs:
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if path.is_file() and path.suffix.lower() in (".otf", ".ttf", ".woff", ".woff2"):
                files.append(str(path))
    return files


def _rasterize_python(
    svg_string: str | None,
    svg_path: Path | None,
    out_path: Path,
    *,
    width: int,
    background: str,
    fonts: list[str],
    default_font_family: str,
) -> tuple[int, int]:
    import resvg_py

    png_bytes = resvg_py.svg_to_bytes(
        svg_string=svg_string,
        svg_path=str(svg_path) if svg_path else None,
        width=width,
        background=background,
        skip_system_fonts=True,
        font_files=fonts or None,
        font_family=default_font_family,
    )
    out_path.write_bytes(png_bytes)
    import struct

    header = png_bytes[:24]
    return struct.unpack(">II", header[16:24])


def _rasterize_node(payload: dict[str, Any], timeout: int = NODE_TIMEOUT_SECONDS) -> dict[str, Any]:
    node = shutil.which("node")
    if not node or not RASTERIZE_SCRIPT.is_file():
        raise RasterizerUnavailable(
            "node or scripts/render/rasterize_svg.mjs unavailable; "
            "install resvg-py (preferred) or node + @resvg/resvg-js"
        )
    process = subprocess.Popen(
        [node, str(RASTERIZE_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(
            json.dumps(payload, ensure_ascii=False) + "\n", timeout=timeout
        )
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), 9)
        process.wait()
        raise RenderError("render_timeout", "rasterize_svg.mjs timed out") from None
    if process.returncode != 0:
        raise RenderError(
            "rasterizer_unavailable",
            f"rasterize_svg.mjs exited {process.returncode}: {stderr.strip()[:300]}",
        )
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise RenderError(
            "rasterizer_unavailable", f"rasterize_svg.mjs protocol invalid: {exc}"
        ) from exc
    if not result.get("ok"):
        raise RasterizerUnavailable(str(result.get("error", "unknown"))[:300])
    return result


def rasterize_svg(
    *,
    svg_string: str | None = None,
    svg_path: str | Path | None = None,
    out_path: str | Path,
    width: int = 2560,
    background: str = "#ffffff",
    default_font_family: str = DEFAULT_FONT_FAMILY,
    extra_font_dirs: list[str | Path] | None = None,
) -> dict[str, Any]:
    """SVG → PNG（2560 宽 fitTo）。返回 out/sha256/尺寸与所用路径。"""

    if (svg_string is None) == (svg_path is None):
        raise RenderError("render_data_invalid", "exactly one of svg_string/svg_path")
    source_path = Path(svg_path) if svg_path else None
    if source_path is not None and not source_path.is_file():
        raise RenderError("render_data_invalid", f"svg missing: {source_path}")
    if width < 1:
        raise RenderError("render_data_invalid", f"invalid width {width}")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    dirs = font_dirs(extra_font_dirs)
    fonts = _existing_font_files(dirs)
    warnings = [f"font dir empty, relying on default family: {d}" for d in dirs if d.is_dir() and not any(d.iterdir())]

    used_path: str
    dimensions: tuple[int, int]
    if _python_bindings_available():
        dimensions = _rasterize_python(
            svg_string,
            source_path,
            out,
            width=width,
            background=background,
            fonts=fonts,
            default_font_family=default_font_family,
        )
        used_path = "resvg-py"
    else:
        payload = {
            "out_path": str(out),
            "width": width,
            "background": background,
            "default_font_family": default_font_family,
            "font_dirs": [str(d) for d in dirs if d.is_dir()],
        }
        if source_path is not None:
            payload["svg_path"] = str(source_path)
        else:
            payload["svg_string"] = svg_string
        result = _rasterize_node(payload)
        dimensions = (int(result["width"]), int(result["height"]))
        used_path = "resvg-node"

    return {
        "out": str(out.resolve()),
        "out_sha256": sha256_file(out),
        "width": dimensions[0],
        "height": dimensions[1],
        "rasterizer": used_path,
        "font_files": len(fonts),
        "warnings": warnings,
    }
