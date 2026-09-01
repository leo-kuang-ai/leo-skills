"""render lane 静态资产的定位（模板 / 字体 / vendored 运行时）。

布局规则与 ``styles._builtin_styles_dir`` 一致：安装器导出
``LEO_PPT_BUNDLE``（技能包根）时优先；仓内开发回退到 ``parents[3]``
相对布局。资产目录：

- ``assets/render-templates/``   HTML 页渲染模板（每模板 ``<id>.html``）
- ``assets/render-fonts/``       离线字体（OFL，NOTICE 登记）
- ``assets/render-vendor/``      浏览器端 vendored 运行时（mermaid 等，
  版本 pin 进包根 ``vendor-lock.json``）
"""

from __future__ import annotations

import os
from pathlib import Path

from ..styles import _marker_bundle_root


def _bundle_root() -> Path:
    override = os.environ.get("LEO_PPT_BUNDLE")
    if override and override.strip():
        candidate = Path(override).expanduser()
        if (candidate / "assets").is_dir():
            return candidate
    # 托管 venv 布局：读 runtime 目录的 bundle_root 标记（安装器写入，
    # 见 runtime_manager._install；查找逻辑与 styles 同源）。
    marked = _marker_bundle_root()
    if marked is not None and (marked / "assets").is_dir():
        return marked
    # 与 styles._builtin_styles_dir 的 parents[3] 布局同源，但从顶层包
    # __init__ 锚定（本模块深一层，直接用 parents[3] 会落到 runtime/）。
    import leo_ppt_generator as _package

    return Path(_package.__file__).resolve().parents[3]


def render_assets_dir(name: str) -> Path:
    """返回 ``assets/<name>`` 目录（不保证存在，调用方自行探测）。"""

    return _bundle_root() / "assets" / name


def templates_dir() -> Path:
    return render_assets_dir("render-templates")


def fonts_dir() -> Path:
    return render_assets_dir("render-fonts")


def vendor_dir(*parts: str) -> Path:
    return render_assets_dir("render-vendor").joinpath(*parts)


def template_path(template_id: str) -> Path:
    """模板 id → ``<id>.html``；拒绝路径分隔符注入。"""

    if not template_id or any(ch in template_id for ch in "/\\:") or template_id.startswith("."):
        raise ValueError("invalid_template_id")
    return templates_dir() / f"{template_id}.html"


def font_dirs(extra: list[str | Path] | None = None) -> list[Path]:
    """栅格化/渲染共用的字体目录清单：内置离线目录 + 调用方追加。

    追加来源（风格包字体）通过参数或 ``LEO_PPT_RENDER_FONT_DIRS``
    （路径分隔符分隔）进入；全部显式化——渲染 lane 不静默使用系统字体。
    """

    dirs = [fonts_dir()]
    env_extra = os.environ.get("LEO_PPT_RENDER_FONT_DIRS", "")
    for item in env_extra.split(os.pathsep):
        if item.strip():
            dirs.append(Path(item).expanduser())
    for item in extra or []:
        dirs.append(Path(item).expanduser())
    return dirs
