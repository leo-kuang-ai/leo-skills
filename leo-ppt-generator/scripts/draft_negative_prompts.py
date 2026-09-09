#!/usr/bin/env python3
"""negative_prompt 渐进补齐的半自动草案器（渐进治理债工具）。

背景：约 126 份早期批参考 brief 的 negative_prompt 不足 3 条（lint 仅对
顶层内置强制）。本脚本从 brief **自身已有字段**确定性派生候选负面词——
不做任何生成式补写：

- ``visual_elements.avoid``（按 ；;。、 切分）
- ``rendering_constraints``（逐条；剔除纯正向句）
- ``color_palette.rule`` / ``layout_usage_rule`` 中含 不要/禁/避免/不招 的分句

用法::

    python3 scripts/draft_negative_prompts.py            # dry-run：列出草案
    python3 scripts/draft_negative_prompts.py --apply    # 把草案写入不足 3 条的
                                                         # brief（去重后补足，最多 5 条）
    python3 scripts/draft_negative_prompts.py --pool template-library/reference/sources/retired-styles-tree/styles/00_索引/负面语料参考池.md
                                                          # 叠加语料池词条（家族组按
                                                          # brief 所在目录名匹配，
                                                          # 通用组全适用）

纪律：--apply 只在既有 negative_prompt < 3 时写入；brief 自身约束字段派生的
候选优先，池词条只补缺口；写入后建议同批跑 lint_style_briefs 确认无回归。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STYLES_ROOT = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles")
DEFAULT_POOL = STYLES_ROOT / "00_索引" / "负面语料参考池.md"

_JSON_BLOCK = re.compile(r"```json\n(.*?)\n```", re.S)
_SPLIT = re.compile(r"[；;。]\s*|\s*[、，]\s*(?=不要|禁|避免|不)")
_NEGATIVE_HINT = re.compile(r"不要|禁|避免|不得|不用|不使用|不出现|拒绝|严禁|≤|不超过")
_ARRAY = re.compile(r'("negative_prompt"\s*:\s*\[)(.*?)(\])', re.S)


def _candidates(brief: dict) -> list[str]:
    seen: list[str] = []
    sources: list[str] = []

    avoid = (brief.get("visual_elements") or {}).get("avoid", "")
    if isinstance(avoid, str):
        sources += _SPLIT.split(avoid)
    for item in brief.get("rendering_constraints") or []:
        if isinstance(item, str):
            sources.append(item)
    for key in ("rule",):
        value = (brief.get("color_palette") or {}).get(key, "")
        if isinstance(value, str):
            sources += _SPLIT.split(value)
    usage = brief.get("layout_usage_rule", "")
    if isinstance(usage, str):
        sources += _SPLIT.split(usage)

    for raw in sources:
        text = raw.strip().strip("；;。，, ")
        if not text or len(text) < 6:
            continue
        if not _NEGATIVE_HINT.search(text):
            continue  # 只收显性禁止句
        if any(text != kept and text in kept for kept in seen):
            continue  # 子串去重：丢弃已被更长条目包含的碎片
        if text not in seen:
            seen.append(text)
    return seen


def _load_pool(path: Path) -> dict[str, list[str]]:
    """解析负面语料参考池：``## 组名`` 二级标题段 + 其下 ``- `` 列表项。

    ``## 选用指引`` 段是给人读的 consuming 说明，不参与解析。
    """
    groups: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            current = None if name == "选用指引" else groups.setdefault(name, [])
        elif current is not None and line.startswith("- "):
            item = line[2:].strip()
            if len(item) >= 6:
                current.append(item)
    return groups


def _pool_candidates(groups: dict[str, list[str]], path_parts: set[str]) -> list[str]:
    """按 brief 路径段匹配池组：``通用`` 组全适用，其余组名命中目录名才适用。"""
    out: list[str] = []
    for name, items in groups.items():
        if name == "通用" or name in path_parts:
            out.extend(items)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="negative_prompt 草案器（dry-run 默认）")
    parser.add_argument("--apply", action="store_true", help="写入不足 3 条的 brief（补足至 3-5 条）")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 份（0=全部）")
    parser.add_argument(
        "--pool", type=Path, nargs="?", const=DEFAULT_POOL, default=None,
        help="负面语料参考池路径；裸 --pool 用内置池"
        f"（{DEFAULT_POOL.relative_to(SKILL_DIR)}），不传则不启用",
    )
    args = parser.parse_args(argv)

    pool_groups: dict[str, list[str]] = {}
    if args.pool is not None:
        pool_groups = _load_pool(args.pool)

    touched = 0
    for path in sorted(STYLES_ROOT.rglob("*.md")):
        if path.parent.name == "00_索引":
            continue
        raw = path.read_text(encoding="utf-8")
        m = _JSON_BLOCK.search(raw)
        if not m:
            continue
        try:
            brief = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        existing = [str(x) for x in brief.get("negative_prompt") or []]
        if len(existing) >= 3:
            continue
        existing_set = {x for x in existing}
        draft = [c for c in _candidates(brief) if c not in existing_set]
        if pool_groups:
            parts = set(path.relative_to(STYLES_ROOT).parts)
            pool_extra = list(dict.fromkeys(  # 组间词条保序去重
                c for c in _pool_candidates(pool_groups, parts)
                if c not in existing_set and c not in draft
            ))
            draft += pool_extra  # 池词条排在自身派生之后，只补缺口
        if not draft:
            continue
        fill = draft[: max(0, 5 - len(existing))][: 3 - len(existing)]
        if not fill:
            continue
        rel = path.relative_to(SKILL_DIR)
        print(f"{rel}: 现有 {len(existing)} 条 → 补 {len(fill)} 条")
        for item in fill:
            print(f"  + {item}")
        if args.apply:
            merged = existing + fill
            new_block = _ARRAY.sub(
                lambda mm: mm.group(1)
                + json.dumps(merged, ensure_ascii=False, indent=2).replace("\n", "\n  ")
                .replace("[\n  ", "[").replace("\n  ]", "\n  ]")
                + mm.group(3),
                m.group(1),
                count=1,
            )
            path.write_text(raw.replace(m.group(1), new_block, 1), encoding="utf-8")
            touched += 1
        if args.limit and (touched if args.apply else 0) >= args.limit:
            break
    mode = "已写入" if args.apply else "dry-run（加 --apply 落盘）"
    print(f"\n{mode}；处理 {touched if args.apply else 'N/A'} 份（apply 模式）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
