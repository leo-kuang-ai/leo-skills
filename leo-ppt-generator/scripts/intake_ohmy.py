#!/usr/bin/env python3
"""oh-my-ppt 风格包吸收迁移器（风格进货批 S1a）。

将外部源仓库 ``oh-my-ppt``（arcsin1，manifest 快照 2026-06-20）的 74 个
风格包（SKILL.md 世界观 + style.json 双语元数据 + preview.html）转换为
leo 风格库 brief（markdown + GPT-Image-2 JSON 块），写入
``template-library/reference/sources/retired-styles-tree/styles/01_通用母版/`` 对应子目录。

配额与去重纪律（docs/plans/2026-08-31-006 进货批 S1a）：

- 概念已在 leo 现库（含并行批次已吸收的 slides_maker/Awesome 条目）
  → 跳过并登记映射（``SKIP`` 表，25 个）；
- 同板指纹（HEX 集合）几乎重合的源包 → 以 ``variant_of`` 归并（1 个）；
- 其余 49 个净新增，目标带 45-55。

迁移合同（计划「通用迁移合同」节）：brief 必含 style_name/best_for/
canvas 16:9/color_palette（HEX 锚）/aliases（双语 + 源目录名）/
negative_prompt（源「不要」清单提炼 3-5 条）；新增家族同步
``style_hard_rules.FAMILIES`` 与 ``_INDEX.md`` 分类（本脚本只产出 brief
文件与配对行素材，索引/家族表由维护者同步）。

内置自检门（--check/--write 前置）：

1. 四角色 palette 各含 #RRGGBB 锚点 + 身份字体声明（lint_style_briefs
   WARNING 子集——新文件不得进白名单）；
2. 文字对比锚（lint_style_governance 同款 WCAG 逻辑：primary 判深浅底，
   合并锚点须有 ≥4.5:1 文字锚）；
3. family_duplicate：新增指纹与全库指纹集合相等即拒绝（R-66）；
4. audit 同族判定副本（name_ratio ≥0.62 且共享 ≥1 HEX，或 name_ratio
   ≥0.45 且 jaccard ≥0.5，或 jaccard ≥0.6）：新增对（含新旧）聚簇即拒绝，
   保证 audit 疑似同族簇数不恶化。

用法::

    python3 scripts/intake_ohmy.py --check   # 只跑自检门与文件一致性
    python3 scripts/intake_ohmy.py --write   # 生成 brief（幂等覆盖同名）

退出码：0 = 通过/写入成功；2 = 自检失败或源/目标异常。
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STYLES_ROOT = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles")
SOURCE_ROOT = Path("/Users/kuang/knowledge/ppt-github/oh-my-ppt/resources/styles")

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
# Intake decisions. 74 source dirs = 49 keep + 25 skip.
# keep fields: name (override zh-derived name), subdir (under 01_通用母版),
# vd (English visual_direction phrase), pairing (08 图片渲染 mate),
# variant_of (optional R-66 attribution), font (optional typography fallback).
# ---------------------------------------------------------------------------
KEEP: dict[str, dict] = {
    # -- 终端配色（terminal palette family, 9） -----------------------------
    "arctic-cool": {"name": "北极冷风", "subdir": "终端配色",
                    "vd": "arctic-cool ice-blue data console, deep cyan panels, crisp "
                          "dashboard numerals, cold professional reporting look",
                    "pairing": "数字仪表盘", "font": "思源黑体 / Inter"},
    "catppuccin-latte": {"name": "Catppuccin拿铁风", "subdir": "终端配色",
                         "vd": "Catppuccin Latte pastel terminal theme, warm light "
                               "surface, soft lavender-blue text accents, gentle "
                               "developer-friendly code slides",
                         "pairing": "数字仪表盘"},
    "catppuccin-mocha": {"name": "Catppuccin摩卡风", "subdir": "终端配色",
                         "vd": "Catppuccin Mocha dark terminal theme, cozy deep-slate "
                               "surface, muted lavender/teal code accents, low-glare "
                               "developer aesthetic",
                         "pairing": "数字仪表盘"},
    "dracula": {"name": "Dracula紫风", "subdir": "终端配色",
                "vd": "Dracula classic dark theme, neon pink and lavender highlights "
                      "over charcoal panels, syntax-glow developer slides",
                "pairing": "数字仪表盘"},
    "gruvbox-dark": {"name": "Gruvbox暗风", "subdir": "终端配色",
                     "vd": "Gruvbox dark retro-groove terminal, earthy orange and "
                           "sand text on warm deep brown, vintage code-first layout",
                     "pairing": "数字仪表盘"},
    "nord": {"name": "北欧风", "subdir": "终端配色",
             "vd": "Nord polar dark theme, frost-blue accent over bluish slate "
                   "panels, restrained calm developer aesthetic",
             "pairing": "数字仪表盘", "font": "思源黑体 Light / Inter"},
    "rose-pine": {"name": "玫瑰松风", "subdir": "终端配色",
                  "vd": "Rosé Pine dawn-forest terminal palette, muted rose gold and "
                        "pine accents on soft dark base, gentle natural dev theme",
                  "pairing": "数字仪表盘"},
    "solarized-light": {"name": "日光浅风", "subdir": "终端配色",
                        "vd": "Solarized Light research terminal, warm cream paper "
                              "background with canonical accent hues, restrained "
                              "readable code aesthetic",
                        "pairing": "数字仪表盘"},
    "tokyo-night": {"name": "东京夜风", "subdir": "终端配色",
                    "vd": "Tokyo Night city-lights theme, cyan and blue glow over "
                          "deep night slate, modern nocturnal developer look",
                    "pairing": "数字仪表盘"},
    # -- 设计流派（design schools / editorial, 8） --------------------------
    "dopamine-clash": {"name": "多巴胺活力撞色风", "subdir": "设计流派",
                       "vd": "dopamine bright clash palette, saturated happy color "
                             "blocking, energetic playful juxtaposition, mood-boosting "
                             "creative deck",
                       "pairing": "扁平几何", "font": "思源黑体 Heavy / Futura"},
    "editorial-serif": {"name": "杂志衬线风", "subdir": "设计流派",
                        "vd": "serif editorial magazine layout, elegant headline "
                              "typography with generous margins, refined print feel",
                        "pairing": "杂志编辑", "font": "思源宋体 / Georgia"},
    "magazine-bold": {"name": "杂志大字风", "subdir": "设计流派",
                      "vd": "bold oversized serif magazine cover energy, amber accent "
                            "on cream paper, type-as-image hero statements",
                      "pairing": "杂志编辑", "font": "思源宋体 Heavy / Georgia"},
    "news-broadcast": {"name": "新闻播报风", "subdir": "设计流派",
                       "vd": "broadcast news lower-third energy, red accent bars on "
                             "white, heavy uppercase sans headline, breaking-news "
                             "information density",
                       "pairing": "扁平几何", "font": "思源黑体 Heavy / Inter"},
    "premium-color-blocking": {"name": "高级撞色风", "subdir": "设计流派",
                               "vd": "premium color blocking, confident large color "
                                     "fields with editorial restraint, gallery-grade "
                                     "contrast pairing",
                               "pairing": "扁平几何", "font": "思源黑体 / DIN"},
    "retro-tv": {"name": "复古电视风", "subdir": "设计流派",
                 "vd": "retro CRT television warm glow, amber screen tint, vintage "
                       "broadcast scanline mood, nostalgic handmade titling",
                 "pairing": "复古海报", "font": "思源宋体 / Georgia"},
    "sharp-mono": {"name": "锐利黑白风", "subdir": "设计流派",
                   "vd": "sharp black-and-white statement, ultra-heavy type with "
                         "brutal borders, zero color maximum contrast manifesto deck",
                   "pairing": "瑞士极简"},
    "y2k-chrome": {"name": "Y2K铬金属风", "subdir": "设计流派",
                   "vd": "Y2K chrome metallic, liquid silver gradients with holographic "
                         "violet-cyan highlights, millennium-futuristic pop gloss",
                   "pairing": "玻璃拟态", "font": "思源黑体 / Futura"},
    # -- 东方意蕴（chinese aesthetic, 10 incl. 1 variant） -------------------
    "amber-aurora": {"name": "国风暖阳风", "subdir": "东方意蕴",
                     "vd": "chinese-heritage sunset gradient, warm bean-purple fading "
                           "to honey-ochre glow, poetic healing oriental atmosphere",
                     "pairing": "水彩晕染"},
    "chinese-cream-blossom": {"name": "米白樱粉风", "subdir": "东方意蕴",
                              "variant_of": "凝脂杨妃风",
                              "vd": "chinese traditional cream-blossom palette, cherry "
                                    "pink over warm ivory paper, spring poem aesthetic",
                              "pairing": "水彩晕染"},
    "chinese-fresh-trio": {"name": "青绿湖蓝风", "subdir": "东方意蕴",
                           "vd": "chinese fresh trio palette, jade green and lake blue "
                                 "on mint paper, modern oriental clarity",
                           "pairing": "自然有机"},
    "chinese-pastel-spring": {"name": "春日嫩柳风", "subdir": "东方意蕴",
                              "vd": "chinese pastel spring palette, tender willow green "
                                    "and peach pink washes, soft seasonal oriental mood",
                              "pairing": "水彩晕染"},
    "chinese-porcelain-rose": {"name": "凝脂杨妃风", "subdir": "东方意蕴",
                               "vd": "chinese traditional named-color system, rose "
                                     "yangfei pink and warm gold on ivory porcelain "
                                     "paper, classical elegant branding",
                               "pairing": "水彩晕染"},
    "indigo-lotus": {"name": "青莲碧蓝风", "subdir": "东方意蕴",
                     "vd": "dreamy oriental indigo-lotus palette, cyan lotus blue with "
                           "soft violet mist, contemporary guofeng fantasy",
                     "pairing": "水彩晕染"},
    "ink-wash-jiangnan": {"name": "水墨江南风", "subdir": "东方意蕴",
                          "vd": "jiangnan ink-wash aesthetic, misty grey-black "
                                "brushwork with rain-washed negative space, poetic "
                                "water-town oriental minimalism",
                          "pairing": "水墨笔记"},
    "oriental-poetic-illustration": {"name": "东方意境插画风", "subdir": "东方意蕴",
                                     "vd": "oriental poetic illustration, soft "
                                           "mountain-mist scenery with classical "
                                           "motifs, narrative guofeng imagery",
                                     "pairing": "水彩晕染"},
    "palace-ink-red": {"name": "故宫墨红风", "subdir": "东方意蕴",
                       "vd": "new-chinese palace aesthetic, forbidden-city ink red "
                             "blocks with stone grey and rice-paper beige, restrained "
                             "oriental gravitas",
                       "pairing": "扁平几何", "font": "思源黑体 Heavy / 苹方"},
    "song-rain-poetic": {"name": "宋韵听雨风", "subdir": "东方意蕴",
                         "vd": "song-dynasty rain aesthetic, mist blue and tender "
                               "green with warm footnote gold, literati slow-life "
                               "poetic layout",
                         "pairing": "水彩晕染"},
    # -- 柔和治愈（soft healing, 9） ----------------------------------------
    "children-warm-orange": {"name": "童趣暖橙风", "subdir": "柔和治愈",
                             "vd": "children-friendly warm orange, sunny rounded "
                                   "shapes with soft contrast, joyful approachable "
                                   "family warmth",
                             "pairing": "矢量插画", "font": "圆润思源黑体 / Nunito"},
    "cream-pastel": {"name": "奶油温柔风", "subdir": "柔和治愈",
                     "vd": "cream pastel gentility, buttery warm neutrals with low "
                           "saturation accents, soft premium comforting mood",
                     "pairing": "水彩晕染", "font": "圆润思源黑体 / Nunito"},
    "dreamy-pink-gradient": {"name": "樱粉雾蓝风", "subdir": "柔和治愈",
                             "vd": "dreamy cherry-pink and mist-blue gradient, romantic "
                                   "poetic atmosphere with airy pastel depth",
                             "pairing": "水彩晕染", "font": "圆润思源黑体 / Nunito"},
    "healing-color-card": {"name": "情绪疗愈色卡风", "subdir": "柔和治愈",
                           "vd": "emotional healing color-card system, lavender warm-"
                                 "peach and mint swatches on soft paper, gentle "
                                 "psychological comfort layout",
                           "pairing": "水彩晕染"},
    "macaron-mist": {"name": "柔雾甜梦风", "subdir": "柔和治愈",
                     "vd": "macaron mist sweetness, mint pink coral and lavender "
                           "pastel fog, parisian dessert-shop delicacy",
                     "pairing": "矢量插画", "font": "圆润思源黑体 / Nunito"},
    "orange-sea": {"name": "晴橙落日海风", "subdir": "柔和治愈",
                   "vd": "sunny orange sunset-sea gradient, warm horizon glow with "
                         "refreshing summer warmth",
                   "pairing": "暖光场景", "font": "圆润思源黑体 / Nunito"},
    "sakura-soft-healing": {"name": "樱花治愈风", "subdir": "柔和治愈",
                            "vd": "sakura soft healing, pale cherry petals drifting on "
                                  "blush white, tender calming spring therapy",
                            "pairing": "水彩晕染", "font": "圆润思源黑体 / Nunito"},
    "sunset-warm": {"name": "日落暖风", "subdir": "柔和治愈",
                    "vd": "warm sunset tones, golden-hour gradient comfort with "
                          "soft apricot glow, cozy evening warmth",
                    "pairing": "暖光场景", "font": "圆润思源黑体 / Nunito"},
    "xiaohongshu-white": {"name": "小红书白风", "subdir": "柔和治愈",
                          "vd": "xiaohongshu lifestyle white, serif headline on clean "
                                "white canvas with warm red accents, collectible "
                                "everyday-life magazine feel",
                          "pairing": "杂志编辑", "font": "思源宋体 / Georgia"},
    # -- 夜空氛围（night-sky drama, 4） -------------------------------------
    "aurora": {"name": "极光风", "subdir": "夜空氛围",
               "vd": "aurora borealis gradient, luminous green-violet ribbons over "
                     "deep night sky, atmospheric spectacle backdrop",
               "pairing": "数字仪表盘", "font": "思源黑体 Light / Inter"},
    "gradient-cosmic": {"name": "梦幻星河风", "subdir": "夜空氛围",
                        "vd": "cosmic gradient drama, deep indigo night with golden "
                              "firework light, epic dreamlike high contrast",
                        "pairing": "数字仪表盘", "font": "思源黑体 Light / Inter"},
    "neon-haze": {"name": "深色弥散风", "subdir": "夜空氛围",
                  "vd": "dark diffused neon haze, blurred glow fields over deep "
                        "charcoal, ambient atmosphere-first backdrop",
                  "pairing": "数字仪表盘", "font": "思源黑体 Light / Inter"},
    "starlight-fireworks": {"name": "星火夜空风", "subdir": "夜空氛围",
                            "vd": "half starlight half fireworks, deep blue night "
                                  "counterpoint with festive orange-gold bursts",
                            "pairing": "暖光场景", "font": "思源黑体 Light / Inter"},
    # -- 质感专业（premium professional, 5） --------------------------------
    "burgundy-premium": {"name": "勃艮第红风", "subdir": "质感专业",
                         "vd": "burgundy premium, wine-red depth with refined serif "
                               "restraint, luxurious editorial gravitas",
                         "pairing": "杂志编辑", "font": "思源宋体 / Georgia"},
    "gold-ivory": {"name": "鎏金象牙风", "subdir": "质感专业",
                   "vd": "gold on ivory premium, gilded accents over warm ivory "
                         "paper, quiet-luxury gallery elegance",
                   "pairing": "杂志编辑", "font": "思源宋体 / Georgia"},
    "industrial-kaizen": {"name": "现代周报风", "subdir": "质感专业",
                          "vd": "kaizen industrial monochrome, strict table-and-form "
                                "report grid with zero decoration, modern operations "
                                "review discipline",
                          "pairing": "矢量插画", "font": "思源黑体 Semibold / Inter"},
    "olive-elegant": {"name": "橄榄奶白风", "subdir": "质感专业",
                      "vd": "olive and cream elegance, muted olive green on milky "
                            "white, understated mature premium taste",
                      "pairing": "矢量插画", "font": "思源黑体 / Inter"},
    "pitch-deck-vc": {"name": "风投路演风", "subdir": "质感专业",
                      "vd": "VC pitch deck white, oversized indigo numerals on clean "
                            "white, three-line-per-page bold investor storytelling",
                      "pairing": "瑞士极简", "font": "思源黑体 Heavy / Inter"},
    # -- 归入现有 艺术表现（+3） --------------------------------------------
    "hand-drawn-autumn": {"name": "手绘秋日手账风", "subdir": "艺术表现",
                          "vd": "hand-drawn autumn travel journal, marker sketches "
                                "with washi-tape and sticker collage, personal "
                                "notebook warmth",
                          "pairing": "手绘笔记", "font": "LXGW 霞鹜文楷 / Kalam"},
    "mint-fresh": {"name": "薄荷清新风", "subdir": "艺术表现",
                   "vd": "mint fresh premium green, cool herbal palette with airy "
                         "white space, refreshing modern nature look",
                   "pairing": "自然有机"},
    "mountain-green-literary": {"name": "山野葱郁风", "subdir": "艺术表现",
                                "vd": "mountain forest literary green, lush layered "
                                      "foliage tones with prose-style layout, nature "
                                      "essay aesthetic",
                                "pairing": "自然有机"},
    # -- 归入现有 科技数字（+1） --------------------------------------------
    "engineering-whiteprint": {"name": "工程白图风", "subdir": "科技数字",
                               "vd": "engineering whiteprint, precise blue line work "
                                     "on white drafting grid, mono-spaced technical "
                                     "documentation clarity",
                               "pairing": "工程蓝图"},
}

# Skipped packs: concept already covered by an existing leo style (palette
# fingerprints differ, so this is a concept-level dedupe, not R-66 variants).
SKIP: dict[str, dict] = {
    "academic-paper": {"leo": "学术期刊风", "reason": "学术论文浅色衬线概念已覆盖"},
    "bauhaus": {"leo": "包豪斯风", "reason": "同概念已存在"},
    "blue-white-chart": {"leo": "商务几何风", "reason": "蓝白图表商务概念已覆盖"},
    "blueprint": {"leo": "工程蓝图风", "reason": "同概念已存在(另有蓝晒图纸风)"},
    "chinese-ink-landscape": {"leo": "水墨禅意风", "reason": "与水墨江南风/水墨禅意风重叠,本批取水墨江南风"},
    "classic-duo-blue": {"leo": "稳重商务风", "reason": "米黄深蓝商务概念已覆盖"},
    "cobalt-sunshine": {"leo": "商务几何风", "reason": "明黄钴蓝专业系与蓝白图表同类"},
    "corporate-clean": {"leo": "清爽专业风", "reason": "同概念已存在"},
    "cyberpunk-neon": {"leo": "荧光高对比科技风", "reason": "深底霓虹高对冲家族已覆盖"},
    "dreamy-romance": {"leo": "樱粉雾蓝风", "reason": "梦幻浪漫治愈与 dreamy-pink-gradient 同类,取后者"},
    "glassmorphism": {"leo": "玻璃拟态风", "reason": "同概念已存在"},
    "handdrawn-watercolor": {"leo": "水彩晕染风", "reason": "同概念已存在"},
    "japanese-minimal": {"leo": "和纸柔光风", "reason": "日式极简已由并行批次吸收"},
    "memphis-pop": {"leo": "孟菲斯风", "reason": "同概念已存在(另有孟菲斯新潮风)"},
    "midcentury": {"leo": "中世纪现代风", "reason": "已由并行批次(slides_maker)吸收"},
    "minimal-white": {"leo": "极简风", "reason": "同概念已存在"},
    "neo-brutalism": {"leo": "新粗野主义风", "reason": "同概念已存在"},
    "rainbow-gradient": {"leo": "极光风", "reason": "泛彩虹渐变价值低于精选渐变系"},
    "soft-pastel": {"leo": "柔雾甜梦风", "reason": "柔和马卡龙与 macaron-mist 同类,取后者"},
    "splash-abstract": {"leo": "多巴胺活力撞色风", "reason": "泼彩多巴胺与 dopamine-clash 同类,取后者"},
    "starry-dust": {"leo": "星火夜空风", "reason": "星屑柔光与星火夜空/夜空系同类"},
    "summer-warm-color": {"leo": "日落暖风", "reason": "夏日暖色与 sunset-warm 同类,取后者"},
    "swiss-grid": {"leo": "瑞士网格风", "reason": "同概念已存在"},
    "terminal-green": {"leo": "终端命令行风", "reason": "已由并行批次(slides_maker)吸收"},
    "vaporwave": {"leo": "蒸汽波风", "reason": "同概念已存在"},
}

# R-66 variant bookkeeping: variants declared on their primary's brief.
VARIANT_NOTES = {
    "米白樱粉风": "樱粉置换杨妃红为主倾向,暖棕灰文字,同板春日叙事",
}

# Per-subdir typography fallback used only when the source prose carries no
# identity-font keyword (lint WARNING gate for new files).
FONT_FALLBACK: dict[str, str] = {
    "终端配色": "JetBrains Mono / 思源黑体 Mono 等宽",
    "设计流派": "思源宋体 / Georgia 衬线",
    "东方意蕴": "思源宋体 / 楷体",
    "柔和治愈": "思源黑体 / Nunito 圆润无衬线",
    "夜空氛围": "思源黑体 Light / Inter",
    "质感专业": "思源黑体 / Inter 无衬线",
    "艺术表现": "思源黑体 / Noto Sans SC",
    "科技数字": "JetBrains Mono / 思源黑体 Mono 等宽",
}


# ---------------------------------------------------------------------------
# Source parsing
# ---------------------------------------------------------------------------
def parse_sections(text: str) -> dict[str, str]:
    """Split a SKILL.md into {heading: body} (intro kept under ``_intro``)."""
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


def parse_pack(src_dir: Path) -> dict:
    meta = json.loads((src_dir / "style.json").read_text(encoding="utf-8"))
    skill_text = (src_dir / "SKILL.md").read_text(encoding="utf-8")
    sections = parse_sections(skill_text)
    color_sec = sections.get("配色", "")
    hexes = [h.upper() for h in HEX_RE.findall(color_sec)]
    if not hexes:
        # Fallback contract: preview.html inline CSS / :root custom props.
        preview = src_dir / "preview.html"
        if preview.exists():
            hexes = [h.upper() for h in HEX_RE.findall(preview.read_text(encoding="utf-8"))]
    bg: list[str] = []
    for sent in re.split(r"[。;；]", color_sec):
        if "背景" in sent or "底" in sent and "渐变" in sent:
            bg = [h.upper() for h in HEX_RE.findall(sent)]
            if bg:
                break
    preview_hexes: list[str] = []
    preview = src_dir / "preview.html"
    if preview.exists():
        # Extra anchor pool (text/edge colors often live only in preview CSS).
        preview_hexes = sorted({h.upper() for h in HEX_RE.findall(preview.read_text(encoding="utf-8"))})
    typography = sections.get("排版") or sections.get("字体") or ""
    negative = sections.get("不要") or sections.get("不要做") or ""
    return {
        "dir": src_dir.name,
        "zh": (meta.get("name") or {}).get("zh", src_dir.name),
        "en": (meta.get("name") or {}).get("en", src_dir.name),
        "category": meta.get("category", ""),
        "aliases": [a for a in meta.get("aliases", []) if a and a != src_dir.name],
        "style_case": meta.get("styleCase", ""),
        "description": meta.get("description", ""),
        "sections": sections,
        "hexes": hexes,
        "bg": bg,
        "preview_hexes": preview_hexes,
        "typography": typography,
        "negative": negative,
        "layout": sections.get("布局", ""),
        "scenes": sections.get("适合场景", ""),
    }


# ---------------------------------------------------------------------------
# Derivations (pure, unit-tested)
# ---------------------------------------------------------------------------
def derive_name(zh: str) -> str:
    """zh name -> leo style name: strip qualifier after '·', drop spaces,
    ensure the 风 suffix."""
    base = zh.split("·")[0].replace(" ", "").strip()
    if base.endswith("风格"):
        return base
    if base.endswith("风"):
        return base + "格" if len(base) <= 2 else base
    return base + "风"


def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a: str, b: str) -> float:
    l1, l2 = _lum(a), _lum(b)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def pick_palette(pack: dict) -> dict[str, str]:
    """Assign the four color_palette roles deterministically.

    primary = first HEX of the 配色 section (title anchor in oh-my-ppt
    convention), secondary = second, accent = third (fallback: last), and
    neutral = the darkest anchor on light decks / lightest on dark decks so
    the WCAG text-anchor gate always finds a compliant anchor.
    """
    hexes = pack["hexes"]
    if not hexes:
        raise ValueError(f"{pack['dir']}: no HEX anchors found")
    primary = hexes[0]
    secondary = hexes[1] if len(hexes) > 1 else hexes[0]
    accent = hexes[2] if len(hexes) > 2 else hexes[-1]
    pool = list(dict.fromkeys(hexes + pack["bg"] + pack.get("preview_hexes", [])))
    if _lum(primary) < 0.35:
        neutral = max(pool, key=_lum)
    else:
        # Light deck: darkest anchor wins (preview text colors qualify).
        neutral = min(pool, key=_lum)
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
    """Distill the 不要 checklist into 3-5 imperative prompt items.

    Source lines are already complete prohibitions («不要使用…»), so keep
    them verbatim (minus the list dash); only normalize separators."""
    items: list[str] = []
    for chunk in re.split(r"[\n;；]", raw):
        chunk = chunk.strip().lstrip("-").strip()
        if chunk:
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


def typography_pack(pack: dict, keep: dict) -> dict[str, str]:
    sents = _sentences(pack["typography"])
    title = next((s for s in sents if "标题" in s), sents[0] if sents else "")
    body = next((s for s in sents if "正文" in s), "")
    labels = next(
        (s for s in sents if any(k in s for k in ("标签", "数字", "引文", "副标题", "色名"))), ""
    )
    result = {
        "title": title or "",
        "body": body if body and body != title else "同族常规字重,行高 1.6-1.9",
        "labels": labels or "小字号同族,适度字距,克制用色",
    }
    # Identity-font gate mirrors lint: check the FINAL merged values, so an
    # identity keyword elsewhere in the source prose cannot mask a bare title.
    joined = " ".join(result.values())
    if not FONT_IDENTITY_RE.search(joined):
        fallback = keep.get("font") or FONT_FALLBACK.get(keep["subdir"], "思源黑体")
        result["title"] = f"{fallback};{title}" if title else fallback
    if not result["title"]:
        result["title"] = FONT_FALLBACK.get(keep["subdir"], "思源黑体")
    return result


def layout_patterns(pack: dict, limit: int = 4) -> list[str]:
    sents = _sentences(pack["layout"])
    picked: list[str] = []
    for s in sents:
        s = re.sub(r"^模拟|^以", "", s)
        frag = s.split("——")[0].strip()
        if 4 <= len(frag) <= 38:
            picked.append(frag)
        if len(picked) >= limit:
            break
    if not picked:
        picked = ["大面积色块分区", "标题区 + 内容卡两层结构"]
    return picked


def build_aliases(pack: dict, keep: dict) -> list[str]:
    zh_base = keep["name"]
    zh_base = zh_base[:-1] if zh_base.endswith("风") and len(zh_base) > 2 else zh_base
    items = [zh_base, pack["en"], *pack["aliases"], pack["dir"]]
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out[:7]


def _first_full_sentence(text: str, limit: int = 72) -> str:
    """First complete sentence of ``text``; never cut mid-word."""
    sents = _sentences(text)
    if not sents:
        return ""
    for s in sents:
        if len(s) <= limit:
            return s
    # Fall back to the longest sentence-boundary prefix that fits.
    return sents[0][:limit].rstrip("，,、；;") + "…"


def build_brief(pack: dict, keep: dict, *, variants_declared: list[str] | None = None) -> dict:
    palette = pick_palette(pack)
    bg_hexes = pack["bg"][:3]
    bg_desc = "→".join(bg_hexes) if bg_hexes else "以 primary/neutral 锚定"
    best_for = pack["style_case"].replace("、", "/") or "通用演示"
    best_for = f"{pack['description']};适合{best_for}"
    hexes = pack["hexes"]
    anchors = ", ".join(hexes[:4])
    rule_src = _first_full_sentence(pack["sections"].get("配色", ""))
    brief = {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": keep["name"],
        # R-66 convention: a merge primary's aliases ARE its variant names
        # (test_audit_style_families enforces set equality); bilingual source
        # aliases stay on non-merged briefs only.
        "aliases": (
            [v.split(":", 1)[0] for v in variants_declared]
            if variants_declared
            else build_aliases(pack, keep)
        ),
        "best_for": best_for,
        "visual_direction": keep["vd"],
        "canvas": {
            "aspect_ratio": "16:9",
            "background": f"{bg_desc}",
            "composition": _first_full_sentence(pack["layout"], limit=48) or "色块分区 + 网格对齐",
            "density": "low-to-medium, 保持风格留白节奏",
        },
        "color_palette": {**palette,
                          "rule": f"锚点 {anchors};{rule_src}" if rule_src else f"锚点 {anchors}"},
        "typography": typography_pack(pack, keep),
        "layout_patterns": layout_patterns(pack),
        "layout_usage_rule": (_sentences(pack["layout"]) or ["按版式骨架排布"])[0][:80],
        "visual_elements": {
            "allowed": _sentences(pack["layout"])[0][:60] if pack["layout"] else "风格化色块与图形",
            "avoid": ";".join(negative_items(pack["negative"], limit=3)),
        },
        "rendering_constraints": [
            *negative_items(pack["negative"], limit=3),
            "色板锚点以 brief HEX 为准,不漂移;文案准确,不虚构标识",
        ],
        "negative_prompt": negative_items(pack["negative"]),
        "reference": f"GitHub: arcsin1/oh-my-ppt · styles/{pack['dir']}",
    }
    if keep.get("variant_of"):
        brief["variant_of"] = keep["variant_of"]
    if variants_declared:
        brief["variants"] = variants_declared
    return brief, bg_hexes  # type: ignore[return-value]


def render_markdown(brief: dict, subdir: str, pack: dict) -> str:
    scenes = [s.strip() for s in re.split(r"[、,;,;]", pack["style_case"]) if s.strip()]
    if not scenes:
        scenes = [pack["en"]]
    lines = [
        f"# {brief['style_name']}",
        "",
        f"**分类:** 01_通用母版 · {subdir}",
        "",
        "**适用场景:**",
    ]
    lines += [f"- {s}" for s in scenes[:5]]
    lines += [
        "",
        "**可参考来源:**",
        f"- {brief['reference']}",
        "",
        "**GPT-Image-2 风格 Brief:**",
        "```json",
        json.dumps(brief, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dedupe / audit gates
# ---------------------------------------------------------------------------
def load_existing_briefs() -> list[tuple[str, str, dict]]:
    entries: list[tuple[str, str, dict]] = []
    for p in sorted(STYLES_ROOT.rglob("*.md")):
        m = JSON_BLOCK_RE.search(p.read_text(encoding="utf-8"))
        if not m:
            continue
        try:
            brief = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(brief, dict) and "style_name" in brief:
            entries.append((str(p.relative_to(STYLES_ROOT)), brief["style_name"], brief))
    return entries


def fingerprint(brief: dict) -> frozenset[str]:
    src = json.dumps(brief.get("color_palette", {}), ensure_ascii=False) + str(
        brief.get("canvas", {}).get("background", "")
    )
    return frozenset(h.upper() for h in HEX_RE.findall(src))


def normalize_name(name: str) -> str:
    stripped = name.strip()
    for suffix in ("风格", "风"):
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
# Main pipeline
# ---------------------------------------------------------------------------
def target_path(keep: dict) -> Path:
    return STYLES_ROOT / "01_通用母版" / keep["subdir"] / f"{keep['name']}.md"


def variants_by_primary() -> dict[str, list[str]]:
    """R-66 bookkeeping: {primary style_name: [variant style names]}."""
    out: dict[str, list[str]] = {}
    for keep in KEEP.values():
        if keep.get("variant_of"):
            out.setdefault(keep["variant_of"], []).append(keep["name"])
    return out


def variants_declaration(primary_name: str) -> list[str] | None:
    names = variants_by_primary().get(primary_name)
    if not names:
        return None
    return [f"{n}: {VARIANT_NOTES.get(n, '同板场景变体')}" for n in sorted(names)]


def run(packs: dict[str, dict], *, write: bool) -> tuple[list[str], int]:
    problems: list[str] = []
    written = 0

    if not SOURCE_ROOT.is_dir():
        return [f"source missing: {SOURCE_ROOT}"], 2

    # Idempotency: briefs written by a previous run of this very script are
    # destinations, not library history -- exclude them from the existing set.
    own_targets = {str(target_path(k)) for k in KEEP.values()}
    existing = [
        (rel, name, brief)
        for rel, name, brief in load_existing_briefs()
        if str(STYLES_ROOT / rel) not in own_targets
    ]
    existing_by_name = {name: (rel, brief) for rel, name, brief in existing}

    # Primary/variant bookkeeping for R-66 fields.
    generated: dict[str, tuple[dict, Path, dict]] = {}
    for src_id, keep in sorted(KEEP.items()):
        if src_id not in packs:
            problems.append(f"intake_table_stale: KEEP 引用源目录 {src_id} 不存在")
            continue
        pack = packs[src_id]
        try:
            brief, bg_hexes = build_brief(
                pack, keep, variants_declared=variants_declaration(keep["name"])
            )
        except ValueError as exc:
            problems.append(f"palette_unparsed: {exc}")
            continue
        generated[src_id] = (brief, target_path(keep), pack)

        # Gate 1: role anchors + identity font (lint WARNING subset).
        for role in ("primary", "secondary", "accent", "neutral"):
            if not HEX_RE.search(brief["color_palette"][role]):
                problems.append(f"role_no_hex: {keep['name']}.{role}")
        typo = brief["typography"]
        if not FONT_IDENTITY_RE.search(" ".join(str(v) for v in typo.values())):
            problems.append(f"typography_no_identity: {keep['name']}")
        # Gate 2: WCAG text anchor.
        anchors = palette_anchors(brief["color_palette"], bg_hexes)
        primary_hex = HEX_RE.search(brief["color_palette"]["primary"]).group(0)
        if not text_anchor_ok(anchors, primary_hex):
            problems.append(f"text_anchor_missing: {keep['name']}")

    # Gate 3: family_duplicate across the whole merged library. Pre-existing
    # fingerprints register silently (lint owns them); new briefs collide-check
    # against everything registered before them.
    seen: dict[frozenset, str] = {}
    for rel, name, brief in existing:
        fp = fingerprint(brief)
        if fp:
            seen.setdefault(fp, name)
    for src_id, (brief, path, pack) in sorted(generated.items()):
        fp = fingerprint(brief)
        if not fp:
            continue
        rel = str(path.relative_to(STYLES_ROOT))
        prior = seen.get(fp)
        if prior and prior != brief["style_name"]:
            problems.append(
                f"family_duplicate: {brief['style_name']}({rel}) 与 {prior} 色板指纹相同"
            )
        seen.setdefault(fp, brief["style_name"])

    # Gate 4: audit suspected-family regression (new-vs-all, new-vs-new).
    # Mirrors audit_style_families: variant_of briefs are not top-level and do
    # not participate in suspected-family pairing.
    new_entries = [
        (brief["style_name"], fingerprint(brief))
        for _, (brief, _, _) in generated.items()
        if not brief.get("variant_of")
    ]
    existing_top = [
        (name, fingerprint(brief))
        for _, name, brief in existing
        if not brief.get("variant_of")
    ]
    for i, (na, fa) in enumerate(new_entries):
        for nb, fb in new_entries[i + 1:]:
            if audit_family_pair(na, fa, nb, fb):
                problems.append(f"audit_cluster_risk: 新增对 {na} × {nb} 会聚簇")
        for nb, fb in existing_top:
            if audit_family_pair(na, fa, nb, fb):
                problems.append(f"audit_cluster_risk: {na} × 既有 {nb} 会聚簇")

    # Variant target integrity.
    for src_id, keep in KEEP.items():
        target = keep.get("variant_of")
        if target and target not in {k["name"] for k in KEEP.values()} and target not in existing_by_name:
            problems.append(f"variant_target_missing: {keep['name']} -> {target}")
        if target and target in existing_by_name:
            problems.append(f"variant_target_exists_outside: {keep['name']} -> {target} 非本批主风格")

    if problems:
        return problems, 2

    if write:
        for src_id, (brief, path, pack) in sorted(generated.items()):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                render_markdown(brief, KEEP[src_id]["subdir"], pack), encoding="utf-8"
            )
            written += 1
    return [], 0


def report(packs: dict[str, dict]) -> str:
    lines = [
        f"oh-my-ppt 吸收决策: 源包 {len(packs)} = 保留 {len(KEEP)}(含变体 "
        f"{sum(1 for k in KEEP.values() if k.get('variant_of'))}) + 跳过 {len(SKIP)}",
        "",
        "跳过映射(概念已有):",
    ]
    for d in sorted(SKIP):
        lines.append(f"  - {d} -> {SKIP[d]['leo']}({SKIP[d]['reason']})")
    lines.append("")
    lines.append("变体归并:")
    for d, keep in sorted(KEEP.items()):
        if keep.get("variant_of"):
            lines.append(f"  - {d}({keep['name']}) -> variant_of {keep['variant_of']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="oh-my-ppt 风格包吸收迁移器(S1a)")
    parser.add_argument("--write", action="store_true", help="生成 brief 文件(幂等)")
    parser.add_argument("--check", action="store_true", help="只跑去重门与自检")
    parser.add_argument("--report", action="store_true", help="输出吸收决策报告")
    parser.add_argument("--source", default=str(SOURCE_ROOT), help="源 styles 目录覆盖")
    args = parser.parse_args(argv)

    src = Path(args.source).resolve()
    packs = {d.name: parse_pack(d) for d in sorted(src.iterdir()) if d.is_dir()}

    if args.report:
        print(report(packs))
        return 0

    problems, code = run(packs, write=args.write)
    for item in problems:
        print(f"  ✗ {item}", file=sys.stderr)
    if code:
        print(f"intake gate FAILED ({len(problems)} problems)", file=sys.stderr)
        return 2
    action = "written" if args.write else "checked"
    print(
        f"intake OK ({action}): keep={len(KEEP)} skip={len(SKIP)} "
        f"variants={sum(1 for k in KEEP.values() if k.get('variant_of'))}"
    )
    if args.write:
        print(report(packs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
