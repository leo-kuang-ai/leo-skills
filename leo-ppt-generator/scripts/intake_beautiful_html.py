#!/usr/bin/env python3
"""beautiful-html-templates 风格吸收迁移器（风格进货批 C3）。

将外部源仓库 ``zarazhangrui/beautiful-html-templates``（MIT，快照
2026-09-01，34 个 HTML 模板）转换为 leo 风格库 brief。源是**双层
JSON 机器可读**结构：根 ``index.json``（34 条：mood / occasion / tone /
formality / density / scheme / best_for / **avoid_for**）+ 每模板
``template.json``（palette 命名色 HEX + typography 字族）。本脚本做
机械字段映射，人工策展集中在 ``KEEP`` / ``SKIP`` 决策表：

- ``avoid_for`` → ``negative_prompt`` 首条（直供负面提示词）；
- ``typography`` display/body/mono → brief title/body/labels 字段；
- ``mood + best_for`` → aliases / best_for 语境；
- ``palette`` 命名色经 ``roles`` 表映射四角色（primary/secondary/
  accent/neutral 各含真实 HEX 锚）；
- ``layout_patterns`` 从 design.md 描述人工提炼为可复制中文版式句。

HTML 模板本体不复制（``template.html`` 路径入 brief ``reference`` 供
溯源参考）。

配额与去重纪律（C3 批）：34 源 = 14 保留 + 20 跳过。跳过登记于
``SKIP`` 表，原因分三类：与 leo 现库既有概念重叠（editorial / swiss /
neobrutalist / 像素 / 商务蓝等）、源内同域簇收敛（editorial 系取代表）、
与本批并行吸收条目撞车（huashu 黑底剧场 vs studio）。

内置自检门（--check/--write 前置，与 intake_ohmy 同款）：

1. 四角色 palette 各含 #RRGGBB 锚点 + 身份字体声明；
2. 文字对比锚（WCAG ≥4.5:1，primary 判深浅底）；
3. family_duplicate：新增指纹与全库指纹集合相等即拒绝（R-66）；
4. audit 同族判定副本（name_ratio ≥0.62 且共享 ≥1 HEX，或
   name_ratio ≥0.45 且 jaccard ≥0.5，或 jaccard ≥0.6）：新增对
   （含新旧）聚簇即拒绝。

用法::

    python3 scripts/intake_beautiful_html.py --check   # 只跑自检门
    python3 scripts/intake_beautiful_html.py --write   # 生成 brief（幂等覆盖）

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
SOURCE_ROOT = Path("/Users/kuang/knowledge/ppt-github/beautiful-html-templates")

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)
# Mirror of lint_style_briefs._FONT_IDENTITY_RE.
FONT_IDENTITY_RE = re.compile(
    r"思源|Noto|MiSans|HarmonyOS|鸿蒙|苹方|PingFang|华文|冬青|宋|黑体|楷体|仿宋|"
    r"小标宋|Source Han|Inter|Helvetica|Roboto|Arial|Georgia|Times|IBM Plex|"
    r"JetBrains|DIN|Avenir|Futura|Garamond|Baskerville|mono|等宽|Monospace|"
    r"霞鹜|LXGW|站酷|ZCOOL|Caveat|Nunito|Kalam",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Intake decisions. 34 source slugs = 14 keep + 20 skip.
#
# keep fields:
#   name     zh style name (ends with 风)
#   subdir   target group under 01_通用母版
#   tag      one-line zh positioning (best_for lead)
#   vd       English visual_direction phrase (consumed by render prompts)
#   pairing  08 图片渲染 mate (视觉风格配对.md row)
#   roles    palette role -> source palette key mapping (4 roles required)
#   role_use zh role-purpose fragments merged into color_palette values
#   patterns 3-4 copyable zh layout rules (distilled from design.md)
#   comp     zh composition sentence for canvas.composition
#   neg      extra English negative items beyond source avoid_for
#   illu     (family, density) for paired_illustration
#   font     optional identity-font fallback when source faces miss the gate
# ---------------------------------------------------------------------------
KEEP: dict[str, dict] = {
    # -- 设计流派（design schools / poster, 6） -----------------------------
    "retro-windows": {
        "name": "复古视窗风", "subdir": "设计流派", "pairing": "像素复古",
        "tag": "以 Win95 系统界面语汇——3D 凸起灰面、海军蓝标题栏、像素字——把每页做成一扇运行在 CRT 上的软件窗口",
        "vd": "Windows 95 desktop chrome aesthetic, beveled 3D gray button-face panels, "
              "navy gradient title bars, pixel typography accents, every slide as a "
              "software window with group boxes and status bars, nostalgic CRT software deck",
        "roles": {"primary": "bg_gray", "secondary": "blue_navy",
                  "accent": "blue_light", "neutral": "black"},
        "role_use": {"primary": "3D 按钮灰面与窗口底", "secondary": "标题栏海军蓝",
                     "accent": "活动态高亮蓝", "neutral": "文字与硬边"},
        "patterns": [
            "每页一扇窗口:海军蓝 #000080 标题栏 + 灰面 #C0C0C0 客户区 + 像素内外凸双边框,内容即窗口部件",
            "章节页 = 满屏对话框:大标题 + 按钮组导航 + 图标位",
            "数据页 = 窗口内分组框 + 状态条,DOS 绿/砖红/芥末黄仅作状态文字色",
            "像素字(Press Start 2P/VT323)只做怀旧标点,正文走系统无衬线",
        ],
        "comp": "软件窗口即版式:标题栏 + 客户区 + 状态条三段",
        "neg": ["no modern glassmorphism or material chrome — strictly beveled 3D Win95",
                "no smooth anti-aliased curves; keep chunky pixel edges",
                "not for institutional finance, healthcare or formal luxury gravitas"],
        "illu": ("diagram", "supportive"),
        "font": "JetBrains Mono / VT323 + 思源黑体",
    },
    "biennale-yellow": {
        "name": "双年展海报风", "subdir": "设计流派", "pairing": "杂志编辑",
        "tag": "以暖羊皮纸上的太阳黄光晕与深靛蓝衬线,做艺术双年展画册与机构年展的安静海报系统",
        "vd": "art-biennale poster on warm parchment, solar yellow radial blooms from "
              "corners, single deep indigo ink with high-contrast serif display, hairline "
              "rules, atmospheric restrained cultural-institution deck",
        "roles": {"primary": "paper", "secondary": "sun",
                  "accent": "ember", "neutral": "ink"},
        "role_use": {"primary": "暖羊皮纸底", "secondary": "太阳黄光晕",
                     "accent": "余烬橙边光", "neutral": "深靛蓝墨(唯一文字色)"},
        "patterns": [
            "暖羊皮纸底 #E9E5DB + 太阳黄 #F1EE2E 径向光晕自画面角落漫出",
            "深靛蓝 #1B2566 单一墨色:衬线大标题 + 1px 发丝规则线,结构只靠线与字级",
            "封面 = 展览海报:黄光晕 + 大衬线标题 + 展讯元数据行",
            "禁圆角、投影、描边卡——纸墨承诺",
        ],
        "comp": "海报式居中/非对称构图,光晕做氛围底",
        "neg": ["no rounded corners, drop shadows or bordered cards — hairline rules only",
                "no multi-hue palettes; one yellow plus indigo ink",
                "not when saturated multi-color punch is the goal"],
        "illu": ("editorial", "sparse"),
    },
    "cobalt-grid": {
        "name": "钴蓝网格简报风", "subdir": "设计流派", "pairing": "杂志编辑",
        "tag": "以奶油纸上的永久性方格底纹、电钴蓝单色衬线巨题与像素阶梯装饰,做日式设计研究简报",
        "vd": "Japanese trend-report bulletin on cream graph paper, strict cobalt "
              "bichromatic ink, towering serif headlines, pixel-glitch stair columns and "
              "QR-grid patches as signature ornaments",
        "roles": {"primary": "paper", "secondary": "ink",
                  "accent": "ink-soft", "neutral": "ink"},
        "role_use": {"primary": "奶油纸底", "secondary": "电钴蓝主墨",
                     "accent": "柔钴蓝次墨", "neutral": "钴蓝即文字线色"},
        "patterns": [
            "奶油纸底 #F0EBDE + 永久性淡钴蓝方格底纹(约 10% 透明度)铺满每页",
            "Newsreader 衬线巨题(屏高量级)+ 全部装饰只用钴蓝 #1F2BE0 单色",
            "宣言页右缘像素阶梯故障列 + QR 式 8×8 网格贴片做签名装饰",
            "严格双色纪律:钴蓝×奶油,无第三色",
        ],
        "comp": "方格纸 + 巨型衬线宣言 + 像素故障装饰列",
        "neg": ["no third color — strictly cobalt-on-cream bichromatic",
                "no photographic imagery; line, grid and pixel ornaments only",
                "not for warm, casual or playful registers"],
        "illu": ("editorial", "sparse"),
    },
    "sakura-chroma": {
        "name": "樱彩磁带包装风", "subdir": "设计流派", "pairing": "扁平几何",
        "tag": "以 1970s 日系磁带包装语汇——六原色斜向缎带、压缩黑体大题、规格复选框——做复古产品目录",
        "vd": "vintage Japanese cassette-package catalogue, cream paper with diagonal "
              "six-color ribbon bands, condensed black grotesk display, starburst seals "
              "and JIS spec checkboxes, warm kawaii-tech product-sheet energy",
        "roles": {"primary": "paper", "secondary": "red",
                  "accent": "pink", "neutral": "ink"},
        "role_use": {"primary": "奶油纸底", "secondary": "磁带红",
                     "accent": "樱粉强调", "neutral": "暖棕墨"},
        "patterns": [
            "奶油纸底 + 六原色(红粉橙黄绿蓝)斜向缎带带 + 12 角星形封缄 + 红色矩形印章",
            "Big Shoulders Display 压缩黑体大题,红/棕双色锁定",
            "产品条/磁带块 + JIS 式规格复选框做目录与参数表",
            "日文汉字(Noto Sans JP)作装饰性微字",
        ],
        "comp": "产品目录页式:缎带 + 压缩大题 + 规格框",
        "neg": ["no restrained quiet typography — condensed loud lockups are the identity",
                "no photoreal product shots; flat catalogue blocks and ribbons only",
                "not for corporate restraint"],
        "illu": ("flat", "core"),
    },
    "peoples-platform": {
        "name": "行动主义海报风", "subdir": "设计流派", "pairing": "丝网印刷",
        "tag": "以 WPA 式政治海报的三字塔排版与丝网印刷质感,做宣言、公共议题与文化评论的一页一口号",
        "vd": "activist WPA political poster energy, cobalt blue and signal orange flat "
              "blocks with red reserved for depth, compressed slab serif all-caps display, "
              "handwritten brush interrupts, paper-grain screen-print overlay",
        "roles": {"primary": "cream", "secondary": "blue",
                  "accent": "red", "neutral": "ink"},
        "role_use": {"primary": "暖奶油纸底", "secondary": "钴蓝平涂大块",
                     "accent": "警示红(仅阴影/深度,绝不做面)", "neutral": "深墨文字"},
        "patterns": [
            "三字塔:Alfa Slab 压缩 slab 超大全大写标题 × Caveat Brush 手写打断句 × DM Mono 元数据",
            "钴蓝 #2C2CDC / 信号橙 #F2A03A 平涂大块对撞,红 #E83A2A 仅作阴影与深度层",
            "每页纸纹叠层出丝网印刷感,一页一口号",
            "标语式非对称构图,文字块可整体倾斜 2-3°",
        ],
        "comp": "抗议海报式:大字口号 + 平涂色块 + 手写打断",
        "neg": ["red is shadow/depth only — never a surface fill",
                "no photographic realism; screen-print poster blocks only",
                "not when institutional restraint is the actual goal"],
        "illu": ("flat", "core"),
        "font": "DM Mono + 思源黑体 Heavy",
    },
    "soft-editorial": {
        "name": "柔彩衬线编辑风", "subdir": "设计流派", "pairing": "杂志编辑",
        "tag": "以 Cormorant 衬线与尘粉/柠檬绿/蜜桃/鼠尾草四柔彩圆角卡,做周日副刊式的慢阅读编辑",
        "vd": "warm Sunday-magazine spread, Cormorant Garamond roman-and-italic "
              "headlines, pastel quartet cards (blush, lemon, peach, sage) with large "
              "rounded corners floating on translucent white, quiet unhurried editorial",
        "roles": {"primary": "paper", "secondary": "sage",
                  "accent": "pink", "neutral": "ink"},
        "role_use": {"primary": "奶油纸底", "secondary": "鼠尾草绿卡底",
                     "accent": "尘粉强调", "neutral": "暖墨文字"},
        "patterns": [
            "奶油纸底 + 四柔彩卡(尘粉 #E1A4C2/柠檬绿 #D6DD63/蜜桃 #E8C9B6/鼠尾草 #B7C7A8)24-36px 圆角浮于半透明白",
            "Cormorant Garamond 罗马×斜体混排标题,Work Sans 正文退后",
            "周日副刊节奏:一页一主题,大留白 + 小图 + 短栏",
            "装饰只用细线与色卡,无重边框无硬阴影",
        ],
        "comp": "杂志跨页:柔彩圆角卡阵 + 衬线标题 + 慢留白",
        "neg": ["no loud contrast or neon; the pastel quartet stays gentle",
                "no brutalist borders or hard shadows",
                "not when visual heat or punch is required"],
        "illu": ("editorial", "supportive"),
        "font": "Garamond 系 / Cormorant + 思源宋体",
    },
    # -- 艺术表现（tactile / handmade / hospitality, 4） -------------------
    "scatterbrain": {
        "name": "便利贴拼贴风", "subdir": "艺术表现", "pairing": "手绘笔记",
        "tag": "以粉彩便利贴、图钉胶带与厚装饰衬线,做头脑风暴墙与创意工坊的暖闹拼贴",
        "vd": "post-it brainstorm wall, pastel sticky notes slightly rotated with "
              "thumbtacks and masking tape, chunky decorative display serif headlines, "
              "handwritten Caveat annotations, cork-and-cream workshop energy",
        "roles": {"primary": "yellow", "secondary": "blue",
                  "accent": "pink", "neutral": "ink"},
        "role_use": {"primary": "便利贴黄主底", "secondary": "便签蓝",
                     "accent": "便签粉强调", "neutral": "墨棕文字"},
        "patterns": [
            "每个内容块 = 一张微旋转(±3°)粉彩便利贴(#FFE066/#A5D8FF/#FFC9C9/#B2F2BB),图钉/胶带做固定件",
            "标题 = Shrikhand 厚装饰衬线大字压在便签群上",
            "章节页 = 软木板/奶油纸底 + 大便签拼贴矩阵",
            "Caveat 手写做批注与连线,装饰涂鸦点缀角落",
        ],
        "comp": "工作坊拼贴墙:便签矩阵 + 手写连线 + 图钉",
        "neg": ["no rigid grid alignment — notes tilt slightly within ±3°",
                "no corporate flat icons; hand-drawn doodles and tape only",
                "not for precision or institutional-weight contexts"],
        "illu": ("collage", "core"),
    },
    "stencil-tablet": {
        "name": "模版印刷标语风", "subdir": "艺术表现", "pairing": "扁平几何",
        "tag": "以模版断墨大字、骨纸底与六色大地色平涂石板卡,做滑板海报与考古档案气质的图形宣言",
        "vd": "skate-poster meets municipal stencil signage, bone paper ground, "
              "stencil-cut display with ink-break gaps, saturated earth palette flat "
              "blocks on rounded tablet cards, oversized numerals, industrial archive mood",
        "roles": {"primary": "bone", "secondary": "sienna",
                  "accent": "magenta", "neutral": "ink"},
        "role_use": {"primary": "骨纸底", "secondary": "赭石平涂块",
                     "accent": "洋红强调", "neutral": "纯黑文字"},
        "patterns": [
            "标题 = Stardos Stencil 模版断墨大字,数字可放到 160-540px 量级",
            "内容卡 = 22-26px 圆角「石板卡」平涂大地色(赭 #A06A3C/洋红 #C73B7A/橙 #EE7A2E/青 #2D7E73/蓝 #3F73B7/橄榄 #6F7A2E)",
            "元数据 = Barlow Condensed 全大写窄字紧字距",
            "色块即版式:整版平涂色块分区,无渐变无描边照片",
        ],
        "comp": "石板卡平涂色块阵列 + 模版大字",
        "neg": ["no gradients or glass surfaces — flat spot blocks only",
                "no thin elegant serifs; display stays heavy stencil-cut",
                "not for digital-native polish or playful pop"],
        "illu": ("flat", "core"),
        "font": "Inter + 思源黑体 Heavy",
    },
    "long-table": {
        "name": "复古晚宴餐牌风", "subdir": "艺术表现", "pairing": "复古海报",
        "tag": "以锈红单墨、黄油奶油纸与胶囊描边徽章,做晚餐俱乐部与招待场景的温暖印刷餐牌",
        "vd": "supper-club program poster, single rust terracotta ink on buttery cream "
              "paper with radial-dot texture, bold uppercase grotesque headlines paired "
              "with warm serif body, pill buttons and outlined edition badges",
        "roles": {"primary": "paper", "secondary": "ink",
                  "accent": "ink-deep", "neutral": "ink-deep"},
        "role_use": {"primary": "黄油奶油纸底", "secondary": "锈红唯一墨色",
                     "accent": "深锈强调", "neutral": "深锈文字线色"},
        "patterns": [
            "黄油奶油纸 #FAF1E2 + 唯一锈红墨 #B53D2A + 4px 径向网点纹理出印刷纸感",
            "Bricolage Grotesque 全大写标题 × Fraunces 衬线正文与图注",
            "胶囊描边按钮 + 描边版次徽章 + 1.5px 虚线/实线框",
            "严格单墨双色纪律:锈红×奶油,菜单式分栏列表",
        ],
        "comp": "印刷餐牌:菜单分栏 + 胶囊徽章 + 单墨排版",
        "neg": ["no second ink color — rust on cream only",
                "no neon or cool-blue corporate accents",
                "not for corporate polish, technical density or cold minimalism"],
        "illu": ("flat", "supportive"),
        "font": "Fraunces / Bricolage + Inter 备选",
    },
    "pin-and-paper": {
        "name": "别针手账风", "subdir": "艺术表现", "pairing": "手绘笔记",
        "tag": "以法务黄拍纸簿、手绘安全别针与墨蓝手写批注,做田野笔记与质性研究的档案温度",
        "vd": "yellow legal-pad field notebook, fractal paper-grain overlay, "
              "hand-drawn safety-pin illustrations pinning cards to the page, "
              "cobalt ink handwritten annotations over heavy grotesk print, archival "
              "corkboard mood",
        "roles": {"primary": "paper", "secondary": "ink",
                  "accent": "red", "neutral": "cream"},
        "role_use": {"primary": "法务黄拍纸簿底", "secondary": "墨蓝手写与标题",
                     "accent": "锈红别针/印章", "neutral": "衬纸奶油白"},
        "patterns": [
            "法务黄拍纸簿底 #EFE56A + 纸纹颗粒叠层铺满每页",
            "手绘安全别针 SVG「钉」住内容卡,卡可微旋转",
            "Caveat 墨蓝 #1F3A8A 手写批注 × Space Grotesk 印刷标题 × DM Mono 档案标签",
            "公告板语汇:便签卡 + 别针 + 纸边撕裂感",
        ],
        "comp": "公告板/田野笔记:别针卡片阵 + 手写连线",
        "neg": ["no clean vector polish; paper grain and hand pins stay visible",
                "no dark-mode palettes; yellow field with cobalt ink only",
                "not for digital-native polish or rigorously data-driven decks"],
        "illu": ("hand-drawn", "core"),
    },
    # -- 极简排版（typographic minimalism, 1） ------------------------------
    "monochrome": {
        "name": "象牙账本风", "subdir": "极简排版", "pairing": "瑞士极简",
        "tag": "以象牙账本纸上的全墨黑排印——超细几何无衬线×斜体衬线×等宽——做零彩色的文学化研究报告",
        "vd": "hand-typeset ledger on ivory paper, all black ink with zero color, "
              "ultra-light geometric sans headlines, italic serif quotes, mono chrome, "
              "typography-line-whitespace as the only system",
        "roles": {"primary": "bg", "secondary": "fg",
                  "accent": "fg_2", "neutral": "fg"},
        "role_use": {"primary": "象牙纸底", "secondary": "深墨黑主字",
                     "accent": "石墨灰「更深即强调」", "neutral": "墨黑文字与表线"},
        "patterns": [
            "象牙纸 #FAFADF + 纯墨黑 #1A1A16,全套零彩色",
            "Jost 超细几何无衬线(200-300 字重)标题 × Lora 斜体衬线引文卡 × JetBrains Mono 结构铬件",
            "账本式表格线 + 行间隔 + 页眉页脚登记位",
            "「强调」= 更深的墨与更大字级,不是彩色",
        ],
        "comp": "账本式排印系统:表格线 + 细字标题 + 大留白",
        "neg": ["no color of any kind — ink on ivory, accent means darker ink",
                "no decorative shapes; typography, line and whitespace carry it",
                "not for color-led storytelling"],
        "illu": ("editorial", "sparse"),
    },
    # -- 几何装饰（shape systems, 1） ---------------------------------------
    "capsule": {
        "name": "胶囊卡波普风", "subdir": "几何装饰", "pairing": "扁平几何",
        "tag": "以全圆角胶囊容器、九色糖果粉彩与硬偏移影,做生活方式与新品发布的 Y2K 轻快卡阵",
        "vd": "pill-shaped capsule cards on sun-bleached bone canvas, nine-color candy "
              "pastel palette as flat capsule fills, didone serif display paired with "
              "geometric sans, soft offset shadows, Memphis-meets-editorial pop",
        "roles": {"primary": "bg", "secondary": "coral",
                  "accent": "violet", "neutral": "fg"},
        "role_use": {"primary": "暖骨白底", "secondary": "珊瑚胶囊主卡",
                     "accent": "紫罗兰强调", "neutral": "墨黑描边文字"},
        "patterns": [
            "所有容器 = 全圆角胶囊(9999px 圆角)2px 墨描边 + 6-12px 硬偏移影",
            "九色糖果粉彩平涂胶囊(珊瑚 #E85D4E/青柠 #C4D94E/薰衣草 #C5B5E0/天蓝 #8BB4F7/紫 #A06CE8/黄 #F2D160/蜜桃 #F5B895/薄荷 #A8E6CF)",
            "Bodoni Moda 高对比衬线大题 × Space Grotesk 几何无衬线正文",
            "漂浮装饰胶囊作氛围壁纸,无直角容器",
        ],
        "comp": "胶囊卡阵 + 糖果色平涂 + 硬偏移影",
        "neg": ["no sharp-cornered rectangles — every container is a pill",
                "no muted corporate palette; candy pastels stay saturated",
                "not for traditional institutional weight"],
        "illu": ("flat", "core"),
    },
    # -- 质感专业（premium editorial business, 2） --------------------------
    "emerald-editorial": {
        "name": "祖母绿刊头风", "subdir": "质感专业", "pairing": "杂志编辑",
        "tag": "以祖母绿满版场、海军墨与双细线戏剧海报饰件,做杂志封面级的领导层汇报与战略简报",
        "vd": "magazine-cover business deck, saturated emerald field with deep navy ink "
              "and oat paper, heavy didone display at 44-460px, stacked double-rule "
              "masthead ornaments bracketing centered display words, zero gradients or "
              "shadows",
        "roles": {"primary": "emerald", "secondary": "navy",
                  "accent": "paper", "neutral": "navy"},
        "role_use": {"primary": "祖母绿满版场", "secondary": "深海军墨",
                     "accent": "燕麦纸点睛", "neutral": "海军墨文字"},
        "patterns": [
            "祖母绿 #3CD896 满版场 + 深海军墨 #0F1A5C + 燕麦纸 #F1E9D6 三色锁定",
            "Bodoni Moda 900 巨字居中词(44-460px 字阶)",
            "双细线叠层饰件(19 世纪戏剧海报式)框住居中词,即「刊头」",
            "零渐变零投影,纸墨承诺;数据页用细线表 + 小 caps 标签",
        ],
        "comp": "杂志封面/戏剧海报:居中巨词 + 双线刊头饰件",
        "neg": ["no gradients or shadows — flat paper-ink commitment",
                "no muted earth tones; emerald stays saturated",
                "not when quiet neutral restraint is required"],
        "illu": ("editorial", "sparse"),
    },
    "editorial-forest": {
        "name": "林间三色季刊风", "subdir": "质感专业", "pairing": "杂志编辑",
        "tag": "以深林绿×尘玫瑰×燕麦三色与 Source Serif 光学轴大题,做文学季刊式的季度回顾与内读汇报",
        "vd": "literary quarterly editorial, deep forest green with dusty rose on "
              "oat-cream paper, Source Serif optical-size display up to 220px, mono "
              "chrome for kickers captions and axis ticks, Penguin-classics calm",
        "roles": {"primary": "forest_green", "secondary": "pink",
                  "accent": "ink", "neutral": "cream"},
        "role_use": {"primary": "深林绿主导场", "secondary": "尘玫瑰粉辅",
                     "accent": "墨黑编号与细线", "neutral": "燕麦奶油纸"},
        "patterns": [
            "深林绿 #2E4A2A × 尘玫瑰 #E89CB1 × 燕麦奶油 #EFE7D4 三色季刊锁定",
            "Source Serif 4 光学尺寸轴大题(封面/数据页可至 220px)",
            "JetBrains Mono 做编辑铬件:kicker/图注/轴刻度",
            "文学季刊节奏:一页一散文段 + 单数据锚,安静不急",
        ],
        "comp": "文学季刊排版:衬线大题 + mono 铬件 + 三色场",
        "neg": ["no urgency cues or saturated neon; quiet tri-tone only",
                "no sans-serif-dominant tech look; the serif leads",
                "not for urgent, punchy or sales-driven decks"],
        "illu": ("editorial", "sparse"),
        "font": "JetBrains Mono + 思源宋体",
    },
}

# Skip ledger: slug -> zh reason (dedupe against leo library / intra-source
# cluster convergence / parallel-batch collision).
SKIP: dict[str, str] = {
    "8-bit-orbit": "与「像素复古风」(8-bit 有限色板)+「合成波风」暗底霓虹像素域重叠",
    "block-frame": "与「新粗野主义风」(粗黑边+粉彩块)同概念",
    "blue-professional": "与「商务几何风」「稳重商务风」「清爽专业风」商务蓝系重叠",
    "bold-poster": "与「大字报巨型排版风」「杂志大字风」巨型显示字域重叠",
    "broadside": "与「深色编辑报告风」(深色编辑+单一强调)同概念",
    "cartesian": "与「极简奢侈品牌风」(暖中性+古典衬线)同概念",
    "coral": "与「杂志大字风」超大 Bebas 衬线/无衬线巨题域重叠",
    "creative-mode": "与「多巴胺活力撞色风」「创意杂志风」多色自信域重叠",
    "daisy-days": "与「奶油温柔风」「童趣暖橙风」粉彩手绘花饰域重叠",
    "editorial-tri-tone": "与「勃艮第红风」(勃艮第酒红+粉尘粉+芥末奶油衬线)三色编辑域重叠",
    "grove": "源内 editorial 绿色域与 editorial-forest 收敛;且与「森林绿临床水彩风」色域撞",
    "mat": "与「中世纪现代风」(mid-century)同概念",
    "neo-grid-bold": "与「新粗野主义风」「粗野报刊风」编辑新粗野域重叠",
    "pink-script": "与「深色编辑报告风」「松烟画报风」深底编辑+单强调域重叠",
    "playful": "与「童趣暖橙风」「多巴胺活力撞色风」友好独立发布域重叠",
    "raw-grid": "与「新粗野主义风」粗边+偏移影同概念",
    "retro-zine": "与「里索印刷风」(risograph zine)同概念",
    "signal": "与「博物馆纪念风」(午夜蓝+黄铜金机构感)同概念",
    "studio": "与 C3 批 huashu「黑底数字剧场风」黑底剧场域撞车,收敛为一个",
    "vellum": "与「博物馆纪念风」深海军+暖金安静域重叠",
}


# ---------------------------------------------------------------------------
# Source loading (two-layer JSON)
# ---------------------------------------------------------------------------
def load_source() -> dict[str, dict]:
    """Merge root index.json entries with per-template template.json."""
    if not SOURCE_ROOT.is_dir():
        raise FileNotFoundError(f"source missing: {SOURCE_ROOT}")
    index = json.loads((SOURCE_ROOT / "index.json").read_text(encoding="utf-8"))
    merged: dict[str, dict] = {}
    for entry in index["templates"]:
        slug = entry["slug"]
        detail_path = SOURCE_ROOT / "templates" / slug / "template.json"
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        merged[slug] = {**entry, **detail}  # template.json wins on overlap
    return merged


def roles_palette(pack: dict, keep: dict) -> dict[str, str]:
    """Map named source palette keys onto the four brief roles (HEX anchored)."""
    src = pack["palette"]
    out: dict[str, str] = {}
    for role, key in keep["roles"].items():
        if key not in src or not HEX_RE.search(str(src[key])):
            raise ValueError(
                f"{pack['slug']}: role {role} key {key!r} missing HEX in source palette"
            )
        use = keep["role_use"].get(role, "")
        out[role] = f"{src[key]}({use})" if use else f"{src[key]}"
    desc = src.get("description", "")
    out["rule"] = f"{desc[:120]};锚点 {'/'.join(str(src[k]) for k in keep['roles'].values())}"
    return out


def typography_pack(pack: dict, keep: dict) -> dict[str, str]:
    t = pack["typography"]
    title_face = t.get("display") or t.get("serif") or ""
    body_face = t.get("body") or t.get("sans") or ""
    label_face = t.get("mono") or t.get("script") or ""
    style_note = t.get("style", "")
    result = {
        "title": f"{title_face} 标题字族;{style_note[:70]}",
        "body": f"{body_face} 正文字族,行距宽绰" if body_face else "同族常规字重",
        "labels": f"{label_face} 标签/数据字族" if label_face else "小字号同族",
    }
    joined = " ".join(result.values())
    if not FONT_IDENTITY_RE.search(joined):
        fallback = keep.get("font", "Inter / 思源黑体")
        result["title"] = f"{fallback};{title_face} 源字族"
    return result


def clean_occasions(pack: dict, limit: int = 4) -> list[str]:
    """Source occasion tags minus vulgar entries, capped."""
    return [
        s for s in pack.get("occasion", []) if "shitpost" not in s.lower()
    ][:limit]


def aliases_pack(pack: dict, keep: dict) -> list[str]:
    zh_base = keep["name"][:-1] if keep["name"].endswith("风") else keep["name"]
    items = [pack["name"], pack["slug"], zh_base]
    for m in pack.get("mood", [])[:2]:
        items.append(m)
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        it = it.strip()
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out[:6]


def negative_pack(pack: dict, keep: dict) -> list[str]:
    items: list[str] = [pack.get("avoid_for", "").strip()]
    items += [n for n in keep.get("neg", []) if n]
    return [i for i in items if i][:5]


def build_brief(pack: dict, keep: dict) -> dict:
    palette = roles_palette(pack, keep)
    primary_hex = HEX_RE.search(palette["primary"]).group(0)  # type: ignore[union-attr]
    scheme = pack.get("scheme", "light")
    density = pack.get("density", "medium")
    return {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": keep["name"],
        "aliases": aliases_pack(pack, keep),
        "best_for": f"{keep['tag']};适合{', '.join(clean_occasions(pack))}",
        "visual_direction": keep["vd"],
        "canvas": {
            "aspect_ratio": "16:9",
            "background": f"{pack['palette'].get('description', '')[:90]}(主锚 {primary_hex},{scheme} 底)",
            "composition": keep["comp"],
            "density": f"{density},保持源模板信息节奏",
        },
        "color_palette": palette,
        "typography": typography_pack(pack, keep),
        "layout_patterns": keep["patterns"],
        "layout_usage_rule": keep["patterns"][0][:80],
        "negative_prompt": negative_pack(pack, keep),
        "paired_illustration": {
            "family": keep["illu"][0],
            "density": keep["illu"][1],
        },
        "visual_elements": {
            "allowed": keep["patterns"][1][:64],
            "avoid": "; ".join(negative_pack(pack, keep)[1:3]),
        },
        "rendering_constraints": [
            f"{keep['name']} follows beautiful-html-templates {pack['slug']} system; palette anchors locked.",
            *keep.get("neg", [])[:2],
            "No invented logos or watermarks.",
        ],
        "reference": (
            "GitHub: zarazhangrui/beautiful-html-templates · "
            f"templates/{pack['slug']}/(design.md + template.html 快照 2026-09-01,MIT)"
        ),
    }


def render_markdown(brief: dict, subdir: str, pack: dict) -> str:
    scenes = clean_occasions(pack)
    lines = [
        f"# {brief['style_name']}",
        "",
        f"**分类:** 01_通用母版 · {subdir}",
        "",
        "**适用场景:**",
    ]
    lines += [f"- {s}" for s in scenes[:4]]
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
# Dedupe / audit gates (mirror lint + audit_style_families semantics)
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
    if not fp_a or not fp_b:
        return False
    ratio = difflib.SequenceMatcher(None, normalize_name(name_a), normalize_name(name_b)).ratio()
    shared = fp_a & fp_b
    jaccard = len(shared) / len(fp_a | fp_b)
    if ratio >= 0.62 and shared:
        return True
    if ratio >= 0.45 and jaccard >= 0.5:
        return True
    return jaccard >= 0.6


def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a: str, b: str) -> float:
    l1, l2 = _lum(a), _lum(b)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


DONE_CACHE: dict[str, tuple[str, frozenset]] = {}


def run(packs: dict[str, dict], *, write: bool) -> tuple[list[str], int]:
    problems: list[str] = []
    written = 0
    existing = load_existing_briefs()
    existing_fps = {(name, fingerprint(b)) for _, name, b in existing}
    existing_by_name = {name: fingerprint(b) for _, name, b in existing}

    for slug, keep in KEEP.items():
        pack = packs[slug]
        brief = build_brief(pack, keep)
        name = brief["style_name"]
        rel = f"01_通用母版/{keep['subdir']}/{name}.md"

        # Gate 1: role HEX anchors (roles_palette raises on missing).
        for role in ("primary", "secondary", "accent", "neutral"):
            if not HEX_RE.search(brief["color_palette"][role]):
                problems.append(f"palette_hex_missing: {rel} {role}")

        # Gate 2: identity font.
        joined_t = " ".join(brief["typography"].values())
        if not FONT_IDENTITY_RE.search(joined_t):
            problems.append(f"font_identity_missing: {rel}")

        # Gate 3: WCAG text anchor against primary-implied ground.
        fp = fingerprint(brief)
        primary_hex = HEX_RE.search(brief["color_palette"]["primary"]).group(0)
        bg = "#1A1A1A" if _lum(primary_hex) < 0.35 else "#FFFFFF"
        if not any(_contrast(h, bg) >= 4.5 for h in fp):
            problems.append(f"text_anchor_fail: {rel} no >=4.5:1 anchor on {bg}")

        # Gate 4a: exact palette-fingerprint duplicate (R-66).
        for ex_name, ex_fp in existing_by_name.items():
            if ex_name != name and ex_fp == fp:
                problems.append(f"family_duplicate: {rel} palette == {ex_name}")
        # Gate 4b: audit-style suspected-family pairs vs library and peers.
        for ex_name, ex_fp in existing_by_name.items():
            if ex_name != name and audit_family_pair(name, fp, ex_name, ex_fp):
                problems.append(f"audit_family_pair: {rel} ~ {ex_name}")
        for done_slug, (done_name, done_fp) in DONE_CACHE.items():
            if done_slug != slug and audit_family_pair(name, fp, done_name, done_fp):
                problems.append(f"audit_family_pair(new): {rel} ~ {done_name}")
        DONE_CACHE[slug] = (name, fp)

        if write and not problems:
            target = STYLES_ROOT / "01_通用母版" / keep["subdir"] / f"{name}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render_markdown(brief, keep["subdir"], pack), encoding="utf-8")
            written += 1

    return problems, written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="run gates only")
    parser.add_argument("--write", action="store_true", help="generate briefs (idempotent)")
    args = parser.parse_args(argv)
    if not (args.check or args.write):
        parser.error("choose --check or --write")
    try:
        packs = load_source()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"source error: {exc}", file=sys.stderr)
        return 2

    slugs = set(packs)
    decided = set(KEEP) | set(SKIP)
    if decided != slugs:
        missing = slugs - decided
        extra = decided - slugs
        print(f"decision table drift: missing={sorted(missing)} extra={sorted(extra)}", file=sys.stderr)
        return 2
    if set(KEEP) & set(SKIP):
        print("KEEP/SKIP overlap", file=sys.stderr)
        return 2
    quota = len(KEEP)
    if not 12 <= quota <= 15:
        print(f"quota band 12-15 violated: {quota}", file=sys.stderr)
        return 2

    problems, written = run(packs, write=args.write)
    if problems:
        print(f"SELF-CHECK FAILED ({len(problems)}):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    if args.write:
        print(f"OK: wrote {written} briefs (skip {len(SKIP)})")
    else:
        print(f"OK: gates pass for {quota} briefs (skip {len(SKIP)} registered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
