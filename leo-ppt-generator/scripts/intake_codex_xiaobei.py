#!/usr/bin/env python3
"""S2b 双源轴条目迁移器（风格进货批 docs/plans/2026-08-31-006）。

两源均不占主风格 220 硬顶配额，分别落在两个分节轴：

1. **codex-slides 社区生图卡 → 08_图片渲染**：源
   ``ppt-github/codex-slides/src/lib/community.ts``（快照 2026-08-31）的
   22 张 YouMind Awesome Nano Banana Pro 社区卡。去重：1 张与现有
   ``黑板粉笔``（chalkboard）同概念跳过，21 张净新增为渲染轴条目
   （styleBlock → 生图提示词主体，tags → best_for，palette → 参考色板，
   每条登记来源 URL 与 CC BY/MIT 许可台账）。45 张内置模板不收（S2a
   域外条目层，与现库高重叠）。
2. **xiaobei 品牌设计系统 → 10_品牌身份**：源
   ``file-github/xiaobei/crews/content-producer/skills/design-full/
   design-systems/`` 的 15 个品牌 md。去重：ibm 与现有 ``ibm.md`` 重复
   跳过，14 个净新品牌（亮暗双模收敛为主色板 + 暗场变体声明，口径见
   ``references/style-library.md`` 暗场预设节）。

产出为字段式 markdown（无 JSON 块），与两轴现行文件形态一致；因此不进
``lint_style_briefs`` 的 brief 计数，也不触发 layouts sidecar / R-66 家族
合并纪律。计数同步点（_INDEX.md / style-library.md / 视觉风格配对末节）
由维护者随批同步，本脚本 ``--check`` 校验已生成文件与内嵌数据一致。

用法::

    python3 scripts/intake_codex_xiaobei.py --check   # 校验在盘文件一致
    python3 scripts/intake_codex_xiaobei.py --write   # 生成/覆盖（幂等）

退出码：0 = 通过/写入成功；2 = 内容漂移或目标异常。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
RENDER_DIR = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles") / "08_图片渲染"
BRAND_DIR = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles") / "10_品牌身份"

# Axis-standard suffix: 08 轴渲染合同（图内无字 + 16:9 画幅）与现库 20 条
# 完全同文，保证 load_rendering 的 paste_ready 段落合同一致。
RENDER_GUARDRAIL = (
    " Rendering guardrails: no text, no lettering, no numbers, no logos, "
    "no watermarks inside the image — any typography is applied later by "
    "the page layout, never by the image model. Compose for a 16:9 "
    "widescreen canvas (2560×1440): wide horizontal frame, not a poster "
    "column."
)

NO_PAIRING = "—（本批新增渲染,无固定 01 配对;可直接点名,默认使用场景见 `00_索引/视觉风格配对.md` 末节）"

# 许可台账（community.ts COMMUNITY_SOURCES, youmind-nano-banana-pro）。
NANO_SOURCE = {
    "repo": "YouMind Awesome Nano Banana Pro Prompts",
    "license": "CC BY 4.0",
    "license_url": "https://github.com/YouMind-OpenLab/awesome-nano-banana-pro-prompts/blob/main/LICENSE",
}

# 每卡: 文件名/slug/分类/中文定位/styleBlock(EN)/五维表/参考色板/密度/author/sourceUrl
RENDER_CARDS: list[dict] = [
    {
        "file": "金句衬线卡.md",
        "slug": "golden-serif-quote",
        "group": "叙事氛围",
        "cn_pos": "暖棕金句卡——一侧柔化人像、一侧超大浅金衬线陈述位,编辑级克制,一页一句 memorable line",
        "best_for": "金句页 / 证言页 / 人物侧写 / 章节开篇",
        "block": (
            "Warm brown canvas with a single light-gold serif voice. A portrait "
            "anchors one-third of the frame behind a soft gradient fade while an "
            "oversized subtle quotation mark and one large serif statement "
            "command the remaining two-thirds. Intimate, editorial, and quietly "
            "premium — built for a single memorable line per slide."
        ),
        "ltd": [
            ("线条质量", "Soft-edged photographic fade against calm serif shapes; no hard outlines"),
            ("纹理", "Gentle gradient falloff around the portrait; warm paper-grade grain"),
            ("深度", "Two-zone figure-ground — portrait recesses, statement slot advances"),
            ("材质", "Warm brown paper + light-gold serif plate"),
            ("情绪", "Intimate, editorial, quietly premium"),
        ],
        "palette": ["#C9A24B", "#3B2A1F", "#E8D9BE"],
        "density": "low",
        "author": "Nicolechan",
        "url": "https://x.com/stark_nico99/status/1991718646570426763",
        "src_id": "nb-golden-serif-quote",
    },
    {
        "file": "液态玻璃便当格.md",
        "slug": "liquid-glass-bento",
        "group": "现代商业",
        "cn_pos": "Apple 液态玻璃便当格——非对称 16:9 格阵,85-90% 透明卡浮于取色模糊底,一块超大 hero 格承载 3D 级主视觉",
        "best_for": "产品矩阵页 / 模块化能力总览 / dashboard 式信息页 / 高级感发布",
        "block": (
            "Apple-style liquid glass over a softly blurred, color-derived "
            "ground: an asymmetric 16:9 bento grid of 85-90% transparent cards "
            "with whisper-thin borders, subtle drop shadows, and floating "
            "depth. One oversized hero cell carries a photoreal or 3D-grade "
            "centerpiece while the remaining modules hold crisp titled facts "
            "with muted-tint icons. Premium, glossy, and modular — every slide "
            "reads as a curated dashboard."
        ),
        "ltd": [
            ("线条质量", "Whisper-thin 1px borders on glass cells; hairline highlights"),
            ("纹理", "Blurred color-derived ground showing through 85-90% transparent cards"),
            ("深度", "Floating layered depth — soft drop shadows, hero cell outweighs modules"),
            ("材质", "Liquid glass panels on blurred color field"),
            ("情绪", "Premium, glossy, modular, curated"),
        ],
        "palette": ["#2DD4BF", "#0B1220", "#E8EEF5", "#7C93A8"],
        "density": "high",
        "author": "Mansi Sanghani",
        "url": "https://x.com/MansiSanghani1/status/2013550795224961492",
        "src_id": "nb-liquid-glass-bento",
    },
    {
        "file": "渐变手绘题头.md",
        "slug": "handdrawn-gradient-header",
        "group": "手绘教育",
        "cn_pos": "蓝绿渐变冲洗的松弛手绘插画题头——斜体速写线 + 标题带并置,解释型内容的人味开场",
        "best_for": "章节开篇 / 解释型 intro / 轻量主题 / 教育培训",
        "block": (
            "Loose hand-drawn illustration washed in a blue-to-green gradient, "
            "with light italic sketch linework and an approachable, human "
            "feel. A simple illustrated character or motif sits beside a clear "
            "title band in 16:9, like the header of a well-designed explainer. "
            "Casual, warm, and inviting — good for intros, section openers, "
            "and lightweight topics."
        ),
        "ltd": [
            ("线条质量", "Light italic sketch linework, loose and unpolished"),
            ("纹理", "Blue-to-green gradient wash over sketch strokes"),
            ("深度", "Flat wash with layering only between motif and band"),
            ("材质", "Marker-style ink under watercolor-grade gradient"),
            ("情绪", "Casual, warm, inviting, human"),
        ],
        "palette": ["#2FBF9F", "#2E86AB", "#F5F7F2"],
        "density": "low",
        "author": "セミナー講師専門AIコンシェルジュ｜工藤 晶",
        "url": "https://x.com/akirakudo_ai/status/1992096860765561190",
        "src_id": "nb-handdrawn-gradient-header",
    },
    {
        "file": "水彩注记地图.md",
        "slug": "watercolor-map",
        "group": "手绘教育",
        "cn_pos": "米白纸面上的软水彩分区地图——每区以细圆珠笔手写标注,以温度换精密的制图法",
        "best_for": "地理 / 市场分区 / 领域地图 / 「一张图看空间」页",
        "block": (
            "Soft watercolor washes on off-white paper, regions bleeding into "
            "gentle pastel fields, every zone hand-labeled in fine "
            "ballpoint-pen script. An artful, tactile take on cartography and "
            "territory diagrams that trades cold precision for warmth. "
            "Educational and charming — ideal for geographies, segmentations, "
            "or any 'map of a space'."
        ),
        "ltd": [
            ("线条质量", "Fine ballpoint-pen annotation script over bleeding wash edges"),
            ("纹理", "Off-white paper grain under pastel watercolor fields"),
            ("深度", "Flat cartography — zone color density carries hierarchy"),
            ("材质", "Watercolor on paper + pen annotation"),
            ("情绪", "Artful, tactile, educational, charming"),
        ],
        "palette": ["#7FB2C9", "#F3EDE0", "#4A4A4A", "#C98B6B"],
        "density": "medium",
        "author": "Florian Gallwitz",
        "url": "https://x.com/FlorianGallwitz/status/1991796624646091091",
        "src_id": "nb-watercolor-map",
    },
    {
        "file": "古董专利文档.md",
        "slug": "vintage-patent",
        "group": "叙事氛围",
        "cn_pos": "1800 年代专利存档——老化象牙纸 + 编号技术线图(Fig.1/Fig.2) + 钢笔批注 + 火漆封印,把机制讲成档案",
        "best_for": "机制拆解 / 产品溯源 / 概念存档化叙事 / 历史感章节",
        "block": (
            "A recovered 1800s patent filing: aged ivory paper with foxing "
            "stains and fold creases, precise technical line drawings with "
            "numbered callouts (Fig. 1, Fig. 2), and fountain-pen annotations "
            "describing each part. An embossed seal and red wax stamp anchor a "
            "corner while a signature and date close the page. Authoritative, "
            "historic, and slightly mysterious — turns any mechanism or "
            "concept into an archival document."
        ),
        "ltd": [
            ("线条质量", "Precise engraved technical linework with numbered callout stems"),
            ("纹理", "Foxing stains, fold creases, aged ivory paper"),
            ("深度", "Flat archival sheet — emboss and wax seal add the only relief"),
            ("材质", "Aged ivory paper + iron-gall ink + wax"),
            ("情绪", "Authoritative, historic, slightly mysterious"),
        ],
        "palette": ["#8B2A1F", "#E8DCC0", "#3A2E1F"],
        "density": "medium",
        "author": "Alexandra Aisling",
        "url": "https://x.com/AllaAisling/status/2004212035333365763",
        "src_id": "nb-vintage-patent",
    },
    {
        "file": "大字产品广告.md",
        "slug": "bold-product-ad",
        "group": "现代商业",
        "cn_pos": "大声量商业广告版——3D 量级产品 hero + 促销文案位 + 徽章体系,让产品成为页面唯一的明星",
        "best_for": "产品卖点页 / 促销活动 / 上市主张 / 转化型营销页",
        "block": (
            "A punchy commercial ad layout: a single product rendered in "
            "dimensional 3D hero placement, wrapped in bold promotional copy, "
            "ranking badges, and a loud pre-head banner. High-contrast type "
            "stacks and accent call-outs sell one offer hard. Confident, "
            "retail-ready, and conversion-minded — built to make a product "
            "the unmistakable star of the slide."
        ),
        "ltd": [
            ("线条质量", "Crisp product silhouette edges; bold type-block boundaries"),
            ("纹理", "Clean commercial render surfaces, minimal environmental texture"),
            ("深度", "Dimensional 3D hero placement with grounded shadow"),
            ("材质", "Glossy commercial 3D + badge/banner print apparatus"),
            ("情绪", "Confident, loud, retail-ready, conversion-minded"),
        ],
        "palette": ["#E63946", "#1A1A1A", "#FFFFFF", "#F0C808"],
        "density": "medium",
        "author": "KAWAI",
        "url": "https://x.com/kawai_design/status/1992142466255114727",
        "src_id": "nb-bold-product-ad",
    },
    {
        "file": "超实产品海报.md",
        "slug": "hyperreal-product-poster",
        "group": "现代商业",
        "cn_pos": "官方 campaign 级超实广告摄影——暖金光下真实瞬间中的产品 hero,凝水/微泡/锐高光,构图纪律给人与产品",
        "best_for": "旗舰产品海报 / 品牌广告页 / 高端生活方式主张",
        "block": (
            "Hyper-real advertising photography with an official-campaign "
            "polish: a product hero — condensation, micro-bubbles, crisp "
            "highlights — caught in an authentic real-world moment under warm "
            "golden light. A disciplined composition budget hands most of the "
            "frame to human action and product, keeping environment and tight "
            "typography minimal. Vivid, premium, and believable — a flagship "
            "brand poster for any product."
        ),
        "ltd": [
            ("线条质量", "Photographic edges — crisp product contours, soft background falloff"),
            ("纹理", "Condensation, micro-bubbles, material micro-detail"),
            ("深度", "Shallow depth of field, golden-hour motivated light"),
            ("材质", "Real-world materials under studio-grade advertising light"),
            ("情绪", "Vivid, premium, believable, flagship-grade"),
        ],
        "palette": ["#A7D129", "#F6E23A", "#FFFFFF", "#B7C9C4"],
        "density": "medium",
        "author": "ᴍᴜʀᴘʜʏ",
        "url": "https://x.com/Diplomeme/status/2075083065127571574",
        "src_id": "nb-hyperreal-product-poster",
    },
    {
        "file": "剖面技术图.md",
        "slug": "technical-cutaway",
        "group": "现代商业",
        "cn_pos": "纯白底超实剖面——主体切开露内部组件,细线引出标注,博物馆标本级「怎么造的」页",
        "best_for": "产品构造页 / 工程解释 / 教学拆解 / 权威性 mechanism 页",
        "block": (
            "A hyper-real cutaway on a clean white background: the subject "
            "sliced open to reveal densely detailed interior components, each "
            "named by a thin-line text callout. High-focus rendering treats "
            "the object like a museum specimen. Precise, technical, and "
            "premium — turns any product, tool, or structure into an "
            "authoritative 'how it's built' slide."
        ),
        "ltd": [
            ("线条质量", "Thin-line callout stems; specimen-grade internal edges"),
            ("纹理", "Component micro-texture inside the cut plane, clean white ground"),
            ("深度", "Museum-specimen high-focus render, single subject centered"),
            ("材质", "Photoreal cutaway materials on seamless white"),
            ("情绪", "Precise, technical, premium, authoritative"),
        ],
        "palette": ["#D64541", "#FFFFFF", "#1D1D1F", "#8A8F98"],
        "density": "medium",
        "author": "Pierrick Chevallier | IA",
        "url": "https://x.com/CharaspowerAI/status/2073104523476828533",
        "src_id": "nb-technical-cutaway",
    },
    {
        "file": "3D角色分镜板.md",
        "slug": "3d-character-storyboard",
        "group": "特色",
        "cn_pos": "白底硬黑框分镜板——Pixar 级 3D 风格化渲染 + 戏剧化饱和光,格子网格讲有个性的人物旅程",
        "best_for": "人物档案 / 用户旅程 / 分步骤叙事 / 团队介绍页",
        "block": (
            "A crisp storyboard poster: white ground, hard black panel "
            "borders, and bold black typography framing premium Pixar-style "
            "3D stylized renders. Dramatic saturated lighting gives each "
            "character or scene cinematic punch across a wide 16:9 grid. "
            "Playful yet structured — great for profiles, journeys, and "
            "step-by-step narratives with personality."
        ),
        "ltd": [
            ("线条质量", "Hard black panel borders, crisp 3D silhouettes"),
            ("纹理", "Smooth stylized 3D surfaces with cinematic lighting falloff"),
            ("深度", "In-panel 3D depth; grid layout stays flat and structured"),
            ("材质", "Pixar-grade 3D render on paper-white board"),
            ("情绪", "Playful, structured, dramatic, personality-forward"),
        ],
        "palette": ["#FF5A1F", "#FFFFFF", "#111111", "#E01E37"],
        "density": "high",
        "author": "𝐌",
        "url": "https://x.com/Strength04_X/status/2071466852614816182",
        "src_id": "nb-3d-character-storyboard",
    },
    {
        "file": "发光扫描渲染.md",
        "slug": "luminous-scan-render",
        "group": "现代商业",
        "cn_pos": "医学扫描美学——单一主体呈现为发光半透明组织,交织光纤/节点/通路浮于白灰渐变,「从内部点亮」的 hero",
        "best_for": "解剖/系统 hero 图 / 医疗科技 / 架构总览 / 未来感主视觉",
        "block": (
            "An advanced medical-scan aesthetic: a single subject rendered as "
            "luminous, semi-transparent structure — interwoven lit fibers, "
            "nodes, and glowing pathways — floating on a clean white-to-grey "
            "gradient. Minimalist, high-focus, and text-free, letting the "
            "glowing form carry the slide. Clean, technological, and "
            "futuristic — a striking hero visual for anatomy, systems, or "
            "anything you want to show 'lit from within'."
        ),
        "ltd": [
            ("线条质量", "Lit fiber pathways and node points; no outlines, glow defines edges"),
            ("纹理", "Semi-transparent volumetric tissue, faint scan banding"),
            ("深度", "Floating luminous volume on receding white-grey gradient"),
            ("材质", "Glowing translucent structure, scan-grade light"),
            ("情绪", "Clean, technological, futuristic, high-focus"),
        ],
        "palette": ["#2BE38A", "#F2F5F3", "#0D1B12", "#7CF2B8"],
        "density": "low",
        "author": "Dera | Performance marketing Creative",
        "url": "https://x.com/Ifekaego1/status/2068607373200039956",
        "src_id": "nb-luminous-scan-render",
    },
    {
        "file": "摘要信息图卡.md",
        "slug": "summary-infographic",
        "group": "现代商业",
        "cn_pos": "把复杂主题组织成可读层级的干净摘要信息图——分组卡片/图标/连线/短事实,百科式信息密度",
        "best_for": "主题总览页 / 知识汇总 / 关系梳理 / 高密度总结页",
        "block": (
            "A clean summary infographic that organizes a complex subject into "
            "a legible visual hierarchy: grouped cards, portraits or icons, "
            "connecting lines, and short labeled facts arranged for fast "
            "comprehension. Structure over decoration, with a restrained "
            "accent guiding the eye through relationships. Clear, "
            "encyclopedic, and information-dense — built to make a tangled "
            "topic instantly scannable."
        ),
        "ltd": [
            ("线条质量", "Connecting lines and clean card edges; restrained iconography"),
            ("纹理", "Flat digital surfaces, minimal texture"),
            ("深度", "Card-layer hierarchy only; no scene depth"),
            ("材质", "Digital infographic cards on light canvas"),
            ("情绪", "Clear, encyclopedic, scannable, structured"),
        ],
        "palette": ["#2563EB", "#0F172A", "#F8FAFC", "#F59E0B"],
        "density": "high",
        "author": "ファーラ@ガンプラ",
        "url": "https://x.com/Live_05/status/2065366252391113120",
        "src_id": "nb-summary-infographic",
    },
    {
        "file": "复古工业概念.md",
        "slug": "retro-industrial-concept",
        "group": "叙事氛围",
        "cn_pos": "架空历史的写实工业渲染——中世纪工程语言重塑对象,低饱和实用色 + 诚实材质 + 期代正确的产品档案照",
        "best_for": "设计概念页 / what-if 变体 / heritage 产品故事 / 工业设计叙事",
        "block": (
            "A realistic alternate-history industrial render: a designed "
            "object reimagined through mid-century engineering — a muted "
            "utilitarian palette, honest materials, restrained chrome, and "
            "period-correct forms. Photographic lighting sells it as a "
            "genuine archival product shot. Retro, tactile, and conceptual — "
            "ideal for design concepts, 'what-if' variants, and "
            "heritage-flavored product stories."
        ),
        "ltd": [
            ("线条质量", "Period-correct machined edges, honest joinery"),
            ("纹理", "Aged utilitarian materials — powder coat, bakelite, brushed steel"),
            ("深度", "Archival product-shot lighting, single hero object"),
            ("材质", "Mid-century industrial materials, restrained chrome"),
            ("情绪", "Retro, tactile, conceptual, credible"),
        ],
        "palette": ["#B04A3A", "#6E7B6B", "#C9C1AE", "#2E2E2C"],
        "density": "low",
        "author": "Riccardo",
        "url": "https://x.com/Riccardo_Nero/status/2065184321514664239",
        "src_id": "nb-retro-industrial-concept",
    },
    {
        "file": "新参数化编辑.md",
        "slug": "neo-parametric-editorial",
        "group": "叙事氛围",
        "cn_pos": "绘画性编辑插画 × 蓝图叠层——流动线稿/交叉排线/制图网格/工程示意穿行主体,象牙金钢蓝的博物馆级智识感",
        "best_for": "高级编辑页 / 技术人文交叉主题 / 品牌世界观 / 概念章节",
        "block": (
            "Neo-parametric editorial illustration: elegant painterly "
            "rendering fused with blueprint overlays — flowing linework, "
            "cross-hatching, drafting grids, dimensional annotations, and "
            "engineering schematics threaded through the subject. A luxury "
            "palette of ivory, champagne gold, graphite, and steel blue sits "
            "under soft cinematic light with controlled line density. "
            "Intellectual, futuristic, and museum-grade — where organic form "
            "meets technical drawing."
        ),
        "ltd": [
            ("线条质量", "Flowing linework + drafting grids + cross-hatching, density-controlled"),
            ("纹理", "Painterly surface under schematic overlay threads"),
            ("深度", "Soft cinematic light; annotation layers float above form"),
            ("材质", "Paint + drafting film"),
            ("情绪", "Intellectual, futuristic, museum-grade, luxurious"),
        ],
        "palette": ["#C9A96A", "#F0EBE0", "#4A5568", "#6B8BA3"],
        "density": "medium",
        "author": "zayan",
        "url": "https://x.com/HustleXR/status/2064955550971121953",
        "src_id": "nb-neo-parametric-editorial",
    },
    {
        "file": "粉笔陈列网格.md",
        "slug": "pastel-chalk-knolling",
        "group": "特色",
        "cn_pos": "粉彩粉笔标本的俯拍 knolling 网格——可见粉尘与纸纹,中央一件 hero,陈列/分类/可比项的温柔底座",
        "best_for": "集合陈列 / 分类法页 / 可比项对比 / 目录型内容",
        "block": (
            "Soft pastel chalk-art specimens arranged in a precise top-down "
            "knolling grid, with visible chalk dust and paper grain and one "
            "larger hero piece anchoring the center. Gently blended colors "
            "sit on a saturated flat ground with clean negative space. "
            "Tactile, curated, and calm — a beautiful way to lay out a "
            "collection, taxonomy, or set of comparable items."
        ),
        "ltd": [
            ("线条质量", "Soft chalk edges, slightly bloomed; precise grid alignment"),
            ("纹理", "Chalk dust and paper grain across a saturated flat ground"),
            ("深度", "Strictly top-down flat lay; scale difference carries hierarchy"),
            ("材质", "Pastel chalk on paper-grade ground"),
            ("情绪", "Tactile, curated, calm, gentle"),
        ],
        "palette": ["#B7D84B", "#F3E9D2", "#E39FB0", "#7FB6C9"],
        "density": "medium",
        "author": "Heather Green",
        "url": "https://x.com/heathergreen/status/2063412874232352859",
        "src_id": "nb-pastel-chalk-knolling",
    },
    {
        "file": "水彩生活拼贴.md",
        "slug": "watercolor-moodboard",
        "group": "叙事氛围",
        "cn_pos": "水彩生活方式 moodboard——中央主体环绕松散水彩小景/手写标题/短注,大地色系讲品牌世界与旅行感",
        "best_for": "品牌世界观页 / 叙事章节 / 生活方式主题 / 旅行文创",
        "block": (
            "A watercolor lifestyle moodboard: a central figure or subject "
            "surrounded by loose painted vignettes, elegant handwritten "
            "script titles, and short bulleted notes on off-white paper "
            "texture. An earthy palette of greens, browns, and warm washes "
            "ties the collage together. Romantic, artisanal, and "
            "story-driven — perfect for narratives, brand worlds, and "
            "travel-flavored themes."
        ),
        "ltd": [
            ("线条质量", "Loose watercolor blobs + fine handwritten script accents"),
            ("纹理", "Off-white paper texture under layered washes"),
            ("深度", "Collage layering — vignettes recede, central subject anchors"),
            ("材质", "Watercolor vignettes + script ink on paper"),
            ("情绪", "Romantic, artisanal, story-driven, warm"),
        ],
        "palette": ["#6B7A4F", "#8B6A4A", "#C9A24B", "#F0EAD9"],
        "density": "medium",
        "author": "Minahil",
        "url": "https://x.com/Minahil42298354/status/2063186164043903032",
        "src_id": "nb-watercolor-moodboard",
    },
    {
        "file": "工程分解信息图.md",
        "slug": "engineering-breakdown-grid",
        "group": "现代商业",
        "cn_pos": "超密工程信息图——锐利分割线成格,每格 photoreal 剖切/爆炸视图/尺寸线/色码箭头,Apple ID 文档级「产品解剖」",
        "best_for": "产品解剖页 / 研发汇报 / 工程总览 / 硬核技术页",
        "block": (
            "An ultra-detailed engineering infographic: a clean ground split "
            "by sharp separator lines into a precise grid, each cell holding "
            "a photoreal 3D render with transparent cutaways, exploded views, "
            "dimension lines, callout boxes, and color-coded engineering "
            "arrows. Apple-style industrial-design documentation, dense with "
            "precise technical labels. Rigorous, high-end, and authoritative "
            "— the definitive 'anatomy of the product' layout."
        ),
        "ltd": [
            ("线条质量", "Dimension lines, callout stems, sharp cell separators"),
            ("纹理", "Photoreal component renders inside a clean gridded ground"),
            ("深度", "In-cell 3D cutaway depth; grid discipline across the page"),
            ("材质", "Industrial-design documentation plates"),
            ("情绪", "Rigorous, high-end, authoritative, dense"),
        ],
        "palette": ["#2563EB", "#FFFFFF", "#111111", "#EA580C"],
        "density": "high",
        "author": "⁠ luciaAI",
        "url": "https://x.com/luciaverseai/status/2062938095109255382",
        "src_id": "nb-engineering-blueprint-grid",
    },
    {
        "file": "多角度照片网格.md",
        "slug": "multi-angle-grid",
        "group": "现代商业",
        "cn_pos": "同一主体的多机位九宫格——远景/中景/特写混排于柔焦自然底,一致光线统一为一项研究",
        "best_for": "产品全览页 / 场地/对象研究 / 细节展示 / 综合呈现",
        "block": (
            "One subject shot from many vantage points and tiled into a clean "
            "nine-square grid — distant, medium, and close-up framings mixing "
            "angles and crops against a softly blurred natural backdrop. "
            "Consistent light and color unify the panels into a single study. "
            "Cinematic and comprehensive — a strong way to present a subject, "
            "product, or place from every side on one slide."
        ),
        "ltd": [
            ("线条质量", "Photographic edges within clean square crops"),
            ("纹理", "Consistent natural-light grain across panels"),
            ("深度", "Per-panel depth of field; unified blurred backdrop"),
            ("材质", "Photography grid on soft natural ground"),
            ("情绪", "Cinematic, comprehensive, studious"),
        ],
        "palette": ["#6FA8DC", "#7FA05A", "#E8E2D0", "#3B3B3B"],
        "density": "medium",
        "author": "coloringany.com",
        "url": "https://x.com/zhoumeng780/status/2062066820656550311",
        "src_id": "nb-multi-angle-grid",
    },
    {
        "file": "实景标注导览.md",
        "slug": "visual-info-guide",
        "group": "现代商业",
        "cn_pos": "真实照片转信息导览——保留实拍底,叠加标注线/兴趣点/数据 chip/短注,编辑信息图壳轻覆真实影像",
        "best_for": "地点/对象导览页 / 实景讲解 / 数据叠加说明 / 沉浸式总览",
        "block": (
            "A photo transformed into an information-visualization guide: the "
            "real scene kept as the backdrop while clean overlays — "
            "annotation lines, labeled points of interest, stat chips, and "
            "short descriptive notes — explain what you're looking at. "
            "Editorial infographic polish sits lightly over authentic "
            "imagery. Informative and immersive — turns any place, object, or "
            "scene into a guided, annotated overview."
        ),
        "ltd": [
            ("线条质量", "Clean annotation lines and pointer stems over photography"),
            ("纹理", "Authentic photographic base under a light UI overlay layer"),
            ("深度", "Photographic depth; overlay layer stays flat"),
            ("材质", "Real photo + editorial infographic chrome"),
            ("情绪", "Informative, immersive, polished, explanatory"),
        ],
        "palette": ["#0EA5E9", "#F8FAFC", "#0F172A", "#F59E0B"],
        "density": "medium",
        "author": "AI探路者Tim",
        "url": "https://x.com/AIExplorerTim/status/2062017023081848863",
        "src_id": "nb-visual-info-guide",
    },
    {
        "file": "分层爆炸图.md",
        "slug": "exploded-layers",
        "group": "现代商业",
        "cn_pos": "超实分层爆炸——主体拆成上下对齐的水平层,细指引线逐层标注,亮棚底商业摄影光,「层层看内部」",
        "best_for": "构成拆解页 / 食品/产品成分 / 组装顺序 / 自解释机制页",
        "block": (
            "A hyper-real exploded breakdown: the subject separated into "
            "cleanly aligned horizontal layers stacked top-to-bottom, each "
            "tagged with a thin pointer line and a short label, floating on "
            "a bright seamless studio background. Commercial-photography "
            "lighting gives every layer crisp reflections and soft shadows. "
            "Appetizing, premium, and self-explaining — the ideal 'what's "
            "inside, layer by layer' slide."
        ),
        "ltd": [
            ("线条质量", "Thin pointer lines to each layer; crisp layer edges"),
            ("纹理", "Material detail per layer, seamless studio ground"),
            ("深度", "Vertically exploded stack with soft commercial shadows"),
            ("材质", "Studio-lit subject layers on bright seamless background"),
            ("情绪", "Appetizing, premium, self-explaining"),
        ],
        "palette": ["#F5C518", "#FFFFFF", "#1A1A1A", "#E07A2F"],
        "density": "medium",
        "author": "𝐌",
        "url": "https://x.com/Strength04_X/status/2061027904738496976",
        "src_id": "nb-exploded-layers",
    },
    {
        "file": "生活方式产品照.md",
        "slug": "lifestyle-product-shot",
        "group": "现代商业",
        "cn_pos": "明亮日光生活方式产品摄影——模特直面镜头呈现产品,浅景深保产品锐利,愉悦户外场景卖情绪与用途",
        "best_for": "产品场景页 / 生活方式营销 / 品牌温度页 / aspirational 主张",
        "block": (
            "Bright, sun-drenched lifestyle product photography: a happy model "
            "presents the product straight to camera with a shallow depth of "
            "field keeping the item razor-sharp against a joyful outdoor "
            "scene. Natural sunlight, a warm vibrant palette, and a slightly "
            "elevated angle sell mood and use in one shot. Energetic, "
            "aspirational, and human — makes any product feel like part of a "
            "good day."
        ),
        "ltd": [
            ("线条质量", "Razor-sharp product contour against soft background falloff"),
            ("纹理", "Natural sunlight, skin and fabric texture, warm vibrant palette"),
            ("深度", "Shallow depth of field, slightly elevated angle"),
            ("材质", "Real product + joyful outdoor environment"),
            ("情绪", "Energetic, aspirational, human, sunny"),
        ],
        "palette": ["#12B5C9", "#F4C542", "#5EC8E5", "#FFF6E5"],
        "density": "low",
        "author": "Maddox",
        "url": "https://x.com/Maddox_Digital/status/2074154537259356554",
        "src_id": "nb-lifestyle-product-shot",
    },
    {
        "file": "编辑动作海报.md",
        "slug": "editorial-action-poster",
        "group": "叙事氛围",
        "cn_pos": "全出血编辑动作海报——暖米色超窄块字被画面裁切,hero 主体斜切破字而出,正午硬光+天蓝中性场+单点艳色",
        "best_for": "活动主张页 / 运动品牌 / 大声量章节 / 杂志级封面",
        "block": (
            "A full-bleed editorial action poster: enormous warm-cream "
            "extra-condensed block letters cropped by the frame and sitting "
            "behind a hero subject that cuts diagonally across and breaks "
            "through the type layer. Hard midday sun, crisp shadows, a "
            "sky-blue neutral environment, one vivid accent on the hero, and "
            "tight clusters of white microcopy pinned to a strong grid. "
            "Kinetic, loud, and magazine-grade — action first, type second, "
            "detail third."
        ),
        "ltd": [
            ("线条质量", "Cropped condensed block type edges; diagonal hero cut"),
            ("纹理", "Hard midday sun, crisp shadows, clean environmental surfaces"),
            ("深度", "Type layer behind subject breaking through — stacked planes"),
            ("材质", "Photographic action + poster print type"),
            ("情绪", "Kinetic, loud, magazine-grade, confident"),
        ],
        "palette": ["#FF4D2E", "#3FA9E0", "#F3E8CE", "#FFFFFF"],
        "density": "medium",
        "author": "H A J R A",
        "url": "https://x.com/codewithhajra/status/2073422730171478176",
        "src_id": "nb-editorial-action-poster",
    },
]

# 去重登记：22 张源卡中与 08 轴现行条目同概念而未收录的卡。
RENDER_SKIPPED = [
    ("nb-chalkboard-lesson", "黑板粉笔", "教师黑板手写+粉笔图示与现行 08 轴条目同概念（slug/风格名碰撞）"),
]

BRAND_FOOTER = (
    "> 品牌身份轴约束「企业 VI（颜色/字体/语气）」。**verified_at: 未核验**——"
    "颜色/字体为公开资料近似值（源：xiaobei design-systems 快照 2026-08-31，"
    "经 S2b 吸收转写）。品牌 deck 交付前必须：① 向客户索取官方 VI token，或 "
    "② 按官方 VI 手册核验主色与字体，并把本文件 verified_at 更新为核验日期与"
    "来源；未核验时不得声称「符合品牌规范」；logo 用法（安全区/最小尺寸/深底"
    "反白）以官方手册为准，本文件未规定处不得自创。"
)

# 每品牌: 文件名/主色/强调色/定位/语气/字体/氛围/亮色板/暗场变体/使用边界
BRANDS: list[dict] = [
    {
        "file": "airbnb.md",
        "primary": "#FF385C",
        "accent": "#222222",
        "pos": "Airbnb-style warm hospitality identity — travel, hosting, community platforms, and belonging-driven product decks",
        "tone": "Warm, inviting, human, conversational micro-copy, trustworthy",
        "font": 'Cereal（品牌专有,近似替代 Nunito Sans）, "Nunito", "Microsoft YaHei", sans-serif',
        "mood": "Clean white canvas, warm photography as primary visual driver, coral accent signals action without shouting, rounded corners everywhere, UI chrome stays light",
        "palette": "背景 #FFFFFF · 卡面 #F7F7F7 / 暖面 #FFFAF5 · 正文 #222222 · 次级 #717171 · 边线 #DDDDDD · 语义 success #008A05 / warning #C7B82F / error #C13515",
        "dark": "无官方暗场体系;dark-deck 预设按中性色反转推导（背景 #222222 系,文字反白 #FFFFFF,Rausch 提亮一档）,正文对比度 ≥4.5:1 复检",
        "bounds": "Rausch 珊瑚只作 CTA/选中/品牌锚点,禁止大面积背景填充（费眼）;Surface Warm #FFFAF5 承担「温暖而不装饰」的分区;全局圆角,无锐利边角",
    },
    {
        "file": "apple.md",
        "primary": "#0071E3",
        "accent": "#1D1D1F",
        "pos": "Apple-style premium simplicity — consumer electronics launches, hero product showcases, keynote-grade decks",
        "tone": "Confident, luminous, precise, unhurried, premium",
        "font": '"SF Pro Display"/"SF Pro Text"（近似替代 "Helvetica Neue"）, Helvetica, Arial, "Microsoft YaHei", sans-serif',
        "mood": "Every surface breathes; content is the hero and UI chrome recedes; cinematic full-bleed photography; white space is structural, not decorative; typography large and never timid",
        "palette": "亮场:背景 #FFFFFF · 卡面 #F5F5F7 · 正文 #1D1D1F · 次级 #6E6E73 · 分隔线 #D2D2D7",
        "dark": "官方暗场（dark-deck 预设直接采用）:背景纯黑 #000000（OLED）· 卡面 #1C1C1C / 浮层 #2C2C2E · 正文 #F5F5F7 · accent 提亮为 #2997FF;深底对比度复检正文 ≥4.5:1",
        "bounds": "渐变只允许克制的径向光晕,禁彩虹扫过;产品图必须棚拍级干净底;暗场要 rich and deep,不要 flat gray;动效物理弹簧感而非线性",
    },
    {
        "file": "bmw.md",
        "primary": "#1C69D4",
        "accent": "#0066B1",
        "pos": "BMW-style engineered luxury — automotive, premium manufacturing, motorsport-adjacent engineering decks",
        "tone": "Engineered precision, measured luxury, Bavarian authority, structured, machined",
        "font": 'BMW Type Next（授权字体,公开近似替代 Inter 700/300）, "Inter", "Helvetica Neue", "Microsoft YaHei", sans-serif',
        "mood": "Dark navy hero bands frame studio-lit automotive photography; weight contrast 700 display vs 300 body does the heavy lifting; twin-kidney symmetry philosophy — nothing rounded, nothing soft",
        "palette": "亮场:画布 #FFFFFF · 柔面 #F7F7F7 · 正文 #262626 · 次级 #6B6B6B · BMW Blue #1C69D4 · 巴伐利亚蓝 #0066B1 · M 红 #E22718（仅 M 语境）",
        "dark": "官方暗场（dark-deck 预设直接采用,premium default）:画布暖深海军蓝 #1A2129（非纯黑,巴伐利亚暖调）· 浮层 #262E38 · 正文暖白 #F5F5F5 · primary 提亮 #3B8FE3;与 Tesla 纯黑/Apple OLED 黑区分",
        "bounds": "暗面永不纯黑 #000000;M 三色条纹只出现在 motorsport 语境,是受控 accent 不是装饰;无圆角无软形;摄影必须棚拍级或黄金时刻 16:9+",
    },
    {
        "file": "figma.md",
        "primary": "#F24E1E",
        "accent": "#A259FF",
        "pos": "Figma-style creative confidence — design tools, creative platforms, community and craft-oriented product decks",
        "tone": "Energetic optimism, structured playfulness, tool-first confidence, inclusive warmth",
        "font": '"Inter", system-ui, -apple-system, "Microsoft YaHei", sans-serif; 代码 "JetBrains Mono", Menlo, monospace',
        "mood": "Vibrant multi-color palette that stays professional; purposeful asymmetry over safe neutrality; bright colors balanced by generous whitespace and a clean grid, never chaotic",
        "palette": "品牌五色:红橙 #F24E1E · 珊瑚红 #FF7262 · 紫 #A259FF · 绿 #0ACF83 · 蓝 #1ABCFE;深底（主模态）:画布 #1E1E1E · 卡面 #2C2C2C · 正文 #FFFFFF · 次级 #B3B3B3",
        "dark": "深色为主模态（dark-deck 原生）:画布 #1E1E1E → 浮层 #3C3C3C 分层,正文 #FFFFFF,品牌五色在深底直接可用（本就高饱和）;浅模态:画布 #FFFFFF · 卡面 #F5F5F5 · 正文 #1E1E1E",
        "bounds": "多色是品牌资产但每屏至多一两个主色承担结构;渐变端点用品牌紫;装饰彩度靠留白与网格平衡,禁止无网格的彩色堆砌",
    },
    {
        "file": "framer.md",
        "primary": "#0055FF",
        "accent": "#0A0A0A",
        "pos": "Framer-style creative-tool boldness — web tooling, interactive product, design-engineering crossover decks",
        "tone": "Bold, electric, motion-first, interactive, creative, confident",
        "font": 'Inter（display 可用 Fraktion 近似:Inter tight tracking）, "Microsoft YaHei", sans-serif',
        "mood": "Dark high-contrast surfaces with electric blue punctuating key interactions; slightly playful, never corporate; interactive showcases are the content, not decoration",
        "palette": "深底:画布 #0A0A0A · 卡面 #141414 · 浮层 #1E1E1E · 正文 #FFFFFF · 次级 #B0B0B0 · 边线 #2A2A2A;语义 success #00C853 / warning #FFAB00 / error #FF1744",
        "dark": "深色为主模态（dark-deck 原生）:#0A0A0A 画布三层递进,正文 #FFFFFF,Electric Blue #0055FF 承担全部交互语义;浅场仅作辅助（白底 + 电蓝）",
        "bounds": "Electric Blue 是灵魂:每个交互 affordance 都用它,禁止用渐变稀释——必须纯且饱和;焦点环/悬停光晕用 #0055FF@20%;静态页面视为「坏的」——版式要有动势暗示",
    },
    {
        "file": "linear.md",
        "primary": "#5E6AD2",
        "accent": "#0A0A0F",
        "pos": "Linear-style engineer-grade dark minimalism — project management, dev tooling, engineer-facing product decks",
        "tone": "Radical restraint, instrument-grade precision, quiet, no-nonsense, clarity over ornament",
        "font": 'Inter, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; 等宽 "SF Mono", "Fira Code", Menlo, monospace',
        "mood": "Precision-instrument feel: dark, quiet, fast; flat matte surfaces; purple accent used as a surgical highlight, never decoration; transitions quick and purposeful",
        "palette": "深底:根 #0A0A0F · 面1 #111118 · 面2 #181820 · 面3 #1F1F2A · 悬停 #25252F · 正文 #E8E8ED · 次级 #8B8B96 · 边线 #25252F · 语义 success #4ADE80 / warning #FBBF24 / error #F87171",
        "dark": "深色为主模态（dark-deck 原生）:深度靠底色分层而非投影;紫 accent #5E6AD2 每视口一处即足;深底正文 #E8E8ED 对比度远超 4.5:1",
        "bounds": "accent 不得作装饰性填充（divider/大面底色禁用,选中态可用 accent-subtle）;卡片默认无投影、无装饰渐变;圆角纪律 6/8/9999px;正文最重 600;一律左对齐;1px 边线,禁 2px+（焦点环除外）",
    },
    {
        "file": "notion.md",
        "primary": "#37352F",
        "accent": "#2EAADC",
        "pos": "Notion-style warm minimalism — knowledge management, docs-first products, calm competence decks",
        "tone": "Warm, calm, scholarly, approachable, unhurried, trustworthy",
        "font": '标题衬线 "Noto Serif", Georgia, serif;正文 -apple-system, "Segoe UI", Helvetica, Arial, "Microsoft YaHei", sans-serif;代码 Menlo, Consolas, monospace',
        "mood": "A well-lit study, not a cold lab: cream and warm whites dominate (never pure white on large surfaces), serif headings create a book-like cadence, shadows are whispered not shouted, icons at 1.5px thin strokes",
        "palette": "亮场:画布 #FFFFFF（暖语境）· 外壳 #FBFBFA · 侧栏米 #F7F6F3 · 正文墨 #37352F · 次级 #9B9A97 · 边线 #E9E9E7 · 动作蓝 #2EAADC · 语义绿 #0F7B6C / 红 #EB5757 / 黄 #DFAB01",
        "dark": "无官方暗场体系;dark-deck 预设推导:米色系中性反转（背景 #37352F 系暖深）,文字反白,动作蓝提亮一档;正文对比度 ≥4.5:1 复检",
        "bounds": "大面积禁纯白 #FFF——用 #FBFBFA/#F7F6F3 暖面;色彩只作语义 accent 不作装饰;图标细线 1.5px 不填充;衬线只上标题,正文保持无衬线快扫",
    },
    {
        "file": "shopify.md",
        "primary": "#008060",
        "accent": "#0B1215",
        "pos": "Shopify-style dark commerce control-center — commerce platforms, merchant tooling, and retail business decks",
        "tone": "Dark-commerce, cinematic, terminal-sharp, platform-power, merchant-centric",
        "font": '-apple-system, "Segoe UI", Roboto, "Helvetica Neue", "Microsoft YaHei", sans-serif; display 用 200-300 超轻字重;等宽 "SF Mono", Menlo, monospace',
        "mood": "Deep dark surfaces like a mission-critical dashboard; ultra-light display type (300, even 200); neon green cuts through like a terminal cursor; dramatic moody photography; depth from background layering, not shadows",
        "palette": "深底:画布 #0B1215 · 面 #111820 · 浮层 #1A232B · 叠层 #222D38 · 正文 #FFFFFF · 次级 #637381 系;accent 绿 #008060（深浅两模态同值）;浅场:画布 #F6F7F8 · 卡面 #FFFFFF",
        "dark": "深色为主模态（dark-deck 原生）:#0B1215 → #222D38 表面分层,正文 #FFFFFF,绿 accent 只作交互语义（按钮/链接/选中）;浅模态仅辅助",
        "bounds": "neon green #008060 只作 surgical accent——按钮/链接/选中/焦点环,从不装饰;display 超轻字重是签名,别用重黑标题;摄影高对比深影棚调;数据密度靠层级不靠噪点",
    },
    {
        "file": "spotify.md",
        "primary": "#1DB954",
        "accent": "#121212",
        "pos": "Spotify-style dark vibrancy — music, media, entertainment platforms, and content-forward decks",
        "tone": "Immersive, bold, musical, confident, dark-first, cover-art-driven",
        "font": 'Circular（近似替代:系统 sans 栈）, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", "Microsoft YaHei", sans-serif;禁装饰体与衬线',
        "mood": "A club, not a boardroom: near-black canvas makes the green and album art explode forward; one accent hue carries the entire brand, all other color comes from content; energy at rest until something plays",
        "palette": "深底:画布 #121212 · 卡面 #181818 · 悬停 #282828 · 按下 #333333 · 正文 #FFFFFF · 次级 #B3B3B3 · 弱化 #6A6A6A;绿 #1DB954（亮变体 #1ED760 / 暗变体 #1AA34A）;语义 error #E91429 / warning #FFC862",
        "dark": "深色为主模态（dark-deck 原生）:#121212 三层表面,正文 #FFFFFF,绿 button 上文字用黑 #000000;内容色（专辑/封面）反哺表面 tint",
        "bounds": "绿是唯一品牌 accent——CTA/active/品牌锚点;其余色彩必须来自内容素材;深底上的绿文字对比度按 ≥4.5:1 复检（用亮变体 #1ED760 承担正文级绿色）;绿上文字一律黑",
    },
    {
        "file": "starbucks.md",
        "primary": "#00704A",
        "accent": "#1E3932",
        "pos": "Starbucks-style warm third-place craft — coffee, retail experience, community and craft-heritage decks",
        "tone": "Warm, inviting, community, craft, approachable, optimistic, artful",
        "font": '正文 "Sodo Sans"（近似替代系统 sans）, -apple-system, "Segoe UI", sans-serif;标题 "Pike"（近似替代窄体 sans）, "Arial Narrow";表达时刻 "Lander"（近似替代 Georgia 衬线）',
        "mood": "The page is a coffeehouse: cream walls and wood tables as warm neutrals, Siren green as the apron visible across the room, rounded corners as the curve of a ceramic cup; photography shows real people in real moments; illustration carries hand-drawn legacy",
        "palette": "亮场:画布暖奶油 #F2F0EB（永不纯白）· 卡面 #FFFFFF · 暖面 #FAF8F5 · 绿面 #D4E9E2 · 正文 House Green #1E3932 · Siren Green #00704A · Accent Green #00A862 · 金 #C2A461 · 边线 #E0DDD6",
        "dark": "官方暗场（dark-deck 预设直接采用）:画布 House Green 深绿 #1E3932（非纯黑）· 卡面 #2A4A40 · 浮层 #345C4F · 正文暖奶油 #F2F0EB;深底仍走绿色系与大地色",
        "bounds": "中性色必须暖调（禁冷灰主导）;绿是结构性品牌锚点不是装饰壁纸;插画承袭手绘线稿传统（Siren/线艺/季节画）,禁通用图标感;季节表达色系可演变但品牌绿始终在场",
    },
    {
        "file": "stripe.md",
        "primary": "#635BFF",
        "accent": "#0A2540",
        "pos": "Stripe-style engineered elegance — fintech, payments infrastructure, API platforms, and trust-forward SaaS decks",
        "tone": "Engineered elegance, airy authority, precise without cold, trust-forward",
        "font": 'Inter（签名:正文默认 weight-300）, -apple-system, "Segoe UI", Roboto, "Microsoft YaHei", sans-serif;代码 "JetBrains Mono", Consolas, Menlo, monospace',
        "mood": "Infrastructure you can trust rendered with Swiss-poster restraint: white canvas with signature purple gradients, deep navy wells for code and data, generous 96px+ section rhythm against tight 16-24px card padding",
        "palette": "亮场（主模态）:画布 #FFFFFF · 内嵌带 #F6F9FC · 边线 #E8ECF1 · 正文 #1A1F36 · 次级 #425466 · 紫 #635BFF（hover #7A73FF / 淡紫底 #E8E5FF）;深海军 #0A2540（暗段/代码井/页脚）",
        "dark": "官方深色段（dark-deck 预设可全盖 navy）:深海军 #0A2540 / #1A2E4A 分层成「井」,井内文字 #FFFFFF;dark-deck 预设可用 navy 全盖,正文反白,紫 accent 保持 #635BFF→#7A73FF",
        "bounds": "全系统禁衬线（UI 全 sans + 代码 mono）;weight-300 是非协商默认,强调靠 500/600 标题不靠加粗正文;display 负字距随字号缩放;渐变只走 #635BFF→#7A73FF 紫系;圆角 6-8px 卡 / 4px 输入",
    },
    {
        "file": "supabase.md",
        "primary": "#3ECF8E",
        "accent": "#1C1C1C",
        "pos": "Supabase-style developer-tooling identity — open-source infra, database and platform docs-grade decks",
        "tone": "Developer-tooling, terminal-dark, documentation-grade, surgical precision, open-source credibility",
        "font": 'Inter, system-ui, -apple-system, "Microsoft YaHei", sans-serif;代码块一等公民:mono 栈（"SF Mono"/JetBrains 系）',
        "mood": "IDE dark-mode borrowings: deep charcoal backgrounds, syntax-highlighted accents, monospaced code as first-class content; emerald green signals active/live/connected — a running Postgres instance made visible",
        "palette": "深底:画布 #1C1C1C · 侧栏/对话框 #151515 · 控制 #222222 · 面 #282828 · 按钮底 #2D2D2D · 边线 #343434/#3D3D3D · 正文 #ECECEC · 弱化 #9F9F9F;品牌绿 #3ECF8E（hover #34B97D / 深绿面 #15593B 系）",
        "dark": "深色为主模态（dark-deck 原生）:#1C1C1C 灰阶分层,正文 #ECECEC,绿 #3ECF8E 只给「active/live」语义;绿闪 rgba(62,207,142,0.1) 作状态变化反馈",
        "bounds": "绿 = 运行态语义（链接/active/live）,不作大面积装饰;代码块是内容不是装饰（$ CLI 提示语可进营销页）;表格行高 28px 的 spreadsheet 感优先于营销留白",
    },
    {
        "file": "tesla.md",
        "primary": "#000000",
        "accent": "#E82127",
        "pos": "Tesla-style radical subtraction — EV, energy, and engineering-brand decks that behave like film trailers",
        "tone": "Radical subtraction, cinematic, electric, powerful, silent, confident",
        "font": 'Universal Sans（近似替代 Inter）, "Inter", system-ui, "Microsoft YaHei", sans-serif',
        "mood": "Pure black voids; full-bleed hero imagery shot at golden hour or stark studio light; the product is the visual and UI recedes until needed; slow reveals, minimal text, maximum impact; silence as a design tool",
        "palette": "深底:画布纯黑 #000000 · 卡面 #171717 · 悬停面 #222222 · 正文 #FFFFFF · 次级冷灰 #A6A6A6 · 弱化钢灰 #5C5C5C;Tesla Red #E82127 仅 accent",
        "dark": "深色为主模态（dark-deck 原生）:void 黑 #000000,正文 #FFFFFF,层次只靠 #171717/#222222 面差;红只在错误态与罕见高光",
        "bounds": "近单色纪律:Tesla Red 每页至多一次;冷灰 #A6A6A6 承担一切非主内容;禁装饰元素/渐变/图案——留白与影像即设计;文字极简,一页一个主张",
    },
    {
        "file": "vercel.md",
        "primary": "#000000",
        "accent": "#0070F3",
        "pos": "Vercel-style monochrome engineering rigor — frontend infra, developer platforms, and systems-thinking decks",
        "tone": "Monochrome, precise, developer-tool, systematic, engineered, high-contrast",
        "font": '"Geist Sans"（近似替代 Inter）, -apple-system, "Segoe UI", Roboto, "Microsoft YaHei", sans-serif;等宽 Geist Mono 系',
        "mood": "Black and white precision, every pixel deliberate; signature blueprint grid (5-10% opacity line/dot matrix) signals systematic thinking on hero sections; information density high but never cluttered thanks to surgical typographic hierarchy",
        "palette": "深底（默认模态）:画布 #000000 · 面 #0A0A0A/#111111 · 按下 #1A1A1A · 边线 #1A1A1A→#2E2E2E · 正文 #EDEDED · 次级 #A1A1A1 · 反白面 #FAFAFA;accent 蓝 #0070F3 · error #EE0000 · success #00C853",
        "dark": "深色为 canonical 模态（dark-deck 原生）:纯黑画布 + 近黑面分层,正文 #EDEDED,高对比反白面 #FAFAFA 承担按钮;浅模态:画布 #FFFFFF · 正文 #171717（次级 #737373）",
        "bounds": "表面禁渐变、禁装饰插画、禁 ornament;accent 蓝 #0070F3 只上交互文本链接/焦点环/选中态,永不作面填充;调色板 95% 中性——色彩是信号不是装饰;blueprint 网格仅饰 hero/feature 区且不与内容争",
    },
]


def _render_md(card: dict) -> str:
    palette = " / ".join(card["palette"]) + "（首色为 accent）"
    lines = [
        f"# 图片渲染：{Path(card['file']).stem}（{card['slug']}）",
        "",
        f"**分类:** 08_图片渲染 · {card['group']}",
        "",
        f"**配对视觉风格:** {NO_PAIRING}",
        "",
        f"**定位:** {card['cn_pos']}",
        "",
        "## 1. 风格段落（paste-ready，可直接用于图片生成）",
        "",
        f"> {card['block']}{RENDER_GUARDRAIL}",
        "",
        "## 2. 线条 · 纹理 · 深度",
        "",
        "| 维度 | 处理 |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in card["ltd"]]
    lines += [
        "",
        f"> 渲染画法不写死 HEX;源卡参考色板 `{palette}` 与信息密度"
        f" `{card['density']}` 仅作 deck `colors` 锚点缺省时的默认建议。"
        "适用场景（源自卡 tags）：" + card["best_for"] + "。",
        "",
        "## 3. 来源与许可",
        "",
        f"- 源卡: `{card['src_id']}` · author: {card['author']} · "
        f"{NANO_SOURCE['repo']}",
        f"- 案例页: {card['url']}",
        f"- 许可: {NANO_SOURCE['license']} — {NANO_SOURCE['license_url']}"
        "（经 codex-slides `src/lib/community.ts` 快照 2026-08-31 映射;S2b 吸收）",
        "",
    ]
    return "\n".join(lines)


def _brand_md(brand: dict) -> str:
    lines = [
        f"# 品牌身份：{Path(brand['file']).stem}",
        "",
        "**分类:** 10_品牌身份",
        "",
        f"**主色:** {brand['primary']} · **强调色:** {brand['accent']}",
        "",
        f"**定位:** {brand['pos']}",
        "",
        "## VI 要点",
        "",
        f"- 语气：{brand['tone']}",
        f"- 字体：{brand['font']}",
        f"- 氛围：{brand['mood']}",
        f"- 色板（主模态）：{brand['palette']}",
        f"- 暗场变体：{brand['dark']}",
        f"- 使用边界：{brand['bounds']}",
        "",
        BRAND_FOOTER,
        "",
    ]
    return "\n".join(lines)


def _targets() -> list[tuple[Path, str]]:
    out = [(RENDER_DIR / c["file"], _render_md(c)) for c in RENDER_CARDS]
    out += [(BRAND_DIR / b["file"], _brand_md(b)) for b in BRANDS]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S2b 双源轴条目迁移器(codex-slides 社区生图卡 + xiaobei 品牌)"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="校验在盘文件与内嵌数据一致")
    mode.add_argument("--write", action="store_true", help="生成/覆盖目标文件（幂等）")
    args = parser.parse_args(argv)

    targets = _targets()
    drift: list[str] = []
    for path, content in targets:
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            continue
        if not path.is_file():
            drift.append(f"missing: {path.relative_to(SKILL_DIR)}")
        elif path.read_text(encoding="utf-8") != content:
            drift.append(f"drift: {path.relative_to(SKILL_DIR)}")

    if args.write:
        print(
            f"wrote {len(targets)} files "
            f"(08_图片渲染 +{len(RENDER_CARDS)}, 10_品牌身份 +{len(BRANDS)}; "
            f"skipped: {', '.join(s[0] for s in RENDER_SKIPPED)} + xiaobei ibm)"
        )
        return 0
    if drift:
        for item in drift:
            print(f"  ✗ {item}")
        print(f"check failed: {len(drift)} file(s) drift or missing")
        return 2
    print(
        f"OK: {len(targets)} files match "
        f"(renders={len(RENDER_CARDS)}, brands={len(BRANDS)}, "
        f"dedup-skipped={len(RENDER_SKIPPED)}+1)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
