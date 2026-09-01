#!/usr/bin/env python3
"""gpt-image2-ppt-skills 风格吸收迁移器（风格进货批 C1，全量模式）。

将外部源仓库 ``gpt-image2-ppt-skills/styles``（自声明 265 套 =
initial 10 + featured 22 + xiamulingzi 单页参考池 233）转换为 leo 风格库
资产：

- initial/featured 32 套完整套：md 提示词内 HEX 正则抽取 → color_palette、
  【禁止】清单 → negative_prompt、适用场景 → best_for、同名 .layouts.json
  版式摘要 → layout_patterns，经四重去重后净新增 12 个主风格 brief，写入
  ``references/styles/`` 既有 01/02/03 子目录；
- xiamulingzi 233 套单页池：不逐条入库，按确定性调色板规则家族化归并为
  7 个参考池（莫兰迪×3 / 朋克×2 / 科技×2），每池产出 1 个池代表 brief +
  1 份池内清单（登记源 ID / 原名 / 主色板 / 回指），全部写入新目录
  ``references/styles/14_参考池_gpt-image2/``（不计入 _INDEX 主风格口径，
  最小破坏计数结构；登记见池目录 00_README.md）。

四重去重纪律（C1 批合同）：

1. 概念 grep：概念已被 leo 现库覆盖 → 跳过并登记映射（``SKIP`` 表，20 个，
   initial 10 中 8 套与现库 swiss-grid/glass/sketch 系直接重叠）；
2. 同板指纹：color_palette + background 的 HEX 集合与全库相等即拒绝（R-66）；
3. audit 同族副本：name_ratio ≥0.62 且共享 ≥1 HEX，或 name_ratio ≥0.45 且
   jaccard ≥0.5，或 jaccard ≥0.6 —— 新增对（含新旧）聚簇即拒绝，保证
   audit 疑似同族簇数不恶化；
4. WCAG 文字锚：primary 判深浅底，合并锚点须有 ≥4.5:1 文字锚
   （lint_style_governance 同款逻辑）。

内置自检门（--check/--write 前置）另含：四角色 palette HEX 锚 + 身份字体
声明（lint_style_briefs WARNING 子集，新文件不得进白名单）、决策表与源
一致性（32 套恰好 keep|skip 一次）、池覆盖完整性（233 套每套恰好归入一池）。

用法::

    python3 scripts/intake_gpt_image2.py --check    # 只跑去重门与自检
    python3 scripts/intake_gpt_image2.py --write    # 生成 brief/清单（幂等覆盖）
    python3 scripts/intake_gpt_image2.py --report   # 输出吸收决策报告

退出码：0 = 通过/写入成功；2 = 自检失败或源/目标异常。
"""

from __future__ import annotations

import argparse
import colorsys
import difflib
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STYLES_ROOT = SKILL_DIR / "references" / "styles"
SOURCE_ROOT = Path("/Users/kuang/knowledge/ppt-github/gpt-image2-ppt-skills/styles")
POOL_DIR_REL = "14_参考池_gpt-image2"

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)
# Mirror of lint_style_briefs._FONT_IDENTITY_RE (single source: schema docs).
FONT_IDENTITY_RE = re.compile(
    r"思源|Noto|MiSans|HarmonyOS|鸿蒙|苹方|PingFang|华文|冬青|宋|黑体|楷体|仿宋|"
    r"小标宋|Source Han|Inter|Helvetica|Roboto|Arial|Georgia|Times|IBM Plex|"
    r"JetBrains|DIN|Avenir|Futura|Garamond|Baskerville|mono|等宽|Monospace|"
    r"霞鹜|LXGW|站酷|ZCOOL|Caveat|Nunito|Kalam",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Intake decisions for initial + featured (32 = 12 keep + 20 skip).
# keep fields: name (leo style name), subdir (under references/styles),
# vd (English visual_direction phrase), pairing (08 图片渲染 mate),
# font (optional typography identity fallback).
# ---------------------------------------------------------------------------
KEEP: dict[str, dict] = {
    # -- initial（2）--------------------------------------------------------
    "clean-tech-blue": {
        "name": "Stripe蓝白风", "subdir": "01_通用母版/科技数字",
        "vd": "Stripe-grade SaaS blue-white pitch deck, restrained violet and "
              "blue anchors on pure white, precise product-grade grid, airy "
              "startup fundraising clarity",
        "pairing": "扁平几何", "font": "思源黑体 / Inter"},
    "editorial-mono": {
        "name": "黑白杂志风", "subdir": "01_通用母版/设计流派",
        "vd": "Kinfolk-Monocle monochrome editorial, huge serif headlines on "
              "ivory paper, one restrained crimson accent, asymmetrical "
              "luxury whitespace with pull quotes and footnotes",
        "pairing": "金句衬线卡", "font": "思源宋体 / Georgia"},
    # -- featured（10）-------------------------------------------------------
    "abstract-art-showcase": {
        "name": "抽象艺术画册风", "subdir": "01_通用母版/艺术表现",
        "vd": "minimalist art-showcase editorial, brutalist sans mixed with "
              "delicate script, stark near-black text on off-white with a "
              "single olive accent, gallery portfolio restraint",
        "pairing": "编辑动作海报", "font": "思源黑体 Heavy / Futura"},
    "coal-industry-business-company-profile": {
        "name": "煤炭工业风", "subdir": "02_行业内容域/制造能源",
        "vd": "brutalist industrial corporate profile, strict tan-and-black "
              "palette, grainy gradient lighting, bold structural dividers, "
              "mining and heavy-industry gravitas",
        "pairing": "复古工业概念", "font": "思源黑体 Heavy / Inter"},
    "creative-agency": {
        "name": "珊瑚紫双色调风", "subdir": "01_通用母版/设计流派",
        "vd": "strict coral and deep purple duotone agency deck, oversized "
              "condensed typography, thin structural accents, monochrome "
              "image treatment, bold modern creative credentials",
        "pairing": "丝网印刷", "font": "思源黑体 Heavy / Futura"},
    "culinary-innovation": {
        "name": "高级料理杂志风", "subdir": "02_行业内容域/文旅餐饮",
        "vd": "fine-dining magazine editorial, generous negative space, tall "
              "vertical image crops, cream paper with near-black serif and "
              "muted olive accents, refined culinary innovation storytelling",
        "pairing": "生活方式产品照", "font": "思源宋体 / Georgia"},
    "economic-impact-of-coronavirus": {
        "name": "深蓝红新闻编辑风", "subdir": "01_通用母版/设计流派",
        "vd": "high-contrast news editorial, bold navy field with bright red "
              "and white, striking duotone image treatment, crisis-report "
              "information discipline",
        "pairing": "企业摄影", "font": "思源黑体 Heavy / Inter"},
    "fashion-business-consulting-toolkit-aesthetic": {
        "name": "时尚咨询工具包风", "subdir": "02_行业内容域/消费时尚",
        "vd": "brutalist fashion-consulting toolkit, light gray black white "
              "with stark yellow highlight, high-contrast sans hierarchy, "
              "trend-forecast editorial rigor",
        "pairing": "杂志编辑", "font": "思源黑体 Heavy / Inter"},
    "flowery": {
        "name": "有机渐变形风", "subdir": "01_通用母版/艺术表现",
        "vd": "vibrant organic blob gradients, oversized overlapping botanical "
              "shapes over deep purple ground, balanced by stark white "
              "geometric content panels, energetic creative coverage",
        "pairing": "水彩晕染", "font": "思源黑体 / Futura"},
    "investment-company-business-plan": {
        "name": "荧光黄商务风", "subdir": "01_通用母版/设计流派",
        "vd": "neon yellow on dark charcoal corporate statement, geometric "
              "color blocking with white breathing room, high-contrast "
              "investment-plan boldness",
        "pairing": "扁平几何", "font": "思源黑体 Heavy / Inter"},
    "meeting-agenda": {
        "name": "纸质文件夹拟物风", "subdir": "01_通用母版/设计流派",
        "vd": "tactile skeuomorphic paper file folders, realistic tab "
              "dividers with soft drop shadows, hand-labeled agenda cards, "
              "warm workshop-desk physicality",
        "pairing": "复古海报", "font": "LXGW 霞鹜文楷 / Kalam"},
    "mind-maps-workshop-professional": {
        "name": "深蓝极简工作坊风", "subdir": "01_通用母版/商务专业",
        "vd": "deep navy minimalist workshop canvas, oversized off-white "
              "typography with subtle geometric motifs, polished corporate "
              "strategy-session focus",
        "pairing": "瑞士极简", "font": "思源黑体 Light / Inter"},
}

# Skipped sets: concept already covered by an existing leo style (concept-level
# dedupe; palettes may differ, so these are not R-66 variants).
SKIP: dict[str, dict] = {
    # initial（8）：与现库直接重叠的经典美学
    "swiss-grid": {"leo": "瑞士网格风", "reason": "同概念已存在"},
    "gradient-glass": {"leo": "玻璃拟态风", "reason": "磨砂玻璃+柔渐变同概念已存在"},
    "hand-sketch": {"leo": "手绘白板风", "reason": "白板手绘/sketchnote 已覆盖"},
    "japanese-wabi": {"leo": "和纸柔光风", "reason": "日式极简米白+单一朱红已覆盖"},
    "risograph": {"leo": "里索印刷风", "reason": "Riso 双套色已覆盖(S1b)"},
    "vector-illustration": {"leo": "复古扁平插画风", "reason": "复古柔和矢量插画已覆盖"},
    "y2k-chrome": {"leo": "Y2K铬金属风", "reason": "同概念已存在(S1a)"},
    "dark-aurora": {"leo": "深色弥散风", "reason": "深空底+弧光+玻璃卡与深色弥散同族"},
    # featured（12）：概念已被现库吸收或源缺 HEX 锚（宁实勿虚）
    "college-candy-aesthetics-infographics": {
        "leo": "新粗野主义风", "reason": "糖果色新粗野与现库粗野/孟菲斯系重叠"},
    "data-science-consulting": {
        "leo": "数据智能风", "reason": "深蓝数据咨询概念已覆盖;源无 HEX 锚"},
    "eco-green-business-plan": {
        "leo": "环保绿动风", "reason": "鼠尾草绿极简商务已由环保绿动/雾感鼠尾草覆盖;源无 HEX 锚"},
    "final-year-project-thesis-defense": {
        "leo": "学术论文答辩风", "reason": "学术答辩家族已饱和"},
    "first-impressions": {
        "leo": "奶油温柔风", "reason": "蜜桃米色优雅极简与柔和治愈系重叠"},
    "formal-lavender-portfolio": {
        "leo": "求职作品集风", "reason": "淡紫作品集概念已覆盖;源无 HEX 锚"},
    "geometric-business": {"leo": "商务几何风", "reason": "同概念已存在"},
    "geometric-clinical-case": {
        "leo": "临床试验风", "reason": "包豪斯几何医学已由临床/冷蓝系覆盖;源无 HEX 锚"},
    "geometric-duotone-thesis": {
        "leo": "包豪斯风", "reason": "电蓝明黄原色几何与包豪斯原色系重叠;答辩域饱和"},
    "health-disparities-and-social-determinants-of-health-doctor-of-philosophy-phd-in-health-behavior-and-health-education": {
        "leo": "医疗学术风", "reason": "学术医学蓝桃色系已覆盖(医疗健康 18 套)"},
    "indigenous-cultures": {
        "leo": "写实摄影风", "reason": "全幅摄影人文叙事已覆盖;源无 HEX 锚"},
    "mindfulness-in-the-classroom-breathing-techniques": {
        "leo": "情绪疗愈色卡风", "reason": "正念粉彩有机形状与柔和治愈系重叠"},
}

# ---------------------------------------------------------------------------
# xiamulingzi reference pools. Pool assignment is deterministic over the
# source palette (see classify_pool): dark decks split first, then the
# warm/cool anchor majority. tech/punk groups only use the dark split.
# ---------------------------------------------------------------------------
POOLS: dict[str, dict] = {
    "莫兰迪暖调编辑池": {
        "group": "morandi", "key": "warm",
        "vd": "muted Morandi warm-earth editorial, grayed terracotta and "
              "olive blocks on warm paper, asymmetrical lookbook grids, "
              "quiet gallery-grade color restraint",
        "font": "思源黑体 / Helvetica"},
    "莫兰迪冷调编辑池": {
        "group": "morandi", "key": "cool",
        "vd": "muted Morandi cool-mist editorial, gray-blue and sage haze "
              "over off-white, soft structural geometry, calm editorial "
              "narrative",
        "font": "思源黑体 / Helvetica"},
    "莫兰迪深色雕塑池": {
        "group": "morandi", "key": "dark",
        "vd": "dark-sculptural Morandi, deep umber and slate fields with "
              "muted amber accents, heavy color blocking, moody premium "
              "editorial depth",
        "font": "思源黑体 Light / Inter"},
    "朋克深底撞色池": {
        "group": "punk", "key": "dark",
        "vd": "punk-cool dark-ground clash, black canvas with high-voltage "
              "red or acid accents, oversized gritty type, edgy "
              "street-fashion energy",
        "font": "思源黑体 Heavy / Futura"},
    "朋克白底撞色池": {
        "group": "punk", "key": "light",
        "vd": "punk-cool white-ground clash, crisp paper with shocking "
              "color strikes and rotated type, zine-cut boldness",
        "font": "思源黑体 Heavy / Futura"},
    "科技深底霓虹池": {
        "group": "tech", "key": "dark",
        "vd": "curated dark tech, near-black grounds with neon cyan violet "
              "or lime data accents, precise futuristic depth",
        "font": "思源黑体 Light / Inter"},
    "科技浅底净色池": {
        "group": "tech", "key": "light",
        "vd": "curated light tech, clean white grounds with one electric "
              "blue or signal accent, airy product-grade precision",
        "font": "思源黑体 / Inter"},
}

FONT_FALLBACK: dict[str, str] = {
    "morandi": "思源黑体 / Helvetica",
    "punk": "思源黑体 Heavy / Futura",
    "tech": "思源黑体 / Inter",
}


# ---------------------------------------------------------------------------
# Source parsing
# ---------------------------------------------------------------------------
def parse_sections(text: str) -> dict[str, str]:
    """Split a source md into {heading: body} (intro kept under ``_intro``)."""
    sections: dict[str, str] = {}
    current, buf = "_intro", []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            sections[current] = "\n".join(buf).strip()
            current, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    sections[current] = "\n".join(buf).strip()
    return sections


def _clean_desc(raw: str) -> str:
    """Some featured mds store the description as a python-list repr; the
    universal 来源说明 provenance line is noise for brief prose."""
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("来源说明")]
    raw = "\n".join(lines).strip()
    if raw.startswith("["):
        first = raw.splitlines()[0].rstrip()
        if first.endswith("]"):
            try:
                items = json.loads(first.replace("'", '"'))
                if isinstance(items, list):
                    raw = " ".join(str(x) for x in items) + raw[len(first):]
            except json.JSONDecodeError:
                pass
    sents = [s for s in re.split(r"(?<=[。.])", raw)
             if s.strip() and not s.strip().startswith("来源说明")]
    return "".join(sents).strip()


def _forbid_block(prompt_section: str) -> str:
    """Extract the 【禁止】 bullet block from the prompt-template section."""
    m = re.search(r"【禁止】\n(.*?)(?=\n【|\Z)", prompt_section, re.S)
    return m.group(1).strip() if m else ""


def parse_set(md_path: Path) -> dict:
    """Parse one source set (md + same-stem .layouts.json)."""
    text = md_path.read_text(encoding="utf-8")
    sections = parse_sections(text)
    prompt = sections.get("基础提示词模板", "")
    hexes: list[str] = []
    # Prefer the explicit 推荐配色 line; fall back to ordered md prose.
    rec = re.search(r"推荐配色：([^\n]+)", prompt)
    if rec:
        hexes = [h.upper() for h in HEX_RE.findall(rec.group(1))]
    if not hexes:
        hexes = [h.upper() for h in HEX_RE.findall(text)]
    try:
        layouts_doc = json.loads(
            md_path.with_suffix(".layouts.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        layouts_doc = {}
    theme = layouts_doc.get("theme") or {}
    palette_sidecar = [c.upper() for c in (theme.get("palette") or [])]
    layouts = layouts_doc.get("layouts") or []
    bg: list[str] = []
    for line in prompt.splitlines():
        if ("背景" in line or "底" in line) and HEX_RE.search(line):
            # Keep only the segment introducing the background (cut at the
            # text-color clause) so ink anchors do not leak into bg.
            seg = re.split(r"文字[：:]", line)[0]
            bg = [h.upper() for h in HEX_RE.findall(seg)]
            if bg:
                break
    name = sections.get("风格名称", md_path.stem).split(" / ")[0].strip()
    desc = _clean_desc(sections.get("风格描述", ""))
    # Design-token fonts (featured/xia) live in the 设计令牌 section.
    fonts = ""
    for line in sections.get("设计令牌", "").splitlines():
        if line.lstrip("- ").startswith("fonts:"):
            fonts = line.split("fonts:", 1)[1].strip()
            break
    if not fonts:
        m = re.search(r"## 字体\n(.*?)(?=\n## |\Z)", text, re.S)
        fonts = m.group(1).strip() if m else ""
    return {
        "id": md_path.stem,
        "group": md_path.parent.name,
        "name": name,
        "desc": desc,
        "sections": sections,
        "prompt": prompt,
        "hexes": list(dict.fromkeys(hexes)) or palette_sidecar,
        "palette_sidecar": palette_sidecar,
        "bg": bg,
        "fonts": fonts,
        "negative": _forbid_block(prompt),
        "scenes": sections.get("适用场景", ""),
        "layouts": [
            {
                "id": l.get("id", ""),
                "page_type": l.get("page_type", ""),
                "summary": l.get("summary", ""),
            }
            for l in layouts
        ],
        "anchors": [
            str(a) for a in (theme.get("identity_anchors") or [])
        ],
    }


def load_source(source: Path) -> dict[str, dict]:
    """Parse every set under initial/ + featured/ + xiamulingzi/."""
    packs: dict[str, dict] = {}
    for sub in ("initial", "featured", "xiamulingzi"):
        for md in sorted((source / sub).glob("*.md")):
            packs[md.stem] = parse_set(md)
    return packs


# ---------------------------------------------------------------------------
# Derivations (pure, unit-tested)
# ---------------------------------------------------------------------------
def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a: str, b: str) -> float:
    l1, l2 = _lum(a), _lum(b)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def pick_palette(hexes: list[str], extra: list[str] | None = None) -> dict[str, str]:
    """Assign the four color_palette roles deterministically.

    primary = darkest anchor among the first three distinct HEX (the title
    ink on light paper decks, the ground color on dark decks), secondary and
    accent = next anchors in source order, neutral = the compliant extreme
    anchor (darkest on light decks / lightest on dark decks) for the WCAG
    text-anchor gate.
    """
    unique = list(dict.fromkeys(hexes))
    if not unique:
        raise ValueError("no HEX anchors found")
    head = unique[:3]
    primary = min(head, key=_lum)
    rest = [h for h in unique if h != primary]
    secondary = rest[0] if rest else primary
    accent = rest[1] if len(rest) > 1 else rest[-1] if rest else primary
    pool = list(dict.fromkeys(hexes + (extra or [])))
    # Deck polarity comes from the background anchors when available (a
    # light paper deck can still carry a dark title ink as primary).
    deck_lum = sum(_lum(h) for h in (extra or [])) / len(extra) if extra else _lum(primary)
    neutral = max(pool, key=_lum) if deck_lum < 0.35 else min(pool, key=_lum)
    return {
        "primary": f"{primary}(主色/标题锚)",
        "secondary": f"{secondary}(辅助色)",
        "accent": f"{accent}(强调色)",
        "neutral": f"{neutral}(文字与中性锚)",
    }


def palette_anchors(brief_palette: dict, bg_hexes: list[str]) -> set[str]:
    src = json.dumps(brief_palette, ensure_ascii=False) + " ".join(bg_hexes)
    return {h.upper() for h in HEX_RE.findall(src)}


def text_anchor_ok(anchors: set[str], primary_hex: str) -> bool:
    bg = "#1A1A1A" if _lum(primary_hex) < 0.35 else "#FFFFFF"
    return any(_contrast(h, bg) >= 4.5 for h in anchors)


def negative_items(raw: str, limit: int = 5) -> list[str]:
    """Distill the 【禁止】 checklist into 3-5 imperative prompt items.

    Source lines are complete prohibitions already (Chinese 严禁/禁止 or
    English noun phrases); keep them verbatim minus the list dash. Skip the
    universal source-provenance line (every set carries it)."""
    items: list[str] = []
    for chunk in re.split(r"\n", raw):
        chunk = chunk.strip().lstrip("-").strip()
        if not chunk or "来源网站" in chunk or chunk in items:
            continue
        items.append(chunk)
    if len(items) < 3:
        items.extend(
            filler
            for filler in (
                "不要偏离该风格的字体/配色/质感约定",
                "不要堆砌与风格气质无关的装饰元素",
            )
            if filler not in items
        )
    return items[:limit]


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[。\n;；]", text) if p.strip()]
    return [re.sub(r"^[-–—\s]+", "", p) for p in parts]


def typography_pack(pack: dict, font_fallback: str) -> dict[str, str]:
    """Distill source font tokens into the brief typography contract."""
    sents = _sentences(pack["fonts"])
    title = next((s for s in sents if any(k in s.lower() for k in
                 ("heading", "title", "标题", "serif", "sans"))), sents[0] if sents else "")
    body = next((s for s in sents if "body" in s.lower() or "正文" in s), "")
    result = {
        "title": title or "",
        "body": body if body and body != title else "同族常规字重,行高 1.6-1.9",
        "labels": "小字号同族,适度字距,克制用色",
    }
    joined = " ".join(result.values())
    if not FONT_IDENTITY_RE.search(joined):
        result["title"] = f"{font_fallback};{title}" if title else font_fallback
    if not result["title"]:
        result["title"] = font_fallback
    return result


def layout_patterns(pack: dict, limit: int = 4) -> list[str]:
    """First composition sentence per distinct page type from layouts.json."""
    picked: list[str] = []
    seen_types: set[str] = set()
    for l in pack["layouts"]:
        ptype = l.get("page_type", "")
        if ptype in seen_types:
            continue
        seen_types.add(ptype)
        frag = _sentences(l.get("summary", ""))[0] if l.get("summary") else ""
        frag = frag.split(":")[-1].strip()
        # English layout summaries run longer than CJK ones before they say
        # anything useful; admit both lengths.
        if 6 <= len(frag) <= 110:
            picked.append(frag)
        if len(picked) >= limit:
            break
    if not picked:
        picked = ["大面积色块分区", "标题区 + 内容卡两层结构"]
    return picked


def _first_sentence(text: str, limit: int = 72) -> str:
    sents = _sentences(text)
    for s in sents:
        if len(s) <= limit:
            return s
    return sents[0][:limit].rstrip("，,、；;") + "…" if sents else ""


def build_aliases(pack: dict, keep_name: str) -> list[str]:
    zh_base = keep_name[:-1] if keep_name.endswith("风") and len(keep_name) > 2 else keep_name
    items = [zh_base, pack["name"], pack["id"]]
    out: list[str] = []
    for item in items:
        item = item.strip()
        if item and item not in out:
            out.append(item)
    return out[:7]


def build_brief(pack: dict, keep: dict) -> tuple[dict, list[str]]:
    """Build one main-style brief from a parsed set + KEEP row."""
    palette = pick_palette(pack["hexes"], pack["bg"] or None)
    bg_hexes = pack["bg"][:3]
    bg_desc = "→".join(bg_hexes) if bg_hexes else "以 primary/neutral 锚定"
    anchors = ", ".join(pack["hexes"][:4])
    scenes = pack["scenes"].replace("、", "/").replace("\n", " ")
    best_for = _first_sentence(pack["desc"], 60)
    if best_for:
        best_for = f"{best_for};适合{scenes[:80]}" if "适合" not in best_for else (
            f"{best_for}{';' + scenes[:80] if scenes else ''}"
        )
    else:
        best_for = f"适合{scenes[:100]}"
    page_types = [l["page_type"] for l in pack["layouts"]]
    brief = {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": keep["name"],
        "aliases": build_aliases(pack, keep["name"]),
        "best_for": best_for,
        "visual_direction": keep["vd"],
        "canvas": {
            "aspect_ratio": "16:9",
            "background": bg_desc,
            "composition": _first_sentence(pack["layouts"][0]["summary"] if pack["layouts"] else "", 96)
                          or "色块分区 + 网格对齐",
            "density": "low-to-medium, 保持风格留白节奏",
        },
        "color_palette": {
            **palette,
            "rule": f"锚点 {anchors};{_first_sentence(pack['desc'], 56)}",
        },
        "typography": typography_pack(pack, keep.get("font", "思源黑体")),
        "layout_patterns": layout_patterns(pack),
        "layout_usage_rule": (
            f"版式骨架 {'/'.join(dict.fromkeys(page_types)) or 'cover/section/content/closing'}"
            ";按版式骨架排布,同 deck 内封面/收尾构图呼应"
        ),
        "visual_elements": {
            "allowed": _first_sentence(pack["layouts"][1]["summary"] if len(pack["layouts"]) > 1 else "", 60)
                        or "风格化色块与图形",
            "avoid": ";".join(negative_items(pack["negative"], limit=3)),
        },
        "rendering_constraints": [
            *negative_items(pack["negative"], limit=3),
            "色板锚点以 brief HEX 为准,不漂移;文案准确,不虚构标识",
        ],
        "negative_prompt": negative_items(pack["negative"]),
        "reference": f"gpt-image2-ppt-skills · styles/{pack['group']}/{pack['id']}.md",
    }
    return brief, bg_hexes


# ---------------------------------------------------------------------------
# Pool classification (deterministic)
# ---------------------------------------------------------------------------
def classify_pool(hexes: list[str], group: str) -> str:
    """Deterministic pool key for one xia set.

    The distilled palettes are background-first (layouts.json theme.palette
    convention), so polarity = luminance of the first anchor: dark grounds
    (<0.45, catching muted mid-dark Morandi bases) split first; otherwise
    the warm/cool saturated-anchor majority decides (ties -> warm, the pool
    majority for muted palettes). tech/punk groups only use dark/light.
    """
    if not hexes:
        return "light"

    dark = _lum(hexes[0]) < 0.45
    if group in ("punk", "tech") or dark:
        return "dark" if dark else "light"

    def hsv(hex_color: str) -> tuple[float, float]:
        r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
        h, s, _ = colorsys.rgb_to_hsv(r, g, b)
        return h * 360, s

    warm = cool = 0
    for c in hexes:
        hue, sat = hsv(c)
        if sat > 0.25 and (hue < 70 or hue > 330):
            warm += 1
        elif sat > 0.25 and 150 < hue < 270:
            cool += 1
    return "cool" if cool > warm else "warm"


def pool_for(hexes: list[str], group: str) -> str:
    for pool_name, spec in POOLS.items():
        if spec["group"] == group and spec["key"] == classify_pool(hexes, group):
            return pool_name
    raise KeyError(f"no pool for group={group}")


def _mean_rgb(hexes: list[str]) -> tuple[float, float, float]:
    vals = []
    for c in hexes:
        vals.append(tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)))
    n = len(vals)
    return (sum(v[0] for v in vals) / n, sum(v[1] for v in vals) / n,
            sum(v[2] for v in vals) / n)


def pick_pool_representative(members: list[dict]) -> dict:
    """Member whose mean RGB is closest to the pool centroid (deterministic
    tiebreak: source id lexical order)."""
    if len(members) == 1:
        return members[0]
    means = {m["id"]: _mean_rgb(m["hexes"]) for m in members}
    centroid = (
        sum(v[0] for v in means.values()) / len(means),
        sum(v[1] for v in means.values()) / len(means),
        sum(v[2] for v in means.values()) / len(means),
    )

    def dist(rgb: tuple[float, float, float]) -> float:
        return sum((a - b) ** 2 for a, b in zip(rgb, centroid))

    return min(members, key=lambda m: (dist(means[m["id"]]), m["id"]))


def build_pool_brief(pool_name: str, rep: dict, size: int) -> tuple[dict, list[str]]:
    """Build the pool-representative brief from the representative set."""
    spec = POOLS[pool_name]
    hexes = rep["palette_sidecar"] or rep["hexes"]
    palette = pick_palette(hexes, rep["bg"] or None)
    bg_hexes = rep["bg"][:3]
    bg_desc = "→".join(bg_hexes) if bg_hexes else hexes[-1] if hexes else "以 neutral 锚定"
    anchors = ", ".join(hexes[:4])
    group_label = {"morandi": "莫兰迪系", "punk": "朋克酷风 FG11", "tech": "精选科技风"}[spec["group"]]
    best_for = (
        f"{group_label}单页参考池代表(池内 {size} 套,池代表可整池选用);"
        f"{_first_sentence(rep['desc'], 60)}"
    )
    brief = {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": pool_name,
        "aliases": [pool_name[:-1], group_label.split(" ")[0],
                    f"linzi-{spec['group']}", rep["id"]],
        "best_for": best_for,
        "visual_direction": spec["vd"],
        "canvas": {
            "aspect_ratio": "16:9",
            "background": bg_desc,
            "composition": _first_sentence(rep["layouts"][0]["summary"] if rep["layouts"] else "", 96)
                          or "色块分区 + 网格对齐",
            "density": "low-to-medium, 保持池系留白节奏",
        },
        "color_palette": {
            **palette,
            "rule": f"锚点 {anchors};{group_label}池代表色板,池内变体见同名 .清单.md",
        },
        "typography": typography_pack(rep, FONT_FALLBACK[spec["group"]]),
        "layout_patterns": layout_patterns(rep),
        "layout_usage_rule": "版式骨架沿用池代表;同池成员构图可互换,保持锚点与网格",
        "visual_elements": {
            "allowed": _first_sentence(rep["layouts"][1]["summary"] if len(rep["layouts"]) > 1 else "", 60)
                        or "风格化色块与图形",
            "avoid": ";".join(negative_items(rep["negative"], limit=3)),
        },
        "rendering_constraints": [
            *negative_items(rep["negative"], limit=3),
            "色板锚点以池代表 HEX 为准,不漂移;文案准确,不虚构标识",
        ],
        "negative_prompt": negative_items(rep["negative"]),
        "reference": f"gpt-image2-ppt-skills · styles/xiamulingzi/{rep['id']}.md"
                     f"(设计师 @夏目玲子 单页参考池,本池 {size} 套)",
    }
    return brief, bg_hexes


# ---------------------------------------------------------------------------
# Dedupe / audit gates (isomorphic to intake_ohmy)
# ---------------------------------------------------------------------------
def load_existing_briefs(styles_root: Path) -> list[tuple[str, str, dict]]:
    entries: list[tuple[str, str, dict]] = []
    for p in sorted(styles_root.rglob("*.md")):
        m = JSON_BLOCK_RE.search(p.read_text(encoding="utf-8"))
        if not m:
            continue
        try:
            brief = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(brief, dict) and "style_name" in brief:
            entries.append((str(p.relative_to(styles_root)), brief["style_name"], brief))
    return entries


def fingerprint(brief: dict) -> frozenset[str]:
    src = json.dumps(brief.get("color_palette", {}), ensure_ascii=False) + str(
        brief.get("canvas", {}).get("background", "")
    )
    return frozenset(h.upper() for h in HEX_RE.findall(src))


def normalize_name(name: str) -> str:
    stripped = name.strip()
    for suffix in ("风格", "风", "池"):
        if stripped.endswith(suffix) and len(stripped) > len(suffix):
            return stripped[: -len(suffix)]
    return stripped


def audit_family_pair(name_a: str, fp_a: frozenset, name_b: str, fp_b: frozenset) -> bool:
    """Mirror of audit_style_families suspected-family rule."""
    if not fp_a or not fp_b:
        return False
    ratio = difflib.SequenceMatcher(
        None, normalize_name(name_a), normalize_name(name_b)
    ).ratio()
    shared = fp_a & fp_b
    jaccard = len(shared) / len(fp_a | fp_b)
    if ratio >= 0.62 and shared:
        return True
    if ratio >= 0.45 and jaccard >= 0.5:
        return True
    return jaccard >= 0.6


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def render_markdown(brief: dict, classification: str, scenes: list[str],
                    reference: str) -> str:
    lines = [
        f"# {brief['style_name']}",
        "",
        f"**分类:** {classification}",
        "",
        "**适用场景:**",
    ]
    lines += [f"- {s}" for s in scenes[:5]] or ["- 通用演示"]
    lines += [
        "",
        "**可参考来源:**",
        f"- {reference}",
        "",
        "**GPT-Image-2 风格 Brief:**",
        "```json",
        json.dumps(brief, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def render_pool_inventory(pool_name: str, members: list[dict], rep_id: str) -> str:
    """Pool inventory: every original set registered with a back-reference."""
    lines = [
        f"# {pool_name} · 池内清单",
        "",
        f"> 参考池代表 brief: [`{pool_name}.md`](./{pool_name}.md)"
        f"(代表成员 `{rep_id}`,确定性最贴近池心)。池内 {len(members)} 套均为"
        " gpt-image2-ppt-skills `styles/xiamulingzi/` 单页蒸馏风格(设计师"
        " @夏目玲子),只登记抽象视觉规律;启用时以代表 brief 的色板/字体/"
        "版式骨架为锚,可按本清单回源查询任意成员的原始布局摘要。",
        "",
        "| 源 ID | 原名 | 主色板 | 一句话描述 |",
        "|---|---|---|---|",
    ]
    for m in members:
        pal = " ".join((m["palette_sidecar"] or m["hexes"])[:5])
        desc = m["desc"].replace("|", "/")[:72]
        name = m["name"].replace("|", "/")[:48]
        lines.append(f"| `{m['id']}` | {name} | {pal} | {desc} |")
    lines.append("")
    return "\n".join(lines)


def render_pool_readme(pools: dict[str, dict]) -> str:
    lines = [
        "# 14_参考池_gpt-image2",
        "",
        "> gpt-image2-ppt-skills `styles/xiamulingzi/` 233 套单页参考池的家族化",
        "> 归并目录(C1 批)。每池 = 1 个池代表 brief(可整池选用的独立风格)",
        "> + 1 份同名 `.清单.md`(登记全部成员源 ID/原名/主色板)。本目录",
        "> **不计入 _INDEX.md 的 JSON 风格 brief 口径**(lint_style_index 的",
        "> BRIEF_DIRS 不含 14_),也不进视觉风格配对主表——最小破坏计数",
        "> 结构;选风格时可经 `_INDEX.md` 参考池节或直接点名池名/成员源 ID。",
        "",
        "| 池 | 归并键 | 池内套数 | 代表成员 |",
        "|---|---|---|---|",
    ]
    for pool_name, info in pools.items():
        lines.append(
            f"| **{pool_name}** | {POOLS[pool_name]['group']}/{POOLS[pool_name]['key']} "
            f"| {info['size']} | `{info['rep_id']}` |"
        )
    lines += [
        "",
        "归并规则(确定性,见 `scripts/intake_gpt_image2.py` 的 classify_pool):",
        "底色锚(色板首位)亮度 <0.45 → 深色池;否则按饱和锚的暖/冷多数归池(平局归暖)。",
        "punk/tech 组仅按深浅二分。重跑 `--write` 幂等覆盖本目录全部产物。",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run(packs: dict[str, dict], styles_root: Path, *, write: bool
        ) -> tuple[list[str], int, dict]:
    problems: list[str] = []
    report: dict = {"written": 0, "pools": {}}

    full_ids = {p for p, pack in packs.items() if pack["group"] in ("initial", "featured")}
    decided = set(KEEP) | set(SKIP)
    if decided != full_ids:
        missing = full_ids - decided
        extra = decided - full_ids
        if missing:
            problems.append(f"intake_table_stale: 完整套未决策 {sorted(missing)}")
        if extra:
            problems.append(f"intake_table_stale: 决策表引用不存在源 {sorted(extra)}")

    # ---- build main briefs -------------------------------------------------
    generated: dict[str, tuple[dict, Path, dict, list[str]]] = {}
    for src_id, keep in sorted(KEEP.items()):
        pack = packs.get(src_id)
        if pack is None:
            problems.append(f"intake_table_stale: KEEP 引用源 {src_id} 不存在")
            continue
        try:
            brief, bg_hexes = build_brief(pack, keep)
        except ValueError as exc:
            problems.append(f"palette_unparsed: {src_id}: {exc}")
            continue
        path = styles_root / keep["subdir"] / f"{keep['name']}.md"
        generated[src_id] = (brief, path, pack, bg_hexes)

    # ---- pool assignment ----------------------------------------------------
    xia = [p for p in packs.values() if p["group"] == "xiamulingzi"]
    assignments: dict[str, list[dict]] = {name: [] for name in POOLS}
    for pack in xia:
        hexes = pack["palette_sidecar"] or pack["hexes"]
        try:
            assignments[pool_for(hexes, "morandi" if "morandi" in pack["id"]
                                 else "punk" if "punk" in pack["id"] else "tech")].append(pack)
        except KeyError as exc:
            problems.append(f"pool_unassigned: {pack['id']}: {exc}")
    for pool_name, members in assignments.items():
        if not members:
            problems.append(f"pool_empty: {pool_name} 无成员")
    if sum(len(v) for v in assignments.values()) != len(xia):
        problems.append(
            f"pool_coverage: 233 套应全部归池,实际归类 {sum(len(v) for v in assignments.values())}"
        )

    pool_generated: dict[str, tuple[dict, Path, dict, list[str]]] = {}
    for pool_name, members in sorted(assignments.items()):
        rep = pick_pool_representative(members)
        brief, bg_hexes = build_pool_brief(pool_name, rep, len(members))
        path = styles_root / POOL_DIR_REL / f"{pool_name}.md"
        pool_generated[pool_name] = (brief, path, rep, bg_hexes)
        report["pools"][pool_name] = {"size": len(members), "rep_id": rep["id"]}

    all_generated = {**generated, **pool_generated}

    # ---- idempotency: own targets are destinations, not library history ----
    own_targets = {str(t[1]) for t in all_generated.values()}
    existing = [
        (rel, name, brief)
        for rel, name, brief in load_existing_briefs(styles_root)
        if str(styles_root / rel) not in own_targets
    ]

    # ---- Gate 1: role anchors + identity font (lint WARNING subset) --------
    for src_id, (brief, path, pack, bg_hexes) in sorted(all_generated.items()):
        for role in ("primary", "secondary", "accent", "neutral"):
            if not HEX_RE.search(brief["color_palette"][role]):
                problems.append(f"role_no_hex: {brief['style_name']}.{role}")
        typo = brief["typography"]
        if not FONT_IDENTITY_RE.search(" ".join(str(v) for v in typo.values())):
            problems.append(f"typography_no_identity: {brief['style_name']}")
        # Gate 4: WCAG text anchor.
        anchors = palette_anchors(brief["color_palette"], bg_hexes)
        primary_hex = HEX_RE.search(brief["color_palette"]["primary"]).group(0)
        if not text_anchor_ok(anchors, primary_hex):
            problems.append(f"text_anchor_missing: {brief['style_name']}")

    # ---- Gate 2: family_duplicate across the merged library ----------------
    seen: dict[frozenset, str] = {}
    for rel, name, brief in existing:
        fp = fingerprint(brief)
        if fp:
            seen.setdefault(fp, name)
    for src_id, (brief, path, pack, bg_hexes) in sorted(all_generated.items()):
        fp = fingerprint(brief)
        if not fp:
            continue
        prior = seen.get(fp)
        if prior and prior != brief["style_name"]:
            problems.append(
                f"family_duplicate: {brief['style_name']} 与 {prior} 色板指纹相同"
            )
        seen.setdefault(fp, brief["style_name"])

    # ---- Gate 3: audit suspected-family regression ---------------------------
    new_entries = [
        (brief["style_name"], fingerprint(brief)) for brief, _, _, _ in all_generated.values()
    ]
    existing_top = [(name, fingerprint(brief)) for _, name, brief in existing]
    for i, (na, fa) in enumerate(new_entries):
        for nb, fb in new_entries[i + 1:]:
            if audit_family_pair(na, fa, nb, fb):
                problems.append(f"audit_cluster_risk: 新增对 {na} × {nb} 会聚簇")
        for nb, fb in existing_top:
            if audit_family_pair(na, fa, nb, fb):
                problems.append(f"audit_cluster_risk: {na} × 既有 {nb} 会聚簇")

    # ---- name uniqueness -----------------------------------------------------
    names = [b["style_name"] for b, _, _, _ in all_generated.values()]
    if len(names) != len(set(names)):
        problems.append("name_collision: 新增 style_name 存在重复")

    if problems:
        return problems, 2, report

    if write:
        for src_id, (brief, path, pack, bg_hexes) in sorted(generated.items()):
            keep = KEEP[src_id]
            scenes = [s.strip() for s in re.split(r"[、,;,;。]|、", pack["scenes"]) if s.strip()]
            if not scenes:
                scenes = [pack["name"]]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                render_markdown(brief, keep["subdir"], scenes, brief["reference"]),
                encoding="utf-8",
            )
            report["written"] += 1
        for pool_name, (brief, path, rep, bg_hexes) in sorted(pool_generated.items()):
            members = assignments[pool_name]
            pool_root = styles_root / POOL_DIR_REL
            pool_root.mkdir(parents=True, exist_ok=True)
            path.write_text(
                render_markdown(
                    brief, f"{POOL_DIR_REL} · 参考池代表",
                    ["整池选用的池代表风格", "按池内清单回源查询任意成员布局摘要"],
                    brief["reference"],
                ),
                encoding="utf-8",
            )
            inv_path = path.with_name(f"{pool_name}.清单.md")
            inv_path.write_text(
                render_pool_inventory(pool_name, members, rep["id"]), encoding="utf-8"
            )
            report["written"] += 2
        (styles_root / POOL_DIR_REL / "00_README.md").write_text(
            render_pool_readme(report["pools"]), encoding="utf-8"
        )
    return [], 0, report


def build_report(packs: dict[str, dict], run_report: dict) -> str:
    lines = [
        "gpt-image2-ppt-skills 吸收决策(C1 全量模式):",
        f"  完整套 32 = 保留 {len(KEEP)} + 跳过 {len(SKIP)};",
        f"  单页池 233 → {len(POOLS)} 个参考池(共 {sum(v['size'] for v in run_report.get('pools', {}).values())} 套归池)。",
        "",
        "跳过映射(概念已有):",
    ]
    for d in sorted(SKIP):
        lines.append(f"  - {d} -> {SKIP[d]['leo']}({SKIP[d]['reason']})")
    lines.append("")
    lines.append("净新增主风格:")
    for d in sorted(KEEP):
        lines.append(f"  - {d}({KEEP[d]['name']}) -> {KEEP[d]['subdir']}")
    lines.append("")
    lines.append("参考池(代表成员):")
    for pool in sorted(run_report.get("pools", {})):
        info = run_report["pools"][pool]
        lines.append(f"  - {pool}: {info['size']} 套, 代表 {info['rep_id']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="gpt-image2-ppt-skills 吸收迁移器(C1)")
    parser.add_argument("--write", action="store_true", help="生成 brief/清单(幂等)")
    parser.add_argument("--check", action="store_true", help="只跑去重门与自检")
    parser.add_argument("--report", action="store_true", help="输出吸收决策报告")
    parser.add_argument("--source", default=str(SOURCE_ROOT), help="源 styles 目录覆盖")
    parser.add_argument("--styles-root", default=str(STYLES_ROOT),
                        help="目标 references/styles 覆盖")
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    if not source.is_dir():
        print(f"source missing: {source}", file=sys.stderr)
        return 2
    packs = load_source(source)

    problems, code, run_report = run(packs, Path(args.styles_root), write=args.write)
    if args.report:
        print(build_report(packs, run_report))
        return 0
    for item in problems:
        print(f"  ✗ {item}", file=sys.stderr)
    if code:
        print(f"intake gate FAILED ({len(problems)} problems)", file=sys.stderr)
        return 2
    action = "written" if args.write else "checked"
    print(
        f"intake OK ({action}): keep={len(KEEP)} skip={len(SKIP)} "
        f"pools={len(POOLS)} "
        f"members={sum(v['size'] for v in run_report['pools'].values())}"
    )
    if args.write:
        print(build_report(packs, run_report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
