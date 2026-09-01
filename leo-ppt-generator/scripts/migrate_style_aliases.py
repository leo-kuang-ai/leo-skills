#!/usr/bin/env python3
"""主风格 aliases 债清偿迁移（R-63 遗留 / S1b 任务 3）。

121 个既有参考主风格中 103 个缺 ``aliases`` 字段（18 个已有：11 顶层内置
+ 7 个 R-66 家族主风格）。本脚本以确定性数据表补齐：每条 2-5 个中英别名/
俗称/易检索变体，从风格名/场景/气质推导（人工审定，非模板拼接）。

纪律：

- 只补缺：已有 ``aliases`` 的主风格不覆盖（R-63 已确认别名优先）；
- 不碰变体：带 ``variant_of`` 的 16 个条目不加（其名经主风格 aliases 检索）；
- 手术式插入：在 JSON 块 ``style_name`` 行后插入一行 ``aliases``，不重排
  原文（diff 最小，零格式漂移）；
- ``--check`` 只读校验（单测/CI 用），缺字段即非零退出。

用法::

    python3 scripts/migrate_style_aliases.py           # 注入（幂等）
    python3 scripts/migrate_style_aliases.py --check   # 只读校验
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
STYLES_ROOT = SKILL_DIR / "references" / "styles"

JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)

# Deterministic alias table: 103 master styles that lacked the field before
# this migration. Derived from style name / scenario / temperament; keep
# entries 2-5 items each, no self-name, no empty strings.
ALIASES: dict[str, list[str]] = {
    # 01_通用母版 · 几何装饰
    "扁平风": ["flat design", "扁平化", "纯扁平"],
    "半扁平风": ["semi-flat", "准扁平风", "轻度拟物风"],
    "微立体轻拟态风": ["轻拟物风", "微立体风", "semi-skeuomorphism"],
    "新拟态风": ["neumorphism", "新拟物风", "软UI风"],
    "新粗野主义风": ["neubrutalism", "新野兽派风", "粗野主义风"],
    "孟菲斯风": ["Memphis", "孟菲斯设计", "后现代拼贴风"],
    "波普艺术风": ["pop art", "波普风", "沃霍尔风"],
    "装饰艺术风": ["Art Deco", "装饰主义风", "爵士时代风"],
    "蒸汽波风": ["vaporwave", "蒸汽波美学", "赛博怀旧风"],
    "合成波风": ["synthwave", "outrun", "复古未来电子风"],
    # 01_通用母版 · 商务专业
    "麦肯锡咨询风": ["McKinsey风", "咨询报告风", "顶级咨询风"],
    "稳重商务风": ["沉稳商务风", "经典商务风", "corporate classic"],
    "简约商务风": ["简洁商务风", "极简商务风", "clean business"],
    "商务几何风": ["几何商务风", "结构商务风", "corporate geometric"],
    "CEO高级商务风": ["CEO汇报风", "高管商务风", "executive premium"],
    "金融奢华风": ["投行风", "黑金商务风", "金融高端风"],
    "静奢极简风": ["quiet luxury", "静奢风", "低调奢华风"],
    # 01_通用母版 · 极简排版
    "极简风": ["minimalism", "极简主义", "性冷淡风"],
    "瑞士网格风": ["Swiss style", "国际主义排版风", "网格主义风"],
    "暖调柔形风": ["暖色有机风", "柔和几何风", "warm organic"],
    "包豪斯风": ["Bauhaus", "包豪斯主义", "构成主义风"],
    "大字报巨型排版风": ["大字报风", "巨型排版风", "big type"],
    "黑白极简艺术展风": ["黑白艺术展风", "美术馆风", "mono gallery"],
    # 01_通用母版 · 科技数字
    "暗黑科技风": ["dark tech", "深色科技风", "黑科技发布会"],
    "科技未来感风": ["futurism", "未来科技风", "sci-fi风"],
    "全息棱镜科技风": ["全息科技风", "虹彩科技风", "holo tech"],
    "玻璃拟态风": ["glassmorphism", "毛玻璃风", "玻璃态"],
    "荧光高对比科技风": ["荧光科技风", "高对比暗色风", "neon tech"],
    "工程蓝图风": ["蓝图风", "engineering blueprint", "制图风"],
    "代码开发者风": ["developer风", "代码风", "程序员风"],
    # 01_通用母版 · 艺术表现
    "3D软体卡通风": ["3D软体风", "卡通渲染风", "soft 3D"],
    "低多边形风": ["low poly", "低面数风", "三角面风"],
    "像素复古风": ["pixel art", "8-bit风", "像素画风"],
    "水墨禅意风": ["水墨风", "国风禅意风", "shuimo"],
    "水彩晕染风": ["水彩风", "晕染插画风", "watercolor"],
    "迷幻国潮风": ["国潮风", "新中式潮流风", "guochao"],
    "黏土定格风": ["claymation", "黏土动画风", "定格动画风"],
    # 02_行业内容域 · 互联网科技
    "SaaS介绍风": ["SaaS风", "软件服务风", "SaaS pitch"],
    "人工智能大模型风": ["AI大模型风", "大模型风", "LLM风", "AIGC风"],
    "数据智能风": ["BI风", "数据风", "data intelligence"],
    "软件发布风": ["release notes风", "版本发布风", "产品更新风"],
    # 02_行业内容域 · 体育健身
    "体育赛事风": ["赛事风", "体育竞技风", "sports event"],
    "健身训练风": ["健身风", "训练计划风", "fitness"],
    "户外运动风": ["户外风", "越野风", "outdoor"],
    # 02_行业内容域 · 制造能源
    "工业产品风": ["工业风", "硬件产品风", "industrial"],
    "建筑工程风": ["建筑风", "工程建造风", "construction"],
    "新能源双碳风": ["双碳风", "新能源风", "碳中和风"],
    "智能制造风": ["工业4.0风", "数字化工厂风", "smart manufacturing"],
    "环保绿动风": ["环保风", "绿色生态风", "eco风"],
    # 02_行业内容域 · 医疗健康
    "临床试验风": ["临床风", "试验数据风", "clinical trial"],
    "健康科普插画风": ["健康科普风", "医学科普风", "health illustration"],
    "医疗学术风": ["医学学术风", "医疗风", "medical academic"],
    "医药发布会风": ["医药发布风", "药企风", "pharma launch"],
    "医院品牌风": ["医院风", "医疗机构风", "hospital brand"],
    # 02_行业内容域 · 咨询法律/政务公共
    "律所专业风": ["律所风", "法律风", "legal风"],
    "党建活动风": ["党建风", "红色党建风", "party building"],
    "政府工作报告风": ["政府报告风", "政务风", "白皮书风"],
    # 02_行业内容域 · 教育学术
    "中小学课堂风": ["K12课堂风", "小学课堂风", "少儿课件风"],
    "学术期刊风": ["期刊风", "论文排版风", "journal风"],
    "数学可视化教学风": ["数学教学风", "数学可视化风", "math teaching"],
    # 02_行业内容域 · 文旅餐饮/汽车交通
    "文旅目的地风": ["文旅风", "目的地宣传风", "tourism风"],
    "酒店民宿风": ["酒店风", "民宿风", "hospitality风"],
    "餐饮美食风": ["美食风", "餐饮风", "food风"],
    "出行服务风": ["网约车风", "出行风", "mobility风"],
    "汽车品牌风": ["汽车风", "车企风", "automotive风"],
    "物流供应链风": ["物流风", "供应链风", "logistics风"],
    # 02_行业内容域 · 消费时尚/游戏娱乐/金融审计
    "快消营销风": ["快消风", "FMCG风", "消费品牌营销风"],
    "新消费品牌风": ["新消费风", "DTC品牌风", "new consumer"],
    "时尚品牌风": ["时尚风", "fashion风", "潮流品牌风"],
    "电商大促风": ["大促风", "电商风", "双十一风"],
    "影视宣发风": ["影视风", "电影宣发风", "film promo"],
    "游戏攻略风": ["攻略风", "游戏风", "game guide"],
    "电竞数据风": ["电竞风", "赛事数据风", "esports风"],
    "保险品牌风": ["保险风", "险企风", "insurance风"],
    "四大审计风": ["四大风", "审计风", "Big Four风"],
    "投资机构风": ["投资风", "机构风", "VC风", "PE风"],
    "银行年报风": ["银行风", "年报风", "bank annual风"],
    # 03_场景用途结构
    "招商推介风": ["招商风", "推介会风", "investment promo风"],
    "直播带货风": ["带货风", "直播风", "livestream风"],
    "求职作品集风": ["作品集风", "portfolio风", "求职展示风"],
    "简历自我介绍风": ["简历风", "自我介绍风", "resume风"],
    "获奖申报风": ["申报风", "评奖风", "award风"],
    "公益科普风": ["公益风", "公益传播风", "nonprofit风"],
    "品牌宣传风": ["品牌风", "宣传风", "brand campaign风"],
    "展览导览风": ["导览风", "展陈风", "exhibition风"],
    "旅行指南风": ["旅行风", "攻略指南风", "travel guide风"],
    "短视频脚本风": ["短视频风", "脚本分镜风", "short video风"],
    "企业内训风": ["内训风", "企业培训风", "corporate training风"],
    "工作坊风": ["workshop风", "共创风", "研讨会风"],
    "技术分享风": ["技术演讲风", "tech talk风", "开发者分享风"],
    "知识卡片风": ["卡片风", "知识卡风", "knowledge card风"],
    "知识科普风": ["科普风", "知识普及风", "science风"],
    "读书笔记风": ["读书会风", "书摘风", "book notes风"],
    "团队建设风": ["团建风", "团队风", "team building风"],
    "年会庆典风": ["年会风", "庆典风", "annual gala风"],
    "摄影展作品集风": ["摄影集风", "影展风", "photo gallery风"],
    "节日节气风": ["节日风", "节气风", "festival风"],
    "创意提案风": ["创意pitch风", "概念提案风", "creative风"],
    "咨询提案风": ["提案风", "advisory风", "proposal风"],
    "投标竞标风": ["投标风", "竞标风", "bid风"],
    # 05_来源_awesome-gpt-image-2 · 借鉴新增
    "写实摄影风": ["photoreal风", "纪实摄影风", "真实照片风"],
    "历史古风题材风": ["古风题材风", "历史题材风", "朝代服饰风"],
    "场景叙事分镜风": ["分镜风", "storyboard风", "叙事分镜风"],
}


def iter_briefs(styles_root: Path):
    """Yield (path, text, match, brief) for every parseable style brief."""
    for path in sorted(styles_root.rglob("*.md")):
        if "00_索引" in str(path.relative_to(styles_root)):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        match = JSON_BLOCK_RE.search(text)
        if not match:
            continue
        try:
            brief = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(brief, dict) and "style_name" in brief:
            yield path, text, match, brief


def inject_aliases(styles_root: Path) -> dict[str, int]:
    """Insert one aliases line after style_name in each missing master brief."""
    stats = {"injected": 0, "skipped_existing": 0, "skipped_variant": 0,
             "missing_from_table": 0}
    for path, text, match, brief in iter_briefs(styles_root):
        if "variant_of" in brief:
            stats["skipped_variant"] += 1
            continue
        name = str(brief["style_name"])
        if brief.get("aliases"):
            stats["skipped_existing"] += 1
            continue
        aliases = ALIASES.get(name)
        if not aliases:
            stats["missing_from_table"] += 1
            continue
        block = match.group(0)
        line = '  "aliases": ' + json.dumps(aliases, ensure_ascii=False) + ","
        # Surgical insert right after the style_name line inside the block.
        style_line = re.search(r'(^  "style_name": .*?$)', block, re.M)
        if not style_line:
            stats["missing_from_table"] += 1
            continue
        new_block = block.replace(
            style_line.group(1), style_line.group(1) + "\n" + line, 1
        )
        new_text = text.replace(block, new_block, 1)
        # Guard: the edited file must still parse as the same brief + aliases.
        reparsed = json.loads(JSON_BLOCK_RE.search(new_text).group(1))
        assert reparsed.get("aliases") == aliases and \
            reparsed.get("style_name") == name
        path.write_text(new_text, encoding="utf-8")
        stats["injected"] += 1
    return stats


def check_aliases(styles_root: Path) -> list[str]:
    """Return master style names still lacking a non-empty aliases list."""
    gaps = []
    for _path, _text, _match, brief in iter_briefs(styles_root):
        if "variant_of" in brief:
            continue
        if not brief.get("aliases"):
            gaps.append(str(brief["style_name"]))
    return gaps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="主风格 aliases 债清偿迁移")
    parser.add_argument("--check", action="store_true",
                        help="只读校验：存在缺 aliases 的主风格则退出 2")
    parser.add_argument("--root", help="技能根目录覆盖（默认脚本所在仓库）")
    args = parser.parse_args(argv)

    styles_root = Path(args.root).resolve() / "references" / "styles" \
        if args.root else STYLES_ROOT

    if args.check:
        gaps = check_aliases(styles_root)
        if gaps:
            print(f"aliases_missing: {len(gaps)} 个主风格缺 aliases:")
            for name in gaps:
                print(f"  - {name}")
            return 2
        print("aliases_check OK: 主风格全覆盖（变体经主风格 aliases 检索）")
        return 0

    stats = inject_aliases(styles_root)
    print(
        f"aliases injected={stats['injected']} "
        f"skipped(existing)={stats['skipped_existing']} "
        f"skipped(variant)={stats['skipped_variant']} "
        f"missing_from_table={stats['missing_from_table']}"
    )
    if stats["missing_from_table"]:
        print("存在数据表未覆盖的主风格（须补表再跑）", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
