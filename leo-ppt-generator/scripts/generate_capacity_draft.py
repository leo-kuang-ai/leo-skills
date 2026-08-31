#!/usr/bin/env python3
"""generate_capacity_draft.py — 36 版式文本 slot 容量数值的公式化标定器。

用途（一次性标定流程的可复现记录，B3-T2）：
- 本脚本持有 36 版式每个文本 slot 的几何表（栏数 / 容器高 vh / 字号 px），
  字号一律取自 ``00_索引/版心Canon.md`` 字阶刻度离散表；
- 容量三值（chars_per_line / max_lines / max_chars）由
  ``check_deck_geometry.py`` 的 leo 化 ``capacity_for()`` 从版心 token 推导，
  **不拍脑袋**；
- ``--check`` 校验已落盘 sidecar（``12_版式库/<stem>.layouts.json``）的文本
  slot 三值与公式输出一致（防手写漂移；lint 检查 C 只守恒恒等式，本脚本
  连公式来源一起对账）。缺 slot / 多 slot / 数值漂移均报 ERROR。

公式（leo 版心 token 语境，系数移植自 GordenPPTSkill，MIT）：

    容器可用宽 px = 栏数/12 × (100vw − 2×5vw 版心边距 − 2vw gutter) × 25.6 × 0.95
    chars_per_line = floor(可用宽 / 字号)
    max_lines      = floor(容器高 px / (字号 × 行高 1.0))
    max_chars      = floor(chars_per_line × max_lines × 1.2)

用法：
    python3 scripts/generate_capacity_draft.py            # 打印全部 slot 容量草稿
    python3 scripts/generate_capacity_draft.py P6         # 只看单个版式
    python3 scripts/generate_capacity_draft.py --check    # 校验 sidecar 落盘值

退出码：0 通过；1 --check 发现漂移；2 表内部不一致（缺版式/缺 slot）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from check_deck_geometry import leo_capacity_for  # noqa: E402  单真值公式来源

LAYOUT_DIR = SKILL_DIR / "references" / "styles" / "12_版式库"

# 几何表：layout_id -> {slot: (栏数, 容器高 vh, 字号 px)}。
# 字号取值 ∈ 版心Canon 字阶刻度：meta=24 caption=28 body=48(44-56 中值)
# h2=179(7vw) display=236(9.2vw) display_96=246(9.6vw) h1=215 h3=102(4vw)
# display_xl=297(11.6vw)。容器高从各版式 .md 骨架的区块高度语义审定。
GEOMETRY: dict[str, dict[str, tuple[int, float, float]]] = {
    "P1": {
        "title": (12, 19, 297),
        "subtitle": (8, 5, 48),
        "meta": (6, 4, 24),
    },
    "P2": {
        "node_value": (3, 5, 102),
        "node_desc": (8, 6, 28),
    },
    "P3": {
        "statement": (12, 40, 236),
        "footnote": (4, 4, 24),
    },
    "P4": {
        "cell_title": (4, 5, 102),
        "cell_desc": (4, 6, 28),
    },
    "P5": {
        "card_title": (8, 5, 102),
        "card_desc": (8, 8, 48),
    },
    "P6": {
        "item_label": (3, 4, 28),
        "big_number": (3, 5, 102),
    },
    "P7": {
        "item_label": (5, 4, 28),
        "item_value": (2, 4, 48),
    },
    "P8": {
        "side_title": (6, 6, 102),
        "side_desc": (6, 10, 48),
    },
    "P9": {
        "manifesto": (7, 15, 236),
        "takeaway_note": (7, 4, 28),
    },
    "P10": {
        "statement": (12, 25, 179),
    },
    "P11": {
        "step_name": (3, 4, 28),
    },
    "P12": {
        "manifesto": (8, 40, 102),
        "explainer": (4, 10, 48),
        "banner_line": (12, 6, 48),
    },
    "P13": {
        "card_title": (8, 5, 102),
        "card_desc": (8, 12, 48),
    },
    "P14": {
        "step_desc": (4, 5, 48),
    },
    "P15": {
        "item_title": (3, 8, 28),
        "hero_stat": (4, 8, 179),
    },
    "P16": {
        "card_main": (4, 5, 48),
        "card_footnote": (4, 4, 24),
    },
    "P17": {
        "layer_desc": (6, 8, 48),
    },
    "P18": {
        "point_desc": (4, 10, 48),
        "point_stat": (4, 8, 215),
    },
    "P19": {
        "card_title": (3, 5, 102),
        "card_desc": (3, 12, 48),
    },
    "P20": {
        "row_label": (6, 5, 48),
        "row_number": (4, 8, 215),
    },
    "P21": {
        "spec_number": (3, 6, 102),
    },
    "P22": {
        "desc": (12, 12, 48),
    },
    "P23": {
        "chapter_number": (4, 20, 297),
        "chapter_title": (8, 8, 102),
    },
    "P24": {
        "hero_number": (6, 20, 297),
        "hero_caption": (8, 6, 48),
    },
    "P25": {
        "cell": (4, 5, 24),
    },
    "P26": {
        "ref_line": (6, 4, 24),
    },
    "P27": {
        "objective_text": (8, 6, 48),
    },
    "P28": {
        "recap_text": (8, 6, 48),
        "hook": (8, 4, 28),
    },
    "P29": {
        "stem": (12, 8, 48),
        "option_text": (4, 6, 48),
    },
    "P30": {
        "assertion_title": (5, 8, 102),
        "body_copy": (5, 30, 48),
        "kpi_number": (5, 10, 236),
    },
    "P31": {
        "assertion_title": (12, 8, 215),
        "caption": (4, 6, 28),
    },
    "P32": {
        "entry_note": (4, 4, 28),
    },
    "P33": {
        "member_role": (3, 4, 24),
        "member_bio": (3, 6, 28),
    },
    "P34": {
        "quote": (8, 33, 236),
        "source": (4, 6, 24),
    },
    "P35": {
        "wall_number": (4, 8, 215),
        "wall_label": (4, 6, 102),
        "wall_meta": (4, 4, 28),
    },
    "P36": {
        "assertion": (8, 50, 246),
        "kicker": (4, 4, 24),
    },
}

# sidecar 文件名前缀（P 码 -> stem）
STEMS: dict[str, str] = {
    "P1": "01_Cover", "P2": "02_Vertical_Timeline", "P3": "03_Statement",
    "P4": "04_Six_Cells", "P5": "05_Three_Sub_cards", "P6": "06_KPI_Tower",
    "P7": "07_H_Bar_Chart", "P8": "08_Duo_Compare",
    "P9": "09_Closing_Manifesto", "P10": "10_Dot_Matrix_Statement",
    "P11": "11_Horizontal_Timeline", "P12": "12_Manifesto_Ink_Banner",
    "P13": "13_Three_Forces_Cards", "P14": "14_Loop_Diagram",
    "P15": "15_Image_Matrix_Hero_Stat", "P16": "16_Multi_card_Brief",
    "P17": "17_System_Diagram", "P18": "18_Why_Now", "P19": "19_Four_Cards",
    "P20": "20_Stacked_KPI_Ledger", "P21": "21_Tech_Spec_Sheet",
    "P22": "22_Image_Hero", "P23": "P23_Section_Divider",
    "P24": "P24_Number_Hero", "P25": "P25_Spec_Table",
    "P26": "P26_Reference_List", "P27": "P27_Learning_Objectives",
    "P28": "P28_Recap", "P29": "P29_Quiz", "P30": "30_Swiss_Image_Split",
    "P31": "31_Swiss_Evidence_Grid", "P32": "32_Agenda", "P33": "33_Team_Grid",
    "P34": "34_Quote_Hero", "P35": "35_Data_Wall",
    "P36": "36_Ambience_Full_Bleed",
}


def draft(layout_id: str) -> dict[str, tuple[int, int, int]]:
    """返回 slot -> (chars_per_line, max_lines, max_chars) 的公式化草稿。"""
    return {
        slot: leo_capacity_for(cols, height_vh, font_px)
        for slot, (cols, height_vh, font_px) in GEOMETRY[layout_id].items()
    }


def check() -> int:
    errors: list[str] = []
    for layout_id in sorted(GEOMETRY):
        path = LAYOUT_DIR / f"{STEMS[layout_id]}.layouts.json"
        if not path.is_file():
            errors.append(f"{path.name}: sidecar 缺失")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        capacity = data.get("content_capacity", {})
        expected = draft(layout_id)
        text_slots = {
            name for name, slot in capacity.items()
            if isinstance(slot, dict) and "chars_per_line" in slot
        }
        for slot in sorted(set(expected) | text_slots):
            if slot not in capacity:
                errors.append(f"{path.name}: 文本 slot {slot} 在 sidecar 中缺失")
                continue
            if slot not in expected:
                errors.append(
                    f"{path.name}: slot {slot} 不在几何表内（先登记几何再落盘）"
                )
                continue
            got = capacity[slot]
            want = expected[slot]
            for key, value in zip(
                ("chars_per_line", "max_lines", "max_chars"), want
            ):
                if got.get(key) != value:
                    errors.append(
                        f"{path.name}.{slot}.{key}: 落盘 {got.get(key)} "
                        f"≠ 公式 {value}（栏数/高/字号 = {GEOMETRY[layout_id][slot]}）"
                    )
    if errors:
        print(f"capacity drift: {len(errors)} 处")
        for e in errors:
            print("  -", e)
        return 1
    total = sum(len(v) for v in GEOMETRY.values())
    print(f"capacity check OK: 36 layouts, {total} text slots 与公式一致")
    return 0


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if "--check" in argv:
        return check()
    ids = args if args else sorted(GEOMETRY)
    for layout_id in ids:
        if layout_id not in GEOMETRY:
            print(f"unknown layout: {layout_id}", file=sys.stderr)
            return 2
        print(f"{layout_id} ({STEMS[layout_id]}):")
        for slot, values in draft(layout_id).items():
            geo = GEOMETRY[layout_id][slot]
            print(
                f"  {slot}: cpl={values[0]} lines={values[1]} "
                f"max_chars={values[2]}  <- cols={geo[0]} h={geo[1]}vh "
                f"font={geo[2]}px"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
