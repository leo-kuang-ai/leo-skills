#!/usr/bin/env python3
"""风格库治理断言 lint（配对完整性 / 图表警示 / 品牌核验）。

多视角防回归断言：

1. **配对完整性**：每个可加载风格 brief（顶层 + 01/02/03/05，共 137）
   在 ``00_索引/视觉风格配对.md`` 主表中都有配对行——任何风格走图片
   路线都有渲染锚，不静默退回默认。
2. **图表警示**：``11_图表语法`` 下含示例代码块（mermaid/text）的文件
   必须有「示例数字仅为语法演示」警示行，防止示意数字流入成品。
3. **品牌核验**：``10_品牌身份`` 全部文件声明 ``verified_at`` 状态，
   近似色值交付前必须核验的合同不因新增文件而缺位。

用法::

    python3 scripts/lint_style_governance.py

退出码：0 = 全部通过；2 = 存在违规。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STYLES_ROOT = SKILL_DIR / "references" / "styles"
PAIRING_PATH = STYLES_ROOT / "00_索引" / "视觉风格配对.md"

_PAIR_ROW_RE = re.compile(r"^\| ([^|]+) \| ([^|]+) \|$")


def _brief_stems() -> list[str]:
    stems = [p.stem for p in STYLES_ROOT.glob("*.md")]
    for d in ("01_通用母版", "02_行业内容域", "03_场景用途结构"):
        stems += [p.stem for p in (STYLES_ROOT / d).rglob("*.md") if p.name != "_content_rules.md"]
    stems += [p.stem for p in (STYLES_ROOT / "05_来源_awesome-gpt-image-2" / "借鉴新增").glob("*.md")]
    return stems


def _check_pairing(errors: list[str]) -> None:
    text = PAIRING_PATH.read_text(encoding="utf-8")
    main = text.split("## 未被视觉风格引用")[0]
    paired = {m.group(1).strip() for l in main.splitlines() if (m := _PAIR_ROW_RE.match(l)) and "视觉风格" not in l}
    for stem in _brief_stems():
        if stem not in paired:
            errors.append(f"配对缺失: {stem} 不在视觉风格配对表主表中")


def _check_chart_warnings(errors: list[str]) -> None:
    chart_dir = STYLES_ROOT / "11_图表语法"
    for p in sorted(chart_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if re.search(r"```(mermaid|text|xychart)", text) and "示例数字仅为语法演示" not in text:
            errors.append(f"图表警示缺失: {p.name} 含示例代码块但无「示例数字仅为语法演示」警示")


def _check_brand_verified(errors: list[str]) -> None:
    brand_dir = STYLES_ROOT / "10_品牌身份"
    for p in sorted(brand_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if "verified_at" not in text:
            errors.append(f"品牌核验缺失: {p.name} 未声明 verified_at 状态")


def main() -> int:
    errors: list[str] = []
    _check_pairing(errors)
    _check_chart_warnings(errors)
    _check_brand_verified(errors)
    print(f"governance errors={len(errors)}")
    for item in errors[:20]:
        print(f"  ✗ {item}")
    if len(errors) > 20:
        print(f"  ~ … 其余 {len(errors) - 20} 条")
    if not errors:
        print("OK")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
