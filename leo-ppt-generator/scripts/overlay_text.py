#!/usr/bin/env python3
"""TF-2 确定性贴字（Text Fidelity Fallback，C2）与 R-70a 主题化文字层。

用 Pillow 把 `required_text[]` 白名单逐字渲染叠加到留白版式底图上。这是
"最终图片必须来自确认 backend"禁令的**唯一封闭例外**：启用前提是 TF-2 已按
generation method 变更走样张重确认（见 image-deck-workflow.md 文字保真降级链）；
底图必须来自确认 backend，本脚本只做确定性文字层。

用法：
  overlay_text.py <base.png> <whitelist.json> <out.png> [--font <path>]
                  [--font-size N] [--color #RRGGBB] [--theme <theme.json>]
                  [--text-layer] [--json]

whitelist.json 两种形态：
  1. ["标题", "要点一", ...]——纯白名单：自上而下自动排版。
  2. {"required_text": [...], "anchors": [
       {"text": "标题", "x": 128, "y": 200, "size": 96, "color": "#111111",
        "color_role": "title", "max_width": 1200}, ...]}
     锚点形态：每个 required_text 条目必须恰好有锚点（逐字对应，多余锚点指向
     白名单外文字或白名单条目无锚点 → exit 1，拒绝渲染）。锚点可选字段：
     `max_width`（密集文本确定性换行，逐字不丢）与 `color_role`（主题颜色
     角色，需 --theme）。

--theme <effective-theme.json>（R-70a 主题化文字层）：文字颜色取主题颜色
角色（自动排版默认 body 角色；锚点显式 color 始终优先）；主题字体经资产
resolver 离线解析；逐条按 visual-qa 对比度下限（正文 4.5:1 / 大字 3:1）对
底图采样校验，不足即拒绝。未提供 --theme 时保持 TF-2 既有行为。

--text-layer：输出仅含文字的透明 RGBA 图层（2560×1440），供
render.composite 背景层/文字层合成（R-70b）使用；逐字与确定性合同不变。

硬合同：
- 输出 PNG 恰为 2560×1440（底图同比例不同尺寸时确定性缩放；非 16:9 底图
  exit 1）。
- 只渲染白名单内文字（逐字，不改写、不截断）；非白名单文字拒绝渲染。
- 确定性：同输入两次运行输出位级一致（可做回归 diff）。
- stdout 末行输出 JSON 摘要（含 base_sha256 / output_sha256 双指纹与
  deterministic-overlay 标记，供 sources manifest 与交付收据联动记录）。

字体解析顺序：--font > 主题离线字体 > 环境变量 LEO_PPT_OVERLAY_FONT >
系统常见 CJK 字体 > Pillow 内置默认字体。白名单/锚点/主题/换行机制的单点
owner 是 runtime ``render.text_layer``，本脚本是 TF-2 消费入口。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))

from leo_ppt_generator.render import text_layer as tl

CANVAS_W, CANVAS_H = tl.CANVAS_W, tl.CANVAS_H
DEFAULT_COLOR = tl.DEFAULT_COLOR


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="留白版式底图（须来自确认 backend，16:9）")
    parser.add_argument("whitelist", help="required_text 白名单 JSON 文件")
    parser.add_argument("out", help="输出 PNG 路径（2560×1440）")
    parser.add_argument("--font", help="字体文件路径（默认主题离线字体或系统 CJK 字体）")
    parser.add_argument("--font-size", type=int, default=tl.DEFAULT_FONT_SIZE,
                        help=f"自动排版字号（默认 {tl.DEFAULT_FONT_SIZE}）")
    parser.add_argument("--color", help=f"自动排版颜色（默认 {DEFAULT_COLOR}；--theme 时默认主题 body 角色）")
    parser.add_argument("--theme", help="effective theme JSON（colors/fonts；启用主题化文字层与对比度门）")
    parser.add_argument("--text-layer", action="store_true",
                        help="输出透明文字层（RGBA），供 composite 背景层/文字层合成")
    args = parser.parse_args(argv)

    try:
        from PIL import Image
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

    try:
        items, anchors = tl.load_whitelist_spec(raw_whitelist)
        theme = None
        theme_font = None
        if args.theme:
            theme = tl.normalize_theme(json.loads(Path(args.theme).read_text(encoding="utf-8")))
            theme_font = tl.theme_font_path(theme)
        theme_colors = theme["colors"] if theme else {}
        if args.color is not None:
            auto_color = args.color
        elif theme_colors:
            auto_color = theme_colors.get("body", tl.DEFAULT_COLOR)
        else:
            auto_color = tl.DEFAULT_COLOR
        plan = (
            tl.plan_anchored(items, anchors, args.font_size, theme_colors)
            if anchors
            else tl.plan_auto(items, args.font_size, auto_color)
        )
    except tl.TextLayerError as exc:
        fail(exc.detail or exc.reason_code)

    try:
        with Image.open(base_path) as opened:
            base = opened.convert("RGBA")
    except Exception as exc:
        fail(f"底图无法按图片读取：{exc}")
    try:
        base = tl.normalize_canvas(base)
    except tl.TextLayerError as exc:
        fail(exc.detail or exc.reason_code)
    width, height = base.size

    try:
        sizes = {int(item["size"]) for item in plan}
        fonts = {size: tl.resolve_font(args.font, size, theme_font) for size in sizes}
        # 对比度门只在主题化模式启用；TF-2 既有路径行为不变。
        lines = tl.layout_plan(plan, tl.draw_of(base), fonts, (width, height), base=base if theme else None)
        target = tl.new_canvas((width, height)) if args.text_layer else base
        tl.draw_lines(lines, fonts, target)
    except tl.TextLayerError as exc:
        fail(exc.detail or exc.reason_code)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.text_layer:
        target.save(out_path, format="PNG")
    else:
        target.convert("RGB").save(out_path, format="PNG")
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
    if args.text_layer:
        summary["text_layer"] = True
    if theme is not None:
        summary["theme"] = {"colors": sorted(theme["colors"]), "font_from_theme": bool(theme_font)}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
