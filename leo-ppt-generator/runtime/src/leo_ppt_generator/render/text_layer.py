"""U8/R-70 composite 主题化文字层：白名单逐字规划与确定性绘制的共享机制。

KTD7：composite 复用 overlay_text 的白名单与锚点机制——该机制的唯一 owner
在本模块，两个消费方分别是 TF-2 脚本（``scripts/overlay_text.py``）与
composite 合成管线（``render.composite``）。只依赖 stdlib + Pillow；
同输入产出位级一致的图层。

主题化（R-70a）：文字颜色取自 effective theme 的颜色角色——锚点可显式
``color_role``（如 title/body），未声明时自动排版用 ``body`` 角色；显式
``color`` 始终优先（保持 TF-2 既有行为）。主题字体经资产 resolver 离线
解析，不落回系统字体。逐条按 visual-qa 对比度下限对底图采样校验。
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

CANVAS_W, CANVAS_H = 2560, 1440
AUTO_MARGIN_X = 160
AUTO_START_Y = 200
AUTO_LINE_FACTOR = 1.8
DEFAULT_FONT_SIZE = 72
DEFAULT_COLOR = "#111111"

# visual-qa.md 对比度下限：正文 vs 背景 ≥4.5:1；大字 ≥3:1。
LARGE_TEXT_MIN_SIZE = 96
BODY_CONTRAST_FLOOR = 4.5
LARGE_TEXT_CONTRAST_FLOOR = 3.0

SYSTEM_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
)

# 行尾禁则：这些开引号/开括号之后不断行。
_NO_BREAK_AFTER = set("（「『《〔［｛([{\"'“‘￥$")


class TextLayerError(Exception):
    """白名单/主题/绘制合同的确定性失败；``reason_code`` 稳定命名。"""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail


def fail(reason_code: str, message: str) -> None:
    raise TextLayerError(reason_code, message)


def parse_color(value: str | None) -> tuple[int, int, int]:
    text = (value or DEFAULT_COLOR).strip()
    if len(text) == 7 and text[0] == "#":
        try:
            return tuple(int(text[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]
        except ValueError:
            pass
    fail("overlay_spec_invalid", f"颜色必须为 #RRGGBB 形式：{text}")


def load_whitelist_spec(raw: object) -> tuple[list[str], list[dict] | None]:
    """返回 (白名单文字列表, 锚点列表或 None)；逐字合同在这里单点维护。"""

    supplied = raw.get("required_text") if isinstance(raw, dict) else raw
    if not isinstance(supplied, list) or any(not isinstance(item, str) or not item.strip() for item in supplied):
        fail("overlay_spec_invalid", "required_text 必须是非空字符串数组，不转换类型或静默丢弃条目")
    if isinstance(raw, list):
        items = list(raw)
        if not items:
            fail("overlay_spec_invalid", "白名单为空——没有可贴文字（检查 required_text 是否漏了）")
        return items, None
    if isinstance(raw, dict):
        items = list(supplied)
        if not items:
            fail("overlay_spec_invalid", "required_text 为空——没有可贴文字（检查 required_text 是否漏了）")
        anchors = raw.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            fail("overlay_spec_invalid", "锚点形态要求 anchors 数组非空")
        for anchor in anchors:
            if not isinstance(anchor, dict) or not isinstance(anchor.get("text"), str):
                fail("overlay_spec_invalid", "每个锚点必须是含 text 字段的对象")
        return items, anchors
    fail("overlay_spec_invalid", "whitelist.json 必须是字符串数组或 {required_text, anchors} 对象")


def normalize_theme(theme: object) -> dict:
    """effective theme 最小校验：colors 为 #RRGGBB 角色映射；fonts 可选。"""

    if not isinstance(theme, dict):
        fail("overlay_theme_invalid", "theme 必须是对象（effective theme 的 colors/fonts）")
    colors = theme.get("colors")
    if not isinstance(colors, dict) or not colors:
        fail("overlay_theme_invalid", "theme.colors 必须是非空对象")
    for role, value in colors.items():
        if not (isinstance(value, str) and len(value) == 7 and value[0] == "#" and _is_hex_digits(value[1:])):
            fail("overlay_theme_invalid", f"theme.colors.{role}={value!r} 非 #RRGGBB")
    fonts = theme.get("fonts") or {}
    if not isinstance(fonts, dict):
        fail("overlay_theme_invalid", "theme.fonts 必须是对象")
    return {"colors": dict(colors), "fonts": fonts}


def _is_hex_digits(text: str) -> bool:
    try:
        int(text, 16)
    except ValueError:
        return False
    return True


def theme_font_path(theme: dict, resolver=None) -> str | None:
    """主题正文字族 → 离线字体文件；未登记即失败，不落回系统字体。"""

    body = (theme.get("fonts") or {}).get("body") or {}
    family = body.get("family")
    if not family:
        return None
    if resolver is None:
        from ..asset_resolver import AssetResolver

        resolver = AssetResolver()
    try:
        resolved = resolver.require(family, kind="font")
    except Exception as exc:
        fail("overlay_font_missing", f"主题字族未登记离线资产: {family}: {exc}")
    for entry in resolved["data"]["files"]:
        if int(entry.get("weight", 400)) == 400:
            path = Path(resolved["path"]).parent / entry["path"]
            if path.is_file():
                return str(path)
    fail("overlay_font_missing", f"主题字族 {family} 缺 weight 400 字体文件")


def resolve_font(explicit: str | None, size: int, theme_font: str | None = None):
    """字体解析顺序：--font > 主题离线字体 > 环境变量 > 系统 CJK > 内置默认。"""

    from PIL import ImageFont

    candidates = []
    if explicit:
        candidates.append(explicit)
    if theme_font:
        candidates.append(theme_font)
    env = os.environ.get("LEO_PPT_OVERLAY_FONT")
    if env:
        candidates.append(env)
    candidates.extend(SYSTEM_FONT_CANDIDATES)
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def color_for_entry(anchor: dict | None, theme_colors: dict, default: str) -> str:
    """锚点显式 color > 锚点 color_role 映射 > 主题默认角色 > 通用默认。"""

    explicit = (anchor or {}).get("color")
    if explicit is not None:
        return str(explicit)
    role = (anchor or {}).get("color_role")
    if role is not None:
        if role not in theme_colors:
            fail("overlay_theme_invalid", f"color_role {role!r} 不在主题颜色角色中")
        return theme_colors[role]
    if "body" in theme_colors:
        return theme_colors["body"]
    return default


def plan_auto(items: list[str], font_size: int, color: str = DEFAULT_COLOR) -> list[dict]:
    line_height = int(font_size * AUTO_LINE_FACTOR)
    return [
        {
            "text": item,
            "x": AUTO_MARGIN_X,
            "y": AUTO_START_Y + index * line_height,
            "size": font_size,
            "color": color,
        }
        for index, item in enumerate(items)
    ]


def plan_anchored(
    items: list[str], anchors: list[dict], font_size: int, theme_colors: dict | None = None
) -> list[dict]:
    colors = theme_colors or {}
    by_text: dict[str, list[dict]] = {}
    for anchor in anchors:
        by_text.setdefault(anchor["text"], []).append(anchor)
    unknown = sorted(set(by_text) - set(items))
    if unknown:
        fail("overlay_spec_invalid", f"锚点指向白名单外文字，拒绝渲染：{unknown}")
    missing = [item for item in items if item not in by_text]
    if missing:
        fail("overlay_spec_invalid", f"白名单条目缺少锚点，拒绝不完整渲染：{missing}")
    duplicate = sorted(item for item in items if len(by_text[item]) != 1)
    if duplicate:
        fail("overlay_spec_invalid", f"白名单条目必须恰好一个锚点，发现重复锚点：{duplicate}")
    plan = []
    for item in items:
        anchor = by_text[item][0]
        max_width = anchor.get("max_width")
        if max_width is not None and (not isinstance(max_width, int) or isinstance(max_width, bool) or max_width <= 0):
            fail("overlay_spec_invalid", f"锚点 max_width 必须为正整数：{max_width!r}")
        entry = {
            "text": item,
            "x": int(anchor.get("x", AUTO_MARGIN_X)),
            "y": int(anchor.get("y", AUTO_START_Y)),
            "size": int(anchor.get("size", font_size)),
            "color": color_for_entry(anchor, colors, DEFAULT_COLOR),
        }
        if max_width is not None:
            entry["max_width"] = max_width
        plan.append(entry)
    return plan


def _is_cjk(char: str) -> bool:
    return unicodedata.east_asian_width(char) in ("W", "F")


def wrap_lines(text: str, draw, font, max_width: int) -> list[str]:
    """确定性密集文本换行：贪心装填 + 禁则回退 + 硬断；"".join(lines)==text。

    断点选择：fitted 前缀内从右往左找最近合法断点（CJK 字后/空白后/
    连字符后，开引号开括号后禁断）；前缀内无断点按字符硬断（不改写不
    丢字，宁断不截）。
    """

    if draw.textlength(text, font=font) <= max_width:
        return [text]
    lines: list[str] = []
    remaining = text
    while remaining:
        if draw.textlength(remaining, font=font) <= max_width:
            lines.append(remaining)
            break
        lo, hi, fitted = 1, len(remaining) - 1, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if draw.textlength(remaining[:mid], font=font) <= max_width:
                fitted = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if fitted == 0:
            fitted = 1  # 单字符即超宽：硬断（仍逐字）
        cut = fitted
        for index in range(fitted, 0, -1):
            previous = remaining[index - 1]
            if index < len(remaining) and (
                (_is_cjk(previous) and previous not in _NO_BREAK_AFTER)
                or previous.isspace()
                or previous in "-–—/&"
            ):
                cut = index
                break
        lines.append(remaining[:cut])
        remaining = remaining[cut:]
    assert "".join(lines) == text, "换行不得改写或丢弃白名单字符"
    return lines


def contrast_floor_for_size(size: int) -> float:
    return LARGE_TEXT_CONTRAST_FLOOR if size >= LARGE_TEXT_MIN_SIZE else BODY_CONTRAST_FLOOR


def _sample_background(base, box: tuple[int, int, int, int]) -> str:
    """文字行覆盖区域的底图平均色（确定性采样）；box 越界部分裁掉。"""

    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0), max(0, y0)
    x1 = min(base.width, max(x1, x0 + 1))
    y1 = min(base.height, max(y1, y0 + 1))
    region = base.crop((x0, y0, x1, y1)).convert("RGB").resize((1, 1))
    r, g, b = region.getpixel((0, 0))
    return f"#{r:02x}{g:02x}{b:02x}"


def check_contrast_entry(base, entry: dict) -> None:
    """visual-qa 对比度下限：正文 4.5:1、大字 3:1；采样框为该条目的落位区。"""

    from .theme import contrast_ratio

    max_width = entry.get("max_width")
    text_width = entry["size"] * len(entry["text"]) if not max_width else max_width
    box = (entry["x"], entry["y"], entry["x"] + text_width, entry["y"] + entry["size"])
    background = _sample_background(base, box)
    fg = "#%02x%02x%02x" % parse_color(entry["color"])
    floor = contrast_floor_for_size(entry["size"])
    ratio = contrast_ratio(fg, background)
    if ratio < floor:
        fail(
            "text_contrast_insufficient",
            f"文字「{entry['text']}」颜色 {fg} 对底图采样 {background} "
            f"= {ratio:.2f}:1（下限 {floor}），拒绝低对比渲染",
        )


def layout_plan(
    plan: list[dict], draw, fonts: dict, canvas: tuple[int, int], base=None
) -> list[dict]:
    """规划 → 可绘制行：密集文本换行在此展开；越界与对比度校验在此收口。"""

    width, height = canvas
    lines: list[dict] = []
    for entry in plan:
        size = int(entry["size"])
        if size <= 0:
            fail("overlay_spec_invalid", f"字号必须为正整数：{size}")
        font = fonts[size]
        if entry.get("max_width"):
            wrapped = wrap_lines(entry["text"], draw, font, entry["max_width"])
            line_height = int(size * AUTO_LINE_FACTOR)
            for offset, line in enumerate(wrapped):
                lines.append({**entry, "text": line, "y": entry["y"] + offset * line_height})
        else:
            lines.append(dict(entry))
    # 贴出界即合同失败，宁可拒绝也不静默截断。
    for line in lines:
        font = fonts[int(line["size"])]
        text_width = draw.textlength(line["text"], font=font)
        if (
            line["x"] < 0
            or line["y"] < 0
            or line["x"] + text_width > width
            or line["y"] + int(line["size"]) > height
        ):
            fail(
                "overlay_out_of_canvas",
                f"文字「{line['text']}」落位 ({line['x']}, {line['y']}) 超出画布 "
                f"{width}x{height}，拒绝渲染",
            )
    if base is not None:
        for entry in plan:
            check_contrast_entry(base, entry)
    return lines


def new_canvas(size: tuple[int, int]):
    """透明 RGBA 画布（文字层底）。"""

    from PIL import Image

    return Image.new("RGBA", size, (0, 0, 0, 0))


def normalize_canvas(image, canvas: tuple[int, int] = (CANVAS_W, CANVAS_H)):
    """画布比例合同：非 16:9 拒绝；同比例不同尺寸确定性缩放到基准。"""

    from PIL import Image

    width, height = image.size
    if (width, height) == tuple(canvas):
        return image
    if abs(width * canvas[1] - height * canvas[0]) > max(width, height):
        fail(
            "overlay_canvas_mismatch",
            f"底图画幅 {width}x{height} 不是 16:9，违反画布比例合同（基准 {canvas[0]}x{canvas[1]}）",
        )
    return image.resize(tuple(canvas), Image.LANCZOS)


def draw_of(image):
    from PIL import ImageDraw

    return ImageDraw.Draw(image)


def draw_lines(lines: list[dict], fonts: dict, image) -> None:
    draw = draw_of(image)
    for line in lines:
        font = fonts[int(line["size"])]
        draw.text((line["x"], line["y"]), line["text"], font=font, fill=parse_color(line["color"]))
