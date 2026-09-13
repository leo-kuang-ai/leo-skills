#!/usr/bin/env python3
"""suggest_layout.py — 逐页版式匹配的确定性打分器（B2，模板调度师）。

四步链（原创规则链，机制吸收自优先级序思想；无上游文本）：

    角色对齐 → 结构匹配 → 节奏感 → 置信度裁决

- 角色对齐：``page_role``（13_页面语义 25 角色）映射到版式 ``page_type``
  （cover/agenda/section/content/data/closing）；角色不符的候选直接出局。
- 结构匹配：页面侧 {要点条数, 预估字数, 数据点数} 对 sidecar
  ``content_capacity``（count 区间包含度 × max_chars 字数覆盖度；超容量
  硬超候选直接排除）。
- 节奏感：``reuse_friendly=false`` 且已用 → 硬排除（与
  check_layout_reuse.py 同口径）；已用版式 -0.4、与上一页同版式再 -0.4；
  风格路由 preferred +0.1 / discouraged -0.2（风格层参与但不越权）。
- 置信度裁决：top1 综合分 < 0.5 → ``decision: "undecided"``（合法结果，
  不是失败）；**禁止编造版式 id**——候选只能来自 sidecar 枚举集，输出 id
  不在枚举集内即脚本自身 bug（防御断言 exit 2）。

打分公式（固定、可解释）::

    score = 0.45 * role_fit + 0.40 * capacity_fit + 0.15 * rhythm + routing_adj

无状态只读：不写任何文件、不记忆跨调用状态。

用法::

    python3 scripts/suggest_layout.py [input.json] [--style 清爽专业风] [--json-schema]
    cat input.json | python3 scripts/suggest_layout.py

输入（stdin 或文件）::

    {"pages": [{"page": 3, "page_role": "对比·多维", "points": 2,
                "est_chars": 120, "data_points": 0, "image_sources": 0,
                "already_used": ["P1", "P4"]}]}

输出（stdout，键排序、确定性、无时间戳）：逐页 candidates（top 2）、
confidence、decision（auto / undecided）。

退出码（CI-4）：0 = 正常产出（auto 与 undecided 均合法）；2 = 输入 schema
错误 / 脚本防御断言触发。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.asset_resolver import AssetResolver, ResolverError
from leo_ppt_generator.content_projection import page_types_for_role
from leo_ppt_generator.page_intent import analyze_page_intent, semantic_layout_adjustment
from leo_ppt_generator.render.layout import capacity_level
from leo_ppt_generator.layout_selection import rank_page, load_style_routing, _role_fit, _capacity_fit, _rhythm

W_ROLE, W_CAPACITY, W_RHYTHM = 0.45, 0.40, 0.15
CONFIDENCE_FLOOR = 0.5
TOP_CANDIDATES = 2

# 13_页面语义 25 角色 → 版式 page_type（6 值枚举）。未列角色按中性 0.5 评分。
# 角色映射唯一来自 page-type-regime-v2，推荐脚本只消费不复制。

INPUT_SCHEMA = {
    "type": "object",
    "required": ["pages"],
    "properties": {
        "backend": {"type": "string", "enum": ["image", "render:html"]},
        "pages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["page", "page_role"],
                "properties": {
                    "page": {"type": "integer"},
                    "page_role": {"type": "string"},
                    "points": {"type": "integer"},
                    "est_chars": {"type": "number"},
                    "data_points": {"type": "integer"},
                    "image_sources": {"type": "integer"},
                    "already_used": {"type": "array", "items": {"type": "string"}},
                    "previous_layout": {"type": "string"},
                },
            },
        }
    },
}


def _compact_id(entity: dict) -> str:
    """Return the stable public alias while retaining the canonical asset ID."""
    aliases = entity.get("aliases") or []
    return str(aliases[0] if aliases else entity["asset_id"])


def load_bank(*, home: Path | None = None) -> dict[str, dict]:
    """Load layout profiles through the catalog-backed resolver.

    The scorer consumes a small compatibility projection (page type, slots and
    reuse policy), while ``layout.json`` remains the only source of truth.
    """
    bank: dict[str, dict] = {}
    resolver = AssetResolver(home=home)
    for entity in resolver.entities:
        if entity.get("kind") != "layout":
            continue
        resolved = resolver.resolve(entity["asset_id"])
        data = resolved["data"]
        layout_id = _compact_id({**data, "asset_id": entity["asset_id"]})
        bank[layout_id] = {
            "layout_id": layout_id,
            "asset_id": entity["asset_id"],
            "name": data.get("name"),
            "page_type": data.get("page_role", "content"),
            "content_capacity": data.get("slots") or {},
            "reuse_friendly": data.get("reuse_friendly", True),
            "max_per_deck": data.get("max_per_deck", 1),
            "renderer_support": data.get("renderer_support") or {},
        }
    return bank


def score_page(page, bank, factor, adjust, backend=None):
    """轻量输入适配；完整排名归 runtime，摘要最多显示两项。"""
    result = rank_page(page, bank, factor, adjust, backend)
    return {**result, "candidates": result["candidates"][:TOP_CANDIDATES]}


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:]]
    style_name = None
    backend = None
    if "--backend" in args:
        idx = args.index("--backend")
        if idx + 1 >= len(args):
            print("用法错误: --backend 需要 image 或 render:html", file=sys.stderr)
            return 2
        backend = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    if "--json-schema" in args:
        print(json.dumps(INPUT_SCHEMA, ensure_ascii=False, indent=2))
        return 0
    home = None
    if "--home" in args:
        idx = args.index("--home")
        if idx + 1 >= len(args):
            print("用法错误: --home 需要目录", file=sys.stderr)
            return 2
        home = Path(args[idx + 1]).expanduser().resolve()
        args = args[:idx] + args[idx + 2:]
    if "--style" in args:
        idx = args.index("--style")
        if idx + 1 >= len(args):
            print("用法错误: --style 需要风格名", file=sys.stderr)
            return 2
        style_name = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    input_text = ""
    if args:
        path = Path(args[0])
        if not path.is_file():
            print(f"[ERROR] {path}: 文件不存在", file=sys.stderr)
            return 2
        input_text = path.read_text(encoding="utf-8")
    else:
        input_text = sys.stdin.read()
    try:
        payload = json.loads(input_text)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] 输入 JSON 不可解析（{exc}）", file=sys.stderr)
        return 2
    if not isinstance(payload, dict) or not isinstance(payload.get("pages"), list):
        print("[ERROR] 输入须为 {\"pages\": [...]}（--json-schema 查看 schema）",
              file=sys.stderr)
        return 2
    pages = payload["pages"]
    backend = backend if backend is not None else payload.get("backend")
    if backend is not None and backend not in ("image", "render:html"):
        print("[ERROR] backend 必须为 image 或 render:html", file=sys.stderr)
        return 2
    if not pages or not all(
        isinstance(p, dict) and "page" in p and "page_role" in p for p in pages
    ):
        print("[ERROR] pages[] 每页必须含 page 与 page_role", file=sys.stderr)
        return 2

    try:
        resolver = AssetResolver(home=home)
        bank = load_bank(home=home)
    except ResolverError as exc:
        print(f"[ERROR] canonical 版式目录不可用（{exc.reason_code}）", file=sys.stderr)
        return 2
    if not bank:
        print("[ERROR] canonical 版式库为空（template-library/canonical/layouts/*/layout.json）",
              file=sys.stderr)
        return 2
    inline_style = payload.get("style")
    effective_style = style_name or (
        inline_style if isinstance(inline_style, str) else None
    )
    factor, adjust = load_style_routing(
        effective_style, home=home, resolver=resolver
    )
    results = []
    for page in pages:
        page_types = set(page_types_for_role(str(page.get("page_role", ""))) or [])
        _, page_adjust = load_style_routing(
            effective_style, home=home, resolver=resolver,
            page_types=page_types or None,
        )
        results.append(score_page(page, bank, factor, page_adjust, backend))
    output = {"pages": results, "backend": backend,
              "capability_check": "backend_filtered" if backend else "not_requested"}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
