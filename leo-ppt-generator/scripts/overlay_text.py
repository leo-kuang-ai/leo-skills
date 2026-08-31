#!/usr/bin/env python3
"""TF-2 确定性贴字（Text Fidelity Fallback，C2）。

用 Pillow 把 `required_text[]` 白名单逐字渲染叠加到留白版式底图上。这是
"最终图片必须来自确认 backend"禁令的**唯一封闭例外**：启用前提是 TF-2 已按
generation method 变更走样张重确认（见 image-deck-workflow.md 文字保真降级链）；
底图必须来自确认 backend，本脚本只做确定性文字层。

用法：
  overlay_text.py <base.png> <whitelist.json> <out.png> [--font <path>]
                  [--font-size N] [--color #RRGGBB] [--json]

whitelist.json 两种形态：
  1. ["标题", "要点一", ...]——纯白名单：自上而下自动排版。
  2. {"required_text": [...], "anchors": [
       {"text": "标题", "x": 128, "y": 200, "size": 96, "color": "#111111"}, ...]}
     锚点形态：每个 required_text 条目必须恰好有锚点（逐字对应，多余锚点指向
     白名单外文字或白名单条目无锚点 → exit 1，拒绝渲染）。

硬合同：
- 输出 PNG 恰为 2560×1440（底图同比例不同尺寸时确定性缩放；非 16:9 底图
  exit 1）。
- 只渲染白名单内文字（逐字，不改写、不截断）；非白名单文字拒绝渲染。
- 确定性：同输入两次运行输出位级一致（可做回归 diff）。
- stdout 末行输出 JSON 摘要（含 base_sha256 / output_sha256 双指纹与
  deterministic-overlay 标记，供 sources manifest 与交付收据联动记录）。

字体解析顺序：--font > 环境变量 LEO_PPT_OVERLAY_FONT > 系统常见 CJK 字体 >
Pillow 内置默认字体。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

CANVAS_W, CANVAS_H = 2560, 1440
AUTO_MARGIN_X = 160
AUTO_START_Y = 200
AUTO_LINE_FACTOR = 1.8
DEFAULT_FONT_SIZE = 72
DEFAULT_COLOR = "#111111"

SYSTEM_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
)


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_color(value: str | None) -> tuple[int, int, int]:
    text = (value or DEFAULT_COLOR).strip()
    if len(text) == 7 and text[0] == "#":
        try:
            return tuple(int(text[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]
        except ValueError:
            pass
    fail(f"颜色必须为 #RRGGBB 形式：{text}")


def load_whitelist(raw: object) -> tuple[list[str], list[dict] | None]:
    """返回 (白名单文字列表, 锚点列表或 None)。"""
    if isinstance(raw, list):
        items = [str(item).strip() for item in raw if str(item).strip()]
        if not items:
            fail("白名单为空——没有可贴文字（检查 required_text 是否漏了）")
        return items, None
    if isinstance(raw, dict):
        items = [str(item).strip() for item in raw.get("required_text") or [] if str(item).strip()]
        if not items:
            fail("required_text 为空——没有可贴文字（检查 required_text 是否漏了）")
        anchors = raw.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            fail("锚点形态要求 anchors 数组非空")
        for anchor in anchors:
            if not isinstance(anchor, dict) or not isinstance(anchor.get("text"), str):
                fail("每个锚点必须是含 text 字段的对象")
        return items, anchors
    fail("whitelist.json 必须是字符串数组或 {required_text, anchors} 对象")


def resolve_font(explicit: str | None, size: int):
    from PIL import ImageFont

    candidates = []
    if explicit:
        candidates.append(explicit)
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


def plan_auto(items: list[str], font_size: int) -> list[dict]:
    line_height = int(font_size * AUTO_LINE_FACTOR)
    return [
        {
            "text": item,
            "x": AUTO_MARGIN_X,
            "y": AUTO_START_Y + index * line_height,
            "size": font_size,
            "color": DEFAULT_COLOR,
        }
        for index, item in enumerate(items)
    ]


def plan_anchored(items: list[str], anchors: list[dict], font_size: int) -> list[dict]:
    by_text: dict[str, list[dict]] = {}
    for anchor in anchors:
        by_text.setdefault(anchor["text"].strip(), []).append(anchor)
    unknown = sorted(set(by_text) - set(items))
    if unknown:
        fail(f"锚点指向白名单外文字，拒绝渲染：{unknown}")
    missing = [item for item in items if item not in by_text]
    if missing:
        fail(f"白名单条目缺少锚点，拒绝不完整渲染：{missing}")
    plan = []
    for item in items:
        anchor = by_text[item][0]
        plan.append(
            {
                "text": item,
                "x": int(anchor.get("x", AUTO_MARGIN_X)),
                "y": int(anchor.get("y", AUTO_START_Y)),
                "size": int(anchor.get("size", font_size)),
                "color": str(anchor.get("color", DEFAULT_COLOR)),
            }
        )
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="留白版式底图（须来自确认 backend，16:9）")
    parser.add_argument("whitelist", help="required_text 白名单 JSON 文件")
    parser.add_argument("out", help="输出 PNG 路径（2560×1440）")
    parser.add_argument("--font", help="字体文件路径（默认 LEO_PPT_OVERLAY_FONT 或系统 CJK 字体）")
    parser.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE, help=f"自动排版字号（默认 {DEFAULT_FONT_SIZE}）")
    parser.add_argument("--color", help=f"自动排版颜色（默认 {DEFAULT_COLOR}）")
    args = parser.parse_args(argv)

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        fail("需要 Pillow（runtime venv 已内置；系统 python 请先安装）")

    base_path = Path(args.base)
    whitelist_path = Path(args.whitelist)
    out_path = Path(args.out)
    for path in (base_path, whitelist_path):
        if not path.is_file():
            fail(f"输入不存在：{path}")
    try:
        raw_whitelist = json.loads(whitelist_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"whitelist JSON 无法读取：{exc}")

    items, anchors = load_whitelist(raw_whitelist)
    plan = plan_anchored(items, anchors, args.font_size) if anchors else plan_auto(items, args.font_size)

    try:
        with Image.open(base_path) as opened:
            base = opened.convert("RGBA")
    except Exception as exc:
        fail(f"底图无法按图片读取：{exc}")
    width, height = base.size
    if (width, height) != (CANVAS_W, CANVAS_H):
        if abs(width * CANVAS_H - height * CANVAS_W) > max(width, height):
            fail(
                f"底图画幅 {width}x{height} 不是 16:9，违反画布比例合同（基准 {CANVAS_W}x{CANVAS_H}）"
            )
        base = base.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
        width, height = base.size

    # 文字不可超出画布（贴出界即合同失败，宁可拒绝也不静默截断）。
    fonts: dict[int, object] = {}
    draw = ImageDraw.Draw(base)
    for item in plan:
        size = int(item["size"])
        if size <= 0:
            fail(f"字号必须为正整数：{size}")
        if size not in fonts:
            fonts[size] = resolve_font(args.font, size)
        font = fonts[size]
        text_width = draw.textlength(item["text"], font=font)
        if item["x"] < 0 or item["y"] < 0 or item["x"] + text_width > width or item["y"] + size > height:
            fail(
                f"文字「{item['text']}」落位 ({item['x']}, {item['y']}) 超出画布 "
                f"{width}x{height}，拒绝渲染"
            )

    for item in plan:
        font = fonts[int(item["size"])]
        draw.text((item["x"], item["y"]), item["text"], font=font, fill=parse_color(item["color"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out_path, format="PNG")
    summary = {
        "deterministic-overlay": True,
        "base": str(base_path),
        "base_sha256": sha256_file(base_path),
        "output": str(out_path),
        "output_sha256": sha256_file(out_path),
        "width": width,
        "height": height,
        "rendered": [item["text"] for item in plan],
        "source_class": "deterministic-overlay",
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
