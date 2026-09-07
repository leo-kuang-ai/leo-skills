#!/usr/bin/env python3
"""check_deck_prose.py — deck 文案确定性检测（R-15）与讲稿口语化纪律（R-16）。

对母版 markdown（deck-master-v<N>.md）的标题、各页要点与 speaker_script 段做
正则级检测：同输入同 stdout，不依赖模型。定位为「线索而非门禁」，与
check_master_contract.py 的 FAIL/WARN 分层同构，但唯一硬项（exit 1）是翻案腔
deck 级超限；其余各族均 WARN。

检测族（密度/豁免框架。机制来源：humanizer "What not to flag"（多模式聚集才
定罪、孤立过渡词不算）、shuorenhua severity.md（Tier1/2/3 分级）与
structures.md §1（二元对比骨架按长度归一设阈值 + 豁免上限、豁免项不计密度）、
xiaoma-durex-copywriter diction.md（人称纪律/数字裸用/禁解释自己）；
上游快照 2026-08-31）：

  a. 翻案腔及变体（reversal，唯一 FAIL 族）：「不是X，而是Y / 不在于X而在于Y /
     与其说X不如说Y / X未必…但Y / 看似X其实Y / X不重要，重要的是Y / 真正的X是Y」；
     deck 级计 ≤1 处，且唯一命中须为真实论证骨架并在该行尾注明
     「（豁免：论证骨架）」；单处孤立命中在要点数 ≤3 的页不计。计 ≥2 处 exit 1。
  b. 黑话词表（jargon，WARN）：词表常量 JARGON_WORDS（脚本头部可维护）；
     行业既定词豁免——同页 ≥3 次或 --allow 词表命中则不计。
  c. 名词化信号（nominalization，WARN 仅计数）：进行/实现/完成/开展/起到/具有
     带动名词（「进行了优化」「实现了效率的提升」）。
  d. 三连同构开头（isomorphic，WARN）：连续 3 个内容页第一条要点同构开头
     （前两字相同）。
  e. 连词密度（connective，WARN）：每页连词 >7 处/千字且 ≥2 处聚集才报；
     孤立单处不计。
  f. 格式子集（format，WARN）：中英之间空格、全角标点、数字单位写法
     （「多达/高达/整整+数字」数字裸用、数字与单位间加空格）。
  g. 讲稿纪律（R-16，WARN）：speaker_script 段的开场收尾套话、>40 字长句、
     「大家」通知腔（「大家好」不计）；export_speaker_notes.py --prose-check
     复用本模块的 scan_speaker_scripts。
  h. 措辞纪律（R-17，WARN，词表常量同既有各族模式）：① 自我解释连接词作
     要点开头（这说明/这意味着/由此可见/不难看出——要点是断言不是讲解）；
     ② 「大家」通知腔入要点（金句/氛围页加重提示）；③ 非常/十分/极其+
     形容词 同页 ≥2 处（形容词堆砌）。
  i. 标题兑现对账（R-18，WARN）：解析每页标题数字（含百分数；紧跟字母的
     标识符片段与四位年份豁免），对照数字登记表该页行的数值集合——标题数字
     不在本页登记表数值中即提示回母版对账或补登记行；无登记表的母版该族
     跳过（INFO 一条）。
  j. 论证媒介多样性（R-21，WARN）：连续 3 个内容页同为纯数据论证
     （argument_role 声明数据/证据，或数字要点占比 ≥60%）或纯定性论证
     （零数字要点）→ 提示换媒介（类比/案例/反例）；混合型不触发。
  k. 金句判据（R-22，WARN）：金句/氛围页要点为口号模式（无数字、无证据
     短标的抽象短语，词表判定）→ 提示重写为具体洞见；「A 即是 B」式反向
     克制型金句 deck 级 >1 → 提示。「脱离上下文独立成立」的语义判断归
     评测 judge，本族只做确定性子集。
  l. 要点模糊词（R-23，WARN，学术场景）：要点含 显著/先进/有效/鲁棒 且
     同行无量化条件（数字/百分比/对照词）→ 提示替换为测量条件；引号内、
     示意级标注、文风样本高频词（--style-sample）豁免；非学术母版（无
     deck-contract 块）该族跳过（INFO 一条）。
  m. AI 腔英文套话（R-27，WARN）：标题/要点整短语命中 dive into / explore /
     let's / journey 词边界 → 提示换回具体动作或直陈句；引号内专名（如
     「Customer Journey Map」）、--allow、文风样本高频词豁免。
  n. 推断句式纪律（R2 测评迭代，WARN）：要点含 根因/症结在/根源在/本质上是/
     最可能是/归因于 且同行既无证据标签跨度（【引用|src:…】等）亦无线索/
     待验证/unknown/假设/或含 缓冲 → 提示降级为线索句式或补证据锚点；
     有据或有缓冲的归因不报；标题是论断句不在本族范围。

用法：python3 scripts/check_deck_prose.py <deck-master.md> [--json]
    [--allow 词1,词2] [--style-sample 样本文件]
输出：stdout 人类可读报告（或 --json 全量 JSON）；退出码
  0 干净（WARN/INFO 不改退出码）/ 1 翻案腔 deck 级超限 / 2 用法或解析错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Maintainable vocabularies and thresholds (edit here, not in detectors).
# ---------------------------------------------------------------------------

# Family a: anti-reversal patterns ("先立误解再推翻抬价" skeleton, wording-agnostic
# per shuorenhua structures.md §1 — the action matters, not the literal words).
REVERSAL_PATTERNS = (
    ("不是X而是Y", re.compile(
        r"(?:不是|并非|不只是|不仅仅是)[^。；\n]{0,40}?(?:而是|确是|实则是|实际上是)")),
    ("不在于X而在于Y", re.compile(r"不在于[^。；\n]{0,40}?而在于")),
    ("与其说X不如说Y", re.compile(r"与其说?[^。；\n]{0,40}?(?:不如说?|毋宁)")),
    ("X未必但Y", re.compile(r"未必[^。；\n]{0,30}?但")),
    ("看似X其实Y", re.compile(
        r"(?:看似|表面上|乍看)[^。；\n]{0,30}?(?:其实|实际上|实则是)")),
    ("X不重要重要的是Y", re.compile(r"[^，。\n]{1,20}?不重要[，,][^，。\n]{0,10}?重要的是")),
    ("真正的X是Y", re.compile(r"真正的[^。；，\n]{1,20}?(?:从来不是|不是|关键是|是)")),
)
# Inline exemption marker honored on the same line as a reversal hit.
REVERSAL_EXEMPT_RE = re.compile(r"豁免[：:]?\s*(?:论证骨架|翻案腔)")
REVERSAL_DECK_LIMIT = 1          # deck-level cap on counted hits
REVERSAL_SHORT_PAGE_POINTS = 3   # isolated single hits on pages with <= N points don't count

# Family b: business/Internet jargon (deck-master checklist item 5 subset +
# shuorenhua phrases-zh.md Tier1 representatives).
JARGON_WORDS = (
    "闭环", "抓手", "赋能", "组合拳", "底层逻辑", "降本增效", "全链路", "顶层设计",
    "颗粒度", "沉淀", "痛点", "打造", "助力", "拉通", "心智",
)
JARGON_INDUSTRIAL_MIN = 3        # >= N same-page occurrences count as established term

# Family c: light-verb + deverbal noun signals (shuorenhua SKILL.md §2).
NOMINALIZATION_RE = re.compile(
    r"(?:进行|实现|完成|开展|起到|具有)(?:了|过)?[一-龥]{0,4}"
    r"(?:优化|提升|建设|整合|实施|部署|管理|分析|落实|推进|加强|完善|治理|升级|迭代|重构|转变|覆盖|核实|评估|排查)")

# Family d: three consecutive isomorphic point openings.
ISOMORPHIC_PREFIX_LEN = 2

# Family e: connective density per page (deck-master checklist item 9).
CONNECTIVE_WORDS = (
    "然而", "因此", "同时", "但是", "所以", "因为", "此外", "与此同时", "尽管如此",
    "进一步地",
)
# Longest-first alternation: re picks the first alternative that matches at
# each position, so 「与此同时」 counts once and never feeds the shorter
# 「同时」 a second hit (isolated single connectives must stay unflagged).
CONNECTIVE_ANY_RE = re.compile(
    "|".join(sorted((re.escape(w) for w in CONNECTIVE_WORDS),
                    key=len, reverse=True)))
CONNECTIVE_DENSITY_LIMIT = 7.0   # per 1000 chars
CONNECTIVE_MIN_HITS = 2          # isolated single connective is not a tell

# Family f: formatting subset (chinese-copywriting-guidelines + autocorrect rule
# ideas, regex subset; xiaoma diction.md §8 for bare numbers).
FORMAT_CHECKS = (
    ("中英空格", re.compile(r"[A-Za-z]{2,}[\u4e00-\u9fff]|[\u4e00-\u9fff][A-Za-z]{2,}"),
     "中英之间加空格（单字母组合如 B站/A轮 不计）"),
    ("全角标点", re.compile(r"[\u4e00-\u9fff]\s*[,;:?!()]|[,;:?!()]\s*[\u4e00-\u9fff]"),
     "中文语境用全角标点"),
    ("数字裸用", re.compile(r"(?:多达|高达|整整)(?=\d)"),
     "删「多达/高达/整整」，数字裸用不加量词修饰"),
    ("数字单位", re.compile(r"\d(?:km|mb|gb|tb|kb|ms|ghz|mhz|kg|cm|mm|kw)(?![a-zA-Z0-9])",
                            re.I),
     "数字与单位之间加空格"),
)
# 合同规定的证据标签跨度（【引用|src:锚点】/【用户确认|round:N】/[src:锚点]，
# 语法见 deck-master.md「数字登记表」节）是行内元数据不是文案——格式族扫描前
# 先掩蔽，其半角分隔符不得读成中文语境的全角标点命中。
EVIDENCE_SPAN_RE = re.compile(
    r"【(?:引用|估算|示意|用户确认|unknown)[^】]*】|\[src:[^\]]*\]")

# Family m (R-27): AI-flavored English filler phrases in titles/points. Source:
# baoyu-slide-deck base-prompt.md banned-phrase list ("dive into" / "explore" /
# "let's" / "journey" — JimLiu original, MIT snapshot 6b7a2e4 2026-07-03).
# Deterministic subset = whole-phrase word-boundary matches on title/point
# text, WARN level (never blocks; quoted product/brand names are exempt via
# the same --allow / style-sample channels as jargon).
AI_FLAVOR_PATTERNS = (
    ("dive into", re.compile(r"\bdive\s+(?:deep\s+)?into\b|\bdeep\s+dive\b", re.I)),
    ("explore", re.compile(r"\bexplo(?:re|ring)\b", re.I)),
    ("let's", re.compile(r"\blet's\b|\blet\s+us\b", re.I)),
    ("journey", re.compile(r"\bjourney(?:s|ed|ing)?\b", re.I)),
)

# Family g (R-16): speaker-script discipline. Clichés from shuorenhua
# phrases-zh.md Tier1 (开场套话/过渡废话/正能量收尾) + diction.md.
SCRIPT_CLICHES = (
    "接下来我将", "接下来我们会", "下面我为大家", "值得注意的是", "值得一提的是",
    "需要指出的是", "不难发现", "综上所述", "总而言之", "总的说来", "归根结底",
    "最后我想说的是", "让我们拭目以待", "未来可期", "希望对大家有所帮助",
)
SCRIPT_MAX_SENTENCE_LEN = 40
SCRIPT_NOTICE_PERSONA = "大家"   # 通知腔; "大家好" greeting is exempt

# Family h (R-17): point diction discipline. Sources: xiaoma-durex-copywriter
# diction.md §6 (从不解释自己 — 260 条语料零次「这意味着」类 narrator 腔) and
# §5 (「大家」= 通知的口吻), §3 (形容词接近于零 → intensifier stacking);
# shuorenhua SKILL.md §8 Pass 2 item 3 (narrator 残留). Points are assertions,
# not narration — connectives only count at the point opening.
POINT_NARRATOR_OPENERS = (
    "这说明", "这意味着", "由此可见", "不难看出",
)
POINT_NOTICE_PERSONA = "大家"            # notice tone inside points
QUOTE_PAGE_ROLE_WORDS = ("金句", "氛围")  # persona hit aggravated on these pages
INTENSIFIER_ADVERBS = ("非常", "十分", "极其")
INTENSIFIER_RE = re.compile(
    "(?:" + "|".join(INTENSIFIER_ADVERBS) + ")(?=[一-龥])")
INTENSIFIER_PAGE_MIN = 2                 # same-page stacking threshold

# Family i (R-18): title-fulfillment reconciliation. Source:
# bigpeng-hot-gzh qa-checklist 「每条标题都写了正文必须兑现什么」— the
# machine-checkable subset is: every number in a title must be covered by this
# page's number-ledger rows (value set of the 数值 column).
# Tokens glued to ASCII letters/digits (S5, P23, F3, 2026Q3, 100ms) are
# identifier fragments, not assertion numbers; bare 19xx/20xx four-digit tokens
# read as years, not metrics.
TITLE_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?<![A-Za-z]-)"
    r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|\d+(?:\.\d+)?%?)(?![A-Za-z0-9])")
LEDGER_PAGE_CODE_RE = re.compile(r"^(S\d+|P\d+|附)")
YEAR_LIKE_RE = re.compile(r"^(?:19|20)\d{2}$")

# Family j (R-21): argument-medium diversity. Source: Viral_Writer_Skill
# SKILL.md 维度 8「论证方式多样性」— alternating story/data/analogy keeps
# attention; the machine-checkable subset is a monotonous run of 3 content
# pages all-pure-data or all-pure-qualitative (upstream snapshot 2026-08-31).
MEDIUM_DATA_RATIO = 0.6           # digit-bearing points >= 60% => pure-data page
ARGUMENT_ROLE_DATA_WORDS = ("数据", "证据")
POINT_DIGIT_RE = re.compile(r"\d")
MEDIUM_RUN_LEN = 3

# Family k (R-22): quote-page criteria. Source: Viral_Writer_Skill SKILL.md
# 维度 5 — a good quote "能脱离上下文独立传播 / 包含洞见（不是口号）";
# deterministic subset = slogan-pattern lexicon + at most one opposite-pair
# quote per deck ("少即是多" style restraint inversions).
SLOGAN_WORDS = (
    "拥抱", "坚持", "相信", "成就", "创造", "引领", "赋能", "突破", "超越",
    "共赢", "未来", "梦想", "初心", "热爱", "坚守", "致远", "前行", "追梦",
    "砥砺", "扬帆", "启航", "同心", "聚力", "乘势", "笃行",
)
SLOGAN_MAX_LEN = 16                # abstract short phrases only
EVIDENCE_TAG_RE = re.compile(r"【(?:引用|估算|示意|用户确认)|\[src:")
OPPOSITE_QUOTE_RE = re.compile(r"[一-龥]{1,3}(?:即是|就是)[一-龥]{1,3}")
OPPOSITE_QUOTE_DECK_LIMIT = 1

# Family l (R-23): vague intensifiers in academic points. Source:
# codex-claude-academic-skills research-writing-skill/SKILL.md L35 —
# 'Replace vague words such as "显著", "先进", "有效", "鲁棒" with measured
# conditions, comparison baselines, or remove them' (snapshot 2026-08-31).
VAGUE_WORDS = ("显著", "先进", "有效", "鲁棒")
QUOTED_SPAN_RE = re.compile(r"「[^」]*」|“[^”]*”|\"[^\"]*\"|《[^》]*》")
VAGUE_QUANTIFIER_RE = re.compile(
    r"\d|相比|对照|基线|相对|versus|vs\.?", re.I)
ILLUSTRATIVE_TAG_RE = re.compile(r"【示意|\[示意|\(示意")
ACADEMIC_MARKER_RE = re.compile(r"deck-contract\s*[:：]|math_load|figure_orientation")

# Family m (R2 测评迭代): causal-attribution discipline in points. Source:
# insight-persuasion round-1 ledger — R06-4「全局限流假设」/R11-1「差异由
# 店型决定」/R12-1「11 天不是人的问题是没有标尺的问题」：根因断言句式强于
# 证据等级。Deterministic subset: attribution markers in a point line with
# neither an evidence-tag span nor an explicit hedge → WARN suggesting the
# hedged wording; sourced (【引用|src:…】) or hedged (线索/待验证/unknown/
# 假设/或含) attributions stay exempt.
CAUSAL_ATTRIBUTION_MARKERS = (
    "根因", "症结在", "根源在", "本质上是", "最可能是", "归因于",
)
CAUSAL_HEDGE_MARKERS = ("线索", "待验证", "unknown", "假设", "或含")

# Style-sample high-frequency words (R-20): user voice outranks generic
# vocabularies; top-N join the exemption side of word-list families
# (jargon / intensifiers / vague words). Single-char stopwords that would
# kill real two-char words (赋能/有效/要素…) are deliberately absent.
STYLE_SAMPLE_TOP_N = 20
STYLE_SAMPLE_STOPWORDS = {
    "的", "了", "和", "是", "在", "与", "及", "或", "等", "为", "对", "从",
    "被", "把", "向", "于", "中", "上", "下", "并", "其", "这", "那", "也",
    "都", "就", "个", "之", "以", "而", "则", "将",
    "我们", "可以", "一个", "没有", "自己", "什么", "就是", "还是", "因为",
    "所以", "但是", "如果", "这个", "那个",
}
STYLE_SAMPLE_CJK_BIGRAM_RE = re.compile(r"[一-龥]{2}")
STYLE_SAMPLE_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]+")

# ---------------------------------------------------------------------------
# Master markdown parsing (best effort; both S<N> and P<N> conventions).
# ---------------------------------------------------------------------------

PAGE_RE = re.compile(r"^##\s+(?:S\d+|P\d+|附)[^\n]*$", re.M)
TITLE_RE = re.compile(r"[-•]\s*标题[：:]\s*(.+)")
POINT_LINE_RE = re.compile(r"^\s*(?:[-•]|\d+\.|\d+、)\s*(.+)$", re.M)
SPEAKER_LINE_RE = re.compile(r"^\s*[-*]?\s*speaker_script\s*[:：]\s*(.+)$", re.M)
ROLE_RE = re.compile(r"(?:页面角色|角色|role)[：:]\s*([^\s,，;；。]+)", re.I)
ARGUMENT_ROLE_RE = re.compile(
    r"argument_role[：:]\s*([^\s,，;；。]+)", re.I)
FUNCTIONAL_ROLE_WORDS = (
    "开场", "封面", "目录", "章节", "隔断", "过渡", "收束", "结尾", "致谢", "问答",
)
# Bullet lines matching these keys are metadata, not points.
NON_POINT_KEYS = (
    "标题", "备注", "视觉行", "视觉", "argument_role", "数字登记表",
    "speaker_script", "engineering", "图[",
)
# 页面级元信息（deck-master.md「页面级元信息」节: 页面角色/argument_role/beat/
# audience_takeaway/rst_relation）可能合法地写成 bullet——把它们挡在要点列表
# 之外，防同构/金句/措辞族把元数据读成文案。
METADATA_POINT_KEYS = (
    "页面角色", "audience_takeaway", "rst_relation", "beat：", "beat:",
)
NON_POINT_KEYS = NON_POINT_KEYS + METADATA_POINT_KEYS
# Bare label lines ("要点：" header or the zero-point declaration "要点：无").
POINT_LABEL_RE = re.compile(r"^要点[：:]\s*(?:无)?$")


class ProseParseError(Exception):
    """Raised when the master cannot be parsed into pages at all."""


class Page:
    __slots__ = ("label", "title", "points", "speaker", "functional",
                 "role", "argument_role")

    def __init__(self, label):
        self.label = label
        self.title = ""
        self.points = []
        self.speaker = []
        self.functional = False
        self.role = ""
        self.argument_role = ""

    def text_segments(self):
        """Yield (where, line_text) for title, points, then speaker_script lines."""
        if self.title:
            yield "标题", self.title
        for i, point in enumerate(self.points, start=1):
            yield f"要点{i}", point
        for line in self.speaker:
            yield "speaker_script", line

    def slide_text(self):
        """Title + points joined (on-slide text only)."""
        parts = ([self.title] if self.title else []) + self.points
        return "".join(parts)


def page_is_functional(body: str, header: str) -> bool:
    # Same role-line detection as check_master_contract.py, plus header keywords
    # as a best-effort fallback for masters without explicit 角色： lines.
    for m in ROLE_RE.finditer(body):
        if any(w in m.group(1) for w in FUNCTIONAL_ROLE_WORDS):
            return True
    return any(w in header for w in FUNCTIONAL_ROLE_WORDS)


def parse_master(text: str) -> "list[Page]":
    # The number ledger tail is not page prose; drop it before splitting.
    body_text = text.split("## 数字登记表", 1)[0]
    matches = list(PAGE_RE.finditer(body_text))
    if not matches:
        raise ProseParseError(
            "母版解析失败：未发现任何页（## S<N> / ## P<N> / ## 附 均无命中）")
    pages = []
    for i, m in enumerate(matches):
        seg = body_text[m.start():matches[i + 1].start()
                        if i + 1 < len(matches) else len(body_text)]
        header = m.group(0).strip()
        page = Page(header.lstrip("#").strip())
        t = TITLE_RE.search(seg)
        if t:
            page.title = t.group(1).strip()
        for pm in POINT_LINE_RE.finditer(seg):
            content = pm.group(1)
            if any(k in content for k in NON_POINT_KEYS):
                continue
            if POINT_LABEL_RE.match(content.strip()):
                continue
            page.points.append(content.strip())
        for sm in SPEAKER_LINE_RE.finditer(seg):
            page.speaker.append(sm.group(1).strip())
        role_m = ROLE_RE.search(seg)
        if role_m:
            page.role = role_m.group(1)
        arg_m = ARGUMENT_ROLE_RE.search(seg)
        if arg_m:
            page.argument_role = arg_m.group(1)
        page.functional = page_is_functional(seg, header)
        pages.append(page)
    return pages


def parse_number_ledger(text):
    """Extract per-page numeric value sets from the trailing number ledger.

    Returns ``(page_values, exists)``: ``page_values`` maps a ledger 页 cell
    ("S3", "P2", "附", …) to the set of normalized numeric literals found in
    that row's 数值 cells ("55%", "1.24"); ``exists`` is False when the master
    carries no ``## 数字登记表`` section (or an unusable table), in which case
    family i skips. Numeric literals use the same TITLE_NUMBER_RE as titles so
    both sides normalize identically ("1.24 亿元" ↔ "1.24").
    """
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("## 数字登记表"):
            start = i + 1
            break
    if start is None:
        return {}, False
    rows = []
    for ln in lines[start:]:
        s = ln.strip()
        if s.startswith("## "):
            break
        if s.startswith("|"):
            rows.append(s)
    if not rows:
        return {}, False
    header = split_ledger_row(rows[0])
    if "数值" not in header or "页" not in header:
        return {}, False
    value_idx, page_idx = header.index("数值"), header.index("页")
    page_values = {}
    for row in rows[1:]:
        if re.match(r"^\|[\s:|-]+\|$", row):
            continue
        cells = split_ledger_row(row)
        if len(cells) <= max(value_idx, page_idx):
            continue
        for code in re.split(r"[、,，/／\s]+", cells[page_idx]):
            if code:
                page_values.setdefault(code, set()).update(
                    _numeric_key(v)
                    for v in TITLE_NUMBER_RE.findall(cells[value_idx]))
    return page_values, True


def _numeric_key(token):
    """Normalize a numeric literal for title↔ledger comparison.

    Batch-1 interop fix (2026-09-07): titles and ledger cells write the same
    quantity in different shapes — 「+11%」 vs 「11.0」, 「1,599」 vs 「1599」.
    Strip thousand separators and a trailing ``%`` so both sides compare by
    value; genuine numeric differences still warn (the message keeps the raw
    title token)."""
    key = token.replace(",", "").rstrip("%")
    try:
        return repr(float(key))  # 「55」与「55.0」按值对齐
    except ValueError:
        return key


def split_ledger_row(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def _finding(family, severity, page, where, message):
    return {"family": family, "severity": severity, "page": page,
            "where": where, "message": message}


def _excerpt(text, limit=24):
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…"


def find_reversal(pages):
    """Family a. Density/exemption framework:
    - inline 「（豁免：论证骨架）」on the hit line → exempt (INFO);
    - a single isolated hit on a page with <= 3 points → not counted (INFO);
    - counted hits: >= 2 → FAIL (deck-level cap is 1); exactly 1 → WARN asking
      for the real-argument-skeleton exemption note.
    """
    findings = []
    counted = []
    for page in pages:
        hits = []
        for where, line_text in page.text_segments():
            for name, rx in REVERSAL_PATTERNS:
                for m in rx.finditer(line_text):
                    hits.append((where, name, m.group(0), line_text))
        if not hits:
            continue
        short_page = len(page.points) <= REVERSAL_SHORT_PAGE_POINTS
        for where, name, matched, line_text in hits:
            if REVERSAL_EXEMPT_RE.search(line_text):
                findings.append(_finding(
                    "reversal", "INFO", page.label, where,
                    f"翻案腔（{name}）已豁免注明：{_excerpt(matched)}"))
            elif len(hits) == 1 and short_page:
                findings.append(_finding(
                    "reversal", "INFO", page.label, where,
                    f"孤立翻案腔命中不计（要点 ≤{REVERSAL_SHORT_PAGE_POINTS} 的页）："
                    f"{_excerpt(matched)}"))
            else:
                counted.append((page, where, name, matched))
    total = len(counted)
    if total >= 2:
        for page, where, name, matched in counted:
            findings.append(_finding(
                "reversal", "FAIL", page.label, where,
                f"翻案腔（{name}）：{_excerpt(matched)}"))
        findings.append(_finding(
            "reversal", "FAIL", "全 deck", "",
            f"翻案腔计 {total} 处，超过 deck 级上限 {REVERSAL_DECK_LIMIT}"
            "——回母版改为正面陈述"))
    elif total == 1:
        page, where, name, matched = counted[0]
        findings.append(_finding(
            "reversal", "WARN", page.label, where,
            f"唯一翻案腔命中（{name}）：{_excerpt(matched)}"
            "——须为真实论证骨架；若确为论证，该行尾注明（豁免：论证骨架）"))
    return findings


def find_jargon(pages, allow):
    """Family b. Industry-term exemption: same word >= JARGON_INDUSTRIAL_MIN
    times on one page, or listed via --allow."""
    findings = []
    for page in pages:
        page_text = " ".join(filter(None, [page.title] + page.points))
        for word in JARGON_WORDS:
            if word in allow:
                continue
            n = page_text.count(word)
            if n == 0:
                continue
            if n >= JARGON_INDUSTRIAL_MIN:
                findings.append(_finding(
                    "jargon", "INFO", page.label, "",
                    f"黑话「{word}」同页 {n} 次，按行业既定词豁免"))
            else:
                findings.append(_finding(
                    "jargon", "WARN", page.label, "",
                    f"黑话「{word}」出现 {n} 次——换回普通动作"
                    f"（行业既定词可 --allow {word}，同页 ≥{JARGON_INDUSTRIAL_MIN} "
                    "次自动豁免）"))
    return findings


def find_nominalization(pages):
    """Family c. WARN-level counting only (deck-master checklist item 4)."""
    findings = []
    for page in pages:
        for where, line_text in page.text_segments():
            for m in NOMINALIZATION_RE.finditer(line_text):
                findings.append(_finding(
                    "nominalization", "WARN", page.label, where,
                    f"名词化「{m.group(0)}」——还原为直接动词句"))
    return findings


def find_isomorphic(pages):
    """Family d. First takeaway point of 3 consecutive content pages sharing
    the same opening prefix (deck-master checklist item 3, points variant)."""
    findings = []
    seq = [p for p in pages if not p.functional and p.points]
    n = ISOMORPHIC_PREFIX_LEN
    i = 0
    while i + 2 < len(seq):
        window = seq[i:i + 3]
        prefixes = [p.points[0][:n] for p in window]
        if all(len(x) >= n for x in prefixes) and len(set(prefixes)) == 1:
            labels = "、".join(p.label for p in window)
            findings.append(_finding(
                "isomorphic", "WARN", "全 deck", "",
                f"连续 3 页第一条要点同构开头「{prefixes[0]}…」（{labels}）"
                "——留两项或第三项换写法"))
            i += 3
        else:
            i += 1
    return findings


def find_connective(pages):
    """Family e. Per-page density; isolated single connectives never flag
    (humanizer: one *however* is not a tell). Longest-first non-overlapping
    counting via CONNECTIVE_ANY_RE — a lone 「与此同时」 is one hit, not two."""
    findings = []
    for page in pages:
        text = page.slide_text()
        if not text:
            continue
        hits = len(CONNECTIVE_ANY_RE.findall(text))
        if hits < CONNECTIVE_MIN_HITS:
            continue
        char_len = len(re.sub(r"\s", "", text))
        density = hits * 1000 / char_len if char_len else 0.0
        if density > CONNECTIVE_DENSITY_LIMIT:
            findings.append(_finding(
                "connective", "WARN", page.label, "",
                f"连词 {hits} 处 / 约 {char_len} 字（{density:.1f} 处/千字 > "
                f"{CONNECTIVE_DENSITY_LIMIT:g}）——删掉一半，小句靠语序与事理相接"))
    return findings


def find_format(pages):
    """Family f. WARN-level formatting subset over title/points/speaker lines.

    Evidence-tag spans (EVIDENCE_SPAN_RE) are masked first: they carry the
    contract-mandated halfwidth ``src:``/``round:`` separators that must not
    read as halfwidth punctuation in CJK context.
    """
    findings = []
    for page in pages:
        for where, line_text in page.text_segments():
            scan_text = EVIDENCE_SPAN_RE.sub("", line_text)
            for name, rx, advice in FORMAT_CHECKS:
                for m in rx.finditer(scan_text):
                    findings.append(_finding(
                        "format", "WARN", page.label, where,
                        f"格式[{name}]「{m.group(0)}」——{advice}"))
    return findings


def find_ai_flavor(pages, allow):
    """Family m (R-27). Whole-phrase word-boundary matches only; quoted spans
    stay exempt so product names like "Customer Journey Map" survive when the
    deck author marks them as such."""
    findings = []
    for page in pages:
        segments = [(where, text) for where, text in page.text_segments()
                    if where == "标题" or where.startswith("要点")]
        for where, line_text in segments:
            stripped = QUOTED_SPAN_RE.sub("", line_text)
            for label, pattern in AI_FLAVOR_PATTERNS:
                if label in allow:
                    continue
                m = pattern.search(stripped)
                if m:
                    findings.append(_finding(
                        "ai_flavor", "WARN", page.label, where,
                        f"AI 腔英文套话「{m.group(0).lower()}」（{label}）——换回具体动作或直陈句"
                        f"（产品名可加引号豁免，或 --allow {label}）"))
    return findings


def scan_speaker_scripts(items):
    """Family g (R-16). Reused by export_speaker_notes.py --prose-check.

    ``items``: iterable of (label, text) pairs — e.g. page label and its
    joined speaker_script lines, or PPTX notes pages. Returns WARN findings
    for clichés, over-long sentences, and notice-tone 「大家」.
    """
    findings = []
    for label, text in items:
        if not text:
            continue
        for phrase in SCRIPT_CLICHES:
            n = text.count(phrase)
            if n:
                findings.append(_finding(
                    "script-cliche", "WARN", label, "",
                    f"讲稿套话「{phrase}」×{n}——删掉，直接说"))
        for sent in re.split(r"[。！？!?；;\n]+", text):
            s = sent.strip()
            if len(s) > SCRIPT_MAX_SENTENCE_LEN:
                findings.append(_finding(
                    "script-sentence", "WARN", label, "",
                    f"长句 {len(s)} 字（> {SCRIPT_MAX_SENTENCE_LEN}）："
                    f"{_excerpt(s, 20)}…——拆成短句口语"))
        persona_n = text.count(SCRIPT_NOTICE_PERSONA) - text.count("大家好")
        if persona_n > 0:
            findings.append(_finding(
                "script-persona", "WARN", label, "",
                f"「{SCRIPT_NOTICE_PERSONA}」×{persona_n}——通知腔，"
                "改「你」或去人称（「大家好」问候不计）"))
    return findings


def find_diction(pages, sample_words=frozenset()):
    """Family h (R-17). All WARN: points are assertions, not narration.

    ① narrator connectives only count at the point opening (mid-point uses are
    legitimate argumentation); ② notice-tone 「大家」 in points, aggravated
    wording on 金句/氛围 pages; ③ intensifier-adverb stacking counted per page
    over title + points, threshold INTENSIFIER_PAGE_MIN (style-sample words
    exempt per R-20).
    """
    findings = []
    for page in pages:
        for i, point in enumerate(page.points, start=1):
            for opener in POINT_NARRATOR_OPENERS:
                if point.startswith(opener):
                    findings.append(_finding(
                        "diction-narrator", "WARN", page.label, f"要点{i}",
                        f"要点以「{opener}」开头——要点是断言不是讲解，"
                        "删连接词直接给结论"))
                    break
            if POINT_NOTICE_PERSONA in point:
                quote_page = any(w in page.label for w in QUOTE_PAGE_ROLE_WORDS)
                findings.append(_finding(
                    "diction-persona", "WARN", page.label, f"要点{i}",
                    f"要点含「{POINT_NOTICE_PERSONA}」——通知腔人称，改「你」或"
                    "去人称" + ("（金句/氛围页加重）" if quote_page else "")))
        hits = [h for h in INTENSIFIER_RE.findall(page.slide_text())
                if h not in sample_words]
        if len(hits) >= INTENSIFIER_PAGE_MIN:
            words = "、".join(dict.fromkeys(hits))
            findings.append(_finding(
                "diction-intensifier", "WARN", page.label, "",
                f"强度副词+形容词 ×{len(hits)}（{words}，同页 "
                f"≥{INTENSIFIER_PAGE_MIN} 处）——形容词堆砌，换具体数字或动词"))
    return findings


def find_title_fulfillment(pages, page_values, ledger_exists):
    """Family i (R-18). Title numbers must be covered by this page's ledger
    rows (数值 set of the 页-matching rows); masters without a ledger skip
    the family with a single INFO note."""
    findings = []
    if not ledger_exists:
        findings.append(_finding(
            "title-ledger", "INFO", "全 deck", "",
            "母版无数字登记表，标题兑现对账跳过"))
        return findings
    for page in pages:
        if not page.title:
            continue
        code_m = LEDGER_PAGE_CODE_RE.match(page.label)
        if not code_m:
            continue
        code = code_m.group(1)
        ledger_values = page_values.get(code, set())
        for token in TITLE_NUMBER_RE.findall(page.title):
            if YEAR_LIKE_RE.match(token):
                continue  # bare 19xx/20xx reads as a year, not an assertion
            if _numeric_key(token) not in ledger_values:
                findings.append(_finding(
                    "title-ledger", "WARN", page.label, "标题",
                    f"标题数字「{token}」不在本页（{code}）登记表数值中——"
                    "回母版对账，或补登记行"))
    return findings


def _page_medium(page):
    """Family j helper: 'data' / 'qualitative' / 'mixed' / None (no points).

    argument_role declaring 数据/证据 wins (evidence pages citing textual
    findings still argue through data); otherwise the digit-bearing share of
    points decides: >= MEDIUM_DATA_RATIO pure-data, zero pure-qualitative.
    """
    if any(w in page.argument_role for w in ARGUMENT_ROLE_DATA_WORDS):
        return "data"
    if not page.points:
        return None
    digit_points = sum(1 for p in page.points if POINT_DIGIT_RE.search(p))
    ratio = digit_points / len(page.points)
    if ratio >= MEDIUM_DATA_RATIO:
        return "data"
    if digit_points == 0:
        return "qualitative"
    return "mixed"


def find_argument_medium(pages):
    """Family j (R-21). A monotonous run of MEDIUM_RUN_LEN content pages all
    pure-data or all pure-qualitative flags a medium change (analogy / case /
    counter-example)."""
    findings = []
    seq = [p for p in pages if not p.functional and p.points]
    mediums = [_page_medium(p) for p in seq]
    i = 0
    while i + MEDIUM_RUN_LEN <= len(seq):
        window = mediums[i:i + MEDIUM_RUN_LEN]
        if window[0] in ("data", "qualitative") and len(set(window)) == 1:
            kind = "纯数据" if window[0] == "data" else "纯定性"
            labels = "、".join(p.label for p in seq[i:i + MEDIUM_RUN_LEN])
            findings.append(_finding(
                "argument-medium", "WARN", "全 deck", "",
                f"连续 {MEDIUM_RUN_LEN} 个内容页同为{kind}论证（{labels}）——"
                "换一页媒介：类比 / 案例 / 反例，防连排单调"))
            i += MEDIUM_RUN_LEN
        else:
            i += 1
    return findings


def _is_quote_page(page):
    label_role = page.label + " " + page.role
    return any(w in label_role for w in QUOTE_PAGE_ROLE_WORDS)


def find_quote_quality(pages):
    """Family k (R-22). Deterministic subset of the quote criteria: slogan
    patterns (abstract phrase, no digits, no evidence tag, lexicon hit) on
    quote/atmosphere pages, and at most one opposite-pair quote per deck."""
    findings = []
    opposite_hits = []
    for page in pages:
        if not _is_quote_page(page):
            continue
        for i, point in enumerate(page.points, start=1):
            if (POINT_DIGIT_RE.search(point) or EVIDENCE_TAG_RE.search(point)):
                continue
            compact = re.sub(r"[\s，。,.;；:：!！?？]", "", point)
            if len(compact) <= SLOGAN_MAX_LEN and any(
                    w in compact for w in SLOGAN_WORDS):
                findings.append(_finding(
                    "quote-slogan", "WARN", page.label, f"要点{i}",
                    f"金句要点为口号模式「{_excerpt(point)}」——重写为具体洞见"
                    "（具体名词/数字；脱离本页上下文仍能独立成立）"))
            if OPPOSITE_QUOTE_RE.search(compact):
                opposite_hits.append((page.label, i, _excerpt(point)))
    if len(opposite_hits) > OPPOSITE_QUOTE_DECK_LIMIT:
        listed = "；".join(f"{lbl} 要点{i}「{txt}」"
                          for lbl, i, txt in opposite_hits)
        findings.append(_finding(
            "quote-opposite", "WARN", "全 deck", "",
            f"反向克制型金句（A 即是 B）deck 级 {len(opposite_hits)} 处，"
            f"超过上限 {OPPOSITE_QUOTE_DECK_LIMIT}（{listed}）——留最锐的一处，"
            "其余改为正面具体洞见"))
    return findings


def find_vague_words(pages, master_text, exempt_words):
    """Family l (R-23). Academic decks only (deck-contract block present):
    vague intensifier in a point without a same-line quantifier (digit /
    percent / comparison baseline) warns; quoted spans, illustrative-level
    tags and style-sample words are exempt."""
    findings = []
    if not ACADEMIC_MARKER_RE.search(master_text):
        findings.append(_finding(
            "vague-word", "INFO", "全 deck", "",
            "非学术母版（无 deck-contract 块），要点模糊词检查跳过"))
        return findings
    for page in pages:
        if page.functional:
            continue
        for i, point in enumerate(page.points, start=1):
            if ILLUSTRATIVE_TAG_RE.search(point):
                continue
            bare = QUOTED_SPAN_RE.sub("", point)
            for word in VAGUE_WORDS:
                if word in exempt_words:
                    continue
                if word in bare and not VAGUE_QUANTIFIER_RE.search(point):
                    findings.append(_finding(
                        "vague-word", "WARN", page.label, f"要点{i}",
                        f"要点模糊强度词「{word}」且同行无量化条件——"
                        "替换为测量条件（数字/百分比/对照基线），或删除该修饰"))
    return findings


def find_causal_attribution(pages):
    """Family m (R2 eval iteration). Root-cause assertion phrasing in a
    point without either an evidence-tag span or an explicit hedge reads
    stronger than its source level (round-1 ledger R06-4/R11-1/R12-1);
    WARN suggests the hedged wording. Titles are assertion sentences by
    design and stay out of scope."""
    findings = []
    for page in pages:
        for where, line_text in page.text_segments():
            if not where.startswith("要点"):
                continue
            if not any(m in line_text for m in CAUSAL_ATTRIBUTION_MARKERS):
                continue
            if EVIDENCE_SPAN_RE.search(line_text):
                continue  # attribution carries a source_ref → sourced
            if any(h in line_text for h in CAUSAL_HEDGE_MARKERS):
                continue  # already hedged as a lead, not a conclusion
            marker = next(m for m in CAUSAL_ATTRIBUTION_MARKERS
                          if m in line_text)
            findings.append(_finding(
                "causal-attribution", "WARN", page.label, where,
                f"根因断言「{marker}」无引用级证据锚点——降级为线索句式"
                "（标「线索/待验证」）或补【引用|src:锚点】"))
    return findings


def extract_style_sample_words(text, top_n=STYLE_SAMPLE_TOP_N):
    """R-20. Deterministic top-N high-frequency words of a user voice sample:
    CJK bigrams + ASCII tokens, stopword-filtered, frequency then lexical
    order for stability."""
    counts: dict[str, int] = {}
    for m in STYLE_SAMPLE_CJK_BIGRAM_RE.finditer(text):
        gram = m.group(0)
        if gram[0] in STYLE_SAMPLE_STOPWORDS or gram[1] in STYLE_SAMPLE_STOPWORDS:
            continue
        counts[gram] = counts.get(gram, 0) + 1
    for m in STYLE_SAMPLE_TOKEN_RE.finditer(text):
        token = m.group(0).casefold()
        if token in STYLE_SAMPLE_STOPWORDS:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {word for word, _ in ranked[:top_n]}


def run_checks(pages, allow, ledger=None, sample_words=frozenset(),
               master_text=""):
    """Run all deck families + speaker discipline; returns findings list.

    ``ledger`` is the ``(page_values, exists)`` tuple from
    parse_number_ledger (family i); defaults to no-ledger skip behaviour.
    ``sample_words`` (R-20 --style-sample) joins the exemption side of the
    word-list families; ``master_text`` feeds the academic marker for family l.
    """
    findings = []
    findings += find_reversal(pages)
    findings += find_jargon(pages, allow | sample_words)
    findings += find_nominalization(pages)
    findings += find_isomorphic(pages)
    findings += find_connective(pages)
    findings += find_format(pages)
    findings += scan_speaker_scripts(
        (p.label, "\n".join(p.speaker)) for p in pages)
    findings += find_diction(pages, sample_words)
    page_values, ledger_exists = ledger if ledger else ({}, False)
    findings += find_title_fulfillment(pages, page_values, ledger_exists)
    findings += find_argument_medium(pages)
    findings += find_quote_quality(pages)
    findings += find_vague_words(pages, master_text, sample_words)
    findings += find_ai_flavor(pages, allow)
    findings += find_causal_attribution(pages)
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render_human(file_name, pages, findings):
    content = sum(1 for p in pages if not p.functional)
    lines = [
        f"DECK-PROSE: {file_name}",
        f"PAGES: {len(pages)} 页（内容页 {content} / 功能页 {len(pages) - content}）",
    ]
    for f in findings:
        loc = " ".join(x for x in (f["page"], f["where"]) if x)
        lines.append(f"[{f['severity']}] " + (f"{loc}：" if loc else "") + f["message"])
    counts = {sev: sum(1 for f in findings if f["severity"] == sev)
              for sev in ("FAIL", "WARN", "INFO")}
    lines.append(
        f"SUMMARY: FAIL {counts['FAIL']} / WARN {counts['WARN']} / "
        f"INFO {counts['INFO']} —— WARN 随确认摘要说明取舍；FAIL 回母版改写后重跑")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="deck 文案确定性检测（R-15）与讲稿口语化纪律（R-16）")
    parser.add_argument("master", help="母版 markdown 路径（deck-master-v<N>.md）")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 而非人类可读报告")
    parser.add_argument("--allow", action="append", default=[], metavar="词表",
                        help="豁免词表（黑话/行业既定词），逗号分隔，可多次")
    parser.add_argument("--style-sample", default=None, metavar="FILE",
                        help="用户文风样本文件（R-20）：高频词加入词表类检测"
                             "（黑话/强度副词/模糊词）的豁免侧")
    args = parser.parse_args(argv)

    path = Path(args.master)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: 无法读取母版 {path}: {exc}", file=sys.stderr)
        return 2
    try:
        pages = parse_master(text)
    except ProseParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    sample_words = frozenset()
    if args.style_sample:
        try:
            sample_text = Path(args.style_sample).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: 无法读取文风样本 {args.style_sample}: {exc}",
                  file=sys.stderr)
            return 2
        if not sample_text.strip():
            print(f"ERROR: 文风样本为空文件 {args.style_sample}", file=sys.stderr)
            return 2
        sample_words = extract_style_sample_words(sample_text)

    allow = {w.strip() for a in args.allow for w in a.split(",") if w.strip()}
    findings = run_checks(pages, allow, parse_number_ledger(text),
                          sample_words, master_text=text)
    fails = sum(1 for f in findings if f["severity"] == "FAIL")
    exit_code = 1 if fails else 0

    if args.json:
        content = sum(1 for p in pages if not p.functional)
        payload = {
            "file": str(path),
            "pages": {"total": len(pages), "content": content,
                      "functional": len(pages) - content},
            "exit": exit_code,
            "counts": {sev: sum(1 for f in findings if f["severity"] == sev)
                       for sev in ("FAIL", "WARN", "INFO")},
            "allow": sorted(allow),
            "style_sample_words": sorted(sample_words),
            "findings": findings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(render_human(path.name, pages, findings))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
