#!/usr/bin/env python3
"""validate_visual_measure.py — 社交卡片测量式视觉质检（规格真值见
references/social-card-specs.md，阈值取自上游 guizang-social-card-skill
validate-social-deck.mjs R1-R9 的可测量子集，快照 2026-07 v0.15）。

双态设计：

1. **纯规则态（核心，纯标准库）**：输入「测量结果 JSON」（页面元素几何数据：
   各内容块的 y 范围 / 字号 / 角色、画布宽高），输出违规清单。实现规则：
   - R1 溢出        元素超出画布边界（error 级），附四档修正阶梯
                     （1-40 微调 / 41-90 压缩 / 91-160 删减 / >160 换版式）
   - R4 最小字号    正文/导语/脚注等文字角色低于机读下限（warn 级）
   - R5 4 横带密度  仅 3:4 画板：总覆盖 <75% 违规；>15% 画布高的空白横带
                     无 whitespace_reason 标注即违规；相邻两带同稀判中段空洞
   - R8 视觉边界    内容贴边间距低于画板安全区下限；底部留白超限且活跃
                     高度不足（warn 级）
   - R9 标题间距    展示/局部标题与下一内容块间距低于下限（warn 级）
2. **渲染测量态（可选）**：`--html <file>` 且本机可 import playwright 时，
   真实渲染 HTML，对每个 ``section.poster`` 跑一段测量 JS 收集几何 JSON，
   再走同一套规则函数；playwright 缺失时输出固定降级块并以退出码 3 结束。

测量 JSON 结构（纯规则态输入）::

    {
      "canvas": {"width": 1080, "height": 1440, "board": "xhs"},   // board 可省略，按比例识别
      "pages": [
        {
          "id": "xhs-01-cover",
          "blocks": [   // 有意义内容块（文字/图/规则线/色块），坐标相对画布左上角
            {"id": "title-1", "role": "title",      // title|local_title|body|lead|
             "y_top": 96, "y_bottom": 220,          //  caption|meta|cell_title|num_note|
             "x_left": 72, "x_right": 1008,         //  image|other
             "font_size": 88, "text": "…", "background": false}
          ],
          "whitespace_reasons": [                   // 留白理由标注，豁免空白横带判定
            {"y_top": 900, "y_bottom": 1160, "reason": "hero breathing"}
          ]
        }
      ]
    }

用法：
    python3 scripts/validate_visual_measure.py --measurements deck.json
    python3 scripts/validate_visual_measure.py --html index.html
    python3 scripts/validate_visual_measure.py            # 打印用法与降级说明

退出码：0 无 error 级违规；1 存在 error 级违规；2 用法/输入错误；
        3 --html 渲染态因 playwright 缺失降级。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 阈值常量（与 references/social-card-specs.md 数值一一对应；来源括注上游文件）
# ---------------------------------------------------------------------------

# R1/R8 溢出容差（validate-social-deck.mjs R1 `overflow > 4`）
OVERFLOW_TOLERANCE_PX = 4
# R1 修正阶梯分档上限（qa-checklist.md Overflow Correction Ladder 40/90/160）
LADDER_TWEAK_MAX_PX = 40
LADDER_COMPACT_MAX_PX = 90
LADDER_REDUCE_MAX_PX = 160

# R4 最小字号机读下限（validate-social-deck.mjs MIN_FONT；设计下限见规格表第三节）
MIN_FONT_PX = {
    "body": 22,
    "lead": 26,
    "caption": 18,
    "meta": 18,
    "cell_title": 20,
    "num_note": 20,
}

# R5 4 横带密度（validate-social-deck.mjs R5 + qa-checklist.md 4-band check）
DENSITY_BANDS = 4
DENSITY_TOTAL_MIN = 0.745  # ≥75%，含 0.5% 浮点容差（上游 0.745）
EMPTY_BAND_RATIO = 0.15  # 空白横带 >15% 画布高（>216px @1440）需留白理由
ADJACENT_SPARSE_RATIO = 0.15  # 相邻两带占有率均 <15% = 中段 >25% 空洞
REASON_OVERLAP_EXEMPT = 0.5  # 空白带与理由标注重叠 ≥50% 视为已豁免

# R8 视觉边界（platform-specs.md 安全区下限 + components.md 间距 token sp-11/sp-13）
EDGE_FLOOR_PX = {
    "xhs": {"top": 72, "side": 72, "bottom": 80},
    "square": {"top": 80, "side": 80, "bottom": 80},
    "wide": {"top": 80, "side": 160, "bottom": 80},
}
EDGE_FLOOR_DEFAULT_PX = 48  # 未知画板兜底（sp-9 段距 token）
# R8 底部留白上限与活跃高度下限（validate-social-deck.mjs R8）
BOTTOM_GAP_LIMIT_PX = {"xhs": 190, "square": 160, "wide": 130}
ACTIVE_RATIO_MIN = 0.78

# R9 标题间距（validate-social-deck.mjs R9 minGap：局部 16 / 宽画板 24 / 其余 28）
TITLE_GAP_MIN_PX = 28
LOCAL_TITLE_GAP_MIN_PX = 16
WIDE_TITLE_GAP_MIN_PX = 24
TITLE_GAP_XOVERLAP_MIN = 0.12  # 相邻块最小水平重叠比（上游 overlapRatio 门槛）
TITLE_GAP_SKIP_OVERLAP_PX = -2  # gap < -2px 属叠放/溢出问题，交 R1，不按间距报

# 画板识别（上游 board ratio 容差）
BOARD_RATIO_MATCH = (
    ("xhs", 0.75, 0.02),  # 3:4
    ("square", 1.0, 0.02),  # 1:1
    ("wide", 7 / 3, 0.05),  # 21:9
)
BOARD_ALIASES = {"3:4": "xhs", "1:1": "square", "21:9": "wide"}

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2
EXIT_DEGRADED = 3

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"

RULE_LABELS = {
    "R1": "溢出",
    "R4": "最小字号",
    "R5": "4横带密度",
    "R8": "视觉边界",
    "R9": "标题间距",
}

DEGRADE_BLOCK = """---- 降级：渲染测量态不可用 ----
当前 Python 环境未安装 playwright，--html 无法真实渲染。两种继续方式：
  1) 安装前置后重试 --html：
       pip install playwright && playwright install chromium
  2) 手工/外部提供测量结果 JSON，直接走纯规则态（测试与 CI 主入口）：
       python3 scripts/validate_visual_measure.py --measurements deck.json
     测量 JSON 结构见脚本 docstring 或 references/social-card-specs.md 第六节。
--------------------------------"""

# 渲染测量态注入页面的测量 JS：对每个 section.poster 收集内容块几何与计算字号。
JS_COLLECTOR = r"""
() => {
  const ROLE_RULES = [
    [".h-display, .h-xl, .h-hero, .h-statement, .num-mega, .num-xl", "title"],
    [".h-md, .row-title, .step-title", "local_title"],
    [".body", "body"],
    [".lead", "lead"],
    [".kicker, .caption, .swiss-img-caption, .img-cap, .cap, .h-sub", "caption"],
    [".meta, .label, .mono, .t-meta, .t-cat", "meta"],
    [".cell-title, .brief-card .title, .char-grid .name", "cell_title"],
    [".stat-card .lbl, .ledger .sub, .num .sub", "num_note"],
  ];
  const TRANSPARENT = /rgba?\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0?\s*\)|transparent/;
  const hasDirectText = (n) => {
    for (const c of n.childNodes) {
      if (c.nodeType === 3 && c.textContent.trim()) return true;
    }
    return false;
  };
  const pages = [];
  for (const el of document.querySelectorAll("section.poster")) {
    const er = el.getBoundingClientRect();
    const W = el.clientWidth, H = el.clientHeight, area = W * H;
    const blocks = [];
    for (const n of el.querySelectorAll("*")) {
      if (n.closest("script, style")) continue;
      if (n === el || n.classList.contains("content")) continue;
      const cs = getComputedStyle(n);
      const r = n.getBoundingClientRect();
      if (r.width < 6 || r.height < 6) continue;
      const nodeArea = r.width * r.height;
      const isBgLayer = n.classList.contains("mag-bg") || n.classList.contains("grain") ||
        n.classList.contains("ink-vignette") ||
        (cs.position === "absolute" && nodeArea >= area * 0.85);
      const tag = n.tagName;
      const isText = hasDirectText(n);
      const isMedia = tag === "IMG" || tag === "CANVAS" || tag === "SVG";
      const visibleBg = cs.backgroundColor && !TRANSPARENT.test(cs.backgroundColor);
      const isRule = tag === "HR" ||
        (r.height <= 4 && (parseFloat(cs.borderTopWidth) >= 1 ||
                           parseFloat(cs.borderBottomWidth) >= 1 || visibleBg));
      const hasFill = visibleBg && nodeArea >= 1600 && !["MAIN", "SECTION"].includes(tag);
      const hasBorder = (parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth) +
        parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth)) >= 1 && nodeArea >= 1600;
      if (!isText && !isMedia && !isRule && !hasFill && !hasBorder && !isBgLayer) continue;
      let role = isMedia ? "image" : "other";
      if (!isMedia) {
        for (const pair of ROLE_RULES) {
          if (n.matches(pair[0])) { role = pair[1]; break; }
        }
      }
      let id = n.id ? n.id : tag.toLowerCase();
      if (!n.id && n.className && typeof n.className === "string") {
        id = "." + n.className.trim().split(/\s+/).slice(0, 2).join(".");
      }
      blocks.push({
        id: String(id).slice(0, 40),
        role: role,
        y_top: Math.round((r.top - er.top) * 10) / 10,
        y_bottom: Math.round((r.bottom - er.top) * 10) / 10,
        x_left: Math.round((r.left - er.left) * 10) / 10,
        x_right: Math.round((r.right - er.left) * 10) / 10,
        font_size: (role !== "image" && cs.fontSize) ? Math.round(parseFloat(cs.fontSize)) : null,
        text: n.textContent.trim().replace(/\s+/g, " ").slice(0, 24),
        background: isBgLayer,
      });
    }
    let whitespace_reasons = [];
    if (el.dataset.whitespaceReasons) {
      try { whitespace_reasons = JSON.parse(el.dataset.whitespaceReasons); }
      catch (e) { whitespace_reasons = []; }
    }
    pages.push({
      id: el.id || "(no-id)",
      width: W,
      height: H,
      board: el.classList.contains("xhs") ? "xhs"
        : el.classList.contains("square") ? "square"
        : el.classList.contains("wide") ? "wide" : null,
      blocks: blocks,
      whitespace_reasons: whitespace_reasons,
    });
  }
  return { pages: pages };
}
"""


# ---------------------------------------------------------------------------
# 输入归一化
# ---------------------------------------------------------------------------

def detect_board(width: float, height: float, declared: str | None = None) -> str:
    """画板识别：显式声明优先（含 3:4/1:1/21:9 别名），否则按宽高比。"""
    if declared:
        norm = str(declared).strip().lower()
        if norm in BOARD_ALIASES:
            return BOARD_ALIASES[norm]
        if norm in ("xhs", "square", "wide"):
            return norm
    if width <= 0 or height <= 0:
        return "unknown"
    ratio = width / height
    for name, target, tol in BOARD_RATIO_MATCH:
        if abs(ratio - target) < tol:
            return name
    return "unknown"


def _require(block: dict, key: str, page_no: int, idx: int) -> float:
    if key not in block or block[key] is None:
        raise ValueError(f"第 {page_no} 页第 {idx} 个内容块缺少 {key}")
    return float(block[key])


def normalize_document(data: object) -> list[dict]:
    """把测量 JSON 归一化为页列表（画布/画板/内容块/留白理由均已解析）。"""
    if isinstance(data, dict) and isinstance(data.get("pages"), list):
        base_canvas = data.get("canvas") or {}
        raw_pages = data["pages"]
    elif isinstance(data, list):
        base_canvas, raw_pages = {}, data
    elif isinstance(data, dict) and isinstance(data.get("blocks"), list):
        base_canvas, raw_pages = data.get("canvas") or {}, [data]
    else:
        raise ValueError("测量 JSON 需为 {canvas, pages}、页列表或单页对象")

    pages = []
    for i, raw in enumerate(raw_pages, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"第 {i} 页不是对象")
        canvas = raw.get("canvas") or base_canvas or {}
        width = raw.get("width", canvas.get("width"))
        height = raw.get("height", canvas.get("height"))
        if not width or not height:
            raise ValueError(f"第 {i} 页缺少画布 width/height")
        width, height = float(width), float(height)
        blocks = []
        for j, b in enumerate(raw.get("blocks") or [], 1):
            if not isinstance(b, dict):
                raise ValueError(f"第 {i} 页第 {j} 个内容块不是对象")
            font = b.get("font_size")
            blocks.append({
                "id": str(b.get("id") or f"block-{j}"),
                "role": str(b.get("role") or "other"),
                "y_top": _require(b, "y_top", i, j),
                "y_bottom": _require(b, "y_bottom", i, j),
                "x_left": float(b.get("x_left", 0) or 0),
                "x_right": float(b.get("x_right", width) or width),
                "font_size": float(font) if font is not None else None,
                "text": str(b.get("text") or ""),
                "background": bool(b.get("background", False)),
            })
        reasons = []
        for r in raw.get("whitespace_reasons") or []:
            if isinstance(r, dict) and r.get("y_top") is not None and r.get("y_bottom") is not None:
                reasons.append((float(r["y_top"]), float(r["y_bottom"]),
                                str(r.get("reason", ""))))
        pages.append({
            "id": str(raw.get("id") or f"page-{i}"),
            "board": detect_board(width, height, raw.get("board") or canvas.get("board")),
            "width": width,
            "height": height,
            "blocks": blocks,
            "whitespace_reasons": reasons,
        })
    if not pages:
        raise ValueError("测量 JSON 不含任何页")
    return pages


def _content_blocks(page: dict) -> list[dict]:
    """氛围/背景层（background: true）不计密度、贴边与溢出。"""
    return [b for b in page["blocks"] if not b["background"]]


def _violation(rule: str, code: str, severity: str, page: dict, element: str,
               measured: str, threshold: str, fix: str) -> dict:
    return {"rule": rule, "code": code, "severity": severity, "page": page["id"],
            "element": element, "measured": measured, "threshold": threshold, "fix": fix}


# ---------------------------------------------------------------------------
# 规则实现
# ---------------------------------------------------------------------------

def overflow_fix_ladder(px: float) -> str:
    """R1 修正阶梯（qa-checklist.md Overflow Correction Ladder 四档）。"""
    n = round(px)
    if n <= LADDER_TWEAK_MAX_PX:
        return (f"微调档（1-{LADDER_TWEAK_MAX_PX}px）：整体上移内容组或收紧一处"
                f"间距/内边距 20-{LADDER_TWEAK_MAX_PX}px，不删内容")
    if n <= LADDER_COMPACT_MAX_PX:
        return (f"压缩档（{LADDER_TWEAK_MAX_PX + 1}-{LADDER_COMPACT_MAX_PX}px）：收紧局部"
                "间距并压低一个内容块高度，尽量避免删文案")
    if n <= LADDER_REDUCE_MAX_PX:
        return (f"删减档（{LADDER_COMPACT_MAX_PX + 1}-{LADDER_REDUCE_MAX_PX}px）：适度缩小"
                "展示标题或压缩一个段落，再考虑删内容")
    return (f"换版式档（>{LADDER_REDUCE_MAX_PX}px）：切换更高容量版式，"
            "或有意合并/删除内容模块")


def check_overflow(page: dict) -> list[dict]:
    """R1：内容块超出画布边界（error 级）。"""
    width, height = page["width"], page["height"]
    out = []
    for b in _content_blocks(page):
        candidates = (
            ("底", b["y_bottom"] - height),
            ("顶", -b["y_top"]),
            ("右", b["x_right"] - width),
            ("左", -b["x_left"]),
        )
        worst = max(candidates, key=lambda t: t[1])
        if worst[1] > OVERFLOW_TOLERANCE_PX:
            out.append(_violation(
                "R1", "R1.overflow", SEVERITY_ERROR, page, b["id"],
                f"{worst[0]}边超出画布 {round(worst[1])}px",
                f"容差 ≤{OVERFLOW_TOLERANCE_PX}px",
                overflow_fix_ladder(worst[1])))
    return out


def check_min_font(page: dict) -> list[dict]:
    """R4：文字角色字号低于机读下限（warn 级）。"""
    out = []
    for b in _content_blocks(page):
        floor = MIN_FONT_PX.get(b["role"])
        size = b["font_size"]
        if floor is None or size is None:
            continue
        if size < floor:
            label = b["text"][:12] or b["id"]
            out.append(_violation(
                "R4", "R4.min_font", SEVERITY_WARN, page, b["id"],
                f"{b['role']}「{label}」{round(size)}px",
                f"≥{floor}px",
                "删文案而不是缩字号（components.md 最小可读字号）"))
    return out


def _band_occupancy(page: dict) -> tuple[list[float], list[int]]:
    """按内容块 y 覆盖构造像素行占用位图，返回（4 带占有率, 行位图）。"""
    rows_total = max(1, int(round(page["height"])))
    rows = [0] * rows_total
    for b in _content_blocks(page):
        top = max(0, int(math.floor(b["y_top"])))
        bottom = min(rows_total, int(math.ceil(b["y_bottom"])))
        for y in range(top, bottom):
            rows[y] = 1
    band_size = rows_total / DENSITY_BANDS
    occ = []
    for i in range(DENSITY_BANDS):
        lo = int(math.floor(i * band_size))
        hi = int(math.floor((i + 1) * band_size))
        span = max(1, hi - lo)
        occ.append(sum(rows[lo:hi]) / span)
    return occ, rows


def _empty_runs(rows: list[int]) -> list[tuple[int, int]]:
    runs, start = [], None
    for y, filled in enumerate(rows):
        if not filled and start is None:
            start = y
        elif filled and start is not None:
            runs.append((start, y))
            start = None
    if start is not None:
        runs.append((start, len(rows)))
    return runs


def _reason_coverage(reasons, start: int, end: int) -> float:
    """空白带被留白理由覆盖的比例（重叠区间先合并再计长）。"""
    spans = sorted((max(float(r[0]), start), min(float(r[1]), end)) for r in reasons)
    merged, covered = [], 0.0
    for lo, hi in spans:
        if hi <= lo:
            continue
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    for lo, hi in merged:
        covered += hi - lo
    return covered / max(1, end - start)


def check_band_density(page: dict) -> list[dict]:
    """R5：4 横带密度，仅 3:4（xhs）画板（qa-checklist.md 4-band check）。"""
    if page["board"] != "xhs":
        return []
    out = []
    occ, rows = _band_occupancy(page)
    total = sum(occ) / DENSITY_BANDS
    bands_text = " / ".join(f"{o * 100:.0f}%" for o in occ)
    if total < DENSITY_TOTAL_MIN:
        out.append(_violation(
            "R5", "R5.total", SEVERITY_WARN, page, "(bands)",
            f"总覆盖 {total * 100:.0f}%（各带 {bands_text}）",
            f"≥{round(DENSITY_TOTAL_MIN * 100 + 0.5)}%",
            "扩写内容（加台账行/边注列/证据行）或换更高容量版式；"
            "不缩画布、不加装饰填充"))
    rows_total = len(rows)
    limit = EMPTY_BAND_RATIO * rows_total
    for start, end in _empty_runs(rows):
        run_h = end - start
        if run_h <= limit:
            continue
        # 顶/底引导边距（合计 ≤15% 画布高）按上游 layout-recipes 密度硬规则
        # 本就低于单带 15% 上限，无需豁免分支；超出即要求 whitespace_reason。
        if _reason_coverage(page["whitespace_reasons"], start, end) >= REASON_OVERLAP_EXEMPT:
            continue
        out.append(_violation(
            "R5", "R5.empty_band", SEVERITY_WARN, page, f"y{start}-{end}",
            f"空白横带 {run_h}px（{run_h / rows_total * 100:.0f}% 画布高）",
            f"≤{round(EMPTY_BAND_RATIO * 100)}% 画布高或标注 whitespace_reason",
            "给出留白理由（hero 呼吸/单句论点/天地边距）或用该空间扩写相邻内容块"))
    for i in range(DENSITY_BANDS - 1):
        if occ[i] < ADJACENT_SPARSE_RATIO and occ[i + 1] < ADJACENT_SPARSE_RATIO:
            out.append(_violation(
                "R5", "R5.adjacent", SEVERITY_WARN, page, f"band{i + 1}-{i + 2}",
                f"第 {i + 1}+{i + 2} 带均稀（{occ[i] * 100:.0f}% / {occ[i + 1] * 100:.0f}%）",
                "相邻两带不得同低于 15% 占有率",
                "扩写正文内容或插入边注列，消除中段 >25% 空洞"))
            break
    return out


def check_visual_bounds(page: dict) -> list[dict]:
    """R8：视觉边界——贴边间距下限 + 底部留白上限/活跃高度（warn 级）。"""
    blocks = _content_blocks(page)
    if not blocks:
        return []
    width, height = page["width"], page["height"]
    board = page["board"]
    floor = EDGE_FLOOR_PX.get(board) or {k: EDGE_FLOOR_DEFAULT_PX for k in ("top", "side", "bottom")}
    top = min(b["y_top"] for b in blocks)
    bottom = max(b["y_bottom"] for b in blocks)
    left = min(b["x_left"] for b in blocks)
    right = max(b["x_right"] for b in blocks)
    out = []
    for name, gap, key in (("顶", top, "top"), ("底", height - bottom, "bottom"),
                           ("左", left, "side"), ("右", width - right, "side")):
        if gap < floor[key]:
            out.append(_violation(
                "R8", "R8.edge", SEVERITY_WARN, page, "(content-bbox)",
                f"内容距{name}边 {round(gap)}px",
                f"≥{floor[key]}px（{board} 安全区下限）",
                "内容组内收至安全区；有意出血需显式设计并另行标注"))
    bottom_gap = height - bottom
    limit = BOTTOM_GAP_LIMIT_PX.get(board)
    active_ratio = (bottom - top) / height if height else 0.0
    if limit is not None and bottom_gap > limit and active_ratio < ACTIVE_RATIO_MIN:
        out.append(_violation(
            "R8", "R8.bottom_gap", SEVERITY_WARN, page, "(content-bbox)",
            f"底部留白 {round(bottom_gap)}px；活跃高度 {active_ratio * 100:.0f}%",
            f"留白 ≤{limit}px 或活跃高度 ≥{round(ACTIVE_RATIO_MIN * 100)}%",
            "用实测空白扩最后一块或整体下移；防溢出修复后过度收紧"))
    return out


def check_title_gap(page: dict) -> list[dict]:
    """R9：标题与相邻内容块的垂直间距下限（warn 级）。"""
    blocks = _content_blocks(page)
    out = []
    for t in blocks:
        if t["role"] not in ("title", "local_title"):
            continue
        if t["role"] == "local_title":
            min_gap = LOCAL_TITLE_GAP_MIN_PX
        elif page["board"] == "wide":
            min_gap = WIDE_TITLE_GAP_MIN_PX
        else:
            min_gap = TITLE_GAP_MIN_PX
        t_width = max(1.0, t["x_right"] - t["x_left"])
        nearest = None
        for b in blocks:
            if b is t:
                continue
            gap = b["y_top"] - t["y_bottom"]
            if gap < TITLE_GAP_SKIP_OVERLAP_PX:
                continue
            b_width = max(1.0, b["x_right"] - b["x_left"])
            overlap = min(t["x_right"], b["x_right"]) - max(t["x_left"], b["x_left"])
            if overlap <= 0 or overlap / min(t_width, b_width) < TITLE_GAP_XOVERLAP_MIN:
                continue
            if nearest is None or gap < nearest[0]:
                nearest = (gap, b)
        if nearest and nearest[0] < min_gap:
            out.append(_violation(
                "R9", "R9.title_gap", SEVERITY_WARN, page, t["id"],
                f"标题底距下一块 {round(nearest[0])}px（→ {nearest[1]['id']}）",
                f"≥{min_gap}px",
                "先恢复标题下方计量间距，再考虑减文案或整体缩放"))
    return out


def run_rules(pages: list[dict]) -> list[dict]:
    """对全部页跑规则子集，返回违规清单（未排序，按页/规则顺序）。"""
    out = []
    for page in pages:
        out.extend(check_overflow(page))
        out.extend(check_min_font(page))
        out.extend(check_band_density(page))
        out.extend(check_visual_bounds(page))
        out.extend(check_title_gap(page))
    return out


# ---------------------------------------------------------------------------
# 报告与 CLI
# ---------------------------------------------------------------------------

def format_violation(v: dict) -> str:
    return (f"{v['rule']} | {v['severity']} | {v['page']}#{v['element']} | "
            f"{v['measured']} | {v['threshold']} | {v['fix']}")


def format_report(pages: list[dict], violations: list[dict], source: str) -> str:
    errors = [v for v in violations if v["severity"] == SEVERITY_ERROR]
    warns = [v for v in violations if v["severity"] == SEVERITY_WARN]
    rule_counts: dict[str, int] = {}
    for v in violations:
        rule_counts[v["rule"]] = rule_counts.get(v["rule"], 0) + 1
    lines = ["==== validate_visual_measure ====",
             f"来源: {source}"]
    boards = ", ".join(sorted({p["board"] for p in pages}))
    lines.append(f"画板: {boards} · 页 {len(pages)}")
    lines.append("-" * 40)
    by_page: dict[str, list[dict]] = {}
    for v in violations:
        by_page.setdefault(v["page"], []).append(v)
    for page in pages:
        page_v = by_page.get(page["id"], [])
        if not page_v:
            lines.append(f"[PASS] {page['id']} · {page['board']}")
            continue
        page_errors = [v for v in page_v if v["severity"] == SEVERITY_ERROR]
        tag = "[FAIL]" if page_errors else "[WARN]"
        lines.append(f"{tag} {page['id']} · {page['board']} · "
                     f"error {len(page_errors)} / warn {len(page_v) - len(page_errors)}")
        lines.extend(f"  {format_violation(v)}" for v in page_v)
    lines.append("-" * 40)
    rules_text = "  ".join(f"{r}={c}" for r, c in sorted(rule_counts.items()))
    lines.append(f"统计: 页 {len(pages)} · 违规 {len(violations)}"
                 f"（error {len(errors)} / warn {len(warns)}）" +
                 (f" · {rules_text}" if rules_text else ""))
    lines.append("规则: " + " · ".join(f"{k} {label}" for k, label in RULE_LABELS.items()))
    lines.append("退出码 1 仅 error 级；warn 为建议级（与上游 validator 口径一致）")
    return "\n".join(lines)


def load_measurements(path: str) -> object:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(f"测量 JSON 不存在: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"测量 JSON 解析失败: {exc}")


def run_rule_mode(data: object, source: str) -> int:
    pages = normalize_document(data)
    violations = run_rules(pages)
    print(format_report(pages, violations, source))
    if any(v["severity"] == SEVERITY_ERROR for v in violations):
        return EXIT_VIOLATION
    return EXIT_OK


def measure_html_with_playwright(html_path: str) -> object:
    from playwright.sync_api import sync_playwright

    url = Path(html_path).resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        try:
            ctx = browser.new_context(
                viewport={"width": 1400, "height": 1700}, device_scale_factor=1)
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(1200)
            return page.evaluate(JS_COLLECTOR)
        finally:
            browser.close()


def run_html_mode(html_path: str) -> int:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print(DEGRADE_BLOCK)
        return EXIT_DEGRADED
    try:
        doc = measure_html_with_playwright(html_path)
    except Exception as exc:  # 渲染环境问题（如未 install chromium）不抛 traceback
        print(f"渲染测量失败: {exc}")
        print("可先执行 playwright install chromium，或改用 --measurements 走纯规则态。")
        return EXIT_USAGE
    return run_rule_mode(doc, f"--html {html_path}（渲染测量态）")


USAGE = """用法:
  python3 scripts/validate_visual_measure.py --measurements <measurements.json>
      纯规则态：对测量结果 JSON 跑 R1/R4/R5/R8/R9（测试与 CI 主入口）。
  python3 scripts/validate_visual_measure.py --html <index.html>
      渲染测量态：真实渲染并自动收集每个 section.poster 的几何（需 playwright）。

测量 JSON 结构与全部阈值见脚本 docstring 或
leo-ppt-generator/references/social-card-specs.md 第六节。"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_visual_measure.py",
        description="社交卡片测量式视觉质检（纯规则态 + 可选渲染测量态）",
        add_help=True)
    parser.add_argument("--measurements", metavar="JSON", help="测量结果 JSON 路径（纯规则态）")
    parser.add_argument("--html", metavar="FILE", help="待渲染 HTML 路径（渲染测量态）")
    args = parser.parse_args(argv)

    if args.measurements and args.html:
        print("错误: --measurements 与 --html 互斥，只选一种模式", file=sys.stderr)
        return EXIT_USAGE
    if not args.measurements and not args.html:
        print(USAGE)
        print()
        print(DEGRADE_BLOCK)
        return EXIT_USAGE
    if args.measurements:
        try:
            data = load_measurements(args.measurements)
            return run_rule_mode(data, f"--measurements {args.measurements}")
        except ValueError as exc:
            # 载入与 schema 归一化同为输入错误：单行清晰失败，不抛 traceback
            print(f"错误: {exc}", file=sys.stderr)
            return EXIT_USAGE
    return run_html_mode(args.html)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
