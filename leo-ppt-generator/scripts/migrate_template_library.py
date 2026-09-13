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
import os
import re
import shutil
import sys
import tempfile
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


def _plan_digest(plan: dict) -> str:
    body = {k: v for k, v in plan.items() if k != "plan_digest"}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
        source = SKILL_DIR / entry.get("source_path", "")
        if not source.is_file() and entry.get("disposition") not in grouped_ok:
            problems.append(f"source_missing: {entry.get('source_path')}")
            continue
        if "）" in target or target.endswith("/"):
            continue  # 目录组条目由具体文件条目承载
        path = SKILL_DIR / target if not target.startswith("template-library") else LIBRARY / target.removeprefix("template-library/")
        if not path.is_file():
            problems.append(f"missing: {entry['source_path']} -> {target}")
    return problems, len(problems)


def publish_staged_manifest(library: Path, *, plan_digest: str,
                            delivery_root: Path | None = None) -> dict:
    """CAS-publish a verified shadow manifest under an exclusive maintenance lock."""
    from filelock import FileLock
    manifest_path = library / "governance/migration/staging-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("plan_digest") != plan_digest:
        raise ValueError("staging_manifest_plan_mismatch")
    shadow_root = Path(manifest.get("shadow_root", "")).resolve()
    if not shadow_root.is_dir():
        raise ValueError("staging_shadow_missing")
    delivery_root = (delivery_root or Path(__file__).resolve().parents[1]).resolve()
    journal_path = library / "governance/migration/publication-journal.json"
    journal = {"schema_version": 1, "plan_digest": plan_digest, "status": "started", "paths": []}
    _write_json(journal_path, journal)
    try:
        with FileLock(str(library / "governance/migration/maintenance.lock")):
            for item in manifest.get("entries", []):
                source = Path(item["path"]).resolve(); delivery = Path(item["delivery_path"]).resolve()
                if not source.is_file() or not source.is_relative_to(shadow_root):
                    raise ValueError("staged_file_missing:" + str(source))
                if delivery.is_symlink() or not delivery.is_relative_to(delivery_root):
                    raise ValueError("delivery_path_escape")
                current = hashlib.sha256(delivery.read_bytes()).hexdigest() if delivery.is_file() else None
                if current != item.get("delivery_sha256"):
                    raise ValueError("delivery_drift:" + str(delivery))
                delivery.parent.mkdir(parents=True, exist_ok=True)
                temporary = delivery.with_name("." + delivery.name + ".publish.tmp")
                shutil.copyfile(source, temporary)
                os.replace(temporary, delivery)
                journal["paths"].append({"path": str(delivery), "sha256": item["sha256"]})
            journal["status"] = "published"
            _write_json(journal_path, journal)
    except Exception:
        journal["status"] = "failed"
        _write_json(journal_path, journal)
        raise
    return journal


def cleanup_published(library: Path, plan: dict, receipt: dict,
                      delivery_root: Path | None = None) -> dict:
    """Delete only receipt-bound legacy files whose bytes still match preview."""
    if receipt.get("phase") != "published":
        raise ValueError("migration_receipt_not_published")
    if receipt.get("plan_digest") != _plan_digest(plan):
        raise ValueError("migration_receipt_plan_mismatch")
    allowlist = plan.get("delete_allowlist")
    if not isinstance(allowlist, list) or any(not isinstance(item, str) for item in allowlist):
        raise ValueError("delete_allowlist_invalid")
    snapshot = plan.get("source_snapshot", {}).get("files", {})
    root = (delivery_root or Path(__file__).resolve().parents[1]).resolve()
    deleted = []
    for relative in sorted(set(allowlist)):
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path.is_symlink():
            raise ValueError("cleanup_path_escape:" + relative)
        if not path.exists():
            continue
        expected = snapshot.get(relative)
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if expected is None or actual != expected:
            raise ValueError("cleanup_drift:" + relative)
        path.unlink()
        deleted.append(relative)
    return {"phase": "cleaned", "deleted": deleted, "allowlist_count": len(set(allowlist))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="U10 模板库全量结构迁移")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--retire-old-tree", action="store_true")
    parser.add_argument("--phase", choices=("preview", "stage", "verify", "publish", "cleanup"))
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args(argv)
    if args.phase:
        if args.phase == "preview":
            args.verify = True
        elif args.phase == "stage":
            args.execute = True
        elif args.phase == "cleanup":
            args.retire_old_tree = True
        elif args.phase == "publish":
            args.verify = True
        elif args.phase == "verify":
            args.verify = True
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    if args.plan:
        plan_path = args.plan
        if not plan_path.is_absolute():
            plan_path = SKILL_DIR / plan_path
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"无法读取 migration plan: {exc}")
        current_hash = hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest()
        if plan.get("ledger_sha256") != current_hash:
            parser.error("migration_plan_ledger_digest_mismatch")
        if plan.get("plan_digest") and plan.get("plan_digest") != _plan_digest(plan):
            parser.error("migration_plan_digest_mismatch")
    if args.phase == "preview":
        entries = ledger.get("entries", [])
        source_hashes = {}
        for entry in entries:
            src = SKILL_DIR / entry.get("source_path", "")
            if src.is_file():
                source_hashes[entry["source_path"]] = hashlib.sha256(src.read_bytes()).hexdigest()
        missing_sources = sorted(e.get("source_path") for e in entries if e.get("source_path") and not (SKILL_DIR / e["source_path"]).is_file())
        closure = {"unclassified_hits": len(missing_sources), "active_legacy_hits": sum(1 for e in entries if e.get("disposition") == "manual-review"), "missing_sources": missing_sources}
        mapping = {e.get("source_path"): e.get("target_path") for e in entries if e.get("source_path")}
        allowlist = sorted({e.get("source_path") for e in entries if e.get("disposition") in {"rebuild-delete", "delete"} and e.get("source_path")})
        body = {"schema_version": 2, "phase": "preview", "ledger": str(LEDGER_PATH.relative_to(SKILL_DIR)),
                "ledger_sha256": hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest(),
                "source_snapshot": {"head": __import__('subprocess').check_output(["git","rev-parse","HEAD"], cwd=SKILL_DIR, text=True).strip(), "files": source_hashes},
                "dirty_hashes": source_hashes, "closure": closure, "mapping": mapping,
                "delete_allowlist": allowlist, "entry_count": len(entries), "next_phase": "stage"}
        body["plan_digest"] = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        plan = body
        _write_json(LIBRARY / "governance/migration/migration-plan.json", plan)

    if args.phase == "cleanup":
        receipt_path = LIBRARY / "governance/migration/migration-receipt.json"
        plan_path = args.plan.resolve() if args.plan else LIBRARY / "governance/migration/migration-plan.json"
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            cleanup_plan = json.loads(plan_path.read_text(encoding="utf-8"))
            result = cleanup_published(LIBRARY, cleanup_plan, receipt)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.retire_old_tree:
        receipt_path = LIBRARY / "governance/migration/migration-receipt.json"
        try:
            prior = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"published receipt required: {exc}")
        if prior.get("phase") != "published" or prior.get("ledger_sha256") != hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest():
            parser.error("migration_receipt_not_published")
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

    if args.phase == "publish":
        receipt_path = LIBRARY / "governance/migration/migration-receipt.json"
        try:
            prior = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"verified receipt required: {exc}")
        plan_path = args.plan.resolve() if args.plan else LIBRARY / "governance/migration/migration-plan.json"
        current_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if (prior.get("phase") != "verified"
                or prior.get("ledger_sha256") != hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest()
                or prior.get("plan_digest") != _plan_digest(current_plan)):
            parser.error("migration_receipt_not_verified")
        try:
            publish_staged_manifest(LIBRARY, plan_digest=_plan_digest(current_plan))
        except (OSError, ValueError, KeyError) as exc:
            parser.error(str(exc))

    if not (args.execute or args.verify):
        parser.error("需要 --execute 或 --verify")
    if args.execute:
        if args.phase == "stage":
            # Stage into an isolated shadow tree; delivery remains untouched.
            shadow = Path(tempfile.mkdtemp(prefix="leo-template-stage-"))
            staged_library = shadow / "template-library"
            shutil.copytree(LIBRARY, staged_library, dirs_exist_ok=True)
            original_library = globals()["LIBRARY"]
            globals()["LIBRARY"] = staged_library
            try:
                report = execute(ledger)
                staged_root = staged_library
            finally:
                globals()["LIBRARY"] = original_library
        else:
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
        if args.phase == "stage":
            manifest = []
            manifest_root = staged_root if args.phase == "stage" else SKILL_DIR
            for entry in ledger.get("entries", []):
                target = entry.get("target_path")
                if not target or target.endswith("/"):
                    continue
                path = manifest_root / target if not target.startswith("template-library") else manifest_root / target.removeprefix("template-library/")
                if path.is_file():
                    delivery = (SKILL_DIR / target).resolve()
                    manifest.append({"path": str(path), "delivery_path": str(delivery),
                                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                     "delivery_sha256": hashlib.sha256(delivery.read_bytes()).hexdigest() if delivery.is_file() else None})
            _write_json(original_library / "governance/migration/staging-manifest.json", {"schema_version": 2, "plan_digest": _plan_digest(json.loads((original_library / "governance/migration/migration-plan.json").read_text())), "shadow_root": str(staged_library), "entries": manifest})
        print(json.dumps({"processed": len(report), "failed": len(failed)},
                         ensure_ascii=False))
        if failed:
            for item in failed[:10]:
                print("  FAIL", item["source"], item["error"], file=sys.stderr)
            return 1
    problems, count = verify(ledger)
    if args.phase == "verify":
        manifest_path = LIBRARY / "governance/migration/staging-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"staging_manifest_unreadable: {exc}", file=sys.stderr)
            return 1
        for item in manifest.get("entries", []):
            path = Path(item["path"])
            if not path.is_absolute():
                path = SKILL_DIR / path
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
                problems.append(f"staging_manifest_drift: {item.get('path')}")
        count = len(problems)
    if problems:
        for problem in problems[:20]:
            print(problem, file=sys.stderr)
        print(f"verify: {count} problems", file=sys.stderr)
        return 1 if count else 0
    print("verify: all ledger entries have targets")
    if args.phase in {"verify", "publish"}:
        receipt = {
            "schema_version": 1,
            "kind": "template-library-migration-receipt",
            "phase": "verified" if args.phase == "verify" else "published",
            "ledger_sha256": hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest(),
            "plan_sha256": hashlib.sha256((args.plan.resolve() if args.plan else LEDGER_PATH).read_bytes()).hexdigest(),
            "plan_digest": _plan_digest(json.loads((LIBRARY / "governance/migration/migration-plan.json").read_text())) if (LIBRARY / "governance/migration/migration-plan.json").is_file() else None,
            "entry_count": len(ledger.get("entries", [])),
        }
        _write_json(LIBRARY / "governance/migration/migration-receipt.json", receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
