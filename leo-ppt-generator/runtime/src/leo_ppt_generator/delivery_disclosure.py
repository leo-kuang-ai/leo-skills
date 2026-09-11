"""U14 交付披露面（R-78 拼图 / R-79 alt 清单 / R-82 讲稿时长）。

与收据的边界（负责人裁决，实施计划 U14 落点）：披露工件**加性、不进收据
五类指纹**——拼图在 `<run>/diffs/`、alt 清单在 `<run>/disclosure/`
（reports/** 属 qa_reports 指纹类，披露工件不得落入），`delivery receipt`
仅附加非指纹的 `disclosure` 摘要块；旧收据验证不受影响。

- R-78：变更页的新旧拼图写 `<run>/diffs/`，页集合与 `compute_impact` 波及
  面集合严格相等（缺图/多图即拒）；每张拼图带图注（页面身份 + 新旧标识 +
  regime 版本戳）；不做像素级自动判同。
- R-79：alt 文本清单按页登记（文本来自调用方传入的内容包事实，本模块不
  编造）；缺失页如实标 `missing` 披露，不静默。
- R-82：讲稿"预算时长 vs 讲稿字数"对照——预算先页级 `budget_seconds`，
  缺失用显式整册 `duration_seconds` 均分，双缺失 `unknown`；语速模型为
  常量字/分（可配），结论 advisory 不阻断。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .storage import atomic_write_json, sha256_file

DIFFS_DIRNAME = "diffs"
ALT_MANIFEST_RELATIVE = "disclosure/alt-manifest.json"
SPEAKING_CHARS_PER_MINUTE = 240.0  # CJK 口播常速经验值；advisory，可配
DISCLOSURE_SCHEMA_VERSION = 1


class DisclosureError(ValueError):
    """披露工件合同失败；``reason_code`` 稳定命名。"""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


# --------------------------------------------------------------------------- #
# R-78 视觉回归拼图
# --------------------------------------------------------------------------- #

def build_diff_puzzles(
    *,
    run_root: str | Path,
    pairs: list[dict[str, Any]],
    affected_pages: list[str],
    regime_version: str | None = None,
) -> dict[str, Any]:
    """波及页集合的新旧拼图 → ``<run>/diffs/``（页集合严格相等）。

    ``pairs`` 元素：``{"page_id", "number", "old", "new"}``（产物路径）。
    缺图（任一侧文件缺失）或多图（pairs 页 ∉ 波及面）一律拒绝——拼图页
    集合 ⊃ 波及面集合即 FAIL（R-78 验收 3）。
    """

    from PIL import Image, ImageDraw

    root = Path(run_root)
    pair_ids = [str(pair.get("page_id")) for pair in pairs]
    if sorted(pair_ids) != sorted(set(affected_pages)):
        raise DisclosureError(
            "diff_puzzle_page_set_mismatch",
            f"拼图页集合 {sorted(pair_ids)} != 波及面集合 {sorted(set(affected_pages))}")
    diffs_dir = root / DIFFS_DIRNAME
    diffs_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for pair in pairs:
        page_id = str(pair["page_id"])
        old_path, new_path = Path(pair["old"]), Path(pair["new"])
        for label, path in (("旧", old_path), ("新", new_path)):
            if not path.is_file():
                raise DisclosureError(
                    "diff_puzzle_image_missing", f"页 {page_id} {label}产物缺失：{path}")
        with Image.open(old_path) as old, Image.open(new_path) as new:
            old_rgb, new_rgb = old.convert("RGB"), new.convert("RGB")
            height = max(old_rgb.height, new_rgb.height)
            width = max(old_rgb.width, new_rgb.width)
            sheet = Image.new("RGB", (width * 2 + 24, height + 72), (24, 24, 28))
            sheet.paste(old_rgb, (8, 64))
            sheet.paste(new_rgb, (width + 16, 64))
            draw = ImageDraw.Draw(sheet)
            caption = (
                f"{page_id} 视觉回归对照  左=旧  右=新"
                + (f"  regime={regime_version}" if regime_version else ""))
            draw.rectangle((0, 0, sheet.width, 56), fill=(24, 24, 28))
            draw.text((12, 18), caption, fill=(240, 240, 236))
        puzzle_path = diffs_dir / f"{page_id}.png"
        sheet.save(puzzle_path, format="PNG")
        entries.append({
            "page_id": page_id,
            "number": pair.get("number"),
            "puzzle": str(puzzle_path),
            "puzzle_sha256": sha256_file(puzzle_path),
            "old": str(old_path), "old_sha256": sha256_file(old_path),
            "new": str(new_path), "new_sha256": sha256_file(new_path),
            "caption": caption,
        })
    entries.sort(key=lambda item: str(item["page_id"]))
    index = {
        "schema_version": DISCLOSURE_SCHEMA_VERSION,
        "kind": "diff-puzzles",
        "regime_version": regime_version,
        "affected_pages": sorted(set(affected_pages)),
        "pages": entries,
        "note": "披露工件：不进交付收据五类指纹；不做像素级自动判同",
    }
    atomic_write_json(diffs_dir / "index.json", index)
    return index


# --------------------------------------------------------------------------- #
# R-79 无障碍 alt 清单
# --------------------------------------------------------------------------- #

def build_alt_manifest(*, run_root: str | Path, pages: list[dict[str, Any]]) -> dict[str, Any]:
    """逐页 alt 文本清单 → ``<run>/disclosure/alt-manifest.json``。

    ``pages`` 元素：``{"page_id", "number", "artifact", "title", "claim",
    "alt"}``；alt 文本来自内容包事实（claim/title），调用方未提供即
    ``status=missing`` 如实披露——本模块不编造替代文本。
    """

    entries: list[dict[str, Any]] = []
    missing = 0
    for page in pages:
        alt = page.get("alt")
        has_alt = bool(alt and str(alt).strip())
        if not has_alt:
            missing += 1
        artifact = page.get("artifact")
        entries.append({
            "page_id": str(page["page_id"]),
            "number": page.get("number"),
            "title": page.get("title"),
            "alt": str(alt).strip() if has_alt else None,
            "status": "ok" if has_alt else "missing",
            "artifact": artifact,
            "artifact_sha256": sha256_file(artifact) if artifact and Path(artifact).is_file() else None,
        })
    manifest = {
        "schema_version": DISCLOSURE_SCHEMA_VERSION,
        "kind": "alt-manifest",
        "pages": entries,
        "pages_total": len(entries),
        "pages_missing_alt": missing,
        "note": "加性披露：缺失按 missing 披露不静默；不进收据五类指纹；"
                "不承诺全量无障碍合规（R-79 缩围）",
    }
    atomic_write_json(Path(run_root) / ALT_MANIFEST_RELATIVE, manifest)
    return manifest


# --------------------------------------------------------------------------- #
# R-82 讲稿时长校准（advisory）
# --------------------------------------------------------------------------- #

def speaker_duration_report(
    *,
    pages: list[dict[str, Any]],
    deck_duration_seconds: float | None = None,
    chars_per_minute: float = SPEAKING_CHARS_PER_MINUTE,
) -> dict[str, Any]:
    """逐页"预算时长 vs 讲稿字数"对照（KTD9：页级 → 整册均分 → unknown）。

    ``pages`` 元素：``{"page_id", "chars"}``，可选自带 ``budget_seconds``。
    输出 advisory：超时页标注不阻断（超时是否阻断定稿由既有叙事三查规则
    ——实测讲稿超硬上限才阻断——另行判断）。
    """

    if chars_per_minute <= 0:
        raise DisclosureError("duration_rate_invalid", "chars_per_minute 必须为正")
    budgeted = [page for page in pages if page.get("budget_seconds") is not None]
    share = None
    if len(budgeted) < len(pages) and deck_duration_seconds is not None and pages:
        share = float(deck_duration_seconds) / len(pages)
    rows: list[dict[str, Any]] = []
    over_pages = 0
    unknown_pages = 0
    for page in pages:
        budget = page.get("budget_seconds")
        if budget is not None:
            source = "page-budget"
        elif share is not None:
            budget, source = share, "deck-share"
        else:
            budget, source = None, "unknown"
        chars = int(page.get("chars") or 0)
        actual = round(chars / chars_per_minute * 60.0, 1)
        status = "unknown" if budget is None else ("over" if actual > float(budget) else "ok")
        over_pages += status == "over"
        unknown_pages += status == "unknown"
        rows.append({
            "page_id": str(page["page_id"]),
            "chars": chars,
            "budget_seconds": budget,
            "budget_source": source,
            "estimated_seconds": actual,
            "status": status,
        })
    return {
        "schema_version": DISCLOSURE_SCHEMA_VERSION,
        "kind": "speaker-duration",
        "chars_per_minute": chars_per_minute,
        "pages": rows,
        "pages_total": len(rows),
        "pages_over": over_pages,
        "pages_unknown_budget": unknown_pages,
        "advisory": True,
        "note": "时长为语速模型估算（advisory），不阻断导出；预算来源=页级优先，"
                "缺失用显式整册均分，双缺失 unknown",
    }


def disclosure_summary(run_root: str | Path) -> dict[str, Any]:
    """收据附加摘要块（非指纹）：披露工件的存在性与计数。"""

    root = Path(run_root)
    diffs_index = root / DIFFS_DIRNAME / "index.json"
    alt_manifest = root / ALT_MANIFEST_RELATIVE
    diffs: dict[str, Any] | None = None
    if diffs_index.is_file():
        try:
            diffs = json.loads(diffs_index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            diffs = None
    alt: dict[str, Any] | None = None
    if alt_manifest.is_file():
        try:
            alt = json.loads(alt_manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            alt = None
    return {
        "schema_version": DISCLOSURE_SCHEMA_VERSION,
        "kind": "delivery-disclosure-summary",
        "diff_puzzles": (
            {"pages": len(diffs.get("pages", [])), "regime_version": diffs.get("regime_version")}
            if diffs else None),
        "alt_manifest": (
            {"pages_total": alt.get("pages_total"), "pages_missing_alt": alt.get("pages_missing_alt")}
            if alt else None),
        "note": "加性摘要，不属于收据五类指纹；缺失即 null（not_run 披露口径）",
    }
