#!/usr/bin/env python3
"""风格库 brief 结构 lint（风格系统优化计划 U7 / KTD5）。

单真值源：必需键与 HEX pattern 一律从
``runtime/src/leo_ppt_generator/schemas/style-brief-v1.schema.json`` 派生
（stdlib json 读取，零第三方依赖）；脚本只自实现 schema 表达不了的数量
子集校验。分级：

- **ERROR**：必需键缺失、canvas/typography 子键缺失、layout_patterns 为空、
  JSON 块不可解析、白名单之外的 WARNING（含新增文件——新文件不得进白名单）、
  顶层内置风格缺同名 ``.layouts.json`` 路由视图（layout-bank-v1 配对纪律；
  范围仅 11 顶层内置，126 子目录参考风格不强制——渐进轴）、
  negative_prompt / paired_illustration 校验（R-25 / R-68：11 顶层内置必填；
  参考风格可选——带字段即校验形状，缺省不报错，同 layouts sidecar 渐进轴）、
  家族合并校验（R-66 防回潮）：同一色板指纹（HEX 集合相等）的独立顶层
  风格 >1 即 ERROR——同板场景须显式 ``variant_of`` 归属家族主风格，且
  ``variants`` 列表与实际变体双向一致。
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

# R-68 插画配对词汇表（family 取自 ppt-master paired-rendering 家族 +
# leo 11 内置实际用到的家族；新增家族须同步本表）。density 三档语义：
# core=插画承担主要视觉载体 / supportive=辅助证据与氛围 / sparse=极简点缀。
ILLUSTRATION_FAMILIES = (
    "flat", "glass", "hand-drawn", "dashboard", "photographic",
    "editorial", "collage", "diagram",
)
ILLUSTRATION_DENSITIES = ("core", "supportive", "sparse")

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
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def _load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _brief_files(styles_root: Path = STYLES_ROOT) -> list[Path]:
    return sorted(p for p in styles_root.rglob("*.md") if _looks_like_brief(p))


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


def _lint_one(
    path: Path,
    schema: dict,
    *,
    is_builtin: bool = False,
    rel_to: Path | None = None,
) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)，条目形如 ``检查项: 细节``。"""
    errors: list[str] = []
    warnings: list[str] = []
    rel = path.relative_to(rel_to or SKILL_DIR)
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

    # R-25 负面提示词 / R-68 插画配对：内置必填（ERROR），参考风格可选
    # （带字段即校验形状，缺省不报错——同 layouts sidecar 的渐进轴口径）。
    # schema（style-brief-v1）未声明这两个可选键；此处为脚本内子集校验。
    negative = brief.get("negative_prompt")
    if negative is None:
        if is_builtin:
            errors.append(f"negative_prompt_missing: {rel}")
    elif (
        not isinstance(negative, list)
        or not negative
        or not all(isinstance(item, str) and item.strip() for item in negative)
    ):
        errors.append(f"negative_prompt_invalid: {rel} 须为非空字符串数组")

    paired = brief.get("paired_illustration")
    if paired is None:
        if is_builtin:
            errors.append(f"paired_illustration_missing: {rel}")
    elif not isinstance(paired, dict):
        errors.append(f"paired_illustration_invalid: {rel} 须为对象")
    else:
        family = paired.get("family")
        density = paired.get("density")
        if family not in ILLUSTRATION_FAMILIES:
            errors.append(
                f"paired_illustration_invalid: {rel}.family 须 ∈ "
                f"{'/'.join(ILLUSTRATION_FAMILIES)}， got {family!r}"
            )
        if density not in ILLUSTRATION_DENSITIES:
            errors.append(
                f"paired_illustration_invalid: {rel}.density 须 ∈ "
                f"{'/'.join(ILLUSTRATION_DENSITIES)}， got {density!r}"
            )

    # R-66 family merge fields: shape check here, cross-file consistency in
    # _family_merge_check (a variant must not declare its own variants list).
    variants = brief.get("variants")
    variant_of = brief.get("variant_of")
    if variants is not None:
        if variant_of is not None:
            errors.append(f"variant_fields_conflict: {rel} 同时带 variants 与 variant_of")
        elif (
            not isinstance(variants, list)
            or not variants
            or not all(isinstance(item, str) and item.strip() for item in variants)
        ):
            errors.append(f"variants_invalid: {rel} 须为非空字符串数组（「原名: 差异短句」）")
    if variant_of is not None and (
        not isinstance(variant_of, str) or not variant_of.strip()
    ):
        errors.append(f"variant_of_invalid: {rel} 须为非空字符串（家族主风格 style_name）")

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


# 别名撞名存量白名单（2026-09-01 快照，28 串；消歧规则见 风格路由.md 使用规则）。
# 收敛纪律：只缩不增——某串消歧清理后从此处删除；新增撞名必须 ERROR 拦截。
ALIAS_COLLISION_BASELINE: frozenset[str] = frozenset({
    "BI风", "Memphis", "catppuccin", "dreamy", "editorial", "linzi-morandi",
    "linzi-punk", "linzi-tech", "literary", "magazine", "playful", "retro",
    "terminal", "公益风", "古典", "国风", "撞色", "星河", "朋克酷风", "杂志风",
    "梦幻", "樱粉", "温柔", "烟火", "精选科技风", "莫兰迪系", "薄荷", "高级",
})


def _alias_collision_check(parsed: list[tuple[str, dict]]) -> list[str]:
    """别名撞名审计：同一别名被多个独立风格声明时，口语点名（R-63）产生
    歧义。存量撞名经白名单豁免（消歧规则兜底）；白名单外的新撞名即 ERROR。"""
    alias_owners: dict[str, list[str]] = {}
    for rel, brief in parsed:
        for alias in brief.get("aliases", []) or []:
            alias_owners.setdefault(str(alias), []).append(brief.get("style_name") or rel)
    errors: list[str] = []
    for alias in sorted(alias_owners):
        owners = alias_owners[alias]
        if len(owners) > 1 and alias not in ALIAS_COLLISION_BASELINE:
            errors.append(
                f"alias_collision: 别名「{alias}」被 {len(owners)} 个风格声明"
                f"（{'/'.join(sorted(owners))}）——新撞名不在存量白名单，请消歧或改名"
            )
    return errors


def _palette_fingerprint(brief: dict) -> frozenset[str]:
    """Same HEX anchor scope as audit_style_families (palette + canvas bg)."""
    palette_src = json.dumps(
        brief.get("color_palette", {}), ensure_ascii=False
    ) + str(brief.get("canvas", {}).get("background", ""))
    return frozenset(h.upper() for h in HEX_RE.findall(palette_src))


def _family_merge_check(parsed: list[tuple[str, dict]]) -> list[str]:
    """R-66 anti-regression: identical palette fingerprints may not back more
    than one independent top-level style, and variant/primary bookkeeping must
    stay bidirectionally consistent. Deterministic set arithmetic only."""
    errors: list[str] = []
    by_name: dict[str, tuple[str, dict]] = {}
    for rel, brief in parsed:
        name = str(brief.get("style_name") or "")
        if name:
            by_name[name] = (rel, brief)

    # variant_of integrity: target exists, no self/chained attribution.
    for name, (rel, brief) in sorted(by_name.items()):
        target = brief.get("variant_of")
        if target is None:
            continue
        if target == name:
            errors.append(f"variant_self: {rel} variant_of 指向自己")
        elif target not in by_name:
            errors.append(f"variant_target_missing: {rel} variant_of 指向不存在的 {target!r}")
        elif by_name[target][1].get("variant_of") is not None:
            errors.append(f"variant_chain: {rel} 指向的 {target} 自身也是变体（禁止链式归属）")

    # variants list vs actual variant files: bidirectional set equality.
    actual_variants: dict[str, set[str]] = {}
    for name, (rel, brief) in by_name.items():
        target = brief.get("variant_of")
        if target is not None:
            actual_variants.setdefault(target, set()).add(name)
    for name, (rel, brief) in sorted(by_name.items()):
        declared = brief.get("variants")
        if declared is None:
            if name in actual_variants:
                errors.append(
                    f"variants_list_missing: {rel} 被变体指向但缺 variants 声明: "
                    f"{sorted(actual_variants[name])}"
                )
            continue
        declared_names = {str(item).split(":", 1)[0].strip() for item in declared}
        actual = actual_variants.get(name, set())
        if declared_names != actual:
            errors.append(
                f"variants_list_mismatch: {rel} 声明 {sorted(declared_names)}，"
                f"实际指向它的变体 {sorted(actual)}"
            )

    # Same-fingerprint top-level duplicates (Jaccard == 1.0 <=> set equality).
    top_level = [
        (name, rel, _palette_fingerprint(brief))
        for name, (rel, brief) in sorted(by_name.items())
        if brief.get("variant_of") is None
    ]
    for i in range(len(top_level)):
        name_a, rel_a, fp_a = top_level[i]
        if not fp_a:
            continue
        for name_b, rel_b, fp_b in top_level[i + 1:]:
            if fp_a == fp_b:
                errors.append(
                    f"family_duplicate: 同板顶层风格 {name_a}({rel_a}) 与 "
                    f"{name_b}({rel_b}) 色板指纹相同——同板场景须以 variant_of "
                    f"归属家族主风格（R-66）"
                )
    return errors


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
    parser.add_argument(
        "--root",
        help="技能根目录覆盖（默认脚本所在仓库；供单测用 fixture 根）",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else SKILL_DIR
    styles_root = root / "references" / "styles"

    schema = _load_schema()
    errors: list[str] = []
    warnings: list[str] = []
    files = _brief_files(styles_root)
    parsed: list[tuple[str, dict]] = []
    for path in files:
        e, w = _lint_one(
            path, schema, is_builtin=path.parent == styles_root, rel_to=root
        )
        errors.extend(e)
        warnings.extend(w)
        text = path.read_text(encoding="utf-8")
        match = _JSON_BLOCK_RE.search(text)
        if match:
            try:
                brief = json.loads(match.group(1))
            except json.JSONDecodeError:
                brief = None
            if isinstance(brief, dict):
                parsed.append((str(path.relative_to(root)), brief))

    # R-66 anti-regression check runs in both lint and write-baseline modes.
    errors.extend(_family_merge_check(parsed))

    # 别名撞名（口语点名消歧债）：存量 28 个撞名串白名单只缩不增；
    # 新增撞名（新风格 aliases 撞既有别名）即 ERROR。
    errors.extend(_alias_collision_check(parsed))

    # 顶层内置风格必须有同名 .layouts.json 路由视图（B1-T4；仅顶层，子目录
    # 参考风格不强制——渐进轴，将来按批次纳入时走 baseline 收敛纪律）。
    for path in sorted(p for p in styles_root.glob("*.md") if _looks_like_brief(p)):
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
