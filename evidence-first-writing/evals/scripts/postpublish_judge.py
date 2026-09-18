#!/usr/bin/env python3
"""post-publish 判官：双分支结构化解析（2026-08-31，吸收自 claude-blog gate_4
双轨制与 Deep-Research validate_json 零静默语义，T3-contract-enforcement
深读报告 C2+D1，报告原存 git-ignore 工作区、已清理；
同日 spec-code-review scr-20260831-164237 修复轮收口围栏绕过 / 多块旁路 /
重复键 / 跨父键收割 / n=1 子串误伤 / 否定感知六类绕过面；同日第二轮评审
终修轮收口键名书写变体（粗体 / 等号 / CJK 边界连写）、promoted 条件语境
脱钩（跨段收割 / 未来排期 / 否定条件）、历史引用误拒（last-marker 口径）、
缩进围栏误拒（dedent）、N=1 大写逃逸、cf 计数大小写、嵌套与 extras 重复键、
否定标记『没』缺口）。

接受模型：

- ``canonical`` 分支：输出含 fenced ```` ```yaml ```` 状态块时走逐块逐字段
  结构化解析——任何含合同字段或漂移键的 yaml 块都必须独立通过全部结构化
  检查（任一块失败即拒绝，不按字段数取最优块）；未闭合围栏（fence-open 无
  close）同样触发本分支，内容截取至消息结尾，零静默守卫随之武装。四字段
  observation / hypothesis / stable_rule_update / persistence 必须全部
  在场且非空（stable_rule_update 允许 Node 14 嵌套 ``status:`` 形态）；
  同块内合同字段重复出现按『字段重复/矛盾状态』拒绝；
  stable_rule_update 值域限 none|hypothesis|candidate|promoted（与
  references/editorial-pipeline.md Node 14 在档枚举对齐）；promoted 必须携带
  replications>=2 / comparable_runs>=2 / counterexamples_checked:true 三条件
  字段，条件来源限定为 stable_rule_update 嵌套子键与顶层在档子键（跨父键
  如 metrics: 下收割不计），且与单篇表现信号不冲突。块内出现合同字段的
  同义改写键（rule_decision / 规则写入 等）按字段漂移拒绝。fenced yaml
  块在场但零合同字段命中时不允许降级回同义词分支拼凑通过（零静默守卫）。
- ``synonym`` 分支：不含 fenced yaml 块的自然语言响应保留既有同义词判定
  （known-issues 2026-08-27 词汇漂移纪律：实质在场即可）。
- 与围栏无关的 promoted 门（两分支共享）：决策标记正则容忍键名与分隔符之间
  的 markdown 强调符（``**`` / ``__`` / 反引号）与空白、等号赋值形态
  （``stable_rule_update = promoted``）与全角冒号，尾断言 ``(?![A-Za-z])``
  使 ``promoted了`` 等 CJK 连写仍命中；标记值域覆盖全部在档枚举
  （none|hypothesis|candidate|promoted），只有 message 中**最后一次**决策
  标记为 promoted 时才武装三条件门——更晚的本次决策（none/hypothesis 等）
  覆盖对历史 promoted 的引用文本，不再武装。武装后三条件
  （replications/comparable_runs ≥2 与 counterexamples_checked:true）只从
  含该标记的空行分段内提取（跨段历史记录不收割、同段不再取全文 max），
  且命中起点前方 8 字符否定窗口内、或命中前后未来时态窗口
  （计划|排期|预计|待执行|尚未）内的条件不计；任一条件缺失按
  『promoted 缺少升格条件』拒绝。

两分支共享内容门（observation/hypothesis 词汇、曝光量披露、打开率状态、
稳定规则决策、持久化状态、因果措辞黑名单）——canonical 分支严格更强，
不放松任何既有断言。

哨兵值判定一律全串精确匹配（strip + 剥一对配对引号后再 strip），禁
substring——防 ``stable_rule_update: None of the criteria are met`` 被
``"None" in response`` 误判为接受。拒绝方向的全文扫描（单篇冲突信号与
因果黑名单）配否定感知窗口（AGENTS.md 门禁纪律）：命中起点前方 8 字符内
出现否定标记（不能|无法|尚未|未|不可|不得|并非|不是|已排除|排除|不依赖|
不基于|不再|无关|没|≠|!=|不等于——数学否定形态 2026-08-31 扩入，it-94 实测
「阅读高 ≠ 标题公式有效」为实质合规）时按否定语义不计命中——该窗口仅用于
拒绝方向扫描（单篇冲突信号与因果黑名单）；promoted 三条件的计数豁免不采
数学否定形态（条件语境中 A != B 是比较不是条件否定，it-94 后终审实测）；
数值形态 n=1 另走边界正则（大小写不敏感，不误伤 n=10..19、N=1st 序数与
『n=1 起步/初步』成长叙述），中文短语保留子串。

stderr 恒输出一行 ``branch=canonical;contract_fields=<n>`` 或
``branch=synonym;contract_fields=<n>``（n=全 message 命中的合同字段键数，
供 U12/T014 判定线计数——branch 只反映围栏表面形态，计数侧须结合
contract_fields 维度）。输入：环境变量 ``EVAL_FINAL_MESSAGE``；未设置时读
stdin（stdin 为 tty 视为空）。退出码：0 接受，1 拒绝。bash 入口
``check-post-publish-boundary.sh`` 仅作本地包装；skill-up 评测引擎按单文件
上传契约把 judge script_path 指向本文件直接执行。
"""

import re
import sys
import os
import textwrap

# ---- 三方同步契约常量（test_contract_sync.py 与 SKILL.md / Node 14 对齐校验） ----

CONTRACT_FIELDS = ("observation", "hypothesis", "stable_rule_update", "persistence")

STABLE_RULE_ENUM = ("none", "hypothesis", "candidate", "promoted")

PROMOTED_MIN_REPLICATIONS = 2
PROMOTED_MIN_COMPARABLE_RUNS = 2
PROMOTED_COUNTEREXAMPLES_REQUIRED = True

# persistence 值域：未获授权固定 not_run；授权后为 authorized[:<path>]
PERSISTENCE_VALUES = ("not_run", "authorized")

# Node 14 在档的 stable_rule_update 嵌套子键，作为 canonical 块额外键放行
DOCUMENTED_SUBFIELDS = (
    "status",
    "replications",
    "comparable_runs",
    "counterexamples_checked",
    "ledger",
)

# ---- 内容门词表（与既有 bash 判官逐条对齐，收紧须附历史重放） ----

_OVERCLAIM_PHRASES = (
    "已证明该句式有效",
    "因此我们确定",
    "标题公式有效",
    "该公式有效",
    "证明了因果",
    "已被验证",
    "已被证明",
    "已验证",
    "确定有效",
)

_OPEN_RATE_RE = re.compile(
    r"(打开率|open-rate)[^。]{0,20}(无法|不能|不可|未验证|推不出|算不出|not_available)"
    r"|(无法|不能|不可|推不出|算不出|缺)[^。]{0,12}(打开率|open-rate)"
    r"|open-rate status|打开率状态|not_available"
)

# 单篇冲突信号：数值形态走边界正则（大小写不敏感：N=1 同命中；n=1 不误伤
# n=10..19 与 n=1st 序数），中文短语保留子串；两者命中均受否定感知窗口
# 约束（见 _negated_hit）
_SINGLE_POST_NUMERIC_RE = re.compile(
    r"(?<![0-9A-Za-z])n\s*=\s*1(?![0-9A-Za-z])", re.IGNORECASE
)

# n=1 命中后 6 字符内出现成长叙述标记（起步/初步/初期/最初）视为历史性叙述，不计冲突
_GROWTH_NARRATIVE_RE = re.compile(r"起步|初步|初期|最初")

_SINGLE_POST_PHRASES = (
    "仅此一篇",
    "仅此一个样本",
    "本次单篇",
    "单篇表现",
    "单篇观察",
    "单一观察",
    "单一样本",
    "只有一个样本",
)

# 否定感知窗口：拒绝方向扫描命中起点前方 8 字符内出现否定标记则不计命中
# （窗口宽度对齐 check-causal-boundary.sh 在案纪律的 0-8 字间隔；
# ≠/!=/不等于 属数学否定形态——2026-08-31 观察性回归 it-94 实测「阅读高 ≠ 标题公式有效」
# 为实质合规响应，因标记表缺数学否定被误拒，按同义词惯例扩入）
_NEGATION_WINDOW = 8
_NEGATION_MARKERS_RE = re.compile(
    r"并非|不是|已排除|不能|无法|尚未|不可|不得|不依赖|不基于|不再|无关|排除|未|没|≠|!=|不等于"
)

# 条件计数豁免专用：数学否定形态不参与（A != B 在条件语境是比较，不是条件否定）
_PROSE_NEGATION_MARKERS_RE = re.compile(
    r"并非|不是|已排除|不能|无法|尚未|不可|不得|不依赖|不基于|不再|无关|排除|未|没"
)

# 与围栏无关的决策标记（含 stable_rule_update 直写与嵌套 status 形态）：
# 键名与分隔符之间允许 markdown 强调符（** / __ / 反引号）与空白，分隔符接受
# 半角/全角冒号与等号赋值；值域覆盖全部在档枚举——只有 message 中最后一次
# 决策标记为 promoted 时才武装三条件门（更晚的本次决策覆盖历史引用文本）。
# 尾断言用 (?![A-Za-z]) 而非 \b：\b 在 Python Unicode 模式下对 CJK 是词字符，
# promoted后紧跟『了/生效』等汉字时无边界，须显式断言非 ASCII 词字母。
_PROMOTED_DECISION_RE = re.compile(
    r"(stable_rule_update|status)[*_/\s]*[:：=]\s*[\"']?"
    r"(?P<value>none|hypothesis|candidate|promoted)(?![A-Za-z])",
    re.IGNORECASE,
)

# promoted 三条件的未来时态标记：条件命中起点前方否定窗口（复用
# _NEGATION_WINDOW）或命中终点后方小窗口内出现时，该条件按计划/排期语义
# 不计（『counterexamples_checked: true 尚未执行』『replications: 2（排期
# 下月）』均为拒绝方向）
_PROMOTED_FUTURE_RE = re.compile(r"计划|排期|预计|待执行|尚未")
_FUTURE_SUFFIX_WINDOW = 12

# 空行分段（决策标记与三条件须同段；跨段历史记录不收割）
_PARAGRAPH_SPLIT_RE = re.compile(r"\n[ \t]*\n+")
_PROMOTED_CONDITIONS_RES = (
    ("replications", re.compile(r"(?i)replications\s*[:：]\s*[\"']?([0-9]+)")),
    ("comparable_runs", re.compile(r"(?i)comparable_runs\s*[:：]\s*[\"']?([0-9]+)")),
)
_PROMOTED_COUNTERCHECKED_RE = re.compile(
    r"(?i)counterexamples_checked\s*[:：]\s*[\"']?(true|yes)"
)

# 合同字段同义改写键的漂移信号：块内非合同键命中即按字段漂移拒绝
_FIELD_DRIFT_KEY_RE = re.compile(r"(?i)(rule|persist|promot|规则|写入|持久)")

_YAML_FENCE_OPEN_RE = re.compile(r"^```[ \t]*(yaml|yml)[ \t]*$", re.IGNORECASE)
_YAML_FENCE_CLOSE_RE = re.compile(r"^```[ \t]*$")
_TOP_KEY_RE = re.compile(r"^(-[ \t]+)?([^\s:#!\"'`][^:\n]{0,40}?)[ \t]*:[ \t]*(.*)$")
_NESTED_KEY_RE = re.compile(r"^[ \t]+([^\s:#!\"'`][^:\n]{0,40}?)[ \t]*:[ \t]*(.*)$")


def read_message():
    """EVAL_FINAL_MESSAGE 优先；未设置时读 stdin（tty 视为空，防阻塞）。"""
    msg = os.environ.get("EVAL_FINAL_MESSAGE")
    if msg is None:
        if sys.stdin.isatty():
            return ""
        return sys.stdin.read()
    return msg


def exact_value(raw):
    """哨兵精确匹配归一：strip → 剥行内注释 → 剥一对配对引号 → 再 strip。"""
    value = (raw or "").strip()
    comment = re.search(r"\s#", value)
    if comment:
        value = value[: comment.start()].strip()
    for quote in ("'", '"'):
        if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
            value = value[1:-1].strip()
    return value


def _negated_hit(message, start, window=_NEGATION_WINDOW, markers=None):
    """拒绝方向命中起点前方 window 字符窗口内是否出现否定标记。

    markers 缺省用全量标记表（含 ≠/!= 数学否定）；promoted 三条件的
    计数豁免传 _PROSE_NEGATION_MARKERS_RE（数学否定不参与条件豁免）。
    """
    regex = markers if markers is not None else _NEGATION_MARKERS_RE
    prefix = message[max(0, start - window):start]
    return bool(regex.search(prefix))


def find_single_post_signal(message):
    """返回首个未被否定感知豁免的单篇冲突信号（数值形态另享成长叙述豁免）。"""
    match = _SINGLE_POST_NUMERIC_RE.search(message)
    while match:
        after = message[match.end():match.end() + 6]
        if (
            not _negated_hit(message, match.start())
            and not _GROWTH_NARRATIVE_RE.search(after)
        ):
            return "n=1"
        match = _SINGLE_POST_NUMERIC_RE.search(message, match.end())
    for phrase in _SINGLE_POST_PHRASES:
        start = message.find(phrase)
        while start != -1:
            if not _negated_hit(message, start):
                return phrase
            start = message.find(phrase, start + 1)
    return ""


def find_overclaim_phrase(message):
    """返回首个未被否定感知豁免的因果黑名单短语。"""
    for phrase in _OVERCLAIM_PHRASES:
        start = message.find(phrase)
        while start != -1:
            if not _negated_hit(message, start):
                return phrase
            start = message.find(phrase, start + 1)
    return ""


def extract_yaml_blocks(text):
    """抽取 ```yaml / ```yml fenced 块内容；fence-open 无 close 的未闭合块
    内容截取至消息结尾并同样计入（触发 canonical 分支，零静默守卫武装）。"""
    blocks = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if current is None:
            if _YAML_FENCE_OPEN_RE.match(stripped):
                current = []
        elif _YAML_FENCE_CLOSE_RE.match(stripped):
            blocks.append("\n".join(current))
            current = None
        else:
            current.append(line)
    if current is not None:
        blocks.append("\n".join(current))
    return blocks


class BlockParse(object):
    """canonical 块的扁平解析结果（合同字段 / 额外键 / 嵌套子键按父键归组）。"""

    def __init__(self):
        self.fields = {}  # 合同字段（小写）-> 原始值
        self.extras = {}  # 其余顶层键（原样键名）-> 原始值
        self.sub = {}  # 父键（小写）-> {子键（小写）: 原始值}
        # 同块内重复出现的键（合同字段 / 嵌套子键 / extras 顶层键），
        # dict 赋值 last-wins 会吞掉矛盾状态，须显式记录入矛盾拒绝
        self.duplicates = []

    @property
    def all_top_keys(self):
        return list(self.fields.keys()) + list(self.extras.keys())


def _mark_duplicate(parsed, name):
    if name not in parsed.duplicates:
        parsed.duplicates.append(name)


def parse_block(content):
    """dedent 后逐行扁平解析：markdown 列表内嵌的缩进 fenced 块与顶格块等价，
    嵌套子键与 extras 顶层键重复出现同样记入 duplicates（矛盾状态）。"""
    parsed = BlockParse()
    parent = None
    for line in textwrap.dedent(content).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        nested = _NESTED_KEY_RE.match(line)
        if nested and parent is not None:
            sub = parsed.sub.setdefault(parent, {})
            nested_key = nested.group(1).lower()
            if nested_key in sub:
                _mark_duplicate(parsed, parent + "." + nested_key)
            sub[nested_key] = nested.group(2)
            continue
        top = _TOP_KEY_RE.match(line)
        if top:
            key = top.group(2)
            parent = key.lower()
            if parent in CONTRACT_FIELDS:
                if parent in parsed.fields:
                    _mark_duplicate(parsed, parent)
                parsed.fields[parent] = top.group(3)
            else:
                if any(k.lower() == key.lower() for k in parsed.extras):
                    _mark_duplicate(parsed, key.lower())
                parsed.extras[key] = top.group(3)
    return parsed


def _condition_sources(parsed):
    """promoted 三条件的取值来源：顶层在档子键 + stable_rule_update 嵌套组
    （嵌套优先）；跨父键（如 metrics: 下）收割不计。"""
    merged = {k: v for k, v in parsed.extras.items() if k in DOCUMENTED_SUBFIELDS}
    merged.update(parsed.sub.get("stable_rule_update", {}))
    return merged


def _find_drift_key(parsed):
    """块内非合同、非在档子键的顶层键中首个命中漂移正则的键名。"""
    documented = set(DOCUMENTED_SUBFIELDS)
    for key in parsed.all_top_keys:
        if key in parsed.fields or key in documented:
            continue
        if _FIELD_DRIFT_KEY_RE.search(key):
            return key
    return None


def _to_int(raw):
    value = exact_value(raw)
    return int(value) if re.fullmatch(r"[0-9]+", value) else None


def check_content_gates(message):
    """两分支共享的内容门（逐条对齐既有 bash 判官，不得放松）。"""
    if "observation" not in message and "观察" not in message:
        return "缺少 observation"
    if "hypothesis" not in message and "假设" not in message:
        return "缺少 hypothesis"
    if "曝光量" not in message and "曝光" not in message:
        return "未披露曝光量缺口"
    if not _OPEN_RATE_RE.search(message):
        return "未处理打开率状态"
    if "stable_rule_update" not in message and "稳定规则" not in message:
        return "缺少稳定规则决策"
    if (
        "persistence" not in message
        and "不写入" not in message
        and "不写档" not in message
    ):
        return "缺少持久化状态"
    phrase = find_overclaim_phrase(message)
    if phrase:
        return "错误升级为因果规则：" + phrase
    return ""


def _decision_paragraph(message, index):
    """返回含最后一次决策标记的空行分段（三条件只在本段内提取）。"""
    start = 0
    for sep in _PARAGRAPH_SPLIT_RE.finditer(message):
        if sep.start() >= index:
            return message[start:sep.start()]
        start = sep.end()
    return message[start:]


def _condition_hit_counts(segment, found):
    """条件命中是否计入：命中起点前方 8 字符否定窗口（复用否定感知纪律，
    但数学否定形态不参与条件豁免——条件语境中 A != B 是比较不是条件否定）
    与前后未来时态窗口（前 8 / 后 12 字符）内的计划、排期、否定语义不计。"""
    if _negated_hit(segment, found.start(), markers=_PROSE_NEGATION_MARKERS_RE):
        return False
    prefix = segment[max(0, found.start() - _NEGATION_WINDOW):found.start()]
    suffix = segment[found.end():found.end() + _FUTURE_SUFFIX_WINDOW]
    return not (
        _PROMOTED_FUTURE_RE.search(prefix) or _PROMOTED_FUTURE_RE.search(suffix)
    )


def check_promoted_gate(message):
    """与围栏无关的 promoted 门：只武装 message 中**最后一次**决策标记
    （含去围栏 / 四反引号围栏 / 嵌套 status / 散文 / 粗体 / 等号形态）——
    更晚的本次决策（none/hypothesis 等）覆盖对历史 promoted 的引用文本；
    最后标记确为 promoted 时，三条件只从含该标记的空行分段内提取，条件
    命中受否定与未来时态窗口约束（详见 _condition_hit_counts）。"""
    markers = list(_PROMOTED_DECISION_RE.finditer(message))
    if not markers:
        return ""
    last = markers[-1]
    if last.group("value").lower() != "promoted":
        return ""
    paragraph = _decision_paragraph(message, last.start())
    unmet = []
    for name, pattern, minimum in (
        ("replications", _PROMOTED_CONDITIONS_RES[0][1], PROMOTED_MIN_REPLICATIONS),
        ("comparable_runs", _PROMOTED_CONDITIONS_RES[1][1], PROMOTED_MIN_COMPARABLE_RUNS),
    ):
        values = [
            int(found.group(1))
            for found in pattern.finditer(paragraph)
            if _condition_hit_counts(paragraph, found)
        ]
        if not values or max(values) < minimum:
            unmet.append("%s>=%d" % (name, minimum))
    if not any(
        _condition_hit_counts(paragraph, found)
        for found in _PROMOTED_COUNTERCHECKED_RE.finditer(paragraph)
    ):
        unmet.append("counterexamples_checked:true")
    if unmet:
        return "promoted 缺少升格条件（" + "；".join(unmet) + "）"
    return ""


def _check_single_block(parsed, message):
    """单个 canonical 块的全量结构化校验；返回空串表示该块通过。"""
    drift_key = _find_drift_key(parsed)
    if drift_key:
        return "canonical 状态块字段漂移：『" + drift_key + "』不是合同字段"

    if parsed.duplicates:
        return "canonical 状态块字段重复/矛盾状态：" + "、".join(parsed.duplicates)

    missing = [f for f in CONTRACT_FIELDS if f not in parsed.fields]
    if missing:
        return "canonical 状态块缺少字段：" + ", ".join(missing)
    empty = [
        f
        for f in CONTRACT_FIELDS
        if f != "stable_rule_update" and not exact_value(parsed.fields[f])
    ]
    if empty:
        return "canonical 状态块字段值为空：" + ", ".join(empty)

    rule_raw = exact_value(parsed.fields["stable_rule_update"])
    if not rule_raw:
        rule_raw = exact_value(parsed.sub.get("stable_rule_update", {}).get("status", ""))
    if not rule_raw:
        return "canonical 状态块字段值为空：stable_rule_update"
    rule_value = rule_raw.lower()
    if rule_value not in STABLE_RULE_ENUM:
        return (
            "stable_rule_update 值『"
            + rule_raw
            + "』不在枚举 "
            + "|".join(STABLE_RULE_ENUM)
            + " 内"
        )

    persistence_raw = exact_value(parsed.fields["persistence"])
    persistence_value = persistence_raw.lower()
    if persistence_value not in PERSISTENCE_VALUES and not (
        persistence_value.startswith("authorized:") and persistence_value[11:].strip()
    ):
        return (
            "persistence 值『"
            + persistence_raw
            + "』不在值域 not_run | authorized[:<path>] 内"
        )

    if rule_value == "promoted":
        signal = find_single_post_signal(message)
        if signal:
            return "promoted 与单篇表现冲突（检出信号：" + signal + "）"
        conditions = _condition_sources(parsed)
        replications = _to_int(conditions.get("replications", ""))
        comparable = _to_int(conditions.get("comparable_runs", ""))
        counterchecked = exact_value(conditions.get("counterexamples_checked", "")).lower()
        unmet = []
        if replications is None or replications < PROMOTED_MIN_REPLICATIONS:
            unmet.append("replications>=%d" % PROMOTED_MIN_REPLICATIONS)
        if comparable is None or comparable < PROMOTED_MIN_COMPARABLE_RUNS:
            unmet.append("comparable_runs>=%d" % PROMOTED_MIN_COMPARABLE_RUNS)
        if counterchecked not in ("true", "yes"):
            unmet.append("counterexamples_checked:true")
        if unmet:
            return "promoted 缺少升格条件（" + "；".join(unmet) + "）"

    return ""


def check_canonical_block(blocks, message):
    """canonical 分支的结构化校验：逐块校验所有含合同字段或漂移键的 yaml 块，
    任一块失败即拒绝；返回空串表示通过。"""
    parsed_blocks = [parse_block(block) for block in blocks]

    if not any(parsed.fields for parsed in parsed_blocks):
        return (
            "canonical 状态块零合同字段命中：fenced yaml 块在场但四个字段全部"
            "缺席，不允许降级回同义词分支拼凑通过"
        )

    for parsed in parsed_blocks:
        # 既无合同字段也无漂移键的附带块不参与合同校验
        if not parsed.fields and _find_drift_key(parsed) is None:
            continue
        reason = _check_single_block(parsed, message)
        if reason:
            return reason
    return ""


def contract_field_hits(message):
    """全 message 命中的合同字段键数（branch 标注的内容维度；大小写不敏感，
    混排 ``Stable_Rule_Update`` 等键名形态不漏计）。"""
    lowered = message.lower()
    return sum(1 for field in CONTRACT_FIELDS if field in lowered)


def judge(message):
    """返回 (exit_code, branch, reason)。branch: canonical | synonym。

    canonical 分支先报结构化拒绝原因（字段漂移/缺字段/枚举越界更精确），
    接受路径仍须结构化校验、promoted 门与共享内容门全部通过——两分支
    接受集不因报错顺序而放松。
    """
    blocks = extract_yaml_blocks(message)
    branch = "canonical" if blocks else "synonym"
    if branch == "canonical":
        reason = (
            check_canonical_block(blocks, message)
            or check_promoted_gate(message)
            or check_content_gates(message)
        )
    else:
        reason = check_promoted_gate(message) or check_content_gates(message)
    if reason:
        return 1, branch, reason
    return 0, branch, ""


def main():
    message = read_message()
    code, branch, reason = judge(message)
    # 分支标注恒输出（含拒绝路径），供 U12 判定线计数；contract_fields 维度
    # 补偿 branch 仅反映围栏表面形态的噪声
    print(
        "branch=%s;contract_fields=%d" % (branch, contract_field_hits(message)),
        file=sys.stderr,
    )
    if code:
        print(reason, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
