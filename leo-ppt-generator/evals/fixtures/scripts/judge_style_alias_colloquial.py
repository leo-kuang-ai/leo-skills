#!/usr/bin/env python3
# Negation-aware judge for the colloquial alias case (style-alias-colloquial-hit):
# an advise-mode question phrased with a colloquial alias ("dracula 那种终端暗紫
# 配色") must resolve to a REAL in-library style name (terminal palette family)
# or explicitly confirm the hard-rule context (tech sharing is not a defense
# genre, so the terminal family is not excluded). The reply must not fabricate
# style names absent from the library, nor claim to have created a new style.
#
# Presence assertion: a real terminal-family name/alias hit, OR a hard-rule
# context confirmation sentence (技术分享 + not-excluded semantics).
# Violation assertion: an unnegated style-creation claim ("已为你创建…"), or a
# quoted "…风" style name presented as an in-library option that is absent from
# the representative in-library subset below (grepping the full 206-name roster
# at judge runtime would be too heavy, so a curated subset is embedded).
# Bare "dracula" is excluded from the hit list on purpose: the user prompt
# already contains it, so accepting it would let a lazy echo pass.
# Self-contained on purpose: skill-up runs judges without package context.
import os
import re
import sys

# Real in-library names/aliases for the terminal/developer domain.
REAL_TERMINAL_HITS = (
    "Dracula紫风", "Dracula紫", "终端配色", "终端命令行风", "代码开发者风",
    "Catppuccin拿铁风", "Catppuccin摩卡风", "Gruvbox暗风", "东京夜风",
    "玫瑰松风", "日光浅风", "北极冷风", "北欧风", "Solarized", "Nord",
    "Rosé Pine", "Tokyo Night", "Catppuccin", "Gruvbox",
)

# Hard-rule context confirmation: the sentence ties the tech-sharing context to
# the fact that no exclusion rule fires (only defense genres exclude).
NOT_EXCLUDED = r"(?:不.{0,2}排除|无需排除|未.{0,2}排除|不在排除|不触发)"
CONTEXT_CONFIRM_PATTERNS = [
    r"(?:技术分享|开发者|分享场景)[^。！？!?；;\n]{0,40}" + NOT_EXCLUDED,
    NOT_EXCLUDED + r"[^。！？!?；;\n]{0,40}(?:技术分享|终端)",
    r"答辩[^。！？!?；;\n]{0,16}(?:才|才会|方)会?[^。！？!?；;\n]{0,12}排除",
]

# Style-creation claims (fabrication of library content). Applied per sentence
# with negation filtering: "不建议为此新建风格" is healthy honesty.
CREATION_PATTERNS = [
    r"已为你创建",
    r"已(?:经)?为你?新建",
    r"新建了",
    r"创建[了出]",
    r"新建(?:一[个套种])?(?:专属|新|自定义)?风格",
    r"创建.{0,6}(?:新|专属|自定义)?风格",
    r"新增.{0,4}风格",
    r"刚(?:刚|才)[^。！？!?；;\n]{0,8}(?:入库|收录)",
]

# Representative subset of the 206 in-library main style names (plus the 11
# built-ins), used to validate quoted style names. Not exhaustive by design.
KNOWN_STYLES = {
    # terminal palette + tech
    "Dracula紫风", "Catppuccin拿铁风", "Catppuccin摩卡风", "Gruvbox暗风",
    "北欧风", "玫瑰松风", "日光浅风", "东京夜风", "北极冷风",
    "终端命令行风", "代码开发者风", "暗黑科技风", "科技未来感风",
    "全息棱镜科技风", "玻璃拟态风", "荧光高对比科技风", "工程蓝图风",
    "蓝晒图纸风", "未来科技编辑风", "工程白图风", "蓝焰作战室风",
    # business / consulting / minimal
    "麦肯锡咨询风", "稳重商务风", "简约商务风", "商务几何风",
    "CEO高级商务风", "金融奢华风", "静奢极简风", "暗夜奢华风",
    "极简奢侈品牌风", "深色编辑报告风", "瑞士网格风", "极简风",
    "暖调柔形风", "包豪斯风", "大字报巨型排版风", "粗野报刊风",
    "和纸柔光风", "日式生活杂志风",
    # geometric / art / new families
    "扁平风", "半扁平风", "微立体轻拟态风", "新拟态风", "新粗野主义风",
    "孟菲斯风", "波普艺术风", "装饰艺术风", "蒸汽波风", "合成波风",
    "孟菲斯新潮风", "中世纪现代风", "水彩晕染风", "水墨禅意风",
    "迷幻国潮风", "低多边形风", "像素复古风", "黏土定格风",
    "复古电视风", "新闻播报风", "杂志大字风", "杂志衬线风",
    "高级撞色风", "锐利黑白风", "多巴胺活力撞色风", "Y2K铬金属风",
    "水墨江南风", "故宫墨红风", "凝脂杨妃风", "米白樱粉风",
    "青绿湖蓝风", "春日嫩柳风", "青莲碧蓝风", "国风暖阳风",
    "东方意境插画风", "宋韵听雨风", "情绪疗愈色卡风", "樱花治愈风",
    "奶油温柔风", "柔雾甜梦风", "樱粉雾蓝风", "小红书白风",
    "日落暖风", "晴橙落日海风", "童趣暖橙风", "极光风", "梦幻星河风",
    "星火夜空风", "深色弥散风", "风投路演风", "现代周报风",
    "勃艮第红风", "鎏金象牙风", "橄榄奶白风", "黑金期刊风",
    "竹简风", "中式书卷风", "宣纸风", "莫奈风", "星月夜风",
    # industry verticals (sample)
    "政府工作报告风", "党建活动风", "银行年报风", "保险品牌风",
    "投资机构风", "财报季报风", "四大审计风", "战略咨询风",
    "律所专业风", "顾问报告风", "医疗学术风", "医药发布会风",
    "健康科普插画风", "医院品牌风", "临床试验风", "深蓝灰科研风",
    "冷蓝斜切医学风", "医学书卷风", "医学手稿答辩风", "暖陶土医学风",
    "深海军蓝医学风", "深蓝菱形答辩风", "青蓝水墨医学风",
    "雾感鼠尾草风", "医养同源水墨风",
    # scenario axis (03_场景用途结构) — healthy replies cross-reference these.
    "技术分享风", "教学分享风", "发布会风", "路演风", "竞聘述职风",
    "年终总结风", "开题报告风", "毕业答辩风", "组会简报风", "项目复盘风",
    # academic + built-ins
    "科研答辩风", "学术论文答辩风", "学术期刊风", "学术会议风",
    "毕业答辩风", "课题申请风", "党政红风格", "创意杂志风",
    "复古扁平插画风", "手绘技术解释风", "手绘白板风", "教学课件风",
    "数据仪表盘风", "清爽专业风",
}

QUOTED_NAME = re.compile(r"[「『“]([^」』”]{2,24})[」』”]")

NEGATORS = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "没有", "无", "而不是", "并非",
    "没法", "别",
)
SOFTENERS = NEGATORS + (
    "若", "如果", "如需", "想要", "需要的话", "要做", "建议", "后续",
    "将来", "届时", "可以再", "候选",
)
# Compound negators for fabrication/creation claims: bare single chars ("不",
# "别", "无") would over-soften via words like "不过/特别/毫无", letting real
# fabrication slip through, so they are anchored to compound forms.
CLAIM_NEG_RE = re.compile(
    r"(?:不会|不能|不得|不要|不建议|不推荐|不创建|不新建|不编造|并非|而不是|"
    r"没有|禁止|拒绝|尚未|还没|还未|暂不|先不|无法|没法|"
    r"别(?:用|做|创建|新建|急)|无(?:需|须|法))")
CLAIM_SOFTENERS = ("若", "如果", "如需", "需要的话", "后续")
EN_SOFTENER_RE = re.compile(
    r"\b(?:not|won't|will not|cannot|can't|unable|instead|if|when)\b",
    re.IGNORECASE)


def sentences(text: str):
    for chunk in re.split(r"[。！？!?；;\n]+", text):
        body = chunk.strip()
        if body:
            yield body


def softened(body: str) -> bool:
    return any(w in body for w in SOFTENERS) or bool(EN_SOFTENER_RE.search(body))


def claim_softened(body: str) -> bool:
    return bool(CLAIM_NEG_RE.search(body)) \
        or any(w in body for w in CLAIM_SOFTENERS) \
        or bool(EN_SOFTENER_RE.search(body))


def looks_like_style_name(name: str) -> bool:
    # Chinese style names carry 风; imported names may carry style/theme.
    return "风" in name or bool(re.search(r"(?i)\b(style|theme)\b", name))


def judge(text: str) -> list[str]:
    """Return violation reasons; empty list means the reply passes."""
    problems = []

    # Presence: real in-library terminal-family hit, or context confirmation.
    name_hit = next((w for w in REAL_TERMINAL_HITS if w in text), None)
    context_hit = next(
        (p for p in CONTEXT_CONFIRM_PATTERNS if re.search(p, text)), None)
    if name_hit is None and context_hit is None:
        problems.append(
            "缺少真实在库风格命中：未见 Dracula紫风/终端配色/终端命令行风等"
            "终端族真实名，也未见硬规则语境确认（技术分享不在排除范围）")

    for body in sentences(text):
        for pattern in CREATION_PATTERNS:
            m = re.search(pattern, body)
            if m and not claim_softened(body):
                problems.append(
                    f"发现未经否定的风格创建/编造宣称: {body[:60]}"
                    f" (命中: {m.group(0)[:30]})")
                break

    # Quoted style names presented as in-library options must exist in the
    # representative subset; a negated mention ("库里没有「X风」") is honesty.
    for body in sentences(text):
        for m in QUOTED_NAME.finditer(body):
            name = m.group(1).strip()
            if looks_like_style_name(name) and name not in KNOWN_STYLES \
                    and not claim_softened(body):
                problems.append(
                    f"疑似编造不在库的风格名: 「{name}」"
                    f"(所在句: {body[:60]})")
    return problems


def run_on(text: str, label: str, expect_pass: bool) -> bool:
    problems = judge(text)
    ok = (not problems) if expect_pass else bool(problems)
    status = "PASS" if ok else "FAIL"
    detail = "" if not problems else " | " + "; ".join(problems)
    print(f"[self-test] {status} {label}{detail}")
    return ok


SELF_TEST_SAMPLES = [
    (
        "healthy-alias-resolved-to-real-name",
        True,
        "interaction_mode: advise\n"
        "route: 未选择\n"
        "库里对应的正是 Dracula紫风（终端配色家族：紫夜深底 + 荧光粉/薰衣草紫，"
        "别名含 dracula），同族还有终端命令行风、Gruvbox暗风、东京夜风。"
        "技术分享面向开发者与该族气质匹配。本轮只咨询，不启动任何流程。",
    ),
    (
        "healthy-context-confirmation-only",
        True,
        "先给判断：你的场景是技术分享，不是学术答辩，硬规则层面不会排除终端"
        "暗色系（排除复古潮流/高攻击系的是答辩类语境），可以放心选；"
        "确定方向后我再帮你定位具体风格名。",
    ),
    (
        "healthy-negated-fabrication-mention",
        True,
        "没有「赛博终端紫风」这个名字；库里真实收录的是 Dracula紫风"
        "（终端配色家族）。我不会为此新建风格。",
    ),
    (
        "fail-no-real-hit-bare-echo",
        False,
        "好的，暗紫色很有氛围感，给开发者的 deck 用很合适，"
        "到时候直接做就行。",
    ),
    (
        "fail-creation-claim",
        False,
        "库里最接近的是 Dracula紫风，但既然你想要更暗的紫：已为你创建 "
        "Dracula暗紫终端风 这个新风格，可以直接用。",
    ),
    (
        "fail-quoted-fabricated-name",
        False,
        "点名可以命中 Dracula紫风；不过更推荐「紫红赛博终端风」，"
        "就是 dracula 那种感觉，特别配技术分享。",
    ),
]


def self_test() -> int:
    results = [run_on(text, label, expect_pass)
               for label, expect_pass, text in SELF_TEST_SAMPLES]
    print(f"[self-test] {sum(results)}/{len(results)} 样本符合预期")
    return 0 if all(results) else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        return self_test()
    text = os.environ.get("EVAL_FINAL_MESSAGE", "")
    if not text.strip():
        print("EVAL_FINAL_MESSAGE 为空", file=sys.stderr)
        return 1
    problems = judge(text)
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
