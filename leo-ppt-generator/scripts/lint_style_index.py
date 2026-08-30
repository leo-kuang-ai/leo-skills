#!/usr/bin/env python3
"""风格库索引一致性 lint（_INDEX.md 数量口径 vs 文件系统实际）。

防漂移断言：新增/删除风格文件而 _INDEX.md 数字未同步时 ERROR。
口径与 _INDEX.md 顶行声明一致：

- **JSON 风格 brief** = 顶层 ``*.md`` + ``01_通用母版`` 全部
  + ``02_行业内容域``（排除各行业 ``_content_rules.md``）
  + ``03_场景用途结构`` 全部 + ``05_来源_awesome-gpt-image-2/借鉴新增``。
- **分节轴文档** = ``06_论证模式`` + ``07_信息图类型`` + ``08_图片渲染``
  + ``09_结构布局`` + ``10_品牌身份`` + ``11_图表语法``
  + ``12_版式库``（含选版式原则/常犯错误/关键类清单 3 份规则）
  + ``13_页面语义``。
- **规则/索引文档** = ``00_索引`` 全部 + ``04_来源_guizang`` 全部
  + ``05_来源_awesome-gpt-image-2/00_合并映射.md``。

检查项：

1. 顶行三大总数（brief / 分节轴 / 规则索引）与文件系统实际一致；
2. 总览表每个目录行的数量与实际一致；
3. ``## 图表语法（N）`` 节标题数与表格行数、实际文件数三者一致；
4. ``style-library.md`` 的分节轴总数与各轴目录括号数与实际一致（防同款漂移）。

用法::

    python3 scripts/lint_style_index.py

退出码：0 = 一致；2 = 存在漂移。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STYLES_ROOT = SKILL_DIR / "references" / "styles"
INDEX_PATH = STYLES_ROOT / "00_索引" / "_INDEX.md"
LIBRARY_PATH = SKILL_DIR / "references" / "style-library.md"

# 总览表口径：目录 -> 计数方式。
# all = 目录下全部 .md；exclude_rules = 排除 _content_rules.md；
# subdir_新增 = 仅「借鉴新增」子目录；whole = 目录整体（含规则）。
AXIS_COUNT_RULES: dict[str, str] = {
    "01_通用母版": "all",
    "02_行业内容域": "exclude_rules",
    "03_场景用途结构": "all",
    "04_来源_guizang": "all",
    "05_来源_awesome-gpt-image-2": "subdir_新增",
    "06_论证模式": "all",
    "07_信息图类型": "all",
    "08_图片渲染": "all",
    "09_结构布局": "all",
    "10_品牌身份": "all",
    "11_图表语法": "all",
    "12_版式库": "all",
    "13_页面语义": "all",
}
BRIEF_DIRS = ("01_通用母版", "02_行业内容域", "03_场景用途结构", "05_来源_awesome-gpt-image-2")
AXIS_DIRS = ("06_论证模式", "07_信息图类型", "08_图片渲染", "09_结构布局", "10_品牌身份",
             "11_图表语法", "12_版式库", "13_页面语义")
# 分节轴目录 -> style-library.md 中使用的中文短名
AXIS_NAMES = {
    "06_论证模式": "论证模式",
    "07_信息图类型": "信息图类型",
    "08_图片渲染": "图片渲染",
    "09_结构布局": "结构布局",
    "10_品牌身份": "品牌身份",
    "11_图表语法": "图表语法",
    "12_版式库": "版式库",
    "13_页面语义": "页面语义",
}

_HEADER_RE = re.compile(
    r"含 JSON 风格 (\d+) 份（(\d+) 顶层内置 \+ (\d+) 子目录参考）"
    r"\+ (\d+) 份分节轴文档.*?\+ (\d+) 份规则/索引文档"
)
_OVERVIEW_ROW_RE = re.compile(r"^\|\s*`(\d{2}_[^/]+)/`\s*\|\s*(\d+)\s*\|", re.M)
_CHART_SECTION_RE = re.compile(r"^## 图表语法（(\d+)）\s*$", re.M)


def _count_dir(name: str) -> int:
    rule = AXIS_COUNT_RULES[name]
    root = STYLES_ROOT / name
    if rule == "subdir_新增":
        return len(list((root / "借鉴新增").glob("*.md")))
    files = [p for p in root.rglob("*.md")]
    if rule == "exclude_rules":
        files = [p for p in files if p.name != "_content_rules.md"]
    return len(files)


def _actual_counts() -> dict[str, int]:
    return {name: _count_dir(name) for name in AXIS_COUNT_RULES}


def _check_library(errors: list[str], actual: dict[str, int]) -> None:
    """style-library.md 与 _INDEX 同源的数字不得单独漂移。

    两处口径：规模表分节轴行的总数与中文短名分解；各轴目录列表的
    ``目录名/`（N）`` 括号数。
    """
    if not LIBRARY_PATH.exists():
        return
    text = LIBRARY_PATH.read_text(encoding="utf-8")
    m = re.search(r"\*\*分节轴规范\*\*.*?\|\s*(\d+) 份\s*\|([^|]*)\|", text)
    if not m:
        errors.append("style-library.md 分节轴规范行缺失或格式变化，无法核对")
    else:
        claimed_axis, breakdown = int(m.group(1)), m.group(2)
        real_axis = sum(actual[d] for d in AXIS_DIRS)
        if claimed_axis != real_axis:
            errors.append(f"style-library.md 分节轴总数: 写 {claimed_axis}，实际 {real_axis}")
        for name in AXIS_DIRS:
            bm = re.search(rf"{AXIS_NAMES[name]} (\d+)", breakdown)
            if bm and int(bm.group(1)) != actual[name]:
                errors.append(
                    f"style-library.md 规模表 {name}: 写 {bm.group(1)}，实际 {actual[name]}"
                )
    for name in AXIS_DIRS:
        lm = re.search(rf"`{re.escape(name)}/?`（(\d+)）", text)
        if lm and int(lm.group(1)) != actual[name]:
            errors.append(
                f"style-library.md 各轴目录 {name}: 写 {lm.group(1)}，实际 {actual[name]}"
            )


def main() -> int:
    text = INDEX_PATH.read_text(encoding="utf-8")
    errors: list[str] = []
    actual = _actual_counts()
    top_level = len(list(STYLES_ROOT.glob("*.md")))

    header = _HEADER_RE.search(text)
    if not header:
        errors.append("_INDEX.md 顶行总数声明缺失或格式变化，无法核对")
    else:
        brief_total, top_claim, sub_claim, axis_total, rule_total = map(int, header.groups())
        actual_brief = top_level + sum(actual[d] for d in BRIEF_DIRS)
        actual_axis = sum(actual[d] for d in AXIS_DIRS)
        merge_map = STYLES_ROOT / "05_来源_awesome-gpt-image-2" / "00_合并映射.md"
        actual_rule = (
            len(list((STYLES_ROOT / "00_索引").glob("*.md")))
            + len(list((STYLES_ROOT / "04_来源_guizang").rglob("*.md")))
            + (1 if merge_map.exists() else 0)
        )
        for label, claimed, real in (
            ("JSON 风格 brief 总数", brief_total, actual_brief),
            ("顶层内置数", top_claim, top_level),
            ("子目录参考数", sub_claim, actual_brief - top_level),
            ("分节轴文档总数", axis_total, actual_axis),
            ("规则/索引文档总数", rule_total, actual_rule),
        ):
            if claimed != real:
                errors.append(f"顶行 {label}: _INDEX 写 {claimed}，实际 {real}")

    for m in _OVERVIEW_ROW_RE.finditer(text):
        name, claimed = m.group(1), int(m.group(2))
        if name not in actual:
            continue
        if claimed != actual[name]:
            errors.append(f"总览表 {name}/: _INDEX 写 {claimed}，实际 {actual[name]}")

    chart_files = actual["11_图表语法"]
    chart_heading = _CHART_SECTION_RE.search(text)
    if not chart_heading:
        errors.append("_INDEX.md 缺少「## 图表语法（N）」节，无法核对")
    else:
        claimed_rows = int(chart_heading.group(1))
        section = text[chart_heading.end():]
        nxt = re.search(r"^## ", section, re.M)
        if nxt:
            section = section[:nxt.start()]
        table_rows = len(
            re.findall(r"^\| [^|#]", section, re.M)
        ) - len(re.findall(r"^\| 类型 \|", section, re.M))
        for label, claimed, real in (
            ("图表语法节标题数", claimed_rows, chart_files),
            ("图表语法节表格行数", table_rows, chart_files),
        ):
            if claimed != real:
                errors.append(f"{label}: _INDEX 写 {claimed}，实际 {real}")

    _check_library(errors, actual)

    print(f"index_consistency errors={len(errors)}")
    for item in errors:
        print(f"  ✗ {item}")
    if not errors:
        print("OK")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
