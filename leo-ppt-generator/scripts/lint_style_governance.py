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
4. **路由存在性**：``00_索引/风格路由.md`` 快速路由表引用的风格名
   （含「风」的 token）必须在风格库或渲染轴中真实存在——路由不指向
   幽灵风格。
5. **文字对比锚点**：按 primary 锚点亮度判定深/浅底后，palette 合并
   锚点中必须存在对相应底色 ≥4.5:1 的文字锚（浅底查深锚、深底查浅
   锚）——无障碍底线，不断言 accent（accent 服务图形/高亮，荧光金
   类低白底对比是风格本性）。

用法::

    python3 scripts/lint_style_governance.py

退出码：0 = 全部通过；2 = 存在违规。
"""

from __future__ import annotations

import json
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


def _check_routing(errors: list[str]) -> None:
    routing = STYLES_ROOT / "00_索引" / "风格路由.md"
    if not routing.is_file():
        return
    stems = {p.stem for p in STYLES_ROOT.rglob("*.md")
             if p.relative_to(STYLES_ROOT).parts[0] not in ("00_索引", "12_版式库", "04_来源_guizang")
             and p.name not in ("_content_rules.md", "00_合并映射.md", "00_README.md")}
    renderings = {p.stem for p in (STYLES_ROOT / "08_图片渲染").glob("*.md")}
    known = stems | renderings
    for line in routing.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "内容 / 任务" in line or re.search(r"^\|[-\s|]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        for cell in cells[1:]:
            for token in re.split(r"[/、]", cell):
                m = re.match(r"^(.*?风)（?", token.strip())
                name = m.group(1).strip() if m else ""
                # 「视觉风」是表头列名「视觉风格（01）」的切分残留，非引用。
                if name and name != "视觉风" and name not in known:
                    errors.append(f"路由失效: 风格路由表引用「{name}」不存在")


def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(fg: str, bg: str) -> float:
    l1, l2 = _lum(fg), _lum(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def _check_text_anchor(errors: list[str]) -> None:
    skip_dirs = {"00_索引", "12_版式库", "04_来源_guizang"}
    skip_names = {"_content_rules.md", "00_合并映射.md"}
    for p in sorted(STYLES_ROOT.rglob("*.md")):
        rel = p.relative_to(STYLES_ROOT)
        if rel.parts[0] in skip_dirs or p.name in skip_names:
            continue
        m = re.search(r"```json\n(.*?)```", p.read_text(encoding="utf-8"), re.S)
        if not m:
            continue
        try:
            palette = json.loads(m.group(1)).get("color_palette", {})
        except json.JSONDecodeError:
            continue
        primary = re.findall(r"#(?:[0-9A-Fa-f]{6})", palette.get("primary", ""))
        all_hex: list[str] = []
        for role in ("primary", "secondary", "accent", "neutral"):
            all_hex += re.findall(r"#(?:[0-9A-Fa-f]{6})", palette.get(role, ""))
        if not primary or not all_hex:
            continue
        if sum(_lum(h) for h in primary) / len(primary) < 0.35:
            bg, kind = "#1A1A1A", "深底(浅文字锚)"
        else:
            bg, kind = "#FFFFFF", "浅底(深文字锚)"
        if not any(_contrast(h, bg) >= 4.5 for h in all_hex):
            errors.append(f"文字锚缺失: {p.name} 为{kind}，palette 无 ≥4.5:1 对比锚点")


def main() -> int:
    errors: list[str] = []
    _check_pairing(errors)
    _check_chart_warnings(errors)
    _check_brand_verified(errors)
    _check_routing(errors)
    _check_text_anchor(errors)
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
