#!/usr/bin/env python3
"""137 brief 家族分布实测（R-66 前置盘点 / 合并后复测，只读不改 brief）。

扫描当前执行真源 ``template-library/canonical/styles/*/brief.json``，输出：

- 轴 / 子家族分布（目录即家族的现有划分）；
- 调性标签分布（dark/light/flat/hand-drawn/serif/… 关键词映射，确定性）；
- 场景标签分布（答辩/汇报/教学/发布/营销/… 关键词映射）；
- 疑似同族清单：名称相似 + 色板重合的简单确定性规则——
  ``name_ratio`` 为去后缀名称的 ``difflib`` 相似度，``palette_jaccard``
  为两 brief 全部 HEX 锚点的 Jaccard；pair 判同族当
  (name_ratio ≥ 0.62 且共享 ≥1 HEX) 或 (name_ratio ≥ 0.45 且
  palette_jaccard ≥ 0.5) 或 palette_jaccard ≥ 0.6；union-find 聚簇；
- 复用色板 TOP（同一 HEX 出现于 ≥3 个 brief——合并候选的最强信号）；
- 家族合并口径（R-66 之后）：带 ``variant_of`` 的 brief 不计为独立
  顶层风格、不参与同族判定；报告 ``top_level_styles`` /
  ``variant_styles`` / ``family_merges``（主风格 → 变体名列表）。

用法::

    python3 scripts/audit_style_families.py           # 人读报告
    python3 scripts/audit_style_families.py --json    # 机读全量数据
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))
from leo_ppt_generator.styles import iter_brief_documents

STYLES_ROOT = SKILL_DIR / Path("template-library/canonical/styles")
LEGACY_STYLES_ROOT = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles")

JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")

# 调性关键词（确定性映射；命中即打标，可多标）
TONE_KEYWORDS = {
    "dark": ("dark", "black", "深黑", "炭黑", "墨黑", "深夜", "黑金"),
    "light": ("white", "light", "浅", "米白", "纸白", "warm white", "off-white"),
    "flat": ("flat", "扁平"),
    "hand-drawn": ("handdrawn", "hand-drawn", "手绘", "手写", "marker", "whiteboard", "手作"),
    "gradient": ("gradient", "渐变"),
    "neon": ("neon", "荧光"),
    "photographic": ("photo", "摄影", "照片", "photoreal"),
    "illustration": ("illustration", "插画", "卡通", "cartoon"),
    "serif": ("serif", "宋体", "衬线"),
    "minimal": ("minimal", "极简", "留白", "clean"),
    "retro": ("retro", "复古", "vintage"),
    "3d": ("3d", "isometric", "等距"),
}
# 场景关键词（best_for + 适用场景行）
SCENARIO_KEYWORDS = {
    "答辩": ("答辩", "defense", "开题", "结题"),
    "汇报": ("汇报", "总结", "review", "述职", "report"),
    "教学": ("教学", "课件", "课程", "培训", "讲座", "teaching", "course"),
    "发布": ("发布", "launch", "发布会", "demo"),
    "营销": ("营销", "marketing", "电商", "种草", "带货"),
    "路演": ("路演", "提案", "pitch", "融资"),
    "数据": ("数据", "analytics", "dashboard", "仪表盘", "kpi", "指标"),
    "科研": ("科研", "学术", "academic", "论文", "基金"),
    "政务": ("政务", "党政", "政府", "机关", "公共"),
    "品牌": ("品牌", "brand", "vi", "identity"),
    "儿童": ("儿童", "亲子", "kids", "child"),
    "技术": ("技术", "架构", "engineering", "开发者", "ai"),
}

NAME_SIMILAR_HARD = 0.62
NAME_SIMILAR_SOFT = 0.45
PALETTE_JACCARD_SOFT = 0.5
PALETTE_JACCARD_HARD = 0.6


def normalize_name(name: str) -> str:
    """去『风格/风』后缀与空白——家族判定用基名。"""
    stripped = name.strip()
    for suffix in ("风格", "风"):
        if stripped.endswith(suffix) and len(stripped) > len(suffix):
            stripped = stripped[: -len(suffix)]
            break
    return stripped


def brief_entries(styles_root: Path = STYLES_ROOT) -> list[dict]:
    entries: list[dict] = []
    canonical = any(styles_root.glob("*/brief.json"))
    if canonical:
        for path in sorted(styles_root.glob("*/brief.json")):
            try:
                brief = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            legacy = brief.get("legacy_payload") or {}
            palette_src = json.dumps(legacy.get("color_palette", {}), ensure_ascii=False) + str(
                legacy.get("canvas", {}).get("background", ""))
            hexes = sorted({h.upper() for h in HEX_RE.findall(palette_src)})
            scenario_text = " ".join(str(item) for item in (brief.get("taxonomy", {}).get("scenarios") or []))
            scenario_text += " " + str(legacy.get("best_for", ""))
            tone_text = " ".join(str(value) for value in (
                brief.get("visual_language", {}).get("direction", ""),
                legacy.get("canvas", {}).get("background", ""),
                legacy.get("color_palette", {}).get("primary", ""),
            )).lower()
            entries.append({
                "name": brief.get("name", path.parent.name),
                "base": normalize_name(str(brief.get("name", path.parent.name))),
                "path": str(path.relative_to(styles_root)),
                "axis": "canonical",
                "subfamily": ((brief.get("taxonomy") or {}).get("families") or ["未分类"])[0],
                "hexes": hexes,
                "tones": sorted(tag for tag, keys in TONE_KEYWORDS.items()
                                if any(k in tone_text for k in keys)),
                "scenarios": sorted(tag for tag, keys in SCENARIO_KEYWORDS.items()
                                    if any(k in scenario_text.lower() or k in scenario_text for k in keys)),
                "variant_of": brief.get("variant_of"),
            })
        return entries
    for path, text, brief in iter_brief_documents(styles_root):
        rel = path.relative_to(styles_root)
        axis = "顶层内置" if rel.parent == Path(".") else rel.parts[0]
        subfamily = rel.parent.name if len(rel.parts) > 2 else axis
        palette_src = json.dumps(
            brief.get("color_palette", {}), ensure_ascii=False
        ) + str(brief.get("canvas", {}).get("background", ""))
        hexes = sorted({h.upper() for h in HEX_RE.findall(palette_src)})
        scenario_text = str(brief.get("best_for", ""))
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("- ") and len(line) < 40:
                scenario_text += " " + line
        # tone signal from descriptive fields only (avoid/rule prose mentions
        # both poles — "avoid dark" would tag dark — and flattens the curve)
        tone_text = " ".join(str(value) for value in (
            brief.get("visual_direction", ""),
            brief.get("canvas", {}).get("background", ""),
            brief.get("color_palette", {}).get("primary", ""),
        )).lower()
        entries.append({
            "name": brief["style_name"],
            "base": normalize_name(str(brief["style_name"])),
            "path": str(rel),
            "axis": axis,
            "subfamily": subfamily,
            "hexes": hexes,
            "tones": sorted(tag for tag, keys in TONE_KEYWORDS.items()
                            if any(k in tone_text for k in keys)),
            "scenarios": sorted(tag for tag, keys in SCENARIO_KEYWORDS.items()
                                if any(k in scenario_text.lower() or k in scenario_text
                                       for k in keys)),
            "variant_of": brief.get("variant_of"),
        })
    return entries


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _name_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def pair_related(a: dict, b: dict) -> "tuple[bool, str]":
    """确定性同族判定：返回 (是否同族, 依据)。"""
    shared = set(a["hexes"]) & set(b["hexes"])
    ratio = _name_ratio(a["base"], b["base"])
    jaccard = _jaccard(set(a["hexes"]), set(b["hexes"]))
    if ratio >= NAME_SIMILAR_HARD and shared:
        return True, f"name={ratio:.2f}+hex{len(shared)}"
    if ratio >= NAME_SIMILAR_SOFT and jaccard >= PALETTE_JACCARD_SOFT:
        return True, f"name={ratio:.2f}+palette={jaccard:.2f}"
    if jaccard >= PALETTE_JACCARD_HARD:
        return True, f"palette={jaccard:.2f}"
    return False, ""


def clusters(entries: list[dict]) -> list[dict]:
    """union-find 聚簇疑似同族 brief。

    R-66 口径：带 ``variant_of`` 的家族变体已并入主风格，不再是独立
    顶层候选——同族判定只在无 ``variant_of`` 的顶层 brief 间进行。"""
    pool = [e for e in entries if e.get("variant_of") is None]
    parent = list(range(len(pool)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pair_notes: dict[tuple[int, int], str] = {}
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            related, why = pair_related(pool[i], pool[j])
            if related:
                pair_notes[(i, j)] = why
                parent[find(i)] = find(j)

    by_root: dict[int, list[int]] = {}
    for i in range(len(pool)):
        by_root.setdefault(find(i), []).append(i)
    result = []
    for members in by_root.values():
        if len(members) < 2:
            continue
        notes = sorted(
            {pair_notes[(i, j)]
             for i in members for j in members if (i, j) in pair_notes}
        )
        result.append({
            "members": [
                {"name": pool[i]["name"], "path": pool[i]["path"],
                 "axis": pool[i]["axis"], "hexes": pool[i]["hexes"]}
                for i in sorted(members)
            ],
            "evidence": notes,
        })
    result.sort(key=lambda c: (-len(c["members"]), c["members"][0]["path"]))
    return result


def build_report(entries: list[dict]) -> dict:
    axis_counts: dict[str, int] = {}
    subfamily_counts: dict[str, int] = {}
    tone_counts: dict[str, int] = {}
    scenario_counts: dict[str, int] = {}
    hex_usage: dict[str, list[str]] = {}
    family_merges: dict[str, list[str]] = {}
    variant_styles = 0
    for entry in entries:
        axis_counts[entry["axis"]] = axis_counts.get(entry["axis"], 0) + 1
        subfamily_counts[entry["subfamily"]] = subfamily_counts.get(entry["subfamily"], 0) + 1
        target = entry.get("variant_of")
        if target:
            variant_styles += 1
            family_merges.setdefault(target, []).append(entry["name"])
        for tag in entry["tones"]:
            tone_counts[tag] = tone_counts.get(tag, 0) + 1
        for tag in entry["scenarios"]:
            scenario_counts[tag] = scenario_counts.get(tag, 0) + 1
        for hex_value in entry["hexes"]:
            hex_usage.setdefault(hex_value, []).append(entry["name"])
    reused = {
        hex_value: names
        for hex_value, names in sorted(hex_usage.items())
        if len(names) >= 3
    }
    cluster_list = clusters(entries)
    clustered = sum(len(c["members"]) for c in cluster_list)
    return {
        "source": "canonical" if any(e.get("axis") == "canonical" for e in entries) else "retired-reference",
        "total_briefs": len(entries),
        "top_level_styles": len(entries) - variant_styles,
        "variant_styles": variant_styles,
        "family_merges": {k: sorted(v) for k, v in sorted(family_merges.items())},
        "by_axis": dict(sorted(axis_counts.items(), key=lambda kv: -kv[1])),
        "by_subfamily": dict(sorted(subfamily_counts.items(), key=lambda kv: -kv[1])),
        "by_tone": dict(sorted(tone_counts.items(), key=lambda kv: -kv[1])),
        "by_scenario": dict(sorted(scenario_counts.items(), key=lambda kv: -kv[1])),
        "reused_palettes": reused,
        "suspected_family_clusters": cluster_list,
        "clustered_briefs": clustered,
        "singleton_briefs": len(entries) - clustered,
    }


def render_text(report: dict) -> str:
    lines = [f"# {report['total_briefs']} brief 家族分布实测"
             f"（source={report.get('source', 'unknown')}，R-66 合并后口径）", "",
             f"brief 总数 {report['total_briefs']}（文件口径）；顶层主风格 "
             f"{report['top_level_styles']} + 家族变体 {report['variant_styles']}"
             f"（variant_of 归属 {len(report['family_merges'])} 个主风格家族）；"
             f"疑似同族簇 {len(report['suspected_family_clusters'])}"
             f"（涉及 {report['clustered_briefs']} 份顶层，"
             f"单例 {report['singleton_briefs']} 份）。", "",
             "## 家族合并（R-66 variant_of 归属）", ""]
    if report["family_merges"]:
        for primary, variants in report["family_merges"].items():
            lines.append(f"- {primary} ← {'、'.join(variants)}")
    else:
        lines.append("- （无）")
    lines += ["", "## 轴分布", ""]
    for axis, count in report["by_axis"].items():
        lines.append(f"- {axis}: {count}")
    lines += ["", "## 子家族分布（目录）", ""]
    for sub, count in report["by_subfamily"].items():
        lines.append(f"- {sub}: {count}")
    lines += ["", "## 调性标签分布", ""]
    for tag, count in report["by_tone"].items():
        lines.append(f"- {tag}: {count}")
    lines += ["", "## 场景标签分布", ""]
    for tag, count in report["by_scenario"].items():
        lines.append(f"- {tag}: {count}")
    lines += ["", "## 复用色板（同一 HEX ≥3 brief，文件口径——R-66 归属合并不删文件，"
              "回潮治理看顶层同族簇数与 lint family_duplicate）", ""]
    if report["reused_palettes"]:
        for hex_value, names in report["reused_palettes"].items():
            lines.append(f"- {hex_value} ×{len(names)}: {'、'.join(names)}")
    else:
        lines.append("- （无）")
    lines += ["", "## 疑似同族簇（名称相似 + 色板重合）", ""]
    if not report["suspected_family_clusters"]:
        lines.append("- （无）")
    for idx, cluster in enumerate(report["suspected_family_clusters"], 1):
        members = "、".join(
            f"{m['name']}（{m['axis']}）" for m in cluster["members"]
        )
        lines.append(f"{idx}. {members}")
        lines.append(f"   - 依据: {'; '.join(cluster['evidence'])}")
    lines.append("")
    return "\n".join(lines)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="输出机读 JSON 全量数据")
    parser.add_argument("--root", help="styles 目录覆盖（默认 canonical styles；供单测用）")
    parser.add_argument("--legacy-fixtures", action="store_true", help="显式检查 retired Markdown 迁移输入")
    args = parser.parse_args(argv)

    styles_root = Path(args.root).resolve() if args.root else STYLES_ROOT
    if args.legacy_fixtures:
        styles_root = Path(args.root).resolve() if args.root else LEGACY_STYLES_ROOT
    if not styles_root.is_dir():
        print(f"ERROR: styles directory not found: {styles_root}", file=sys.stderr)
        return 2
    report = build_report(brief_entries(styles_root))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
