#!/usr/bin/env python3
"""风格推荐硬规则层（R-61 / R-62 接线件，试点 R-63 的 bypass 语义）。

对应《Style推荐引擎设计》第三节硬规则层：规则只做两类事——**排除低级
错配**与**锁定强语境**，全部可被用户显式点名否决（bypass_all）。家族
粒度以 `template-library/reference/sources/retired-styles-tree/styles/00_索引/_INDEX.md` 的实际分类为准（通用母版
五组 / 行业内容域十二组 / 场景七组 / 顶层内置 11），家族是标签不是互斥
分区：一个风格可同时属多系（荧光高对比科技风 ∈ 科技暗色系 + 高攻击系）。

用法::

    python3 scripts/style_hard_rules.py --check-brief '{"genre":"论文答辩"}'
    python3 scripts/style_hard_rules.py --self-test

``--check-brief`` 输入合同信号（genre/domain/audience/formality/culture/
content_shape/named_style，值用中文关键词，列表或单值均可），输出 JSON：

    {"bypassed":false,"exclude_families":[...],"lock_families":[...],
     "prefer_families":{family:count},"triggered_rules":[...]}

语义：exclude = 候选池剔除；lock = 强语境锁定（仅在锁定系内选，冲突时
lock 胜出 exclude）；prefer = 加分不锁定（按命中规则数累计）。用户点名
（named_style 非空）→ bypass_all，规则层零输出，由 style 合同记录依据
（点名优先序见 references/style-recommendation.md 第三节）。

退出码：0 = 正常（含零触发）；2 = 用法错误 / JSON 不可解析 / 自检失败。
纯 stdlib、确定性（纯集合运算，无随机无 IO）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime/src"))

# ---------------------------------------------------------------------------
# Family vocabulary: keys are rule-facing labels, members reference real style
# names from _INDEX.md groups (top-level builtins + 01/02/03 group members).
# A style may belong to more than one family; families are tags, not partitions.
# ---------------------------------------------------------------------------
FAMILIES: dict[str, list[str]] = {
    "党政红": ["党政红风格", "政府工作报告风", "党建活动风"],
    # R-66 家族合并同步：变体名保留在原家族（文件与 style_name 不删），
    # 合并簇的主风格补入相应家族，防规则层对合并后语境失明。
    "学术答辩": ["科研答辩风", "学术论文答辩风", "学术期刊风",
                 "学术会议风", "毕业答辩风", "课题申请风"],
    "商务专业": ["麦肯锡咨询风", "稳重商务风", "简约商务风", "商务几何风",
                 "CEO高级商务风", "金融奢华风", "静奢极简风", "清爽专业风",
                 "成果汇报风", "战略咨询风", "商业计划书风", "融资路演风",
                 "创业大赛路演风", "暗夜奢华风", "极简奢侈品牌风",
                 "深色编辑报告风", "风投路演风", "现代周报风",
                 "勃艮第红风", "鎏金象牙风", "橄榄奶白风", "北极冷风",
                 # C4 批新增（awesome-ppt-skills 地产空间/dashi 色谱图表）。
                 "地产空间风", "色谱图表风",
                 # C1 批新增（gpt-image2-ppt-skills 深蓝工作坊/荧光黄计划书）。
                 "深蓝极简工作坊风", "荧光黄商务风",
                 # C3 批新增（beautiful-html-templates 杂志封面商务双件）。
                 "祖母绿刊头风", "林间三色季刊风"],
    "科技暗色": ["暗黑科技风", "科技未来感风", "荧光高对比科技风",
                 "东京夜风", "Dracula紫风", "Gruvbox暗风",
                 "Catppuccin摩卡风", "深色弥散风", "蓝焰作战室风",
                 # C4 批新增（xhs 深色科技杂志/awesome-ppt-skills Web3）。
                 "深色科技杂志风", "Web3加密风",
                 # C3 批新增（huashu-design Linear 式暗线终端 + 黑底 keynote 剧场）。
                 "暗线终端风", "黑底数字剧场风"],
    "科技浅色": ["全息棱镜科技风", "玻璃拟态风", "产品发布会风",
                 "未来科技编辑风", "Catppuccin拿铁风", "日光浅风",
                 # C1 批新增（gpt-image2-ppt-skills Stripe 蓝白路演）。
                 "Stripe蓝白风",
                 # C3 批新增（huashu-design bento 指标卡）。
                 "便当格卡片风"],
    "工程蓝图": ["工程蓝图风", "代码开发者风", "蓝晒图纸风", "终端命令行风",
                 "工程白图风"],
    "极简排版": ["极简风", "瑞士网格风", "暖调柔形风", "黑白极简艺术展风",
                 "电子墨水杂志风", "粗野报刊风", "和纸柔光风", "日式生活杂志风",
                 # C3 批新增（beautiful-html-templates 象牙账本 +
                 # huashu-design 纯文字备忘录）。
                 "象牙账本风", "宣言备忘录风"],
    "复古潮流": ["蒸汽波风", "合成波风", "像素复古风", "装饰艺术风",
                 "中世纪现代风", "里索印刷风", "复古电视风", "Y2K铬金属风",
                 # C3 批新增（Win95 视窗 + 70s 磁带包装 + supper-club 餐牌）。
                 "复古视窗风", "樱彩磁带包装风", "复古晚宴餐牌风"],
    "波普孟菲斯": ["波普艺术风", "孟菲斯风", "大字报巨型排版风", "孟菲斯新潮风",
                   # C3 批新增（Memphis-meets-editorial 胶囊卡）。
                   "胶囊卡波普风"],
    "高攻击": ["新粗野主义风", "荧光高对比科技风", "粗野报刊风", "锐利黑白风",
               # C3 批新增（WPA 抗议海报的大声排印）。
               "行动主义海报风"],
    "艺术手绘": ["手绘白板风", "手绘技术解释风", "复古扁平插画风",
                 "温暖手工风", "水彩晕染风", "创意杂志风", "手绘秋日手账风",
                 "吉卜力手绘风",
                 # C3 批新增（便利贴墙/别针手账/黑板粉笔）。
                 "便利贴拼贴风", "别针手账风", "粉笔黑板风"],
    "卡通儿童": ["3D软体卡通风", "黏土定格风", "中小学课堂风", "教学课件风",
                 "童趣暖橙风",
                 # C3 批新增（academic-ppt-master 剪纸的儿童/民俗亲和面）。
                 "立体剪纸风"],
    "水墨国风": ["水墨禅意风", "迷幻国潮风", "传统色叙事风",
                 "水墨江南风", "故宫墨红风", "凝脂杨妃风", "米白樱粉风",
                 "青绿湖蓝风", "春日嫩柳风", "青莲碧蓝风", "国风暖阳风",
                 "东方意境插画风", "宋韵听雨风"],
    "数据图表": ["数据仪表盘风", "麦肯锡咨询风", "商务几何风", "色谱图表风",
                 # C3 批新增（Bloomberg/Economist 出版级密度 + bento 指标卡）。
                 "数据新闻编辑风", "便当格卡片风"],
    # R-66 merge cluster: 财报季报风's master 商业计划书风 stays visible
    # to the finance-audit prefer pool.
    "金融审计": ["银行年报风", "投资机构风", "财报季报风", "四大审计风",
                 "保险品牌风", "商业计划书风"],
    "医疗健康": ["医疗学术风", "医药发布会风", "健康科普插画风",
                 "医院品牌风", "临床试验风",
                 # S3 终批吸收 yixueAIganhuo-PPT（医疗域加密 13 条）。
                 "深蓝灰科研风", "冷蓝斜切医学风", "医学书卷风",
                 "医学手稿答辩风", "暖陶土医学风", "深海军蓝医学风",
                 "秋叶麦田水彩医学风", "深蓝菱形答辩风", "青蓝水墨医学风",
                 "雾感鼠尾草风", "医养同源水墨风", "森林绿临床水彩风",
                 "黑白水墨临床风"],
    "消费营销": ["快消营销风", "电商大促风", "时尚品牌风", "新消费品牌风",
                 # C4 批新增（awesome-ppt-skills 美妆个护/达人营销）。
                 "美妆个护风", "达人营销风",
                 # C3 批新增（huashu-design 单色品牌海报 campaign 面）。
                 "单色满版海报风"],
    # R-66 merge cluster: 在线教育风's master 互联网产品风 stays visible
    # to the k12-courseware prefer pool.
    "教学课件": ["教学课件风", "中小学课堂风", "在线教育风", "数学可视化教学风",
                 "互联网产品风",
                 # C3 批新增（黑板板书 + CS50/高桥流一屏一概念教学剧场）。
                 "粉笔黑板风", "高桥流糖果舞台风"],
    "艺术表现": ["3D软体卡通风", "水彩晕染风", "水墨禅意风", "迷幻国潮风",
                 "低多边形风", "像素复古风", "黏土定格风", "博物馆纪念风",
                 "现代插画编辑风", "薄荷清新风", "山野葱郁风", "手绘秋日手账风",
                 "吉卜力手绘风", "松烟画报风", "暗夜植物园风",
                 # C1 批新增（gpt-image2-ppt-skills 抽象画册/有机渐变）。
                 "抽象艺术画册风", "有机渐变形风",
                 # C3 批新增（beautiful-html-templates 手作/印刷四件 +
                 # academic-ppt-master 剪纸/黑板）。
                 "便利贴拼贴风", "模版印刷标语风", "复古晚宴餐牌风",
                 "别针手账风", "立体剪纸风", "粉笔黑板风"],
    "游戏娱乐": ["像素复古风", "声波霓虹风"],
    # S1a 批新增家族（oh-my-ppt 吸收，_INDEX 01_通用母版 新子目录）：
    # 终端配色（流行终端主题）/ 设计流派（编辑与宣言）/ 东方意蕴（中式细分）/
    # 柔和治愈 / 夜空氛围 / 质感专业。成员同时挂靠上方语义家族（标签非互斥）。
    "终端配色": ["北极冷风", "Catppuccin拿铁风", "Catppuccin摩卡风", "Dracula紫风",
                 "Gruvbox暗风", "北欧风", "玫瑰松风", "日光浅风", "东京夜风"],
    "设计流派": ["复古电视风", "新闻播报风", "杂志大字风", "杂志衬线风",
                 "高级撞色风", "锐利黑白风", "多巴胺活力撞色风", "Y2K铬金属风",
                 # C4 批新增（xhs 个人品牌宣言/工具清单 + frontend-slides
                 # 活页标签手册）。
                 "个人品牌宣言风", "工具清单风", "活页标签手册风",
                 # C1 批新增（gpt-image2-ppt-skills 黑白杂志/双色调/拟物
                 # 文件夹/荧光黄撞色）。
                 "黑白杂志风", "珊瑚紫双色调风", "纸质文件夹拟物风",
                 "荧光黄商务风",
                 # C3 批新增（beautiful 7 件海报/编辑 + academic 摄影编辑 +
                 # huashu 单色海报/糖果舞台）。
                 "复古视窗风", "双年展海报风", "钴蓝网格简报风",
                 "樱彩磁带包装风", "行动主义海报风", "柔彩衬线编辑风",
                 "全幅摄影编辑风", "单色满版海报风", "高桥流糖果舞台风"],
    "东方意蕴": ["水墨江南风", "故宫墨红风", "凝脂杨妃风", "米白樱粉风",
                 "青绿湖蓝风", "春日嫩柳风", "青莲碧蓝风", "国风暖阳风",
                 "东方意境插画风", "宋韵听雨风"],
    "柔和治愈": ["情绪疗愈色卡风", "樱花治愈风", "奶油温柔风", "柔雾甜梦风",
                 "樱粉雾蓝风", "小红书白风", "日落暖风", "晴橙落日海风",
                 "童趣暖橙风", "夜间独白风"],
    "夜空氛围": ["极光风", "梦幻星河风", "星火夜空风", "深色弥散风",
                 "夜间独白风"],
    "质感专业": ["风投路演风", "现代周报风", "勃艮第红风", "鎏金象牙风",
                 "橄榄奶白风", "黑金期刊风",
                 # C3 批新增（数据新闻 + 黑底剧场 + 杂志封面商务双件）。
                 "数据新闻编辑风", "黑底数字剧场风",
                 "祖母绿刊头风", "林间三色季刊风"],
    # S2a 批新增家族（LandPPT 吸收，_INDEX 01_通用母版 新子目录）：
    # 中式载体（简/卷/纸的载体材质向，与东方意蕴色彩向正交）/
    # 印象派油画（莫奈/星月夜）。成员同时挂靠上方语义家族（标签非互斥）。
    "中式载体": ["竹简风", "中式书卷风", "宣纸风"],
    "印象派油画": ["莫奈风", "星月夜风"],
    # C1 批新增家族（gpt-image2-ppt-skills 吸收，行业×美学组合）：
    # 煤炭工业（矿业粗野）/ 时尚咨询（fashion consulting 工具包）/
    # 美食编辑（fine-dining 杂志）/ 新闻编辑（深蓝红双色调新闻，新闻播报风
    # 同时挂靠设计流派）。参考池代表为 14_参考池_gpt-image2 的 7 个可整池
    # 选用风格（不计入 _INDEX 主风格口径）。
    "煤炭工业": ["煤炭工业风"],
    "时尚咨询": ["时尚咨询工具包风"],
    "美食编辑": ["高级料理杂志风"],
    "新闻编辑": ["新闻播报风", "深蓝红新闻编辑风"],
    "参考池代表": ["莫兰迪暖调编辑池", "莫兰迪冷调编辑池", "莫兰迪深色雕塑池",
                   "朋克深底撞色池", "朋克白底撞色池", "科技深底霓虹池",
                   "科技浅底净色池"],
    # C2 批新增家族（slides-grab 韩式 design-diversity + OfficeCLI 吸收，
    # _INDEX 16_来源_slides-grab/韩式精密网格 + 15_来源_officecli）：
    # 韩式咨询（MBB 动作标题/企业 IR 的韩式语法，与商务专业标签非互斥）/
    # 精密网格（tokens 级网格纪律向，韩式公共报告 + OfficeCLI 明度分组
    # 挂靠——variant-dimension 六分组在 brief 头部标注，规则层不按明度分家）。
    "韩式咨询": ["咨询精密网格风", "MBB幽灵框架风", "BCG展板风", "投行IR编辑风",
                 "战略藏青风", "精密金融科技风", "集团IR克制风", "星幕金字塔风",
                 "卡片新闻财报风", "黄金网格演讲风"],
    "精密网格": ["咨询精密网格风", "数据信息密集风", "单色基础设施风",
                 "粗块信息图风", "档案索引风", "黄金网格演讲风",
                 "韩式政策报告风", "韩式政府浅蓝风", "政策口号书法风",
                 "全幅极简演讲风", "极简单色笔记风", "植物有机编辑风",
                 "温暖款待风", "电影感演讲风",
                 # C2 OfficeCLI 吸收（variant-dimension 明度第二维度）。
                 "流光液态风", "鼠尾草谷物暗纹风", "聚光舞台风", "斜切重工风",
                 "色差故障风", "粉紫编辑风", "大地有机风",
                 # C2 西式精选。
                 "暗黑学院风", "彩窗马赛克风"],
}

# Rules: keyword containment over contract signals. `when` uses singular string
# fields (genre/audience/culture, substring match on any keyword) and list
# fields (domain, any-item substring match); formality/data_pages thresholds.
# Effects: exclude / lock / prefer family keys from FAMILIES.
RULES: list[dict] = [
    {
        "id": "academic-defense",
        "when": {"genre": ["答辩", "开题", "结题", "中期检查", "基金申报", "课题"]},
        "lock": ["学术答辩"],
        "exclude": ["复古潮流", "波普孟菲斯", "高攻击"],
    },
    {
        "id": "academic-journal",
        "when": {"genre": ["期刊", "论文投稿", "学术出版"]},
        "prefer": ["学术答辩", "极简排版"],
        "exclude": ["波普孟菲斯", "复古潮流"],
    },
    {
        "id": "party-gov-lock",
        "when": {"culture": ["党政", "党建", "政府", "机关", "公文", "支部", "体制内"]},
        "lock": ["党政红"],
        "exclude": ["复古潮流", "波普孟菲斯", "高攻击", "游戏娱乐"],
    },
    {
        "id": "gov-publicity",
        "when": {"genre": ["政策宣讲", "政务宣传", "主题党日"]},
        "lock": ["党政红"],
    },
    {
        "id": "kids-education",
        "when": {"audience": ["儿童", "小学生", "中学", "小学", "幼儿园", "孩子", "少儿"]},
        "exclude": ["高攻击", "工程蓝图"],
        "prefer": ["卡通儿童", "艺术手绘"],
    },
    {
        "id": "k12-courseware",
        "when": {"genre": ["课件", "公开课", "课堂", "讲义", "教案"]},
        "prefer": ["教学课件", "卡通儿童"],
    },
    {
        "id": "investor-pitch-tech",
        "when": {"genre": ["路演", "融资", "BP", "商业计划"],
                 "domain": ["科技", "互联网", "AI", "大模型", "软件", "web3", "SaaS"]},
        "prefer": ["科技暗色"],
    },
    {
        "id": "investor-pitch-general",
        "when": {"genre": ["路演", "融资", "BP", "商业计划"]},
        "prefer": ["商务专业", "金融审计"],
    },
    {
        "id": "board-formal-report",
        "when": {"genre": ["董事会", "述职", "决算", "汇报", "年报"],
                 "formality_min": 0.8},
        "prefer": ["商务专业"],
        "exclude": ["复古潮流"],
    },
    {
        "id": "medical-serious",
        "when": {"domain": ["医疗", "医药", "临床", "医院", "药企", "药监"]},
        "prefer": ["医疗健康"],
        "exclude": ["波普孟菲斯", "复古潮流", "消费营销"],
    },
    {
        "id": "finance-audit",
        "when": {"domain": ["金融", "银行", "审计", "证券", "保险", "投行", "四大"]},
        "prefer": ["金融审计", "商务专业"],
        "exclude": ["波普孟菲斯", "复古潮流", "消费营销"],
    },
    {
        "id": "consulting-legal",
        "when": {"domain": ["咨询", "法律", "律所", "尽调", "合规"]},
        "prefer": ["商务专业"],
        "exclude": ["复古潮流", "波普孟菲斯"],
    },
    {
        "id": "tech-launch",
        "when": {"genre": ["发布会", "新品", "上市"],
                 "domain": ["科技", "互联网", "AI", "大模型", "软件", "SaaS"]},
        "prefer": ["科技暗色", "科技浅色"],
    },
    {
        "id": "engineering-manufacturing",
        "when": {"domain": ["制造", "工程", "能源", "工业", "汽车", "机械", "建筑"]},
        "prefer": ["工程蓝图"],
    },
    {
        "id": "data-dense-report",
        "when": {"data_pages_min": 0.5},
        "prefer": ["数据图表"],
    },
    {
        "id": "chinese-ink",
        "when": {"culture": ["国风", "水墨", "禅意", "茶道", "节气"]},
        "prefer": ["水墨国风"],
        "exclude": ["复古潮流"],
    },
    {
        "id": "guochao-trend",
        "when": {"culture": ["国潮"]},
        "prefer": ["水墨国风"],
    },
    {
        "id": "casual-sharing",
        "when": {"formality_max": 0.3},
        "prefer": ["艺术手绘"],
        "exclude": ["工程蓝图"],
    },
    {
        "id": "dev-community",
        "when": {"domain": ["开发者", "开源", "编程", "程序"]},
        "prefer": ["工程蓝图"],
    },
    {
        "id": "ecommerce-promo",
        "when": {"genre": ["大促", "带货", "促销", "种草"]},
        "prefer": ["消费营销"],
    },
    {
        "id": "ceremony-event",
        "when": {"genre": ["典礼", "晚会", "颁奖", "峰会", "开幕"]},
        "prefer": ["艺术表现"],
        "exclude": ["工程蓝图"],
    },
]


def current_family_members(styles_root: Path | None = None) -> dict[str, list[str]]:
    """家族成员视图（U10 后）：template-library brief 的 taxonomy.families
    为作者真值，未声明家族的成员仍消费 FAMILIES 兼容表。

    ``styles_root`` 指向新库 styles 目录（默认 template-library/canonical/
    styles）。「未分类」是迁移占位标签，不构成家族；v2 schema 家族词表开放，
    未见过的标签按新家族桶收录（可见，不静默并入已知家族）。
    """
    root = Path(styles_root) if styles_root is not None else \
        SKILL_DIR / "template-library" / "canonical" / "styles"
    result = {label: list(names) for label, names in FAMILIES.items()}
    if root.is_dir():
        for brief_path in sorted(root.glob("*/brief.json")):
            try:
                brief = json.loads(brief_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            name = brief.get("name")
            taxonomy = brief.get("taxonomy")
            families = taxonomy.get("families") if isinstance(taxonomy, dict) else None
            if not isinstance(name, str) or not name.strip() or not isinstance(families, list):
                continue
            families = [str(family) for family in families
                        if isinstance(family, str) and family.strip() and family != "未分类"]
            if not families:
                continue
            for names in result.values():
                if name in names:
                    names.remove(name)
            for family in families:
                result.setdefault(family, []).append(name)
    return {label: sorted(set(names)) for label, names in result.items()}


def _as_text_list(value) -> list[str]:
    # Normalize a scalar / list signal field into a list of strings.
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _keywords_hit(signal_value, keywords: list[str]) -> bool:
    # Containment match, case-insensitive: any keyword appears in any value.
    values = _as_text_list(signal_value)
    return any(
        kw.lower() in value.lower()
        for value in values
        for kw in keywords
    )


def _rule_matches(rule: dict, brief: dict) -> bool:
    # Every declared `when` condition must hold (AND across fields).
    when = rule.get("when", {})
    for field in ("genre", "audience", "culture"):
        if field in when and not _keywords_hit(brief.get(field), when[field]):
            return False
    if "domain" in when and not _keywords_hit(brief.get("domain"), when["domain"]):
        return False
    formality = brief.get("formality")
    if "formality_min" in when:
        if not isinstance(formality, (int, float)) or formality < when["formality_min"]:
            return False
    if "formality_max" in when:
        if not isinstance(formality, (int, float)) or formality > when["formality_max"]:
            return False
    data_pages = (brief.get("content_shape") or {}).get("data_pages") \
        if isinstance(brief.get("content_shape"), dict) else None
    if "data_pages_min" in when:
        if not isinstance(data_pages, (int, float)) or data_pages < when["data_pages_min"]:
            return False
    return True


def evaluate(brief: dict) -> dict:
    """Run the rule layer over one contract brief. Pure and deterministic."""
    named = str(brief.get("named_style") or "").strip()
    if named:
        # Explicit user pick always wins: bypass_all (engine design §3 override).
        return {
            "bypassed": True,
            "bypass_reason": f"用户点名：{named}（点名优先序，规则层零输出）",
            "exclude_families": [],
            "lock_families": [],
            "prefer_families": {},
            "triggered_rules": [],
        }

    exclude: set[str] = set()
    lock: set[str] = set()
    prefer: dict[str, int] = {}
    triggered: list[str] = []
    for rule in RULES:
        if not _rule_matches(rule, brief):
            continue
        triggered.append(rule["id"])
        exclude.update(rule.get("exclude", []))
        lock.update(rule.get("lock", []))
        for fam in rule.get("prefer", []):
            prefer[fam] = prefer.get(fam, 0) + 1

    # Conflict resolution: lock is a stronger context commitment than exclude.
    exclude -= lock
    return {
        "bypassed": False,
        "bypass_reason": None,
        "exclude_families": sorted(exclude),
        "lock_families": sorted(lock),
        "prefer_families": {k: prefer[k] for k in sorted(prefer)},
        "triggered_rules": triggered,
    }


# ---------------------------------------------------------------------------
# Self-test: positive/negative samples mirroring engine design §7 adversarial
# cases, plus vocabulary integrity checks against silent rule drift.
# ---------------------------------------------------------------------------
def _library_style_names() -> set[str]:
    """template-library 名称全集（成员存在性检查的真值源）。

    canonical 风格 brief 名称 + reference 参考池实体名（14_参考池 的池代表
    按账本 migrate-as-is 进 reference/pools，不是 style brief）。
    """
    names: set[str] = set()
    styles_root = SKILL_DIR / "template-library" / "canonical" / "styles"
    for brief_path in sorted(styles_root.glob("*/brief.json")):
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = brief.get("name")
        if isinstance(name, str) and name.strip():
            names.add(name)
    pools_root = SKILL_DIR / "template-library" / "reference" / "pools"
    if pools_root.is_dir():
        names.update(path.stem for path in pools_root.rglob("*.md"))
    return names


def _self_test() -> list[str]:
    failures: list[str] = []

    def expect(cond: bool, message: str) -> None:
        if not cond:
            failures.append(message)

    # Vocabulary integrity: rule effects reference declared families only;
    # every compat-table member must be a real library style (anti-blindness).
    library_names = _library_style_names()
    if library_names:
        for label, members in sorted(FAMILIES.items()):
            for missing in sorted(set(members) - library_names):
                failures.append(json.dumps(
                    {"code": "style_member_missing", "name": missing,
                     "family": label}, ensure_ascii=False, sort_keys=True))
    known = set(FAMILIES)
    ids = [r["id"] for r in RULES]
    expect(len(ids) == len(set(ids)), "rule ids not unique")
    for rule in RULES:
        for key in ("exclude", "lock", "prefer"):
            for fam in rule.get(key, []):
                expect(fam in known, f"rule {rule['id']} references unknown family {fam}")
    expect(15 <= len(RULES) <= 25, f"rule count {len(RULES)} outside 15-25 band")

    # R-66 anti-blindness: merge-cluster master styles stay visible to the
    # families that kept their variants (k12 / finance prefer pools).
    expect("互联网产品风" in FAMILIES["教学课件"],
           "k12: variant master 互联网产品风 missing from 教学课件 family")
    expect("商业计划书风" in FAMILIES["金融审计"],
           "finance: variant master 商业计划书风 missing from 金融审计 family")

    # Academic defense: retro/pop/aggressive families excluded, academic locked.
    out = evaluate({"genre": "博士论文答辩", "domain": ["高校"]})
    expect("复古潮流" in out["exclude_families"], "academic: retro not excluded")
    expect("波普孟菲斯" in out["exclude_families"], "academic: pop not excluded")
    expect("学术答辩" in out["lock_families"], "academic: family not locked")

    # Party/government context: party-red locked, playful families excluded.
    out = evaluate({"culture": "支部主题党日"})
    expect(out["lock_families"] == ["党政红"], "party-gov: party-red not locked")
    expect("波普孟菲斯" in out["exclude_families"], "party-gov: pop not excluded")

    # Kids audience: aggressive families excluded, friendly families preferred.
    out = evaluate({"audience": "小学二年级学生"})
    expect("高攻击" in out["exclude_families"], "kids: aggressive not excluded")
    expect("卡通儿童" in out["prefer_families"], "kids: friendly not preferred")

    # Investor pitch x tech: tech-dark boosted, never locked (design §3).
    out = evaluate({"genre": "融资路演", "domain": ["AI 大模型"]})
    expect(out["prefer_families"].get("科技暗色") == 1, "pitch-tech: tech-dark not boosted")
    expect(not out["lock_families"], "pitch-tech: unexpected lock")
    expect("investor-pitch-tech" in out["triggered_rules"], "pitch-tech: rule id missing")

    # Cross-domain pitch: general business families preferred.
    out = evaluate({"genre": "融资路演"})
    expect("商务专业" in out["prefer_families"], "pitch-general: business not preferred")

    # Explicit named style: bypass_all with zero rule output.
    out = evaluate({"genre": "论文答辩", "named_style": "蒸汽波风"})
    expect(out["bypassed"] is True, "named: bypass flag missing")
    expect(out["triggered_rules"] == [], "named: rules still triggered")
    expect(out["exclude_families"] == [], "named: exclusions leaked past bypass")

    # No matching signal: zero output everywhere.
    out = evaluate({"genre": "团队周会", "preferences": ["清爽一点"]})
    expect(out["triggered_rules"] == [], "neutral: rules unexpectedly triggered")
    expect(out["exclude_families"] == [] and out["lock_families"] == []
           and out["prefer_families"] == {}, "neutral: non-empty effect sets")

    # Formality thresholds honored on both sides.
    out = evaluate({"genre": "年度述职汇报", "formality": 0.9})
    expect("商务专业" in out["prefer_families"], "board: business not preferred at 0.9")
    out = evaluate({"genre": "年度述职汇报", "formality": 0.5})
    expect("board-formal-report" not in out["triggered_rules"],
           "board: triggered below 0.8 threshold")

    # Determinism: same input, same output.
    brief = {"genre": "结题验收", "culture": "国风水墨", "formality": 0.85}
    expect(evaluate(brief) == evaluate(brief), "determinism: outputs diverged")

    # Lock beats exclude on conflict.
    out = evaluate({"genre": "课题中期检查", "culture": "国潮"})
    expect(not (set(out["lock_families"]) & set(out["exclude_families"])),
           "conflict: lock family also excluded")

    return [f for f in failures if f]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="风格推荐硬规则层（R-61）")
    parser.add_argument("--check-brief", metavar="JSON",
                        help="合同信号 JSON（genre/domain/audience/formality/"
                             "culture/content_shape/named_style），输出规则层结论")
    parser.add_argument("--self-test", action="store_true",
                        help="内置正反样本自检（对抗样本/锁定/bypass/零输出）")
    args = parser.parse_args(argv)

    if args.self_test:
        failures = _self_test()
        if failures:
            for item in failures:
                print(f"  ✗ {item}", file=sys.stderr)
            print(f"self-test FAILED: {len(failures)} checks", file=sys.stderr)
            return 2
        print(f"self-test OK: {len(RULES)} rules, {len(FAMILIES)} families")
        return 0

    if args.check_brief is None:
        parser.error("需要 --check-brief JSON 或 --self-test")
        return 2
    try:
        brief = json.loads(args.check_brief)
    except json.JSONDecodeError as exc:
        print(f"brief_json_invalid: {exc}", file=sys.stderr)
        return 2
    if not isinstance(brief, dict):
        print("brief_json_not_object: --check-brief 须为 JSON 对象", file=sys.stderr)
        return 2

    print(json.dumps(evaluate(brief), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
