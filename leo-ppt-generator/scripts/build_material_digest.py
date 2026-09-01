#!/usr/bin/env python3
"""build_material_digest.py — 超长材料摘要生成（R-02）。

材料为整书/超长报告时，按与 deck 主题及大纲节标题的相关性抽取关键段落，
产出 ``content/material-digest.md``：**保留原文锚点（段落序号 ¶N）**，
母版制作只读摘要并按需回原文（引用级事实仍可回溯原文段落）。

抽取方法为确定性词频打分，不依赖 embedding / 模型：
  1. 材料按空行切段，过滤 <20 字的碎段（标题、列表头），段落序号即锚点；
  2. 主题词表：主题串的 CJK bigram + ASCII/数字 token（停用词过滤）；
  3. 大纲（可选）：解析节标题行（``#``/``-`` 开头）生成节词表，段落按
     节词命中数归入最高分节；
  4. 每段得分 = 主题词命中数 +（有大纲时）所属节词命中数；每节取
     得分 ≥1 的 top N 段（默认 3），无大纲时全局取 top K（默认 8），
     同分保持原文顺序（稳定排序）。

用法：
  python3 scripts/build_material_digest.py <材料.md> --topic "主题"
      [--outline outline-v1.md] [--output content/material-digest.md]
      [--per-section 3] [--top 8] [--json]
输出：digest markdown（或 --json 元数据）；退出码 0 成功 /
  1 零命中（主题与材料无重合，digest 仍落盘并注明） / 2 用法或读取错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Vocabularies and thresholds (edit here, not in detectors).
# ---------------------------------------------------------------------------

MIN_PARAGRAPH_CHARS = 20   # shorter blocks are headings/lists debris, skipped
MIN_SECTION_SCORE = 1      # paragraphs below this score are never collected

# Meta-narration ("this chapter introduces…") mentions topic words without
# carrying content; discount such paragraphs so substantive text wins.
META_NARRATION_RE = re.compile(
    r"本[节章].{0,6}(?:介绍|概述|回顾|总结)|行业现状|未涉及|(?:与|和)[^。，]{0,12}无关")
META_NARRATION_PENALTY = 2

STOPWORDS = {
    "的", "了", "和", "是", "在", "与", "及", "或", "等", "为", "对", "从",
    "被", "把", "向", "于", "中", "上", "下", "并", "其", "这", "那", "也",
    "都", "就", "会", "能", "要", "有", "个", "之", "以", "而", "则", "将",
    "该", "此", "各", "每", "如", "按", "由", "更", "很", "最", "不", "无",
    "一", "二", "三", "介绍", "概述", "章节", "内容", "我们", "可以",
}

CJK_BIGRAM_RE = re.compile(r"[一-龥]{2}")
ASCII_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{1,}|(?<!\d)\d{2,}(?!\d)")


def extract_terms(text: str) -> "dict[str, int]":
    """Deterministic keyword bag: CJK bigrams + ASCII tokens, stopword-filtered."""
    terms: dict[str, int] = {}
    for m in CJK_BIGRAM_RE.finditer(text):
        gram = m.group(0)
        if gram[0] in STOPWORDS or gram[1] in STOPWORDS:
            continue
        terms[gram] = terms.get(gram, 0) + 1
    for m in ASCII_TOKEN_RE.finditer(text):
        token = m.group(0).casefold()
        if token in STOPWORDS:
            continue
        terms[token] = terms.get(token, 0) + 1
    return terms


def count_hits(terms: "dict[str, int]", paragraph: str) -> int:
    """Weighted hit count of a term bag inside one paragraph (bigrams by
    substring count, ASCII tokens by regex to respect word boundaries)."""
    lowered = paragraph.casefold()
    hits = 0
    for term, weight in terms.items():
        if re.fullmatch(r"[一-龥]{2}", term):
            hits += lowered.count(term) * weight
        else:
            hits += len(re.findall(re.escape(term), lowered)) * weight
    return hits


def split_paragraphs(text: str) -> "list[tuple[int, str]]":
    """Split on blank lines; index (1-based) is the stable citation anchor."""
    blocks = re.split(r"\n\s*\n", text)
    return [(i, b.strip()) for i, b in enumerate(blocks, start=1)
            if len(re.sub(r"\s", "", b)) >= MIN_PARAGRAPH_CHARS]


def parse_outline_sections(outline_text: str) -> "list[tuple[str, dict[str, int]]]":
    """Section titles from markdown headings or `- ` agenda lines, each with
    its keyword bag."""
    sections = []
    for line in outline_text.splitlines():
        stripped = line.strip()
        m = re.match(r"^#{1,4}\s+(.+)$", stripped) or re.match(r"^[-*]\s*(.+)$", stripped)
        if not m:
            continue
        title = m.group(1).strip().strip("#*- ")
        if not title or len(title) < 2:
            continue
        sections.append((title, extract_terms(title)))
    return sections


def build_digest(paragraphs, topic_terms, sections, per_section, top):
    """Score, group and select paragraphs; returns (selected, meta).

    selected: list of dicts {anchor, section, score, text}; stable ordering by
    original anchor within each section keeps output deterministic.
    """
    scored = []
    for anchor, text in paragraphs:
        topic_score = count_hits(topic_terms, text)
        if META_NARRATION_RE.search(text):
            topic_score = max(0, topic_score - META_NARRATION_PENALTY)
        best_section, best_score = None, 0
        for title, terms in sections:
            s = count_hits(terms, text)
            if s > best_score:
                best_section, best_score = title, s
        section_score = best_score if best_section else 0
        total = topic_score + section_score
        if total >= MIN_SECTION_SCORE:
            scored.append({
                "anchor": anchor, "text": text,
                "section": best_section or "主题直取",
                "topic_score": topic_score, "section_score": section_score,
                "score": total,
            })
    if not sections:
        scored.sort(key=lambda e: (-e["score"], e["anchor"]))
        selected = sorted(scored[:top], key=lambda e: e["anchor"])
        return selected, {"mode": "topic-only", "considered": len(scored)}

    by_section: dict[str, list[dict]] = {}
    for entry in scored:
        by_section.setdefault(entry["section"], []).append(entry)
    selected = []
    for title, _ in sections:
        group = by_section.pop(title, [])
        group.sort(key=lambda e: (-e["score"], e["anchor"]))
        selected.extend(group[:per_section])
    # Paragraphs matching no outline section still compete for the topic slot.
    leftovers = [e for group in by_section.values() for e in group]
    leftovers.sort(key=lambda e: (-e["score"], e["anchor"]))
    topic_only = leftovers[:per_section]
    for entry in topic_only:
        entry["section"] = "主题直取"
    selected.extend(topic_only)
    selected.sort(key=lambda e: e["anchor"])
    return selected, {
        "mode": "outline-sectioned",
        "considered": len(scored),
        "sections": [t for t, _ in sections],
    }


def render_digest(material_name, topic, selected, total_paragraphs, meta):
    lines = [
        f"# 材料摘要（material digest）——{material_name}",
        "",
        f"- deck 主题：{topic}",
        f"- 材料段落数：{total_paragraphs}（≥{MIN_PARAGRAPH_CHARS} 字的空白分隔块；"
        "锚点 ¶N = 原文块序号）",
        f"- 收录段落：{len(selected)} / {total_paragraphs}；"
        f"抽取模式：{meta['mode']}（确定性词频打分，非 embedding）",
        "- 母版制作只读本摘要；引用级事实按锚点回原文核对，"
        "数字走数字登记表 source_ref。",
        "",
    ]
    if not selected:
        lines.append("（零命中：主题词与材料无重合——检查主题表述或改用全文）")
        lines.append("")
    current = None
    for entry in selected:
        if entry["section"] != current:
            current = entry["section"]
            lines.append(f"## {current}")
            lines.append("")
        lines.append(f"### ¶{entry['anchor']}（得分 {entry['score']}"
                     f" = 主题 {entry['topic_score']} + 节 {entry['section_score']}）")
        lines.append("")
        lines.append(entry["text"])
        lines.append("")
    collected = {e["anchor"] for e in selected}
    omitted = [i for i in range(1, total_paragraphs + 1) if i not in collected]
    lines.append("## 未收录段落（按需回原文）")
    lines.append("")
    lines.append("、".join(f"¶{i}" for i in omitted) if omitted else "（无）")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="超长材料摘要生成（R-02，确定性词频抽取，保留原文段落锚点）")
    parser.add_argument("material", help="材料 markdown 路径（整书/超长报告）")
    parser.add_argument("--topic", required=True, help="deck 主题（一句话）")
    parser.add_argument("--outline", default=None,
                        help="大纲 markdown 路径（可选，节标题参与分节抽取）")
    parser.add_argument("--output", default="content/material-digest.md",
                        help="digest 输出路径（默认 content/material-digest.md）")
    parser.add_argument("--per-section", type=int, default=3,
                        help="分节模式下每节收录段数上限（默认 3）")
    parser.add_argument("--top", type=int, default=8,
                        help="无大纲时全局收录段数上限（默认 8）")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 元数据而非 digest markdown")
    args = parser.parse_args(argv)

    material = Path(args.material)
    try:
        text = material.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: 无法读取材料 {material}: {exc}", file=sys.stderr)
        return 2
    if not text.strip():
        print(f"ERROR: 材料为空文件 {material}", file=sys.stderr)
        return 2

    outline_sections = []
    if args.outline:
        try:
            outline_sections = parse_outline_sections(
                Path(args.outline).read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"ERROR: 无法读取大纲 {args.outline}: {exc}", file=sys.stderr)
            return 2

    paragraphs = split_paragraphs(text)
    topic_terms = extract_terms(args.topic)
    selected, meta = build_digest(
        paragraphs, topic_terms, outline_sections,
        args.per_section, args.top)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_digest(
        material.name, args.topic, selected, len(paragraphs), meta),
        encoding="utf-8")

    exit_code = 0 if selected else 1
    if args.json:
        payload = {
            "material": str(material),
            "topic": args.topic,
            "paragraphs": len(paragraphs),
            "selected": [{"anchor": e["anchor"], "section": e["section"],
                          "score": e["score"]} for e in selected],
            "mode": meta["mode"],
            "output": str(output),
            "exit": exit_code,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        status = (f"收录 {len(selected)} 段 / {len(paragraphs)} 段"
                  if selected else "零命中——检查主题词或改用全文")
        print(f"DIGEST: {output.name}（{status}，模式 {meta['mode']}）")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
