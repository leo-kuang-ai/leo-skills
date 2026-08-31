#!/usr/bin/env python3
"""check_table_values.py — P25 表格页期望值清单与 OCR 回读逐格比对（批次 3-G）。

密集表格页（12+ 数据点）肉眼比对易漏：本脚本把「期望值清单」与「该页 OCR
回读文本」做逐值比对，输出命中/缺失报告，作为视觉质检的机读补充。

期望值清单 JSON（P25 版式合同产物，agent 从母版登记表派生）：
  [
    {"value": "1.24", "unit": "亿元", "page": 2, "container": "KPI 塔"},
    {"value": "37", "unit": "家", "page": 5, "container": "规格表 B3"}
  ]

OCR 文本：图片式路线来自 PaddleOCR hints（editable 路线既有通道）或人工导出；
每页一段纯文本。

比对规则：
  - 命中＝该页 OCR 文本中同时出现 value 与 unit（容忍全角/半角与千分位逗号
    差异：先归一化，再子串匹配）；
  - 缺失＝value 未命中；单位缺失单独降级报告（P3 级，仍计 pass 但列出）；
  - 输出：逐条 verdict + 汇总（missing_values / missing_units），任一 value
    缺失 exit 1。

用法：python3 check_table_values.py expected.json ocr_dir
  ocr_dir 内每页一个文本文件：page_<N>.txt
"""
import json
import re
import sys
from pathlib import Path


def _normalize(s: str) -> str:
    s = s.strip()
    s = s.replace(",", "").replace("，", "")       # 千分位
    s = s.replace("：", ":").replace("；", ";")
    return s


def main():
    if len(sys.argv) != 3:
        print("usage: check_table_values.py <expected.json> <ocr_dir>",
              file=sys.stderr)
        return 2
    expected = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    ocr_dir = Path(sys.argv[2])
    pages: dict[int, str] = {}
    for f in sorted(ocr_dir.glob("page_*.txt")):
        m = re.match(r"page_(\d+)", f.name)
        if m:
            pages[int(m.group(1))] = _normalize(f.read_text(encoding="utf-8"))

    missing_values, missing_units = [], []
    for item in expected:
        page = int(item.get("page", 0))
        text = pages.get(page, "")
        value = _normalize(str(item["value"]))
        unit = _normalize(str(item.get("unit", "")))
        if value and value not in text:
            missing_values.append(item)
            continue
        if unit and unit not in text:
            missing_units.append(item)

    for it in missing_values:
        print(f"MISSING-VALUE: p{it.get('page')} {it['value']}"
              f"{it.get('unit', '')} @ {it.get('container', '?')}", file=sys.stderr)
    for it in missing_units:
        print(f"MISSING-UNIT:  p{it.get('page')} {it['value']}"
              f"{it.get('unit', '')}（值在、单位缺失）", file=sys.stderr)
    total = len(expected)
    print(f"OK: {total} 项期望值，missing_values={len(missing_values)}, "
          f"missing_units={len(missing_units)}")
    return 1 if missing_values else 0


if __name__ == "__main__":
    sys.exit(main())
