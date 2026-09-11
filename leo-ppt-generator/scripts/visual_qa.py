#!/usr/bin/env python3
"""visual_qa.py — leo-ppt 确定性像素质检前置闸门（E2，CI-4）。

leo 侧适配（自研增量）：

- 尺寸判据对齐 2560×1440 交付档（DIM-01 FAIL/WARN 分层按 leo 比例合同）；
- SIZE-01 仅提示压缩体积，不能替代像素空白检查或审美验收；
- 输入为 leo 的页图命名（``slide_*.png``），单页/目录两种模式；
- 输出机器可读 JSON 报告（--report），退出码 0/1/2 语义与
  check_deck_geometry.py 的职责分界见文件尾注。
- 上游的 planning/density_contract/html_contracts 检查族不移植
  （ppt-agent-skill 专属合同；leo 的 PLAN-01 策划卡对账为 P2 / E2-T3）。

用法：
    # 单页（worker 自查 / render-worker 单页闸门）
    python3 scripts/visual_qa.py <run>/image-deck/origin_image/slide_01.png --report <run>/reports/visual-qa.json

    # 目录批量（父 Agent 2.5 步，record 前对全部页跑）
    python3 scripts/visual_qa.py <run>/image-deck/origin_image --report <run>/reports/visual-qa.json

退出码（CI-4）：
    0 = 全部通过
    1 = 存在 FAIL（阻断交付、该页打回，不进 LLM 审——visual-qa.md 2.5 步）
    2 = 只有 WARN（可交付但必须写入 qa_note 并在交付话术披露）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow", file=sys.stderr)
    sys.exit(1)

# ─── leo 2560 交付档阈值（自研增量；上游为 960/10K/50K 档） ───
DELIVERY_WIDTH = 2560
DELIVERY_HEIGHT = 1440
WEB_WIDTH = 1280
SIZE_WARN_BYTES = 600_000


# ─────────────────────── 检测函数 ───────────────────────
# （函数族保留上游结构与阈值思想；leo 适配点见各 docstring）

def check_dimensions(img: Image.Image) -> dict:
    """DIM-01：16:9 且 ≥2560 宽（交付档）；1280 档 WARN；其余 FAIL。"""
    w, h = img.size
    if abs(w / h - 16 / 9) < 0.05:
        if w >= DELIVERY_WIDTH:
            return {"id": "DIM-01", "status": "PASS", "msg": f"分辨率 {w}x{h}（交付档 16:9）"}
        if w >= WEB_WIDTH:
            return {"id": "DIM-01", "status": "WARN",
                    "msg": f"分辨率 {w}x{h}（web 档；交付档需 ≥{DELIVERY_WIDTH} 宽）"}
        return {"id": "DIM-01", "status": "FAIL",
                "msg": f"分辨率 {w}x{h} 低于 web 档下限 {WEB_WIDTH}"}
    return {"id": "DIM-01", "status": "FAIL", "msg": f"分辨率 {w}x{h} 不符合 16:9 规格"}


def _dominant_color(pixels: list[tuple], total: int) -> tuple[tuple, float]:
    color_count: dict[tuple, int] = {}
    for p in pixels:
        quantized = (p[0] // 8 * 8, p[1] // 8 * 8, p[2] // 8 * 8)
        color_count[quantized] = color_count.get(quantized, 0) + 1
    dominant = max(color_count, key=color_count.get)
    return dominant, color_count[dominant] / total


def check_blank_ratio(img: Image.Image, threshold: float = 0.40) -> dict:
    """BLANK-01：近乎纯色才硬失败，稀疏页面提示复核；墨迹比例不是占用面积。"""
    small = img.resize((128, 72), Image.LANCZOS)
    pixels = list(small.getdata())
    total = len(pixels)

    dominant_color, dominant_ratio = _dominant_color(pixels, total)

    if dominant_ratio > threshold:
        content_pixels = sum(
            1 for p in pixels if max(abs(a - b) for a, b in zip(p, dominant_color)) > 60
        )
        content_ratio = content_pixels / total
        if dominant_ratio > 0.995 and content_ratio < 0.001:
            return {"id": "BLANK-01", "status": "FAIL",
                    "msg": f"页面近乎纯色，差异像素 {content_ratio:.2%}，请检查截图或渲染内容"}
        if content_ratio < 0.15:
            return {"id": "BLANK-01", "status": "WARN",
                    "msg": f"差异像素 {content_ratio:.1%}，请复核稀疏页面；此比例不是留白面积或设计评分"}
        return {"id": "BLANK-01", "status": "PASS",
                "msg": f"主色占 {dominant_ratio:.0%}，差异像素 {content_ratio:.0%}"}

    return {"id": "BLANK-01", "status": "PASS",
            "msg": f"画面色彩分布正常，主色占比 {dominant_ratio:.0%}"}


def check_vertical_text(img: Image.Image) -> dict:
    """VTXT-01：辅助检测疑似竖排单字列（WARN，不判最终）。"""
    w, h = img.size
    right_half = img.crop((w // 2, 0, w, h))
    small = right_half.resize((256, 144), Image.LANCZOS).convert("L")
    pixels = small.load()
    sw, sh = small.size

    threshold = 60
    suspect_regions = []

    x = 0
    while x < sw:
        col_content = sum(1 for y in range(sh) if pixels[x, y] > threshold)
        if col_content > sh * 0.25:
            band_start = x
            band_end = x
            while band_end < sw - 1:
                next_content = sum(1 for y in range(sh) if pixels[band_end + 1, y] > threshold)
                if next_content > sh * 0.15:
                    band_end += 1
                else:
                    break

            band_width = band_end - band_start + 1
            content_rows = set()
            for bx in range(band_start, band_end + 1):
                for y in range(sh):
                    if pixels[bx, y] > threshold:
                        content_rows.add(y)

            content_height = (max(content_rows) - min(content_rows) + 1) if content_rows else 0
            width_ratio = band_width / sw
            height_ratio = content_height / sh

            if width_ratio < 0.06 and height_ratio > 0.35:
                suspect_regions.append(f"w={width_ratio:.1%} h={height_ratio:.1%}")

            x = band_end + 1
        else:
            x += 1

    if suspect_regions:
        return {"id": "VTXT-01", "status": "WARN",
                "msg": f"检测到 {len(suspect_regions)} 处疑似窄列内容带（{'; '.join(suspect_regions[:3])}），建议人工确认排版"}

    return {"id": "VTXT-01", "status": "PASS", "msg": "未检测到竖排异常"}


def check_overflow_cutoff(img: Image.Image) -> dict:
    """CUT-01：底部 4 行 / 右侧 4 列内容像素 → 截断嫌疑（WARN）。

    leo 适配：上游判"亮像素"（brightness>80）假定深色背景；浅纸底整页
    都是亮像素会 100% 误报。改为背景相对：与主色亮度偏离 > 60 才算内容。
    """
    w, h = img.size
    pixels = img.load()
    small = img.resize((128, 72), Image.LANCZOS)
    dominant_color, _ = _dominant_color(list(small.getdata()), 128 * 72)
    dominant_brightness = sum(dominant_color) / 3

    def is_content(pixel) -> bool:
        return abs(sum(pixel[:3]) / 3 - dominant_brightness) > 60

    bottom_content_pixels = 0
    bottom_total = w * 4
    for y in range(h - 4, h):
        for x in range(w):
            if is_content(pixels[x, y]):
                bottom_content_pixels += 1
    bottom_ratio = bottom_content_pixels / bottom_total if bottom_total > 0 else 0

    right_content_pixels = 0
    right_total = h * 4
    for x in range(w - 4, w):
        for y in range(h):
            if is_content(pixels[x, y]):
                right_content_pixels += 1
    right_ratio = right_content_pixels / right_total if right_total > 0 else 0

    issues = []
    if bottom_ratio > 0.2:
        issues.append(f"底部边缘有 {bottom_ratio:.0%} 亮像素，疑似内容被裁切")
    if right_ratio > 0.15:
        issues.append(f"右侧边缘有 {right_ratio:.0%} 亮像素，疑似内容被裁切")

    if issues:
        return {"id": "CUT-01", "status": "WARN", "msg": " | ".join(issues)}
    return {"id": "CUT-01", "status": "PASS", "msg": "边缘无异常裁切痕迹"}


def check_contrast_zones(img: Image.Image) -> dict:
    """CONT-01：8×8 网格低方差中亮度块占比 > 60% → 对比度嫌疑（WARN）。"""
    w, h = img.size
    grid_w, grid_h = 8, 8
    block_w = w // grid_w
    block_h = h // grid_h

    low_contrast_blocks = 0
    total_blocks = grid_w * grid_h

    for gx in range(grid_w):
        for gy in range(grid_h):
            block = img.crop((gx * block_w, gy * block_h, (gx + 1) * block_w, (gy + 1) * block_h))
            small_block = block.resize((16, 16), Image.LANCZOS)
            pixels = list(small_block.getdata())
            brightnesses = [sum(p[:3]) / 3 for p in pixels]

            avg = sum(brightnesses) / len(brightnesses)
            variance = sum((b - avg) ** 2 for b in brightnesses) / len(brightnesses)

            if variance < 25 and 40 < avg < 200:
                low_contrast_blocks += 1

    ratio = low_contrast_blocks / total_blocks
    if ratio > 0.6:
        return {"id": "CONT-01", "status": "WARN",
                "msg": f"{ratio:.0%} 的区块对比度极低，可能存在文字不可读区域"}
    return {"id": "CONT-01", "status": "PASS",
            "msg": f"对比度分布正常（低对比区块 {ratio:.0%}）"}


def check_file_size(png_path: Path) -> dict:
    """SIZE-01：压缩体积仅作提示；空白与损坏分别由 BLANK/OPEN 判定。"""
    size = png_path.stat().st_size
    if size < SIZE_WARN_BYTES:
        return {"id": "SIZE-01", "status": "WARN",
                "msg": f"PNG {size:,} bytes；低体积可能来自平色压缩，不能据此判定内容过少"}
    return {"id": "SIZE-01", "status": "PASS", "msg": f"PNG {size:,} bytes"}


# ─────────────────────── 主逻辑 ───────────────────────

def run_checks(png_path: Path) -> list[dict]:
    """对单张 PNG 运行全部检测（像素内容层；结构层归 check_deck_geometry.py）。"""
    results = [check_file_size(png_path)]
    try:
        img = Image.open(png_path).convert("RGB")
    except Exception as e:
        results.append({"id": "OPEN-01", "status": "FAIL", "msg": f"无法打开 PNG: {e}"})
        return results
    results.append(check_dimensions(img))
    results.append(check_blank_ratio(img))
    results.append(check_vertical_text(img))
    results.append(check_overflow_cutoff(img))
    results.append(check_contrast_zones(img))
    results.append(check_design_density(img))
    return results


def build_page_report(png: Path, results: list[dict]) -> dict:
    fails = [r for r in results if r["status"] == "FAIL"]
    warns = [r for r in results if r["status"] == "WARN"]
    verdict = "FAIL" if fails else ("WARN" if warns else "PASS")
    return {
        "page": png.name,
        "path": str(png.resolve()),
        "verdict": verdict,
        "checks": results,
        "fail_count": len(fails),
        "warn_count": len(warns),
    }


def collect_pngs(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted([*target.glob("slide_*.png"), *target.glob("slide-*.png")])
    return []


def check_design_density(img: Image.Image) -> dict:
    """DESIGN-01：四象限差异像素分布提示，不作为设计验收。

    只看内容像素（亮度偏离主色 >60）的空间分布，不改判任何既有 FAIL：
    - 全页内容占比 < 6% 且存在 ≥2 个内容占比 < 0.5% 的象限 → WARN
      （版面大面积空置，典型如"标题+文字列表+缩略图表"的文档式页面）；
    - 四象限内容占比最大/最小 > 12 倍 → WARN（单象限孤岛布局）。
    判据为观察提示（WARN 不阻断），供 SAMPLE-GATE 人工复核参考；
    对留白型封面/金句页的误报由人工裁决，不升级 FAIL。
    """
    small = img.resize((256, 144), Image.LANCZOS)
    pixels = list(small.getdata())
    total = len(pixels)
    from collections import Counter
    dominant, _ = Counter(pixels).most_common(1)[0]
    flags = [int(max(abs(a - b) for a, b in zip(px, dominant)) > 60) for px in pixels]
    overall = sum(flags) / total
    quads = []
    for qy in range(2):
        for qx in range(2):
            cell = [flags[y * 256 + x] for y in range(qy * 72, (qy + 1) * 72)
                    for x in range(qx * 128, (qx + 1) * 128)]
            quads.append(sum(cell) / len(cell))
    empty_quads = sum(1 for q in quads if q < 0.005)
    if overall < 0.06 and empty_quads >= 2:
        return {"id": "DESIGN-01", "status": "WARN",
                "msg": f"差异像素 {overall:.1%}，{empty_quads} 个象限近空，请结合页面角色复核"}
    if max(quads) > 0 and max(quads) / max(min(quads), 1e-6) > 12:
        return {"id": "DESIGN-01", "status": "WARN",
                "msg": f"象限差异像素分布不均，{empty_quads} 个象限近空，请结合页面角色复核"}
    return {"id": "DESIGN-01", "status": "PASS",
            "msg": f"差异像素 {overall:.1%}，象限分布 {['%.1f%%' % (q*100) for q in quads]}；不代表设计验收通过"}


def main() -> int:
    args = sys.argv[1:]
    report_path = None
    paths = []
    i = 0
    while i < len(args):
        if args[i] == "--report" and i + 1 < len(args):
            report_path = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--help" or args[i] == "-h":
            print(__doc__)
            return 0
        else:
            paths.append(args[i])
            i += 1

    if len(paths) != 1:
        print(__doc__)
        print("ERROR: 恰好一个目标（单页 PNG 或页图目录）", file=sys.stderr)
        return 1

    target = Path(paths[0]).resolve()
    pngs = collect_pngs(target)
    if not pngs:
        print(f"ERROR: 未找到可检查的 PNG（slide_*.png / slide-*.png）于 {target}", file=sys.stderr)
        return 1

    pages = [build_page_report(png, run_checks(png)) for png in pngs]
    total_fails = sum(p["fail_count"] for p in pages)
    total_warns = sum(p["warn_count"] for p in pages)
    verdict = "FAIL" if total_fails else ("WARN" if total_warns else "PASS")

    report = {
        "schema_version": 1,
        "kind": "visual_qa_report",
        "target": str(target),
        "pages": pages,
        "summary": {
            "pages": len(pages),
            "verdict": verdict,
            "fail_pages": [p["page"] for p in pages if p["verdict"] == "FAIL"],
            "warn_pages": [p["page"] for p in pages if p["verdict"] == "WARN"],
            "exit_code": 1 if total_fails else (2 if total_warns else 0),
        },
    }
    for page in pages:
        icons = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}
        print(f"{page['page']}: {page['verdict']}")
        for r in page["checks"]:
            print(f"  [{icons[r['status']]}] {r['id']}: {r['msg']}")
    print(
        f"TOTAL: {len(pages)} pages, FAIL={total_fails}, WARN={total_warns} → "
        f"EXIT {report['summary']['exit_code']}"
        + ("（FAIL 页不进 LLM 审，直接打回）" if total_fails else "")
    )

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return report["summary"]["exit_code"]


# ─── 职责分界（与 check_deck_geometry.py；两文件头注互引） ───
# check_deck_geometry.py：OOXML 结构层（assemble 之后）——画布比例、页图 vs
#   画布、拉伸、覆盖率；输入是 PPTX。
# 本脚本：像素内容层（record 之前，逐页）——空白、截断、对比度、文件大小；
#   输入是 PNG。两者的 DIM 断言在各自层面独立成立，不重复不冲突。

if __name__ == "__main__":
    sys.exit(main())
