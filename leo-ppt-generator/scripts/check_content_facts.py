#!/usr/bin/env python3
"""check_content_facts.py — 内容核查官（R-06）：母版数字断言与材料回读比对。

上游依据：gpt-researcher multi_agents/agents/fact_checker.py（对照
research_data 审 draft、fact_check_revision_count 有界修订环，
orchestrator._route_fact_check 超限优雅放行而非死循环）。本脚本把该环
落到 leo 母版层：母版冻结后、派发前，抽取标题与要点行的数字断言，
与材料文件（或 research-pack.md）文本回读比对。

比对口径（确定性，纯 stdlib）：
  - 抽取范围：每页 `- 标题：` 行与要点行（剔除 备注/视觉行/argument_role/
    数字登记表 等非断言行；剔除「要点 N」序号与「见第 X 页 / 见 SX」
    交叉引用；【…】机器标记与 [src/round/note:…] 方括号字段不计数字）；
  - 格式容忍：千分位（1,234 ↔ 1234）、百分号（18% ↔ 18 % ↔ 百分之18）、
    万/千万/百万/亿/万亿 单位换算（1.24亿 ↔ 12,400万，Decimal 精确）、
    千分号（5‰ ↔ 0.5%）；
  - 标注豁免：行内带 估算/示意/用户确认 短标的要点不比对（估算与口述
    数据本就不出自材料）；引用级与无标注数字照常比对；
  - 年份豁免：四位 19xx/20xx 且无单位/百分号后缀的 token 视为年份，
    不计入断言（「2026 年市场回顾」，与 check_deck_prose 族 i 同口径）；
  - 差异 = 母版数字的规范化键在全部材料的数字键集合中未出现。

有界 2 轮（re-run-after-fix 语义，随文本与 --json 输出一并给出）：
差异清单返母版修复（改数 / 补出处 / 降级标注）后重跑本脚本；第 2 轮
仍有差异不再返工——逐项向用户确认或降级 unknown。

用法：python3 check_content_facts.py <deck-master.md> <material.md> [more.md ...]
                                       [--json]
退出码：0 无差异；1 有差异；2 用法错误 / 文件缺失或不可读 / 母版无任何页块。
"""
import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

PAGE_RE = re.compile(r"^##\s+(S(\d+)|附)[^\n]*$")
TITLE_RE = re.compile(r"[-•]\s*标题[：:]\s*(.+)")
POINT_LINE_RE = re.compile(r"^\s*(?:[-•]|\d+\.|\d+、)\s*(.+)$")
NON_ASSERT = ("标题", "备注", "视觉行", "argument_role", "数字登记表")
POINT_LABEL_RE = re.compile(r"^要点\s*\d+\s*[：:]\s*")

NUM_TOKEN_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(万亿|千万|百万|亿|万|%|‰)?")
PCT_CN_RE = re.compile(r"百分之\s*(\d+(?:\.\d+)?)")
MAGNITUDE = {"万": 10 ** 4, "亿": 10 ** 8, "千万": 10 ** 7,
             "百万": 10 ** 6, "万亿": 10 ** 12}
# Same year exemption as check_deck_prose family i: a bare 19xx/20xx token
# with no unit / percent suffix reads as a year ("2026 年市场回顾"), not an
# assertion number that must trace back to materials.
YEAR_LIKE_RE = re.compile(r"^(?:19|20)\d{2}$")

TIER_MARK_RE = re.compile(
    r"[【（(]\s*(用户确认|引用|估算|示意)(?:\s*[|｜][^】）)]*)?\s*[】）)]")
EXEMPT_TIERS = ("估算", "示意", "用户确认")
METADATA_SQ_RE = re.compile(r"\[\s*(?:src|round|note)\s*[：:][^\]]*\]")
CROSSREF_RE = re.compile(r"见[第附]?\s*\S{1,4}?\s*页|见\s*S\d+")

BOUNDED_ROUNDS = 2
RE_RUN_NOTE = (
    "RE-RUN-AFTER-FIX: 差异清单返母版修复（改数/补出处/降级标注）后重跑；"
    f"有界 {BOUNDED_ROUNDS} 轮——第 {BOUNDED_ROUNDS} 轮仍有差异不再返工，"
    "逐项向用户确认或降级 unknown。")


def normalize_number(num_str, unit):
    """Canonical key for a numeric token; Decimal keeps 万/亿 conversion exact
    (numerically equal Decimals share hash, so set membership is stable)."""
    value = Decimal(num_str.replace(",", ""))
    if unit == "%":
        return ("pct", value)
    if unit == "‰":
        return ("pct", value / Decimal(10))
    if unit:
        return ("num", value * MAGNITUDE[unit])
    return ("num", value)


def strip_metadata(line):
    """Remove cross-refs and machine marks so their digits never count."""
    text = CROSSREF_RE.sub(" ", line)
    text = METADATA_SQ_RE.sub(" ", text)
    text = re.sub(r"【[^】]*】", " ", text)
    text = TIER_MARK_RE.sub(" ", text)
    return text


def extract_number_keys(line):
    """Return [(display_text, canonical_key)] for one assertion line."""
    text = strip_metadata(line)
    keys = []
    for m in NUM_TOKEN_RE.finditer(text):
        if m.group(2) is None and YEAR_LIKE_RE.fullmatch(
                m.group(1).replace(",", "")):
            continue  # bare 19xx/20xx year, not a metric to reconcile
        display = "".join(m.group(0).split())  # "1.35 亿" → "1.35亿"
        keys.append((display, normalize_number(m.group(1), m.group(2))))
    for m in PCT_CN_RE.finditer(text):
        keys.append(("".join(m.group(0).split()),
                     ("pct", Decimal(m.group(1)))))
    return keys


def is_exempt(content):
    """估算/示意/用户确认-marked bullets are not expected to come from
    materials, so their numbers are skipped entirely."""
    return any(t in TIER_MARK_RE.findall(content) for t in EXEMPT_TIERS)


def iter_assertion_lines(text):
    """Yield (page, line_no, content) for title and bullet lines per page."""
    page = "全 deck"
    for line_no, raw in enumerate(text.splitlines(), start=1):
        header = PAGE_RE.match(raw)
        if header:
            page = header.group(0).lstrip("#").strip()
            continue
        title = TITLE_RE.search(raw)
        if title:
            yield page, line_no, title.group(1)
            continue
        m = POINT_LINE_RE.match(raw)
        if not m:
            continue
        content = m.group(1)
        if any(k in content for k in NON_ASSERT):
            continue
        yield page, line_no, POINT_LABEL_RE.sub("", content)


def material_number_keys(paths):
    keys = set()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for m in NUM_TOKEN_RE.finditer(text):
            keys.add(normalize_number(m.group(1), m.group(2)))
        for m in PCT_CN_RE.finditer(text):
            keys.add(("pct", Decimal(m.group(1))))
    return keys


def check(master_text, material_keys):
    """Compare master numeric assertions against material keys; deterministic."""
    diffs = []
    assertions = 0
    numbers = 0
    tier_exempt = 0
    for page, line_no, content in iter_assertion_lines(master_text):
        assertions += 1
        if is_exempt(content):
            tier_exempt += 1
            continue
        for display, key in extract_number_keys(content):
            numbers += 1
            if key not in material_keys:
                diffs.append({
                    "page": page,
                    "line": line_no,
                    "snippet": content.strip()[:60],
                    "value": display,
                })
    return {
        "assertions": assertions,
        "numbers": numbers,
        "tier_exempt": tier_exempt,
        "diffs": diffs,
    }


def render_text(result):
    lines = [
        (f"CONTENT-FACTS: master={result['master']} "
         f"materials={len(result['materials'])} "
         f"assertions={result['assertions']} numbers={result['numbers']} "
         f"tier_exempt={result['tier_exempt']}"),
    ]
    if result["diffs"]:
        lines.append(f"DIFF: {len(result['diffs'])} 个数字未在材料中回读到")
        for d in result["diffs"]:
            lines.append(f"  [{d['page']} 第{d['line']}行] "
                         f"「{d['snippet']}」 → {d['value']}")
    else:
        lines.append("PASS: 全部数字断言均可在材料中回读")
    lines.append(RE_RUN_NOTE)
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="内容核查官：母版数字断言与材料回读比对（R-06）")
    ap.add_argument("master", help="deck 母版 markdown 路径")
    ap.add_argument("materials", nargs="+",
                    help="材料文件（一个或多个，含 research-pack.md）")
    ap.add_argument("--json", action="store_true",
                    help="机读 JSON 输出（差异清单同构）")
    args = ap.parse_args(argv)

    master_path = Path(args.master)
    if not master_path.is_file():
        print(f"FAIL: 母版文件不存在或不可读: {master_path}", file=sys.stderr)
        return 2
    material_paths = []
    for raw in args.materials:
        p = Path(raw)
        if not p.is_file():
            print(f"FAIL: 材料文件不存在或不可读: {p}", file=sys.stderr)
            return 2
        material_paths.append(p)

    try:
        master_text = master_path.read_text(encoding="utf-8")
        material_keys = material_number_keys(material_paths)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"FAIL: 读取失败: {exc}", file=sys.stderr)
        return 2

    # Same family semantics as check_deck_prose / check_master_contract: a
    # master without a single page block is an unusable input, not a clean
    # zero-assertion PASS. PAGE_RE anchors per line (iter_assertion_lines
    # semantics), so check line by line.
    if not any(PAGE_RE.match(line) for line in master_text.splitlines()):
        print("FAIL: 母版解析失败：未发现任何页（## S<N> / ## 附 均无命中）",
              file=sys.stderr)
        return 2

    result = check(master_text, material_keys)
    result["master"] = str(master_path)
    result["materials"] = [str(p) for p in material_paths]
    result["bounded_rounds"] = BOUNDED_ROUNDS
    result["re_run_after_fix"] = RE_RUN_NOTE

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(result))
    return 1 if result["diffs"] else 0


if __name__ == "__main__":
    sys.exit(main())
