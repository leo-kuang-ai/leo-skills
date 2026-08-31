#!/usr/bin/env python3
"""Generate the browsable style gallery (samples/style-gallery.md).

Scans ``references/styles/`` directly (filesystem is the truth, not the
hand-maintained index): the 11 top-level builtin briefs with their 适用场景
bullets, plus per-axis markdown counts for the subdirectories. Output is
deterministic; ``--check`` verifies the committed gallery is up to date
(exit 1 when stale) so it can act as a drift guard.

Exit codes: 0 = written or up to date; 1 = --check found drift; 2 = IO error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

STYLES_DIR = Path(__file__).resolve().parents[1] / "references" / "styles"
GALLERY = Path(__file__).resolve().parents[1] / "samples" / "style-gallery.md"
SCENARIO_HEADER = "**适用场景"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def builtin_styles() -> "list[tuple[str, list[str]]]":
    entries: list[tuple[str, list[str]]] = []
    for path in sorted(STYLES_DIR.glob("*.md")):
        scenarios: list[str] = []
        in_scenarios = False
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            fail(f"cannot read {path}: {exc}")
        for raw in lines:
            line = raw.strip()
            if line.startswith(SCENARIO_HEADER):
                in_scenarios = True
                continue
            if in_scenarios:
                if line.startswith("- "):
                    scenarios.append(line[2:].strip())
                else:
                    break
        entries.append((path.stem, scenarios))
    return entries


def axis_counts() -> "list[tuple[str, int]]":
    entries: list[tuple[str, int]] = []
    for directory in sorted(p for p in STYLES_DIR.iterdir() if p.is_dir()):
        if directory.name == "00_索引":
            continue
        count = len(list(directory.glob("*.md")))
        label = directory.name.split("_", 1)[1] if "_" in directory.name else directory.name
        entries.append((f"{label}（{directory.name.split('_')[0]}）", count))
    return entries


def render(builtins: "list[tuple[str, list[str]]]", axes: "list[tuple[str, int]]") -> str:
    lines = [
        "# 风格画廊（生成物）",
        "",
        "> 由 `python3 scripts/generate_style_gallery.py` 从 `references/styles/` 文件系统确定性生成；",
        "> 手工编辑会被 `--check` 判漂移。完整索引与选风格路由见",
        "> [`references/styles/00_索引/_INDEX.md`](../references/styles/00_索引/_INDEX.md)。",
        "",
        f"## 内置风格（{len(builtins)} 套，直接可选）",
        "",
        "| 风格 | 适用场景（摘自 brief） |",
        "| --- | --- |",
    ]
    for name, scenarios in builtins:
        summary = " / ".join(scenarios[:4]) if scenarios else "（见 brief）"
        lines.append(f"| **{name}** | {summary} |")
    lines += [
        "",
        f"## 参考轴（{len(axes)} 轴，markdown 份数）",
        "",
        "| 轴 | 份数 |",
        "| --- | --- |",
    ]
    for label, count in axes:
        lines.append(f"| {label} | {count} |")
    total = sum(count for _, count in axes) + len(builtins)
    lines += [
        "",
        f"合计 markdown 风格/规范文档 {total} 份（不含 JSON sidecar 与 00_索引规则文档）。",
        "选定后由 `style render` 确定性注入，流程见 [`references/style-library.md`](../references/style-library.md)。",
        "",
    ]
    return "\n".join(lines)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the style gallery from the styles directory.")
    parser.add_argument("--check", action="store_true", help="verify the gallery is up to date instead of writing")
    args = parser.parse_args(argv)

    if not STYLES_DIR.is_dir():
        fail(f"styles directory not found: {STYLES_DIR}")
    content = render(builtin_styles(), axis_counts())

    if args.check:
        try:
            current = GALLERY.read_text(encoding="utf-8")
        except OSError:
            print(f"STALE: {GALLERY} missing; run without --check to generate", file=sys.stderr)
            return 1
        if current != content:
            print(f"STALE: {GALLERY} differs from styles directory; regenerate", file=sys.stderr)
            return 1
        print("OK: gallery up to date")
        return 0

    try:
        GALLERY.parent.mkdir(parents=True, exist_ok=True)
        GALLERY.write_text(content, encoding="utf-8")
    except OSError as exc:
        fail(f"cannot write {GALLERY}: {exc}")
    print(f"wrote {GALLERY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
