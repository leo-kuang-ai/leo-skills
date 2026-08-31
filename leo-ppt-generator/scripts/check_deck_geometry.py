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

退出码：0 全部通过；1 几何断言失败；2 用法/文件错误；3 自测环境缺失。
"""
from __future__ import annotations

import argparse
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
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
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
