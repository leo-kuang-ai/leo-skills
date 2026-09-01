#!/usr/bin/env python3
"""deck_template.py — R-50 deck 模板化复用（结构资产 + 实例数据点指纹 diff）。

模板 = 结构资产：confirmed 母版的页面骨架（页序 + 每页版式 P 码 +
argument_role 序列）、风格合同引用、页数合同、数字登记表列结构，存于
``${LEO_PPT_HOME}/deck-templates/<N>/template.json``。模板**不携带任何业务
数据**——数字登记表数据行不入模板，只留列结构（页面标题/要点等业务文本
同样剥离）。

实例登记：``instantiate`` 时从本期新材料抽取数据点指纹（归一化数值键，
抽取逻辑同构 ``check_content_facts.py`` / ``compute_impact.py``），追加到
模板目录 ``instances.jsonl``；``diff-data`` 对照最近一次实例登记的指纹，
输出 沿用/新增/缺失 三类数据点清单，缺失项进材料确认清单文案。

确认语义红线（写死在输出里）：diff 式确认只减少呈现项，**不减少确认门**
——样张、数据分级、逐件确认每期照常；模板不豁免任何门。

用法：
  python3 scripts/deck_template.py save <project-root> --name N [--home DIR]
  python3 scripts/deck_template.py instantiate N --data <新材料.md> \
      --out <project-root> [--home DIR] [--json]
  python3 scripts/deck_template.py diff-data N <新材料母版.md> [--home DIR] [--json]

退出码：0 成功；2 用法错误 / 模板不存在 / 无 confirmed 基线 / 解析失败。
确定性：同输入同输出——工件不含时间戳，实例登记对同材料幂等（重复
instantiate 不追加重复记录）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

# Sibling-script reuse: ledger parsing from compute_impact, numeric
# normalization from check_content_facts (same deterministic semantics).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import compute_impact  # noqa: E402
import reproject_derivatives  # noqa: E402
from check_content_facts import (  # noqa: E402
    NUM_TOKEN_RE,
    PCT_CN_RE,
    normalize_number,
)

SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_USAGE = 2
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
TEMPLATE_FILE = "template.json"
INSTANCES_FILE = "instances.jsonl"
# v2 nine-column ledger contract (deck-master.md 数字登记表节) as fallback
# when the saved master carries no ledger header of its own.
DEFAULT_LEDGER_COLUMNS = ["数值", "页", "来源", "口径", "期间", "单位",
                          "证据等级", "verified?", "as-of"]
CONFIRM_SEMANTICS = (
    "diff 式确认只减少呈现项，不减少确认门——样张、数据分级、逐件确认每期照常；"
    "模板不豁免任何门。")
ARGUMENT_ROLE_RE = re.compile(r"^argument_role\s*[:：]\s*(\S+)", re.M)
P_CODE_RE = re.compile(r"\bP(\d+)\b")
STYLE_REF_RE = re.compile(r"^(?:风格合同?|style_ref?)\s*[:：]\s*(\S+)", re.M)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(EXIT_USAGE)


def canonical_key_str(key) -> str:
    """Serialize a ('num'|'pct', Decimal) canonical key; numerically equal
    Decimals serialize identically ('1.24亿' and '12400万' -> 'num:124000000')."""
    kind, value = key
    return f"{kind}:{format(value.normalize(), 'f')}"


def key_sortable(key_str: str) -> tuple:
    kind, _, number = key_str.partition(":")
    try:
        return (kind, Decimal(number))
    except Exception:
        return (kind, key_str)


def resolve_home(args) -> Path:
    home = getattr(args, "home", None) or os.environ.get("LEO_PPT_HOME")
    if not home:
        fail("未指定模板根目录：传 --home 或设置 LEO_PPT_HOME")
    return Path(home)


def template_dir(home: Path, name: str) -> Path:
    if not NAME_RE.match(name):
        fail(f"模板名非法（仅限字母数字连字符下划线）：{name!r}")
    return home / "deck-templates" / name


def load_template(home: Path, name: str) -> dict:
    path = template_dir(home, name) / TEMPLATE_FILE
    if not path.is_file():
        fail(f"模板不存在：{path}（先运行 save --name {name}）")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        fail(f"模板不可解析：{path}: {exc}")


def load_instances(home: Path, name: str) -> list:
    path = template_dir(home, name) / INSTANCES_FILE
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError as exc:
            fail(f"实例登记不可解析：{path}: {exc}")
    return records


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def parse_skeleton(text: str) -> dict:
    """Extract the structure asset from a confirmed master (no business data:
    titles/points/ledger rows are dropped; only shape survives)."""
    try:
        pages = compute_impact.split_pages(text)
    except compute_impact.ParseError as exc:
        fail(f"母版不可解析：{exc}")
    skeleton = []
    for pid, _header, body in pages:
        role = ARGUMENT_ROLE_RE.search(body)
        layout = None
        # P-code priority: an explicit 版式 line, then the 视觉行, then any
        # line of the page block (undecided markers list candidate P-codes).
        for selector in (lambda ln: "版式" in ln, lambda ln: "视觉行" in ln,
                         lambda ln: True):
            for line in body.splitlines():
                m = P_CODE_RE.search(line)
                if m and selector(line):
                    layout = f"P{m.group(1)}"
                    break
            if layout:
                break
        skeleton.append({
            "page_id": pid,
            "argument_role": role.group(1) if role else None,
            "layout": layout,
        })
    ledger_columns = DEFAULT_LEDGER_COLUMNS
    rows = compute_impact._table_rows(text, compute_impact.LEDGER_SECTION_RE)
    for row in rows:
        if compute_impact._is_separator(row):
            continue
        cells = compute_impact._cells(row)
        if cells and cells[0] == "数值":
            ledger_columns = cells
            break
    first_page_at = re.search(compute_impact.PAGE_RE, text)
    head = text[: first_page_at.start()] if first_page_at else text
    style = STYLE_REF_RE.search(head)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "leo-deck-template",
        "name": None,  # filled by caller
        "source_master": None,
        "page_contract": {
            "page_count": len(pages),
            "page_ids": [p[0] for p in pages],
        },
        "style_ref": style.group(1) if style else None,
        "pages": skeleton,
        "ledger_columns": ledger_columns,
        "confirm_semantics": CONFIRM_SEMANTICS,
    }


def _number_keys_from(text: str):
    """[(display, canonical_key)] for one text (material or ledger cell)."""
    keys = []
    for m in NUM_TOKEN_RE.finditer(text):
        display = "".join(m.group(0).split())
        keys.append((display, normalize_number(m.group(1), m.group(2))))
    for m in PCT_CN_RE.finditer(text):
        keys.append(("".join(m.group(0).split()),
                     ("pct", Decimal(m.group(1)))))
    return keys


def extract_data_points(text: str) -> list:
    """Deterministic fingerprint list from a master (ledger values win — the
    ledger is the numeric single source of truth) or raw material."""
    entries: dict[str, dict] = {}
    rows = compute_impact._table_rows(text, compute_impact.LEDGER_SECTION_RE)
    page_seq = [pid for pid, _h, _b in compute_impact.split_pages(text)] if \
        re.search(compute_impact.PAGE_RE, text) else []
    mode = "ledger"
    if rows:
        for row in rows:
            if compute_impact._is_separator(row):
                continue
            cells = compute_impact._cells(row)
            if len(cells) < 2 or not cells[0] or cells[0] == "数值":
                continue
            pages = compute_impact._resolve_page_cell(cells[1], page_seq) or [None]
            for display, key in _number_keys_from(cells[0]):
                kstr = canonical_key_str(key)
                if kstr not in entries:
                    entries[kstr] = {"key": kstr, "display": display,
                                     "page": pages[0] if pages else None}
    else:
        mode = "material"
        for display, key in _number_keys_from(text):
            kstr = canonical_key_str(key)
            if kstr not in entries:
                entries[kstr] = {"key": kstr, "display": display, "page": None}
    return sorted(entries.values(), key=lambda e: key_sortable(e["key"])), mode


def cmd_save(args) -> int:
    home = resolve_home(args)
    project = Path(args.project_root)
    content = project / "content"
    if not content.is_dir():
        fail(f"项目内容目录不存在：{content}")
    found = reproject_derivatives.find_confirmed_master(content)
    if not found:
        fail(f"无 confirmed 母版基线：{content}（只有已确认 deck 才能存为模板）")
    master_path, _chain = found
    text = master_path.read_text(encoding="utf-8")
    skeleton = parse_skeleton(text)
    skeleton["name"] = args.name
    skeleton["source_master"] = master_path.name
    tdir = template_dir(home, args.name)
    tpath = tdir / TEMPLATE_FILE
    if tpath.is_file():
        old = json.loads(tpath.read_text(encoding="utf-8"))
        if old.get("page_contract", {}).get("page_ids") != \
                skeleton["page_contract"]["page_ids"]:
            print(f"WARN: 覆盖模板 {args.name}：页序合同变化"
                  f"（旧 {old.get('page_contract', {}).get('page_ids')} -> "
                  f"新 {skeleton['page_contract']['page_ids']}）；"
                  f"实例指纹登记保留，diff 仍按数值键比对。")
    write_atomic(tpath, json.dumps(skeleton, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n")
    pages = skeleton["page_contract"]
    print(f"SAVED: {tpath}")
    print(f"模板 {args.name}：{pages['page_count']} 页（{'、'.join(pages['page_ids'])}），"
          f"版式预填 {sum(1 for p in skeleton['pages'] if p['layout'])}/{pages['page_count']} 页，"
          f"style_ref={skeleton['style_ref'] or '（未声明）'}")
    print("业务数据已剥离：模板只含结构资产（页序/版式/argument_role/页数合同/"
          "登记表列结构）。")
    return EXIT_OK


def draft_master_text(tpl: dict, instance_seq: int, material_name: str,
                      registered: list, previous: list) -> str:
    lines = [
        f"# 母版草案（模板 {tpl['name']} 实例 {instance_seq}）",
        "",
        "confirmation: pending",
        f"template: {tpl['name']}",
        f"instance: {instance_seq}",
        f"page_contract: {tpl['page_contract']['page_count']} 页"
        f"（{'、'.join(tpl['page_contract']['page_ids'])}）",
        f"style_ref: {tpl['style_ref'] or '（未声明，本期按风格推荐流程选定）'}"
        "（来自模板，可改；改后走完整风格确认）",
        "",
        f"<!-- 确认语义红线：{CONFIRM_SEMANTICS} -->",
        "",
    ]
    for page in tpl["pages"]:
        lines.append(f"## {page['page_id']}")
        if page["argument_role"]:
            lines.append(f"argument_role: {page['argument_role']}")
        if page["layout"]:
            lines.append(f"版式: {page['layout']}（模板预填，可改；"
                         "改后按常规划式流程重估容量）")
        else:
            lines.append("版式: （模板未预填——上期母版未声明 P 码，本期按 "
                         "layout-dispatch 流程选定）")
        lines.append("")
        lines.append("- 标题：（待填：结论句标题，按论证模式条件化）")
        lines.append("- 要点：（待填：论断句第一条 + 证据跟随，逐条带证据短标）")
        lines.append(f"视觉行：（待填：容器清单 + 每个要点的落位声明"
                     f"{'；版式 ' + page['layout'] if page['layout'] else ''}）")
        lines.append("- 备注：speaker_script：（待填）／engineering：（待填）")
        lines.append("")
    lines.append("## 数字登记表")
    lines.append("| " + " | ".join(tpl["ledger_columns"]) + " |")
    lines.append("| " + " | ".join(["---"] * len(tpl["ledger_columns"])) + " |")
    lines.append("<!-- 列结构来自模板；数据行不入模板——本期按新材料重新登记。 -->")
    lines.append("")
    lines.append("## 模板数据点指纹清单")
    lines.append("")
    lines.append(f"实例登记（本期材料 {material_name}，{len(registered)} 项）：")
    if registered:
        lines.extend(f"- {e['display']} → {e['key']}" for e in registered)
    else:
        lines.append("-（本期材料未检出数值数据点）")
    lines.append("")
    lines.append("上期登记指纹（沿用候选；母版定稿后 diff-data 复核，"
                 f"{len(previous)} 项）：")
    if previous:
        lines.extend(f"- {e['display']} → {e['key']}" for e in previous)
    else:
        lines.append("-（无上期登记——本期为模板首个实例）")
    lines.append("")
    return "\n".join(lines)


def cmd_instantiate(args) -> int:
    home = resolve_home(args)
    tpl = load_template(home, args.name)
    material = Path(args.data)
    if not material.is_file():
        fail(f"新材料文件不存在：{material}")
    text = material.read_text(encoding="utf-8")
    registered, mode = extract_data_points(text)
    records = load_instances(home, args.name)
    previous = records[-1]["data_points"] if records else []
    record = {
        "schema_version": SCHEMA_VERSION,
        "template": args.name,
        "source_material": material.name,
        "extraction_mode": mode,
        "data_points": registered,
    }
    instance_seq = len(records)
    ipath = template_dir(home, args.name) / INSTANCES_FILE
    # Idempotent registration: re-running with the same material must not
    # append a duplicate record (determinism contract).
    if not (records and json.dumps(records[-1], ensure_ascii=False,
                                   sort_keys=True) ==
            json.dumps(record, ensure_ascii=False, sort_keys=True)):
        instance_seq += 1
        write_atomic(ipath, "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
            for r in records + [record]))
    out_root = Path(args.out)
    content = out_root / "content"
    content.mkdir(parents=True, exist_ok=True)
    draft = draft_master_text(tpl, instance_seq, material.name,
                              registered, previous)
    target = content / "deck-master-v1.md"
    if target.exists() and target.read_text(encoding="utf-8") != draft:
        versions = [int(m.group(1)) for p in content.glob("deck-master-v*.md")
                    if (m := re.match(r"deck-master-v(\d+)\.md$", p.name))]
        target = content / f"deck-master-v{max(versions or [0]) + 1}.md"
    write_atomic(target, draft)
    instance_doc = {
        "schema_version": SCHEMA_VERSION,
        "template": args.name,
        "instance_seq": instance_seq,
        "master_draft": target.name,
        "page_contract": tpl["page_contract"],
        "registered_data_points": registered,
        "previous_data_points": previous,
        "confirm_semantics": CONFIRM_SEMANTICS,
    }
    ipath_out = content / "template-instance.json"
    write_atomic(ipath_out, json.dumps(instance_doc, ensure_ascii=False,
                                       indent=2, sort_keys=True) + "\n")
    payload = {
        "status": "completed",
        "template": args.name,
        "instance_seq": instance_seq,
        "master_draft": str(target),
        "instance_doc": str(ipath_out),
        "registered_points": len(registered),
        "previous_points": len(previous),
        "confirm_semantics": CONFIRM_SEMANTICS,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(f"INSTANTIATED: 模板 {args.name} 实例 {instance_seq} -> {target}")
        print(f"骨架预填 {tpl['page_contract']['page_count']} 页；"
              f"本期材料数据点 {len(registered)} 项已登记"
              f"（抽取模式 {mode}），上期指纹 {len(previous)} 项列为沿用候选。")
        print(f"确认语义：{CONFIRM_SEMANTICS}")
    return EXIT_OK


def cmd_diff_data(args) -> int:
    home = resolve_home(args)
    load_template(home, args.name)  # existence check + parseability
    records = load_instances(home, args.name)
    if not records:
        fail(f"模板 {args.name} 尚无实例登记：先以新材料运行 instantiate")
    master = Path(args.master)
    if not master.is_file():
        fail(f"母版文件不存在：{master}")
    text = master.read_text(encoding="utf-8")
    try:
        master_points, mode = extract_data_points(text)
    except compute_impact.ParseError as exc:
        fail(f"母版不可解析：{exc}")
    baseline = records[-1]
    base_keys = {e["key"]: e for e in baseline["data_points"]}
    master_keys = {e["key"]: e for e in master_points}
    reused = [e for k, e in sorted(base_keys.items(), key=lambda kv: key_sortable(kv[0]))
              if k in master_keys]
    added = [e for k, e in sorted(master_keys.items(), key=lambda kv: key_sortable(kv[0]))
             if k not in base_keys]
    missing = [e for k, e in sorted(base_keys.items(), key=lambda kv: key_sortable(kv[0]))
               if k not in master_keys]
    checklist = [
        f"{e['display']}（{e['key']}）——上期/本期材料数据点未进入母版，"
        "逐项与用户确认保留或放弃"
        for e in missing
    ]
    result = {
        "template": args.name,
        "baseline_instance": len(records),
        "baseline_material": baseline.get("source_material"),
        "master_mode": mode,
        "baseline_points": len(base_keys),
        "master_points": len(master_keys),
        "reused": reused,
        "added": added,
        "missing": missing,
        "checklist": checklist,
        "confirm_semantics": CONFIRM_SEMANTICS,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_OK

    def fmt(entries):
        return "、".join(f"{e['display']}（{e['key']}）" for e in entries) or "（无）"
    print(f"TEMPLATE-DIFF: template={args.name} baseline_instance={len(records)} "
          f"baseline_points={len(base_keys)} master_points={len(master_keys)} "
          f"(master 抽取模式 {mode})")
    print(f"沿用 ({len(reused)}): {fmt(reused)}")
    print(f"新增 ({len(added)}): {fmt(added)}")
    print(f"缺失 ({len(missing)}): {fmt(missing)}")
    if checklist:
        print("材料确认清单（缺失项，进本期确认序列呈现）：")
        for idx, item in enumerate(checklist, start=1):
            print(f"  {idx}. {item}")
    print(f"确认语义：{CONFIRM_SEMANTICS}")
    return EXIT_OK


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="deck 模板化复用：结构资产 save / 实例化 instantiate / 数据点 diff")
    sub = parser.add_subparsers(dest="command", required=True)
    p_save = sub.add_parser("save", help="把 confirmed 母版骨架存为模板")
    p_save.add_argument("project_root", help="项目根目录（含 content/deck-master-v*.md）")
    p_save.add_argument("--name", required=True, help="模板名（字母数字连字符下划线）")
    p_save.add_argument("--home", default=None,
                        help="LEO_PPT_HOME 根目录（缺省读环境变量）")
    p_save.set_defaults(func=cmd_save)
    p_inst = sub.add_parser("instantiate", help="以模板产出新项目 content/ 草案并登记数据点指纹")
    p_inst.add_argument("name", help="模板名")
    p_inst.add_argument("--data", required=True, help="本期新材料 markdown 路径")
    p_inst.add_argument("--out", required=True, help="新项目根目录（草案写入其 content/）")
    p_inst.add_argument("--home", default=None,
                        help="LEO_PPT_HOME 根目录（缺省读环境变量）")
    p_inst.add_argument("--json", action="store_true", help="机器可读 JSON 输出")
    p_inst.set_defaults(func=cmd_instantiate)
    p_diff = sub.add_parser("diff-data", help="对照模板实例指纹 diff 母版数据点")
    p_diff.add_argument("name", help="模板名")
    p_diff.add_argument("master", help="本期（新材料）母版 markdown 路径")
    p_diff.add_argument("--home", default=None,
                        help="LEO_PPT_HOME 根目录（缺省读环境变量）")
    p_diff.add_argument("--json", action="store_true", help="机器可读 JSON 输出")
    p_diff.set_defaults(func=cmd_diff_data)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
