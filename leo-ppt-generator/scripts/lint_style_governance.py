#!/usr/bin/env python3
"""风格库治理断言 lint（配对完整性 / 图表警示 / 品牌核验）。

多视角防回归断言：

1. **配对完整性**：每个可加载风格 brief（顶层 + 01/02/03/05，共 207）
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
6. **提示词进化记账**：``prompts/`` 下每个 ``.md`` 文件在
   ``prompts/registry.yaml`` 至少有一条 ``file`` 引用——prompt 变更
   必须同 commit 记账，缺条目 FAIL；registry 条目指向不存在的文件
   仅 WARN（陈旧记账不阻断）。

用法::

    python3 scripts/lint_style_governance.py

退出码：0 = 全部通过；2 = 存在违规。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_LIBRARY_ROOT = SKILL_DIR / "template-library"
CANONICAL_ROOT = TEMPLATE_LIBRARY_ROOT / "canonical"
GOVERNANCE_INDEX_ROOT = TEMPLATE_LIBRARY_ROOT / "governance" / "authoring" / "index"
STYLES_ROOT = CANONICAL_ROOT / "styles"
BRANDS_ROOT = CANONICAL_ROOT / "brands"
PAIRING_PATH = GOVERNANCE_INDEX_ROOT / "视觉风格配对.md"
ROUTING_PATH = GOVERNANCE_INDEX_ROOT / "风格路由.md"
CHART_DIR = CANONICAL_ROOT / "axes" / "chart"
PROMPTS_DIR = SKILL_DIR / "prompts"
PROMPT_REGISTRY_PATH = PROMPTS_DIR / "registry.yaml"

_REGISTRY_REQUIRED_KEYS = ("id", "date", "name", "file", "improvement", "dimension", "change", "lesson")
_REGISTRY_CHANGE_VALUES = {"added", "updated", "removed", "none"}

_PAIR_ROW_RE = re.compile(r"^\| ([^|]+) \| ([^|]+) \|$")


def check_document_links(documents: dict[str, str], root: Path) -> list[str]:
    """校验给定 Markdown 发布集；生成前可用内存文档验证虚拟目标。"""
    from markdown_it import MarkdownIt

    root = root.resolve()
    parser = MarkdownIt()
    texts = {(root / path).resolve(): text for path, text in documents.items()}
    cache = {}
    errors = []

    def tokens_for(path):
        if path not in cache:
            cache[path] = parser.parse(texts[path] if path in texts else path.read_text(encoding="utf-8"))
        return cache[path]

    def headings(path):
        values = set()
        used = {}
        tokens = tokens_for(path)
        for i, token in enumerate(tokens):
            if token.type != "heading_open":
                continue
            inline = tokens[i + 1]
            title = "".join(t.content for t in inline.children or [] if t.type in {"text", "code_inline", "image"})
            base = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
            suffix = used.get(base, 0)
            used[base] = suffix + 1
            values.add(base if suffix == 0 else f"{base}-{suffix}")
        return values

    def walk(tokens):
        for token in tokens:
            yield token
            yield from walk(token.children or [])

    for relative in sorted(documents):
        source = (root / relative).resolve()
        for token in walk(tokens_for(source)):
            if token.type not in {"link_open", "image"}:
                continue
            href = token.attrGet("href" if token.type == "link_open" else "src") or ""
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                continue
            target = (source.parent / unquote(parts.path)).resolve() if parts.path else source
            if not target.is_relative_to(root.parent):
                errors.append(f"link_outside_repository: {relative}: {href}")
            elif target not in texts and not target.exists():
                errors.append(f"link_target_missing: {relative}: {href}")
            elif parts.fragment and target.suffix == ".md" and unquote(parts.fragment) not in headings(target):
                errors.append(f"link_anchor_missing: {relative}: {href}")
    return errors


def _brief_records() -> list[tuple[Path, dict]]:
    """Return canonical style briefs without treating directory names as IDs."""

    records = []
    for path in sorted(STYLES_ROOT.glob("*/brief.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            records.append((path, value))
    return records


def _brief_stems() -> list[str]:
    """Return canonical display names used by the authoring indexes."""

    return [str(value.get("name") or path.parent.name) for path, value in _brief_records()]


def _check_pairing(errors: list[str]) -> None:
    if not PAIRING_PATH.is_file():
        errors.append(f"配对索引缺失: {PAIRING_PATH.relative_to(SKILL_DIR)}")
        return
    text = PAIRING_PATH.read_text(encoding="utf-8")
    main = text.split("## 未被视觉风格引用")[0]
    paired = {m.group(1).strip() for l in main.splitlines() if (m := _PAIR_ROW_RE.match(l)) and "视觉风格" not in l}
    for path, brief in _brief_records():
        # Legacy-migrated briefs are the styles with the old image-rendering
        # contract. Authored seed styles must declare a rendering binding
        # before they enter this table; otherwise they remain style-only.
        if brief.get("source", {}).get("origin") != "legacy-migrated":
            continue
        name = str(brief.get("name") or path.parent.name)
        if name not in paired:
            errors.append(f"配对缺失: {name} 不在视觉风格配对表主表中")


def _check_chart_warnings(errors: list[str]) -> None:
    if not CHART_DIR.is_dir():
        return
    for p in sorted(CHART_DIR.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        if re.search(r"```(mermaid|text|xychart)", text) and "示例数字仅为语法演示" not in text:
            errors.append(f"图表警示缺失: {p.name} 含示例代码块但无「示例数字仅为语法演示」警示")


def _check_brand_verified(errors: list[str]) -> None:
    if not BRANDS_ROOT.is_dir():
        errors.append(f"品牌目录缺失: {BRANDS_ROOT.relative_to(SKILL_DIR)}")
        return
    for p in sorted(BRANDS_ROOT.glob("*/brand.json")):
        try:
            value = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"品牌核验不可读: {p.relative_to(BRANDS_ROOT)} ({exc})")
            continue
        verification = value.get("verification") if isinstance(value, dict) else None
        if not isinstance(verification, dict) or not str(verification.get("verified_at") or "").strip():
            errors.append(f"品牌核验缺失: {p.relative_to(BRANDS_ROOT)} 未声明 verification.verified_at 状态")


def _check_routing(errors: list[str]) -> None:
    routing = ROUTING_PATH
    if not routing.is_file():
        return
    known = set(_brief_stems())
    known |= {alias for _, brief in _brief_records() for alias in brief.get("aliases", []) if isinstance(alias, str)}
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
    for p, brief in _brief_records():
        palette = brief.get("legacy_payload", {}).get("color_palette", {})
        if not isinstance(palette, dict):
            continue
        primary = re.findall(r"#(?:[0-9A-Fa-f]{6})", str(palette.get("primary", "")))
        all_hex: list[str] = []
        for role in ("primary", "secondary", "accent", "neutral"):
            all_hex += re.findall(r"#(?:[0-9A-Fa-f]{6})", str(palette.get(role, "")))
        if not primary or not all_hex:
            continue
        if sum(_lum(h) for h in primary) / len(primary) < 0.35:
            bg, kind = "#1A1A1A", "深底(浅文字锚)"
        else:
            bg, kind = "#FFFFFF", "浅底(深文字锚)"
        if not any(_contrast(h, bg) >= 4.5 for h in all_hex):
            errors.append(f"文字锚缺失: {p.name} 为{kind}，palette 无 ≥4.5:1 对比锚点")


def _load_prompt_registry(registry_path: Path):
    """解析 registry.yaml；缺文件/坏结构/缺 yaml 模块都归一为 (value, error)。"""

    if not registry_path.is_file():
        try:
            shown = registry_path.relative_to(SKILL_DIR)
        except ValueError:
            shown = registry_path
        return None, f"提示词记账缺失: {shown} 不存在"
    try:
        import yaml
    except ImportError:  # pragma: no cover - CI 环境保证 PyYAML 在场
        return None, "提示词记账不可用: 当前解释器缺 PyYAML，无法解析 registry.yaml"
    try:
        value = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        return None, f"提示词记账不可读: {registry_path.name} ({exc})"
    except Exception as exc:  # yaml.YAMLError 及各发行版解析异常
        return None, f"提示词记账不可解析: {registry_path.name} ({exc})"
    return value, None


def _check_prompt_registry(
    errors: list[str],
    warnings: list[str],
    *,
    prompts_dir: Path | None = None,
    registry_path: Path | None = None,
) -> None:
    prompts_dir = prompts_dir or PROMPTS_DIR
    registry_path = registry_path or PROMPT_REGISTRY_PATH
    if not prompts_dir.is_dir():
        return
    value, error = _load_prompt_registry(registry_path)
    if error is not None:
        errors.append(error)
        return
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        errors.append("提示词记账非法: registry.yaml 须为 schema_version: 1 的映射")
        return
    entries = value.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("提示词记账非法: registry.yaml 缺非空 entries 列表")
        return
    referenced: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("提示词记账非法: entries 含非映射条目")
            continue
        missing_keys = [key for key in _REGISTRY_REQUIRED_KEYS if not str(entry.get(key) or "").strip()]
        if missing_keys and entry.get("change") != "removed":
            errors.append(
                f"提示词记账非法: 条目 {entry.get('id') or entry.get('name') or '?'} 缺字段 {','.join(missing_keys)}"
            )
        if entry.get("change") not in _REGISTRY_CHANGE_VALUES:
            errors.append(
                f"提示词记账非法: 条目 {entry.get('id') or '?'} change 须 ∈ {sorted(_REGISTRY_CHANGE_VALUES)}"
            )
        file_ref = str(entry.get("file") or "").strip().replace("\\", "/").lstrip("./")
        if not file_ref.startswith("prompts/"):
            errors.append(
                f"提示词记账非法: 条目 {entry.get('id') or '?'} file 须为 prompts/ 相对路径，得到 {entry.get('file')!r}"
            )
            continue
        referenced.add(file_ref)
    for path in sorted(prompts_dir.glob("*.md")):
        relative = f"prompts/{path.name}"
        if relative not in referenced:
            errors.append(f"提示词记账缺失: {relative} 无任何 registry 条目引用（prompt 变更必须记账）")
    for file_ref in sorted(referenced - {f"prompts/{p.name}" for p in prompts_dir.glob("*.md")}):
        warnings.append(f"提示词记账陈旧: {file_ref} 已不存在于 prompts/（仅提示，不阻断）")


# 路由可达性显式豁免：有意不进路由地图的 02/03 风格（点名词源/低频场景）。
# 收敛纪律：只缩不增——新增豁免必须写明理由。
ROUTE_REACH_EXEMPT: frozenset[str] = frozenset({
    # （当前为空：全部 02/03 风格经命名/组级桥注/家族主风格代达可达）
})


def _check_route_reachability(errors: list[str]) -> None:
    """7. 路由可达性：canonical taxonomy 中带行业/场景的风格必须可定位。

    旧目录的 02/03 组级桥注已经被 canonical taxonomy 取代；canonical authored
    seeds 允许通过行业词的路由桥接，迁移资产仍由配对索引和 catalog 管理。
    """
    routing = ROUTING_PATH
    if not routing.is_file():
        return
    text = routing.read_text(encoding="utf-8")
    for path, brief in _brief_records():
        taxonomy = brief.get("taxonomy") if isinstance(brief.get("taxonomy"), dict) else {}
        dimensions = [
            str(value).strip()
            for key in ("industries", "scenarios")
            for value in taxonomy.get(key, [])
            if str(value).strip()
        ]
        if not dimensions:
            continue
        name = str(brief.get("name") or path.parent.name)
        if name in ROUTE_REACH_EXEMPT or name in text:
            continue
        # A category row is a valid bridge for a seed whose display name is
        # intentionally not repeated in every route row.
        if any(dimension in text for dimension in dimensions):
            continue
        variant_primary = str(brief.get("variant_of") or "").strip()
        if variant_primary and variant_primary in text:
            continue
        errors.append(
            f"路由不可达: {path.relative_to(STYLES_ROOT)} —— 路由文档无命名/"
            f"行业或场景桥接/主风格代达（variant_of={variant_primary or '无'}）"
        )


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    _check_pairing(errors)
    _check_chart_warnings(errors)
    _check_brand_verified(errors)
    _check_routing(errors)
    _check_text_anchor(errors)
    _check_prompt_registry(errors, warnings)
    _check_route_reachability(errors)
    print(f"governance errors={len(errors)} warnings={len(warnings)}")
    for item in errors[:20]:
        print(f"  ✗ {item}")
    if len(errors) > 20:
        print(f"  ~ … 其余 {len(errors) - 20} 条")
    for item in warnings[:20]:
        print(f"  ⚠ {item}")
    if len(warnings) > 20:
        print(f"  ~ … 其余 {len(warnings) - 20} 条警告")
    if not errors:
        print("OK")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
