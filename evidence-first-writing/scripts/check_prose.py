#!/usr/bin/env python3
# 来源: https://github.com/KKKKhazix/human-writing (MIT, vendored 2026-08-30, 授权已确认)
"""中文文风确定性检查器：定位中文成稿里的模板味形状，只报线索，不自动改文。

定位（evidence-first-writing 技能）：
- 供 audit/humanize 在中文文体诊断时优先运行，与 ``check_factual_invariants.py``
  （改写后事实回归）互补：本脚本只管"像不像模板"，不管"事实对不对"。
- 检测分两级：失败级 FAIL（硬停词、绝对黑话、模型路标、字面翻案腔、提示性
  冒号与破折号）与警告级 WARN（需结合语境判断的形状与统计信号）。
- 每条线索一行，格式：``级别 | 类别 | 位置 | 命中片段 | 建议动作``；级别为
  FAIL/WARN，位置为 ``L<行号>`` 或 ``全文``。输出是诊断线索，非交付门禁；
  作者样本与渠道优先原则可覆盖破折号、冒号等风格类建议。
- 退出码：0 干净；1 存在失败级；2 仅警告级；3 输入或参数错误。上游原版以
  2 表示读取失败，本版按技能 CLI 契约调整：读取/参数错误移到 3，2 专用于
  "仅警告级"。
- 跨宿主调用：先将 ``EVIDENCE_FIRST_WRITING_SKILL_DIR`` 指向已加载
  ``SKILL.md`` 所在目录，再运行
  ``python3 "$EVIDENCE_FIRST_WRITING_SKILL_DIR/scripts/check_prose.py" <file.md>``；
  也支持 ``-`` 从标准输入读取。脚本自身不依赖机器特定绝对路径。

词表、正则、阈值与全部豁免规则自上游原样保留（冒号后接直接引语降级为警告、
语境词与硬黑话重叠不重复计、语义翻案与字面翻案重叠去重等），未做增删。
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from dataclasses import dataclass
from pathlib import Path


HARD_STOPS = (
    "说白了",
    "说穿了",
    "先说结论",
)

HARD_JARGON = (
    "赋能",
    "抓手",
    "商业闭环",
    "价值闭环",
    "能力沉淀",
    "拉通",
    "底层逻辑",
    "顶层设计",
    "认知跃迁",
    "价值释放",
    "能力建设",
    "降本增效",
    "内容矩阵",
    "全链路",
    "组合拳",
    "打开想象空间",
    "结构性机会",
    "关键命题",
    "深层逻辑",
    "技术底座",
    "公共底座",
    "技术主权",
    "单点风险",
    "主脊柱",
    "材料锚点",
    "认知增量",
    "迭代闭环",
)

CONTEXT_JARGON = (
    "沉淀",
    "颗粒度",
    "对齐",
    "协同",
    "链路",
    "生态位",
    "心智",
    "范式",
    "方法论",
    "核心变量",
    "打法",
    "想象空间",
    "闭环",
    "不丢",
)

LYRIC_WORDS = (
    "安放",
    "抵达",
    "微光",
    "褶皱",
    "丰盈",
    "滚烫",
    "轻盈",
    "赤裸",
    "剥开",
)

ROAD_SIGNS = (
    "更微妙的是",
    "还有一层",
    "只说对了一半",
    "值得注意的是",
    "需要指出的是",
    "从某种意义上说",
)

ROAD_STRIP_CHARS = "。！？!? \n"

FORBIDDEN_PUNCTUATION = {
    "：": "中文冒号",
    ":": "英文冒号",
    "—": "破折号",
    "–": "连接号式破折号",
}

PIVOT_PATTERNS = (
    re.compile(r"(?:并)?不是[^。！？\n]{0,90}而是"),
    re.compile(r"并非[^。！？\n]{0,90}而是"),
    re.compile(r"不在于[^。！？\n]{0,90}而在于"),
    re.compile(r"与其说[^。！？\n]{0,90}(?:不如|毋宁|倒不如)"),
    re.compile(r"[。！？!?]\s*而是"),
    re.compile(r"表面(?:上)?[^。！？\n]{0,90}(?:其实|实际|实则)"),
    re.compile(r"看似[^。！？\n]{0,90}(?:其实|实际|实则)"),
)

SEMANTIC_PIVOT_PATTERNS = (
    re.compile(r"(?:总|一直|曾|都)?以为[^！？\n]{2,60}?(?:其实|才发现|才明白|才知道|后来才)"),
    re.compile(r"(?:总|都|一直)以为[^！？\n]{2,60}?[。，](?:可|但|其实)"),
    re.compile(r"回头(?:看|一看)?才(?:发现|明白|知道)"),
    re.compile(r"(?:并)?不是[^。！？\n]{1,40}，(?:更|才)?是[^，。！？\n]"),
    re.compile(r"从来(?:都)?(?:不是|与[^。！？，\n]{1,12}无关)"),
    re.compile(r"答案(?:是否定的|恰恰相反)|恰恰相反"),
    re.compile(r"表面(?:上)?[^！？\n]{0,60}。[^！？\n]{0,12}(?:其实|实际|实则)"),
    re.compile(r"看似[^！？\n]{0,60}。[^！？\n]{0,12}(?:其实|实际|实则)"),
    re.compile(r"[^，。！？\n]{1,12}不重要，(?:重要|要紧)的是"),
    re.compile(r"真正[^，。！？\n]{0,16}的(?:，)?是"),
    re.compile(r"不只(?:是)?[^。！？\n]{0,90}(?:还|也)"),
)

NOMINALIZATION_PATTERNS = (
    re.compile(r"进行(?:了|一次|一场|着)?[^。，！？\n]{0,10}(?:调整|优化|升级|分析|讨论|沟通|梳理|复盘|迭代|探索|尝试|思考|规划|布局)"),
    re.compile(r"实现了?[^。，！？\n]{0,14}的?[^。，！？\n]{0,6}(?:提升|增长|突破|转变|跃升|落地)"),
    re.compile(r"完成了?对[^。，！？\n]{0,16}的"),
    re.compile(r"起到了?[^。，！？\n]{0,12}的?作用"),
    re.compile(r"具有[^。，！？\n]{0,10}(?:意义|价值)"),
)

CONJUNCTIONS = (
    "因为",
    "所以",
    "但是",
    "然而",
    "同时",
    "此外",
    "而且",
    "并且",
    "因此",
    "不仅",
)

ROAD_SIGN_PATTERNS = (
    re.compile(
        rf"(?:^|[。！？!?]\s*){re.escape(ROAD_SIGNS[0])}[^。！？!?\n]{{0,24}}",
        re.MULTILINE,
    ),
    re.compile(
        rf"(?:^|[。！？!?]\s*){re.escape(ROAD_SIGNS[1])}(?=(?:更|原因|问题|意思|考虑|变化|逻辑|价值|作用|风险|影响|值得|很少|不容易|常被|往往))[^。！？!?\n]{{0,24}}",
        re.MULTILINE,
    ),
    *(
        re.compile(
            rf"(?:^|[。！？!?]\s*){re.escape(phrase)}[^。！？!?\n]{{0,24}}",
            re.MULTILINE,
        )
        for phrase in ROAD_SIGNS[2:]
    ),
)

SOFT_MARKERS = (
    "真正",
    "本质上",
    "更深层次",
    "归根结底",
    "换句话说",
    "不可否认",
    "核心是",
    "关键在于",
    "这意味着",
)

REPEATED_OPENERS = (
    "其实",
    "不过",
    "当然",
    "所以",
    "但是",
    "后来",
    "当时",
    "很多人",
    "问题是",
    "更重要的是",
    "说到这里",
)

LEFT_BRANCH_PATTERNS = (
    re.compile(r"(?:^|[。！？]\s*)在[^，。！？\n]{12,70}(?:以后|之后|之前|以前|过程中|情况下|背景下)，"),
    re.compile(r"(?:^|[。！？]\s*)那些[^，。！？\n]{10,60}的[^，。！？\n]{2,30}[，。]"),
    re.compile(r"(?:^|[。！？]\s*)(?:真正|最终|最后)让[^，。！？\n]{8,70}的，是"),
)

METAPHOR_FIELDS = {
    "温度": ("降温", "升温", "冷却", "余温", "温度最高"),
    "生死战争": ("杀死", "死因", "枪响", "开火", "战场", "引爆", "弹药"),
    "建筑灾害": ("坍塌", "崩塌", "地基", "砖头", "支柱", "废墟"),
    "仓储租赁": ("仓库", "库房", "租金", "取货", "入库", "库存"),
    "道路竞赛": ("赛道", "跑道", "岔路", "十字路口", "终点线", "门票"),
    "机器器官": ("齿轮", "引擎", "发动机", "血管", "骨架", "肌肉"),
    "海洋航行": ("蓝海", "浪潮", "潮水", "航船", "灯塔", "彼岸"),
}


@dataclass
class Paragraph:
    position: int
    text: str
    han: int
    sentences: int


@dataclass
class Finding:
    """一条诊断线索：级别、类别、原文位置、命中片段与建议动作。"""

    level: str  # "FAIL" | "WARN"
    category: str
    position: int | None  # 原文偏移；None 表示全文级统计
    excerpt: str
    action: str


def han_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def excerpt(value: str, width: int = 72) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= width else value[: width - 1] + "…"


def mask_non_prose(text: str) -> str:
    """屏蔽代码、网址和机器元数据，同时保留字符位置与换行。"""

    def mask(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group())

    patterns = (
        re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", re.DOTALL),
        re.compile(r"```.*?```", re.DOTALL),
        re.compile(r"`[^`\n]*`"),
        re.compile(r"\]\([^\n)]*\)"),
        re.compile(r"https?://[^\s)>]+"),
        re.compile(r"<[^>\n]+>"),
    )
    masked = text
    for pattern in patterns:
        masked = pattern.sub(mask, masked)
    return masked


def non_overlapping_terms(text: str, terms: tuple[str, ...]):
    matches = []
    occupied = []
    for term in sorted(terms, key=len, reverse=True):
        for match in re.finditer(re.escape(term), text):
            start, end = match.span()
            if any(start < old_end and end > old_start for old_start, old_end in occupied):
                continue
            matches.append((start, term))
            occupied.append((start, end))
    return sorted(matches)


def all_matches(text: str, patterns: tuple[re.Pattern[str], ...]):
    matches = []
    for pattern in patterns:
        matches.extend(pattern.finditer(text))
    return sorted(matches, key=lambda match: match.start())


def heavy_de_sentences(text: str):
    """找出主干可能被多个“的”压到后面的长句。"""

    matches = []
    pattern = re.compile(r"[^。！？!?\n]+(?:[。！？!?]|$)")
    for match in pattern.finditer(text):
        value = match.group()
        if han_count(value) >= 38 and value.count("的") >= 4:
            matches.append(match)
    return matches


def anaphora_runs(text: str, minimum: int = 3):
    """找出同一句里三个以上小句用同一个开头的排比。"""

    matches = []
    for sentence in re.finditer(r"[^。！？!?\n]+(?:[。！？!?]|$)", text):
        clauses = [
            clause.strip()
            for clause in re.split(r"[，、；,;]", sentence.group())
            if han_count(clause) >= 3
        ]
        if len(clauses) < minimum:
            continue
        run = 1
        for previous, current in zip(clauses, clauses[1:]):
            if previous[:2] == current[:2] and re.match(r"[一-鿿]{2}", current):
                run += 1
                if run >= minimum:
                    matches.append(sentence)
                    break
            else:
                run = 1
    return matches


def sentence_length_cv(text: str):
    """句长变异系数。人写的长短句差距大，模型的句长彼此接近。"""

    lengths = [
        han_count(match.group())
        for match in re.finditer(r"[^。！？!?\n]+[。！？!?]", text)
        if han_count(match.group()) >= 4
    ]
    if len(lengths) < 12:
        return None
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return None
    variance = sum((value - mean) ** 2 for value in lengths) / len(lengths)
    return (variance ** 0.5) / mean, len(lengths)


def bracket_highlights(text: str):
    """「」括起来的短语。太密说明在批量造金句。"""

    return list(re.finditer(r"[「『][^」』\n]{1,6}[」』]", text))


def prose_paragraphs(text: str) -> list[Paragraph]:
    paragraphs = []
    cursor = 0
    for block in re.split(r"\n\s*\n", text):
        position = text.find(block, cursor)
        cursor = max(position + len(block), cursor)
        clean = re.sub(r"[>*_`]", "", block).strip()
        if not clean or clean.startswith(("#", "http", "![", "```")):
            continue
        if re.match(r"^(?:[-+*]|\d+[.、])\s", clean):
            continue
        count = han_count(clean)
        if count < 4:
            continue
        sentences = max(1, len(re.findall(r"[。！？!?]", clean)))
        paragraphs.append(Paragraph(position, clean, count, sentences))
    return paragraphs


def metaphor_cluster(text: str, distance: int = 800):
    hits = []
    for field, words in METAPHOR_FIELDS.items():
        for word in words:
            for match in re.finditer(re.escape(word), text):
                hits.append((match.start(), field, word))
    hits.sort()
    for index, (start, _, _) in enumerate(hits):
        window = [hit for hit in hits[index:] if hit[0] - start <= distance]
        fields = {hit[1] for hit in window}
        if len(fields) >= 3:
            return window, fields
    return None


def short_streak(paragraphs: list[Paragraph], limit: int = 4):
    streak = []
    for paragraph in paragraphs:
        if paragraph.han <= 24 and paragraph.sentences <= 1:
            streak.append(paragraph)
            if len(streak) >= limit:
                return streak
        else:
            streak = []
    return None


def opener_counts(paragraphs: list[Paragraph]):
    counts = collections.Counter()
    examples = {}
    for paragraph in paragraphs:
        value = paragraph.text.lstrip("“‘\"（(")
        for opener in REPEATED_OPENERS:
            if value.startswith(opener):
                counts[opener] += 1
                examples.setdefault(opener, paragraph.position)
                break
    return counts, examples


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def format_finding(text: str, finding: Finding) -> str:
    if finding.position is None:
        location = "全文"
    else:
        location = f"L{line_number(text, finding.position)}"
    snippet = excerpt(finding.excerpt, 56) or "-"
    return f"{finding.level} | {finding.category} | {location} | {snippet} | {finding.action}"


class ProseArgumentParser(argparse.ArgumentParser):
    # 保留退出码 2 给"仅警告级"，参数错误改用 3，与 docstring 契约一致。
    def error(self, message: str):
        self.print_usage(sys.stderr)
        print(f"参数错误：{message}", file=sys.stderr)
        raise SystemExit(3)


def main() -> int:
    parser = ProseArgumentParser(
        description="检查中文成稿的模板味形状，输出诊断线索（非交付门禁）"
    )
    parser.add_argument("path", help="Markdown 或文本文件路径。使用 - 从标准输入读取")
    args = parser.parse_args()

    try:
        text = read_text(args.path)
    except (OSError, UnicodeError) as error:
        print(f"无法读取稿件。{error}", file=sys.stderr)
        return 3

    prose = mask_non_prose(text)
    total_han = han_count(prose)
    if total_han == 0:
        print("没有检测到汉字。", file=sys.stderr)
        return 3

    findings: list[Finding] = []

    quote_colons = []
    for symbol, label in FORBIDDEN_PUNCTUATION.items():
        matches = list(re.finditer(re.escape(symbol), prose))
        if symbol in ("：", ":"):
            # 豁免：冒号后紧跟引号，视为引出直接引语，降级为警告。
            hard = []
            for match in matches:
                tail = prose[match.end() : match.end() + 2].lstrip()
                if tail[:1] in ("「", "『", "“", "‘", '"'):
                    quote_colons.append(match)
                else:
                    hard.append(match)
            matches = hard
        for match in matches[:8]:
            findings.append(
                Finding(
                    "FAIL",
                    "punctuation 提示性标点",
                    match.start(),
                    prose[max(0, match.start() - 8) : match.start() + 10],
                    f"{label}属提示性结构，改用句号或逗号相接；作者样本确有此风格时可保留",
                )
            )
    for match in quote_colons[:8]:
        findings.append(
            Finding(
                "WARN",
                "quote-colon 引出原话的冒号",
                match.start(),
                prose[max(0, match.start() - 8) : match.start() + 10],
                "确认引号里确实是原话，且不是提示性用法",
            )
        )

    stop_matches = non_overlapping_terms(prose, HARD_STOPS)
    for position, phrase in stop_matches:
        findings.append(
            Finding("FAIL", "hard-stop 硬停词", position, phrase, "删除硬停词，用事实或例子直接推进")
        )

    jargon_matches = non_overlapping_terms(prose, HARD_JARGON)
    for position, phrase in jargon_matches:
        findings.append(
            Finding("FAIL", "jargon 黑话", position, phrase, "换成具体动作或可核对的事实")
        )

    context_jargon_matches = non_overlapping_terms(prose, CONTEXT_JARGON)
    hard_spans = [
        (position, position + len(phrase)) for position, phrase in jargon_matches
    ]
    context_jargon_matches = [
        (position, phrase)
        for position, phrase in context_jargon_matches
        if not any(
            position < end and position + len(phrase) > start
            for start, end in hard_spans
        )
    ]
    for position, phrase in context_jargon_matches[:8]:
        findings.append(
            Finding("WARN", "context-jargon 语境词", position, phrase, "本义准确时保留，用来抬价时改写")
        )

    road_signs = all_matches(prose, ROAD_SIGN_PATTERNS)
    for match in road_signs:
        findings.append(
            Finding(
                "FAIL",
                "model-road-sign 模型路标",
                match.start(),
                match.group().lstrip(ROAD_STRIP_CHARS),
                "删掉路标，让内容自己承担转折",
            )
        )

    pivots = all_matches(prose, PIVOT_PATTERNS)
    for match in pivots:
        findings.append(
            Finding("FAIL", "pivot 翻案句", match.start(), match.group(), "改成正面陈述，直接说出真正主张")
        )

    occupied_spans = [match.span() for match in pivots]
    semantic_pivots = []
    for match in all_matches(prose, SEMANTIC_PIVOT_PATTERNS):
        if any(
            match.start() < end and match.end() > start
            for start, end in occupied_spans
        ):
            continue
        semantic_pivots.append(match)
        occupied_spans.append(match.span())
    for match in semantic_pivots:
        findings.append(
            Finding(
                "WARN",
                "semantic-pivot 翻案腔变形",
                match.start(),
                match.group(),
                "先立误解再推翻就改成正面陈述，正常用法保留",
            )
        )

    anaphoras = anaphora_runs(prose)
    for match in anaphoras[:4]:
        findings.append(
            Finding("WARN", "anaphora 同构排比", match.start(), match.group(), "留两项，第三项换说法或删掉")
        )

    lyric_matches = non_overlapping_terms(prose, LYRIC_WORDS)
    if len(lyric_matches) >= 2:
        samples = "、".join(dict.fromkeys(term for _, term in lyric_matches))
        findings.append(
            Finding(
                "WARN",
                "lyric-word 抒情词",
                lyric_matches[0][0],
                samples,
                "写具体事物时保留，给抽象概念穿衣服时删掉",
            )
        )

    nominalizations = all_matches(prose, NOMINALIZATION_PATTERNS)
    for match in nominalizations[:4]:
        findings.append(
            Finding("WARN", "nominalization 名词化", match.start(), match.group(), "还原成直接的动词")
        )

    conjunction_hits = non_overlapping_terms(prose, CONJUNCTIONS)
    if total_han >= 600 and len(conjunction_hits) * 1000 / total_han > 7:
        samples = "、".join(
            f"{term} {count} 次"
            for term, count in collections.Counter(
                term for _, term in conjunction_hits
            ).most_common(4)
        )
        findings.append(
            Finding(
                "WARN",
                "conjunction-density 连词密度",
                conjunction_hits[0][0] if conjunction_hits else None,
                samples,
                f"每千字 {len(conjunction_hits) * 1000 // total_han} 个，"
                "中文小句靠语序和事理相接，删掉一半试试",
            )
        )

    highlights = bracket_highlights(prose)
    highlight_limit = max(3, total_han // 700)
    if len(highlights) > highlight_limit:
        samples = "、".join(dict.fromkeys(match.group() for match in highlights[:6]))
        findings.append(
            Finding(
                "WARN",
                "quote-highlight 金句密度",
                highlights[0].start(),
                samples,
                "「」短语太密说明在批量造金句，拆散或删掉",
            )
        )

    cv_result = sentence_length_cv(prose)
    if cv_result and cv_result[0] < 0.42:
        findings.append(
            Finding(
                "WARN",
                "sentence-cv 句长节奏",
                None,
                f"{cv_result[1]} 句，变异系数 {cv_result[0]:.2f}",
                "句长过于接近，放开几句，压短几句",
            )
        )

    marker_matches = non_overlapping_terms(prose, SOFT_MARKERS)
    marker_limit = max(2, total_han // 900)
    if len(marker_matches) > marker_limit:
        samples = "、".join(dict.fromkeys(term for _, term in marker_matches))
        findings.append(
            Finding(
                "WARN",
                "soft-marker 洞察路标",
                marker_matches[0][0],
                samples,
                f"共 {len(marker_matches)} 处，提醒线 {marker_limit} 处，重点检查",
            )
        )

    left_branches = all_matches(prose, LEFT_BRANCH_PATTERNS)
    left_limit = max(2, total_han // 1200)
    if len(left_branches) > left_limit:
        for match in left_branches[:4]:
            findings.append(
                Finding(
                    "WARN",
                    "left-branch 左分支长句",
                    match.start(),
                    match.group(),
                    "把前置成分拆成独立短句，让主干早出现",
                )
            )

    dense_de = heavy_de_sentences(prose)
    dense_de_limit = max(1, total_han // 1500)
    if len(dense_de) > dense_de_limit:
        for match in dense_de[:4]:
            findings.append(
                Finding(
                    "WARN",
                    "dense-de 重定语长句",
                    match.start(),
                    match.group(),
                    "先交代人和动作，再补细节",
                )
            )

    paragraphs = prose_paragraphs(prose)
    if len(paragraphs) >= 10:
        one_sentence = sum(paragraph.sentences <= 1 for paragraph in paragraphs)
        ratio = one_sentence / len(paragraphs)
        if ratio >= 0.75:
            findings.append(
                Finding(
                    "WARN",
                    "one-line-paragraph 单句段比例",
                    None,
                    f"{ratio:.0%} 的可识别段落只有一句话",
                    "可能形成统一的短段鼓点，合并或变化节奏",
                )
            )

    streak = short_streak(paragraphs)
    if streak:
        first = streak[0]
        findings.append(
            Finding(
                "WARN",
                "short-paragraph-streak 短句连排",
                first.position,
                f"连续 {len(streak)} 个短促单句段",
                "检查是否在排队喊结论",
            )
        )

    counts, opener_examples = opener_counts(paragraphs)
    repeated = [(opener, count) for opener, count in counts.items() if count >= 4]
    if repeated:
        details = "、".join(f"{opener} {count} 次" for opener, count in repeated)
        first_position = min(opener_examples[opener] for opener, _ in repeated)
        findings.append(
            Finding(
                "WARN",
                "opener-repeat 段落开场重复",
                first_position,
                details,
                "换开场或直接进入内容",
            )
        )

    metaphors = metaphor_cluster(prose)
    if metaphors:
        window, fields = metaphors
        samples = "、".join(dict.fromkeys(hit[2] for hit in window))
        findings.append(
            Finding(
                "WARN",
                "metaphor-cluster 比喻场聚集",
                window[0][0],
                f"{'、'.join(sorted(fields))}：{samples}",
                "八百字内多套借喻并存，削减到一套或换成具体事实",
            )
        )

    findings.sort(
        key=lambda finding: (
            finding.level != "FAIL",
            finding.position is None,
            finding.position or 0,
        )
    )
    fail_count = sum(1 for finding in findings if finding.level == "FAIL")
    warn_count = len(findings) - fail_count

    print(f"# 汉字数 {total_han}")
    for finding in findings:
        print(format_finding(text, finding))
    if not findings:
        print("# 未发现这份检查器覆盖的问题。")
    print(
        f"# 统计：失败级 {fail_count} 条，警告级 {warn_count} 条；"
        f"翻案句 {len(pivots)}，翻案腔变形 {len(semantic_pivots)}，"
        f"同构排比 {len(anaphoras)}，名词化 {len(nominalizations)}，"
        f"黑话 {len(jargon_matches)}，硬停词 {len(stop_matches)}，"
        f"模型路标 {len(road_signs)}，需辨语境词 {len(context_jargon_matches)}，"
        f"抒情词 {len(lyric_matches)}，洞察路标 {len(marker_matches)}，"
        f"长前置成分 {len(left_branches)}，重定语句 {len(dense_de)}"
    )
    print("# 退出码：0=干净，1=存在失败级，2=仅警告级，3=输入或参数错误。")
    print("# 以上为诊断线索，非交付门禁；警告级线索需结合语境判断，作者样本与渠道惯例可覆盖风格类建议。")

    if fail_count:
        return 1
    if warn_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
