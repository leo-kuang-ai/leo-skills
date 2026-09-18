"""U11/R-75+R-76 版式重排提案与六节点决策简报（KTD9 extend）。

R-75：容量 overflow → ≤3 项带一句话代价的菜单（换版式 / 内容减法），
人做选择。三条硬纪律：永不自动改正文（``preview_apply`` 只返回假设结果，
不写任何状态）；不缩字号（红线，提案只动版式与内容量）；不可行不硬凑
（无可行方案时如实报告并给替代路线）。

R-76：六个推进节点的三行固定摘要（变了什么/影响什么/需要决定什么），
用户语言强制（术语白名单通俗化、单行长度上限、清单字段"计数＋页码区间"）。
工具 JSON 保留结构化全量证据；呈现缺席降级 CLI 报告；委托模式仍生成简报、
仅呈现被豁免（user-delegated 留痕）。

确定性：同输入同输出；波及页数等事实一律来自调用方传入（compute_impact
等生产者），本模块不复述、不编造。
"""

from __future__ import annotations

from .render.layout import capacity_level, visual_width

MAX_PROPOSALS = 3
# 叙事减法的安全下限：减完仍不满足版式 count_min 即不可行，不硬凑。
SIX_NODES = ("contract", "outline", "master", "visual-sample",
             "partial-gate", "delivery-gate")
NODE_LABELS = {
    "contract": "内容合同",
    "outline": "大纲",
    "master": "母版",
    "visual-sample": "视觉方向＋样张",
    "partial-gate": "PARTIAL-GATE（阶段交付门）",
    "delivery-gate": "DELIVERY-GATE（交付门）",
}
MAX_LINE_CHARS = 60
PRESENTATION_MODES = ("presented", "cli-fallback", "exempt-user-delegated")

# 用户语言强制项：术语白名单通俗改写（R-76 范围示例起步，随判例扩充）。
TERM_REWRITES = {
    "失效工件": "之前确认过的样张需要重新确认",
    "指纹失效": "文件变了，需要重新检查",
    "provenance": "来源记录",
    "post-confirm": "确认后的修订",
    "overflow": "内容超出版式容量",
}


class ProposalError(ValueError):
    """提案/简报合同失败；``reason_code`` 稳定命名。"""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail


# --------------------------------------------------------------------------- #
# R-75 容量重排提案
# --------------------------------------------------------------------------- #

def _fit_verdict(bank: dict, layout_id: str, page: dict) -> tuple[bool, list[str]]:
    """与 check_deck_geometry --capacity 同口径的可行判定（不含软超）。"""

    sidecar = bank.get(layout_id) or {}
    capacity = sidecar.get("content_capacity", {})
    reasons: list[str] = []
    points = page.get("points")
    if isinstance(points, list):
        for slot_name, slot in sorted(capacity.items()):
            if "count_min" not in slot:
                continue
            n = len(points)
            if n < slot["count_min"] or n > slot["count_max"]:
                reasons.append(f"count:{slot_name} {n}∉[{slot['count_min']},{slot['count_max']}]")
    slots_text = page.get("slots") or {}
    for slot_name, text in sorted(slots_text.items()):
        slot = capacity.get(slot_name) or {}
        if "max_chars" not in slot:
            continue
        if capacity_level(visual_width(str(text)), slot["max_chars"]) == "overflow":
            reasons.append(f"text:{slot_name} 硬超 {slot['max_chars']}")
    return (not reasons), reasons


def _subtraction_for(bank: dict, layout_id: str, page: dict) -> list[dict] | None:
    """当前版式装下所需的最小内容减法；无法落在 [count_min, count_max] 则 None。"""

    capacity = (bank.get(layout_id) or {}).get("content_capacity", {})
    subtractions: list[dict] = []
    points = page.get("points")
    if isinstance(points, list):
        points_slot = next(
            (slot for _name, slot in sorted(capacity.items()) if "count_min" in slot), None)
        if points_slot is not None:
            target = points_slot["count_max"]
            if len(points) > target:
                if target < points_slot["count_min"]:
                    return None
                removed = points[target:]
                chars = int(sum(visual_width(str(item)) for item in removed))
                subtractions.append({
                    "slot": "points", "action": "drop-to", "count": target,
                    "chars_removed_estimate": chars,
                    "narrative_impact": f"少 {len(removed)} 条佐证（保留前 {target} 条）",
                })
    for slot_name, text in sorted((page.get("slots") or {}).items()):
        slot = capacity.get(slot_name) or {}
        if "max_chars" not in slot:
            continue
        used = visual_width(str(text))
        if capacity_level(used, slot["max_chars"]) == "overflow":
            subtractions.append({
                "slot": slot_name, "action": "trim-to", "count": slot["max_chars"],
                "chars_removed_estimate": int(used - slot["max_chars"]),
                "narrative_impact": f"{slot_name} 文字压到 {slot['max_chars']} 宽度内",
            })
    return subtractions or None


def capacity_proposals(*, page: dict, bank: dict, max_proposals: int = MAX_PROPOSALS) -> dict:
    """overflow 页 → ≤3 项提案菜单（首选标注 + 一句话代价）；确定性。

    顺序：先"换版式即可装下"的同类候选（代价最低），再"当前版式＋内容
    减法"；两者皆无 → ``infeasible`` 如实报告并给替代路线（不硬凑）。
    """

    if not bank:
        raise ProposalError("proposal_bank_empty", "版式库为空，无法生成提案")
    layout_id = str(page.get("layout", ""))
    current = bank.get(layout_id)
    if current is None:
        raise ProposalError("proposal_layout_unknown", f"未知版式 {layout_id!r}")
    fits_now, overflow_reasons = _fit_verdict(bank, layout_id, page)
    proposals: list[dict] = []
    if not fits_now:
        # 提案只服务溢出页：未溢出时给"换版式"菜单会诱导无意义改动。
        page_type = current.get("page_type")
        # ① 换版式即装下（同 page_type，当前内容原样可容纳）。
        candidates: list[tuple[str, int]] = []
        for other_id, sidecar in sorted(bank.items()):
            if other_id == layout_id or sidecar.get("page_type") != page_type:
                continue
            fits, _ = _fit_verdict(bank, other_id, page)
            if fits:
                best = max(
                    (slot.get("max_chars", 0)
                     for slot in (sidecar.get("content_capacity") or {}).values()
                     if "max_chars" in slot),
                    default=0)
                candidates.append((other_id, best))
        candidates.sort(key=lambda kv: (-kv[1], kv[0]))
        for other_id, _best in candidates:
            if len(proposals) >= max_proposals:
                break
            proposals.append({
                "kind": "switch-layout",
                "layout": other_id,
                "subtractions": [],
                "cost_line": f"换版式 {other_id}（{bank[other_id].get('name', other_id)}），"
                             "内容不动；版式结构变化",
                "apply_hint": "走母版修订 + post-confirm 通道；本提案不自动应用",
            })
        # ② 当前版式 + 内容减法。
        if len(proposals) < max_proposals:
            subtractions = _subtraction_for(bank, layout_id, page)
            if subtractions is not None:
                chars = sum(item["chars_removed_estimate"] for item in subtractions)
                proposals.append({
                    "kind": "reduce-content",
                    "layout": layout_id,
                    "subtractions": subtractions,
                    "cost_line": f"保留版式，内容减法约减 {chars} 字宽；"
                                 + "；".join(item["narrative_impact"] for item in subtractions),
                    "apply_hint": "走母版修订 + post-confirm 通道；本提案不自动应用",
                })
    for rank, proposal in enumerate(proposals, 1):
        proposal["rank"] = rank
        proposal["preferred"] = rank == 1
    if fits_now:
        # 负例闭环：未溢出的页不给提案。
        return {
            "schema_version": 1,
            "kind": "layout-proposals",
            "page": page.get("page"),
            "layout": layout_id,
            "fits": True,
            "overflow": [],
            "proposals": [],
            "infeasible": None,
            "note": "提案只描述不应用（KTD9）；不缩字号；应用走母版修订 + post-confirm",
        }
    result = {
        "schema_version": 1,
        "kind": "layout-proposals",
        "page": page.get("page"),
        "layout": layout_id,
        "fits": fits_now,
        "overflow": overflow_reasons,
        "proposals": proposals,
        "infeasible": None,
        "note": "提案只描述不应用（KTD9）；不缩字号；应用走母版修订 + post-confirm",
    }
    if not fits_now and not proposals:
        result["infeasible"] = {
            "reason": "no-same-type-fits-and-no-feasible-subtraction",
            "alternatives": [
                "拆页：把该页内容拆成两页（走母版修订）",
                "降密度：按 3a 数据密度路由改走可编辑/原生图表路线",
                "改交付形态：partial-hybrid 混合确认",
            ],
        }
    return result


def preview_apply(page: dict, proposal: dict) -> dict:
    """返回"若应用该提案"的假设页面（纯函数，不写任何状态——KTD9）。"""

    applied = {**page, "slots": dict(page.get("slots") or {})}
    if proposal.get("kind") == "switch-layout":
        applied["layout"] = proposal["layout"]
        return applied
    points = page.get("points")
    for item in proposal.get("subtractions", []):
        if item["slot"] == "points" and isinstance(points, list):
            applied["points"] = list(points[: item["count"]])
        elif item["action"] == "trim-to":
            text = str(applied["slots"].get(item["slot"], ""))
            kept, width = [], 0.0
            for ch in text:
                if width + visual_width(ch) > item["count"]:
                    break
                kept.append(ch)
                width += visual_width(ch)
            applied["slots"][item["slot"]] = "".join(kept)
    return applied


def fits(bank: dict, page: dict) -> bool:
    """应用假设结果后的容量复检（与 check_deck_geometry 硬超口径一致）。"""

    return _fit_verdict(bank, str(page.get("layout", "")), page)[0]


# --------------------------------------------------------------------------- #
# R-76 六节点决策简报
# --------------------------------------------------------------------------- #

def plain_term(text: str) -> str:
    """术语白名单通俗改写（用户语言强制项）。"""

    for term, plain in TERM_REWRITES.items():
        text = text.replace(term, plain)
    return text


def format_page_ranges(pages: list[int]) -> str:
    """确定性页码区间："第 3、7、12–18 页，共 9 页"（清单按需下钻）。"""

    if not pages:
        return "无波及页"
    ordered = sorted(set(int(p) for p in pages))
    ranges: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for number in ordered[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append((start, previous))
        start = previous = number
    ranges.append((start, previous))
    parts = [
        f"{start}" if start == end else f"{start}–{end}"
        for start, end in ranges
    ]
    return f"第 {'、'.join(parts)} 页，共 {len(ordered)} 页"


def decision_brief(
    *,
    node: str,
    changed: str,
    impact: str,
    decision: str,
    affected_pages: list[int] | None = None,
    presentation: str = "presented",
) -> dict:
    """单节点三行简报（①变了什么②影响什么③需要决定什么）。

    六要素合同：node 必须是六节点之一；三要素缺一即拒（R-76 验收 1）。
    波及页数只渲染调用方传入的事实（与 compute_impact 一致，不编造）。
    委托模式：presentation=exempt-user-delegated 仍生成完整简报，仅呈现被
    豁免（留痕口径）。
    """

    if node not in SIX_NODES:
        raise ProposalError("brief_node_invalid", f"未知节点 {node!r}（六节点：{SIX_NODES}）")
    if presentation not in PRESENTATION_MODES:
        raise ProposalError("brief_presentation_invalid", f"未知呈现模式 {presentation!r}")
    fields = {"changed": changed, "impact": impact, "decision": decision}
    missing = [name for name, value in fields.items() if not (value and str(value).strip())]
    if missing:
        raise ProposalError("brief_field_missing", f"三要素缺失：{missing}")
    lines = {name: plain_term(str(value).strip()) for name, value in fields.items()}
    if affected_pages is not None:
        lines["impact"] = f"{lines['impact']}（{format_page_ranges(affected_pages)}）"
    for name, line in lines.items():
        if len(line) > MAX_LINE_CHARS:
            raise ProposalError(
                "brief_line_too_long",
                f"{name} 行 {len(line)} 字超上限 {MAX_LINE_CHARS}：{line}")
    return {
        "schema_version": 1,
        "kind": "decision-brief",
        "node": node,
        "node_label": NODE_LABELS[node],
        "lines": {
            "changed": lines["changed"],
            "impact": lines["impact"],
            "decision": lines["decision"],
        },
        "affected_pages": sorted(set(int(p) for p in affected_pages)) if affected_pages else [],
        "presentation": presentation,
        "evidence": "波及页数以 compute_impact.py 输出为准，本简报不复算不编造",
    }


def render_brief(brief: dict) -> str:
    """三行人类可读文本（CLI 降级通道与聊天呈现共用同一文本）。"""

    label = brief["node_label"]
    lines = brief["lines"]
    return (
        f"【{label}】\n"
        f"① 变了什么：{lines['changed']}\n"
        f"② 影响什么：{lines['impact']}\n"
        f"③ 需要决定：{lines['decision']}"
    )
