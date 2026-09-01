#!/usr/bin/env python3
"""slides-grab + OfficeCLI morph-ppt 风格吸收迁移器(风格进货批 C2)。

两源 141 套按「概念级去重 + 韩式保真优先」口径转换为 leo 风格库 brief:

- **slides-grab**(MIT 双上游:corazzon/pptx-design-styles 35 套西式 +
  epoko77-ai/design-diversity 60 套韩式,tokens 级 hex):韩式 60 套是
  现库缺失的全新审美(韩式咨询 / 精密网格 / 韩国企事业 IR),按
  「优先保真收录」取 23 套(中文名意译 + 韩文原名入 aliases,四角色
  HEX 全部出自源 tokens);西式 35 套与现库重叠度高(glassmorphism /
  brutalism / bauhaus / vaporwave 等已覆盖),且 C1/C3/C4 并行批已收
  便当格卡片风 / 暗夜植物园风 / 有机渐变形风 / 便利贴拼贴风 / 珊瑚紫
  双色调风等相邻概念,真净新仅 2 套(暗黑学院 / 彩窗马赛克)。
- **OfficeCLI morph-ppt**(51 个 md 风格目录):六分组(bw/dark/light/
  mixed/vivid/warm)作为 variant 第二维度在 brief 头部标注
  (``variant-dimension``);概念级去重后净新 7 套;有成品 PPTX 的
  4 套复制入 ``samples/reference-golden/officecli/``(只登记路径
  不转换)。

锚点保真纪律:四角色 HEX 与 background 锚必须能在源数据(JS tokens /
style.md 色板表 / INDEX.md 三元组)中找到出处,解析不到即
``anchor_unprovenanced`` 拒绝——与 S1a/S2a intake 同纪律。

自检门(复用 ``intake_ohmy`` 共享语义,importlib 加载单一真值源):

1. 四角色 palette 各含 #RRGGBB 锚点 + 身份字体声明(lint WARNING 子集);
2. 文字对比锚(WCAG:primary 判深浅底,合并锚点须有 ≥4.5:1 文字锚);
3. family_duplicate:新增指纹与全库指纹集合相等即拒绝(R-66);
4. audit 同族判定副本(name_ratio ≥0.62 且共享 ≥1 HEX,或 name_ratio
   ≥0.45 且 jaccard ≥0.5,或 jaccard ≥0.6):新增对(含新旧)聚簇即
   拒绝,保证 audit 疑似同族簇数不恶化。

用法::

    python3 scripts/intake_slidesgrab_officecli.py --check    # 只跑自检门
    python3 scripts/intake_slidesgrab_officecli.py --write    # 生成 brief(幂等)
    python3 scripts/intake_slidesgrab_officecli.py --report   # 吸收决策报告

退出码:0 = 通过/写入成功;2 = 自检失败或源/目标异常。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STYLES_ROOT = SKILL_DIR / "references" / "styles"
SAMPLES_GOLDEN = SKILL_DIR / "samples" / "reference-golden" / "officecli"
SLIDESGRAB_SRC = Path(
    "/Users/kuang/knowledge/ppt-github/slides-grab/src"
)
OFFICECLI_STYLES = Path(
    "/Users/kuang/knowledge/ppt-github/OfficeCLI/skills/morph-ppt/reference/styles"
)

# Gate semantics shared with S1a/S2a intakes (single source of truth).
_spec = importlib.util.spec_from_file_location("intake_ohmy", SCRIPT_DIR / "intake_ohmy.py")
ohmy = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("intake_ohmy", ohmy)
_spec.loader.exec_module(ohmy)

HEX_RE = ohmy.HEX_RE

TARGET_KO_DIR = "16_来源_slides-grab/韩式精密网格"
TARGET_WEST_DIR = "16_来源_slides-grab/西式精选"
TARGET_OFFICE_DIR = "15_来源_officecli"

# ---------------------------------------------------------------------------
# KEEP decisions. Each entry hand-curates the leo-facing brief; hex anchors
# must trace back to source tokens (provenance gate), zh notes explain roles.
# Fields: name / vd (English visual_direction) / pairing (08 render mate) /
# anchors (four color_palette roles) / bg / scenes / aliases / composition /
# layout / negatives / typo / best_for / family (paired_illustration).
# ---------------------------------------------------------------------------
KEEP_KO: dict[str, dict] = {
    "DD01": {
        "name": "咨询精密网格风",
        "vd": "korean consulting precision grid, white ground on a 12-column "
              "modular grid, action-title header over a 1px hairline rule, "
              "grayscale body with a single electric-blue accent reserved for "
              "KPI numerals and active data-box borders, square corners, zero "
              "shadow, fixed bottom-right source caption",
        "pairing": "瑞士极简", "family": ("flat", "core"),
        "anchors": {
            "primary": "#FFFFFF(纸白底)",
            "secondary": "#F4F5F7(面板浅灰面)",
            "accent": "#0B5FFF(唯一电蓝,仅数据/KPI)",
            "neutral": "#1A1A1A(墨字)",
        },
        "bg": ["#FFFFFF", "#F4F5F7"],
        "scenes": ["咨询报告", "策略汇报", "数据分析", "经营审查"],
        "aliases": ["컨설팅 정밀그리드", "consulting precision grid", "action title grid"],
        "composition": "12 列模块网格 + 顶部动作标题(完整结论句)+ 右下角来源脚注",
        "layout": [
            "每页顶部动作标题(完整结论句)+ 其下 1px 发丝线",
            "数据盒 1px 灰边直角框,激活项 4px 电蓝左边框",
            "正文全灰阶;KPI 数字用电蓝单色强调",
            "直角零阴影;图解用方形节点 + 0.75pt 直连线",
        ],
        "negatives": [
            "不要第二个强调色或彩色正文——强调仅 #0B5FFF 且只落在数据/KPI",
            "不要圆角、阴影、渐变",
            "不要 3D 图表/彩虹配色/截断 Y 轴等业余图表回潮;柱图全灰 + 单柱电蓝",
            "不要全居中排版——正文一律左对齐;不要缺失来源脚注",
        ],
        "typo": {
            "title": "Inter 700(Arial 兜底),动作标题完整句,tracking -0.01em",
            "body": "Inter 400 灰阶正文,leading 1.3",
            "labels": "Inter 700 kicker,tracking 0.08em;来源脚注 9pt 右下",
        },
        "best_for": "韩式咨询报告正型:白底 12 列精密网格 + 动作标题 + 唯一电蓝数据强调;适合咨询报告/策略汇报/数据审查",
    },
    "DD02": {
        "name": "全幅极简演讲风",
        "vd": "korean keynote minimalism, full-bleed single-color or photographic "
              "ground carrying one sentence per slide, oversized grotesk display, "
              "over two-thirds negative space, no boxes no borders no shadows",
        "pairing": "企业摄影", "family": ("photographic", "core"),
        "anchors": {
            "primary": "#FFFFFF(纯白底)",
            "secondary": "#000000(整页纯黑变体)",
            "accent": "#0071E3(唯一产品蓝)",
            "neutral": "#86868B(次要灰字)",
        },
        "bg": ["#FFFFFF", "#000000"],
        "scenes": ["主题演讲", "产品发布", "品牌宣言", "高规格提案"],
        "aliases": ["Keynote 미니멀 풀블리드", "keynote minimal fullbleed", "한 장 한 메시지"],
        "composition": "一页一讯息:全幅图/纯色底上仅一句完整陈述,文字占画面 ≤1/3",
        "layout": [
            "全幅影像或纯色底 + 一句完整陈述",
            "文字面积 ≤1/3,其余留白或全幅图",
            "无项目符号——多项内容一律拆页",
            "纯白页与纯黑页交替构成节奏",
        ],
        "negatives": [
            "不要项目符号列表——多项即拆页",
            "不要用文字填满版面,文本超 1/3 即失败",
            "不要盒子/卡片/边框/阴影/圆角",
        ],
        "typo": {
            "title": "Helvetica Neue 700(54pt 级,黑或白)",
            "body": "Helvetica Neue 400,leading 1.2",
            "labels": "Helvetica Neue 400 小字,灰 #86868B",
        },
        "best_for": "Keynote 式一页一讯息的极端留白演讲;适合主题演讲/产品发布/品牌宣言",
    },
    "DD06": {
        "name": "韩式政策报告风",
        "vd": "korean government policy report, white ground under a fixed "
              "12%-height navy header band with white gothic title, numbered "
              "section chips on the left, aligned box body and restrained "
              "point colors",
        "pairing": "瑞士极简", "family": ("flat", "supportive"),
        "anchors": {
            "primary": "#FFFFFF(白底)",
            "secondary": "#0B2C5C(藏青头带/主墨)",
            "accent": "#1B66C9(亮蓝强调)",
            "neutral": "#1A1A1A(墨字)",
        },
        "bg": ["#FFFFFF", "#E8F1FB"],
        "scenes": ["政府工作报告", "政策宣讲", "公共项目汇报", "机关简报"],
        "aliases": ["한국 정책보고서 네이비", "korea policy navy", "政策报告"],
        "composition": "顶部 12% 高藏青头带 + 左侧编号分区 + 浅蓝面板正文",
        "layout": [
            "顶部 12% 高(0.9in)藏青头带白字标题,全 deck 固定",
            "正文区块左侧编号片(①②③ / 01·02·03)",
            "浅蓝 #E8F1FB 面板承载图表与要点",
            "红 #E03B3B / 绿 #1F9D57 仅作增减语义点色",
        ],
        "negatives": [
            "不要整页藏青平涂——头带之外保持白底",
            "不要偏离 12% 头带比例",
            "不要非韩文兼容的装饰字体(韩文页面须 Pretendard/Noto Sans KR)",
        ],
        "typo": {
            "title": "Pretendard 700(Noto Sans KR/苹方兜底),头带白字 26pt",
            "body": "Pretendard 400,20pt 级",
            "labels": "Pretendard 700 章节号 chip,tracking 0.06em",
        },
        "best_for": "韩国公共报告正型:藏青头带 + 编号分区 + 浅蓝面板;适合政府工作报告/政策宣讲/机关汇报",
    },
    "DD09": {
        "name": "数据信息密集风",
        "vd": "dense data infographic slide, F-pattern dashboard of 4-8 chart and "
              "KPI card modules on near-white ground, four-color data coding with "
              "strict hierarchy, compact grotesk typography",
        "pairing": "数字仪表盘", "family": ("dashboard", "core"),
        "anchors": {
            "primary": "#F7F8FA(浅灰白底)",
            "secondary": "#FFFFFF(KPI 卡面白)",
            "accent": "#2563EB(数据蓝主强调)",
            "neutral": "#1E2229(墨字)",
        },
        "bg": ["#F7F8FA", "#FFFFFF"],
        "scenes": ["运营复盘", "数据汇报", "增长报告", "指标看板"],
        "aliases": ["데이터 인포그래픽 헤비", "data infographic heavy", "信息密集看板"],
        "composition": "一页 4-8 个图表/KPI 卡模块,F 字动线排布,密度即身份",
        "layout": [
            "一页 4-8 个图表/KPI 卡模块,F 字动线排布",
            "四色数据编码(蓝/青/琥珀/红),不超四色",
            "KPI 数字 40pt 级,辅助文字小两档",
            "圆角 ≤8px,无渐变底",
        ],
        "negatives": [
            "不要一页只有 1-2 个模块——密度是身份,至少 4 个",
            "不要超过四色或装饰性配色",
            "不要大圆角(>8px)与渐变背景",
        ],
        "typo": {
            "title": "Inter 700 24pt,tracking -0.01em",
            "body": "Inter 400,卡头 13pt semibold",
            "labels": "Inter 600 KPI 数字 40pt;涨跌用绿 #16A34A/红 #EF4444",
        },
        "best_for": "图表/KPI 卡高密度填充的仪表盘式信息页;适合运营复盘/数据汇报/增长报告",
    },
    "DD12": {
        "name": "极简单色笔记风",
        "vd": "typewriter mono note, pure white sheet carrying only monospace "
              "text in ink black, one 1pt hairline divider, extreme restraint "
              "without any color",
        "pairing": "瑞士极简", "family": ("flat", "core"),
        "anchors": {
            "primary": "#FFFFFF(纸白)",
            "secondary": "#111111(墨黑标题/强调)",
            "accent": "#111111(强调同为墨黑,单色纪律)",
            "neutral": "#8A8A8A(次级灰)",
        },
        "bg": ["#FFFFFF"],
        "scenes": ["技术笔记", "极简 manifesto", "开发分享", "文档式汇报"],
        "aliases": ["미니멀 모노 노트", "minimal mono note", "打字机笔记"],
        "composition": "纯白页面仅等宽字体文本,墨黑一色,1pt 发丝线是唯一装饰",
        "layout": [
            "纯白页面仅等宽字体文本,墨黑一色",
            "1pt 发丝分隔线是唯一装饰",
            "大量留白,层级用字号与字重区分",
            "图表也只用黑/灰两档",
        ],
        "negatives": [
            "不要任何有彩色(紫/蓝等全部禁止)",
            "不要盒子/卡片/边框/阴影/面填充",
            "不要混入无衬线或衬线字体——等宽单一家族",
        ],
        "typo": {
            "title": "JetBrains Mono 500 36pt(等宽)",
            "body": "JetBrains Mono 400 22pt,leading 1.55",
            "labels": "JetBrains Mono 400 小字,灰 #8A8A8A",
        },
        "best_for": "纯白等宽打字机笔记的单色极简;适合技术笔记/极简宣言/开发分享",
    },
    "DD13": {
        "name": "植物有机编辑风",
        "vd": "botanical organic editorial, beige terracotta and moss earth-tone "
              "canvas with hand-drawn plant illustrations, organic curved "
              "dividers and serif display, wellness warmth",
        "pairing": "水彩晕染", "family": ("hand-drawn", "core"),
        "anchors": {
            "primary": "#F2EAD9(米杏纸底)",
            "secondary": "#E5D9C3(次级面/纸纹)",
            "accent": "#B5654A(陶土主强调)",
            "neutral": "#3A352C(暖墨字)",
        },
        "bg": ["#F2EAD9", "#E5D9C3"],
        "scenes": ["生活方式品牌", "康养疗愈", "可持续发展", "文创编辑"],
        "aliases": ["보태니컬 오가닉", "botanical organic", "植物手绘"],
        "composition": "米杏底上苔绿/陶土/赭金三色有机曲线分区,手绘植物沿边缘生长",
        "layout": [
            "米杏底 + 陶土/苔绿/赭金三色有机曲线分区",
            "手绘植物插画(叶/茎/枝)沿边缘与分栏生长",
            "衬线大标题 + 无衬线正文",
            "无直角边框,分区以曲线与色带过渡",
        ],
        "negatives": [
            "不要原色/霓虹/网格渐变等高饱和",
            "不要纯黑 #000 文字——用暖墨 #3A352C",
            "不要直角边框盒/硬阴影/统一圆角卡",
        ],
        "typo": {
            "title": "Cormorant Garamond 500 48pt(Noto Serif KR 兜底)",
            "body": "Noto Sans KR 400 24pt,leading 1.5",
            "labels": "Cormorant Garamond 小标签,赭金点缀",
        },
        "best_for": "大地色手绘植物 wellness 编辑风;适合生活方式品牌/康养疗愈/可持续叙事",
    },
    "DD21": {
        "name": "精密金融科技风",
        "vd": "precision fintech deck, blue-tinted near-white surfaces stepping "
              "over pure white ground, single indigo-violet accent owning CTA "
              "KPI and charts, hairline grid with editorial area graphs",
        "pairing": "瑞士极简", "family": ("flat", "core"),
        "anchors": {
            "primary": "#FFFFFF(纯白底)",
            "secondary": "#F6F9FC(蓝灰面差分区)",
            "accent": "#5A55E0(靛紫唯一强调)",
            "neutral": "#0A2540(深墨蓝字)",
        },
        "bg": ["#FFFFFF", "#F6F9FC"],
        "scenes": ["金融科技", "支付产品", "toB SaaS 汇报", "量化简报"],
        "aliases": ["Precision Fintech Deck", "precision fintech", "金融科技极简"],
        "composition": "#F6F9FC 蓝灰面差分区代替边框卡,靛紫单色承担全部强调",
        "layout": [
            "#F6F9FC 蓝灰面差分区代替边框卡",
            "靛紫 #5A55E0 承担 CTA/KPI/图表全部强调",
            "发丝线网格 + 面积图编辑风",
            "同 hue 双档渐变允许,禁彩虹渐变",
        ],
        "negatives": [
            "不要第二强调色或彩色正文",
            "不要用边框切卡——以面差分区",
            "不要深阴影/多重阴影/霓虹光晕与彩虹渐变",
        ],
        "typo": {
            "title": "Inter 700 54pt,tracking -0.025em",
            "body": "Inter 400;muted #5C6B7E",
            "labels": "Inter 600 kicker 12pt,tracking 0.06em",
        },
        "best_for": "蓝灰面差 + 靛紫单强调的克制金融科技;适合金融科技/支付产品/toB 数据汇报",
    },
    "DD23": {
        "name": "温暖款待风",
        "vd": "warm hospitality deck, pure white canvas with a single coral-red "
              "accent, rounded humanist sans and full-bleed round-corner "
              "photography, welcoming refined mood",
        "pairing": "企业摄影", "family": ("photographic", "core"),
        "anchors": {
            "primary": "#FFFFFF(白底)",
            "secondary": "#FBF7F4(暖面)",
            "accent": "#F4625F(珊瑚红唯一强调)",
            "neutral": "#2B2B2E(墨字)",
        },
        "bg": ["#FFFFFF", "#FBF7F4"],
        "scenes": ["酒店旅行", "服务体验", "客户提案", "品牌待客叙事"],
        "aliases": ["Warm Hospitality Deck", "warm hospitality", "款待暖调"],
        "composition": "白底 + 珊瑚红单强调 + 20px 圆角全幅照片的款待气质",
        "layout": [
            "白底 + 珊瑚红 #F4625F 单强调连接 CTA/评分点/KPI",
            "照片全幅 20px 圆角,不直角裁切",
            "圆润人文无衬线(Poppins 系)标题",
            "暖面 #FBF7F4 分区,无深阴影",
        ],
        "negatives": [
            "不要第二强调色或珊瑚色正文",
            "不要直角照片与 0 圆角",
            "不要深阴影/多重阴影/任何渐变(含珊瑚渐变)",
        ],
        "typo": {
            "title": "Poppins 600 52pt(兜底 Nunito Sans)",
            "body": "Poppins 400 32pt 级",
            "labels": "Poppins 600 kicker 12pt,tracking 0.06em",
        },
        "best_for": "白底珊瑚红 + 圆角全幅摄影的款待体验风;适合酒店旅行/服务体验/客户提案",
    },
    "DD24": {
        "name": "单色基础设施风",
        "vd": "monochrome infrastructure document, pure white and pure black only "
              "with two gray steps, sans plus mono type mix, 1px hairline "
              "borders, emphasis by weight contrast instead of color",
        "pairing": "工程蓝图", "family": ("diagram", "core"),
        "anchors": {
            "primary": "#FFFFFF(纯白底)",
            "secondary": "#999999(第三档灰/disabled 文字锚)",
            "accent": "#000000(纯黑,粗细对比即强调)",
            "neutral": "#666666(次级灰字)",
        },
        "bg": ["#FFFFFF"],
        "scenes": ["基础设施架构", "系统设计文档", "技术规格", "工程交付"],
        "aliases": ["Monochrome Infrastructure Deck", "monochrome infrastructure", "单色工程"],
        "composition": "纯白/纯黑 + 两档灰的绝对单色纪律,1px 发丝边框,图纸式对齐",
        "layout": [
            "纯白/纯黑 + 两档灰(#F2F2F2 面/#999999 禁用灰)的绝对单色纪律",
            "1px 发丝边框分区,强调靠字重与边框粗细",
            "标签/数值/说明一律等宽字体",
            "图纸式精密对齐,无任何彩色",
        ],
        "negatives": [
            "不要任何颜色——强调色/品牌色/图表数据色全禁",
            "不要圆角/阴影/渐变/纹理/噪点",
            "不要把标签数值写成无衬线——一律等宽",
        ],
        "typo": {
            "title": "Geist 700(Inter 兜底)48pt,tracking -0.02em",
            "body": "Geist 400 30pt 级",
            "labels": "Geist Mono(IBM Plex Mono/JetBrains Mono 兜底)11pt",
        },
        "best_for": "黑白灰绝对单色的图纸式基础设施文档;适合架构设计/系统规格/工程交付",
    },
    "DD27": {
        "name": "电影感演讲风",
        "vd": "cinematic keynote on a pure black stage, one giant key visual per "
              "slide with minimal light-weight text, single amber accent, "
              "disciplined rhythm closing with a summary slide",
        "pairing": "企业摄影", "family": ("photographic", "core"),
        "anchors": {
            "primary": "#000000(纯黑舞台)",
            "secondary": "#0E0E0E(次级面板)",
            "accent": "#E8B341(琥珀唯一强调)",
            "neutral": "#F5F5F7(主文字白)",
        },
        "bg": ["#000000", "#0E0E0E"],
        "scenes": ["高规格发布会", "品牌影院叙事", "年度盛典", "愿景演讲"],
        "aliases": ["Cinematic Keynote Deck", "cinematic keynote", "影院演讲"],
        "composition": "纯黑舞台一页一大视觉,细字重大字,琥珀一点强调",
        "layout": [
            "纯黑 #000000 底,一页一大视觉 + 少量文字",
            "细字重(300)大号无衬线,文本 ≤3 行",
            "琥珀 #E8B341 唯一强调(KPI/刻度)",
            "结尾 summary 页收敛全 deck",
        ],
        "negatives": [
            "不要灰/藏青/CSS 渐变底——必须纯黑",
            "不要项目符号列表填页",
            "不要第二强调色或彩色正文",
        ],
        "typo": {
            "title": "Inter 300 64pt,tracking -0.02em",
            "body": "Inter 400 20pt 级",
            "labels": "Inter 400 琥珀小字刻度",
        },
        "best_for": "纯黑影院级一页一巨幕的克制演讲;适合高规格发布会/品牌叙事/年度盛典",
    },
    "DD29": {
        "name": "战略藏青风",
        "vd": "strategy consulting deck, layered two-blue system of deep navy and "
              "vivid blue on white, serif headings over sans body, 12-column "
              "grid with action titles and evidence modules",
        "pairing": "瑞士极简", "family": ("flat", "core"),
        "anchors": {
            "primary": "#FFFFFF(白底)",
            "secondary": "#F1F4F9(蓝灰面)",
            "accent": "#2563EB(鲜蓝强调)",
            "neutral": "#14213D(藏青墨字)",
        },
        "bg": ["#FFFFFF", "#F1F4F9"],
        "scenes": ["战略规划", "咨询建议书", "管理层汇报", "市场洞察"],
        "aliases": ["Strategy Navy Deck", "strategy navy", "藏青战略"],
        "composition": "藏青+鲜蓝+灰三档蓝色系层级,衬线标题 + 无衬线正文",
        "layout": [
            "每页顶部动作标题(完整结论句)",
            "藏青 + 鲜蓝 + 灰三档层级,不用蓝灰外色相",
            "衬线(PT Serif 系)标题 + 无衬线正文",
            "12 列网格证据模块",
        ],
        "negatives": [
            "不要蓝灰之外的色相——层级只用三档蓝灰",
            "动作标题不要退化为名词标签",
            "不要标题无衬线/正文衬线的反向混排",
        ],
        "typo": {
            "title": "PT Serif 700(Georgia/Source Serif 兜底)26pt",
            "body": "Inter 400",
            "labels": "Inter 600 kicker 11pt,tracking 0.08em",
        },
        "best_for": "双蓝层级 + 衬线标题的战略咨询语法;适合战略规划/咨询建议书/管理层汇报",
    },
    "DD32": {
        "name": "MBB幽灵框架风",
        "vd": "MBB ghost deck on pure white, action title as a complete "
              "declarative sentence over slate-gray body, weight-only "
              "emphasis, waterfall mece and 2x2 as native diagram grammar",
        "pairing": "瑞士极简", "family": ("diagram", "core"),
        "anchors": {
            "primary": "#FFFFFF(纯白底)",
            "secondary": "#C9CDD3(中性条/边框灰)",
            "accent": "#1F3A5F(石板蓝唯一强调)",
            "neutral": "#3D4350(正文灰墨)",
        },
        "bg": ["#FFFFFF"],
        "scenes": ["战略咨询", "问题分解", "高管简报", "批判性分析"],
        "aliases": ["MBB Ghost Deck", "mckinsey ghost", "幽灵草稿"],
        "composition": "纯白底 + 完整陈述句动作标题 + 石板灰正文,粗体即强调",
        "layout": [
            "纯白底 + 顶部完整陈述句动作标题 + 小字 kicker",
            "正文石板灰单色阶,文本强调只靠粗体",
            "石板蓝 1 色仅用于图表单条/单格/增量",
            "瀑布图/MECE 分解/2×2 为母语图式",
        ],
        "negatives": [
            "动作标题不要名词短语——必须是完整陈述句",
            "不要多色强调——文本强调只用粗体",
            "不要彩虹图表/图例盒/网格线/3D/圆角/阴影/渐变",
        ],
        "typo": {
            "title": "Inter 600 26pt 动作标题,leading 1.25",
            "body": "Inter 400 18pt,石板灰阶",
            "labels": "Inter 500 kicker 13pt,tracking 0.04em",
        },
        "best_for": "MBB 式动作标题 + 灰阶粗体强调的咨询语法;适合战略咨询/问题分解/高管简报",
    },
    "DD36": {
        "name": "粗块信息图风",
        "vd": "flat modernist infographic, charcoal amber and teal solid color "
              "blocks acting as nodes segments and cells themselves, borderless "
              "grid, oversized block numerals",
        "pairing": "扁平几何", "family": ("flat", "core"),
        "anchors": {
            "primary": "#FFFFFF(白底)",
            "secondary": "#2A2D34(炭黑块)",
            "accent": "#E8A317(琥珀块)",
            "neutral": "#6B6F76(次级灰字)",
        },
        "bg": ["#FFFFFF"],
        "scenes": ["流程再造", "组织架构", "阶段规划", "方案结构化呈现"],
        "aliases": ["Bold Block Infographic Deck", "bold block infographic", "色块信息图"],
        "composition": "炭/琥珀/青三色实色块本身就是节点/区间/格子,无边框平面构成",
        "layout": [
            "色块(炭/琥珀/青)本身就是节点/区间/格子",
            "无边框平面构成,圆角 ≤2px",
            "区块编号 64pt / 章节号 200pt 超大数字",
            "增减语义:青 #1F8A82 涨 / 红 #C0392B 跌",
        ],
        "negatives": [
            "不要黑色 1px 边框或硬投影(那是新粗野主义)",
            "不要 >2px 圆角/渐变/斜面/立体",
            "不要第四种颜色与彩虹图表",
        ],
        "typo": {
            "title": "Archivo 800(Arial Black 兜底)32pt",
            "body": "Archivo 400,白字置于色块上",
            "labels": "Archivo 700 区块编号 64pt",
        },
        "best_for": "三色实色块即图元的平面现代信息图;适合流程再造/组织架构/阶段规划",
    },
    "DD39": {
        "name": "档案索引风",
        "vd": "archival research catalog, paper-beige canvas with serif and "
              "monospace mix, every diagram indexed by mono numbers and rule "
              "lines like a library card catalogue",
        "pairing": "杂志编辑", "family": ("editorial", "core"),
        "anchors": {
            "primary": "#EFE9DD(纸米底)",
            "secondary": "#F6F2E8(卡面)",
            "accent": "#33302A(墨棕即强调,hatch 影线)",
            "neutral": "#7A7468(次级棕灰)",
        },
        "bg": ["#EFE9DD", "#F6F2E8"],
        "scenes": ["研究报告", "文献综述", "馆藏策展", "田野档案"],
        "aliases": ["Archival Index Deck", "archival index", "档案卡片"],
        "composition": "纸米底上等宽索引号标引一切,细规则线建立秩序",
        "layout": [
            "所有元素以等宽索引号(01/02/A1/B2)标引",
            "细规则线建立秩序,替代箭头连接",
            "衬线标题 + 等宽编号混排",
            "大号章节数字 120pt 级作背景",
        ],
        "negatives": [
            "不要彩色强调/CSS 渐变/发光——只有墨棕实色与影线 hatch",
            "不要圆角/阴影/立体——纸面平整见棱角",
            "不要箭头连接器——流程靠编号连续与规则线",
        ],
        "typo": {
            "title": "Source Serif 4 600(Georgia 兜底)26pt",
            "body": "Source Serif 400 正文",
            "labels": "IBM Plex Mono 500 13pt 索引号,tracking 0.04em",
        },
        "best_for": "图书馆卡片式索引编号的研究档案美学;适合研究报告/文献综述/馆藏策展",
    },
    "DD41": {
        "name": "BCG展板风",
        "vd": "BCG exhibit deck, every slide numbered Exhibit N.N in mono green "
              "at top-left, answer-first conclusion header, source footnote line "
              "at bottom, charts are the slide",
        "pairing": "瑞士极简", "family": ("diagram", "core"),
        "anchors": {
            "primary": "#FFFFFF(白底)",
            "secondary": "#F2F4F3(浅灰面)",
            "accent": "#177B57(BCG 绿唯一强调)",
            "neutral": "#1A1A1A(墨字)",
        },
        "bg": ["#FFFFFF", "#F2F4F3"],
        "scenes": ["咨询展板", "数据论证", "董事会材料", "洞察报告"],
        "aliases": ["BCG 익스히빗 덱", "BCG exhibit", "展板编号"],
        "composition": "左上 Exhibit 编号标签 + 首句结论页眉 + 底部来源行,图表即页面",
        "layout": [
            "左上 Exhibit 3.2 式等宽编号标签(绿)",
            "页首 answer-first 结论句,单结论",
            "底部 Source 脚注行",
            "图表/表即页面主体",
        ],
        "negatives": [
            "不要把 BCG 绿用作大面积底色——只用于强调文本/关键数据系/Exhibit 标签",
            "不要渐变/阴影/圆角/表情符号/剪贴画",
            "不要一页两个 takeaway",
        ],
        "typo": {
            "title": "IBM Plex Sans 700(Inter 兜底)28pt",
            "body": "IBM Plex Sans 400 16pt 级",
            "labels": "IBM Plex Mono 500 11pt Exhibit 标签,tracking 0.06em",
        },
        "best_for": "Exhibit 编号 + answer-first 的咨询展板语法;适合咨询报告/数据论证/董事会材料",
    },
    "DD43": {
        "name": "投行IR编辑风",
        "vd": "investment-bank IR editorial, deep navy full pages with off-white "
              "text, 0.5pt metallic gold hairlines framing headers sections and "
              "tables, transitional serif headings and aligned financial tables",
        "pairing": "杂志编辑", "family": ("editorial", "core"),
        "anchors": {
            "primary": "#0A1A33(深藏青底)",
            "secondary": "#1F3A5F(次级藏青面)",
            "accent": "#C8A24B(金 hairline)",
            "neutral": "#E8E5DE(米白文字)",
        },
        "bg": ["#0A1A33", "#1F3A5F"],
        "scenes": ["投资者关系", "财报发布", "并购材料", "金融简报"],
        "aliases": ["골드만 IR 덱", "goldman IR", "投行投资者关系"],
        "composition": "深藏青整版 + 米白文字,0.5pt 金发丝线划分一切",
        "layout": [
            "深藏青 #0A1A33 整版 + 米白文字",
            "0.5pt 金 #C8A24B 发丝线划分页眉/节/表",
            "过渡衬线(Source Serif 系)标题 + 对齐财务表",
            "金只用于 hairline/标签/图表关键系",
        ],
        "negatives": [
            "不要把金色用作大面积/按钮底——只在 hairline 与关键数据",
            "标题不要用无衬线——过渡衬线是身份",
            "不要渐变/光晕/阴影/圆角/表情",
        ],
        "typo": {
            "title": "Source Serif 4 600(Georgia 兜底)26pt",
            "body": "Inter 400 17pt,leading 1.4",
            "labels": "Inter 500 11pt 节标签,tracking 0.08em",
        },
        "best_for": "深藏青 + 0.5pt 金线的投行 IR 编辑气质;适合投资者关系/财报发布/并购材料",
    },
    "DD44": {
        "name": "黄金网格演讲风",
        "vd": "golden-ratio keynote, every slide skeleton divided by the 1:1.618 "
              "grid governing image blocks text columns whitespace and type "
              "scale, monochrome plus one muted gold accent",
        "pairing": "企业摄影", "family": ("photographic", "core"),
        "anchors": {
            "primary": "#FAFAF8(暖白底)",
            "secondary": "#161616(墨黑结构)",
            "accent": "#B5A642(哑金一点)",
            "neutral": "#6E6E68(灰)",
        },
        "bg": ["#FAFAF8"],
        "scenes": ["品牌年报", "设计演讲", "高端产品叙事", "作品集"],
        "aliases": ["Every 골든 그리드 키노트", "golden grid keynote", "黄金比例"],
        "composition": "1:1.618 黄金比例分割统摄版面骨架与字号尺度",
        "layout": [
            "1:1.618 黄金比例分割统摄版面骨架",
            "图块/文字列/留白/字号全部按黄金尺度",
            "无彩色 + 哑金 #B5A642 一点强调",
            "大图块与文字列交替",
        ],
        "negatives": [
            "不要违背黄金比例的任意分栏",
            "不要第二强调色",
            "不要高饱和与渐变",
        ],
        "typo": {
            "title": "Inter 600 55pt(Helvetica Neue 兜底),tracking -0.01em",
            "body": "Inter 400,leading 1.15",
            "labels": "Inter 500 副题 34pt 级",
        },
        "best_for": "黄金比例网格统摄的高档 keynote;适合品牌年报/设计演讲/作品集",
    },
    "DD45": {
        "name": "图案海报演讲风",
        "vd": "bold poster keynote, each slide flooded edge-to-edge by one "
              "saturated solid electric blue or vermillion, gigantic condensed "
              "sans headline, minimal static components",
        "pairing": "复古海报", "family": ("flat", "core"),
        "anchors": {
            "primary": "#1F3DFF(电蓝整页)",
            "secondary": "#FF4D2E(朱红整页/交替)",
            "accent": "#FF4D2E(交替强调)",
            "neutral": "#FFFFFF(白字/墨 #0E0E0E)",
        },
        "bg": ["#1F3DFF", "#FF4D2E"],
        "scenes": ["创意提案", "campaign 发布", "艺术演讲", "青年品牌"],
        "aliases": ["Pattern 볼드 포스터 키노트", "pattern bold poster", "整页海报"],
        "composition": "整页单一高饱和平涂色 + 巨型紧缩无衬线标题,翻页换色",
        "layout": [
            "整页单一高饱和色(电蓝 #1F3DFF 或朱红 #FF4D2E),翻页交替",
            "巨型紧缩无衬线标题 90-140px",
            "组件极简、静态,一页一主张",
            "左右分割对比页是唯一双色例外",
        ],
        "negatives": [
            "不要一页两种以上面色(左右分割对比页除外)",
            "不要渐变/照片/表情/剪贴画",
            "不要小标题——必须巨型",
        ],
        "typo": {
            "title": "Anton 400(Arial Black 兜底)105pt 级",
            "body": "Archivo 600 副题 24pt",
            "labels": "Archivo 600 标签 13pt,tracking 0.08em",
        },
        "best_for": "整页平涂高饱和色的海报式 keynote;适合创意提案/campaign 发布/艺术演讲",
    },
    "DD51": {
        "name": "集团IR克制风",
        "vd": "korean chaebol quarterly IR, restrained global-enterprise tone, "
              "white body pages alternating with deep-navy photo pages, single "
              "corporate-blue accent, one-line horizontal table rules",
        "pairing": "瑞士极简", "family": ("diagram", "core"),
        "anchors": {
            "primary": "#FFFFFF(白正文页)",
            "secondary": "#06122A(深藏青图页)",
            "accent": "#0028A8(集团蓝唯一强调)",
            "neutral": "#010821(墨字标题)",
        },
        "bg": ["#FFFFFF", "#06122A"],
        "scenes": ["集团财报", "季度 IR", "年度业绩", "法人说明会"],
        "aliases": ["삼성전자 IR 절제", "samsung IR restrained", "集团财报"],
        "composition": "白底正文页与深藏青图页交替,强调仅一色,表格单横线",
        "layout": [
            "白底正文页与深藏青 #06122A 图页交替",
            "强调仅 #0028A8 一色,用于关键数字与单一图表系",
            "表格只用横向单线整理",
            "以数据表与全幅图为主,几乎不用传统图解",
        ],
        "negatives": [
            "不要用旧值 #1428A0——强调色实测 #0028A8 唯一",
            "不要把集团蓝用作大面积/封面整版",
            "不要亮蓝/天蓝/靛/青等蓝色变奏",
        ],
        "typo": {
            "title": "Manrope 700(Inter 兜底)34-36pt",
            "body": "Manrope 400;节标签 14pt",
            "labels": "Manrope 600 节标签;表格头 #5C6B90",
        },
        "best_for": "韩国大集团季度 IR 的克制语法:单蓝强调 + 单横线表;适合集团财报/季度 IR/业绩说明",
    },
    "DD52": {
        "name": "星幕金字塔风",
        "vd": "monochrome-blue annual report like SKT, starlight cover with big "
              "english slogan and a dimensional pyramid diagram as signature, "
              "interactive tab-menu chrome, single-blue vision tone",
        "pairing": "瑞士极简", "family": ("diagram", "core"),
        "anchors": {
            "primary": "#FFFFFF(白底)",
            "secondary": "#E4EEFB(浅蓝面)",
            "accent": "#0010A7(深蓝主强调)",
            "neutral": "#000000(墨字)",
        },
        "bg": ["#FFFFFF", "#E4EEFB"],
        "scenes": ["科技企业年报", "AI 战略", "愿景发布", "技术路线图"],
        "aliases": ["SKT 인터랙티브 AI 피라미드", "SKT interactive AI pyramid", "单色蓝金字塔"],
        "composition": "星空封面 + 立体金字塔图为签名,单色蓝统一,PDF 标签页 chrome",
        "layout": [
            "星空/深蓝封面 + 大号英文标语",
            "立体金字塔图承载 AI 战略层级",
            "页面顶部悬浮标签页菜单(交互报告审美)",
            "单色蓝 #0010A7 统一,红色 #EA002C 仅 logo 位",
        ],
        "negatives": [
            "不要把红 #EA002C 用于正文/图形(仅 logo wordmark)",
            "不要多色系——单色蓝家族是身份",
            "不要手绘/插画装饰",
        ],
        "typo": {
            "title": "Pretendard 500(Noto Sans KR/Inter 兜底)130pt 封面字",
            "body": "Pretendard 400 正文",
            "labels": "Pretendard 600 章节 slate 字 150pt 级",
        },
        "best_for": "单色蓝星空金字塔的科技企业年报审美;适合 AI 战略/愿景发布/技术路线图",
    },    "DD55": {
        "name": "卡片新闻财报风",
        "vd": "conservative quarterly-earnings analyst deck, gray canvas with one "
              "or two yellow accents, half-pill title tab on the left, "
              "quarter-compare tables with a red box highlight on the current "
              "quarter",
        "pairing": "摘要信息图卡", "family": ("flat", "core"),
        "anchors": {
            "primary": "#F2F2F2(灰底)",
            "secondary": "#FFFFFF(卡面白)",
            "accent": "#FAE232(黄强调一两点)",
            "neutral": "#000000(墨字)",
        },
        "bg": ["#F2F2F2"],
        "scenes": ["季度业绩", "分析师简报", "财务速览", "卡式新闻"],
        "aliases": ["카카오 1Q26 보수 IR", "kakao conservative earnings", "卡新闻财报"],
        "composition": "灰底 + 黄一两点强调 + 左端半胶囊标题条 + 红框圈本季",
        "layout": [
            "灰底 #F2F2F2 + 黄 #FAE232 一两点强调",
            "左端半胶囊标题条(半 pill)",
            "季度对比表:本季格红 #FF0000 框圈注",
            "红/黄仅作圈注与涨跌语义,不进正文文字",
        ],
        "negatives": [
            "不要高饱和大面色——灰底黄点是保守气质",
            "不要装饰插画与圆角卡堆叠",
            "不要把黄/红用于正文文字",
        ],
        "typo": {
            "title": "Pretendard 700(Noto Sans KR 兜底)40pt",
            "body": "Pretendard 400",
            "labels": "Pretendard 800 封面 logo 字",
        },
        "best_for": "灰底黄点的保守季度业绩卡式新闻;适合季度 IR/分析师简报/财务速览",
    },
    "DD56": {
        "name": "政策口号书法风",
        "vd": "korean government vision poster, giant hangul calligraphy slogan "
              "fullscreen on dark navy, korean-peninsula and world map "
              "infographics, hero silhouettes and big number cards",
        "pairing": "水墨笔记", "family": ("hand-drawn", "core"),
        "anchors": {
            "primary": "#001838(深藏青整版)",
            "secondary": "#003070(深蓝变体面)",
            "accent": "#0060C0(亮蓝强调)",
            "neutral": "#FFFFFF(白字)",
        },
        "bg": ["#001838", "#003070"],
        "scenes": ["政府愿景发布", "政策口号", "部门业绩宣传", "公共倡议"],
        "aliases": ["산업통상부 슬로건 캘리그래피", "MOTIE slogan", "政府口号海报"],
        "composition": "巨型韩文书法口号整屏 + 地图信息图 + 英雄剪影 + 大数字卡",
        "layout": [
            "巨型韩文书法手写口号整屏(64-96pt 视觉质量)",
            "韩半岛/世界地图信息图与英雄剪影",
            "大数字卡片承载政绩",
            "浅蓝/浅青辅助页与深蓝整版交替",
        ],
        "negatives": [
            "不要普通商务报告的表/柱图主体——口号/地图/剪影/大数字是主角",
            "不要 CSS 渐变与模糊底(光效用预渲染位图)",
            "不要粉彩消费风/亲切插画/表情符号",
        ],
        "typo": {
            "title": "韩文书法体口号(Pretendard Black 兜底)64-96pt",
            "body": "Pretendard Medium(Noto Sans KR 兜底)18-22pt",
            "labels": "Pretendard ExtraBold 标题 34-44pt",
        },
        "best_for": "巨型书法口号 + 地图信息图的政府愿景海报;适合政策发布/部门宣传/公共倡议",
    },
    "DD57": {
        "name": "韩式政府浅蓝风",
        "vd": "korean government light-tone briefing, pale sky-blue ground with "
              "deep navy text, navy ribbon at page bottom exposing key words, "
              "governance satellite-node diagram as climax",
        "pairing": "瑞士极简", "family": ("diagram", "core"),
        "anchors": {
            "primary": "#E7F1FA(浅天蓝底)",
            "secondary": "#FFFFFF(卡面白)",
            "accent": "#0F41BD(深亮蓝强调)",
            "neutral": "#1C2848(深墨蓝字)",
        },
        "bg": ["#E7F1FA", "#FFFFFF"],
        "scenes": ["政府简报", "公共治理", "部委汇报", "政策沟通"],
        "aliases": ["과기정통부 정부 라이트", "korea gov light", "政府浅蓝简报"],
        "composition": "浅天蓝底 + 深藏青文字,页底藏青带露关键词,治理卫星图作高潮",
        "layout": [
            "浅天蓝 #E7F1FA 底 + 深藏青文字",
            "页底 11% 藏青带露出核心关键词",
            "中央部委节点 + 卫星节点治理图是高潮页",
            "浓色只用于底带与标题",
        ],
        "negatives": [
            "不要暗色高级主题——本风格是浅色正统政府调",
            "不要高饱和商业配色",
            "不要花哨装饰字体",
        ],
        "typo": {
            "title": "Pretendard 800(Noto Sans KR 兜底)58pt 封面主标",
            "body": "Pretendard 400 正文",
            "labels": "Pretendard 500 meta 标签 16pt",
        },
        "best_for": "浅天蓝正统政府轻调简报;适合政府简报/公共治理/部委汇报",
    },
}

KEEP_WEST: dict[str, dict] = {
    "04": {
        "name": "暗黑学院风",
        "vd": "dark academia library plate, deep warm brown ground with antique "
              "gold italic serif titles, double inset border frames, monospace "
              "footnotes and thin gold ornament rules, scholarly texture",
        "pairing": "杂志编辑", "family": ("editorial", "core"),
        "anchors": {
            "primary": "#1A1208(深暖棕底)",
            "secondary": "#3D2E10(暗金边框/饰线)",
            "accent": "#C9A84C(古金斜衬线标题)",
            "neutral": "#D4BF9A(羊皮纸正文)",
        },
        "bg": ["#1A1208", "#0E0A05"],
        "scenes": ["人文学术", "经典阅读", "校史叙事", "书卷品牌"],
        "aliases": ["Dark Academia", "暗黑学术", "学院古典"],
        "composition": "双内嵌边框 + 金色斜衬线标题 + 等宽脚注的学院版画",
        "layout": [
            "双内嵌边框(外+内不同粗细),距页边 12-20pt",
            "金色斜衬线大标题,宽字距 6-10pt",
            "衬线正文 1.6-1.8 行距,装饰金色细规线",
            "等宽小字脚注/日期,哑金 #8A7340",
        ],
        "negatives": [
            "不要现代无衬线字体",
            "不要明亮高饱和色",
            "不要干净极简排版——保留纹理与装饰",
        ],
        "typo": {
            "title": "Playfair Display Italic(Georgia Italic 兜底)36-48pt",
            "body": "EB Garamond(Georgia 兜底)13-16pt",
            "labels": "Space Mono 9-11pt 宽字距脚注",
        },
        "best_for": "深棕金饰的学院古典书卷气;适合人文学术/经典叙事/书卷品牌",
    },
    "23": {
        "name": "彩窗马赛克风",
        "vd": "stained-glass mosaic slide, full-bleed cell grid with 2pt "
              "near-black grout gaps, royal blue crimson gold green purple "
              "cells never repeating adjacently, translucent dark overlay "
              "unifying the field",
        "pairing": "玻璃拟态", "family": ("glass", "core"),
        "anchors": {
            "primary": "#0A0A12(近黑格缝底)",
            "secondary": "#1A3A6E(皇室蓝格)",
            "accent": "#E63030(绯红格)",
            "neutral": "#F5D020(金黄格)",
        },
        "bg": ["#0A0A12"],
        "scenes": ["文化艺术", "博物馆叙事", "宗教历史", "装饰主题"],
        "aliases": ["Stained Glass Mosaic", "彩窗玻璃", "花窗"],
        "composition": "满版马赛克格阵 + 2pt 深色格缝 + 半透明深色叠层统一",
        "layout": [
            "6×4 等网格满版,格间 2pt 深色缝(#0A0A12 作 grout)",
            "相邻格不同色,按彩窗节奏配蓝/红/金/绿/紫",
            "半透明深色叠层压暗统一画面",
            "标题作宽字距衬线叠字置底(Cormorant/Trajan 系)",
        ],
        "negatives": [
            "不要粉彩或低饱和格子",
            "不要大片空格",
            "不要无衬线叠字标题",
        ],
        "typo": {
            "title": "Cormorant Garamond Bold(Trajan 兜底)16-22pt 宽字距叠字",
            "body": "Georgia 13-15pt,置于叠层之下",
            "labels": "Georgia 小字图注",
        },
        "best_for": "彩窗玻璃格阵的教堂彩绘美学;适合文化艺术/博物馆叙事/装饰主题",
    },
}

KEEP_OFFICECLI: dict[str, dict] = {
    "dark--liquid-flow": {
        "name": "流光液态风",
        "vd": "fluid light effects, deep purple night ground with overlapping "
              "multicolor translucent ellipses mixing like liquid, brand-upgrade "
              "avant-garde premium",
        "pairing": "玻璃拟态", "family": ("glass", "core"),
        "anchors": {
            "primary": "#0F0F2D(深紫夜底)",
            "secondary": "#6C63FF(紫罗兰主光斑)",
            "accent": "#48E5C2(薄荷辅助光斑)",
            "neutral": "#F5F5FF(标题白)",
        },
        "bg": ["#0F0F2D"],
        "scenes": ["品牌升级", "创意发布", "时尚展示", "高端产品"],
        "aliases": ["Liquid Light", "液态流光", "liquid flow"],
        "composition": "多色大椭圆不同透明度叠压混色,似液体流动",
        "layout": [
            "4 大椭圆(12-14cm)+ 3 小滴(3-4cm),多色不同透明度 0.28-0.55,带旋转",
            "叠色混合造深度,似液体流动",
            "morph 时光斑大幅位移(10-15cm)+ 旋转变化",
            "文字置于光心或深底,辅色珊瑚 #FF6B8A/电蓝 #3D5AFE/琥珀 #F5AF19 点缀小滴",
        ],
        "negatives": [
            "不要高对比硬边几何——光斑必须柔边",
            "不要单一颜色光斑——多色混合是身份",
            "不要亮底",
        ],
        "typo": {
            "title": "Segoe UI(苹方 PingFang 兜底)大标题,白 #F5F5FF",
            "body": "Segoe UI 正文,淡蓝 #C8C8FF",
            "labels": "Segoe UI 小字,辅助灰 #8888CC",
        },
        "best_for": "深紫夜底多色液态光斑的前卫品牌质感;适合品牌升级/创意发布/时尚展示",
        "pptx": "dark__liquid_flow.pptx",
    },
    "dark--sage-grain": {
        "name": "鼠尾草谷物暗纹风",
        "vd": "creative-agency organic dark, sage-grey green ground with grain "
              "noise texture and sparkle cross motifs, extreme bold titles with "
              "gradient fade, elevated white card panels",
        "pairing": "企业摄影", "family": ("photographic", "core"),
        "anchors": {
            "primary": "#1E2720(鼠尾草灰绿暗底)",
            "secondary": "#FFFFFF(白卡面)",
            "accent": "#D9B88F(暖米强调)",
            "neutral": "#8A9088(灰绿次级字)",
        },
        "bg": ["#1E2720"],
        "scenes": ["创意机构", "精品咨询", "有机品牌", "设计工作室"],
        "aliases": ["Sage Grain", "谷物暗纹", "暗调鼠尾草"],
        "composition": "暗绿灰底 + 噪点纹理 + 十字星母题 + 白色浮卡",
        "layout": [
            "暗绿灰底 + 低透明(0.02-0.03)散点椭圆噪点纹理",
            "四线十字星(0.08cm 线径)作装饰母题",
            "56-64pt 超粗标题带 textFill 渐隐",
            "白色 roundRect 卡片承载内容;暗底整页 → 白卡 → 大数字页交替节奏",
        ],
        "negatives": [
            "不要高饱和撞色——保持有机克制",
            "不要纯平无纹理的底",
            "不要细字重正文",
        ],
        "typo": {
            "title": "Segoe UI 56-64pt 超粗(苹方兜底),白字带渐隐",
            "body": "Segoe UI 14pt,置于白卡",
            "labels": "Segoe UI 9-10pt 大写小节标签(苹方兜底),金 #C9A86A 点缀",
        },
        "best_for": "暗调鼠尾草 + 谷物噪点的创意机构质感;适合创意机构/精品咨询/有机品牌",
    },
    "dark--spotlight-stage": {
        "name": "聚光舞台风",
        "vd": "stage spotlight keynote, near-black theatre with large warm "
              "elliptical spotlight beams and layered halos, text set inside "
              "the lit centre, dark zones left empty",
        "pairing": "暖光场景", "family": ("photographic", "core"),
        "anchors": {
            "primary": "#0A0A0A(近黑舞台)",
            "secondary": "#FFFFFF(聚光白文字)",
            "accent": "#FFE0B2(暖金光束)",
            "neutral": "#FFFFFF(暗场白字锚)",
        },
        "bg": ["#0A0A0A"],
        "scenes": ["主题演讲", "产品发布", "年度盛典", "颁奖礼"],
        "aliases": ["Spotlight Stage", "聚光灯舞台", "舞台光"],
        "composition": "近黑剧场 + 大椭圆暖光束多层光晕,文字置光心,暗区留空",
        "layout": [
            "大椭圆光斑 + 多层椭圆光晕(亮心淡缘)模拟光束扩散",
            "光斑页间大幅位移(15cm+)似扫光",
            "文字置于光心,暗区留空引导视线",
            "rect 作舞台元素(地线/文字面板)",
        ],
        "negatives": [
            "不要亮底或多彩光——暖白/金单色系光",
            "不要满页均匀照明——明暗对比即构图",
            "不要在暗区放正文",
        ],
        "typo": {
            "title": "Segoe UI 大标题(苹方兜底),聚光白 #FFFFFF",
            "body": "Segoe UI 正文(苹方兜底),置于光心",
            "labels": "Segoe UI 小字刻度(苹方兜底),暖金 #FFE0B2",
        },
        "best_for": "剧场聚光式戏剧化演讲;适合主题演讲/产品发布/年度盛典",
        "pptx": "dark__spotlight_stage.pptx",
    },
    "dark--diagonal-cut": {
        "name": "斜切重工风",
        "vd": "industrial diagonal cut, near-black ground criss-crossed by "
              "30-45 degree rotated rectangle slashes in orange white and "
              "yellow, ultra-thin cut lines and corner circle accents, rugged "
              "power",
        "pairing": "丝网印刷", "family": ("collage", "core"),
        "anchors": {
            "primary": "#1A1A1A(近黑底)",
            "secondary": "#FFCC00(警示黄斜条)",
            "accent": "#FF6600(工业橙主斜条)",
            "neutral": "#CCCCCC(浅灰副字)",
        },
        "bg": ["#1A1A1A"],
        "scenes": ["工业制造", "工程建设", "机械汽车", "硬核发布"],
        "aliases": ["Diagonal Cut", "斜切工业", "工业斜切"],
        "composition": "30-45° 大斜条旋转贯穿 + 超细切割线 + 角部圆点",
        "layout": [
            "4 条 30-45° 大斜条旋转贯穿版面(主色 0.85-0.9,辅色 0.15-0.3)",
            "2 条 0.1-0.15cm 超细切割线横贯全宽",
            "角落双圆点缀平衡几何",
            "morph:斜条旋 20-25° + 位移 8-12cm;内容页斜条收拢为近垂直分栏(散→序)",
        ],
        "negatives": [
            "不要水平垂直的正交网格——斜切即身份",
            "不要柔和粉彩——高对比工业色",
            "不要细线密网",
        ],
        "typo": {
            "title": "Segoe UI Black 64-72pt(苹方兜底),白/橙",
            "body": "Segoe UI 14-24pt(苹方兜底),浅灰 #CCCCCC",
            "labels": "Segoe UI Black 数据数字 48-64pt(苹方兜底)",
        },
        "best_for": "工业斜切的力量感深色版面;适合工业制造/工程建设/硬核发布",
        "pptx": "dark__diagonal_cut.pptx",
    },
    "mixed--chromatic-aberration": {
        "name": "色差故障风",
        "vd": "CRT chromatic aberration, ultra-dark navy with triple-layer text "
              "offset in hot pink and cyan around a white core, ghostly RGB "
              "split morphing from tight to maximum spread",
        "pairing": "发光扫描渲染", "family": ("dashboard", "core"),
        "anchors": {
            "primary": "#050814(超暗藏青底)",
            "secondary": "#00F5E4(青色偏差层)",
            "accent": "#FF0066(粉色偏差层)",
            "neutral": "#FFFFFF(白色主文字层)",
        },
        "bg": ["#050814", "#0A1030"],
        "scenes": ["科技创业", "AI 平台", "开发者工具", "先锋产品发布"],
        "aliases": ["Chromatic Aberration", "CRT 色差", "RGB 分离"],
        "composition": "同一文字三层渲染:粉左偏/青右偏/白居中,鬼影式 RGB 分离",
        "layout": [
            "同一文字三层渲染:粉 #FF0066 左偏 / 青 #00F5E4 右偏 / 白居中",
            "偏差距离跨页 morph(0.3cm→1.5cm→4cm→0→纵移→归位)",
            "鬼影层透明度 0.20-0.45 随扩散降低",
            "0.10cm 细线青/粉双色极简装饰",
        ],
        "negatives": [
            "不要亮底——超暗底是霓虹可感的前提",
            "不要四层以上文字叠印",
            "不要装饰图形堆砌——文字即演员",
        ],
        "typo": {
            "title": "Segoe UI Black 68pt 三层叠印(苹方兜底)",
            "body": "Segoe UI 13-14pt(苹方兜底)",
            "labels": "Segoe UI 10pt 大写节标签(苹方兜底);统计 18pt",
        },
        "best_for": "CRT 色差 RGB 分离的故障美学;适合科技创业/AI 平台/开发者工具",
    },
    "vivid--pink-editorial": {
        "name": "粉紫编辑风",
        "vd": "pink editorial gradient stats, dark-purple to dusty-rose 135 "
              "degree gradient ground with massive 160-200pt editorial "
              "numerals, grain scatter and gradient sweep actors",
        "pairing": "杂志编辑", "family": ("editorial", "core"),
        "anchors": {
            "primary": "#160B33(深紫渐变端)",
            "secondary": "#7B2D52(dusty rose 渐变端)",
            "accent": "#C85080(粉渐变叠加)",
            "neutral": "#FFFFFF(白主文字)",
        },
        "bg": ["#160B33", "#7B2D52"],
        "scenes": ["年度报告", "数据新闻", "编辑出版", "高层摘要"],
        "aliases": ["Pink Editorial", "粉紫渐变编辑", "gradient stats"],
        "composition": "深紫-玫瑰渐变底 + 160-200pt 巨号编辑数字 + 颗粒扫光",
        "layout": [
            "73%/99.2% 式 160-200pt 巨号编辑数字为主视觉",
            "半透明渐变矩形(0.35-0.40)扫过页面",
            "11 颗白椭圆 0.04 透明度模拟颗粒",
            "2×2 数据格与引言页圆形渐变叠层",
        ],
        "negatives": [
            "不要浅底或低对比——白粗字压深渐变",
            "不要小号主数字——尺寸即戏剧",
            "不要写实照片主体",
        ],
        "typo": {
            "title": "Segoe UI Black 28-36pt(苹方兜底)",
            "body": "Segoe UI 14-22pt(苹方兜底),米白 #F5E8F0",
            "labels": "Segoe UI Black 巨号数字 160-200pt(苹方兜底)",
        },
        "best_for": "深紫玫瑰渐变 + 巨号统计数字的编辑风;适合年度报告/数据新闻/高层摘要",
    },
    "warm--earth-organic": {
        "name": "大地有机风",
        "vd": "earth and sage sustainability, warm cream ground with clay brown "
              "and sage green accents, eco sincere natural mood, organic "
              "rounded shapes",
        "pairing": "自然有机", "family": ("hand-drawn", "supportive"),
        "anchors": {
            "primary": "#F5F0E8(暖米底)",
            "secondary": "#8B6F47(黏土棕主墨)",
            "accent": "#A8C686(鼠尾草绿点缀)",
            "neutral": "#8B6F47(深字锚,同主墨)",
        },
        "bg": ["#F5F0E8"],
        "scenes": ["环保可持续", "有机品牌", "农业食品", "ESG 叙事"],
        "aliases": ["Earth & Sage", "大地鼠尾草", "生态有机"],
        "composition": "暖米底 + 黏土棕主墨 + 鼠尾草绿点缀三色纪律",
        "layout": [
            "暖米底 + 黏土棕主墨 + 鼠尾草绿点缀三色纪律",
            "有机圆角形状与手绘感图形",
            "自然摄影/插画承载生态主题",
            "低对比柔和分区",
        ],
        "negatives": [
            "不要霓虹/高饱和工业色",
            "不要锐利几何与硬阴影",
            "不要冷调蓝紫主导",
        ],
        "typo": {
            "title": "Segoe UI(苹方 PingFang 兜底)标题,黏土棕 #8B6F47",
            "body": "Segoe UI 正文(苹方兜底),暖调深字",
            "labels": "Segoe UI 小标签(苹方兜底),鼠尾草绿 #A8C686",
        },
        "best_for": "大地色有机可持续的诚恳气质;适合环保叙事/有机品牌/ESG 报告",
        "pptx": "warm__earth_organic.pptx",
    },
}

# ---------------------------------------------------------------------------
# SKIP decisions (concept-level dedupe). leo = existing style covering the
# concept; reason explains the overlap judgment (C-batch parallel additions
# are marked as such).
# ---------------------------------------------------------------------------
SKIP_WEST: dict[str, dict] = {
    "01": {"leo": "玻璃拟态风", "reason": "glassmorphism 概念已覆盖"},
    "02": {"leo": "新粗野主义风", "reason": "neo-brutalism 概念已覆盖"},
    "03": {"leo": "便当格卡片风", "reason": "bento 概念已被 C 系并行批收录"},
    "05": {"leo": "有机渐变形风", "reason": "mesh 渐变概念已被 C 系并行批收录"},
    "06": {"leo": "—", "reason": "claymorphism 源无深色文字锚,保真门不可过"},
    "07": {"leo": "瑞士网格风", "reason": "swiss 概念已覆盖"},
    "08": {"leo": "极光风", "reason": "aurora neon 概念已覆盖"},
    "09": {"leo": "Y2K铬金属风", "reason": "Y2K 概念已覆盖"},
    "10": {"leo": "北欧风", "reason": "名称与终端配色系北欧风冲突"},
    "11": {"leo": "大字报巨型排版风", "reason": "typographic bold 概念已覆盖"},
    "12": {"leo": "珊瑚紫双色调风", "reason": "duotone 概念已被 C 系并行批收录"},
    "13": {"leo": "静奢极简风", "reason": "monochrome luxury 概念已覆盖"},
    "14": {"leo": "—", "reason": "cyberpunk outline 源仅 1 个 HEX,四角色锚不足"},
    "15": {"leo": "深色编辑报告风", "reason": "editorial magazine 概念已覆盖"},
    "16": {"leo": "奶油温柔风", "reason": "pastel soft UI 概念已覆盖"},
    "17": {"leo": "蒸汽波风", "reason": "synthwave 概念已覆盖"},
    "18": {"leo": "温暖手工风", "reason": "hand-crafted organic 概念已覆盖"},
    "19": {"leo": "微立体轻拟态风", "reason": "isometric flat 概念已覆盖"},
    "20": {"leo": "蒸汽波风", "reason": "vaporwave 概念已覆盖"},
    "21": {"leo": "装饰艺术风", "reason": "art deco 概念已覆盖"},
    "22": {"leo": "粗野报刊风", "reason": "brutalist newspaper 概念已覆盖"},
    "24": {"leo": "流光液态风", "reason": "liquid blob 与本批 OfficeCLI liquid-flow 同概念"},
    "25": {"leo": "孟菲斯风", "reason": "memphis 概念已覆盖"},
    "26": {"leo": "暗夜植物园风", "reason": "dark forest 概念已被 C 系并行批收录"},
    "27": {"leo": "工程蓝图风", "reason": "blueprint 概念已覆盖"},
    "28": {"leo": "波普艺术风", "reason": "maximalist collage 与波普拼贴/并行便利贴拼贴风双重相邻"},
    "29": {"leo": "全息棱镜科技风", "reason": "holographic HUD 概念已覆盖"},
    "30": {"leo": "里索印刷风", "reason": "risograph 概念已覆盖"},
    "31": {"leo": "清爽专业风", "reason": "executive minimal 概念已覆盖"},
    "32": {"leo": "雾感鼠尾草风", "reason": "sage professional 概念已覆盖"},
    "33": {"leo": "暗黑科技风", "reason": "modern dark 概念已覆盖"},
    "34": {"leo": "商务几何风", "reason": "corporate blue 概念已覆盖"},
    "35": {"leo": "暖调柔形风", "reason": "warm neutral 概念已覆盖"},
}

SKIP_KO: dict[str, dict] = {
    "DD03": {"leo": "黑白杂志风", "reason": "韩式编辑杂志概念与 C 系并行批黑白杂志/柔彩衬线编辑相邻"},
    "DD04": {"leo": "新粗野主义风", "reason": "네오브루탈리즘 概念已覆盖"},
    "DD05": {"leo": "玻璃拟态风", "reason": "글래스모피즘 概念已覆盖"},
    "DD07": {"leo": "暗黑科技风", "reason": "dark tech 概念已覆盖"},
    "DD08": {"leo": "手绘白板风", "reason": "hand-drawn sketch 概念已覆盖"},
    "DD10": {"leo": "锐利黑白风", "reason": "monochrome risk 黑白单色概念相邻,且本批已收 DD24"},
    "DD11": {"leo": "孟菲斯新潮风", "reason": "90s memphis retro 概念已覆盖"},
    "DD14": {"leo": "深色弥散风", "reason": "vivid gradient future 渐变弥散概念已覆盖"},
    "DD15": {"leo": "粗野报刊风", "reason": "print-first newspaper 与并行深蓝红新闻编辑风相邻"},
    "DD16": {"leo": "瑞士网格风", "reason": "swiss editorial bold 概念已覆盖"},
    "DD17": {"leo": "包豪斯风", "reason": "bauhaus geometric 概念已覆盖"},
    "DD18": {"leo": "多巴胺活力撞色风", "reason": "expressive material 撞色概念已覆盖"},
    "DD19": {"leo": "金融奢华风", "reason": "luxury serif 编辑概念已覆盖"},
    "DD20": {"leo": "快消营销风", "reason": "startup pitch colorful 概念已覆盖"},
    "DD22": {"leo": "暗黑科技风", "reason": "engineered dark 概念已覆盖"},
    "DD25": {"leo": "深色弥散风", "reason": "expressive soundwave 渐变声波概念相邻"},
    "DD26": {"leo": "杂志衬线风", "reason": "editorial product 衬线编辑概念已覆盖"},
    "DD28": {"leo": "多巴胺活力撞色风", "reason": "confident color-block 撞色概念已覆盖"},
    "DD30": {"leo": "静奢极简风", "reason": "heritage luxury 概念已覆盖"},
    "DD31": {"leo": "微立体轻拟态风", "reason": "isometric platform 概念已覆盖"},
    "DD33": {"leo": "蓝晒图纸风", "reason": "blueprint schematic 概念已覆盖"},
    "DD34": {"leo": "杂志衬线风", "reason": "editorial infographic 编辑信息图概念已覆盖"},
    "DD35": {"leo": "深色弥散风", "reason": "vivid gradient infographic 渐变概念已覆盖"},
    "DD37": {"leo": "暗黑科技风", "reason": "prismatic dark 棱镜深色概念已覆盖"},
    "DD38": {"leo": "奶油温柔风", "reason": "soft pastel system 概念已覆盖"},
    "DD40": {"leo": "暖调柔形风", "reason": "warm minimal diagram 概念已覆盖"},
    "DD42": {"leo": "BCG展板风", "reason": "bain results 与本批 DD41 同为 MBB 展板语法"},
    "DD46": {"leo": "杂志大字风", "reason": "ultramodern keynote 超大字概念已覆盖"},
    "DD47": {"leo": "极简奢侈品牌风", "reason": "kula lookbook 极简 lookbook 概念已覆盖"},
    "DD48": {"leo": "黑金期刊风", "reason": "epoch premium 深色金概念已覆盖"},
    "DD49": {"leo": "创意杂志风", "reason": "folio portfolio 概念已覆盖"},
    "DD50": {"leo": "暗夜奢华风", "reason": "dark luxury keynote 概念已覆盖"},
    "DD53": {"leo": "电影感演讲风", "reason": "hyundai cinematic 与本批 DD27 同为 cinematic keynote"},
    "DD54": {"leo": "集团IR克制风", "reason": "naver 综合报告与本批 DD51 同为韩企财报 IR"},
    "DD58": {"leo": "韩式政策报告风", "reason": "财政 cinematic 简报与 DD06/57 韩政府系相邻,且荧光黄无源 HEX 锚"},
    "DD59": {"leo": "米白樱粉风", "reason": "K-culture lavender 淡彩概念相邻"},
    "DD60": {"leo": "韩式政策报告风", "reason": "统一部 dark navy 政府报告与 DD06 概念相邻"},
}

SKIP_OFFICECLI: dict[str, dict] = {
    "bw--brutalist-raw": {"leo": "粗野报刊风", "reason": "brutalist 概念已覆盖"},
    "bw--mono-line": {"leo": "锐利黑白风", "reason": "mono line 黑白概念已覆盖"},
    "bw--swiss-bauhaus": {"leo": "包豪斯风", "reason": "swiss bauhaus 概念已覆盖"},
    "bw--swiss-system": {"leo": "瑞士网格风", "reason": "swiss system 概念已覆盖"},
    "dark--architectural-plan": {"leo": "工程蓝图风", "reason": "建筑图纸概念已覆盖"},
    "dark--aurora-softedge": {"leo": "极光风", "reason": "aurora 概念已覆盖"},
    "dark--blueprint-grid": {"leo": "蓝晒图纸风", "reason": "blueprint 概念已覆盖"},
    "dark--circle-digital": {"leo": "暗黑科技风", "reason": "dark digital agency 概念已覆盖"},
    "dark--cosmic-neon": {"leo": "梦幻星河风", "reason": "cosmic neon 概念已覆盖"},
    "dark--cyber-future": {"leo": "暗黑科技风", "reason": "cyber 概念已覆盖"},
    "dark--editorial-story": {"leo": "深色编辑报告风", "reason": "editorial 概念已覆盖"},
    "dark--investor-pitch": {"leo": "风投路演风", "reason": "dark investor pitch 概念已覆盖"},
    "dark--liquid-flow": None,  # keep
    "dark--luxury-minimal": {"leo": "暗夜奢华风", "reason": "luxury minimal 概念已覆盖"},
    "dark--midnight-blueprint": {"leo": "蓝晒图纸风", "reason": "midnight blueprint 概念已覆盖"},
    "dark--neon-productivity": {"leo": "荧光高对比科技风", "reason": "neon 概念已覆盖"},
    "dark--obsidian-amber": {"leo": "黑金期刊风", "reason": "黑曜金概念已覆盖;且源无 HEX 表"},
    "dark--premium-navy": {"leo": "投行IR编辑风", "reason": "navy+gold 与本批 DD43 概念相邻,金融金蓝系现库已密"},
    "dark--space-odyssey": {"leo": "梦幻星河风", "reason": "太空概念已覆盖"},
    "dark--velvet-rose": {"leo": "—", "reason": "velvet 源无 HEX 表,保真锚不可证"},
    "light--bold-type": {"leo": "大字报巨型排版风", "reason": "bold type 概念已覆盖"},
    "light--firmwise-saas": {"leo": "SaaS介绍风", "reason": "SaaS 概念已覆盖"},
    "light--fluid-gradient": {"leo": "—", "reason": "fluid gradient 源无 HEX,保真锚不可证"},
    "light--glassmorphism-vc": {"leo": "玻璃拟态风", "reason": "glassmorphism 概念已覆盖"},
    "light--isometric-clean": {"leo": "微立体轻拟态风", "reason": "isometric 概念已覆盖"},
    "light--minimal-corporate": {"leo": "简约商务风", "reason": "minimal corporate 概念已覆盖"},
    "light--minimal-product": {"leo": "产品发布会风", "reason": "minimal product 概念已覆盖"},
    "light--project-proposal": {"leo": "商业计划书风", "reason": "proposal 概念已覆盖"},
    "light--spring-launch": {"leo": "春日嫩柳风", "reason": "春季绿色营销概念相邻"},
    "light--training-interactive": {"leo": "教学课件风", "reason": "training 概念已覆盖"},
    "light--watercolor-wash": {"leo": "水彩晕染风", "reason": "watercolor 概念已覆盖"},
    "mixed--bauhaus-blocks": {"leo": "包豪斯风", "reason": "bauhaus 概念已覆盖"},
    "mixed--duotone-split": {"leo": "珊瑚紫双色调风", "reason": "duotone 概念已被 C 系并行批收录"},
    "mixed--spectral-grid": {"leo": "—", "reason": "spectral grid 源无 HEX,保真锚不可证"},
    "vivid--bauhaus-electric": {"leo": "包豪斯风", "reason": "bauhaus electric 为包豪斯变体"},
    "vivid--candy-stripe": {"leo": "多巴胺活力撞色风", "reason": "candy rainbow 概念已覆盖"},
    "vivid--energy-neon": {"leo": "荧光高对比科技风", "reason": "energy neon 概念已覆盖"},
    "vivid--playful-marketing": {"leo": "快消营销风", "reason": "playful marketing 概念已覆盖"},
    "warm--bloom-academy": {"leo": "童趣暖橙风", "reason": "教育童趣概念已覆盖"},
    "warm--brand-refresh": {"leo": "新消费品牌风", "reason": "brand refresh 概念已覆盖"},
    "warm--coral-culture": {"leo": "—", "reason": "coral culture 源无 HEX,保真锚不可证"},
    "warm--monument-editorial": {"leo": "—", "reason": "monument editorial 源无 HEX,保真锚不可证"},
    "warm--playful-organic": {"leo": "童趣暖橙风", "reason": "playful organic 概念已覆盖"},
    "warm--sunset-mosaic": {"leo": "—", "reason": "sunset mosaic 源无 HEX,保真锚不可证"},
    "warm--vital-bloom": {"leo": "柔和治愈", "reason": "wellness bloom 概念已覆盖;且源无 HEX"},
}

# ---------------------------------------------------------------------------
# Source parsing (stdlib only; the JS arrays are pure JSON literals).
# ---------------------------------------------------------------------------
def _extract_js_array(text: str, marker: str) -> list:
    idx = text.index(marker)
    start = text.index("[", idx)
    depth, end = 0, -1
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    return json.loads(text[start:end + 1])


def load_slidesgrab() -> tuple[dict[str, dict], dict[str, dict]]:
    """Parse both slides-grab JS data files -> {number: entry}."""
    west_text = (SLIDESGRAB_SRC / "design-styles-data.js").read_text(encoding="utf-8")
    ko_text = (SLIDESGRAB_SRC / "design-diversity-data.js").read_text(encoding="utf-8")
    west = _extract_js_array(west_text, "export const RAW_DESIGN_STYLES")
    ko = _extract_js_array(ko_text, "export const RAW_DESIGN_DIVERSITY_STYLES")
    return {s["number"]: s for s in west}, {s["number"]: s for s in ko}


def load_officecli() -> dict[str, dict]:
    """Parse each style dir: hex universe (style.md tables + INDEX triple),
    group (variant dimension), best-for and mood from INDEX.md rows."""
    index_text = (OFFICECLI_STYLES / "INDEX.md").read_text(encoding="utf-8")
    index_rows: dict[str, dict] = {}
    row_re = re.compile(r"^\|\s*(\S+--\S+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|")
    for line in index_text.splitlines():
        m = row_re.match(line)
        if not m:
            continue
        d, _name, hexes, best, mood = m.groups()
        hex_list = re.findall(r"#[0-9A-Fa-f]{6}", hexes)
        index_rows[d] = {"hexes": hex_list, "best": best.strip(), "mood": mood.strip()}

    out: dict[str, dict] = {}
    for d in sorted(p for p in OFFICECLI_STYLES.iterdir() if p.is_dir()):
        hexes: set[str] = set(index_rows.get(d.name, {}).get("hexes", []))
        overview = ""
        style_md = d / "style.md"
        if style_md.is_file():
            text = style_md.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("| ") and re.search(r"[0-9A-Fa-f]{6}", line):
                    # scan the whole table row: hex cells appear as `#RRGGBB`
                    # or backtick-quoted bare RRGGBB (premium-navy style);
                    # anchored forms only, to avoid hex-alphabet words like
                    # "Facade" leaking in as false anchors
                    for h in re.findall(r"#([0-9A-Fa-f]{6})\b", line) + re.findall(
                        r"`([0-9A-Fa-f]{6})`", line
                    ):
                        if re.fullmatch(r"[0-9A-Fa-f]{6}", h):
                            hexes.add("#" + h.upper())
            m = re.search(r"## Style Overview\s*\n\s*\n(.+?)(?:\n\s*\n|\n##)", text, re.S)
            if m:
                overview = " ".join(m.group(1).split())[:300]
        out[d.name] = {
            "group": d.name.split("--", 1)[0],
            "hexes": {h.upper() for h in hexes if h},
            "overview": overview,
            "best": index_rows.get(d.name, {}).get("best", ""),
            "mood": index_rows.get(d.name, {}).get("mood", ""),
        }
    return out


# ---------------------------------------------------------------------------
# Brief assembly.
# ---------------------------------------------------------------------------
def _hexes_of(value: str) -> list[str]:
    return [h for h in HEX_RE.findall(value)]


def build_brief(keep: dict, *, subdir: str, reference: str,
                variant_dimension: str | None = None,
                sample_path: str | None = None,
                source_title: str | None = None) -> dict:
    family, density = keep["family"]
    brief = {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": keep["name"],
        "aliases": keep["aliases"],
        "best_for": keep["best_for"],
        "visual_direction": keep["vd"],
        "canvas": {
            "aspect_ratio": "16:9",
            "background": "、".join(keep["bg"]) + (
                "(变体锚)" if len(keep["bg"]) > 1 else ""
            ),
            "composition": keep["composition"],
            "density": "medium, 密而不挤" if keep["family"][1] == "core" else "medium-low, 呼吸留白",
        },
        "color_palette": dict(keep["anchors"]),
        "typography": dict(keep["typo"]),
        "layout_patterns": list(keep["layout"]),
        "layout_usage_rule": keep["layout"][0],
        "visual_elements": {
            "allowed": keep["composition"],
            "avoid": "; ".join(keep["negatives"][:2]),
        },
        "rendering_constraints": [
            *keep["negatives"],
            "色板锚点以 brief HEX 为准,不漂移;文案准确,不虚构标识",
        ],
        "negative_prompt": list(keep["negatives"]),
        "paired_illustration": {"family": family, "density": density},
        "reference": reference,
    }
    if sample_path:
        brief["reference"] = f"{reference};金样板 {sample_path}(只登记路径不转换)"
    if variant_dimension:
        brief["token_sidecar"] = f"variant-dimension: {variant_dimension}"
    return brief


def render_markdown(brief: dict, *, subdir: str, scenes: list[str],
                     variant_dimension: str | None = None,
                     source_title: str | None = None) -> str:
    lines = [
        f"# {brief['style_name']}",
        "",
        f"**分类:** {subdir}",
    ]
    if variant_dimension:
        lines += [f"**variant-dimension:** {variant_dimension}(OfficeCLI 六分组第二维度:bw/dark/light/mixed/vivid/warm)"]
    if source_title:
        lines += [f"**来源原题:** {source_title}"]
    lines += ["", "**适用场景:**"]
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


def target_paths() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for num, keep in KEEP_KO.items():
        out[f"ko:{num}"] = STYLES_ROOT / TARGET_KO_DIR / f"{keep['name']}.md"
    for num, keep in KEEP_WEST.items():
        out[f"west:{num}"] = STYLES_ROOT / TARGET_WEST_DIR / f"{keep['name']}.md"
    for d, keep in KEEP_OFFICECLI.items():
        out[f"office:{d}"] = STYLES_ROOT / TARGET_OFFICE_DIR / f"{keep['name']}.md"
    return out


# ---------------------------------------------------------------------------
# Gates + pipeline (mirror of intake_landppt.run, shared semantics).
# ---------------------------------------------------------------------------
def run(*, write: bool) -> tuple[list[str], int]:
    problems: list[str] = []
    if not SLIDESGRAB_SRC.is_dir():
        return [f"source missing: {SLIDESGRAB_SRC}"], 2
    if not OFFICECLI_STYLES.is_dir():
        return [f"source missing: {OFFICECLI_STYLES}"], 2

    west_src, ko_src = load_slidesgrab()
    office_src = load_officecli()

    own_targets = set(target_paths().values())
    existing = [
        (rel, name, brief)
        for rel, name, brief in ohmy.load_existing_briefs()
        if (STYLES_ROOT / rel) not in own_targets
    ]

    generated: dict[str, tuple[dict, Path, dict]] = {}  # key -> (brief, path, provenance)

    def assemble(key: str, keep: dict, provenance: set[str], src_meta: dict,
                 subdir: str, reference: str, **kw) -> None:
        brief = build_brief(keep, subdir=subdir, reference=reference, **kw)
        path = target_paths()[key]
        generated[key] = (brief, path, {"hexes": provenance, "meta": src_meta})

    for num, keep in KEEP_KO.items():
        src = ko_src.get(num)
        if src is None:
            problems.append(f"intake_table_stale: KEEP_KO 引用 {num} 不存在")
            continue
        prov = {c["hex"].upper() for c in src["colors"]}
        prov |= {h.upper() for h in HEX_RE.findall("\n".join(src["background"]))}
        src_title = f"{src['title']}({src.get('id', '')},design-diversity)"
        assemble(
            f"ko:{num}", keep, prov, src, TARGET_KO_DIR,
            f"GitHub: epoko77-ai/design-diversity(via slides-grab design-diversity-data.js,MIT,快照 2026-05-24)· {num} {src['title']}",
            source_title=src_title,
        )
    for num, keep in KEEP_WEST.items():
        src = west_src.get(num)
        if src is None:
            problems.append(f"intake_table_stale: KEEP_WEST 引用 {num} 不存在")
            continue
        prov = {c["hex"].upper() for c in src["colors"]}
        prov |= {h.upper() for h in HEX_RE.findall("\n".join(src["background"]))}
        assemble(
            f"west:{num}", keep, prov, src, TARGET_WEST_DIR,
            f"GitHub: corazzon/pptx-design-styles(via slides-grab design-styles-data.js,MIT)· {num} {src['title']}",
        )
    for d, keep in KEEP_OFFICECLI.items():
        src = office_src.get(d)
        if src is None:
            problems.append(f"intake_table_stale: KEEP_OFFICECLI 引用 {d} 不存在")
            continue
        sample = None
        if keep.get("pptx"):
            src_pptx = OFFICECLI_STYLES / d / keep["pptx"]
            if not src_pptx.is_file():
                problems.append(f"sample_missing: {d}/{keep['pptx']}")
            else:
                sample = f"samples/reference-golden/officecli/{keep['pptx']}"
        assemble(
            f"office:{d}", keep, src["hexes"], src, TARGET_OFFICE_DIR,
            f"GitHub: OfficeCLI · skills/morph-ppt/reference/styles/{d}/style.md(MIT)· {src['mood'][:40]}",
            variant_dimension=src["group"],
            sample_path=sample,
        )

    # Gate 0: provenance -- every anchor hex must exist in the source tokens.
    for key, (brief, path, prov) in sorted(generated.items()):
        for role, value in brief["color_palette"].items():
            for h in _hexes_of(value):
                if h.upper() not in prov["hexes"]:
                    problems.append(
                        f"anchor_unprovenanced: {brief['style_name']}.{role} {h} 不在源 token 中"
                    )
        for h in HEX_RE.findall(brief["canvas"]["background"]):
            if h.upper() not in prov["hexes"]:
                problems.append(f"anchor_unprovenanced: {brief['style_name']} background {h} 无出处")

    # Gate 1: role anchors + identity font (lint WARNING subset).
    for key, (brief, path, prov) in sorted(generated.items()):
        for role in ("primary", "secondary", "accent", "neutral"):
            if not HEX_RE.search(brief["color_palette"][role]):
                problems.append(f"role_no_hex: {brief['style_name']}.{role}")
        typo = brief["typography"]
        if not ohmy.FONT_IDENTITY_RE.search(" ".join(str(v) for v in typo.values())):
            problems.append(f"typography_no_identity: {brief['style_name']}")

    # Gate 2: WCAG text anchor.
    for key, (brief, path, prov) in sorted(generated.items()):
        bg_hexes = [
            h for h in HEX_RE.findall(brief["canvas"]["background"])
        ]
        anchors = ohmy.palette_anchors(brief["color_palette"], bg_hexes)
        primary_hex = HEX_RE.search(brief["color_palette"]["primary"]).group(0)
        if not ohmy.text_anchor_ok(anchors, primary_hex):
            problems.append(f"text_anchor_missing: {brief['style_name']}")

    # Gate 3: family_duplicate across the whole merged library.
    seen: dict[frozenset, str] = {}
    for rel, name, brief in existing:
        fp = ohmy.fingerprint(brief)
        if fp:
            seen.setdefault(fp, name)
    for key, (brief, path, prov) in sorted(generated.items()):
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
        for key, (brief, path, prov) in sorted(generated.items()):
            keep = (
                KEEP_KO.get(key[3:]) if key.startswith("ko:")
                else KEEP_WEST.get(key[5:]) if key.startswith("west:")
                else KEEP_OFFICECLI.get(key[7:])
            )
            vd = None
            st = None
            if key.startswith("office:"):
                vd = prov["meta"]["group"]
            if key.startswith("ko:"):
                st = f"{prov['meta']['title']}({prov['meta'].get('id','')},design-diversity)"
            subdir = str(path.parent.relative_to(STYLES_ROOT))
            if key.startswith("office:"):
                subdir = f"{subdir} · {prov['meta']['group']} 分组"
            else:
                subdir = subdir.replace("/", " · ")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                render_markdown(
                    brief, subdir=subdir, scenes=keep["scenes"],
                    variant_dimension=vd, source_title=st,
                ),
                encoding="utf-8",
            )
        # Golden PPTX samples: copy verbatim, path-registered in briefs only.
        for d, keep in KEEP_OFFICECLI.items():
            if not keep.get("pptx"):
                continue
            src_pptx = OFFICECLI_STYLES / d / keep["pptx"]
            SAMPLES_GOLDEN.mkdir(parents=True, exist_ok=True)
            dst = SAMPLES_GOLDEN / keep["pptx"]
            shutil.copyfile(src_pptx, dst)
    return [], 0


def report() -> str:
    west_src, ko_src = load_slidesgrab()
    office_src = load_officecli()
    lines = [
        "slides-grab + OfficeCLI 吸收决策(C2):",
        f"  西式 35 = 保留 {len(KEEP_WEST)} + 跳过 {len(SKIP_WEST)};"
        f" 韩式 60 = 保留 {len(KEEP_KO)} + 跳过 {len(SKIP_KO)};"
        f" OfficeCLI {len(office_src)} = 保留 {len(KEEP_OFFICECLI)} + 跳过 {len([k for k, v in SKIP_OFFICECLI.items() if v])}",
        f"  净增 {len(KEEP_WEST) + len(KEEP_KO) + len(KEEP_OFFICECLI)} 套:",
        f"    {TARGET_KO_DIR}/({len(KEEP_KO)}) + {TARGET_WEST_DIR}/({len(KEEP_WEST)}) + {TARGET_OFFICE_DIR}/({len(KEEP_OFFICECLI)},variant-dimension 六分组标注)",
        f"    金样板 {len([k for k in KEEP_OFFICECLI.values() if k.get('pptx')])} 份 -> samples/reference-golden/officecli/(只登记路径)",
        "",
        "跳过映射(概念已有;含 C 系并行批收录与源锚不足两类):",
    ]
    for scope, table in (("西式", SKIP_WEST), ("韩式", SKIP_KO), ("OfficeCLI", SKIP_OFFICECLI)):
        for k in sorted(table):
            v = table[k]
            if not v:
                continue
            lines.append(f"  - [{scope} {k}] -> {v['leo']}({v['reason']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="slides-grab + OfficeCLI 风格吸收迁移器(C2)")
    parser.add_argument("--write", action="store_true", help="生成 brief 文件(幂等)")
    parser.add_argument("--check", action="store_true", help="只跑去重门与自检")
    parser.add_argument("--report", action="store_true", help="输出吸收决策报告")
    args = parser.parse_args(argv)

    if args.report:
        print(report())
        return 0

    problems, code = run(write=args.write)
    for item in problems:
        print(f"  ✗ {item}", file=sys.stderr)
    if code:
        print(f"intake gate FAILED ({len(problems)} problems)", file=sys.stderr)
        return 2
    action = "written" if args.write else "checked"
    total = len(KEEP_KO) + len(KEEP_WEST) + len(KEEP_OFFICECLI)
    print(f"intake OK ({action}): keep={total} "
          f"(ko={len(KEEP_KO)} west={len(KEEP_WEST)} officecli={len(KEEP_OFFICECLI)})")
    if args.write:
        print(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())

