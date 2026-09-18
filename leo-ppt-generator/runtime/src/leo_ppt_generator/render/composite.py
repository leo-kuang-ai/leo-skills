"""U8/R-70b composite 合成管线：背景层 + 主题化文字层 → 双 provenance 页产物。

背景层必须携带确认 backend 的 provenance（当前消费 ``<png>.render.json``
render provenance sidecar；image 背景 lane 的 sources-manifest 归路留待后续
单元）；文字层由 ``render.text_layer`` 从 required_text 白名单逐字确定性
产生。产物三件套：最终页 PNG、透明文字层 PNG、``<out>.composite.json``
双 provenance sidecar（背景子记录 + 文字层子记录）。

手改拒绝：``verify_composite`` 从 spec 重推导文字层字节并重合成整页比对，
任一层被手改（字节不一致）即拒绝。旧 run 恢复：``resolved_design`` 提供时
先经 ``verify_design_freshness`` 校验依赖摘要，漂移即拒绝续跑（债4 消费）。

阶段边界（R-70c 门禁）：本模块不更新 ``page_type_regime`` 的 lane 准入；
composite 是否晋升默认路由由阶段验证证据决定，缺数据停止晋升。
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

from ..storage import atomic_write_bytes, atomic_write_json, sha256_file
from .errors import RenderError
from . import text_layer as tl

COMPOSITE_KIND = "composite_provenance"
COMPOSITE_SCHEMA_VERSION = 1


def _png_bytes(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _tl(call):
    """text_layer 合同失败 → render lane 稳定 reason code。"""

    try:
        return call()
    except tl.TextLayerError as exc:
        raise RenderError(exc.reason_code, exc.detail) from exc


def _load_spec(spec_path: str | Path) -> dict[str, Any]:
    path = Path(spec_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RenderError("composite_spec_invalid", f"spec JSON 无法读取：{exc}") from exc


def _resolved_theme(spec: dict[str, Any], resolver=None) -> tuple[dict | None, str | None]:
    """spec 内嵌 theme → (normalize 后的 theme, 离线字体路径或 None)。"""

    theme_raw = spec.get("theme")
    if theme_raw is None:
        return None, None
    theme = _tl(lambda: tl.normalize_theme(theme_raw))
    return theme, _tl(lambda: tl.theme_font_path(theme, resolver=resolver))


def _text_layer_plan(spec_raw: dict[str, Any], base, *, resolver=None):
    """spec + 底图采样 → (文字层 RGBA, 计划, theme, theme_font)。确定性。"""

    items, anchors = _tl(lambda: tl.load_whitelist_spec(spec_raw))
    theme, theme_font = _resolved_theme(spec_raw, resolver=resolver)
    theme_colors = theme["colors"] if theme else {}
    font_size = int(spec_raw.get("font_size", tl.DEFAULT_FONT_SIZE))
    if font_size <= 0:
        raise RenderError("composite_spec_invalid", f"font_size 必须为正整数：{font_size}")
    plan = (
        _tl(lambda: tl.plan_anchored(items, anchors, font_size, theme_colors))
        if anchors
        else _tl(lambda: tl.plan_auto(items, font_size, theme_colors.get("body", tl.DEFAULT_COLOR)))
    )
    sizes = {int(item["size"]) for item in plan}
    fonts = {size: tl.resolve_font(None, size, theme_font) for size in sizes}
    lines = _tl(lambda: tl.layout_plan(plan, tl.draw_of(base), fonts, base.size, base=base))
    layer = tl.new_canvas(base.size)
    tl.draw_lines(lines, fonts, layer)
    return layer, plan, theme, theme_font


def _require_background_receipt(
    render_receipt_path: str | Path, background_path: Path
) -> dict[str, Any]:
    from .provenance import load_render_receipt, verify_receipt_matches_artifact

    receipt = load_render_receipt(render_receipt_path)
    verify_receipt_matches_artifact(receipt, background_path)
    return receipt


def _check_design_freshness(resolved_design: dict, resolver=None) -> None:
    from ..templates import DesignCompositionError, verify_design_freshness

    try:
        report = verify_design_freshness(resolved_design, resolver=resolver)
    except DesignCompositionError as exc:
        raise RenderError("composite_design_invalid", str(exc)) from exc
    if report["status"] != "fresh":
        raise RenderError(
            "composite_design_stale",
            "冻结设计依赖已漂移，拒绝旧 run 续跑："
            + json.dumps(report["mismatches"], ensure_ascii=False)[:400],
        )


def verify_binding_theme(binding: dict, spec_path: str | Path, render_receipt_path: str | Path) -> None:
    """run 绑定交叉核对：spec 主题/背景 receipt backend 与冻结绑定一致。

    绑定或主题变化使合成产物失效（R-70 验收 6）——文字层颜色取自主题，
    主题漂移的合成页不得冒充同一绑定下的产物。
    """

    from .provenance import load_render_receipt

    effective = binding.get("effective") or {}
    receipt = load_render_receipt(render_receipt_path)
    binding_backend = binding.get("backend")
    if binding_backend is not None and receipt["backend"] != binding_backend:
        raise RenderError(
            "composite_binding_backend_mismatch",
            f"背景 receipt backend {receipt['backend']!r} != 绑定 backend {binding_backend!r}",
        )
    spec_raw = _load_spec(spec_path)
    spec_theme = spec_raw.get("theme")
    frozen_theme = effective.get("theme")
    if spec_theme is not None and frozen_theme is not None:
        normalized = _tl(lambda: tl.normalize_theme(spec_theme))
        frozen = {
            "colors": frozen_theme.get("colors") or {},
            "fonts": frozen_theme.get("fonts") or {},
        }
        if normalized["colors"] != frozen["colors"] or normalized["fonts"] != frozen["fonts"]:
            raise RenderError(
                "composite_binding_theme_mismatch",
                "spec theme 与冻结绑定的 effective theme 不一致，拒绝合成",
            )


def compose_page(
    background_path: str | Path,
    spec_path: str | Path,
    out_path: str | Path,
    *,
    render_receipt_path: str | Path,
    resolved_design: dict | None = None,
    text_layer_out: str | Path | None = None,
    resolver=None,
) -> dict[str, Any]:
    """背景层 + 主题化文字层 → 最终页 PNG + 透明文字层 PNG + 双 provenance。

    返回 provenance 摘要（与 sidecar 同构）；同输入位级确定。
    """

    from PIL import Image

    background_path = Path(background_path)
    out_path = Path(out_path)
    if not background_path.is_file():
        raise RenderError("composite_background_missing", f"背景层不存在：{background_path}")
    receipt = _require_background_receipt(render_receipt_path, background_path)
    if resolved_design is not None:
        _check_design_freshness(resolved_design, resolver=resolver)
    spec_raw = _load_spec(spec_path)

    try:
        with Image.open(background_path) as opened:
            background = _tl(lambda: tl.normalize_canvas(opened.convert("RGBA")))
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError("composite_background_invalid", f"背景层无法按图片读取：{exc}") from exc

    layer, plan, theme, _ = _text_layer_plan(spec_raw, background, resolver=resolver)
    layer_bytes = _png_bytes(layer)

    final = background.copy()
    final.alpha_composite(layer)
    final = final.convert("RGB")
    final_bytes = _png_bytes(final)
    if final.size != (tl.CANVAS_W, tl.CANVAS_H):
        raise RenderError(
            "composite_canvas_mismatch",
            f"合成产物 {final.size[0]}x{final.size[1]} != 基准画布",
        )

    layer_path = (
        Path(text_layer_out) if text_layer_out else out_path.parent / (out_path.stem + ".text-layer.png")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    layer_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(layer_path, layer_bytes)
    atomic_write_bytes(out_path, final_bytes)

    import PIL

    theme_sha256 = None
    if theme is not None:
        theme_canonical = json.dumps({"colors": theme["colors"]}, ensure_ascii=False, sort_keys=True)
        theme_sha256 = hashlib.sha256(theme_canonical.encode("utf-8")).hexdigest()
    provenance: dict[str, Any] = {
        "schema_version": COMPOSITE_SCHEMA_VERSION,
        "kind": COMPOSITE_KIND,
        "background": {
            "backend": receipt["backend"],
            "template_id": receipt.get("template_id"),
            "renderer": receipt.get("renderer"),
            "out": receipt.get("out"),
            "out_sha256": receipt["out_sha256"],
            "width": receipt["width"],
            "height": receipt["height"],
            "render_receipt": str(render_receipt_path),
        },
        "text_layer": {
            "source_class": "deterministic-overlay",
            "path": str(layer_path.resolve()),
            "sha256": sha256_file(layer_path),
            "spec_sha256": sha256_file(Path(spec_path)),
            "theme_sha256": theme_sha256,
            "rendered": [item["text"] for item in plan],
        },
        "out": str(out_path.resolve()),
        "out_sha256": sha256_file(out_path),
        "width": final.size[0],
        "height": final.size[1],
        "tool": {"pillow": PIL.__version__},
    }
    sidecar = out_path.with_name(out_path.stem + ".composite.json")
    atomic_write_json(sidecar, provenance)
    provenance["sidecar"] = str(sidecar)
    return provenance


def verify_composite(
    background_path: str | Path,
    spec_path: str | Path,
    text_layer_path: str | Path,
    page_path: str | Path,
    *,
    render_receipt_path: str | Path | None = None,
    resolver=None,
) -> dict[str, Any]:
    """手改拒绝：重推导文字层字节 + 重合成整页，任一层被改即拒绝。

    前提：校验方与写入方使用同一 Pillow 版本（sidecar ``tool`` 留痕），
    PNG 编码在同工具链内字节确定。
    """

    from PIL import Image

    background_path = Path(background_path)
    text_layer_path = Path(text_layer_path)
    page_path = Path(page_path)
    for path in (background_path, text_layer_path, page_path):
        if not path.is_file():
            raise RenderError("composite_verify_missing", f"待校验产物缺失：{path}")
    if render_receipt_path is not None:
        _require_background_receipt(render_receipt_path, background_path)
    spec_raw = _load_spec(spec_path)

    try:
        with Image.open(background_path) as opened:
            background = _tl(lambda: tl.normalize_canvas(opened.convert("RGBA")))
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError("composite_background_invalid", f"背景层无法按图片读取：{exc}") from exc

    expected_layer, _plan, _theme, _font = _text_layer_plan(spec_raw, background, resolver=resolver)
    if _png_bytes(expected_layer) != text_layer_path.read_bytes():
        raise RenderError(
            "composite_text_layer_modified",
            f"文字层与 spec 重推导不一致，疑似手改：{text_layer_path}",
        )

    with Image.open(text_layer_path) as opened:
        layer = opened.convert("RGBA")
    if layer.size != background.size:
        raise RenderError(
            "composite_text_layer_modified",
            f"文字层画幅 {layer.size[0]}x{layer.size[1]} != 背景 {background.size[0]}x{background.size[1]}",
        )
    expected_page = background.copy()
    expected_page.alpha_composite(layer)
    expected_bytes = _png_bytes(expected_page.convert("RGB"))
    if expected_bytes != page_path.read_bytes():
        raise RenderError(
            "composite_page_modified",
            f"整页与背景层+文字层重合成不一致，疑似手改或替换：{page_path}",
        )
    return {
        "status": "verified",
        "text_layer_sha256": sha256_file(text_layer_path),
        "page_sha256": sha256_file(page_path),
        "rendered": [item["text"] for item in _plan],
    }
