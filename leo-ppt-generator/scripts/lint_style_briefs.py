#!/usr/bin/env python3
"""风格库 brief 结构 lint（风格系统优化计划 U7 / KTD5）。

单真值源：必需键与 HEX pattern 一律从
``runtime/src/leo_ppt_generator/schemas/style-brief-v1.schema.json`` 派生
（stdlib json 读取，零第三方依赖）；脚本只自实现 schema 表达不了的数量
子集校验。分级：

- **ERROR**：必需键缺失、canvas/typography 子键缺失、layout_patterns 为空、
  JSON 块不可解析、白名单之外的 WARNING（含新增文件——新文件不得进白名单）、
  顶层内置风格缺同名 ``.layouts.json`` 路由视图（layout-bank-v1 配对纪律；
  范围仅 11 顶层内置，126 子目录参考风格不强制——渐进轴）。
- **WARNING**：color_palette 四角色的值内无任何 ``#RRGGBB`` 锚点；typography
  无身份字体声明（缺具体字族关键词，通用设计规范 §一.6）。存量偏差登记于
  ``scripts/style-lint-baseline.txt``（一行一条 ``相对路径#检查项``，文件头
  注明 owner 与收敛纪律），修掉即从基线消失。

用法::

    python3 scripts/lint_style_briefs.py            # lint（错误非 0 退出）
    python3 scripts/lint_style_briefs.py --write-baseline  # 重新生成基线白名单

退出码：0 = ERROR 为 0；2 = 存在 ERROR。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STYLES_ROOT = SKILL_DIR / "references" / "styles"
SCHEMA_PATH = SKILL_DIR / "runtime" / "src" / "leo_ppt_generator" / "schemas" / "style-brief-v1.schema.json"
BASELINE_PATH = SCRIPT_DIR / "style-lint-baseline.txt"

# 身份字体关键词：中西文具体字族指示（通用设计规范 §一.6「具体到族」的机检近似）。
# 仅收录真实存在的字族名；泛称（如「手写体」「圆体」）不算身份声明。
_FONT_IDENTITY_RE = re.compile(
    r"思源|Noto|MiSans|HarmonyOS|鸿蒙|苹方|PingFang|华文|冬青|宋|黑体|楷体|仿宋|"
    r"小标宋|Source Han|Inter|Helvetica|Roboto|Arial|Georgia|Times|IBM Plex|"
    r"JetBrains|DIN|Avenir|Futura|Garamond|Baskerville|mono|等宽|Monospace|"
    r"霞鹜|LXGW|站酷|ZCOOL|Caveat|Nunito|Kalam",
    re.IGNORECASE,
)
_JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.S)
_IS_BRIEF_RE = re.compile(r"GPT-Image-2|风格 Brief|style brief", re.IGNORECASE)


def _load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _brief_files() -> list[Path]:
    return sorted(p for p in STYLES_ROOT.rglob("*.md") if _looks_like_brief(p))


def _looks_like_brief(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    for block in _JSON_BLOCK_RE.findall(text):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "style_name" in parsed:
            return True
    return False


def _lint_one(path: Path, schema: dict) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)，条目形如 ``检查项: 细节``。"""
    errors: list[str] = []
    warnings: list[str] = []
    rel = path.relative_to(SKILL_DIR)
    text = path.read_text(encoding="utf-8")
    blocks = [b for b in _JSON_BLOCK_RE.findall(text)]
    if not blocks:
        return ([f"brief_json_missing: {rel}"], [])
    brief = None
    try:
        brief = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        return ([f"brief_json_invalid: {rel} ({exc})"], [])
    if not isinstance(brief, dict):
        return ([f"brief_json_not_object: {rel}"], [])

    required: list[str] = schema.get("required", [])
    for key in required:
        if key not in brief:
            errors.append(f"required_missing: {rel} 缺 {key}")

    props = schema.get("properties", {})
    for sub in ("canvas", "typography"):
        node = brief.get(sub)
        sub_required = props.get(sub, {}).get("required", [])
        if isinstance(node, dict):
            for key in sub_required:
                if key not in node:
                    errors.append(f"required_missing: {rel}.{sub} 缺 {key}")
        elif sub in brief:
            errors.append(f"field_invalid: {rel}.{sub} 不是对象")

    if "layout_patterns" in brief and not brief["layout_patterns"]:
        errors.append(f"layout_patterns_empty: {rel}")

    # HEX 锚点（WARNING 级；pattern 从 schema 派生，保持单真值源）
    hex_re_src = (
        props.get("color_palette", {})
        .get("properties", {})
        .get("accent", {})
        .get("pattern", r"#[0-9A-Fa-f]{6}")
    )
    hex_re = re.compile(hex_re_src)
    palette = brief.get("color_palette")
    if isinstance(palette, dict):
        for role in ("primary", "secondary", "accent", "neutral"):
            value = palette.get(role)
            if isinstance(value, str) and not hex_re.search(value):
                warnings.append(f"{rel}#{role}-no-hex")

    # 身份字体声明（WARNING 级）
    typo = brief.get("typography")
    if isinstance(typo, dict):
        joined = " ".join(str(v) for v in typo.values() if isinstance(v, str))
        if not _FONT_IDENTITY_RE.search(joined):
            warnings.append(f"{rel}#typography-no-identity")

    return errors, warnings


def _load_baseline() -> set[str]:
    if not BASELINE_PATH.is_file():
        return set()
    entries: set[str] = set()
    for line in BASELINE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            entries.add(line)
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="把基线白名单收缩为「旧基线 ∩ 当前 WARNING」（只删不增）；"
        "新增 warning 需 --force 才能扩入",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许 --write-baseline 收录当前全部 WARNING（打破只缩不涨，慎用）",
    )
    args = parser.parse_args(argv)

    schema = _load_schema()
    errors: list[str] = []
    warnings: list[str] = []
    files = _brief_files()
    for path in files:
        e, w = _lint_one(path, schema)
        errors.extend(e)
        warnings.extend(w)

    # 顶层内置风格必须有同名 .layouts.json 路由视图（B1-T4；仅顶层，子目录
    # 参考风格不强制——渐进轴，将来按批次纳入时走 baseline 收敛纪律）。
    for path in sorted(p for p in STYLES_ROOT.glob("*.md") if _looks_like_brief(p)):
        sidecar = path.with_name(f"{path.stem}.layouts.json")
        if not sidecar.is_file():
            errors.append(
                f"style_sidecar_missing: 内置风格 {path.name} 缺同名 .layouts.json"
            )

    baseline = _load_baseline()
    if args.write_baseline:
        # ERROR 永远可见且阻断，write 模式不吞。
        if errors:
            for item in errors:
                print(f"  ✗ {item}")
            print(f"baseline NOT rewritten: {len(errors)} errors 必须先修")
            return 2
        if args.force:
            kept, dropped = set(warnings), []
        else:
            kept = {w for w in warnings if w in baseline}
            dropped = sorted(set(warnings) - kept)
        BASELINE_PATH.write_text(
            "# style-lint 基线白名单（存量 WARNING 收录；owner: 风格库维护者）\n"
            "# 收敛纪律：新增文件不得进白名单（--write-baseline 默认只收缩不扩张）；\n"
            "# 修掉一项即删除对应行；存量子目录风格 palette 的渐进 HEX 定型与身份字体\n"
            "# 声明补齐按批次推进（见风格系统优化计划 Deferred）。\n"
            + "\n".join(sorted(kept))
            + "\n",
            encoding="utf-8",
        )
        print(
            f"baseline rewritten: kept={len(kept)} dropped={len(baseline) - len(kept) if not args.force else 0}"
            f" -> {BASELINE_PATH}"
        )
        if dropped:
            print("新增未收录 warning（须修复或显式 --force）：")
            for item in dropped:
                print(f"  ✗ {item}")
            return 2
        return 0

    unknown = [w for w in warnings if w not in baseline]
    if unknown:
        errors.extend(f"warning_not_in_baseline: {w}" for w in unknown)

    print(f"briefs={len(files)} errors={len(errors)} warnings={len(warnings)} "
          f"(baseline={len(baseline)}, 未登记={len(unknown)})")
    for item in errors:
        print(f"  ✗ {item}")
    if not errors:
        n_show = 5
        for item in sorted(warnings)[:n_show]:
            print(f"  ~ {item}")
        if len(warnings) > n_show:
            print(f"  ~ … 其余 {len(warnings) - n_show} 条见基线白名单")
        print("OK")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
