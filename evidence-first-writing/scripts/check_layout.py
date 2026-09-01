#!/usr/bin/env python3
"""中文排版确定性检查器：检查 markdown 产出的排版合同可机械判定子集，只报线索，不改文件。

定位（evidence-first-writing 技能）：
- 排版合同（``references/layout-contract.md``）的 lint 实现；规约条款（标题不跳
  级、表头必含、px 阈值）不在本脚本机械判定范围，本文真值源为准。
- 六类规则：①CJK 标点半角混用——半角 `` , ; : ? ! . ( ) `` 前后紧邻 CJK 字符
  （汉字、全角形式、CJK 标点与弯引号）才报，避免 3.14、1,000、12:30、e.g. 等
  英文/数字语境误报；②callout（连续 ``> `` 行计一块）全文 >4 FAIL；③高亮标记
  ``==...==`` 全文 >5 FAIL；④加粗按段内 ``**…**`` 对计、每段 >2 FAIL（``***``
  不计为加粗对，列表标记内正常计）；⑤表格列按表头分隔行管道数换算（带首尾
  边框管道时列数 = 管道数 - 1）、>4 列 FAIL；
  ⑥连续 3 段纯文本同构（无列表/引用/表格/代码穿插）WARN。
- 保护区豁免六类：fenced code、行内 code、URL、链接段、YAML front-matter、
  HTML 标签。mask 语义与 ``check_prose.py`` 的 ``mask_non_prose`` 一致（同语义
  独立实现，不 import——check_prose 是 vendored 契约，排版规则不得混入）。
- 每条线索一行：``级别 | 规则 | 位置 | 摘录 | 建议动作``；级别 FAIL/WARN，位置
  为 ``L<行号>`` 或 ``全文``。输出是排版诊断线索，非交付门禁。
- 退出码：0 干净；1 存在失败级；2 仅警告级；3 输入或参数错误（缺参、文件不存
  在、空文件）。不设汉字守卫：无汉字时规则照跑、语义不变（区别于 check_prose
  的"无汉字退出 3"口径）。
- 跨宿主调用：先将 ``EVIDENCE_FIRST_WRITING_SKILL_DIR`` 指向已加载 SKILL.md
  所在目录，再运行
  ``python3 "$EVIDENCE_FIRST_WRITING_SKILL_DIR/scripts/check_layout.py" <file.md>``；
  也支持 ``-`` 从标准输入读取。仅标准库。

来源：xiaohu-wechat-format 标点门禁与密度配额机制蓝本（README 声明 MIT、仓库
无 LICENSE 文件，补证失败——机制吸收、文本零复制）；autocorrect（MIT）全角/
半角标点规则口径；快照 2026-08-31。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


CALLOUT_LIMIT = 4
HIGHLIGHT_LIMIT = 5
BOLD_LIMIT = 2
TABLE_COLUMN_LIMIT = 4
RHYTHM_STREAK = 3
PUNCT_DISPLAY_CAP = 12

HALFWIDTH_PUNCT_RE = re.compile(r"[,.;:?!()]")
# "紧邻 CJK 字符"的语境判定：汉字、弯引号、CJK 符号标点、全角形式。
CJK_CONTEXT_RE = re.compile(r"[\u4e00-\u9fff\u2018-\u201d\u3000-\u303f\uff00-\uffef]")
HIGHLIGHT_RE = re.compile(r"==[^=\n]+==")
BOLD_RE = re.compile(r"(?<!\*)\*\*[^*]+\*\*(?!\*)")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
QUOTE_RE = re.compile(r"^\s{0,3}>")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}(?:\s|$)")
LIST_MARKER_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.、)])\s+")
HR_RE = re.compile(r"^\s{0,3}(?:[-*_=]+\s*)+$")
SEPARATOR_CHARS_RE = re.compile(r"^[\s|:-]+$")


@dataclass
class Finding:
    """一条诊断线索：级别、规则、原文位置、命中片段与建议动作。"""

    level: str  # "FAIL" | "WARN"
    rule: str
    position: int | None  # 原文偏移；None 表示全文级统计
    excerpt: str
    action: str


@dataclass
class Chunk:
    """空行分隔的块（fence 内部不切分），带原文偏移与结构分类。"""

    start: int
    end: int
    kind: str  # code | quote | table | heading | list | hr | plain


def han_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def excerpt(value: str, width: int = 72) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= width else value[: width - 1] + "…"


def mask_non_prose(text: str) -> str:
    """屏蔽代码、网址和机器元数据，同时保留字符位置与换行。

    语义与 check_prose.mask_non_prose 一致（独立实现，不 import vendored 契约）：
    YAML front-matter、fenced code、行内 code、链接段、URL、HTML 标签六类。
    """

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


def line_spans(text: str) -> list[tuple[int, str]]:
    spans = []
    offset = 0
    for line in text.split("\n"):
        spans.append((offset, line))
        offset += len(line) + 1
    return spans


def is_separator_row(line: str) -> bool:
    return bool(SEPARATOR_CHARS_RE.match(line)) and "-" in line and "|" in line


def separator_columns(line: str) -> int:
    """由表头分隔行的管道数换算列数，按首尾边框管道形态修正。

    合同配额是"表格 ≤4 列"（layout-contract.md 第 5 条）；管道只是计数手段。
    双边框 ``|---|---|---|---|`` 为 5 管 4 列；半边框 ``|---|---|---|---`` 为
    4 管 4 列；完全无框 ``---|---|---|---`` 为 4 管 5 列。统一公式：
    列数 = 管道数 + 1 - 首管(0/1) - 尾管(0/1)，下限 clamp 到 1。
    """
    pipes = line.count("|")
    stripped = line.strip()
    columns = pipes + 1 - stripped.startswith("|") - stripped.endswith("|")
    return max(columns, 1)


def classify_chunk(lines: list[str]) -> str:
    if any(FENCE_RE.match(line) for line in lines):
        return "code"
    non_blank = [line for line in lines if line.strip()]
    if not non_blank:
        return "plain"
    if all(QUOTE_RE.match(line) for line in non_blank):
        return "quote"
    if any(is_separator_row(line) for line in lines):
        return "table"
    if HEADING_RE.match(non_blank[0]):
        return "heading"
    if any(LIST_MARKER_RE.match(line) for line in non_blank):
        return "list"
    if len(non_blank) == 1 and HR_RE.match(non_blank[0]):
        return "hr"
    return "plain"


def iter_chunks(text: str) -> list[Chunk]:
    """按空行分块；fence 内部的空行不切分，保证代码块完整成块。"""
    chunks: list[Chunk] = []
    current: list[tuple[int, str]] = []
    in_fence = False
    fence_char = ""
    for offset, line in line_spans(text):
        fence = FENCE_RE.match(line)
        if not in_fence and not line.strip():
            if current:
                chunks.append(_build_chunk(current))
                current = []
            continue
        current.append((offset, line))
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence = True
                fence_char = marker
            elif marker == fence_char:
                in_fence = False
    if current:
        chunks.append(_build_chunk(current))
    return chunks


def _build_chunk(lines: list[tuple[int, str]]) -> Chunk:
    start = lines[0][0]
    last_offset, last_line = lines[-1]
    return Chunk(start, last_offset + len(last_line), classify_chunk([line for _, line in lines]))


def quote_runs(text: str) -> list[int]:
    """连续 ``> `` 行计一块，返回每块的起始偏移。"""
    runs: list[int] = []
    start: int | None = None
    for offset, line in line_spans(text):
        if QUOTE_RE.match(line):
            if start is None:
                start = offset
        else:
            if start is not None:
                runs.append(start)
                start = None
    if start is not None:
        runs.append(start)
    return runs


def halfwidth_punct_hits(masked: str) -> list[int]:
    """半角标点前后紧邻 CJK 字符的位置（英文/数字语境不报）。"""
    hits = []
    for match in HALFWIDTH_PUNCT_RE.finditer(masked):
        index = match.start()
        before = masked[index - 1] if index > 0 else ""
        after = masked[index + 1] if index + 1 < len(masked) else ""
        if CJK_CONTEXT_RE.match(before) or CJK_CONTEXT_RE.match(after):
            hits.append(index)
    return hits


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
    return f"{finding.level} | {finding.rule} | {location} | {snippet} | {finding.action}"


class LayoutArgumentParser(argparse.ArgumentParser):
    # 保留退出码 2 给"仅警告级"，参数错误改用 3，与 docstring 契约一致。
    def error(self, message: str):
        self.print_usage(sys.stderr)
        print(f"参数错误：{message}", file=sys.stderr)
        raise SystemExit(3)


def main() -> int:
    parser = LayoutArgumentParser(
        description="检查 markdown 产出的排版合同可机械判定子集，输出诊断线索（非交付门禁）"
    )
    parser.add_argument("path", help="Markdown 或文本文件路径。使用 - 从标准输入读取")
    args = parser.parse_args()

    try:
        text = read_text(args.path)
    except (OSError, UnicodeError) as error:
        print(f"无法读取稿件。{error}", file=sys.stderr)
        return 3
    if not text.strip():
        print("文件为空。", file=sys.stderr)
        return 3

    masked = mask_non_prose(text)
    chunks = iter_chunks(text)
    findings: list[Finding] = []

    punct_hits = halfwidth_punct_hits(masked)
    for position in punct_hits[:PUNCT_DISPLAY_CAP]:
        findings.append(
            Finding(
                "FAIL",
                "halfwidth-punct 半角标点混用",
                position,
                masked[max(0, position - 8) : position + 10],
                "改为对应全角标点（，。；：？！（）），英文或数字语境可保留",
            )
        )

    # 传入 masked 文本：fenced code 与 front-matter 已被等长空格替换，
    # 围栏内的 "> " 示例行不计 callout（评审 P1 修复——真实 callout 的
    # "> " 不在任何保护区，原位保留；换行与偏移不变，行号语义不受影响）。
    callouts = quote_runs(masked)
    if len(callouts) > CALLOUT_LIMIT:
        findings.append(
            Finding(
                "FAIL",
                "callout-quota 引用块超额",
                callouts[0],
                f"callout 共 {len(callouts)} 块（上限 {CALLOUT_LIMIT}）",
                "删减或合并引用块，全文保留 ≤4 块",
            )
        )

    highlights = list(HIGHLIGHT_RE.finditer(masked))
    if len(highlights) > HIGHLIGHT_LIMIT:
        findings.append(
            Finding(
                "FAIL",
                "highlight-quota 高亮标记超额",
                highlights[0].start(),
                f"高亮标记共 {len(highlights)} 处（上限 {HIGHLIGHT_LIMIT}）",
                "删减高亮，全文保留 ≤5 处；==…== 属渲染器依赖扩展，发布前核对渲染器支持",
            )
        )

    bold_over: list[Chunk] = []
    for chunk in chunks:
        pairs = list(BOLD_RE.finditer(masked[chunk.start : chunk.end]))
        if len(pairs) > BOLD_LIMIT:
            bold_over.append(chunk)
            findings.append(
                Finding(
                    "FAIL",
                    "bold-quota 加粗超额",
                    chunk.start + pairs[0].start(),
                    f"本段加粗 {len(pairs)} 对（上限 {BOLD_LIMIT}）",
                    "拆分段落或删减加粗，每段保留 ≤2 对",
                )
            )

    table_over: list[int] = []
    for offset, line in line_spans(masked):
        if not is_separator_row(line):
            continue
        columns = separator_columns(line)
        if columns > TABLE_COLUMN_LIMIT:
            table_over.append(offset)
            findings.append(
                Finding(
                    "FAIL",
                    "table-columns 表格列数超额",
                    offset,
                    f"{columns} 列：{line.strip()}",
                    "拆表或改列表，表格保留 ≤4 列",
                )
            )

    rhythm_runs: list[list[Chunk]] = []
    streak: list[Chunk] = []
    for chunk in chunks:
        if chunk.kind == "plain" and masked[chunk.start : chunk.end].strip():
            streak.append(chunk)
        else:
            if len(streak) >= RHYTHM_STREAK:
                rhythm_runs.append(streak)
            streak = []
    if len(streak) >= RHYTHM_STREAK:
        rhythm_runs.append(streak)
    for run in rhythm_runs:
        findings.append(
            Finding(
                "WARN",
                "paragraph-rhythm 连续同构段落",
                run[0].start,
                f"连续 {len(run)} 段纯文本，无列表/引用/表格/代码穿插",
                "插入列表、引用或表格等结构变化，或调整长短段节奏",
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

    print(f"# 汉字数 {han_count(masked)}")
    for finding in findings:
        print(format_finding(text, finding))
    if not findings:
        print("# 未发现这份检查器覆盖的问题。")
    print(
        f"# 统计：失败级 {fail_count} 条，警告级 {warn_count} 条；"
        f"半角标点混用 {len(punct_hits)}，callout {len(callouts)} 块（上限 {CALLOUT_LIMIT}），"
        f"高亮 {len(highlights)} 处（上限 {HIGHLIGHT_LIMIT}），加粗超段 {len(bold_over)}，"
        f"表格超列 {len(table_over)}，同构段组 {len(rhythm_runs)}"
    )
    print("# 退出码：0=干净，1=存在失败级，2=仅警告级，3=输入或参数错误。")
    print("# 以上为排版诊断线索，非交付门禁；规则真值源见 references/layout-contract.md，渠道或用户给出的排版规范优先。")

    if fail_count:
        return 1
    if warn_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
