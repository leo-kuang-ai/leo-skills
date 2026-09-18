"""render lane 静态资产的定位（模板 / 字体 / vendored 运行时）。

布局规则与 ``styles._builtin_styles_dir`` 一致：安装器导出
``LEO_PPT_BUNDLE``（技能包根）时优先；仓内开发回退到 ``parents[3]``
相对布局。资产目录：

- ``template-library/canonical/templates/``   HTML 页渲染模板（每模板 ``<slug>/page.html``）
- ``assets/render-fonts/``       离线字体（OFL，NOTICE 登记）
- ``assets/render-vendor/``      浏览器端 vendored 运行时（mermaid 等，
  版本 pin 进包根 ``vendor-lock.json``）
"""

from __future__ import annotations

import os
from pathlib import Path

from ..asset_resolver import _marker_bundle_root


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


def fonts_dir() -> Path:
    return render_assets_dir("render-fonts")


def vendor_dir(*parts: str) -> Path:
    return render_assets_dir("render-vendor").joinpath(*parts)


def templates_dir() -> Path:
    """Canonical template root used as the HTTP server document root."""
    from ..asset_resolver import builtin_library_root

    return builtin_library_root() / "canonical" / "templates"


def template_path(template_id: str, *, resolver=None) -> Path:
    """模板 id → page.html 路径；拒绝路径分隔符注入。

    唯一真源：template-library/canonical/templates/<slug>/page.html。
    """
    if not template_id or any(ch in template_id for ch in "/\\") or template_id.startswith("."):
        raise ValueError("invalid_template_id")
    # Layout profiles carry the canonical asset id (builtin:template:<slug>),
    # while the CLI commonly receives the short slug. Accept both forms but
    # never treat an arbitrary colon-containing string as a path.
    if ":" in template_id:
        parts = template_id.split(":")
        if len(parts) != 3 or parts[0] not in ("builtin", "user") or parts[1] != "template":
            raise ValueError("invalid_template_id")
        slug = parts[2]
    else:
        slug = template_id
    from ..asset_resolver import ASSET_ID_RE, AssetResolver, ResolverError

    asset_id = template_id if ":" in template_id else f"builtin:template:{slug}"
    if not ASSET_ID_RE.fullmatch(asset_id):
        raise ValueError("invalid_template_id")
    try:
        resolved = (resolver or AssetResolver()).resolve(asset_id)
    except ResolverError as exc:
        raise FileNotFoundError(f"render_template_not_found: {template_id}: {exc.reason_code}") from exc
    if resolved["data"].get("lane") != "render:html":
        raise ValueError("render_template_lane_unsupported")
    page = Path(resolved["path"]).with_name("page.html")
    if not page.resolve().is_relative_to(Path(resolved["trusted_root"]).resolve()):
        raise ValueError("render_template_scope_violation")
    if not page.is_file():
        raise FileNotFoundError(f"render_template_not_found: {template_id}")
    return page


def _canonical_template_dirs() -> list[Path]:
    dirs: list[Path] = []
    from ..asset_resolver import _candidate_bundle_roots

    for bundle_root in _candidate_bundle_roots():
        dirs.append(bundle_root / "template-library" / "canonical" / "templates")
    return dirs


def template_http_entry(name: str, *, resolver=None) -> Path | None:
    """HTTP 供给的模板入口文件（``<slug>.html`` → 实际 page.html）。

    与 ``template_path`` 使用同一 canonical 解析策略。
    """

    if not name.endswith(".html"):
        return None
    try:
        path = template_path(name[:-5], resolver=resolver)
    except (ValueError, FileNotFoundError):
        return None
    return path if path.is_file() else None


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
