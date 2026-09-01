#!/usr/bin/env python3
"""yixueAIganhuo-PPT + open-kimi-ppt-skill 吸收迁移器（风格进货批 S3 终批）。

按 docs/plans/2026-08-31-006 S3「价值精选」口径将两源转换为 leo 风格库
brief（markdown + GPT-Image-2 JSON 块），本批净增 16 主风格（≤18 配额带）：

- **yixueAIganhuo-PPT 医学 19 → 净 13**（新条目全部落
  ``02_行业内容域/医疗健康``，医疗域加密）：深蓝灰科研 / 冷蓝斜切 / 医学
  书卷 / 医学手稿答辩 / 暖陶土医学 / 深海军蓝医学 / 秋叶麦田水彩医学 /
  深蓝菱形答辩 / 青蓝水墨医学 / 雾感鼠尾草 / 医养同源水墨 / 森林绿临床
  水彩 / 黑白水墨临床。源 JSON 的色板/avoid_style → negative_prompt
  直迁；``continuity``/``asset_embedding`` 不迁（M1 已通用化为
  style-continuity 机制，避免重复）；6 个源文件与现库医疗 5 条 + 学术
  家族概念重复（SKIP 表）。
- **open-kimi-ppt-skill 30 套双段式 design.md → 精选 3**（落
  ``01_通用母版``）：黑金期刊（质感专业，finance/black-gold-ledger——
  黑白灰金融期刊台账 + 单金锚）/ 蓝焰作战室（科技数字，work/blue-flame-
  brand——近黑蓝作战室监控）/ 松烟画报（艺术表现，promotion/pine-soot-
  pictorial——近黑场电影感画报）。其余 27 套与现库 190 概念去重后跳过
  （SKIP 表：终端蓝紫/暖橙备忘/画册杂志/学术答辩/暖陶土等族均有覆盖）。

锚点来源纪律（source fidelity）：四角色 HEX 与 background 里的 HEX 必须能
在源文件原文（yixue JSON 全文 / open-kimi design.md 全文）中找到出处，
解析不到即 ``anchor_unprovenanced`` 拒绝，防止迁移时手写漂移。

自检门（复用 ``intake_ohmy`` 的同构实现，importlib 加载共享语义；
S1a/S2a/S3 门语义单一真值源）：

1. 四角色 palette 各含 #RRGGBB 锚点 + 身份字体声明（lint WARNING 子集）；
2. 文字对比锚（WCAG：primary 判深浅底，合并锚点须有 ≥4.5:1 文字锚）；
3. family_duplicate：新增指纹与全库指纹集合相等即拒绝（R-66）；
4. audit 同族判定副本（name_ratio ≥0.62 且共享 ≥1 HEX，或 name_ratio
   ≥0.45 且 jaccard ≥0.5，或 jaccard ≥0.6）：新增对（含新旧）聚簇即
   拒绝，保证 audit 疑似同族簇数不恶化。

用法::

    python3 scripts/intake_yixue_kimi.py --check   # 只跑自检门与文件一致性
    python3 scripts/intake_yixue_kimi.py --write   # 生成 brief（幂等覆盖同名）
    python3 scripts/intake_yixue_kimi.py --report  # 输出吸收决策报告

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
YIXUE_ROOT = Path("/Users/kuang/knowledge/ppt-github/yixueAIganhuo-PPT/references")
KIMI_ROOT = Path(
    "/Users/kuang/knowledge/ppt-github/open-kimi-ppt-skill/skills/"
    "open-kimi-ppt/reference/design_system"
)

# Gate semantics shared with the S1a intake (single source of truth).
_spec = importlib.util.spec_from_file_location("intake_ohmy", SCRIPT_DIR / "intake_ohmy.py")
ohmy = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("intake_ohmy", ohmy)
_spec.loader.exec_module(ohmy)

HEX_RE = ohmy.HEX_RE

# ---------------------------------------------------------------------------
# Intake decisions -- yixueAIganhuo-PPT (19 medical JSONs).
# 19 source files = 13 keep + 6 skip (concept dedupe vs library medical 5 +
# academic family). keep fields: name (all -> 02_行业内容域/医疗健康),
# vd (English visual_direction), pairing (08 render mate), anchors (four
# color_palette roles, each HEX verbatim from the source JSON), bg (canvas
# background anchors, prose allowed when the source names no bg HEX),
# scenes, aliases, composition, layout, negatives (from avoid_style +
# negative_constraints), typo (from typography_and_evidence), best_for.
# ---------------------------------------------------------------------------
MEDICAL_KEEP: dict[str, dict] = {
    "003_深蓝灰医学研究汇报PPT风格提示词.json": {
        "name": "深蓝灰科研风",
        "vd": "dark slate medical research system, monochrome clinical imagery "
              "under deep slate bands with engineering-amber highlight tags, "
              "hospital-grade formal reporting",
        "pairing": "企业摄影",
        "anchors": {
            "primary": "#152A36(深蓝灰主色/标题锚)",
            "secondary": "#263946(压色块)",
            "accent": "#F2A900(医学信息高亮黄)",
            "neutral": "#1F2F3A(深文字锚)",
        },
        "bg": ["#F7F8F8", "#FFFFFF", "#D9DEE1"],
        "scenes": ["临床研究汇报", "病例分析", "医学答辩", "公共卫生课题"],
        "aliases": ["深蓝灰", "深蓝灰医学", "slate medical research"],
        "composition": "黑白灰医学图像底色 + 深蓝灰压色块 + 工程黄高亮点缀",
        "layout": [
            "黑白医学底图叠深蓝灰半透明横向色带",
            "黄色编号标签 + 圆形/六边形编号建立识别",
            "内容页白底细线框 + 顶部小标题栏 + 页脚细线",
            "高信息密度但留白充足,视觉稳定学院化",
        ],
        "negatives": [
            "不要大面积鲜艳渐变、霓虹或科幻 UI",
            "不要黄色点缀滥用或深蓝灰色块遮挡主体内容",
            "不要卡通插画或杂志海报化",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "思源黑体 Heavy 超粗中文标题,字面宽大,层级明确",
            "body": "思源黑体/微软雅黑 Regular 小字号,行距紧凑但清晰",
            "labels": "DIN/Arial Narrow 大写英文,粗体几何编号置于黄色标签",
        },
        "best_for": "黑白灰医学图像底色+深蓝灰压色+工程黄高亮的严谨学院化汇报;适合临床研究汇报/病例分析/医学答辩/公共卫生课题",
    },
    "004_冷蓝斜切生物医学汇报PPT风格提示词.json": {
        "name": "冷蓝斜切医学风",
        "vd": "cold-blue biomedical deck, white academic layout with navy "
              "diagonal-cut geometry and coral accents, rigorous research "
              "infographic",
        "pairing": "扁平几何",
        "anchors": {
            "primary": "#243A52(深海军蓝主色/标题锚)",
            "secondary": "#5F8FB4(医学蓝灰)",
            "accent": "#F1644A(珊瑚橙强调)",
            "neutral": "#637282(灰蓝正文)",
        },
        "bg": ["#F4F8FB", "#D9EAF3"],
        "scenes": ["生物医学汇报", "医学博士答辩", "医学科研课题", "医学会议报告"],
        "aliases": ["冷蓝斜切", "斜切生物医学", "cold blue diagonal medical"],
        "composition": "纯白/淡冷灰底 + 深蓝珊瑚橙斜切几何色带 + 白底圆角卡片栅格",
        "layout": [
            "左上深蓝大标题 + 小号英文副题,珊瑚橙下划线统一识别",
            "页面边缘/右下深蓝与珊瑚橙斜切几何色带作母版装饰",
            "白底圆角卡片 + 浅灰描边 + 轻微投影 + 严格栅格大面积留白",
            "低透明分子网络/DNA 双螺旋/点阵矩阵背景",
        ],
        "negatives": [
            "不要深色整页背景",
            "不要斜切装饰压迫正文",
            "不要卡片大小无规律或元素随机摆放",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "思源黑体 Heavy 深蓝 #20364F,字号大且稳重",
            "body": "思源黑体 Regular 灰蓝 #637282,行距宽松",
            "labels": "Arial/Calibri 小号英文副题,ExtraBold 深蓝圆形编号",
        },
        "best_for": "白底冷蓝学术版式+珊瑚橙强调+斜切几何母版;适合生物医学汇报/医学博士答辩/医学科研课题/医学会议报告",
    },
    "006_生物医学书卷风医学汇报PPT风格提示词.json": {
        "name": "医学书卷风",
        "vd": "medical scholarly bookish deck, ivory paper texture with "
              "terracotta-brown structural bands and graphite-gray text, quiet "
              "academic scroll",
        "pairing": "手绘笔记",
        "anchors": {
            "primary": "#B9856F(陶土棕/标题锚)",
            "secondary": "#3F3F3F(深石墨灰正文)",
            "accent": "#6F8794(雾蓝灰点缀)",
            "neutral": "#8A837B(暖灰说明)",
        },
        "bg": ["象牙白/暖米白/浅灰白纸张质感"],
        "scenes": ["医学院答辩", "医学科研汇报", "大学医学院课题", "生物医学研究"],
        "aliases": ["医学书卷", "生物医学书卷", "medical bookish"],
        "composition": "暖纸质感 + 陶土棕结构色 + 严格学术栅格,安静书卷气",
        "layout": [
            "页眉标题区 8%-13%,主体证据区 72%-84%,底部来源 4%-10%",
            "两位数字章节编号 + 细线分割 + 竖向信息轴建立秩序",
            "右侧竖向医学图片拼贴与陶土棕竖向色块",
            "页眉短条/侧边栏承载结构,页面边距宽松",
        ],
        "negatives": [
            "不要深色背景或高饱和撞色",
            "不要夸张圆角与强烈阴影",
            "不要装饰线稿压过医学证据",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "宋体/明朝体高字重衬线标题,字距略放大",
            "body": "宋体/仿宋正文,行距宽松",
            "labels": "Helvetica/思源黑体图表标注与页码,陶土棕章节编号",
        },
        "best_for": "象牙纸质感+陶土棕结构的书卷气医学科研;适合医学院答辩/医学科研汇报/大学医学院课题",
    },
    "007_生物医学手稿论文答辩PPT风格提示词.json": {
        "name": "医学手稿答辩风",
        "vd": "biomedical manuscript defense, ivory manuscript paper with navy "
              "ink annotations and sage lab-sketch margins, vintage scholarly "
              "handwriting temper",
        "pairing": "手绘笔记",
        "anchors": {
            "primary": "#0B2344(深海军蓝/标题锚)",
            "secondary": "#5F86A9(灰蓝批注)",
            "accent": "#C9BFA8(暖灰米框线)",
            "neutral": "#14223A(深蓝黑正文)",
        },
        "bg": ["#F7F4EC"],
        "scenes": ["论文答辩", "实验流程汇报", "机制探索", "科研结果展示"],
        "aliases": ["医学手稿", "手稿答辩", "medical manuscript defense"],
        "composition": "象牙纸医学研究手稿 + 蓝色科研标注 + 实验室素描边纹",
        "layout": [
            "细窄浅米色外框 + 充足内部留白",
            "深海军蓝页眉页脚编号,灰蓝手写批注与编号圆点",
            "淡蓝色医学手绘草图背景纹理(DNA/细胞/神经元/实验器材)",
            "象牙纸面 + 蓝色科研标注的答辩叙事结构",
        ],
        "negatives": [
            "不要纯白无质感的普通办公模板",
            "不要过度复古泛黄或把科研插图改成铜版画风",
            "不要元素随机摆放或没有对齐关系",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "Georgia/Cormorant Garamond Bold 英文 + 思源宋体加粗中文",
            "body": "思源黑体/Inter Regular,行距宽松",
            "labels": "灰蓝小标签,图表标注与目录条目低调",
        },
        "best_for": "象牙纸医学手稿+海军蓝标注+实验室素描边纹;适合论文答辩/实验流程汇报/机制探索/科研结果展示",
    },
    "008_暖陶土细胞医学学术PPT风格提示词.json": {
        "name": "暖陶土医学风",
        "vd": "warm terracotta medical academic, ivory-cream ground with "
              "clay-brown titles and slate-blue wave accents, gentle cell "
              "aesthetics meets rigorous reporting",
        "pairing": "矢量插画",
        "anchors": {
            "primary": "#B45A3C(暖陶土棕/标题锚)",
            "secondary": "#25323B(深蓝灰辅助)",
            "accent": "#C9825F(铜橙点缀)",
            "neutral": "#1F292E(近黑蓝灰文字)",
        },
        "bg": ["#F7F0E6", "#FBF6EF", "#F3E4D4"],
        "scenes": ["生物医学汇报", "生命科学", "临床研究", "实验医学汇报"],
        "aliases": ["暖陶土", "暖陶土医学", "terracotta medical"],
        "composition": "暖色学术 + 柔和细胞美学:象牙白底 + 陶土棕标题 + 大面积留白严格栅格",
        "layout": [
            "大面积留白 + 左对齐信息层级 + 严格栅格",
            "角落暖棕有机曲线色块与深蓝灰波浪色块",
            "细胞粒子/分子连线/点阵/细弧线轨迹低调装饰",
            "圆形描边外框医学科研图标,单色线性",
        ],
        "negatives": [
            "不要深色背景或霓虹赛博",
            "不要装饰压过证据内容",
            "不要过度拥挤的数据区",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "宋体/明朝体 Bold-High 高对比衬线标题,笔画清晰锋利",
            "body": "思源黑体 Regular,行距舒展",
            "labels": "窄体无衬线大写英文小号辅助,陶土棕线性图标",
        },
        "best_for": "暖陶土细胞美学与严谨科研排版结合;适合生物医学/生命科学/临床研究/实验医学汇报",
    },
    "009_深海军蓝浅蓝医学科研模板PPT风格提示词.json": {
        "name": "深海军蓝医学风",
        "vd": "deep navy medical research template, white high-whitespace ground "
              "with navy title system and light-blue cards, cool rational "
              "academic formality",
        "pairing": "数字仪表盘",
        "anchors": {
            "primary": "#0B2E5F(深海军蓝/标题锚)",
            "secondary": "#DCEBF7(医学浅蓝)",
            "accent": "#4AA6B5(青绿点缀)",
            "neutral": "#071F3F(深蓝黑文字)",
        },
        "bg": ["#FFFFFF", "#F6F9FC", "#EEF6FB"],
        "scenes": ["高校医学院汇报", "附属医院科研", "医学中心", "国际医学会议"],
        "aliases": ["深海军蓝", "海军蓝医学", "navy medical research"],
        "composition": "白底高留白 + 深蓝标题系统 + 浅蓝描边卡片,冷色医学科研统一模板感",
        "layout": [
            "左对齐标题系统,大号章节编号/深蓝编号块",
            "浅蓝描边卡片 + 圆角信息框 + 三/四栏模块",
            "上下分区数据面板,深蓝表头浅色表格底纹",
            "低透明分子线/细胞膜弧线/虚线箭头装饰,圆角端点线性图标",
        ],
        "negatives": [
            "不要深色背景或大面积高饱和渐变",
            "不要图标和插图抢占证据图位置",
            "不要元素自由漂浮或没有对齐关系",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "思源黑体 700-900 方正深海军蓝大标题",
            "body": "思源黑体 400-500,行距宽松,深蓝黑/灰蓝",
            "labels": "condensed/几何无衬线全大写小号英文,粗体深蓝编号",
        },
        "best_for": "深海军蓝+浅蓝白底高留白冷色科研模板;适合高校医学院/附属医院/医学中心/国际医学会议",
    },
    "010_秋叶麦田水彩医学汇报PPT风格提示词.json": {
        "name": "秋叶麦田水彩医学风",
        "vd": "autumn wheat-field watercolor medical, pale blue sky wash with "
              "golden-brown foliage edges and tidy academic grids, gentle "
              "nature-toned research",
        "pairing": "水彩晕染",
        "anchors": {
            "primary": "#B08A3A(金棕/标题锚)",
            "secondary": "#3F3F3F(深灰正文)",
            "accent": "#E7A54B(暖橙点缀)",
            "neutral": "#111111(近黑文字)",
        },
        "bg": ["#EAF7FB", "#F6FBFD", "#F2E6C9"],
        "scenes": ["医学科研汇报", "医学院课题汇报", "临床研究总结", "学术会议报告"],
        "aliases": ["秋叶麦田", "秋叶麦田水彩", "autumn wheat watercolor medical"],
        "composition": "淡蓝天空白云水彩底 + 顶部棕枝淡叶 + 底部米黄麦穗远山带,边缘低干扰装饰",
        "layout": [
            "居中标题 + 右上大号两位数字章节编号 + 金棕短横线",
            "金棕/深灰交替圆形线性图标,树状分支图与横向时间轴",
            "四栏图标说明 + 左右对称流程 + 图文证据区",
            "严格演示文稿网格,自然元素不遮挡标题与证据",
        ],
        "negatives": [
            "不要高饱和色或深色背景",
            "不要装饰叶片遮挡正文或医学证据",
            "不要把科研插图本体画成水彩树枝麦穗装饰画",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "思源黑体 Bold-Heavy 近黑方正标题",
            "body": "思源黑体 Regular 深灰小字号多行短文本",
            "labels": "几何无衬线全大写金棕英文,金棕粗体数字编号",
        },
        "best_for": "浅蓝天空+金棕秋叶麦田水彩与医学信息图结合;适合医学科研汇报/医学院课题汇报/临床研究总结",
    },
    "011_深蓝菱形论文答辩PPT风格提示词.json": {
        "name": "深蓝菱形答辩风",
        "vd": "indigo diamond defense deck, warm white ground with deep-blue "
              "diamond nodes and diagonal geometry blocks, disciplined thesis "
              "order",
        "pairing": "扁平几何",
        "anchors": {
            "primary": "#1F2A66(论文深蓝/标题锚)",
            "secondary": "#C9CDD6(银灰辅助)",
            "accent": "#33407A(靛蓝强调)",
            "neutral": "#111111(近黑标题副字)",
        },
        "bg": ["#F6F6F4", "#FFFFFF", "#D9DEE8"],
        "scenes": ["医学博士答辩", "课题开题", "中期汇报", "科研成果报告"],
        "aliases": ["深蓝菱形", "菱形答辩", "indigo diamond defense"],
        "composition": "大面积暖白高留白 + 低饱和论文深蓝菱形/斜切几何 + 隐形网格信息秩序",
        "layout": [
            "左上深蓝竖向双条 + 黑色中文标题 + 右上深蓝菱形页码",
            "隐形网格组织图文分栏/四宫格卡片/圆形节点/菱形流程",
            "深蓝填充卡 + 白色线性图标与白色短文字",
            "封面左侧大面积深蓝斜切几何块 + 浅灰斜线纹理三角",
        ],
        "negatives": [
            "不要整页深色背景",
            "不要菱形和卡片过度堆叠",
            "不要斜切装饰压迫正文",
            "不要复制固定答辩示例内容或虚构机构信息",
        ],
        "typo": {
            "title": "思源黑体 Bold 近黑 #111111,层级明确",
            "body": "思源黑体 Regular 深灰 #333333",
            "labels": "全大写无衬线 Light 字距加宽,深蓝菱形白色页码",
        },
        "best_for": "低饱和论文深蓝+菱形几何+高留白答辩秩序;适合医学博士答辩/课题开题/中期汇报/科研成果报告",
    },
    "013_青蓝水墨医学汇报PPT风格提示词.json": {
        "name": "青蓝水墨医学风",
        "vd": "teal ink-wash medical, xuan-paper ground with blue-green mist "
              "mountains, cinnabar seals and thin gold lines, oriental clinical "
              "quietude",
        "pairing": "水墨笔记",
        "anchors": {
            "primary": "#1F5D6D(医学深青蓝/标题锚)",
            "secondary": "#8FB8C4(雾蓝)",
            "accent": "#B43A2E(朱砂红编号章)",
            "neutral": "#163F4C(深墨蓝文字)",
        },
        "bg": ["#F5F7F4", "#D7E6E8", "#C8DEE5"],
        "scenes": ["临床研究汇报", "中西医结合", "疾病科普", "健康管理"],
        "aliases": ["青蓝水墨", "青蓝水墨医学", "teal ink-wash medical"],
        "composition": "青蓝水墨+宣纸肌理+云雾留白与严谨医学信息设计结合,安静清透克制",
        "layout": [
            "中国风留白与医学学术网格结合,安全边距 4%-6%",
            "朱砂圆形编号章 + 深墨蓝标题 + 暗金/浅灰蓝 1px 细线",
            "左图右文:图片区 38%-48%,文字区 46%-56%,中间留 4%-6%",
            "半透明柔白/浅雾蓝卡片,圆角轻微,水墨远山靠边靠底",
        ],
        "negatives": [
            "不要沿用普通蓝白医院模板",
            "不要水墨装饰压过医学内容或宣纸纹理过脏",
            "不要红色印章滥用或暗金大面积铺色",
            "不要把科研机制图本体画成水墨画",
        ],
        "typo": {
            "title": "宋体/思源宋体/仿宋中字重标题,传统笔触但规范可读",
            "body": "思源宋体/仿宋,行距较大,字距略松",
            "labels": "朱砂红圆章编号,1.5px 医学线性图标 #1F5D6D",
        },
        "best_for": "青蓝水墨+宣纸肌理+云雾留白的东方医学汇报;适合临床研究汇报/中西医结合/疾病科普/健康管理",
    },
    "014_雾感鼠尾草医疗服务PPT风格提示词.json": {
        "name": "雾感鼠尾草风",
        "vd": "misty sage healthcare, fog-gray green palette on warm white, "
              "translucent sage cards and soft medical photography, calm "
              "trusted service air",
        "pairing": "企业摄影",
        "anchors": {
            "primary": "#9BA890(雾感鼠尾草绿/标题锚)",
            "secondary": "#A8B19F(灰橄榄绿)",
            "accent": "#7FAE9A(医疗薄荷绿)",
            "neutral": "#3F4140(深炭灰文字)",
        },
        "bg": ["#FAFAF7", "#F1F3F0", "#EEF0ED"],
        "scenes": ["医院介绍", "临床护理", "体检中心", "健康管理", "医疗服务展示"],
        "aliases": ["雾感鼠尾草", "鼠尾草医疗", "misty sage healthcare"],
        "composition": "雾感低饱和医疗绿体系:大面积留白 + 矩形色块 + 细线分割 + 半透明鼠尾草绿信息卡",
        "layout": [
            "大面积留白 + 矩形色块 + 细线分割",
            "竖排英文分类/超大浅灰绿页码贴近边缘",
            "半透明鼠尾草绿信息卡 + 低饱和柔雾绿滤镜医学摄影",
            "阴影柔和对比度低,秩序化信息呈现",
        ],
        "negatives": [
            "不要深色背景或高饱和撞色",
            "不要粗重黑体压迫版面或厚边框",
            "不要彩虹图表或复杂 3D 图表",
            "不要装饰图标和植物纹样抢占医学证据位置",
        ],
        "typo": {
            "title": "思源黑体/Noto Sans SC Regular-Medium,不用粗重黑体",
            "body": "Noto Sans SC Light 无衬线正文,行高宽松",
            "labels": "全大写无衬线 Light 字距加宽,医用深绿灰",
        },
        "best_for": "雾感鼠尾草绿低饱和医疗服务气质;适合医院介绍/临床护理/体检中心/健康管理/医疗服务展示",
    },
    "015_医养同源水墨草本医学汇报PPT风格提示词.json": {
        "name": "医养同源水墨风",
        "vd": "herbal ink-wash TCM wellness, rice-paper ground with ink-green "
              "herb motifs and cinnabar seal accents, east-asian medicine "
              "scholarly mist",
        "pairing": "水墨笔记",
        "anchors": {
            "primary": "#2F4A3A(墨绿/标题锚)",
            "secondary": "#A8B7AE(淡竹青/卡片层次)",
            "accent": "#B43A2E(朱砂印章)",
            "neutral": "#1F2623(深墨黑文字)",
        },
        "bg": ["#F7F6F1", "#EEF1EE", "#E2E5E1"],
        "scenes": ["中医药课题汇报", "临床观察", "健康管理汇报", "医学科普"],
        "aliases": ["医养同源", "水墨草本", "herbal ink-wash TCM"],
        "composition": "东方水墨+宣纸肌理+草本医学的融合学术模板:低饱和雾化留白充足",
        "layout": [
            "东方水墨学术栅格,主体内容占页面 66%-78%",
            "墨绿大标题 + 章节编号 + 朱砂印章少量点缀",
            "淡墨山水/云纹/草药枝叶低透明背景",
            "雾灰绿分割线 + 冷灰白卡片边界",
        ],
        "negatives": [
            "不要纯白硬质办公模板",
            "不要满屏山水装饰或过度古风海报",
            "不要把科研机制插图改成水墨装饰画",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "书法楷行/毛笔笔触大标题,墨绿 #2F4A3A,少量大号",
            "body": "思源宋体/仿宋/Noto Serif CJK 常规字重,行距宽松",
            "labels": "Garamond 英文术语,朱砂印章式编号",
        },
        "best_for": "东方水墨草本与中医药研究的融合学术模板;适合中医药课题/临床观察/健康管理汇报/医学科普",
    },
    "017_森林绿水彩临床医学PPT风格提示词.json": {
        "name": "森林绿临床水彩风",
        "vd": "forest-green watercolor clinical, white ground with deep green "
              "watercolor washes, black ink splashes and diagonal photo crops, "
              "humane clinical narrative",
        "pairing": "水彩晕染",
        "anchors": {
            "primary": "#2F5F4A(医用森林绿/标题锚)",
            "secondary": "#18382D(深墨绿)",
            "accent": "#F3D46B(消毒黄点缀)",
            "neutral": "#111111(黑墨迹文字)",
        },
        "bg": ["#FFFFFF", "#FAF8F1", "#F7F4EA"],
        "scenes": ["临床研究", "护理康复", "医院介绍", "患者教育", "医疗科研汇报"],
        "aliases": ["森林绿临床", "森林绿水彩", "forest green clinical watercolor"],
        "composition": "白底大面积留白 + 森林绿水彩晕染 + 黑色墨迹泼溅 + 斜向几何照片裁切",
        "layout": [
            "强烈留白 + 斜向几何切割 + 三角/梯形照片裁切",
            "不规则水彩遮罩 + 干刷笔触 + 淡圆环 + 短横线",
            "透明浅色块 + 极细分割线 + 线性医学图标",
            "真实医学场景照低饱和绿色调,水彩边缘融入页面",
        ],
        "negatives": [
            "不要冷硬办公模板或深色整页背景",
            "不要墨迹和水彩遮挡正文或医学证据",
            "不要照片硬边拼贴或过度水墨化",
            "不要虚构医院/大学名称或伪参考文献",
        ],
        "typo": {
            "title": "Didot/Bodoni/Playfair Display Bold + 思源宋体加粗中文",
            "body": "思源宋体/衬线正文近黑 #111111,行距宽松",
            "labels": "深墨绿衬线小标签,消毒黄关键点点缀",
        },
        "best_for": "森林绿水彩+墨迹泼溅+斜切照片裁切的临床叙事;适合临床研究/护理康复/医院介绍/患者教育",
    },
    "018_黑白水墨临床研究PPT风格提示词.json": {
        "name": "黑白水墨临床风",
        "vd": "black-white ink-wash clinical research, xuan-white paper with "
              "monochrome mist mountains and hospital linework, quiet "
              "monochrome academic zen",
        "pairing": "水墨笔记",
        "anchors": {
            "primary": "#111111(墨黑/标题锚)",
            "secondary": "#6F7476(雾灰)",
            "accent": "#8FA8A6(青灰编号章)",
            "neutral": "#4A4F50(中性灰)",
        },
        "bg": ["#F4F5F2", "#E9ECE8"],
        "scenes": ["中医现代化", "临床研究", "病例讨论", "健康管理实践"],
        "aliases": ["黑白水墨临床", "黑白水墨医学", "monochrome ink clinical"],
        "composition": "东方黑白水墨+宣纸白+雾化山水+医院建筑线稿的融合学术模板",
        "layout": [
            "宣纸白 + 云雾灰底,水墨远山与医院剪影靠边",
            "墨黑大标题 + 章节标题 + 关键编号与主要线条",
            "青灰圆形编号章 + 关键数据 + 低饱和图表色块点缀",
            "黑白灰层次,不用高饱和红蓝绿",
        ],
        "negatives": [
            "不要沿用普通蓝白医院模板",
            "不要高饱和红蓝绿或满屏山水装饰",
            "不要墨迹压住正文或宣纸纹理过脏",
            "不要把科研机制图本体画成水墨画",
        ],
        "typo": {
            "title": "宋体/思源宋体/Noto Serif CJK 500-600,书籍目录感端正可读",
            "body": "宋体/仿宋 300-400,行距较疏",
            "labels": "Garamond/Times 小型大写,青灰圆形编号章",
        },
        "best_for": "黑白水墨宣纸与临床研究的融合学术模板;适合中医现代化/临床研究/病例讨论/健康管理实践",
    },
}

MEDICAL_SKIP: dict[str, dict] = {
    "001_通用医学汇报PPT风格提示词.json": {
        "leo": "医疗学术风",
        "reason": "普通蓝白医院模板概念已覆盖,且源文件无 HEX 锚点可迁移",
    },
    "002_暖米复古论文答辩医学汇报PPT风格提示词.json": {
        "leo": "医学手稿答辩风",
        "reason": "同为暖纸论文答辩族,本批取手稿版(007),暖米复古并入",
    },
    "005_生物医学冷蓝期刊风PPT风格提示词.json": {
        "leo": "学术期刊风",
        "reason": "冷蓝白期刊排版概念已由教育学术轴覆盖",
    },
    "012_秋麦水彩暖棕医学汇报PPT风格提示词.json": {
        "leo": "秋叶麦田水彩医学风",
        "reason": "同族秋麦水彩暖棕,本批取秋叶麦田版(010)",
    },
    "016_暖棕人文医疗品牌PPT风格提示词.json": {
        "leo": "医院品牌风",
        "reason": "人文医疗品牌概念已覆盖(信任+温度)",
    },
    "019_浅粉棕医院运营PPT风格提示词.json": {
        "leo": "医院品牌风",
        "reason": "浅粉棕暖人文医院表达与医院品牌风同族",
    },
}

# ---------------------------------------------------------------------------
# Intake decisions -- open-kimi-ppt-skill (30 dual-part design systems).
# 30 sources = 3 keep + 27 skip. keep fields: name, subdir (under
# 01_通用母版), vd, pairing, anchors (HEX verbatim from design.md), bg,
# scenes, aliases, composition, layout, negatives (from Prohibited),
# typo, best_for. Path is relative to the design_system root.
# ---------------------------------------------------------------------------
KIMI_KEEP: dict[str, dict] = {
    "finance/black-gold-ledger": {
        "name": "黑金期刊风",
        "subdir": "质感专业",
        "vd": "financial-periodical ledger order, white evidence pages with "
              "hairline tables and axis-free charts, quarter dark judgment "
              "pages, single gold anchor discipline",
        "pairing": "杂志编辑",
        "anchors": {
            "primary": "#0A0A0A(墨黑标题/顶规线锚)",
            "secondary": "#3D3C3A(暖深灰正文)",
            "accent": "#D6A000(唯一金锚)",
            "neutral": "#606060(副文灰/单位)",
        },
        "bg": ["#FFFFFF", "#151515"],
        "scenes": ["投研报告", "尽调", "估值汇报", "基金季报", "机构年报"],
        "aliases": ["黑金期刊", "黑金台账", "black gold ledger"],
        "composition": "白证据页 3/4 + 深炭判断页 1/4,黑白灰数据台阶 + 单金锚(<3% 面积/页)",
        "layout": [
            "白色证据页:细黑顶规线+结论式标题+灰色依据副题+浅灰分割线",
            "深色判断页:字距加宽英文小标+白色结论标题+编号判断/通栏浅卡",
            "横线表格无竖线无斑马纹,数据标签直标在图形标记上",
            "封面短粗金线+右置超大浅灰水印字+底部黑色依据带",
        ],
        "negatives": [
            "不要彩色图表序列或第二强调色(数据一律灰阶)",
            "不要红绿涨跌对,不要饼图/雷达/3D/阴影/渐变",
            "不要 y 轴网格图框或只能靠图例读图",
            "不要大面积金色铺陈(单页<3%,一页一金焦点)",
        ],
        "typo": {
            "title": "思源黑体 700-800 结论式标题,一律左对齐",
            "body": "思源黑体 400 正文,数字列对齐带千分位",
            "labels": "全大写无衬线 Light tracking 0.20-0.28em 金融刊眉",
        },
        "best_for": "黑白灰金融期刊台账+单金锚的证据/判断双色温节奏;适合投研报告/尽调/估值/基金季报/机构年报",
    },
    "work/blue-flame-brand": {
        "name": "蓝焰作战室风",
        "subdir": "科技数字",
        "vd": "late-night operations war room, near-black blue ground with "
              "flame-cyan and ice-blue data tiers, amber anomalies, fixed "
              "four-corner monitoring skeleton",
        "pairing": "数字仪表盘",
        "anchors": {
            "primary": "#06070B(近黑蓝底/标题锚)",
            "secondary": "#F7F8FA(冷白主标题)",
            "accent": "#1FB9D5(火焰青品牌锚)",
            "neutral": "#DFA93C(琥珀异常语义)",
        },
        "bg": ["#06070B", "#020307"],
        "scenes": ["运营复盘", "经营分析", "指标监控", "项目状态汇报"],
        "aliases": ["蓝焰作战室", "作战室", "blue flame war room"],
        "composition": "近黑蓝底作战室:火焰青=达成/进度,冰蓝大数字,琥珀=异常与后果,摄影只留封面",
        "layout": [
            "固定四角骨架:业务属主左上/报告信息右上/结论带 83%-90%/页脚依据页码",
            "环形进度仪表+12 点刻度,火焰青=达成,琥珀=缺口,每页至多 3 个",
            "正文栏比 35:65 或 60:40,超细竖线分栏,比较型 23% 总览+三同构栏",
            "发丝线+留白+字重分层组织模块,不用面板",
        ],
        "negatives": [
            "不要默认圆角卡片墙或无依据的均匀等分版式",
            "不要蓝紫渐变/霓虹玻璃卡等无依据配色",
            "不要图表背景另填色块(与页底同色或透明)",
            "不要摄影进入正文页(封面除外)",
        ],
        "typo": {
            "title": "思源黑体同句混排:常规陈述+粗体结论,2.3-2.5 倍正文",
            "body": "思源黑体正文;表格可整体换宋体/明朝体衬线对撞",
            "labels": "窄数字工业仪表感,单位同基线缩小约半",
        },
        "best_for": "近黑蓝底作战室监控+火焰青/冰蓝数据双层+琥珀异常语义;适合运营复盘/经营分析/指标监控/项目状态汇报",
    },
    "promotion/pine-soot-pictorial": {
        "name": "松烟画报风",
        "subdir": "艺术表现",
        "vd": "pine-soot cinematic pictorial, near-black fields hard-split "
              "with full-bleed cinematic photography, white Inter type and "
              "one-off cover red-magenta bursts",
        "pairing": "企业摄影",
        "anchors": {
            "primary": "#000101(近黑场/标题锚)",
            "secondary": "#FFFFFF(白色正文字)",
            "accent": "#EF1722(封面红一次性爆发)",
            "neutral": "#FD1AEE(封面洋红窄条纹)",
        },
        "bg": ["#000101", "#000000"],
        "scenes": ["品牌画报", "影视宣发", "视觉叙事", "机构形象"],
        "aliases": ["松烟画报", "电影画报", "pine soot pictorial"],
        "composition": "近黑场与全幅电影感摄影硬分割(约 44%/56%),白字只落在黑场/压暗层,红洋红仅封面一次性",
        "layout": [
            "照片/黑场硬分割 43.7%/56.3% 可镜像,方角贴边,黑发丝线接缝",
            "顶部五个微导航锚点+左下四位页码,贴页缘且在正文网格外",
            "下部属性标签组:4-10 个透明细白描边胶囊,ALL CAPS 两行排布",
            "封面左 59% 全幅特写+右 41% 黑场与红洋红竖条纹",
        ],
        "negatives": [
            "不要在正文页使用红/洋红或彩色界面块",
            "不要圆角照片、悬浮卡片或阴影白边",
            "不要白字直接压在亮部照片上(先重新裁剪)",
            "不要用插画或 3D 替代摄影证据",
        ],
        "typo": {
            "title": "Inter SemiBold 大标题,可 2-3 行,行高 0.6-0.7em 收紧",
            "body": "Inter Regular 双栏正文",
            "labels": "Inter SemiBold 全大写属性胶囊标签,四位索引竖排",
        },
        "best_for": "近黑场与全幅电影感摄影硬分割+白色字组;适合品牌画报/影视宣发/视觉叙事/机构形象",
    },
}

KIMI_SKIP: dict[str, dict] = {
    "academic/blue-line-courseware": {"leo": "教学课件风", "reason": "白底电蓝结构色课件概念已覆盖"},
    "academic/deep-blue-atlas": {"leo": "商务几何风", "reason": "白底深蓝线性推理图表与商务几何同类"},
    "academic/paper-white-courseware": {"leo": "教学课件风", "reason": "暖纸白课程件与教学课件/书卷族同类"},
    "academic/pastel-derivation": {"leo": "数学可视化教学风", "reason": "白板推导+变量语义色与数学可视化教学同类"},
    "academic/teal-green-academic-defense": {"leo": "学术论文答辩风", "reason": "白底青绿结构色答辩与学术论文答辩同类"},
    "academic/wine-red-data": {"leo": "科研答辩风", "reason": "白底酒红讲义型学术汇报已覆盖"},
    "consulting/apricot-white-brief": {"leo": "顾问报告风", "reason": "杏白咨询简报与顾问报告族同类"},
    "consulting/indigo-due-diligence": {"leo": "战略咨询风", "reason": "靛蓝尽调与咨询研究族同类"},
    "consulting/marine-blue-research": {"leo": "战略咨询风", "reason": "海军蓝楷体结论咨询研究与咨询族同类"},
    "consulting/moss-green-transformation": {"leo": "顾问报告风", "reason": "苔绿转型咨询与顾问报告族同类"},
    "consulting/pine-green-strategy": {"leo": "战略咨询风", "reason": "松绿战略页眉摄影与咨询族同类"},
    "consulting/red-black-growth": {"leo": "锐利黑白风", "reason": "红黑高对冲增长汇报与锐利宣言族同类"},
    "finance/ebony-ledger": {"leo": "黑金期刊风", "reason": "同族黑白灰台账,本批取黑金期刊版"},
    "finance/honey-orange-memo": {"leo": "稳重商务风", "reason": "暖白深蓝骨架亮橙锚与商务蓝橙族同类"},
    "finance/lake-blue-memo": {"leo": "银行年报风", "reason": "湖蓝机构编辑报告与金融年报族同类"},
    "finance/prospect-annual": {"leo": "投资机构风", "reason": "深navy薄荷绿年度节奏与机构募资族同类"},
    "finance/rice-paper-annual": {"leo": "现代周报风", "reason": "暖纸白超粗黑年报与周报纪律族同类"},
    "promotion/aqua-charity-report": {"leo": "温暖手工风", "reason": "水色公益报告与公益温度叙事族同类"},
    "promotion/cream-collage": {"leo": "温暖手工风", "reason": "奶油纸拼贴与手工拼贴(scrapbook collage)概念已覆盖"},
    "promotion/silver-gray-luxury-magazine": {"leo": "静奢极简风", "reason": "冷白银灰奢侈品编辑与静奢概念同类"},
    "promotion/silk-yellow-magazine": {"leo": "杂志大字风", "reason": "粗边杂志单章色与杂志大字族同类"},
    "promotion/travel-green-handbook": {"leo": "日式生活杂志风", "reason": "灰米纸人文手册与生活杂志手册族同类"},
    "work/electric-violet-business": {"leo": "Dracula紫风", "reason": "单一电紫焦点与紫系单强调族同类"},
    "work/moon-white-imagery": {"leo": "创意杂志风", "reason": "月白意象画册与高端编辑杂志画册族同类"},
    "work/sky-blue-wayfinding": {"leo": "清爽专业风", "reason": "天蓝导视工作汇报与蓝白清爽族同类"},
    "work/warm-clay-works": {"leo": "暖陶土医学风", "reason": "窑制陶土暖白与本批暖陶土族同类(跨轴同气质)"},
    "work/warm-jade-annual-report": {"leo": "财报季报风", "reason": "暖玉年报状态灯与财报状态汇报族同类"},
}


# ---------------------------------------------------------------------------
# Source parsing
# ---------------------------------------------------------------------------
def _hexes(text: str) -> set[str]:
    return {h.upper() for h in HEX_RE.findall(text)}


def parse_yixue(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    meta = data.get("metadata", {})
    return {
        "file": path.name,
        "source_name": meta.get("name", path.stem),
        "purpose": meta.get("purpose", ""),
        "anchors": _hexes(raw),
    }


def parse_kimi(dir_path: Path) -> dict:
    doc = dir_path / "design.md"
    raw = doc.read_text(encoding="utf-8") if doc.is_file() else ""
    return {
        "dir": str(dir_path.relative_to(dir_path.parents[1])),
        "anchors": _hexes(raw),
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


def build_brief(keep: dict, pack: dict, *, reference: str) -> tuple[dict, list[str]]:
    anchors = keep["anchors"]
    bg_items = list(keep["bg"])
    bg_hexes = [h for item in bg_items for h in HEX_RE.findall(item)]
    bg_desc = "→".join(bg_items)
    role_hexes = [HEX_RE.search(v).group(0) for v in anchors.values()]
    rule = (
        f"锚点 {', '.join(role_hexes)};来源:源文件色板原文直迁;"
        f"{pack.get('purpose') or keep['best_for'].split(';')[0]}"
    )
    brief = {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": keep["name"],
        "aliases": _dedupe([keep["name"], *keep["aliases"]]),
        "best_for": keep["best_for"],
        "visual_direction": keep["vd"],
        "canvas": {
            "aspect_ratio": "16:9",
            "background": f"{bg_desc} ({keep['name']}底)",
            "composition": keep["composition"],
            "density": "low-to-medium, 保持风格留白节奏",
        },
        "color_palette": {**anchors, "rule": rule[:160]},
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
        "reference": reference,
    }
    return brief, bg_hexes


def render_markdown(brief: dict, header: str, scenes: list[str]) -> str:
    lines = [
        f"# {brief['style_name']}",
        "",
        f"**分类:** {header}",
        "",
        "**适用场景:**",
    ]
    lines += [f"- {s}" for s in (scenes or ["通用演示"])[:5]]
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


def yixue_target(keep: dict) -> Path:
    return STYLES_ROOT / "02_行业内容域" / "医疗健康" / f"{keep['name']}.md"


def kimi_target(keep: dict) -> Path:
    return STYLES_ROOT / "01_通用母版" / keep["subdir"] / f"{keep['name']}.md"


# ---------------------------------------------------------------------------
# Gates + pipeline (mirror of intake_ohmy.run, shared semantics)
# ---------------------------------------------------------------------------
def run(yixue_packs: dict[str, dict], kimi_packs: dict[str, dict], *, write: bool):
    problems: list[str] = []
    written = 0

    if not YIXUE_ROOT.is_dir():
        return [f"source missing: {YIXUE_ROOT}"], 2
    if not KIMI_ROOT.is_dir():
        return [f"source missing: {KIMI_ROOT}"], 2

    own_targets = {str(yixue_target(k)) for k in MEDICAL_KEEP.values()} | {
        str(kimi_target(k)) for k in KIMI_KEEP.values()
    }
    existing = [
        (rel, name, brief)
        for rel, name, brief in ohmy.load_existing_briefs()
        if str(STYLES_ROOT / rel) not in own_targets
    ]

    generated: dict[str, tuple[dict, Path, dict]] = {}
    for src_id, keep in sorted(MEDICAL_KEEP.items()):
        if src_id not in yixue_packs:
            problems.append(f"intake_table_stale: MEDICAL_KEEP 引用源文件 {src_id} 不存在")
            continue
        pack = {**yixue_packs[src_id], "scenes": keep["scenes"]}
        brief, bg_hexes = build_brief(
            keep, pack, reference=f"GitHub: yixueAIganhuo-PPT · references/{src_id}"
        )
        generated[f"yixue/{src_id}"] = (brief, yixue_target(keep), pack)
    for src_id, keep in sorted(KIMI_KEEP.items()):
        if src_id not in kimi_packs:
            problems.append(f"intake_table_stale: KIMI_KEEP 引用源目录 {src_id} 不存在")
            continue
        pack = {**kimi_packs[src_id], "scenes": keep["scenes"]}
        brief, bg_hexes = build_brief(
            keep, pack,
            reference=f"GitHub: open-kimi-ppt-skill · reference/design_system/{src_id}/design.md",
        )
        generated[f"kimi/{src_id}"] = (brief, kimi_target(keep), pack)

    # Gate 0: source fidelity -- every anchor HEX must appear in the source.
    for src_id, (brief, path, pack) in generated.items():
        provenance = pack["anchors"]
        for role, value in brief["color_palette"].items():
            if role == "rule":
                continue
            for hexm in HEX_RE.findall(value):
                if hexm.upper() not in provenance:
                    problems.append(
                        f"anchor_unprovenanced: {brief['style_name']}.{role} {hexm} 不在源文件 token 中"
                    )
        bg_text = brief["canvas"]["background"]
        for hexm in HEX_RE.findall(bg_text):
            if hexm.upper() not in provenance:
                problems.append(
                    f"anchor_unprovenanced: {brief['style_name']} background {hexm} 无出处"
                )

        # Gate 1: role anchors + identity font (lint WARNING subset).
        for role in ("primary", "secondary", "accent", "neutral"):
            if not HEX_RE.search(brief["color_palette"][role]):
                problems.append(f"role_no_hex: {brief['style_name']}.{role}")
        typo = brief["typography"]
        if not ohmy.FONT_IDENTITY_RE.search(" ".join(str(v) for v in typo.values())):
            problems.append(f"typography_no_identity: {brief['style_name']}")

        # Gate 2: WCAG text anchor -- roles only, mirroring
        # lint_style_governance._check_text_anchor (bg hexes are deck
        # context, not text anchors).
        anchors = ohmy.palette_anchors(brief["color_palette"], [])
        primary_hex = HEX_RE.search(brief["color_palette"]["primary"]).group(0)
        if not ohmy.text_anchor_ok(anchors, primary_hex):
            problems.append(f"text_anchor_missing: {brief['style_name']}")

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
            header = (
                "02_行业内容域 · 医疗健康"
                if src_id.startswith("yixue/")
                else f"01_通用母版 · {path.parent.name}"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                render_markdown(brief, header, pack.get("scenes")), encoding="utf-8"
            )
            written += 1
    return [], 0


def report() -> str:
    lines = [
        f"S3 终批吸收决策: yixueAIganhuo-PPT 19 = 保留 {len(MEDICAL_KEEP)} + 跳过 {len(MEDICAL_SKIP)};"
        f" open-kimi-ppt-skill 30 = 保留 {len(KIMI_KEEP)} + 跳过 {len(KIMI_SKIP)};"
        f" 净增 {len(MEDICAL_KEEP) + len(KIMI_KEEP)}",
        "",
        "yixue 跳过映射(概念已有):",
    ]
    for f in sorted(MEDICAL_SKIP):
        lines.append(f"  - {f} -> {MEDICAL_SKIP[f]['leo']}({MEDICAL_SKIP[f]['reason']})")
    lines += ["", "open-kimi 跳过映射(概念已有):"]
    for d in sorted(KIMI_SKIP):
        lines.append(f"  - {d} -> {KIMI_SKIP[d]['leo']}({KIMI_SKIP[d]['reason']})")
    lines += [
        "",
        "落位:",
        "  - 02_行业内容域/医疗健康: 13 条(医疗域加密)",
        "  - 01_通用母版/质感专业: 黑金期刊风",
        "  - 01_通用母版/科技数字: 蓝焰作战室风",
        "  - 01_通用母版/艺术表现: 松烟画报风",
        "  - continuity/asset_embedding 不迁(M1 已通用化)",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="yixueAIganhuo-PPT + open-kimi-ppt-skill 吸收迁移器(S3 终批)"
    )
    parser.add_argument("--write", action="store_true", help="生成 brief 文件(幂等)")
    parser.add_argument("--check", action="store_true", help="只跑去重门与自检")
    parser.add_argument("--report", action="store_true", help="输出吸收决策报告")
    args = parser.parse_args(argv)

    if args.report:
        print(report())
        return 0

    yixue_packs = {}
    for p in sorted(YIXUE_ROOT.glob("[0-9]*.json")):
        pack = parse_yixue(p)
        yixue_packs[pack["file"]] = pack
    kimi_packs = {}
    if KIMI_ROOT.is_dir():
        for d in sorted(KIMI_ROOT.iterdir()):
            if d.is_dir() and (d / "design.md").is_file():
                kimi_packs[d.name] = parse_kimi(d)
        # PART B signature systems live one level deeper (finance/consulting/
        # work/promotion/academic); index them by "<group>/<name>".
        for group in sorted(KIMI_ROOT.iterdir()):
            if not group.is_dir():
                continue
            for d in sorted(group.iterdir()):
                if d.is_dir() and (d / "design.md").is_file():
                    kimi_packs[f"{group.name}/{d.name}"] = parse_kimi(d)

    problems, code = run(yixue_packs, kimi_packs, write=args.write)
    for item in problems:
        print(f"  ✗ {item}", file=sys.stderr)
    if code:
        print(f"intake gate FAILED ({len(problems)} problems)", file=sys.stderr)
        return 2
    action = "written" if args.write else "checked"
    print(
        f"intake OK ({action}): yixue keep={len(MEDICAL_KEEP)} skip={len(MEDICAL_SKIP)}; "
        f"kimi keep={len(KIMI_KEEP)} skip={len(KIMI_SKIP)}"
    )
    if args.write:
        print(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
