#!/usr/bin/env python3
r"""U1 基线冻结：全量模板资产账本 + 消费者闭包（template-rebuild v4）。

唯一方案：docs/plans/2026-09-08-001-feat-leo-ppt-template-quality-plan.md §4/U1。

职责（机械冻结，不做语义审阅——语义处置归 U3）：
  1. 枚举 leo-ppt-generator 内全部模板域源资产（references/styles 源集合、
     版式/品牌/轴/参考池、presets、render-templates、render-fonts、
     render-lint-rules、samples 画廊与 reference-golden、模板域 runtime schema），
     按当前 dirty worktree 实际文件 sha256 冻结。
  2. 为每项资产分配类型化稳定 ID（builtin:<kind>:<slug>）与目标路径
     （template-library 五区），记录处置（convert/migrate-as-is/merge/
     to-reference/rebuild-delete）与 owner 单元。
  3. 扫描消费者闭包：哪些源码/脚本/文档消费旧路径或旧 API，各自由哪个
     单元负责切换。
  4. 落盘 template-library/governance/migration/{asset-ledger.json,
     consumers.json, freeze-manifest.json}；summary 文档另由维护者核对后
     写入 docs/leo-ppt-generator/template-rebuild-baseline.md。

ID 规则（KTD4，一次分配后登记即稳定）：
  - 顶层 11 风格使用显式英文 slug（TOPLEVEL_STYLE_SLUGS）；
  - 其余 slug = 文件 stem 规范化（ASCII kebab-case；非 ASCII 保留原文，
    UTF-8 路径安全；冲突加 -2 序号）；
  - §8.1 九方向种子 slug（management-clear 等）保留给 U3 新增种子，
    机械分配不得占用。

确定性：路径排序、无时间戳、固定键序。重复运行同树输出逐字节一致。

Usage:
  python3 scripts/freeze_template_rebuild_baseline.py [--root DIR] [--check]

--check 只读校验既有账本与当前树一致（漂移即非零退出）。
Exit: 0 ok; 1 drift/check-fail; 2 usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))

from leo_ppt_generator.styles import describe_style_asset  # noqa: E402

STYLES_DIR = Path("references") / "styles"
LEDGER_DIR = Path("template-library") / "governance" / "migration"

# 顶层 11 风格的显式 slug（§5.1 示例 builtin:style:clean-professional）。
TOPLEVEL_STYLE_SLUGS = {
    "清爽专业风": "clean-professional",
    "党政红风格": "official-red-classic",
    "创意杂志风": "creative-magazine",
    "复古扁平插画风": "retro-flat-illustration",
    "手绘技术解释风": "handdrawn-tech-explainer",
    "手绘白板风": "handdrawn-whiteboard",
    "教学课件风": "teaching-courseware",
    "数据仪表盘风": "data-dashboard",
    "温暖手工风": "warm-handcraft",
    "电子墨水杂志风": "eink-magazine",
    "科研答辩风": "research-defense",
}

# §8.1 九方向种子 slug 保留给 U3，机械分配冲突时拒绝而非改写。
RESERVED_SEED_SLUGS = {
    "management-clear", "finance-navy", "consulting-pyramid", "tech-dark",
    "gov-red", "health-clean", "edu-bright", "brand-creative", "academic-austere",
}

# 12_版式库 中非版式的规则文档（→ governance/rules/layouts/）。
LAYOUT_RULE_DOCS = {
    "00_容量档位参考", "00_选版式P0原则", "01_常犯错误", "02_关键类清单",
}

AXIS_GROUPS = {
    "06_论证模式": "argument",
    "07_信息图类型": "infographic",
    "08_图片渲染": "rendering",
    "09_结构布局": "structure",
    "11_图表语法": "chart",
    "13_页面语义": "page-semantics",
}

# 模板域 runtime schema（迁 governance/schemas；其余 schema 保持原 owner）。
TEMPLATE_SCHEMAS = (
    "style-brief-v1.schema.json",
    "style-index-v1.schema.json",
    "layout-bank-v1.schema.json",
)

RENDER_TEMPLATES = (
    "cover-basic", "body-basic", "compare", "timeline",
    "spec-table", "pull-quote", "frame-shot",
)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slugify(stem: str) -> str:
    text = stem.strip()
    if text.isascii():
        text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
        return text or "unnamed"
    return text


def _assign_slug(stem: str, used: dict[str, int], explicit: str | None = None) -> str:
    base = explicit or _slugify(stem)
    if base in RESERVED_SEED_SLUGS and explicit is None:
        base = base + "-legacy"
    count = used.get(base, 0)
    used[base] = count + 1
    return base if count == 0 else f"{base}-{count + 1}"


def _entry(source: Path, rel: str, *, kind: str, slug: str, target: str,
           disposition: str, basis: str, owner: str, role: str | None = None,
           note: str | None = None, body_sha: str | None = None,
           current_name: str | None = None) -> dict:
    entry = {
        "source_path": rel,
        "file_sha256": body_sha or _hash_file(source),
        "bytes": source.stat().st_size,
        "current_role": role,
        "target_asset_id": f"builtin:{kind}:{slug}",
        "target_path": target,
        "disposition": disposition,
        "disposition_basis": basis,
        "owner_unit": owner,
        "review_status": "pending-u3" if kind in {"style", "theme", "brand", "preset"} else "frozen-mechanical",
    }
    if current_name:
        entry["current_name"] = current_name
    if note:
        entry["note"] = note
    return entry


def build_styles_entries(root: Path, used: dict[str, int]) -> list[dict]:
    styles_root = root / STYLES_DIR
    entries: list[dict] = []
    if not styles_root.is_dir():
        raise ValueError("styles_source_missing")
    for path in sorted(styles_root.rglob("*")):
        if not path.is_file():
            continue
        rel_from_styles = path.relative_to(styles_root)
        parts = rel_from_styles.parts
        if any(part in {"generated", "generated.previous"} or part.startswith(".style-index-")
               for part in parts):
            continue
        rel = (STYLES_DIR / rel_from_styles).as_posix()
        top = parts[0] if len(parts) > 1 else ""
        stem = path.stem
        described = describe_style_asset(path, styles_root, scope="builtin")
        role = described["asset_role"]
        name = described.get("name") or stem

        if len(parts) == 1:  # 顶层
            if path.suffix == ".md":
                slug = _assign_slug(stem, used, TOPLEVEL_STYLE_SLUGS.get(stem))
                entries.append(_entry(
                    path, rel, kind="style", slug=slug,
                    target=f"template-library/canonical/styles/{slug}/brief.json",
                    disposition="convert", basis="toplevel_brief_md_to_json",
                    owner="U3", role=role, current_name=name,
                    note="MD 内嵌 JSON 块 → 纯 JSON 真值；名称/别名保留为属性"))
            else:  # 顶层 .layouts.json 薄路由 → 并入对应 brief
                style_stem = stem[:-len(".layouts")] if stem.endswith(".layouts") else stem
                style_slug = TOPLEVEL_STYLE_SLUGS.get(style_stem, _slugify(style_stem))
                entries.append(_entry(
                    path, rel, kind="style-route", slug=style_slug + "-routes",
                    target=f"template-library/canonical/styles/{style_slug}/brief.json#bindings.layout_routes",
                    disposition="merge", basis="toplevel_layouts_sidecar_merge",
                    owner="U3", role="layout",
                    note="routing/capacity_factor 并入 brief.bindings；容量因子归实际 layout profile"))
            continue

        if top == "00_索引":
            entries.append(_entry(
                path, rel, kind="index-doc", slug=_assign_slug(stem, used),
                target=f"template-library/governance/authoring/index/{stem}.md",
                disposition="convert", basis="index_doc_split",
                owner="U10", role=role,
                note="作者保留部分迁 governance/authoring；手工计数与成员双真值由 catalog 重建替代"))
        elif top == "02_行业内容域" and stem == "_content_rules":
            industry = parts[1] if len(parts) > 2 else "default"
            entries.append(_entry(
                path, rel, kind="rule", slug=_assign_slug(f"domain-{industry}", used),
                target=f"template-library/governance/rules/domains/{industry}/content-rules.md",
                disposition="convert", basis="content_rules_to_governance",
                owner="U3", role="rule", note="行业内容规则语义不变；任务 domain 显式关联"))
        elif top in AXIS_GROUPS:
            group = AXIS_GROUPS[top]
            slug = _assign_slug(f"{group}-{stem}", used)
            entries.append(_entry(
                path, rel, kind="axis", slug=slug,
                target=f"template-library/canonical/axes/{group}/{slug}/",
                disposition="convert", basis="axis_doc_with_manifest",
                owner="U3", role=role,
                note="正文引用 + 显式 manifest；去掉标题嗅探（templates.py 逐目录硬编码改为 manifest/ID 解析）"))
        elif top == "10_品牌身份":
            slug = _assign_slug(stem, used)
            entries.append(_entry(
                path, rel, kind="brand", slug=slug,
                target=f"template-library/canonical/brands/{slug}/brand.json",
                disposition="convert", basis="brand_field_md_to_json",
                owner="U3", role=role, note="保留核验状态字段，不冒称官方 VI"))
        elif top == "12_版式库":
            if path.suffix == ".json":
                layout_id = _layout_id_of(path)
                slug = _assign_slug(_layout_slug(layout_id, path), used)
                entries.append(_entry(
                    path, rel, kind="layout", slug=slug,
                    target=f"template-library/canonical/layouts/{slug}/layout.json",
                    disposition="convert", basis="layout_sidecar_geometry_truth",
                    owner="U5", role="layout",
                    note="几何真值唯一化：capacity/slot/renderer 支持进入 layout.json；MD 骨架并入同目录说明"))
            elif stem in LAYOUT_RULE_DOCS:
                entries.append(_entry(
                    path, rel, kind="rule", slug=_assign_slug(f"layout-{stem}", used),
                    target=f"template-library/governance/rules/layouts/{stem}.md",
                    disposition="convert", basis="layout_rule_doc",
                    owner="U5", role=role))
            else:
                # 版式 MD：几何真值并入对应 layout.json（与同名 sidecar 合并）。
                layout_slug = _layout_slug(_layout_id_of(path.with_suffix(".layouts.json")), path) \
                    if path.with_suffix(".layouts.json").is_file() else _slugify(stem)
                entries.append(_entry(
                    path, rel, kind="layout-doc", slug=_assign_slug(layout_slug + "-notes", used),
                    target=f"template-library/canonical/layouts/{layout_slug}/notes.md",
                    disposition="merge", basis="layout_md_prose_merge",
                    owner="U5", role=role,
                    note="用途/骨架散文保留为 notes；机器可读部分以 layout.json 为准"))
        elif top == "14_参考池_gpt-image2":
            entries.append(_entry(
                path, rel, kind="pool", slug=_assign_slug(stem, used),
                target=f"template-library/reference/pools/gpt-image2/{stem}.md",
                disposition="migrate-as-is", basis="reference_pool_preserve",
                owner="U10", role="pool", note="不再作为整体风格执行"))
        elif top in {"04_来源_guizang", "05_来源_awesome-gpt-image-2",
                     "15_来源_officecli", "16_来源_slides-grab"}:
            source_name = top.split("_", 1)[1]
            if role == "style":
                slug = _assign_slug(stem, used)
                entries.append(_entry(
                    path, rel, kind="style", slug=slug,
                    target=f"template-library/canonical/styles/{slug}/brief.json",
                    disposition="convert", basis="source_dir_brief_review",
                    owner="U3", role=role, current_name=name,
                    note="来源目录按实体真实角色处置；U3 逐项语义审阅后定 draft/active"))
            else:
                slug = _assign_slug(stem, used)
                entries.append(_entry(
                    path, rel, kind="reference", slug=slug,
                    target=f"template-library/reference/sources/{source_name}/{stem}.md",
                    disposition="to-reference", basis="source_dir_non_brief",
                    owner="U10", role=role))
        else:
            # 01 通用 / 02 行业（除规则）/ 03 场景：完整 brief → styles（draft），其余 → candidates。
            if role == "style":
                slug = _assign_slug(stem, used)
                entries.append(_entry(
                    path, rel, kind="style", slug=slug,
                    target=f"template-library/canonical/styles/{slug}/brief.json",
                    disposition="convert", basis="complete_brief_to_canonical_draft",
                    owner="U3", role=role, current_name=name,
                    note="lifecycle=draft 待 U3 审阅；不做执行资格假设"))
            else:
                slug = _assign_slug(stem, used)
                entries.append(_entry(
                    path, rel, kind="reference", slug=slug,
                    target=f"template-library/reference/candidates/{stem}.md",
                    disposition="to-reference", basis="incomplete_or_prose_to_candidates",
                    owner="U3", role=role,
                    note="信息不足/散文文档显式转参考，不凑字段晋升"))
    return entries


_LAYOUT_ID_RE = re.compile(r'"layout_id"\s*:\s*"(P\d+)"')


def _layout_id_of(sidecar: Path) -> str:
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return str(data.get("layout_id") or sidecar.stem)
    except (OSError, ValueError):
        return sidecar.stem


def _layout_slug(layout_id: str, path: Path) -> str:
    # P 码 + 可读名：p25-spec-table 风格（P 码保留为别名，绑定用 ID）。
    name = re.sub(r"[^\w]+", "-", path.stem).strip("-")
    code = layout_id.lower()
    if name.lower().startswith(code.lower() + "-") or name.lower() == code.lower():
        return name.lower() if name.isascii() else code
    return f"{code}-{name}".lower() if name.isascii() else code


def build_supplementary_entries(root: Path, used: dict[str, int]) -> list[dict]:
    entries: list[dict] = []

    def add(rel: str, **kwargs):
        path = root / rel
        if not path.is_file():
            raise ValueError(f"supplementary_asset_missing: {rel}")
        entries.append(_entry(path, rel, **kwargs))

    # generated/ 派生物：catalog 重建，不当真值。
    generated = root / STYLES_DIR / "generated"
    if generated.is_dir():
        for path in sorted(generated.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                entries.append(_entry(
                    path, rel, kind="derived", slug=_assign_slug(path.stem, used),
                    target="template-library/catalog/（由 capability_manifest 重建）",
                    disposition="rebuild-delete", basis="derived_not_truth",
                    owner="U10", role="reference",
                    note="旧派生文件不迁移；新 catalog 从 canonical 重建"))

    add("references/style-presets.json", kind="preset", slug=_assign_slug("scene-presets", used),
        target="template-library/canonical/presets/scene-presets/preset.json",
        disposition="convert", basis="preset_json_authoring_source",
        owner="U3", role="reference", note="JSON 唯一作者源；生成说明分离")
    add("references/style-presets.md", kind="preset-doc", slug=_assign_slug("scene-presets-doc", used),
        target="template-library/canonical/presets/scene-presets/README.md",
        disposition="convert", basis="preset_doc_companion",
        owner="U3", role="reference")

    add("assets/render-lint-rules.json", kind="rule", slug=_assign_slug("render-lint-rules", used),
        target="template-library/governance/rules/render-lint-rules.json",
        disposition="migrate-as-is", basis="lint_rule_mapping",
        owner="U5", role="rule")

    for template in RENDER_TEMPLATES:
        add(f"template-library/canonical/templates/{template}/page.html", kind="template",
            slug=_assign_slug(template, used),
            target=f"template-library/canonical/templates/{template}/page.html",
            disposition="convert", basis="template_html_theme_switch",
            owner="U5", role="reference",
            note="HTML 保留 DOM 结构，改为消费主题角色 token + layout profile；移除硬编码色/字体/几何真值")

    for rel in ("assets/render-fonts/NotoSansSC-Regular.otf",
                "assets/render-fonts/NotoSansSC-Bold.otf",
                "assets/render-fonts/LICENSE-OFL.txt",
                "assets/render-fonts/NOTICE.md"):
        slug_map = {"NotoSansSC-Regular.otf": "noto-sans-sc-regular",
                    "NotoSansSC-Bold.otf": "noto-sans-sc-bold",
                    "LICENSE-OFL.txt": "noto-sans-sc-license",
                    "NOTICE.md": "noto-sans-sc-notice"}
        add(rel, kind="font", slug=_assign_slug(slug_map[Path(rel).name], used),
            target=f"template-library/canonical/fonts/noto-sans-sc/{Path(rel).name}",
            disposition="migrate-as-is", basis="font_file_registry",
            owner="U5", role="reference",
            note="manifest 登记字重/覆盖/许可（Regular/Bold 两字重；无衬线中文正文基线）")

    add("scripts/chart-palette-pool.json", kind="component",
        slug=_assign_slug("chart-palette-pool", used),
        target="template-library/canonical/components/chart-palettes/pool.json",
        disposition="convert", basis="chart_palette_pool_component",
        owner="U5", role="reference")

    # samples 画廊与 reference-golden：历史证据，不赋予新验证资格。
    for rel_dir, target_dir in (
        ("samples/style-gallery", "reference/historical-gallery/style-gallery"),
        ("samples/reference-golden", "reference/sources/reference-golden"),
    ):
        base = root / rel_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                target_rel = path.relative_to(base).as_posix()
                entries.append(_entry(
                    path, rel, kind="reference",
                    slug=_assign_slug(f"{Path(rel_dir).name}-{path.stem}", used),
                    target=f"template-library/{target_dir}/{target_rel}",
                    disposition="migrate-as-is", basis="historical_evidence_preserve",
                    owner="U10", role="reference",
                    note="原件保留为历史证据；不作为新风格还原证明"))
    add("samples/style-gallery.md", kind="reference",
        slug=_assign_slug("style-gallery-index", used),
        target="template-library/reference/historical-gallery/style-gallery/index.md",
        disposition="migrate-as-is", basis="historical_evidence_preserve",
        owner="U10", role="reference")
    for png in ("education-content-page.png", "finance-data-page.png", "government-cover.png"):
        rel = f"samples/{png}"
        if (root / rel).is_file():
            add(rel, kind="reference", slug=_assign_slug(png.rsplit(".", 1)[0], used),
                target=f"template-library/reference/historical-gallery/{png}",
                disposition="migrate-as-is", basis="historical_evidence_preserve",
                owner="U10", role="reference")

    for schema in TEMPLATE_SCHEMAS:
        add(f"runtime/src/leo_ppt_generator/schemas/{schema}", kind="schema",
            slug=_assign_slug(schema.removesuffix(".schema.json"), used),
            target=f"template-library/governance/schemas/{schema}",
            disposition="convert", basis="template_schema_to_governance",
            owner="U9", role="reference",
            note="v2 schema（style-brief-v2/render-theme-v1/layout/template）以治理区为唯一源；v1 保留为迁移输入")
    return entries


def build_consumers(root: Path) -> dict:
    """消费者闭包：旧路径/旧 API 的全部活动消费点与切换 owner。"""
    consumers = []
    scan_targets = [
        ("runtime/src/leo_ppt_generator", ".py"),
        ("scripts", ".py"),
    ]
    path_patterns = {
        "references/styles": "U10",
        "12_版式库": "U9",
        "08_图片渲染": "U9",
        "07_信息图类型": "U9",
        "06_论证模式": "U9",
        "10_品牌身份": "U9",
        "11_图表语法": "U9",
        "render-templates": "U10",
        "render-fonts": "U10",
        "style-presets": "U10",
        "style-gallery": "U10",
        "00_索引": "U10",
    }
    api_patterns = {
        "from .styles import": "U9",
        "from leo_ppt_generator.styles import": "U9",
        "from .templates import": "U9",
        "from leo_ppt_generator.templates import": "U9",
        "from .layout_bank import": "U9",
        "from leo_ppt_generator.layout_bank import": "U9",
        "builtin_style_path": "U9",
        "load_style(": "U9",
        "compose_style(": "U4",
        "compose_layout(": "U4",
        "load_layout(": "U4",
        "load_brand(": "U4",
        "paired_rendering(": "U4",
        "load_rendering(": "U4",
        "load_mode(": "U4",
        "load_image_type(": "U4",
        "layout_bank": "U9",
        "style_asset_inventory": "U10",
        "capability_manifest": "U10",
    }
    for scan_dir, suffix in scan_targets:
        base = root / scan_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob(f"*{suffix}")):
            if "__pycache__" in path.parts or ".venv" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            hits = {"paths": [], "apis": []}
            for pattern, owner in path_patterns.items():
                if pattern in text:
                    hits["paths"].append(pattern)
            for pattern, owner in api_patterns.items():
                if pattern in text:
                    hits["apis"].append(pattern)
            if hits["paths"] or hits["apis"]:
                consumers.append({
                    "consumer": path.relative_to(root).as_posix(),
                    "old_path_refs": sorted(set(hits["paths"])),
                    "old_api_refs": sorted(set(hits["apis"])),
                    "switch_owner": "U9" if hits["apis"] else "U10",
                })
    return {
        "kind": "template-rebuild-consumers",
        "schema_version": 1,
        "note": "grep 只作发现；切换验收按方案 §11 以 API/CLI、打包、干净安装、导入导出为准。",
        "consumers": consumers,
    }


def git_facts(root: Path) -> dict:
    def run(*args: str) -> str:
        try:
            return subprocess.run(("git", "-C", str(root), *args),
                                  capture_output=True, text=True, check=False).stdout.strip()
        except OSError:
            return ""
    return {
        "head": run("rev-parse", "HEAD") or None,
        "branch": run("branch", "--show-current") or None,
        "dirty_files": sorted(run("status", "--porcelain").splitlines()),
    }


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="U1 冻结全量模板资产账本（v4 方案）")
    parser.add_argument("--root", default=None)
    parser.add_argument("--check", action="store_true", help="只读校验账本与当前树一致")
    args = parser.parse_args(argv)
    root = (Path(args.root).expanduser().resolve() if args.root else SKILL_DIR)
    if not root.is_dir():
        print(f"根目录不存在: {root}", file=sys.stderr)
        return 2

    used: dict[str, int] = {}
    entries = build_styles_entries(root, used) + build_supplementary_entries(root, used)

    ids = [entry["target_asset_id"] for entry in entries]
    duplicates = sorted({asset_id for asset_id in ids if ids.count(asset_id) > 1})
    if duplicates:
        print("duplicate_asset_id: " + ", ".join(duplicates), file=sys.stderr)
        return 1
    source_paths = [entry["source_path"] for entry in entries]
    if len(source_paths) != len(set(source_paths)):
        print("duplicate_source_path", file=sys.stderr)
        return 1

    facts = git_facts(root)
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["target_asset_id"].split(":")[1]] = counts.get(entry["target_asset_id"].split(":")[1], 0) + 1
    dispositions: dict[str, int] = {}
    for entry in entries:
        dispositions[entry["disposition"]] = dispositions.get(entry["disposition"], 0) + 1

    ledger = {
        "kind": "template-rebuild-asset-ledger",
        "schema_version": 1,
        "plan": "docs/plans/2026-09-08-001-feat-leo-ppt-template-quality-plan.md",
        "freeze": facts,
        "counts": {"assets": len(entries), "by_kind": dict(sorted(counts.items())),
                   "by_disposition": dict(sorted(dispositions.items()))},
        "slug_rules": {
            "toplevel": "TOPLEVEL_STYLE_SLUGS 显式英文 slug",
            "others": "stem 规范化（ASCII kebab-case；非 ASCII 保留原文；冲突 -N 序号）",
            "reserved": sorted(RESERVED_SEED_SLUGS),
        },
        "entries": entries,
    }

    out_dir = root / LEDGER_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "asset-ledger.json"
    if args.check:
        try:
            existing = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print("ledger_missing_or_invalid", file=sys.stderr)
            return 1
        drift = [
            entry["source_path"] for entry in existing["entries"]
            for fresh in entries
            if entry["source_path"] == fresh["source_path"]
            and entry["file_sha256"] != fresh["file_sha256"]
        ]
        new_paths = {entry["source_path"] for entry in entries} - {
            entry["source_path"] for entry in existing["entries"]}
        gone_paths = {entry["source_path"] for entry in existing["entries"]} - {
            entry["source_path"] for entry in entries}
        if drift or new_paths or gone_paths:
            print(json.dumps({"drifted": drift[:20], "new": sorted(new_paths)[:20],
                              "gone": sorted(gone_paths)[:20]}, ensure_ascii=False))
            return 1
        print(f"ledger check ok: {len(entries)} assets, no drift")
        return 0

    consumers = build_consumers(root)
    (out_dir / "asset-ledger.json").write_bytes(_json_bytes(ledger))
    (out_dir / "consumers.json").write_bytes(_json_bytes(consumers))
    print(json.dumps({"assets": len(entries), "by_kind": ledger["counts"]["by_kind"],
                      "by_disposition": ledger["counts"]["by_disposition"],
                      "consumers": len(consumers["consumers"]),
                      "head": facts["head"], "dirty": len(facts["dirty_files"])},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
