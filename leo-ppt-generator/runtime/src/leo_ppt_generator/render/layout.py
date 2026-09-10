"""render/layout.py：layout-profile → 几何 CSS 变量与容量判定（F4，方案 §7.2）。

只把已校验 profile 编译为几何 CSS 变量与容量结论，不重选布局、不拥有字号
（字号/行高从 effective_theme 引用）。首批布局类型：固定区域、行/列堆叠、
网格和表格；坐标越界、负尺寸、列数不匹配均拒绝。

容量语义：先按真实列宽扣除 padding 估算行高（字号×行高 + 双向 padding +
边框），累计表头、行高与 gap 与可用高度比较；字符数与条数仅作预筛。硬超
返回具体 slot、需要/可用空间，由内容规划重新分配或拆页。
"""

from __future__ import annotations

from ..asset_resolver import ResolverError

CANVAS = (1280, 720)
SUPPORTED_LAYOUT_TYPES = {"fixed-regions", "stack-row", "stack-column", "grid", "table"}
CAPACITY_TOLERANCE = 1.2


def capacity_level(used: float, limit: float) -> str:
    """推荐与交付预检共用声明容量的三态边界。"""
    if used <= limit:
        return "ok"
    return "over" if used <= limit * CAPACITY_TOLERANCE else "overflow"


class LayoutProfileError(ResolverError):
    reason_code = "layout_profile_invalid"


class CapacityOverflowError(ResolverError):
    reason_code = "layout_capacity_exceeded"


def validate_profile(profile: dict, *, require_regions: bool | None = None) -> None:
    """Validate the profile contract without forcing image-only geometry.

    Pure image profiles may carry descriptive geometry in ``notes`` and omit
    ``regions``; HTML profiles and geometry compilation require concrete
    regions.  The schema uses the same renderer-aware rule.
    """
    if profile.get("entity") != "layout-profile":
        raise LayoutProfileError("layout_profile_invalid: entity 不符")
    canvas = profile.get("canvas") or {}
    if (canvas.get("width"), canvas.get("height"), canvas.get("units")) != (*CANVAS, "logical-px"):
        raise LayoutProfileError(
            f"layout_profile_invalid: 画布必须为 {CANVAS[0]}×{CANVAS[1]} logical-px")
    if profile.get("layout_type") not in SUPPORTED_LAYOUT_TYPES:
        raise LayoutProfileError(
            f"layout_profile_invalid: 布局类型 {profile.get('layout_type')!r} 不在首批五类")
    renderer = profile.get("renderer_support") or {}
    html_bound = isinstance(renderer.get("render:html"), str)
    if require_regions is None:
        require_regions = html_bound
    regions = profile.get("regions")
    if regions is None:
        if require_regions:
            raise LayoutProfileError("layout_profile_invalid: 缺 regions")
        regions = {}
    elif not isinstance(regions, dict) or not regions:
        raise LayoutProfileError("layout_profile_invalid: 缺 regions")
    for name, region in regions.items():
        for key in ("x", "y", "width", "height"):
            value = region.get(key)
            if not isinstance(value, (int, float)) or value < 0:
                raise LayoutProfileError(
                    f"layout_profile_invalid: region {name}.{key} 非法（{value!r}）")
        if region["x"] + region["width"] > CANVAS[0] or region["y"] + region["height"] > CANVAS[1]:
            raise LayoutProfileError(
                f"layout_profile_invalid: region {name} 越出画布")
    columns = profile.get("columns")
    if isinstance(columns, dict):
        weights = columns.get("weights")
        if columns.get("layout_type") == "table" or profile.get("layout_type") == "table":
            if not isinstance(weights, list) or not weights:
                raise LayoutProfileError("layout_profile_invalid: table 布局缺列权重")
            if any(not isinstance(w, (int, float)) or w <= 0 for w in weights):
                raise LayoutProfileError("layout_profile_invalid: 列权重必须为正数")
            total = sum(weights)
            if abs(total - 100) > 0.5:
                raise LayoutProfileError(
                    f"layout_profile_invalid: 列权重合计 {total}（应为 100）")


def _font(effective_theme: dict, role: str, *, size_default: float,
          line_default: float) -> tuple[float, float]:
    defn = (effective_theme.get("fonts") or {}).get(role) or {}
    size = defn.get("size") if isinstance(defn.get("size"), (int, float)) else None
    line = defn.get("line_height") if isinstance(defn.get("line_height"), (int, float)) else None
    return (size or size_default, line or line_default)


def compile_geometry(profile: dict, effective_theme: dict,
                     *, column_count: int | None = None) -> dict:
    """profile + effective_theme → CSS 变量字典（render/page 注入为 --leo-*）。"""
    validate_profile(profile, require_regions=True)
    if profile["layout_type"] == "table":
        return _compile_table(profile, effective_theme, column_count)
    geometry: dict[str, object] = {}
    for name, region in sorted(profile["regions"].items()):
        for key in ("x", "y", "width", "height"):
            geometry[f"{name}-{key}"] = region[key]
    padding = profile.get("padding") or {}
    for key, value in sorted(padding.items()):
        geometry[f"padding-{key}"] = value
    return geometry


def _compile_table(profile: dict, effective_theme: dict,
                   column_count: int | None) -> dict:
    columns = profile["columns"]
    weights = columns["weights"]
    declared = columns.get("count")
    if column_count is None:
        column_count = declared or len(weights)
    if declared is not None and column_count != declared:
        raise LayoutProfileError(
            f"layout_profile_invalid: 输入列数 {column_count} ≠ 声明列数 {declared}；"
            "未声明对应列数的 profile 时报不支持，不能硬套比例")
    if column_count != len(weights):
        raise LayoutProfileError(
            f"layout_profile_invalid: 输入列数 {column_count} 与权重数 {len(weights)} 不一致")
    region = profile["regions"].get("content")
    if region is None:
        raise LayoutProfileError("layout_profile_invalid: table 布局缺 content region")
    header_size, header_line = _font(
        effective_theme, (profile.get("font_size_refs") or {}).get("table_header", "table_header"),
        size_default=26, line_default=1.3)
    body_size, body_line = _font(
        effective_theme, (profile.get("font_size_refs") or {}).get("table_body", "table_body"),
        size_default=25, line_default=1.5)
    padding = profile.get("padding") or {"block": 15, "inline": 18}
    total = sum(weights)
    geometry = {
        "content-x": region["x"],
        "content-y": region["y"],
        "content-w": region["width"],
        "content-h": region["height"],
        "padding-block": padding.get("block", 15),
        "padding-inline": padding.get("inline", 18),
        "font-size-table_header": header_size,
        "font-line-height-table_header": header_line,
        "font-size-table_body": body_size,
        "font-line-height-table_body": body_line,
        "column_weights": [round(w * 100.0 / total, 4) for w in weights],
    }
    return geometry


def _column_widths(profile: dict) -> list[float]:
    """真实列宽（逻辑 px）：region 宽按权重分配。"""
    region = profile["regions"]["content"]
    total = sum(profile["columns"]["weights"])
    return [region["width"] * w / total for w in profile["columns"]["weights"]]


def estimate_line_count(text: str, column_width: float, padding_inline: float,
                        font_size: float) -> int:
    """换行估算：按列内容宽与字号估每行字符数（中文全宽近似 1em/字）。

    预筛口径：仅用于容量预判；最终以 DOM 实测换行为准（render 路线）。
    """
    usable = max(column_width - 2 * padding_inline, 1.0)
    chars_per_line = max(int(usable / font_size), 1)
    if not text:
        return 1
    import math

    return max(math.ceil(len(str(text)) / chars_per_line), 1)


def estimate_table_capacity(
    profile: dict,
    effective_theme: dict,
    *,
    rows: list[list],
    columns: int | None = None,
) -> dict:
    """表格容量判定：行高累计与可用高度比较；硬超返回具体空间数字。"""
    geometry = _compile_table(profile, effective_theme, columns)
    column_count = len(geometry["column_weights"])
    widths = _column_widths(profile)
    header_size = geometry["font-size-table_header"]
    header_line = geometry["font-line-height-table_header"]
    body_size = geometry["font-size-table_body"]
    body_line = geometry["font-line-height-table_body"]
    block = geometry["padding-block"]
    inline = geometry["padding-inline"]
    header_height = header_size * header_line + 2 * block
    row_heights: list[float] = []
    for row in rows:
        lines = 1
        for i, cell in enumerate(row):
            if i >= column_count:
                break
            lines = max(lines, estimate_line_count(
                str(cell), widths[i], inline, body_size))
        row_heights.append(body_size * body_line * lines + 2 * block + 1)
    needed = header_height + sum(row_heights)
    available = geometry["content-h"]
    fits = needed <= available
    return {
        "slot": "rows",
        "fits": fits,
        "needed_height": round(needed, 2),
        "available_height": available,
        "row_count": len(rows),
        "max_rows_estimate": _max_rows(profile, effective_theme),
    }


def _max_rows(profile: dict, effective_theme: dict) -> int:
    """单行文本假设下的最大行数（预筛上界）。"""
    geometry = _compile_table(profile, effective_theme, None)
    header = geometry["font-size-table_header"] * geometry["font-line-height-table_header"] + 2 * geometry["padding-block"]
    row = geometry["font-size-table_body"] * geometry["font-line-height-table_body"] + 2 * geometry["padding-block"] + 1
    return max(int((geometry["content-h"] - header) // row), 0)


def require_capacity(profile: dict, effective_theme: dict, *,
                     rows: list[list], columns: int | None = None) -> dict:
    result = estimate_table_capacity(profile, effective_theme, rows=rows, columns=columns)
    if not result["fits"]:
        raise CapacityOverflowError(
            "layout_capacity_exceeded: slot=rows "
            f"需要 {result['needed_height']}px > 可用 {result['available_height']}px"
            f"（{result['row_count']} 行；单行估算上限 {result['max_rows_estimate']} 行）；"
            "重新分配到已声明布局或拆页，并重新冻结设计")
    return result
