"""D1-T1 render backend readiness 三态探测。

状态语义（设计 §3.1.6；不套用 Provider 三态——无凭据概念）：

- ``render_backend_ready``   playwright 可导入 + chromium 可启动 + 离线字体
  目录存在且非空。允许路由提议进入 render lane。
- ``render_backend_missing`` 依赖未安装或 chromium 二进制缺失。安装指引
  随探测结果返回；期间路由提议被抑制并披露。
- ``render_backend_unknown`` 组件在场但探测不可判（如 chromium 启动探测
  异常退出）。按 missing 处置路由，但披露为探测不可判。

chromium 缓存纪律：优先使用 ``$LEO_PPT_HOME/render-browsers/``（安装时
``PLAYWRIGHT_BROWSERS_PATH`` 固定指向该目录）；该目录无浏览器时尊重
playwright 默认缓存；``LEO_PPT_RENDER_CHROMIUM`` 显式覆盖 executable_path。
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.runtime_config import default_home
from .assets import fonts_dir

RENDER_BROWSERS_SUBDIR = "render-browsers"
LAUNCH_PROBE_TIMEOUT_MS = 15_000

INSTALL_GUIDE = (
    "render lane 依赖未就绪，安装步骤："
    "1) pip install playwright（或 uv pip install playwright）；"
    "2) PLAYWRIGHT_BROWSERS_PATH=\"<$LEO_PPT_HOME>/render-browsers\" "
    "python -m playwright install chromium；完成后重跑 render ready。"
    "期间图像 lane 不受影响。"
)


def _concrete_install_guide() -> str:
    """一键可复制版安装指引：以当前解释器与 home 目录生成具体命令，
    免去用户拼接路径（托管 venv 场景 pip 即 venv 内 pip）。"""
    py = Path(sys.executable)
    pip = py.with_name("pip") if py.name.startswith("python") else py
    browsers = default_home() / RENDER_BROWSERS_SUBDIR
    return (
        "render lane 依赖未就绪，一键安装（复制执行）：\n"
        f'  "{pip}" install playwright\n'
        f'  PLAYWRIGHT_BROWSERS_PATH="{browsers}" "{py}" -m playwright install chromium\n'
        "完成后重跑 render ready。期间图像 lane 不受影响。"
    )


@dataclass
class ReadinessReport:
    status: str  # render_backend_ready | render_backend_missing | render_backend_unknown
    playwright_version: str | None = None
    chromium_version: str | None = None
    chromium_path: str | None = None
    browsers_path: str | None = None
    fonts_dir: str | None = None
    fonts_present: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    install_guide: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "playwright_version": self.playwright_version,
            "chromium_version": self.chromium_version,
            "chromium_path": self.chromium_path,
            "browsers_path": self.browsers_path,
            "fonts_dir": self.fonts_dir,
            "fonts_present": self.fonts_present,
            "details": self.details,
            "warnings": list(self.warnings),
            "install_guide": self.install_guide,
        }


def browsers_cache_dir() -> Path:
    return default_home() / RENDER_BROWSERS_SUBDIR


def _apply_browsers_path() -> str | None:
    """缓存选择：专用目录有浏览器则固定 PLAYWRIGHT_BROWSERS_PATH 到它。

    返回生效的 browsers path（供报告披露）；用户环境已有
    PLAYWRIGHT_BROWSERS_PATH 时不覆盖。
    """

    explicit = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if explicit and explicit.strip():
        return explicit
    cache = browsers_cache_dir()
    if cache.is_dir() and any(cache.iterdir()):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(cache)
        return str(cache)
    return None


def _probe_chromium(
    *, launch: bool
) -> tuple[str | None, str | None, str | None]:
    """单次 playwright 会话内完成 executable 探测与（可选）真实启动。

    返回 (executable_path, chromium_version, error)。两次独立
    ``sync_playwright()`` 会话（先探测后启动）会触发 playwright 1.62 的
    asyncio teardown 竞态噪声，因此合并为一次会话。
    """

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - 环境相关
        return None, None, f"playwright import failed: {exc}"
    try:
        with sync_playwright() as p:
            path = p.chromium.executable_path
            if not path or not Path(path).exists():
                return (str(path) if path else None), None, "chromium executable missing"
            version = None
            if launch:
                browser = p.chromium.launch(
                    headless=True,
                    timeout=LAUNCH_PROBE_TIMEOUT_MS,
                    executable_path=os.environ.get("LEO_PPT_RENDER_CHROMIUM") or None,
                )
                version = browser.version
                browser.close()
            return str(path), version, None
    except Exception as exc:
        return None, None, f"chromium probe failed: {exc}"


def _default_playwright_cache() -> Path | None:
    """playwright 默认浏览器缓存目录（跨平台），不启动 driver。"""

    import sys

    if sys.platform == "darwin":
        return Path.home() / "Library/Caches/ms-playwright"
    if sys.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) / "ms-playwright" if base else None
    return Path.home() / ".cache/ms-playwright"


def _has_chromium_dir(root: Path) -> bool:
    try:
        return any(
            child.name.startswith("chromium")
            for child in root.iterdir()
            if child.is_dir()
        )
    except OSError:
        return False


def probe_fast() -> ReadinessReport:
    """零 driver 探测：doctor 高频调用的快速分面。

    不 ``import playwright`` 驱动（executable_path 探测会在解释器退出时
    留下 asyncio teardown 噪声），只做包元数据 + 文件系统级浏览器目录 +
    字体目录检查；启动级真值以 ``render ready``（probe(launch=True)）为准。
    """

    report = ReadinessReport(status="render_backend_missing")
    report.fonts_dir = str(fonts_dir())
    report.fonts_present = fonts_dir().is_dir() and any(fonts_dir().iterdir())
    if not report.fonts_present:
        report.warnings.append(
            "assets/render-fonts/ 缺失或为空：渲染仍可运行（模板回退系统字体），"
            "但跨机器位级一致性不成立；按 references/render-contract.md 补齐离线字体。"
        )
    try:
        import importlib.metadata as metadata

        report.playwright_version = metadata.version("playwright")
    except Exception:
        report.install_guide = _concrete_install_guide()
        report.details["missing"] = ["playwright"]
        return report

    override = os.environ.get("LEO_PPT_RENDER_CHROMIUM")
    if override and Path(override).exists():
        report.chromium_path = override
        report.details["detection"] = "explicit_override"
        report.status = "render_backend_ready"
        return report

    explicit_root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    candidates = []
    if explicit_root and explicit_root.strip():
        candidates.append(Path(explicit_root))
    candidates.append(browsers_cache_dir())
    default_cache = _default_playwright_cache()
    if default_cache:
        candidates.append(default_cache)
    for root in candidates:
        if root.is_dir() and _has_chromium_dir(root):
            report.chromium_path = str(root)
            report.browsers_path = str(root)
            report.details["detection"] = "filesystem"
            report.status = "render_backend_ready"
            return report
    report.install_guide = _concrete_install_guide()
    report.details["missing"] = ["chromium"]
    report.details["probe_note"] = "filesystem-level detection; run `render ready` for launch-level truth"
    return report


def probe(*, launch: bool = True) -> ReadinessReport:
    """三态探测。``launch=True`` 时真实启动 chromium 一次（doctor/ready 真值）。"""

    report = ReadinessReport(status="render_backend_missing")
    report.fonts_dir = str(fonts_dir())
    report.fonts_present = fonts_dir().is_dir() and any(fonts_dir().iterdir())
    if not report.fonts_present:
        report.warnings.append(
            "assets/render-fonts/ 缺失或为空：渲染仍可运行（模板回退系统字体），"
            "但跨机器位级一致性不成立；按 references/render-contract.md 补齐离线字体。"
        )

    try:
        import importlib.metadata as metadata
        report.playwright_version = metadata.version("playwright")
    except Exception:
        report.install_guide = _concrete_install_guide()
        report.details["missing"] = ["playwright"]
        return report

    report.browsers_path = _apply_browsers_path()
    do_launch = launch and os.environ.get("LEO_PPT_RENDER_SKIP_LAUNCH") != "1"
    executable, version, error = _probe_chromium(launch=do_launch)
    report.chromium_path = executable
    report.chromium_version = version
    if error:
        report.install_guide = _concrete_install_guide()
        report.details["missing"] = ["chromium"]
        report.details["probe_error"] = error
        # executable 缺失是确知的 missing；executable 在场但启动/探测异常
        # 归 unknown（按 missing 抑制路由提议，但披露探测不可判）。
        if executable is not None:
            report.status = "render_backend_unknown"
            report.details.pop("missing", None)
        return report
    report.status = "render_backend_ready"
    return report


def render_ready(*, launch: bool = True) -> dict[str, Any]:
    """``render ready`` 的机器输出（供 CLI 与 doctor 分面复用）。"""

    report = probe(launch=launch)
    return report.to_dict()


def chromium_executable_override() -> str | None:
    value = os.environ.get("LEO_PPT_RENDER_CHROMIUM")
    if value and Path(value).exists():
        return value
    return None


def node_available() -> bool:
    return shutil.which("node") is not None
