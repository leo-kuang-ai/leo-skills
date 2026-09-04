#!/usr/bin/env python3
"""chart_series 调色板弹药池（机制线 M1，源 echarts + ppt-mcp）。

聚合两个外部上游的图表数据系列色序，输出确定性 JSON 池
（palette 名 → chart 色序列表），供 chart_series 弹药与
token_sidecar 选色参考；不进风格条目配额、不改 brief schema。

源（快照 2026-08-31）：

- echarts: ``echarts/theme/*.js`` 36 个主题——正则提取系列色数组
  ``var colorPalette|colorAll = [ '#rrggbb', ... ]`` 与主题级
  ``backgroundColor``（缩进 <=8 空格的 hex 赋值或 ``var backgroundColor``
  声明；tooltip 的 rgba 背景与组件级双色渐变不收）；
- ppt-mcp: ``ppt-mcp/src/ppt_com/themes.py`` ``PRESET_PALETTES`` 17 组
  ——ast 解析 dict 字面量，色序取 accent1..accent6（PPT 图表系列循环），
  dark/light 四键留作 context 不进色序；
- office-mcp: ``Office-PowerPoint-MCP-Server/utils/design_utils.py``
  ``PROFESSIONAL_COLOR_SCHEMES`` 4 组（快照 2026-09-02，RGB 数值按事实
  数据直引，表述思想级；指纹查重与既有 53 条零同板重叠，合计 57 条）——**静态快照
  常量内置**（不依赖外部目录），``--aggregate`` 重建时确定性重现，幂等。

确定性：条目按键排序、色序保持源序、仅收 ``#RRGGBB``（3 位/非 hex 丢弃）。

用法::

    python3 scripts/chart_palette_pool.py                    # 打印全池(默认快照)
    python3 scripts/chart_palette_pool.py --query macarons   # 子串查询(无匹配 exit 1)
    python3 scripts/chart_palette_pool.py --aggregate \
        --echarts-dir <echarts/theme> --ppt-mcp-themes <themes.py> \
        [--output scripts/chart-palette-pool.json]           # 从源重建

源路径优先级：CLI 参数 > 环境变量 ``LEO_CHART_POOL_ECHARTS_DIR`` /
``LEO_CHART_POOL_PPT_MCP_THEMES`` > 报错（不内嵌机器特定绝对路径）。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_POOL_PATH = SCRIPT_DIR / "chart-palette-pool.json"

# Series color array declarations across echarts theme files.
_COLOR_ARRAY_RE = re.compile(
    r"var\s+(colorPalette|colorAll)\s*=\s*\[(.*?)\]", re.S
)
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Theme-level background: `var backgroundColor = '#...'` or an assignment
# indented <= 8 spaces (tooltip/legend backgrounds sit deeper and use rgba).
_VAR_BG_RE = re.compile(r"var\s+backgroundColor\s*=\s*'(#[0-9A-Fa-f]{3,6})'")
_THEME_BG_RE = re.compile(r"^ {4,8}backgroundColor:\s*'(#[0-9A-Fa-f]{3,6})'", re.M)
_PPT_MCP_PREFIX = "ppt_mcp/"
_ECHARTS_PREFIX = "echarts/"
_OFFICE_MCP_PREFIX = "office_mcp/"

# Office-PowerPoint-MCP-Server PROFESSIONAL_COLOR_SCHEMES 快照（2026-09-02，
# UB4 色板池增量）。RGB 数值按事实数据直引；系列色序 = primary → accent1 →
# accent2 → secondary → text（light 太浅留作 background，不进系列色）。
_OFFICE_MCP_SCHEMES: dict[str, dict[str, list[int]]] = {
    "modern_blue": {
        "primary": [0, 120, 215], "secondary": [40, 40, 40],
        "accent1": [0, 176, 240], "accent2": [255, 192, 0],
        "light": [247, 247, 247], "text": [68, 68, 68],
    },
    "corporate_gray": {
        "primary": [68, 68, 68], "secondary": [0, 120, 215],
        "accent1": [89, 89, 89], "accent2": [217, 217, 217],
        "light": [242, 242, 242], "text": [51, 51, 51],
    },
    "elegant_green": {
        "primary": [70, 136, 71], "secondary": [255, 255, 255],
        "accent1": [146, 208, 80], "accent2": [112, 173, 71],
        "light": [238, 236, 225], "text": [89, 89, 89],
    },
    "warm_red": {
        "primary": [192, 80, 77], "secondary": [68, 68, 68],
        "accent1": [230, 126, 34], "accent2": [241, 196, 15],
        "light": [253, 253, 253], "text": [44, 62, 80],
    },
}


def _rgb_hex(rgb: list[int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _normalize_hex(value: str) -> str | None:
    value = value.strip().strip("'\"")
    return value if _HEX_RE.match(value) else None


def parse_echarts_js(text: str) -> tuple[list[str], str | None]:
    """Extract (series colors, theme background) from one echarts theme js."""
    colors: list[str] = []
    for _name, body in _COLOR_ARRAY_RE.findall(text):
        for raw in re.findall(r"['\"]([^'\"]+)['\"]", body):
            hexv = _normalize_hex(raw)
            if hexv and hexv not in colors:
                colors.append(hexv)
    background = None
    m = _VAR_BG_RE.search(text)
    if m:
        background = m.group(1)
    else:
        m = _THEME_BG_RE.search(text)
        if m:
            background = m.group(1)
    return colors, background


def parse_preset_palettes_py(text: str) -> dict[str, dict[str, str]]:
    """Parse the PRESET_PALETTES dict literal from ppt-mcp themes.py via ast."""
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assign_name, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            assign_name, value = node.targets[0].id, node.value
        else:
            continue
        if assign_name != "PRESET_PALETTES" or not isinstance(value, ast.Dict):
            continue
        out: dict[str, dict[str, str]] = {}
        for key, val in zip(value.keys, value.values):
            if not (isinstance(key, ast.Constant) and isinstance(val, ast.Dict)):
                continue
            entry = {}
            for k, v in zip(val.keys, val.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                    entry[str(k.value)] = str(v.value)
            out[str(key.value)] = entry
        return out
    return {}


def build_pool(
    echarts_dir: Path | None, ppt_mcp_themes: Path | None
) -> dict[str, dict]:
    """Aggregate both upstream sources into one sorted pool dict."""
    pool: dict[str, dict] = {}
    if echarts_dir:
        for js in sorted(echarts_dir.glob("*.js")):
            colors, background = parse_echarts_js(
                js.read_text(encoding="utf-8", errors="replace")
            )
            if colors:
                pool[f"{_ECHARTS_PREFIX}{js.stem}"] = {
                    "colors": colors,
                    "background": background,
                    "source": f"echarts/theme/{js.name}",
                }
    if ppt_mcp_themes:
        presets = parse_preset_palettes_py(
            ppt_mcp_themes.read_text(encoding="utf-8")
        )
        for name, entry in presets.items():
            # PPT chart series cycle over accent1..accent6; dark/light keys
            # stay as context, not chart series colors.
            colors = [
                entry[k] for k in (f"accent{i}" for i in range(1, 7)) if k in entry
            ]
            colors = [c for c in (_normalize_hex(x) for x in colors) if c]
            if colors:
                pool[f"{_PPT_MCP_PREFIX}{name}"] = {
                    "colors": colors,
                    "background": _normalize_hex(entry.get("light1", "")),
                    "source": "ppt-mcp/src/ppt_com/themes.py#PRESET_PALETTES",
                }
    # 静态快照源：无论 --aggregate 是否提供外部目录，office-mcp 4 组确定性在池。
    for name, scheme in _OFFICE_MCP_SCHEMES.items():
        pool[f"{_OFFICE_MCP_PREFIX}{name}"] = {
            "colors": [
                _rgb_hex(scheme[k])
                for k in ("primary", "accent1", "accent2", "secondary", "text")
            ],
            "background": _rgb_hex(scheme["light"]),
            "source": (
                "Office-PowerPoint-MCP-Server/utils/design_utils.py"
                "#PROFESSIONAL_COLOR_SCHEMES"
            ),
        }
    return dict(sorted(pool.items()))


def _resolve_source(
    flag_value: str | None, env_var: str, label: str
) -> Path | None:
    raw = flag_value or os.environ.get(env_var)
    if not raw:
        return None
    path = Path(raw)
    if not path.exists():
        sys.exit(f"chart_palette_pool: {label} 源不存在: {raw}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL_PATH,
                        help="池 JSON 文件路径（默认 scripts/chart-palette-pool.json）")
    parser.add_argument("--query", help="palette 名子串查询（大小写不敏感）")
    parser.add_argument("--aggregate", action="store_true",
                        help="从外部源重建池（需 --echarts-dir/--ppt-mcp-themes 或环境变量）")
    parser.add_argument("--echarts-dir", help="echarts/theme 目录")
    parser.add_argument("--ppt-mcp-themes", help="ppt-mcp themes.py 文件")
    parser.add_argument("--output", type=Path,
                        help="--aggregate 时写出路径（默认 --pool 路径）")
    args = parser.parse_args(argv)

    if args.aggregate:
        echarts_dir = _resolve_source(
            args.echarts_dir, "LEO_CHART_POOL_ECHARTS_DIR", "echarts"
        )
        ppt_mcp = _resolve_source(
            args.ppt_mcp_themes, "LEO_CHART_POOL_PPT_MCP_THEMES", "ppt-mcp"
        )
        if echarts_dir is None and ppt_mcp is None:
            parser.error(
                "--aggregate 需要至少一个源：--echarts-dir / --ppt-mcp-themes "
                "或环境变量 LEO_CHART_POOL_ECHARTS_DIR / LEO_CHART_POOL_PPT_MCP_THEMES"
            )
        pool = build_pool(echarts_dir, ppt_mcp)
        out_path = args.output or args.pool
        out_path.write_text(
            json.dumps(pool, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"chart_palette_pool: wrote {len(pool)} palettes -> {out_path}")
        return 0

    if not args.pool.exists():
        sys.exit(
            f"chart_palette_pool: 池文件不存在: {args.pool}（先 --aggregate 生成）"
        )
    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    if args.query:
        needle = args.query.lower()
        matched = {
            k: v for k, v in pool.items() if needle in k.lower()
        }
        if not matched:
            print(f"chart_palette_pool: 无匹配 palette: {args.query}", file=sys.stderr)
            return 1
        print(json.dumps(matched, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(json.dumps(pool, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
