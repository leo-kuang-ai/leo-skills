#!/usr/bin/env python3
"""check_layout_reuse.py — 强视觉版式「一 deck 一次」机器执行（B1-T6）。

遍历 deck_spec（或母版 JSON）的 slides[].layout，对 ``reuse_friendly=false``
版式（P1/P9/P23/P24/P34/P36）断言出现次数 ≤ ``max_per_deck``（sidecar 顶层
声明，缺省 1；P36 = 2）。超用即列出版式与页号，exit 1 阻断定稿。

版式真值：``references/styles/12_版式库/*.layouts.json``（layout-bank-v1）。

输入形态（slides[].layout 兼容两种）::

    {"slides": [{"page": 1, "layout": "P1"},
                {"page": 9, "layout": {"layout_name": "P9 · Closing Manifesto · deck 收尾页"}}]}

纯文本 ``layout`` 取 P 码；对象取 ``layout_name``/``layout_id`` 字段中的
P 码（`P\\d+` 首个匹配）。无 layout 字段的 deck → 用法错误 exit 2。

退出码（CI-4）：0 = 全部合规；1 = 存在超用；2 = 文件/用法错误。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

LAYOUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "references" / "styles" / "12_版式库"
)
_P_CODE_RE = re.compile(r"\bP([1-9]|[1-2][0-9]|3[0-6])\b")


def load_reuse_rules() -> dict[str, int]:
    """读全部 sidecar，返回 {P 码: max_per_deck}（仅 reuse_friendly=false）。"""
    rules: dict[str, int] = {}
    for path in sorted(LAYOUT_DIR.glob("*.layouts.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"[ERROR] sidecar 不可解析: {path.name} ({exc})", file=sys.stderr)
            raise SystemExit(2)
        if not isinstance(data, dict) or data.get("entity") != "layout":
            continue
        if data.get("reuse_friendly") is False:
            rules[str(data.get("layout_id"))] = int(data.get("max_per_deck", 1))
    return rules


def _p_code(layout_value: object) -> str | None:
    """从 layout 字段（字符串或对象）解析 P 码。"""
    if isinstance(layout_value, str):
        text = layout_value
    elif isinstance(layout_value, dict):
        text = str(
            layout_value.get("layout_id")
            or layout_value.get("layout_name")
            or ""
        )
    else:
        return None
    m = _P_CODE_RE.search(text)
    return f"P{m.group(1)}" if m else None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法: check_layout_reuse.py <deck_spec.json|master.json>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"[ERROR] {path}: 文件不存在", file=sys.stderr)
        return 2
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        print(f"[ERROR] {path}: 不可读（{exc}）", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"[ERROR] {path}: JSON 不可解析（{exc}）", file=sys.stderr)
        return 2
    slides = spec.get("slides")
    if not isinstance(slides, list) or not slides:
        print(f"[ERROR] {path}: 缺 slides 数组", file=sys.stderr)
        return 2

    rules = load_reuse_rules()
    usage: dict[str, list[int]] = {}
    saw_layout_field = False
    for slide in slides:
        if not isinstance(slide, dict) or "layout" not in slide:
            continue
        saw_layout_field = True
        code = _p_code(slide["layout"])
        if code is None:
            continue
        usage.setdefault(code, []).append(int(slide.get("page", 0) or 0))
    if not saw_layout_field:
        print(f"[ERROR] {path}: slides[] 无 layout 字段（母版需先落版式列）",
              file=sys.stderr)
        return 2

    violations = []
    for code in sorted(usage):
        limit = rules.get(code)
        if limit is None:
            continue  # reuse_friendly 版式不受限
        pages = usage[code]
        if len(pages) > limit:
            violations.append(
                f"{code}: 出现 {len(pages)} 次 > 上限 {limit}（页 "
                + ", ".join(str(p) for p in sorted(pages))
                + "）"
            )

    total_strong = Counter(
        c for c in usage if c in rules
    )
    print("== layout reuse check ==")
    if total_strong:
        for code in sorted(total_strong):
            limit = rules[code]
            print(
                f"  {code}: {len(usage[code])}/{limit} 次"
                + ("（超用）" if len(usage[code]) > limit else "")
            )
    else:
        print("  无强视觉版式（reuse_friendly=false）使用")
    if violations:
        print("FAIL: 强视觉版式超用")
        for v in violations:
            print("  -", v)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
