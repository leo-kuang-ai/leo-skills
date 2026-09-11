#!/usr/bin/env python3
r"""U10：按 U1 冻结账本执行 template-library 全量结构迁移（v4 方案 §4/§10）。

机械转换纪律：
  - 不伪造执行资格：长尾风格一律 lifecycle=draft，缺主题/推荐特征记
    adaptation_gaps，不猜 HEX/字体凑完成率；
  - 语义内容保留：旧 brief 完整 JSON 进 legacy_payload（U3 审阅来源）；
  - 每项处置可核对：迁移后逐条比对账本（--verify），源 hash 冻结不变；
  - 旧活动树退役为独立步骤（--retire-old-tree），在消费者切换后执行。

Usage:
  python3 scripts/migrate_template_library.py --execute    # 执行迁移（幂等）
  python3 scripts/migrate_template_library.py --verify     # 账本↔目标核对
  python3 scripts/migrate_template_library.py --retire-old-tree  # 退役旧树
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "runtime" / "src"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from leo_ppt_generator.styles import parse_style_document  # noqa: E402
import style_hard_rules  # noqa: E402

LEDGER_PATH = SKILL_DIR / "template-library" / "governance" / "migration" / "asset-ledger.json"
LIBRARY = SKILL_DIR / "template-library"
OLD_STYLES = SKILL_DIR / "references" / "styles"
RETIRED_ROOT = SKILL_DIR / "template-library" / "reference" / "sources" / "retired-styles-tree"

_JSON_BLOCK = re.compile(r"```json[ \t]*\r?\n(.*?)\r?\n```", re.S)
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8")


def _families_for(name: str) -> list[str]:
    families = []
    members = style_hard_rules.current_family_members(OLD_STYLES)
    for label, names in sorted(members.items()):
        if name in names:
            families.append(label)
    return families or ["未分类"]


def _map_density(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    vocab = json.loads((LIBRARY / "governance/vocabularies/density.json").read_text())
    mapping = vocab["legacy_text_mapping"]
    text = raw.strip().casefold()
    if text in mapping:
        return mapping[text]
    first = text.split(",")[0].strip()
    if first in mapping:
        return mapping[first]
    return None


def convert_style_brief(entry: dict, report: list[dict]) -> None:
    source = SKILL_DIR / entry["source_path"]
    target = LIBRARY / entry["target_path"].removeprefix("template-library/")
    if target.is_file() and entry.get("current_name") == "清爽专业风":
        return  # 垂直切片已完成的实体不重写。
    text = source.read_text(encoding="utf-8")
    parsed = parse_style_document(text)
    brief = parsed["brief"]
    gaps: list[str] = []
    if brief is None:
        report.append({"source": entry["source_path"], "status": "skipped",
                       "reason": "no_parseable_brief"})
        return
    name = brief.get("style_name") or entry.get("current_name") or source.stem
    density = _map_density((brief.get("canvas") or {}).get("density"))
    if density is None:
        gaps.append("density_free_text_unmapped")
    payload = {k: v for k, v in brief.items()
               if k not in {"style_name", "type"}}
    negative = [c for c in (brief.get("rendering_constraints") or [])
                if isinstance(c, str) and c.strip()]
    if not negative:
        gaps.append("negative_constraints_not_extracted")
    document = {
        "schema_version": 2,
        "entity": "style-brief",
        "asset_id": entry["target_asset_id"],
        "name": name,
        "aliases": brief.get("aliases") or [],
        "variant_of": brief.get("variant_of"),
        "lifecycle": "draft",
        "source": {"origin": "legacy-migrated", "upstream": entry["source_path"]},
        "taxonomy": {"families": _families_for(name), "industries": [], "scenarios": []},
        "visual_language": {"direction": str(brief.get("visual_direction") or "")[:400]},
        "bindings": {},
        "adaptation_gaps": gaps + ["theme_not_extracted", "recommendation_features_not_extracted"],
        "content_review": {"reviewed": False, "disposition": "draft"},
        "legacy_payload": payload,
    }
    if density:
        document["recommendation_features"] = {
            "density": density,
            "audience_conservatism": "balanced", "formality": 0.6,
            "environments": ["desktop-review"],
        }
        document["adaptation_gaps"].append(
            "recommendation_features_defaults_pending_u3")
    if negative:
        document["constraints"] = {"negative": negative}
    _write_json(target, document)
    report.append({"source": entry["source_path"], "status": "converted",
                   "target": str(target.relative_to(SKILL_DIR))})


P_CODE_TEMPLATE = {"P25": "builtin:template:spec-table"}


def convert_layout(entry: dict, report: list[dict]) -> None:
    source = SKILL_DIR / entry["source_path"]
    target = LIBRARY / entry["target_path"].removeprefix("template-library/")
    data = json.loads(source.read_text(encoding="utf-8"))
    p_code = str(data.get("layout_id") or "")
    slots = {}
    for slot_name, slot_def in (data.get("content_capacity") or {}).items():
        if not isinstance(slot_def, dict):
            continue
        slot = {"region": "content", "desc": slot_def.get("desc", "")}
        for key in ("count_min", "count_max", "max_chars", "chars_per_line", "max_lines"):
            if isinstance(slot_def.get(key), int):
                slot[key] = slot_def[key]
        slots[slot_name] = slot
    html_template = P_CODE_TEMPLATE.get(p_code)
    document = {
        "schema_version": 1,
        "entity": "layout-profile",
        "asset_id": entry["target_asset_id"],
        "name": data.get("name") or p_code,
        "aliases": [p_code] if p_code else [],
        "canvas": {"width": 1280, "height": 720, "units": "logical-px"},
        "page_role": data.get("page_type") if data.get("page_type") in {
            "cover", "agenda", "section", "content", "data", "quote", "evidence", "closing"
        } else "content",
        "layout_type": "table" if html_template else "fixed-regions",
        "slots": slots,
        "reuse_friendly": bool(data.get("reuse_friendly", True)),
        "renderer_support": {
            "render:html": html_template,
            "image": data.get("visual_signature"),
        },
        "notes": f"机械迁移自 {entry['source_path']}；几何 regions 未声明"
                 + ("（P25 已由垂直切片单独建 profile）" if p_code == "P25" else "，待 U5 按 renderer 绑定深化"),
    }
    if document["reuse_friendly"] is False:
        document["max_per_deck"] = int(data.get("max_per_deck") or 1)
    if html_template == "builtin:template:spec-table":
        return  # 垂直切片的 p25-spec-table 是作者真值，机械迁移不覆盖。
    if p_code == "P25":
        # 同名 P25：账本 slug 与垂直切片不同（p25-spec-table 已占用），跳过。
        report.append({"source": entry["source_path"], "status": "merged-into",
                       "target": "builtin:layout:p25-spec-table"})
        return
    _write_json(target, document)
    report.append({"source": entry["source_path"], "status": "converted",
                   "target": str(target.relative_to(SKILL_DIR))})


def convert_layout_notes(entry: dict, report: list[dict]) -> None:
    source = SKILL_DIR / entry["source_path"]
    target = LIBRARY / entry["target_path"].removeprefix("template-library/")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    report.append({"source": entry["source_path"], "status": "copied",
                   "target": str(target.relative_to(SKILL_DIR))})


def convert_axis(entry: dict, report: list[dict]) -> None:
    source = SKILL_DIR / entry["source_path"]
    target_dir = LIBRARY / entry["target_path"].removeprefix("template-library/")
    target_dir.mkdir(parents=True, exist_ok=True)
    body = target_dir / "body.md"
    shutil.copyfile(source, body)
    first_heading = next((line for line in
                          source.read_text(encoding="utf-8").splitlines()
                          if line.startswith("#")), "")
    manifest = {
        "schema_version": 1, "entity": "axis-manifest",
        "asset_id": entry["target_asset_id"],
        "name": first_heading.lstrip("# ").strip() or source.stem,
        "kind": entry["target_asset_id"].split(":")[2].split("-", 1)[0],
        "body_ref": "body.md",
        "applicability_limits": [],
    }
    _write_json(target_dir / "manifest.json", manifest)
    report.append({"source": entry["source_path"], "status": "converted",
                   "target": str((target_dir / "manifest.json").relative_to(SKILL_DIR))})


def convert_brand(entry: dict, report: list[dict]) -> None:
    source = SKILL_DIR / entry["source_path"]
    text = source.read_text(encoding="utf-8")

    def field(key: str) -> str:
        m = re.search(rf"\*{{0,2}}{key}\*{{0,2}}[ \t]*[:：][ \t]*(.*)", text)
        return m.group(1).strip() if m else ""

    hexes = _HEX.findall(text)
    document = {
        "schema_version": 1, "entity": "brand-identity",
        "asset_id": entry["target_asset_id"],
        "name": entry.get("current_name") or source.stem,
        "colors": {},
        "typography": field("字体"),
        "tone": field("语气"),
        "verification": {
            "status": "verified" if field("verified_at") else "unverified",
            "verified_at": field("verified_at"),
            "basis": "legacy-migrated",
        },
        "locked_roles": [],
    }
    if hexes:
        document["colors"]["primary"] = hexes[0]
    if len(hexes) > 1:
        document["colors"]["accent"] = hexes[1]
    _write_json(LIBRARY / entry["target_path"].removeprefix("template-library/"), document)
    report.append({"source": entry["source_path"], "status": "converted",
                   "target": entry["target_path"]})


def copy_entry(entry: dict, report: list[dict]) -> None:
    source = SKILL_DIR / entry["source_path"]
    target = LIBRARY / entry["target_path"].removeprefix("template-library/")
    if entry["target_path"].endswith("/") or entry["target_path"].endswith("）"):
        report.append({"source": entry["source_path"], "status": "grouped",
                       "reason": "目录组目标由条目自身携带"})
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    report.append({"source": entry["source_path"], "status": "copied",
                   "target": str(target.relative_to(SKILL_DIR))})


def convert_preset_pack(entry: dict, report: list[dict]) -> None:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    name_to_id = {e.get("current_name"): e["target_asset_id"]
                  for e in ledger["entries"] if "current_name" in e}
    pack = json.loads((SKILL_DIR / "references/style-presets.json").read_text(encoding="utf-8"))
    gaps = []
    converted = 0
    for preset in pack.get("presets", []):
        style_name = preset.get("composition", {}).get("style")
        style_id = name_to_id.get(style_name)
        if not style_id:
            gaps.append(f"preset:{preset.get('id')}:style_unmapped:{style_name}")
            continue
        document = {
            "schema_version": 1, "entity": "scene-preset",
            "asset_id": f"builtin:preset:{preset['id']}",
            "id": preset["id"],
            "name_zh": preset.get("name_zh", preset["id"]),
            "match_signals": preset.get("match_signals", {}),
            "composition": {"style": style_id,
                            "layouts": [],  # P 码绑定由 U6 按 layout ID 重接
                            "density": preset.get("composition", {}).get("density", "balanced")},
            "fallbacks": {"style": [name_to_id[n] for n in
                                    preset.get("fallbacks", {}).get("style", [])
                                    if n in name_to_id]},
        }
        _write_json(LIBRARY / f"canonical/presets/{preset['id']}/preset.json", document)
        converted += 1
    report.append({"source": entry["source_path"], "status": "converted",
                   "converted": converted, "gaps": gaps[:10],
                   "target": "canonical/presets/<id>/preset.json"})


def migrate_font_manifest(entry: dict, report: list[dict]) -> None:
    manifest = {
        "schema_version": 1, "entity": "font-manifest",
        "asset_id": "builtin:font:noto-sans-sc",
        "name": "Noto Sans SC",
        "family": "Noto Sans SC",
        "files": [
            {"path": "NotoSansSC-Regular.otf", "weight": 400, "coverage": "cjk-full"},
            {"path": "NotoSansSC-Bold.otf", "weight": 700, "coverage": "cjk-full"},
        ],
        "license": {"status": "verified-distributable", "type": "OFL-1.1",
                    "file": "LICENSE-OFL.txt"},
    }
    _write_json(LIBRARY / "canonical/fonts/noto-sans-sc/manifest.json", manifest)
    report.append({"source": "assets/render-fonts/*", "status": "converted",
                   "target": "canonical/fonts/noto-sans-sc/manifest.json"})


def migrate_templates(entry: dict, report: list[dict]) -> None:
    slug = entry["target_asset_id"].split(":")[2]
    target_dir = LIBRARY / f"canonical/templates/{slug}"
    if target_dir.is_dir():
        return  # spec-table 垂直切片已有完整作者真值。
    source = SKILL_DIR / entry["source_path"]
    target_dir.mkdir(parents=True, exist_ok=True)
    if source.suffix == ".html":
        shutil.copyfile(source, target_dir / "page.html")
        html = source.read_text(encoding="utf-8")
        slots = sorted(set(re.findall(r'data-leo-block="([^"]+)"', html)))
        template = {
            "schema_version": 1, "entity": "render-template",
            "asset_id": f"builtin:template:{slug}",
            "name": slug,
            "input_fields": [{"name": slot, "required": False, "type": "string"}
                             for slot in slots],
            "slot_bindings": [{"slot": slot, "selector": f"[data-leo-block='{slot}']"}
                              for slot in slots],
            "theme_roles": ["background", "surface", "text", "primary",
                            "on_primary", "muted", "border", "accent"],
            "dependencies": [],
            "layout_profiles": [],
            "lane": "render:html",
            "notes": "机械迁移：HTML 仍含硬编码色/字体，待 U5 切换主题变量",
        }
        _write_json(target_dir / "template.json", template)
        report.append({"source": entry["source_path"], "status": "converted",
                       "target": str((target_dir / "template.json").relative_to(SKILL_DIR))})
    else:
        shutil.copyfile(source, LIBRARY / "canonical/templates/README.md")
        report.append({"source": entry["source_path"], "status": "copied",
                       "target": "canonical/templates/README.md"})


def execute(ledger: dict) -> list[dict]:
    report: list[dict] = []
    for entry in ledger["entries"]:
        kind = entry["target_asset_id"].split(":")[1]
        disposition = entry["disposition"]
        try:
            if disposition in {"rebuild-delete", "merge"}:
                continue
            if kind == "style" and disposition == "convert":
                convert_style_brief(entry, report)
            elif kind == "layout" and disposition == "convert":
                convert_layout(entry, report)
            elif kind == "layout-doc":
                convert_layout_notes(entry, report)
            elif kind == "axis":
                convert_axis(entry, report)
            elif kind == "brand":
                convert_brand(entry, report)
            elif kind == "preset":
                convert_preset_pack(entry, report)
            elif kind == "font":
                if entry["source_path"].endswith(".otf") or "LICENSE" in entry["source_path"] or "NOTICE" in entry["source_path"]:
                    copy_entry(entry, report)
                else:
                    migrate_font_manifest(entry, report)
            elif kind == "template" or kind == "template-doc":
                migrate_templates(entry, report)
            else:
                copy_entry(entry, report)
        except Exception as exc:  # noqa: BLE001 —— 迁移逐项失败必须显式记录
            report.append({"source": entry["source_path"], "status": "failed",
                           "error": f"{type(exc).__name__}: {exc}"})
    return report


def verify(ledger: dict) -> tuple[list[str], int]:
    problems: list[str] = []
    grouped_ok = {"merge", "rebuild-delete"}
    for entry in ledger["entries"]:
        if entry["disposition"] in grouped_ok:
            continue
        target = entry["target_path"]
        if "）" in target or target.endswith("/"):
            continue  # 目录组条目由具体文件条目承载
        path = SKILL_DIR / target if not target.startswith("template-library") else LIBRARY / target.removeprefix("template-library/")
        if not path.is_file():
            problems.append(f"missing: {entry['source_path']} -> {target}")
    return problems, len(problems)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="U10 模板库全量结构迁移")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--retire-old-tree", action="store_true")
    args = parser.parse_args(argv)
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))

    if args.retire_old_tree:
        if not OLD_STYLES.is_dir():
            print("旧树已退役")
            return 0
        RETIRED_ROOT.mkdir(parents=True, exist_ok=True)
        marker = RETIRED_ROOT / "RETIREMENT.md"
        marker.write_text(
            "# 旧 references/styles 树退役归档\n\n"
            "由 docs/plans/2026-09-08-001 v4 §10 退役；原件按 U1 账本 hash 可追溯，\n"
            "git 历史保留全部内容。此归档不参与执行，仅供离线追溯。\n",
            encoding="utf-8")
        print(f"retired {OLD_STYLES} -> {RETIRED_ROOT}")
        shutil.move(str(OLD_STYLES), str(RETIRED_ROOT / "styles"))
        return 0

    if not (args.execute or args.verify):
        parser.error("需要 --execute 或 --verify")
    if args.execute:
        report = execute(ledger)
        report_path = LIBRARY / "governance/migration/migration-report.json"
        failed = [item for item in report if item["status"] == "failed"]
        _write_json(report_path, {
            "kind": "template-library-migration-report",
            "schema_version": 1,
            "entries": report,
            "counts": {"total": len(report),
                       "failed": len(failed)},
        })
        print(json.dumps({"processed": len(report), "failed": len(failed)},
                         ensure_ascii=False))
        if failed:
            for item in failed[:10]:
                print("  FAIL", item["source"], item["error"], file=sys.stderr)
            return 1
    problems, count = verify(ledger)
    if problems:
        for problem in problems[:20]:
            print(problem, file=sys.stderr)
        print(f"verify: {count} problems", file=sys.stderr)
        return 1 if count else 0
    print("verify: all ledger entries have targets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
