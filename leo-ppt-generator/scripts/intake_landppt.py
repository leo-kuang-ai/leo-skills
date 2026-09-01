#!/usr/bin/env python3
"""LandPPT 模板吸收迁移器（风格进货批 S2a）。

将外部源仓库 ``LandPPT`` 的 25 个带标签完整 HTML 模板
（``template_examples/*.json``，``html_template`` 内嵌 CSS）按 S2a
「价值精选」口径转换为 leo 风格库 brief（markdown + GPT-Image-2 JSON 块）：

- **中式载体家族**（新子类 ``01_通用母版/中式载体``，3）：竹简 / 中式书卷 /
  宣纸——载体材质向（简 / 卷 / 纸的物理质感与装帧语言），与既有
  「东方意蕴」的色彩向子类正交；
- **印象派油画家族**（新子类 ``01_通用母版/印象派油画``，2）：莫奈 / 星月夜；
- 吉卜力手绘风（归入既有 ``艺术表现``，1）——2D 手绘动画场景主风格为
  现库缺口（08 轴「幻想动画」渲染已有，主风格层缺位）。

其余 19 个模板与现库概念重复（终端 / 赛博朋克 / 玻璃拟态 / 商务蓝白 /
日落橙 / 森林绿 / 答辩蓝白 / 素白极简等），按概念级去重跳过并登记映射
（``SKIP`` 表）——与 S1a ``intake_ohmy.SKIP`` 同纪律：色板指纹不同但概念
已覆盖时以概念为准（如 rainbow-gradient → 极光风先例）。

锚点来源纪律（source fidelity）：四角色 HEX 与 background 锚必须能在源
``html_template`` CSS 中找到出处——显式 ``#RRGGBB``、URL 编码 ``%23rrggbb``
（SVG data URI 装饰色）或 ``rgba(r,g,b,a>0.08)`` 解码三者之一；解析不到
即 ``anchor_unprovenanced`` 拒绝，防止迁移时手写漂移。

自检门（复用 ``intake_ohmy`` 的同构实现，importlib 加载共享语义；
S1a/S2a 门语义单一真值源）：

1. 四角色 palette 各含 #RRGGBB 锚点 + 身份字体声明（lint WARNING 子集）；
2. 文字对比锚（WCAG：primary 判深浅底，合并锚点须有 ≥4.5:1 文字锚）；
3. family_duplicate：新增指纹与全库指纹集合相等即拒绝（R-66）；
4. audit 同族判定副本（name_ratio ≥0.62 且共享 ≥1 HEX，或 name_ratio
   ≥0.45 且 jaccard ≥0.5，或 jaccard ≥0.6）：新增对（含新旧）聚簇即
   拒绝，保证 audit 疑似同族簇数不恶化。

用法::

    python3 scripts/intake_landppt.py --check   # 只跑自检门与文件一致性
    python3 scripts/intake_landppt.py --write   # 生成 brief（幂等覆盖同名）
    python3 scripts/intake_landppt.py --report  # 输出吸收决策报告

退出码：0 = 通过/写入成功；2 = 自检失败或源/目标异常。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STYLES_ROOT = SKILL_DIR / "references" / "styles"
SOURCE_ROOT = Path("/Users/kuang/knowledge/ppt-github/LandPPT/template_examples")

# Gate semantics shared with the S1a intake (single source of truth).
_spec = importlib.util.spec_from_file_location("intake_ohmy", SCRIPT_DIR / "intake_ohmy.py")
ohmy = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("intake_ohmy", ohmy)
_spec.loader.exec_module(ohmy)

HEX_RE = ohmy.HEX_RE
RGBA_RE = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([\d.]+)\s*)?\)"
)

# ---------------------------------------------------------------------------
# Intake decisions. 25 source files = 6 keep + 19 skip (concept dedupe).
# keep fields: name, subdir (under 01_通用母版), vd (English visual_direction),
# pairing (08 render mate), anchors (four color_palette roles with zh notes),
# bg (canvas background anchors), scenes, aliases, composition, layout,
# negatives, typo (title/body/labels), best_for note.
# ---------------------------------------------------------------------------
KEEP: dict[str, dict] = {
    # -- 中式载体（chinese physical carriers, 3） ----------------------------
    "竹简风.json": {
        "name": "竹简风", "subdir": "中式载体",
        "vd": "chinese bamboo-slip chronicle carrier, vertical reed-brown slip "
              "panels bound by cord lines over warm tan paper texture, ancient "
              "archival layout",
        "pairing": "水墨笔记",
        "anchors": {
            "primary": "#8B4513(竹褐主色/标题锚)",
            "secondary": "#E8D5B5(简牍米)",
            "accent": "#A52A2A(编绳朱砂)",
            "neutral": "#1C1917(墨字)",
        },
        "bg": ["#F5E5C5", "#E8D5B5"],
        "scenes": ["传统文化", "历史人文", "经典诵读", "博物展陈"],
        "aliases": ["竹简", "简牍", "bamboo slip"],
        "composition": "纵向简条分区,标题横排大字居上,内容以简牍条列承载",
        "layout": [
            "纵向简条分区,标题区横排大字居上",
            "内容卡为简牍条,条间以编绳线索分隔",
            "要点用褐底浅字条列,强调点朱砂小块",
            "页脚以卷次编号收尾",
        ],
        "negatives": [
            "不要现代渐变霓虹或玻璃拟态面板",
            "不要冷色蓝紫主导,保持竹褐暖调",
            "不要无纹理纯白平底,保留简牍质感",
        ],
        "typo": {
            "title": "标题用 ZCOOL 小薇或宋体衬系,竹褐墨色,气势古拙",
            "body": "正文用思源宋体,行距宽松",
            "labels": "小字用宋体或楷体,适度字距",
        },
        "best_for": "竹简的颜色和纹理,浅米色与淡褐色纵向渐变;适合传统文化/历史人文/经典诵读",
    },
    "中式书卷风.json": {
        "name": "中式书卷风", "subdir": "中式载体",
        "vd": "chinese handscroll carrier, paper sheet flanked by wooden roller "
              "rods with ink-wash ruled lines, quiet classical reading layout",
        "pairing": "水墨笔记",
        "anchors": {
            "primary": "#4A3C2B(卷面墨褐/标题锚)",
            "secondary": "#F7F3E9(书卷纸白)",
            "accent": "#D9534F(朱红钤印)",
            "neutral": "#383028(卷轴深褐)",
        },
        "bg": ["#383028", "#F7F3E9"],
        "scenes": ["古典文学", "文化讲堂", "诗词雅集", "品牌国风叙事"],
        "aliases": ["书卷", "卷轴", "手卷", "chinese scroll"],
        "composition": "左右卷轴杆 + 中央纸面,上下留白,栏线古典排版",
        "layout": [
            "左右卷轴杆 + 中央纸面的横向卷轴构图",
            "标题区带下栏线,正文以栏线分隔",
            "强调点用朱红钤印小块",
            "引文用竖排或缩进古典块",
        ],
        "negatives": [
            "不要高饱和现代撞色",
            "不要几何硬阴影卡片,保持纸面平整",
            "不要无衬线粗黑大标题",
        ],
        "typo": {
            "title": "标题用思源宋体大字,配 Georgia 衬线副题",
            "body": "正文思源宋体,栏线内排行",
            "labels": "标签用宋体小字,朱红点缀",
        },
        "best_for": "模拟卷轴的边框和水墨质感,沉静典雅的阅读体验;适合古典文学/文化讲堂/诗词雅集",
    },
    "宣纸风.json": {
        "name": "宣纸风", "subdir": "中式载体",
        "vd": "xuan rice-paper carrier, fibrous warm-white sheet with faint ink "
              "bleed and soft ochre mist-blue corner glows, literati blank-space "
              "layout",
        "pairing": "水墨笔记",
        "anchors": {
            "primary": "#F4F1EA(宣纸米/底色锚)",
            "secondary": "#FDFAF3(暖宣白)",
            "accent": "#C8A064(暖赭晕)",
            "neutral": "#2C2C2C(墨字)",
        },
        "bg": ["#FDFAF3"],
        "scenes": ["水墨艺术", "文人雅集", "茶道养生", "冥想疗愈"],
        "aliases": ["宣纸", "rice paper", "xuan paper"],
        "composition": "大面积留白 + 墨字呼吸,细边小圆角容器,角落光晕",
        "layout": [
            "大留白居中或偏轴构图,文字为画面主体",
            "内容容器细边框小圆角,半透明宣纸底",
            "角落暖赭/雾蓝光晕点缀",
            "要点以墨点或细线引导",
        ],
        "negatives": [
            "不要厚重色块或深底",
            "不要高对比荧光强调",
            "不要拥挤排版,必须保持留白",
        ],
        "typo": {
            "title": "标题用楷体大字,竖排或横排皆宜",
            "body": "正文用宋体墨色,行距呼吸",
            "labels": "楷体小字,克制用色",
        },
        "best_for": "传统宣纸的水墨质感,典雅而富有变化;适合水墨艺术/文人雅集/茶道养生",
    },
    # -- 印象派油画（impressionist oil painting, 2） ------------------------
    "莫奈风.json": {
        "name": "莫奈风", "subdir": "印象派油画",
        "vd": "monet impressionist oil wash, flowing pastel blue-pink-gold "
              "gradient canvas with visible brush turbulence, dreamy light-filled "
              "composition",
        "pairing": "水彩晕染",
        "anchors": {
            "primary": "#A1C4FD(雾蓝笔触/标题锚)",
            "secondary": "#FBC2EB(樱粉晕)",
            "accent": "#FDDB92(暖金光)",
            "neutral": "#2C3A47(深青灰字)",
        },
        "bg": ["#E4D8C8", "#A1C4FD", "#C2E9FB", "#FDDB92", "#FBC2EB"],
        "scenes": ["艺术赏析", "文化活动", "品牌美学", "情感叙事"],
        "aliases": ["莫奈", "Monet", "impressionist", "印象派"],
        "composition": "全幅流动渐变 + 半透明磨砂白卡承载文字",
        "layout": [
            "全幅印象派渐变背景,内容置于半透明白卡",
            "标题衬线大字,金色光晕强调",
            "卡片大圆角软阴影,轻玻璃质感",
            "图文分区以柔和色带过渡",
        ],
        "negatives": [
            "不要硬边几何与锐利阴影",
            "不要单色平涂,保持笔触渐变",
            "不要深黑大底",
        ],
        "typo": {
            "title": "标题用 Georgia/Garamond 衬线,光影渐变着色",
            "body": "正文 Georgia + 思源宋体",
            "labels": "衬线小字,金色点缀",
        },
        "best_for": "油画笔触动态背景与光影文字,印象派艺术风格;适合艺术赏析/文化活动/品牌美学",
    },
    "星月夜风.json": {
        "name": "星月夜风", "subdir": "印象派油画",
        "vd": "van gogh starry night oil swirl, deep ultramarine sky with molten "
              "gold star spirals and expressive impasto brushwork, dreamlike "
              "night drama",
        "pairing": "水彩晕染",
        "anchors": {
            "primary": "#0B2A54(群青夜空/标题锚)",
            "secondary": "#4A90E2(星夜蓝)",
            "accent": "#F9D71C(熔金星芒)",
            "neutral": "#E0E6F1(月光白字)",
        },
        "bg": ["#010410", "#03102A", "#0B2A54"],
        "scenes": ["艺术赏析", "夜间活动", "情感表达", "创意提案"],
        "aliases": ["星月夜", "梵高", "Starry Night", "Van Gogh"],
        "composition": "深夜群青渐变 + 切角内容面板 + 金色星芒强调",
        "layout": [
            "深夜蓝渐变底 + 切角多边形内容面板",
            "标题配金渐变分隔线,星芒点缀",
            "文字浅色高对比,群青底金色数字",
            "装饰性笔触涡旋置于角落负空间",
        ],
        "negatives": [
            "不要白天浅底或办公白",
            "不要粉色系柔化,保持群青金对冲",
            "不要扁平无纹理色块",
        ],
        "typo": {
            "title": "标题用楷体手写艺术感,金渐变着色",
            "body": "正文浅白无衬线,群青底高对比",
            "labels": "手写体小字,星芒符号引导",
        },
        "best_for": "梵高《星月夜》的流动笔触与强烈色彩对比,梦幻而具情感张力;适合艺术赏析/夜间活动/情感表达",
    },
    # -- 归入现有 艺术表现（+1） --------------------------------------------
    "吉卜力风.json": {
        "name": "吉卜力手绘风", "subdir": "艺术表现",
        "vd": "ghibli hand-painted animation scenery, warm nostalgic watercolor "
              "fields with teal-green brush titles and sage botanical margins, "
              "gentle storybook calm",
        "pairing": "幻想动画",
        "anchors": {
            "primary": "#2C5D63(森青标题锚)",
            "secondary": "#A3B8A1(鼠尾草绿)",
            "accent": "#8FBC8F(叶绿点缀)",
            "neutral": "#4A443D(暖褐文字)",
        },
        "bg": ["#FDFAF3"],
        "scenes": ["自然教育", "儿童内容", "治愈叙事", "品牌温情"],
        "aliases": ["吉卜力", "Ghibli", "宫崎骏"],
        "composition": "纸纹底 + 角落手绘植物装饰 + 温暖叙事排版",
        "layout": [
            "纸纹底 + 角落植物/星光手绘装饰",
            "标题手写体青绿色,下衬双线",
            "内容区卡片奶油底圆角,柔和阴影",
            "图文以横向场景带编排",
        ],
        "negatives": [
            "不要锐利科技感线条",
            "不要高饱和荧光色",
            "不要深黑大底",
        ],
        "typo": {
            "title": "标题用 Segoe Print 手写感,森青着色",
            "body": "正文 Georgia/思源宋体,暖褐色",
            "labels": "圆润小字,克制用色",
        },
        "best_for": "温暖治愈的吉卜力动画手绘风格,自然气息与童话感;适合自然教育/儿童内容/治愈叙事",
    },
}

# Skipped packs: concept already covered by an existing leo style (concept-level
# dedupe, same discipline as intake_ohmy.SKIP).
SKIP: dict[str, dict] = {
    "Toy风.json": {"leo": "童趣暖橙风", "reason": "玩具彩色卡通风概念已覆盖,源描述仅词元"},
    "中国风.json": {"leo": "水墨禅意风", "reason": "泼墨水墨概念已覆盖(另有水墨江南风)"},
    "五彩斑斓的黑.json": {"leo": "荧光高对比科技风", "reason": "黑底霓虹镭射渐变概念已覆盖"},
    "商务.json": {"leo": "稳重商务风", "reason": "深色蓝调商务概念已覆盖"},
    "大气红.json": {"leo": "党政红风格", "reason": "大气红概念已覆盖"},
    "拟态风.json": {"leo": "新拟态风", "reason": "软 UI 拟态概念已覆盖"},
    "日落大道.json": {"leo": "日落暖风", "reason": "日落橙黄渐变概念已覆盖(S1a sunset-warm)"},
    "星月蓝.json": {"leo": "星月夜风", "reason": "同族蓝金星夜,并入本批星月夜风,不另立条目"},
    "森林绿.json": {"leo": "山野葱郁风", "reason": "森林绿清新概念已覆盖"},
    "模糊玻璃.json": {"leo": "玻璃拟态风", "reason": "液体玻璃概念已覆盖"},
    "清新笔记.json": {"leo": "手绘秋日手账风", "reason": "生活文艺暖调笔记概念已覆盖"},
    "清新风.json": {"leo": "清爽专业风", "reason": "蓝白清新概念已覆盖"},
    "科技风.json": {"leo": "暗黑科技风", "reason": "青色深底科技概念已覆盖"},
    "简约答辩风.json": {"leo": "学术论文答辩风", "reason": "蓝白大学答辩概念已覆盖"},
    "素白风.json": {"leo": "极简风", "reason": "素白极简概念已覆盖"},
    "终端风.json": {"leo": "终端命令行风", "reason": "同概念已存在(S1b terminal)"},
    "赛博朋克风.json": {"leo": "荧光高对比科技风", "reason": "赛博霓虹概念已覆盖"},
    "速度黄.json": {"leo": "新粗野主义风", "reason": "明黄黑高对比能量语言同类,源描述仅词元"},
    "饺子风.json": {"leo": "温暖手工风", "reason": "食物暖棕治愈概念已覆盖,源描述仅词元"},
}


# ---------------------------------------------------------------------------
# Source parsing
# ---------------------------------------------------------------------------
def source_anchors(css: str) -> set[str]:
    """Every HEX provably present in the CSS: explicit hex, URL-encoded
    ``%23hex`` (SVG data-URI decoration), and decoded ``rgba()`` with
    alpha > 0.08 (faint washes still carry hue identity)."""
    text = css.replace("%23", "#")
    found = {h.upper() for h in HEX_RE.findall(text)}
    for r, g, b, a in RGBA_RE.findall(text):
        if a == "" or float(a) > 0.08:
            found.add(f"#{int(r):02X}{int(g):02X}{int(b):02X}")
    return found


def parse_pack(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    css = data.get("html_template", "")
    return {
        "file": path.name,
        "template_name": data.get("template_name", path.stem),
        "description": data.get("description", ""),
        "tags": data.get("tags", []),
        "css": css,
        "anchors": source_anchors(css),
    }


# ---------------------------------------------------------------------------
# Brief derivation (pure, unit-tested)
# ---------------------------------------------------------------------------
def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_brief(keep: dict, pack: dict) -> tuple[dict, list[str]]:
    anchors = keep["anchors"]
    bg_hexes = keep["bg"]
    bg_desc = "→".join(bg_hexes)
    rule = (
        f"锚点 {', '.join(re.findall(HEX_RE, v)[0] for v in anchors.values())};"
        f"来源:LandPPT html_template CSS 实测 token;{pack['description'] or keep['best_for']}"
    )
    brief = {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": keep["name"],
        "aliases": _dedupe(
            [keep["name"], *keep["aliases"], pack["file"].removesuffix(".json")]
        ),
        "best_for": keep["best_for"],
        "visual_direction": keep["vd"],
        "canvas": {
            "aspect_ratio": "16:9",
            "background": f"{bg_desc} ({keep['name']}底)",
            "composition": keep["composition"],
            "density": "low-to-medium, 保持风格留白节奏",
        },
        "color_palette": {**anchors, "rule": rule},
        "typography": dict(keep["typo"]),
        "layout_patterns": list(keep["layout"]),
        "layout_usage_rule": keep["layout"][0],
        "visual_elements": {
            "allowed": keep["composition"],
            "avoid": ";".join(keep["negatives"][:2]),
        },
        "rendering_constraints": [
            *keep["negatives"],
            "色板锚点以 brief HEX 为准,不漂移;文案准确,不虚构标识",
        ],
        "negative_prompt": list(keep["negatives"]),
        "reference": f"GitHub: LandPPT · template_examples/{pack['file']}",
    }
    return brief, bg_hexes


def render_markdown(brief: dict, subdir: str, pack: dict) -> str:
    lines = [
        f"# {brief['style_name']}",
        "",
        f"**分类:** 01_通用母版 · {subdir}",
        "",
        "**适用场景:**",
    ]
    lines += [f"- {s}" for s in (_scenes_of(brief) or ["通用演示"])[:5]]
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


def _scenes_of(brief: dict) -> list[str]:
    raw = brief["best_for"].rsplit("适合", 1)[-1]
    return [s for s in re.split(r"[/、]", raw) if s.strip()]


def target_path(keep: dict) -> Path:
    return STYLES_ROOT / "01_通用母版" / keep["subdir"] / f"{keep['name']}.md"


# ---------------------------------------------------------------------------
# Gates + pipeline (mirror of intake_ohmy.run, shared semantics)
# ---------------------------------------------------------------------------
def run(packs: dict[str, dict], *, write: bool) -> tuple[list[str], int]:
    problems: list[str] = []
    written = 0

    if not SOURCE_ROOT.is_dir():
        return [f"source missing: {SOURCE_ROOT}"], 2

    own_targets = {str(target_path(k)) for k in KEEP.values()}
    existing = [
        (rel, name, brief)
        for rel, name, brief in ohmy.load_existing_briefs()
        if str(STYLES_ROOT / rel) not in own_targets
    ]

    generated: dict[str, tuple[dict, Path, dict]] = {}
    for src_id, keep in sorted(KEEP.items()):
        if src_id not in packs:
            problems.append(f"intake_table_stale: KEEP 引用源文件 {src_id} 不存在")
            continue
        pack = packs[src_id]
        brief, bg_hexes = build_brief(keep, pack)
        generated[src_id] = (brief, target_path(keep), pack)

        # Gate 0: source-fidelity -- every anchor must trace back to the CSS.
        provenance = pack["anchors"]
        for role, value in brief["color_palette"].items():
            if role == "rule":
                continue
            for hexm in HEX_RE.findall(value):
                if hexm.upper() not in provenance:
                    problems.append(
                        f"anchor_unprovenanced: {keep['name']}.{role} {hexm} 不在源 CSS token 中"
                    )
        for hexm in bg_hexes:
            if hexm.upper() not in provenance:
                problems.append(f"anchor_unprovenanced: {keep['name']} background {hexm} 无出处")

        # Gate 1: role anchors + identity font (lint WARNING subset).
        for role in ("primary", "secondary", "accent", "neutral"):
            if not HEX_RE.search(brief["color_palette"][role]):
                problems.append(f"role_no_hex: {keep['name']}.{role}")
        typo = brief["typography"]
        if not ohmy.FONT_IDENTITY_RE.search(" ".join(str(v) for v in typo.values())):
            problems.append(f"typography_no_identity: {keep['name']}")

        # Gate 2: WCAG text anchor.
        anchors = ohmy.palette_anchors(brief["color_palette"], bg_hexes)
        primary_hex = HEX_RE.search(brief["color_palette"]["primary"]).group(0)
        if not ohmy.text_anchor_ok(anchors, primary_hex):
            problems.append(f"text_anchor_missing: {keep['name']}")

    # Gate 3: family_duplicate across the whole merged library.
    seen: dict[frozenset, str] = {}
    for rel, name, brief in existing:
        fp = ohmy.fingerprint(brief)
        if fp:
            seen.setdefault(fp, name)
    for src_id, (brief, path, pack) in sorted(generated.items()):
        fp = ohmy.fingerprint(brief)
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
    new_entries = [(b["style_name"], ohmy.fingerprint(b)) for _, (b, _, _) in generated.items()]
    existing_top = [
        (name, ohmy.fingerprint(brief))
        for _, name, brief in existing
        if not brief.get("variant_of")
    ]
    for i, (na, fa) in enumerate(new_entries):
        for nb, fb in new_entries[i + 1:]:
            if ohmy.audit_family_pair(na, fa, nb, fb):
                problems.append(f"audit_cluster_risk: 新增对 {na} × {nb} 会聚簇")
        for nb, fb in existing_top:
            if ohmy.audit_family_pair(na, fa, nb, fb):
                problems.append(f"audit_cluster_risk: {na} × 既有 {nb} 会聚簇")

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
        f"LandPPT 吸收决策: 源模板 {len(packs)} = 保留 {len(KEEP)} + 跳过 {len(SKIP)}",
        "",
        "跳过映射(概念已有):",
    ]
    for f in sorted(SKIP):
        lines.append(f"  - {f} -> {SKIP[f]['leo']}({SKIP[f]['reason']})")
    lines += [
        "",
        "新子类:",
        "  - 中式载体(01_通用母版): 竹简风/中式书卷风/宣纸风 —— 载体材质向",
        "  - 印象派油画(01_通用母版): 莫奈风/星月夜风",
        "  - 吉卜力手绘风归入既有 艺术表现",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LandPPT 模板吸收迁移器(S2a)")
    parser.add_argument("--write", action="store_true", help="生成 brief 文件(幂等)")
    parser.add_argument("--check", action="store_true", help="只跑去重门与自检")
    parser.add_argument("--report", action="store_true", help="输出吸收决策报告")
    parser.add_argument("--source", default=str(SOURCE_ROOT), help="源模板目录覆盖")
    args = parser.parse_args(argv)

    src = Path(args.source).resolve()
    packs = {p.name: parse_pack(p) for p in sorted(src.glob("*.json"))}

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
    print(f"intake OK ({action}): keep={len(KEEP)} skip={len(SKIP)}")
    if args.write:
        print(report(packs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
