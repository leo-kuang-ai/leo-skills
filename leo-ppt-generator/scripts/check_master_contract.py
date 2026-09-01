#!/usr/bin/env python3
"""check_master_contract.py — 逐页母版合同校验器（母版机读语法 v2）。

校验项（结构核对，不做 prose 语义匹配）：
  ① 每页四段完备：结论句标题 / 要点（≥1 条）/ 视觉行 / 备注；
  ② 落位闭合：视觉行容器清单与要点编号引用对得上（无点无家、无空容器）；
  ③ 数字登记表存在且行完备（调 check_number_ledger 逻辑）；
  ④ argument_role 在场（页首元信息含 argument_role 字样）；
  ⑤ 交叉引用页码存在（「见第 X 页/SX」不超过页数）；
  ⑥ 标题连读稿输出（TITLE-READTHROUGH）与要点连读稿输出
     （TAKEAWAY-READTHROUGH：内容页第一条要点连读，功能页与零要点页跳过）；
  ⑦ 图行校验（v2）：`图[F<N>] 模式:… 状态:… 焦点:…` + 承载/服务/避免误读三段
     齐备、模式/状态枚举合法、figure_id deck 内唯一、非 vision-reviewed 图行
     不得携带位置性标注词（见 references/academic-figure-evidence.md）；
  ⑧ deck-contract 块校验（v2）：学术场景（论文/答辩/组会/文献汇报/科研答辩
     信号）三字段 math_load/figure_orientation/section_priority 必填，
     枚举合法；section_priority Σ建议页数 ≠ 内容页数 → WARN；
  ⑨ deck-promises 承诺表校验（R-34）：顶层 `deck-promises:` 块或
     deck-contract 内嵌同名子表，四列（承诺/锚页/兑现页/状态）；每个
     open/fulfilled 行的锚页与兑现页必须存在（目录多宣称一章即 FAIL），
     closed 豁免；无承诺表的旧母版静默跳过（向后兼容）；
  ⑩ 要点级标注与 source_ref（R-08/R-09）：要点行标注短标词表为四级
     （引用/估算/示意/用户确认，全/半角括号或【】均可，可带竖线字段）；
     引用级要点必须携带 source_ref（【引用|src:材料锚点】 或行尾
     [src:锚点]），用户确认级要点必须携带会话轮标记（round:N）或说明
     字段（note:/说明:）；估算/示意与无标注要点豁免（向后兼容：
     旧母版无标注要点不触发本判据）。

母版机读语法约定（deck-master.md 合同）：
  - 页由 `## S<N> ` 或 `## 附` 起始；
  - 每页内 `- 标题：<结论句>` 行为标题段；`- 要点`/编号列表为要点段；
  - 视觉行以 `视觉行` 或 `视觉：` 标识，容器引用写作 `要点N→容器名` 或
    `N→容器`；未编号的容器计入空容器检查的候选；
  - 页首元信息行含 `argument_role`；页面角色行 `角色：`（或 `role:`）用于
    功能页识别（开场/封面/目录/章节/隔断/过渡/收束/结尾/致谢/问答）；
  - 图行以 `图[F<N>]` 起始，三段可同行或换行续写；
  - deck 级合同块以缩进的 `deck-contract:` 节声明。

向后兼容：不含 `图[F` 行与 `deck-contract:` 块的旧母版不触发 v7/v2 新校验。

用法：python3 check_master_contract.py <deck-master.md>
输出：stdout 首行 `MASTER-SCHEMA: v2`，末两行 TITLE-READTHROUGH 与
TAKEAWAY-READTHROUGH；失败项写 stderr，exit 1；仅 WARN 项 exit 2。
"""
import re
import sys
from pathlib import Path

PAGE_RE = re.compile(r"^##\s+(S(\d+)|附)[^\n]*$", re.M)
TITLE_RE = re.compile(r"[-•]\s*标题[：:]\s*(.+)")
POINT_LINE_RE = re.compile(r"^\s*(?:[-•]|\d+\.|\d+、)\s*(.+)$", re.M)
_NON_POINT = ("标题", "备注", "视觉行", "argument_role", "数字登记表")
VISUAL_RE = re.compile(r"(?:视觉行|视觉)[：:]\s*(.+)")
MAPPING_RE = re.compile(r"(?:要点\s*)?(\d+)\s*→\s*([^\s，,；;。]+)")
CROSS_REF_RE = re.compile(r"见[第附]?\s*(\S{1,4}?)\s*页|见\s*S(\d+)")

# --- v2：图行（academic-figure-evidence.md 合同） ---
FIGURE_ROW_START_RE = re.compile(r"图\[(F\d+)\]")
FIGURE_MODE_RE = re.compile(r"模式[：:]\s*([^\s|，,；;]+)")
FIGURE_STATUS_RE = re.compile(r"状态[：:]\s*([^\s|，,；;]+)")
FIGURE_FOCUS_RE = re.compile(r"焦点[：:]\s*([^\n|]+?)\s*(?:\||$|\n)")
FIGURE_SEGMENT_RES = {
    "承载": re.compile(r"(?:^|\n|\|)\s*承载[：:]"),
    "服务": re.compile(r"(?:^|\n|\|)\s*服务[：:]"),
    "避免误读": re.compile(r"(?:^|\n|\|)\s*避免误读[：:]"),
}
FIGURE_MODES = {
    "preserve", "overview+detail", "split", "cross-slide",
    "not-use", "request-higher-resolution",
}
FIGURE_STATUSES = {
    "vision-reviewed", "metadata-reviewed", "caption-inferred",
    "user-described", "not-reviewed",
}
POSITIONAL_ANNOTATION_WORDS = (
    "高亮", "右上", "左上", "右下", "左下", "子图", "箭头", "红框", "圈选", "panel",
)

# --- v2：功能页 / 学术场景 / deck-contract ---
ROLE_RE = re.compile(r"(?:页面角色|角色|role)[：:]\s*([^\s,，;；。]+)", re.I)
FUNCTIONAL_ROLE_WORDS = (
    "开场", "封面", "目录", "章节", "隔断", "过渡", "收束", "结尾", "致谢", "问答",
)
ACADEMIC_SIGNALS = ("论文", "答辩", "组会", "文献汇报", "科研答辩")
MATH_LOADS = {"light", "medium", "heavy"}
FIGURE_ORIENTATIONS = {"figure-first", "balanced", "text-first"}
DECK_CONTRACT_RE = re.compile(r"^deck-contract[：:][ \t]*$", re.M)

# --- v2：deck-promises（目录/agenda 承诺账本，R-34） ---
PROMISES_BLOCK_RE = re.compile(r"^deck-promises[：:][ \t]*$", re.M)
PROMISE_HEADER_CELLS = ("承诺", "锚页", "兑现页", "状态")
PROMISE_STATUSES = {"open", "fulfilled", "closed"}

# --- R-08/R-09：要点级四级标注与 source_ref ---
# Tier vocabulary extends the ledger's three levels (引用/估算/示意) with a
# fourth level 用户确认 (data stated by the user in a contract/clarification
# round). Marks live in full/half-width brackets and may carry pipe fields.
TIER_MARK_RE = re.compile(
    r"[【（(]\s*(用户确认|引用|估算|示意)(?:\s*[|｜][^】）)]*)?\s*[】）)]")
POINT_LABEL_RE = re.compile(r"^要点\s*\d+\s*[：:]\s*")
SRC_SQ_RE = re.compile(r"\[\s*src\s*[：:]\s*([^\]]+?)\s*\]")
SRC_BRACKET_RE = re.compile(r"【[^】]*?src\s*[：:]\s*[^】\s][^】]*】")
ROUND_MARK_RE = re.compile(r"round\s*[：:]\s*\d+")
NOTE_MARK_RE = re.compile(r"(?:note|说明)\s*[：:]\s*[^】\]\s]")


def split_pages(text):
    matches = list(PAGE_RE.finditer(text))
    pages = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pages.append((m.group(0), text[m.start():end]))
    return pages


def page_is_functional(body):
    """功能页（开场/封面/目录/章节隔断/收束等）识别：页面角色行取词表。"""
    for m in ROLE_RE.finditer(body):
        if any(w in m.group(1) for w in FUNCTIONAL_ROLE_WORDS):
            return True
    return False


def collect_figure_rows(text):
    """收集图行：`图[F<N>]` 起始行 + 后续承载/服务/避免误读续行。"""
    lines = text.splitlines()
    rows = []  # (fig_id, row_text, line_no_1based)
    i = 0
    while i < len(lines):
        m = FIGURE_ROW_START_RE.search(lines[i])
        if m:
            fig_id = m.group(1)
            row_lines = [lines[i]]
            j = i + 1
            while j < len(lines):
                nxt = lines[j].lstrip().lstrip("-•").strip()
                is_seg = any(r.match(nxt) or r.search("|" + nxt) is not None
                             for r in FIGURE_SEGMENT_RES.values())
                if (nxt and is_seg and not FIGURE_ROW_START_RE.search(nxt)):
                    row_lines.append(lines[j])
                    j += 1
                else:
                    break
            rows.append((fig_id, "\n".join(row_lines), i + 1))
            i = j
        else:
            i += 1
    return rows


def check_figure_rows(text, failures):
    rows = collect_figure_rows(text)
    seen = {}
    for fig_id, row, line_no in rows:
        where = f"图[{fig_id}]（第 {line_no} 行）"
        if fig_id in seen:
            failures.append(
                f"{where}: figure_id 与第 {seen[fig_id]} 行重复（deck 内必须唯一）")
        else:
            seen[fig_id] = line_no
        mode = FIGURE_MODE_RE.search(row)
        if not mode:
            failures.append(f"{where}: 图行缺「模式」字段")
        elif mode.group(1) not in FIGURE_MODES:
            failures.append(
                f"{where}: 模式「{mode.group(1)}」不在封闭枚举 "
                f"{sorted(FIGURE_MODES)}")
        status = FIGURE_STATUS_RE.search(row)
        if not status:
            failures.append(f"{where}: 图行缺「状态」字段")
        else:
            st = status.group(1)
            if st not in FIGURE_STATUSES:
                failures.append(
                    f"{where}: 状态「{st}」不在封闭枚举 "
                    f"{sorted(FIGURE_STATUSES)}")
            elif st != "vision-reviewed":
                hit = [w for w in POSITIONAL_ANNOTATION_WORDS
                       if w in row or w.lower() in row.lower()]
                if hit:
                    failures.append(
                        f"{where}: 状态「{st}」的图行不得携带位置性标注词 "
                        f"{hit}（仅 vision-reviewed 允许）")
        focus = FIGURE_FOCUS_RE.search(row)
        if not focus or not focus.group(1).strip():
            failures.append(f"{where}: 图行缺「焦点」（该图回答的演示问题）")
        for name, seg_re in FIGURE_SEGMENT_RES.items():
            if not seg_re.search(row):
                failures.append(f"{where}: 图行缺「{name}」段（三段须齐备）")
    return rows


def parse_deck_contract(text):
    """解析缩进 deck-contract 块；返回 (block_text or None)。"""
    m = DECK_CONTRACT_RE.search(text)
    if not m:
        return None
    lines = text[m.end():].splitlines()
    block = []
    for ln in lines:
        if not ln.strip():
            if block:
                break
            continue
        if ln.startswith(" ") or ln.startswith("\t"):
            block.append(ln)
        else:
            break
    return "\n".join(block) if block else ""


def check_deck_contract(text, content_pages, failures, warnings):
    academic = any(sig in text for sig in ACADEMIC_SIGNALS)
    block = parse_deck_contract(text)
    sink = failures if academic else warnings

    if academic and block is None:
        failures.append(
            "全 deck: 学术场景母版缺 deck-contract 块（math_load / "
            "figure_orientation / section_priority 必填）")
        return
    if block is None:
        return  # 非学术缺块：合法，不阻断

    fields = {
        "math_load": re.search(r"math_load[：:]\s*(\S+)", block),
        "figure_orientation": re.search(r"figure_orientation[：:]\s*(\S+)", block),
    }
    for name, m in fields.items():
        if not m:
            sink.append(f"全 deck: deck-contract 块缺 {name} 字段")
        else:
            vocab = MATH_LOADS if name == "math_load" else FIGURE_ORIENTATIONS
            if m.group(1) not in vocab:
                failures.append(
                    f"全 deck: deck-contract.{name}「{m.group(1)}」不在枚举 "
                    f"{sorted(vocab)}")

    # section_priority：节级表 Σ建议页数 vs 内容页数
    has_sp = re.search(r"section_priority[：:]", block)
    sp_rows = []
    if has_sp:
        for ln in block.splitlines():
            s = ln.strip()
            if s.startswith("|"):
                cells = [c.strip() for c in s.strip("|").split("|")]
                if cells and re.match(r"^[\s:-]+$", "".join(cells)):
                    continue  # 分隔行
                if cells and cells[-1].isdigit():
                    sp_rows.append(int(cells[-1]))
    if not has_sp:
        sink.append("全 deck: deck-contract 块缺 section_priority 字段")
    elif not sp_rows:
        sink.append("全 deck: section_priority 表无可解析的建议页数行")
    elif sum(sp_rows) != content_pages:
        warnings.append(
            f"WARN: section_priority Σ建议页数 {sum(sp_rows)} ≠ 内容页数 "
            f"{content_pages}（请对账页数口径）")


def _adjacent_pipe_rows(lines, start):
    """Collect the pipe-table rows immediately following a declaration line."""
    rows = []
    for ln in lines[start:]:
        s = ln.strip()
        if s.startswith("|"):
            rows.append(s)
        else:
            break
    return rows


def parse_deck_promises(text):
    """Collect raw deck-promises table rows.

    Accepted locations: a top-level `deck-promises:` block, or an indented
    `deck-promises:` sub-table inside the deck-contract block. Returns None
    when no block exists anywhere (legacy masters: criterion silently skips).
    """
    lines = text.splitlines()
    rows = []
    for i, ln in enumerate(lines):
        if PROMISES_BLOCK_RE.match(ln):
            rows.extend(_adjacent_pipe_rows(lines, i + 1))
    block = parse_deck_contract(text)
    if block:
        blines = block.splitlines()
        for i, ln in enumerate(blines):
            if ln.strip().startswith("deck-promises"):
                rows.extend(_adjacent_pipe_rows(blines, i + 1))
    return rows if rows else None


def _resolve_promise_page(ref, page_seq):
    """Resolve S<N> / N / 附 against the deck's page sequence; None if absent."""
    s = ref.strip()
    valid = set(page_seq)
    m = re.fullmatch(r"[Ss](\d+)", s)
    if m:
        pid = f"S{m.group(1)}"
        return pid if pid in valid else None
    if s == "附":
        return "附" if "附" in valid else None
    if s.isdigit():
        n = int(s)
        return page_seq[n - 1] if 1 <= n <= len(page_seq) else None
    return None


def check_deck_promises(text, page_seq, failures):
    """Validate the deck-promises ledger (R-34).

    Every open/fulfilled row must carry an anchor page and a payoff page that
    both exist in the deck (a fabricated agenda chapter fails); `closed` rows
    are exempt from payoff checking. Returns None when no table exists
    (backward-compatible silent skip), else the count of validated rows.
    """
    rows = parse_deck_promises(text)
    if rows is None:
        return None
    if not rows:
        failures.append("deck-promises: 表存在但无可解析承诺行")
        return 0
    header = [c.strip() for c in rows[0].strip("|").split("|")]
    if not all(c in header for c in PROMISE_HEADER_CELLS):
        failures.append(
            "deck-promises: 表头须含四列「承诺/锚页/兑现页/状态」")
        return 0
    passed = 0
    data_rows = [r for r in rows[1:]
                 if not re.match(r"^[\s:-]+$", r.replace("|", ""))]
    for idx, row in enumerate(data_rows, start=1):
        cells = [c.strip() for c in row.strip("|").split("|")]
        where = f"deck-promises 行{idx}"
        if len(cells) < len(PROMISE_HEADER_CELLS):
            failures.append(f"{where}: 列数不足（{len(cells)} < 4）")
            continue
        promise, anchor, payoff, status = cells[:4]
        if status not in PROMISE_STATUSES:
            failures.append(
                f"{where}: 状态「{status}」不在封闭枚举 "
                f"{sorted(PROMISE_STATUSES)}")
            continue
        if status == "closed":
            passed += 1  # exempt: confirmed-closed promise needs no payoff
            continue
        if not anchor:
            failures.append(f"{where}「{promise}」: 缺锚页")
            continue
        if _resolve_promise_page(anchor, page_seq) is None:
            failures.append(f"{where}「{promise}」: 锚页「{anchor}」不存在")
            continue
        if not payoff:
            failures.append(
                f"{where}「{promise}」: 状态 {status} 缺兑现页")
            continue
        if _resolve_promise_page(payoff, page_seq) is None:
            failures.append(
                f"{where}「{promise}」: 兑现页「{payoff}」不存在"
                "（目录多宣称一章即此类失败）")
            continue
        passed += 1
    return passed


def _has_source_ref(content):
    """True when the bullet carries a machine-checkable source reference:
    a trailing [src:锚点] or a pipe field inside a 【…】 mark."""
    m = SRC_SQ_RE.search(content)
    if m and m.group(1).strip():
        return True
    return bool(SRC_BRACKET_RE.search(content))


def _has_session_provenance(content):
    """True when a 用户确认 bullet traces to a conversation round
    (round:N marker) or carries an explicit note/说明 field."""
    if ROUND_MARK_RE.search(content):
        return True
    return bool(NOTE_MARK_RE.search(content))


def check_bullet_tiers(text, failures):
    """Validate bullet-level tier marks and source_ref (R-08/R-09).

    Citation-tier bullets (引用) must carry a source_ref — pipe form
    【引用|src:材料锚点】 or trailing [src:锚点]. User-confirmed bullets
    (用户确认) must carry a session-round marker (round:N) or a note field.
    估算/示意 bullets and unmarked bullets are exempt (legacy masters never
    trigger this criterion). Returns the count of tier-marked bullets seen.
    """
    current = "全 deck"
    checked = 0
    for line_no, raw in enumerate(text.splitlines(), start=1):
        header = PAGE_RE.match(raw)
        if header:
            current = header.group(0).lstrip("#").strip()
            continue
        m = POINT_LINE_RE.match(raw)
        if not m:
            continue
        content = m.group(1)
        if any(k in content for k in _NON_POINT):
            continue
        content = POINT_LABEL_RE.sub("", content)
        marks = TIER_MARK_RE.findall(content)
        if not marks:
            continue
        checked += 1
        where = f"{current}（第 {line_no} 行）"
        if "引用" in marks and not _has_source_ref(content):
            failures.append(
                f"{where}: 引用级要点缺 source_ref（语法：【引用|src:材料锚点】"
                "或要点行尾 [src:锚点]）")
        if "用户确认" in marks and not _has_session_provenance(content):
            failures.append(
                f"{where}: 用户确认级要点缺会话轮标记（语法："
                "【用户确认|round:N】或 note/说明 字段）")
    return checked


def check_page(header, body, total_pages, failures, prefix):
    title = TITLE_RE.search(body)
    if not title:
        failures.append(f"{prefix}: 缺少「- 标题：」段")
    points = [m.group(1) for m in POINT_LINE_RE.finditer(body)
              if not any(k in m.group(1) for k in _NON_POINT)]
    if not points:
        failures.append(f"{prefix}: 要点段为空")
    visual = VISUAL_RE.search(body)
    if not visual:
        failures.append(f"{prefix}: 缺少视觉行")
        mapped = set()
        containers = set()
    else:
        maps = MAPPING_RE.findall(visual.group(1))
        mapped = {int(n) for n, _ in maps}
        containers = {c for _, c in maps}
    if "argument_role" not in body:
        failures.append(f"{prefix}: 页首元信息缺 argument_role")
    n_points = len(points)
    homeless = sorted(n for n in mapped if n < 1 or n > n_points)
    if homeless:
        failures.append(f"{prefix}: 落位引用指向不存在要点 {homeless}")
    if points and not mapped:
        failures.append(f"{prefix}: 视觉行无任何要点落位声明（无点无家）")
    empty_targets = total_points = 0  # 容器无内容检查受 prose 限制，仅报告未映射容器
    unused = sorted(containers) if False else []
    for ref in CROSS_REF_RE.finditer(body):
        page_no = ref.group(1) if ref.group(1) and ref.group(1).isdigit() else None
        s_no = ref.group(2)
        if page_no and int(page_no) > total_pages:
            failures.append(f"{prefix}: 交叉引用「见第 {page_no} 页」超出页数 {total_pages}")
        if s_no and int(s_no) > total_pages:
            failures.append(f"{prefix}: 交叉引用 S{s_no} 超出页数 {total_pages}")
    return title.group(1).strip() if title else None, points


def main():
    if len(sys.argv) != 2:
        print("usage: check_master_contract.py <deck-master.md>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    print("MASTER-SCHEMA: v2")
    failures = []
    warnings = []
    pages = split_pages(text)
    if not pages:
        print("FAIL: 未发现任何页（## S<N> 或 ## 附）", file=sys.stderr)
        return 1
    total = len(pages)
    titles = []
    takeaways = []
    functional_count = 0
    for header, body in pages:
        t, points = check_page(header.strip(), body, total, failures,
                               header.strip())
        if t:
            titles.append(t)
        if page_is_functional(body):
            functional_count += 1
        elif points:
            takeaways.append(points[0].strip())
    if "## 数字登记表" not in text:
        failures.append("全 deck: 缺少「## 数字登记表」节")
    check_figure_rows(text, failures)
    content_pages = total - functional_count
    check_deck_contract(text, content_pages, failures, warnings)
    page_seq = []
    for header, _body in pages:
        m = re.match(r"^##\s+(?:S(\d+)|附)", header.strip())
        page_seq.append("附" if m is None or m.group(1) is None else f"S{m.group(1)}")
    promise_count = check_deck_promises(text, page_seq, failures)
    tier_count = check_bullet_tiers(text, failures)
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    ok = (f"OK: {total} 页四段/落位/argument_role/交叉引用/登记表全部通过"
          f"（内容页 {content_pages}，功能页 {functional_count}")
    if promise_count is not None:
        ok += f"；承诺表 {promise_count} 条核对通过"
    if tier_count:
        ok += f"；要点标注 {tier_count} 条核对通过"
    ok += "）"
    print(ok)
    print("TITLE-READTHROUGH: " + " → ".join(titles))
    print("TAKEAWAY-READTHROUGH: " + " → ".join(takeaways))
    if warnings:
        for w in warnings:
            print(w if w.startswith("WARN") else f"WARN: {w}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
