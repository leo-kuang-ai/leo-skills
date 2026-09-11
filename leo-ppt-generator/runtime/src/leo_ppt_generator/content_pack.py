"""content_pack.py — 母版到机器输入的无损内容投影（dashi 集成 K1/U2）。

职责边界（references/deck-master.md + docs/plans/2026-09-10-001 KTD1）：
  - 公共母版解析：页块、图行、数字登记表、术语表、页首元信息与备注分栏，
    由 scripts/reproject_derivatives.py、scripts/check_master_contract.py 与
    本模块共同消费；runtime 不反向导入 scripts。
  - 稳定身份：母版页首 `page_id: pg-<hex>` 行是跨 revision 保留的稳定身份，
    展示顺序（`number`）与母版标签（`S<N>`/`附`）独立维护；插页、换序不给
    未变化页重新编号。身份只能一次性写入母版（`propose_page_id_stamping`），
    编译器永不代发。
  - 内容包：confirmed 母版的单向派生物（schema `page-content-pack-v1`），
    绑定母版路径、SHA256、revision 与规范化内容摘要；同输入重编译必须得到
    相同摘要，手改内容包在校验时被拒。`engineering` 备注留在包内隔离字段，
    不进版面或 PPTX notes。

失败语义：解析不了的正文、图行或登记表行返回母版位置（页 + 行号），不静默
丢弃、截断、改数或降级为可选。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .storage import canonical_json

PACK_SCHEMA_VERSION = 1
COMPILER_VERSION = "2"

PAGE_HEADER_RE = re.compile(r"^##\s+(S(\d+)|附)[^\n]*$", re.M)
ANY_SECTION_RE = re.compile(r"^##\s+.*$", re.M)
PAGE_ID_LINE_RE = re.compile(r"^page_id[：:]\s*(\S+)\s*$", re.M)
PAGE_ID_FORMAT_RE = re.compile(r"^pg-[0-9a-f]{8,16}$")
TITLE_RE = re.compile(r"[-•]\s*标题[：:]\s*(.+)")
POINT_LINE_RE = re.compile(r"^\s*(?:[-•]|\d+\.|\d+、)\s*(.+)$", re.M)
_NON_POINT = ("标题", "备注", "视觉行", "argument_role", "数字登记表")
_PAGE_META_KEYS = ("page_id", "argument_role", "beat", "audience_takeaway",
                   "rst_relation", "角色", "页面角色", "role",
                   "结构数据", "对照侧", "表列", "表行", "page_expression", "content_model")
VISUAL_RE = re.compile(r"(?:视觉行|视觉)[：:]\s*(.+)")
ROLE_RE = re.compile(r"(?:页面角色|角色|role)[：:]\s*([^\s,，;；。]+)", re.I)
META_LINE_RES = {
    "argument_role": re.compile(r"^argument_role[：:]\s*(\S+)", re.M),
    "beat": re.compile(r"^beat[：:]\s*([^\n]+)$", re.M),
    "audience_takeaway": re.compile(r"^audience_takeaway[：:]\s*([^\n]+)$", re.M),
    "rst_relation": re.compile(r"^rst_relation[：:]\s*([a-z-]+)", re.I | re.M),
}
NOTES_RE = re.compile(r"(?:^|\n)[-•]?\s*备注[：:]\s*([^\n]*)")
SPEAKER_RE = re.compile(r"speaker_script[：:]\s*([^\n]*)")
ENGINEERING_RE = re.compile(r"^[-•]?\s*engineering[：:]\s*([^\n]*)", re.M)
# 结构标记（K3/U3）：对照侧——`对照侧: 左｜标题｜要点1；要点2`，母版显式声明
# 比较结构，编译器不猜测；缺标记的母版不产生 sides 结构（compare 绑定不合格）。
SIDE_MARKER_RE = re.compile(r"^[-•]?\s*对照侧[：:]\s*([^\n]+)$", re.M)
# 结构标记（K6/U6）：表列/表行——`表列: 维度,方案A,方案B` + `表行: 指标｜6 周｜1 周`，
# 台账/矩阵结构显式声明；列数与每行单元格数由投影层交叉校验。
TABLE_COLUMNS_RE = re.compile(r"^[-•]?\s*表列[：:]\s*([^\n]+)$", re.M)
TABLE_ROW_RE = re.compile(r"^[-•]?\s*表行[：:]\s*([^\n]+)$", re.M)
STRUCTURED_FIELDS_RE = re.compile(r"^[-•]?\s*结构数据[：:][ \t]*(.*)$", re.M)
DECK_META_RES = {
    "goal": re.compile(r"^(?:goal|目标)[：:]\s*([^\n]+)$", re.M),
    "audience": re.compile(r"^(?:audience|受众)[：:]\s*([^\n]+)$", re.M),
    "argumentation_mode": re.compile(r"^argumentation_mode[：:]\s*(\S+)", re.M),
    "decision_source": re.compile(
        r"^decision_source[：:]\s*(user-confirmed|user-delegated)", re.M),
}
DELIVERY_TIER_RE = re.compile(r"^delivery_tier[：:]\s*(\S+)", re.M)
LEDGER_SECTION_RE = re.compile(r"^##\s+数字登记表\s*$", re.M)
GLOSSARY_SECTION_RE = re.compile(r"^##\s+术语表\s*$", re.M)
LEDGER_COLUMNS = ("value", "pages", "source", "caliber", "period", "unit",
                  "evidence_tier", "verified", "as_of")
LEDGER_MIN_NON_EMPTY = 6

# 图行三段（与 check_master_contract ⑦ 同口径）：模式/状态/焦点 + 承载/服务/避免误读。
FIGURE_ROW_START_RE = re.compile(r"图\[(F\d+)\]")
FIGURE_MODE_RE = re.compile(r"模式[：:]\s*([^\s|，,；;]+)")
FIGURE_STATUS_RE = re.compile(r"状态[：:]\s*([^\s|，,；;]+)")
FIGURE_FOCUS_RE = re.compile(r"焦点[：:]\s*([^\n|]+?)\s*(?:\||$|\n)")
FIGURE_SEGMENT_RES = {
    "承载": re.compile(r"(?:^|\n|\|)\s*承载[：:]"),
    "服务": re.compile(r"(?:^|\n|\|)\s*服务[：:]"),
    "避免误读": re.compile(r"(?:^|\n|\|)\s*避免误读[：:]"),
}

# 要点级四级标注（与 check_master_contract ⑩ 同口径）。
TIER_MARK_RE = re.compile(
    r"[【（(]\s*(用户确认|引用|估算|示意)(?:\s*[|｜][^】）)]*)?\s*[】）)]")
SRC_SQ_RE = re.compile(r"\[\s*src\s*[：:]\s*([^\]]+?)\s*\]")
SRC_PIPE_RE = re.compile(r"[【（(][^】）)]*?src[：:]\s*([^】）)]+?)\s*[】）)]")
ROUND_MARK_RE = re.compile(r"round[：:]\s*(\d+)")


class ContentPackError(ValueError):
    """母版不可无损投影；消息携带母版位置（页 + 行号）供回母版补齐。

    继承 ValueError：既有脚本（reproject 等）按 (OSError, ValueError)
    捕获母版解析失败并给出干净退出码。
    """


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_digest(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k != "content_digest"}
    return sha256_text(canonical_json(body))


# ---------------------------------------------------------------------------
# 公共母版解析
# ---------------------------------------------------------------------------

def split_page_blocks(text: str) -> list[dict]:
    """有序页块：{master_page, header, body, start_line}；deck 级表格截止末页正文。"""
    matches = list(PAGE_HEADER_RE.finditer(text))
    if not matches:
        raise ContentPackError("母版无任何页块（## S<N> 或 ## 附）")
    section_starts = [m.start() for m in ANY_SECTION_RE.finditer(text)]
    blocks = []
    for idx, m in enumerate(matches):
        end = len(text)
        for pos in section_starts:
            if pos > m.start():
                end = pos
                break
        header = m.group(0)
        label = "附" if header.startswith("## 附") else f"S{m.group(2)}"
        blocks.append({
            "master_page": label,
            "header": header,
            "body": text[m.start():end],
            "start_line": text.count("\n", 0, m.start()) + 1,
        })
    return blocks


def declared_page_id(body: str) -> str | None:
    m = PAGE_ID_LINE_RE.search(body)
    return m.group(1) if m else None


def collect_figure_rows(body: str) -> list[dict]:
    """页内图行（含续行）：{figure_id, raw, line_no}；不做枚举校验。"""
    lines = body.splitlines()
    offset = 0  # body 相对行号即母版正文切片，行号在错误消息中按页内呈现。
    rows = []
    i = 0
    while i < len(lines):
        m = FIGURE_ROW_START_RE.search(lines[i])
        if m:
            row_lines = [lines[i]]
            j = i + 1
            while j < len(lines):
                nxt = lines[j].lstrip().lstrip("-•").strip()
                is_seg = any(r.match(nxt) or r.search("|" + nxt) is not None
                             for r in FIGURE_SEGMENT_RES.values())
                if nxt and is_seg and not FIGURE_ROW_START_RE.search(nxt):
                    row_lines.append(lines[j])
                    j += 1
                else:
                    break
            rows.append({"figure_id": m.group(1), "raw": "\n".join(row_lines),
                         "line_no": offset + i + 1})
            i = j
        else:
            i += 1
    return rows


def table_rows(text: str, section_re: re.Pattern) -> list[list[str]]:
    m = section_re.search(text)
    if not m:
        return []
    rows = []
    seen_header = False
    for ln in text[m.end():].splitlines():
        s = ln.strip()
        if s.startswith("## "):
            break
        if s.startswith("|"):
            if not seen_header:
                seen_header = True
                continue
            if re.fullmatch(r"[\s:-]+", s.replace("|", "")):
                continue
            rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows


def parse_page_points(body: str) -> list[str]:
    """要点行（含标题行排除项与页首元信息行排除项）。

    「要点 N：」列表标签不是内容——剥离后进入 pack（与 check_master_contract
    的要点标注判定同口径），模板自渲染列表序号。
    """
    label_re = re.compile(r"^要点\s*\d+\s*[：:]\s*")
    points = []
    meta_key_hit = re.compile(
        r"^(?:" + "|".join(re.escape(k) for k in _PAGE_META_KEYS) + r")[：:]")
    for m in POINT_LINE_RE.finditer(body):
        content = m.group(1).strip()
        if any(k in content for k in _NON_POINT):
            continue
        if meta_key_hit.match(content):
            continue
        points.append(label_re.sub("", content))
    return points


def parse_structures(body: str) -> dict:
    """母版显式结构标记 → pack structures（K3/U3）。

    当前支持：对照侧（compare sides）。要点用「；」分隔；label/标题/要点
    用全角「｜」分隔。结构必须来自母版显式标记——确定性编译器不猜测结构。
    """
    structures: dict = {}
    field_markers = list(STRUCTURED_FIELDS_RE.finditer(body))
    if len(field_markers) > 1:
        raise ContentPackError("每页只允许一行结构数据 JSON，不能静默覆盖")
    if field_markers:
        from .template_inputs import load_template_json
        try:
            fields = load_template_json(field_markers[0].group(1))
        except ValueError as exc:
            raise ContentPackError(f"结构数据必须是单行合法 JSON: {exc}") from exc
        if not isinstance(fields, dict):
            raise ContentPackError("结构数据必须为 JSON object")
        structures["fields"] = fields
    sides = []
    for m in SIDE_MARKER_RE.finditer(body):
        parts = [p.strip() for p in m.group(1).split("｜")]
        if len(parts) < 2 or not parts[0]:
            raise ContentPackError(
                f"对照侧标记格式非法（须为「对照侧: 标签｜标题｜要点；要点」）: {m.group(0)}")
        points = [p.strip() for p in parts[2].split("；")] if len(parts) > 2 and parts[2] else []
        sides.append({"label": parts[0], "title": parts[1], "points": points})
    if sides:
        structures["sides"] = sides
    columns_m = TABLE_COLUMNS_RE.search(body)
    if columns_m:
        columns = [c.strip() for c in re.split(r"[,，]", columns_m.group(1)) if c.strip()]
        rows = []
        for m in TABLE_ROW_RE.finditer(body):
            cells = [c.strip() for c in m.group(1).split("｜")]
            if len(cells) != len(columns):
                raise ContentPackError(
                    f"表行标记单元格数 {len(cells)} ≠ 表列数 {len(columns)}"
                    f"（{m.group(0)}），回母版对齐")
            rows.append(cells)
        if not rows:
            raise ContentPackError(
                "表列标记存在但无表行标记（表列: … 须伴随 表行: … 行），回母版补齐")
        structures["table"] = {"columns": columns, "rows": rows}
    elif TABLE_ROW_RE.search(body):
        raise ContentPackError("表行标记存在但缺表列标记，回母版补齐表列声明")
    fields = structures.get("fields", {})
    if ("sides" in fields and sides) or (
            {"columns", "rows"}.intersection(fields) and "table" in structures):
        raise ContentPackError("结构数据与对照侧/表列/表行重复声明，须保留唯一来源")
    return structures


def parse_master(text: str) -> dict:
    """公共结构化解析：页（身份/标题/要点/备注/图行/元信息）+ 登记/术语表。"""
    blocks = split_page_blocks(text)
    pages = []
    for block in blocks:
        body = block["body"]
        title_m = TITLE_RE.search(body)
        notes_m = NOTES_RE.search(body)
        speaker_m = SPEAKER_RE.search(body)
        eng_m = ENGINEERING_RE.search(body)
        role_m = ROLE_RE.search(body)
        meta = {name: (rx.search(body).group(1).strip() if rx.search(body) else None)
                for name, rx in META_LINE_RES.items()}
        pages.append({
            "master_page": block["master_page"],
            "start_line": block["start_line"],
            "page_id": declared_page_id(body),
            "title": title_m.group(1).strip() if title_m else None,
            "points": parse_page_points(body),
            "visual": VISUAL_RE.search(body).group(1).strip()
                      if VISUAL_RE.search(body) else None,
            "figures": collect_figure_rows(body),
            "narrative_role": role_m.group(1) if role_m else None,
            "meta": meta,
            "structures": parse_structures(body),
            "notes": {
                "speaker_script": (speaker_m.group(1).strip() if speaker_m
                                   else (notes_m.group(1).strip() if notes_m else None)),
                "engineering": eng_m.group(1).strip() if eng_m else None,
            },
        })
    deck_meta = {name: (rx.search(text).group(1).strip() if rx.search(text) else None)
                 for name, rx in DECK_META_RES.items()}
    tier_m = DELIVERY_TIER_RE.search(text)
    return {
        "pages": pages,
        "number_ledger": [
            dict(zip(LEDGER_COLUMNS, row + [""] * (len(LEDGER_COLUMNS) - len(row))))
            for row in table_rows(text, LEDGER_SECTION_RE)],
        "glossary": [{"cells": row} for row in table_rows(text, GLOSSARY_SECTION_RE)],
        "deck_meta": deck_meta,
        "delivery_tier": tier_m.group(1) if tier_m else None,
    }


def page_identity_map(parsed: dict) -> list[tuple[str, str, int]]:
    """[(stable-or-derived id, master_page, start_line)]；身份不一致即报错。

    全部页带 `page_id` → 稳定身份；全部页缺失 → 派生定位 id（slide_NN，仅供
    重投影等定位用途，内容包编译另行拒绝）；部分页带身份 → 母版损坏。
    """
    pages = parsed["pages"]
    declared = [p["page_id"] for p in pages]
    labels: dict[str, int] = {}
    for page in pages:
        if page["master_page"] in labels:
            raise ContentPackError(
                f"母版页标签「{page['master_page']}」重复（第 {labels[page['master_page']]} 行起"
                f"与第 {page['start_line']} 行起）——同标签页块会造成内容替换，回母版改用唯一标签")
        labels[page["master_page"]] = page["start_line"]
    if all(declared):
        seen: dict[str, int] = {}
        for page in pages:
            pid = page["page_id"]
            where = f"{page['master_page']}（第 {page['start_line']} 行起）"
            if not PAGE_ID_FORMAT_RE.fullmatch(pid):
                raise ContentPackError(
                    f"{where}: page_id「{pid}」格式非法（须为 pg-<8-16 位十六进制）")
            if pid in seen:
                raise ContentPackError(
                    f"{where}: page_id「{pid}」与第 {seen[pid]} 行起的页重复（deck 内必须唯一）")
            seen[pid] = page["start_line"]
        return [(p["page_id"], p["master_page"], p["start_line"]) for p in pages]
    if not any(declared):
        order = [p["master_page"] for p in pages]
        out = []
        for idx, page in enumerate(pages, start=1):
            label = page["master_page"]
            if label == "附":
                pos = order.index(label) + 1
                out.append((f"slide_{pos:02d}", label, page["start_line"]))
            else:
                out.append((f"slide_{int(label[1:]):02d}", label, page["start_line"]))
        return out
    missing = [p["master_page"] for p in pages if not p["page_id"]]
    raise ContentPackError(
        f"母版部分页缺 page_id（{missing}）：身份必须全 deck 一致；"
        "先一次性写入身份形成新的合法母版，不能部分携带")


def require_stable_identity(parsed: dict) -> list[tuple[str, str, int]]:
    """内容包编译入口的身份门：拒绝无身份母版（legacy 需先一次性补齐）。"""
    identity = page_identity_map(parsed)
    if not identity[0][0].startswith("pg-"):
        raise ContentPackError(
            "母版未携带稳定 page_id：内容包不接受派生序号身份。"
            "先用 propose_page_id_stamping 一次性写入身份形成新的合法母版，"
            "再确认后编译；编译器不在每次运行时重发 ID")
    return identity


# ---------------------------------------------------------------------------
# 内容包编译与校验
# ---------------------------------------------------------------------------

def _point_annotations(text: str) -> dict:
    marks = TIER_MARK_RE.findall(text)
    tier = marks[0] if marks else None
    out = {"evidence_tier": tier, "source_ref": None, "session_round": None}
    if not tier:
        return out
    src = SRC_SQ_RE.search(text) or SRC_PIPE_RE.search(text)
    if src:
        out["source_ref"] = src.group(1).strip()
    if tier == "用户确认":
        round_m = ROUND_MARK_RE.search(text)
        if round_m:
            out["session_round"] = int(round_m.group(1))
    return out


def _item_id(kind: str, *parts: str) -> str:
    digest = sha256_text("|".join(parts))[:10]
    return f"{kind}-{digest}"


def _parse_ledger_pages(cell: str) -> list[str]:
    return [tok for tok in re.split(r"[，,、/\s]+", cell.strip()) if tok]


def compile_content_pack(master_text: str, *, master_path: str,
                         master_revision: str | None = None,
                         decision_source: str | None = None,
                         post_confirm_chain: list[str] | None = None,
                         compiler_version: str = COMPILER_VERSION) -> dict:
    """从母版文本编译内容包；同输入必须得到相同 content_digest。"""
    parsed = parse_master(master_text)
    identity = require_stable_identity(parsed)
    if decision_source is None:
        decision_source = (parsed["deck_meta"].get("decision_source")
                           or "user-confirmed")
    by_label = {label: pid for pid, label, _ in identity}
    order_labels = [label for _, label, _ in identity]

    numbers = []
    number_by_page: dict[str, list[dict]] = {}
    for idx, row in enumerate(parsed["number_ledger"], start=1):
        where = f"数字登记表行{idx}（数值「{row['value'] or '空'}」）"
        non_empty = sum(1 for v in row.values() if v)
        if not row["value"]:
            raise ContentPackError(f"{where}: 数值列为空，回母版补齐")
        if non_empty < LEDGER_MIN_NON_EMPTY:
            raise ContentPackError(
                f"{where}: 九列契约非空字段不足 {LEDGER_MIN_NON_EMPTY} 个"
                f"（当前 {non_empty}），回母版补齐口径/期间/单位等字段")
        if not row["unit"] or not row["period"]:
            raise ContentPackError(f"{where}: 单位与期间为必填，同数不同单位/期间"
                                   "不可合并，回母版补齐")
        page_ids = []
        for tok in _parse_ledger_pages(row["pages"]):
            pid = by_label.get(tok)
            if pid is None and re.fullmatch(r"\d+", tok):
                pos = int(tok)
                pid = by_label.get(order_labels[pos - 1]) if 1 <= pos <= len(order_labels) else None
            if pid is None:
                raise ContentPackError(
                    f"{where}: 页列「{tok}」无法解析到母版页块，回母版核对")
            page_ids.append(pid)
        item_id = _item_id("num", row["value"], row["unit"], row["period"], row["caliber"])
        entry = {"item_id": item_id, "kind": "number", "required": True,
                 **{k: row[k] for k in LEDGER_COLUMNS},
                 "page_ids": sorted(set(page_ids))}
        numbers.append(entry)
        for pid in entry["page_ids"]:
            number_by_page.setdefault(pid, []).append(entry)

    pages_out = []
    for number, (pid, label, start_line) in enumerate(identity, start=1):
        page = next(p for p in parsed["pages"] if p["master_page"] == label)
        where = f"{label}（第 {start_line} 行起）"
        if not page["title"]:
            raise ContentPackError(f"{where}: 缺「- 标题：」段，回母版补齐")
        items = []
        seen_point_ids: dict[str, int] = {}
        for point in page["points"]:
            base_id = _item_id("it", pid, point)
            occurrence = seen_point_ids.get(base_id, 0) + 1
            seen_point_ids[base_id] = occurrence
            item_id = base_id if occurrence == 1 else f"{base_id}-{occurrence}"
            ann = _point_annotations(point)
            items.append({"item_id": item_id, "kind": "point", "required": True,
                          "text": point, **ann})
        for figure in page["figures"]:
            raw = figure["raw"]
            fig_where = f"{where} 图[{figure['figure_id']}]（页内第 {figure['line_no']} 行）"
            mode = FIGURE_MODE_RE.search(raw)
            status = FIGURE_STATUS_RE.search(raw)
            focus = FIGURE_FOCUS_RE.search(raw)
            if not (mode and status and focus and focus.group(1).strip()):
                raise ContentPackError(
                    f"{fig_where}: 图行缺 模式/状态/焦点 字段，回母版补齐")
            for seg_name, seg_re in FIGURE_SEGMENT_RES.items():
                if not seg_re.search(raw):
                    raise ContentPackError(
                        f"{fig_where}: 图行缺「{seg_name}」段（三段须齐备），回母版补齐")
            items.append({
                "item_id": figure["figure_id"], "kind": "figure", "required": True,
                "figure_id": figure["figure_id"],
                "handling_mode": mode.group(1),
                "review_status": status.group(1),
                "focus": focus.group(1).strip(),
            })
        for entry in number_by_page.get(pid, []):
            items.append({"item_id": entry["item_id"], "kind": "number-ref",
                          "required": True, "number_item_id": entry["item_id"]})
        meta = page["meta"]
        pages_out.append({
            "page_id": pid,
            "number": number,
            "master_page": label,
            "narrative_role": page["narrative_role"],
            "argument_role": meta["argument_role"],
            "beat": meta["beat"],
            "audience_takeaway": meta["audience_takeaway"],
            "rst_relation": meta["rst_relation"],
            "claim": page["title"],
            "items": items,
            "structures": page["structures"],
            "notes": page["notes"],
        })

    deck = {"goal": parsed["deck_meta"].get("goal"),
            "audience": parsed["deck_meta"].get("audience"),
            "argumentation_mode": parsed["deck_meta"].get("argumentation_mode"),
            "delivery_tier": parsed["delivery_tier"] or "standard"}
    pack = {
        "schema_version": PACK_SCHEMA_VERSION,
        "artifact_kind": "page-content-pack",
        "compiler_version": compiler_version,
        "source": {
            "master_path": master_path,
            "master_sha256": sha256_text(master_text),
            "master_revision": master_revision,
            "decision_source": decision_source,
            "post_confirm_chain": post_confirm_chain or [],
        },
        "deck": deck,
        "pages": pages_out,
        "numbers": numbers,
        "glossary": parsed["glossary"],
    }
    _extend_content_model(pack, master_text)
    pack["content_digest"] = content_digest(pack)
    verify_content_pack(pack)
    return pack


def _json_metadata(text, key):
    matches = list(re.finditer(r"^" + re.escape(key) + r"[：:][ \t]*(.*)$", text, re.M))
    if not matches:
        return None
    if len(matches) != 1:
        raise ContentPackError(f"{key} 必须只有一处声明")
    from .template_inputs import load_template_json
    try:
        value = load_template_json(matches[0].group(1))
    except ValueError as exc:
        raise ContentPackError(f"{key} 必须是合法单行 JSON") from exc
    if not isinstance(value, dict):
        raise ContentPackError(f"{key} 必须是 JSON object")
    return value


def _page_sources(page, numbers):
    sources = {item["source_ref"] for item in page["items"] if item.get("source_ref")}
    sources.update(number["source"] for number in numbers if page["page_id"] in number["page_ids"])
    return sources


def _required_page_text(page, numbers):
    text = [page["claim"]] + [item["text"] for item in page["items"] if item["kind"] == "point"]
    def strings(value):
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [s for item in value for s in strings(item)]
        if isinstance(value, dict):
            return [s for item in value.values() for s in strings(item)]
        return []
    text.extend(strings(page.get("structures", {})))
    text.extend(n["value"] for n in numbers if page["page_id"] in n["page_ids"])
    return list(dict.fromkeys(text))


def _extend_content_model(pack, master_text):
    model = _json_metadata(master_text, "content_model")
    blocks = split_page_blocks(master_text)
    expressions = [_json_metadata(block["body"], "page_expression") for block in blocks]
    if model is None:
        if any(expression is not None for expression in expressions):
            raise ContentPackError("page_expression 必须伴随 content_model v2")
        return
    allowed = {"schema_version", "main_claim", "main_style", "brand_constraints", "narrative_order",
               "chapters", "duration_seconds"}
    if model.get("schema_version") != 2 or set(model) - allowed:
        raise ContentPackError("content_model 版本或字段非法")
    pack["schema_version"] = 2
    pack["compiler_version"] += "+content-v2"
    pack["chapters"] = model.get("chapters")
    for key in ("main_claim", "main_style", "brand_constraints", "narrative_order"):
        pack["deck"][key] = model.get(key)
    pack["deck"]["duration_seconds"] = model.get("duration_seconds")
    allowed_expression = {"chapter_id", "semantic_structure", "media_role", "evidence_refs", "basis",
                          "budget_seconds", "style_exception"}
    for page, expression in zip(pack["pages"], expressions):
        if expression is None or set(expression) - allowed_expression:
            raise ContentPackError(f"{page['page_id']}: 缺 page_expression 或存在未知字段")
        page.update({key: expression.get(key) for key in
                     ("chapter_id", "semantic_structure", "media_role", "evidence_refs", "basis")})
        page["budget_seconds"] = expression.get("budget_seconds")
        page["style_exception"] = expression.get("style_exception")
        page["required_text"] = _required_page_text(page, pack["numbers"])
        page["data_refs"] = [n["item_id"] for n in pack["numbers"] if page["page_id"] in n["page_ids"]]
        page["capacity_requirements"] = {"text_chars": sum(map(len, page["required_text"])),
                                         "point_count": sum(i["kind"] == "point" for i in page["items"]),
                                         "number_count": len(page["data_refs"])}
        if not isinstance(page["basis"], list) or not isinstance(page["evidence_refs"], list):
            raise ContentPackError(f"{page['page_id']}: basis/evidence_refs 必须是数组")
        page["confidence"] = "medium" if (page["evidence_refs"] and page["basis"]
                                                  and page["semantic_structure"] != "undecided") else "undecided"
        if page["confidence"] == "undecided":
            page["basis"] = [*page["basis"], "证据或结构不足，保留 undecided"]


def _verify_content_model(pack):
    ids = [page["page_id"] for page in pack["pages"]]
    if len(ids) != len(set(ids)):
        raise ContentPackError("page_id 重复")
    chapter_ids = [chapter["chapter_id"] for chapter in pack["chapters"]]
    order = pack["deck"]["narrative_order"]
    if len(chapter_ids) != len(set(chapter_ids)) or set(order) != set(chapter_ids) or len(order) != len(chapter_ids):
        raise ContentPackError("章节身份与叙事顺序不一致")
    page_chapters = []
    for page in pack["pages"]:
        if not page_chapters or page_chapters[-1] != page["chapter_id"]:
            page_chapters.append(page["chapter_id"])
    if page_chapters != order:
        raise ContentPackError("实际页序与章节叙事顺序不一致")
    number_ids = [n["item_id"] for n in pack["numbers"]]
    if len(number_ids) != len(set(number_ids)):
        raise ContentPackError("数字账本身份重复；不得合并不同来源或单位")
    for number in pack["numbers"]:
        if not set(number["page_ids"]).issubset(ids):
            raise ContentPackError("数字账本引用未知页面")
    for page in pack["pages"]:
        if page["chapter_id"] not in chapter_ids:
            raise ContentPackError("页面引用未知章节")
        actual = {n["item_id"] for n in pack["numbers"] if page["page_id"] in n["page_ids"]}
        declared = {i["number_item_id"] for i in page["items"] if i["kind"] == "number-ref"}
        if set(page["data_refs"]) != actual or declared != actual:
            raise ContentPackError("页面数据引用与账本不一致")
        if page["required_text"] != _required_page_text(page, pack["numbers"]):
            raise ContentPackError("required_text 丢失或新增内容")
        capacity = {"text_chars": sum(map(len, page["required_text"])),
                    "point_count": sum(i["kind"] == "point" for i in page["items"]),
                    "number_count": len(page["data_refs"])}
        if page["capacity_requirements"] != capacity:
            raise ContentPackError("容量声明与实际内容不一致")
        if not set(page["evidence_refs"]).issubset(_page_sources(page, pack["numbers"])):
            raise ContentPackError("页面证据来源不可回溯")
        if page["confidence"] != "undecided" and not page["evidence_refs"]:
            raise ContentPackError("缺证据的页面必须保持 undecided")
    for chapter in pack["chapters"]:
        pos = order.index(chapter["chapter_id"])
        previous = order[pos - 1] if pos else None
        following = order[pos + 1] if pos + 1 < len(order) else None
        if (chapter["previous"], chapter["next"]) != (previous, following):
            raise ContentPackError("章节承接与叙事顺序不一致")
        sources = set().union(*[_page_sources(page, pack["numbers"]) for page in pack["pages"]
                               if page["chapter_id"] == chapter["chapter_id"]])
        if not set(chapter["evidence_refs"]).issubset(sources):
            raise ContentPackError("章节证据无法回溯到所属页面")


def verify_content_pack(pack: dict) -> None:
    """校验内容包自洽摘要；手改任何内容字段即拒绝。"""
    if not isinstance(pack, dict) or type(pack.get("schema_version")) is not int or pack["schema_version"] not in (1, 2):
        raise ContentPackError("内容包版本必须为 1 或 2")
    if pack.get("artifact_kind") != "page-content-pack":
        raise ContentPackError("artifact_kind 不是 page-content-pack")
    recorded = pack.get("content_digest")
    if not isinstance(recorded, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded):
        raise ContentPackError("content_digest 缺失或格式非法")
    if content_digest(pack) != recorded:
        raise ContentPackError(
            "content_digest 不一致：内容包在生成后被手改。内容包是母版的单向"
            "派生物——修改内容须回母版并重新编译，不得直接编辑包")
    from jsonschema import Draft202012Validator
    schema_path = Path(__file__).parent / "schemas" / f"page-content-pack-v{pack['schema_version']}.schema.json"
    errors = list(Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).iter_errors(pack))
    if errors:
        raise ContentPackError("内容包 schema 校验失败: " + errors[0].message)
    if pack["schema_version"] == 2:
        _verify_content_model(pack)


def load_content_pack(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    verify_content_pack(payload)
    return payload


# ---------------------------------------------------------------------------
# 一次性身份写入（legacy 母版 → 合法身份母版）
# ---------------------------------------------------------------------------

def propose_page_id_stamping(master_text: str) -> str:
    """在每页页首元信息区写入 page_id 行；幂等，且不改动其他内容。

    提案确定性：pg- + sha256(母版标签|标题)[:10]，仅一次性使用；写入后身份
    由作者与工具按字面保留，跨 revision 不再重算。
    """
    blocks = split_page_blocks(master_text)
    stamped_ids: set[str] = set()
    replacements: list[tuple[int, int, str]] = []
    for block in blocks:
        body = block["body"]
        if declared_page_id(body):
            stamped_ids.add(declared_page_id(body))
            continue
        title_m = TITLE_RE.search(body)
        anchor = title_m.group(1).strip() if title_m else ""
        proposal = f"pg-{sha256_text(f'{block['master_page']}|{anchor}')[:10]}"
        while proposal in stamped_ids:
            proposal = f"pg-{sha256_text(proposal)[:10]}"
        stamped_ids.add(proposal)
        # 插入点：页头行的换行之后（页首元信息区顶部）。
        header_end = block["body"].find("\n")
        insert_at = header_end + 1 if header_end != -1 else len(block["body"])
        replacements.append((block["start_line"], insert_at, proposal))
    if not replacements:
        return master_text
    # 从后往前插入，避免偏移失效；按块 start_line 键配对（重复正文块不可
    # 能共享 start_line，杜绝 zip 错位把身份写进别的页）。
    by_start_line = {line: (insert_at, proposal)
                     for line, insert_at, proposal in replacements}
    out = master_text
    for block in reversed(blocks):
        entry = by_start_line.get(block["start_line"])
        if entry is None:
            continue
        insert_at, proposal = entry
        base = out.find(block["body"])
        if base == -1:
            raise ContentPackError(f"{block['master_page']}: 页块定位失败，无法写入身份")
        pos = base + insert_at
        out = out[:pos] + f"page_id: {proposal}\n" + out[pos:]
    return out
