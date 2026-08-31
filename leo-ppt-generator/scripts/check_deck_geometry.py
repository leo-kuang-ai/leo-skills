#!/usr/bin/env python3
"""check_deck_geometry.py — 图片式 PPTX 交付的画布/页图几何断言。

背景（2026-08-29 事故）：页图以 3:2（1536x1024）生成，组装默认 contain
等高放置进 16:9 画布，每页左右各 0.781in 白边（15.6% 画布宽度），
结构门与三轮视觉审查均未拦截。本脚本把"画布比例 == 页图比例、满幅、
无拉伸"变成确定性门禁：非 0 退出即阻止交付。

仅用标准库（zipfile/re/struct/xml.etree），不依赖 python-pptx；
--self-test 需要 python-pptx（运行时 venv 内可用）用于构造 fixture。

用法：
    python3 scripts/check_deck_geometry.py <pptx> [more.pptx ...]
    python3 scripts/check_deck_geometry.py <pptx> --expect-ratio 16:9 --tolerance 0.02
    python3 scripts/check_deck_geometry.py --self-test
    python3 scripts/check_deck_geometry.py --capacity <deck_spec.json>

--capacity 为互斥模式（与 positional pptx 同给报用法错误）：生成前文本级
容量预检，输入 JSON 形如::

    {"style": "清爽专业风",
     "slides": [{"page": 3, "layout": "P5",
                 "slots": {"card_desc": "文本…"}},
                {"page": 4, "layout": "P19",
                 "points": ["要点一…", "要点二…"]}]}

三态：ok（exit 0）/ over 软超 ≤ max_chars×1.2（exit 0 + WARN 行，建议
降档位或换版式，绝不建议缩字号）/ overflow 硬超（exit 1 阻断定稿，输出
逐 slot 当前 vw / 容量 vw / 替代版式候选）。软超不占退出码是刻意的：
CI-4 的 2 语义保留给用法错误，三态用输出行区分（文档成文见
references/layout-dispatch.md）。

退出码：0 全部通过；1 几何断言失败（--capacity 模式为硬超容量）；2 用法/文件错误；3 自测环境缺失。
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

EMU_PER_INCH = 914400

# --------------------------------------------------------------------------- #
# vw 容量模型（B3：生成前文本级容量预检）
#
# vw_of 字符宽度语义：CJK/全角 = 1.0、空格 = 0.35、ASCII = 0.5、其他 = 0.8。
# leo_capacity_for 是 leo 版心 token 语境的换算（公式来源
# references/styles/00_索引/版心Canon.md）。
# --------------------------------------------------------------------------- #

CANVAS_W_PX = 2560  # 16:9 生图画布基准，1vw = 25.6px
CANVAS_H_PX = 1440  # 1vh = 14.4px
PAGE_MARGIN_X_VW = 5  # 版心 Canon: page-margin-x
GRID_GUTTER_VW = 2  # 版心 Canon: grid-gutter（桌面）
GRID_COLS = 12
FILL_MARGIN = 0.95  # 容器内边距让渡（近似上游 H_MARGIN 的 5%）
CAPACITY_LINE_HEIGHT = 1.0  # 上游 LINE_HEIGHT：CJK 正文单倍行距
CAPACITY_TOLERANCE = 1.2  # 上游 TOLERANCE：模型 slack，假阳校准 0-5%

SIDEcar_LAYOUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "references" / "styles" / "12_版式库"
)
STYLES_DIR = Path(__file__).resolve().parents[1] / "references" / "styles"


def vw_of(text: str) -> float:
    """文本的视觉宽度（CJK 等效单位）：CJK/全角=1.0，空格=0.35，ASCII=0.5，其他=0.8。"""
    width = 0.0
    for ch in text:
        if ("\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f"
                or "\uff00" <= ch <= "\uffef"):
            width += 1.0
        elif ch == " ":
            width += 0.35
        elif ch.isascii():
            width += 0.5
        else:
            width += 0.8
    return width


def container_px(cols: int) -> float:
    """栏数对应的容器可用宽（px），从版心 Canon token 推导。"""
    usable_vw = 100 - 2 * PAGE_MARGIN_X_VW - GRID_GUTTER_VW
    return (cols / GRID_COLS) * usable_vw * (CANVAS_W_PX / 100) * FILL_MARGIN


def leo_capacity_for(cols: int, height_vh: float, font_px: float) -> tuple[int, int, int]:
    """从版心 token 几何推导 (chars_per_line, max_lines, max_chars)。

    chars_per_line = floor(可用宽 px / 字号 px)；max_lines 按容器高 vh 与
    行高 1.0 推导；max_chars = floor(cpl × lines × 1.2)（TOLERANCE 保留）。
    """
    import math

    if font_px <= 0:
        raise ValueError("font_px must be positive")
    cpl = max(1, math.floor(container_px(cols) / font_px))
    height_px = height_vh / 100 * CANVAS_H_PX
    max_lines = max(1, math.floor(height_px / (font_px * CAPACITY_LINE_HEIGHT)))
    max_chars = max(1, math.floor(cpl * max_lines * CAPACITY_TOLERANCE))
    return cpl, max_lines, max_chars


def _load_layout_sidecars() -> dict[str, dict]:
    """读全部版式 sidecar（layout_id -> sidecar dict）；不可解析即清晰失败。"""
    bank: dict[str, dict] = {}
    for path in sorted(SIDEcar_LAYOUT_DIR.glob("*.layouts.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("entity") == "layout":
            bank[str(data.get("layout_id"))] = data
    return bank


def _style_capacity_factor(style_name: str | None) -> float:
    if not style_name:
        return 1.0
    path = STYLES_DIR / f"{style_name}.layouts.json"
    if not path.is_file():
        return 1.0
    data = json.loads(path.read_text(encoding="utf-8"))
    factor = data.get("capacity_factor", {}).get("text", 1.0)
    return float(factor) if isinstance(factor, (int, float)) else 1.0


def _capacity_alternatives(
    bank: dict[str, dict], layout_id: str, needed_chars: float, points: int | None
) -> list[str]:
    """同 page_type、能装下当前需求（数量或文本量）的替代版式候选（≤3 个）。"""
    page_type = bank[layout_id].get("page_type")
    candidates: list[tuple[str, int]] = []
    for other_id, sidecar in bank.items():
        if other_id == layout_id or sidecar.get("page_type") != page_type:
            continue
        capacity = sidecar.get("content_capacity", {})
        if points is not None:
            counts = [
                (s.get("count_min", 0), s.get("count_max", 0))
                for s in capacity.values()
                if "count_min" in s
            ]
            if counts and not any(lo <= points <= hi for lo, hi in counts):
                continue
        best_text = max(
            (s.get("max_chars", 0) for s in capacity.values()
             if "max_chars" in s),
            default=0,
        )
        if best_text >= needed_chars:
            candidates.append((other_id, best_text))
    candidates.sort(key=lambda kv: (-kv[1], kv[0]))
    return [cid for cid, _ in candidates[:3]]


def capacity_check(spec_path: Path) -> int:
    """--capacity 模式：逐页文本级容量三态预检（ok / over / overflow）。"""
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        print(f"[ERROR] {spec_path}: 不可读（{exc}）")
        return 2
    except json.JSONDecodeError as exc:
        print(f"[ERROR] {spec_path}: JSON 不可解析（{exc}）")
        return 2
    slides = spec.get("slides")
    if not isinstance(slides, list) or not slides:
        print(f"[ERROR] {spec_path}: 缺 slides 数组")
        return 2
    try:
        bank = _load_layout_sidecars()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] 版式 sidecar 不可读: {exc}")
        return 2
    if not bank:
        print("[ERROR] 版式 sidecar 库为空（12_版式库/*.layouts.json）")
        return 2
    factor = _style_capacity_factor(spec.get("style"))
    rc = 0
    saw_soft = False
    for slide in slides:
        if not isinstance(slide, dict) or "layout" not in slide:
            print("[ERROR] slides[] 每页必须含 layout 字段")
            return 2
        page = slide.get("page", "?")
        layout_id = str(slide["layout"])
        # 版式名（如 "KPI Tower"）解析到 P 码
        if layout_id not in bank:
            matches = [
                lid for lid, sc in bank.items()
                if layout_id in str(sc.get("name", ""))
            ]
            if len(matches) != 1:
                print(f"[ERROR] 第 {page} 页: 未知版式 {layout_id!r}")
                return 2
            layout_id = matches[0]
        sidecar = bank[layout_id]
        capacity = sidecar.get("content_capacity", {})
        slots_text = slide.get("slots") or {}
        points = slide.get("points")
        problems: list[str] = []
        hard = False
        soft = False
        # ① 数量型：points 条数落在 count 区间（含 1.2 软带）
        if isinstance(points, list):
            for slot_name, slot in sorted(capacity.items()):
                if "count_min" not in slot:
                    continue
                lo, hi = slot["count_min"], slot["count_max"]
                n = len(points)
                if n < lo:
                    problems.append(
                        f"count:{slot_name} 条数 {n} < 下限 {lo}（换版式候选 "
                        f"{_capacity_alternatives(bank, layout_id, 0, n) or '无同型'}）"
                    )
                elif n > hi:
                    band = hi * CAPACITY_TOLERANCE
                    if n <= band:
                        soft = True
                        problems.append(
                            f"over:count:{slot_name} 条数 {n} 超上限 {hi}"
                            f"（降档删要点至 ≤{hi}，或换版式候选 "
                            f"{_capacity_alternatives(bank, layout_id, 0, n) or '无同型'}）"
                        )
                    else:
                        hard = True
                        problems.append(
                            f"overflow:count:{slot_name} 条数 {n} 硬超上限 {hi}"
                            f"（降档删要点至 ≤{hi}，或换版式候选 "
                            f"{_capacity_alternatives(bank, layout_id, 0, n) or '无同型'}）"
                        )
        # ② 文本型：slots 显式给文本，逐 slot 对账
        if not isinstance(slots_text, dict):
            print(f"[ERROR] 第 {page} 页: slots 必须是对象")
            return 2
        for slot_name in sorted(slots_text):
            if slot_name not in capacity:
                print(f"[ERROR] 第 {page} 页: 版式 {layout_id} 无 slot {slot_name!r}")
                return 2
        checks: list[tuple[str, str]] = [
            (name, text) for name, text in sorted(slots_text.items())
        ]
        if isinstance(points, list) and points and not checks:
            # 无显式 slots 时，points 逐条对最宽文本 slot（每要点一条的近似）
            widest = sorted(
                ((s.get("max_chars", 0), n) for n, s in capacity.items()
                 if "max_chars" in s),
                reverse=True,
            )
            if widest:
                slot_name = widest[0][1]
                checks = [(slot_name, text) for text in points]
        for slot_name, text in checks:
            slot = capacity.get(slot_name, {})
            if "max_chars" not in slot:
                print(f"[ERROR] 第 {page} 页: slot {slot_name!r} 非文本型")
                return 2
            limit = slot["max_chars"] * factor
            used = vw_of(str(text))
            if used <= limit:
                continue
            band = limit * CAPACITY_TOLERANCE
            if used <= band:
                soft = True
                problems.append(
                    f"over:{slot_name} {used:.1f}/{limit:.0f} vw（软超 ≤1.2×）→ "
                    "降档位（删减要点文字）或换版式，不缩字号"
                )
            else:
                hard = True
                alts = _capacity_alternatives(bank, layout_id, used, None)
                problems.append(
                    f"overflow:{slot_name} {used:.1f}/{limit:.0f} vw（硬超 >1.2×）→ "
                    f"降档（论点页 ≤3 → ≤2）或换版式候选 "
                    f"{alts or '无同型'}，不缩字号、不省略号截断"
                )
        if problems:
            level = "FAIL" if hard else "WARN"
            saw_soft = saw_soft or soft
            print(f"[{level}] 第 {page} 页 {layout_id}（{sidecar.get('name')}）:")
            for p in problems:
                print(f"  - {p}")
            if hard:
                rc = 1
        else:
            print(f"[OK] 第 {page} 页 {layout_id}（{sidecar.get('name')}）: 容量内")
    if rc == 0:
        note = "（含 over 软超 WARN 行，降档/换版式处理，不占退出码）" if saw_soft else ""
        print(f"capacity precheck 完成{note}")
    return rc


def parse_ratio(text: str) -> float:
    if ":" in text:
        w, h = text.split(":", 1)
        return float(w) / float(h)
    return float(text)


def sniff_image_size(data: bytes, name: str) -> tuple[int, int]:
    """从 PNG/JPEG 字节流读取像素尺寸（本路线页图为 PNG）。"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if data[12:16] != b"IHDR":
            raise ValueError(f"{name}: PNG 缺少 IHDR")
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    if data[:2] == b"\xff\xd8":  # JPEG：扫描 SOF0/SOF2 段
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                return int(w), int(h)
            seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
            i += 2 + seg_len
        raise ValueError(f"{name}: JPEG 中未找到 SOF 段")
    raise ValueError(f"{name}: 不支持的图片格式（仅 PNG/JPEG）")


class SlideGeometry:
    def __init__(self, index: int, slide_ratio: float, pictures: list[dict]):
        self.index = index
        self.slide_ratio = slide_ratio
        self.pictures = pictures  # [{name, disp_w, disp_h, nat_w, nat_h, crop}]


def inspect_pptx(path: Path, expect_ratio: float, tolerance: float, min_coverage: float):
    problems: list[str] = []
    with zipfile.ZipFile(path) as z:
        pres = ET.fromstring(z.read("ppt/presentation.xml"))
        sld = pres.find(f"{{{NS_P}}}sldSz")
        if sld is None:
            raise ValueError("presentation.xml 缺少 sldSz")
        cw, ch = int(sld.get("cx")), int(sld.get("cy"))
        slide_ratio = cw / ch
        if abs(slide_ratio - expect_ratio) / expect_ratio > tolerance:
            problems.append(
                f"画布比例 {slide_ratio:.4f} ≠ 期望 {expect_ratio:.4f} "
                f"({cw/EMU_PER_INCH:.3f}x{ch/EMU_PER_INCH:.3f}in)"
            )

        slide_names = sorted(
            (n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.search(r"(\d+)", n).group(1)),
        )
        slides: list[SlideGeometry] = []
        for idx, name in enumerate(slide_names, 1):
            xml = z.read(name)
            root = ET.fromstring(xml)
            rels = ET.fromstring(
                z.read(f"ppt/slides/_rels/{Path(name).name}.rels")
            )
            rel_map = {
                rel.get("Id"): rel.get("Target") for rel in rels
            }
            pictures = []
            for pic in root.iter(f"{{{NS_P}}}pic"):
                blip = pic.find(f".//{{{NS_A}}}blip")
                embed = blip.get(f"{{{NS_R}}}embed") if blip is not None else None
                target = rel_map.get(embed, "")
                target = target.replace("../", "ppt/")
                if not target.startswith("ppt/"):
                    target = "ppt/" + target.lstrip("/")
                nat_w = nat_h = None
                if target in z.namelist():
                    nat_w, nat_h = sniff_image_size(z.read(target), target)
                xfrm = pic.find(f".//{{{NS_A}}}xfrm")
                ext = xfrm.find(f"{{{NS_A}}}ext") if xfrm is not None else None
                disp_w = int(ext.get("cx")) if ext is not None else None
                disp_h = int(ext.get("cy")) if ext is not None else None
                src = pic.find(f".//{{{NS_A}}}srcRect")
                crop = {
                    "l": float(src.get("l", 0)) if src is not None else 0.0,
                    "r": float(src.get("r", 0)) if src is not None else 0.0,
                    "t": float(src.get("t", 0)) if src is not None else 0.0,
                    "b": float(src.get("b", 0)) if src is not None else 0.0,
                }
                pictures.append(
                    {
                        "name": target or "<unknown>",
                        "disp_w": disp_w,
                        "disp_h": disp_h,
                        "nat_w": nat_w,
                        "nat_h": nat_h,
                        "crop": crop,
                    }
                )
            slides.append(SlideGeometry(idx, slide_ratio, pictures))

    # 断言
    for s in slides:
        if not s.pictures:
            problems.append(f"第 {s.index} 页：没有任何图片形状")
            continue
        covered = 0.0
        for p in s.pictures:
            if p["nat_w"] is None or p["disp_w"] is None:
                problems.append(f"第 {s.index} 页：图片 {p['name']} 尺寸不可解析")
                continue
            nat_crop_w = p["nat_w"] * (1 - p["crop"]["l"] - p["crop"]["r"])
            nat_crop_h = p["nat_h"] * (1 - p["crop"]["t"] - p["crop"]["b"])
            natural_ratio = nat_crop_w / nat_crop_h
            disp_ratio = p["disp_w"] / p["disp_h"]
            if abs(disp_ratio - natural_ratio) / natural_ratio > tolerance:
                problems.append(
                    f"第 {s.index} 页：图片 {Path(p['name']).name} 被拉伸 "
                    f"({p['nat_w']}x{p['nat_h']} → 显示比例 {disp_ratio:.4f} ≠ 原始 {natural_ratio:.4f})"
                )
            covered += (p["disp_w"] * p["disp_h"]) / (cw * ch)
        coverage = min(1.0, covered)
        if coverage < min_coverage:
            side = "左右" if slide_ratio > max(
                (p["nat_w"] / p["nat_h"]) for p in s.pictures if p["nat_w"]
            ) else "上下"
            problems.append(
                f"第 {s.index} 页：图片覆盖率 {coverage:.1%} < {min_coverage:.0%} "
                f"（存在 {side}留白，页图比例与画布不一致）"
            )
    return len(slides), problems


def make_png(w: int, h: int, rgb=(255, 255, 255)) -> bytes:
    """最小可用 PNG（单行压缩），纯标准库。"""
    import zlib

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        c = struct.pack(">I", len(payload)) + tag + payload
        return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def self_test() -> int:
    try:
        from pptx import Presentation
        from pptx.util import Inches
    except ImportError:
        print("self-test 需要 python-pptx（可用运行时 venv 的 python）", file=sys.stderr)
        return 3
    import tempfile

    failures = 0
    cases = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # 好：16:9 画布 + 2560x1440 满幅
        good = td / "good.pptx"
        prs = Presentation()
        prs.slide_width, prs.slide_height = Inches(10), Inches(5.625)
        img = td / "wide.png"
        img.write_bytes(make_png(256, 144))
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_picture(str(img), 0, 0, width=prs.slide_width, height=prs.slide_height)
        prs.save(str(good))
        cases.append((good, True, "16:9 满幅"))
        # 坏：3:2 图片 contain 放置（本次事故形态）
        bad = td / "bad.pptx"
        img32 = td / "narrow.png"
        img32.write_bytes(make_png(153, 102))
        prs2 = Presentation()
        prs2.slide_width, prs2.slide_height = Inches(10), Inches(5.625)
        s2 = prs2.slides.add_slide(prs2.slide_layouts[6])
        s2.shapes.add_picture(str(img32), Inches(0.781), 0, height=prs2.slide_height)
        prs2.save(str(bad))
        cases.append((bad, False, "3:2 contain 留白"))
        # 坏：拉伸填满
        stretch = td / "stretch.pptx"
        prs3 = Presentation()
        prs3.slide_width, prs3.slide_height = Inches(10), Inches(5.625)
        s3 = prs3.slides.add_slide(prs3.slide_layouts[6])
        s3.shapes.add_picture(str(img32), 0, 0, width=prs3.slide_width, height=prs3.slide_height)
        prs3.save(str(stretch))
        cases.append((stretch, False, "3:2 拉伸变形"))
        for path, should_pass, label in cases:
            try:
                _, problems = inspect_pptx(path, parse_ratio("16:9"), 0.02, 0.98)
                passed = not problems
            except Exception as exc:  # noqa: BLE001
                passed, problems = False, [str(exc)]
            ok = passed == should_pass
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}: expected={'通过' if should_pass else '拦截'} 实际={'通过' if passed else '拦截: ' + '; '.join(problems)}")
            failures += 0 if ok else 1
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="图片式 PPTX 画布/页图几何断言（非 0 退出阻止交付）")
    ap.add_argument("pptx", nargs="*", help="待检查的 PPTX 路径")
    ap.add_argument("--expect-ratio", default="16:9", help="期望画布比例，如 16:9 或 1.7778")
    ap.add_argument("--tolerance", type=float, default=0.02, help="比例相对容差（默认 0.02）")
    ap.add_argument("--min-coverage", type=float, default=0.98, help="页图最小画布覆盖率（默认 0.98）")
    ap.add_argument("--self-test", action="store_true", help="运行内置 fixture 自测")
    ap.add_argument(
        "--capacity", metavar="SPEC",
        help="互斥模式：生成前文本级容量预检（deck_spec/master JSON，"
             "消费 12_版式库/*.layouts.json 容量表；与 positional pptx 同给报用法错误）",
    )
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.capacity:
        if args.pptx:
            ap.error("--capacity 与 positional PPTX 互斥（二者只给其一）")
        spec = Path(args.capacity)
        if not spec.is_file():
            print(f"[ERROR] {spec}: 文件不存在")
            return 2
        return capacity_check(spec)
    if not args.pptx:
        ap.error("至少提供一个 PPTX 路径")
    expect = parse_ratio(args.expect_ratio)
    rc = 0
    for raw in args.pptx:
        path = Path(raw)
        if not path.is_file():
            print(f"[ERROR] {path}: 文件不存在")
            rc = 2
            continue
        try:
            count, problems = inspect_pptx(path, expect, args.tolerance, args.min_coverage)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {path}: {exc}")
            rc = 2
            continue
        if problems:
            rc = 1
            print(f"[FAIL] {path.name}（{count} 页）")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"[OK] {path.name}（{count} 页）：画布 {args.expect_ratio}，页图满幅无拉伸")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
