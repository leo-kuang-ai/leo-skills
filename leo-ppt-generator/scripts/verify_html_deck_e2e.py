#!/usr/bin/env python3
"""U7/§3：HTML 完整 deck 端到端（组合→冻结→渲染→PPTX→回读→收据）。

固定输入：005 u19 大宗商品贸易（铜贸业务风险敞口与对冲策略复盘）6 页稿。
链路：compose_design 冻结（两次组合 design_digest 必须一致）→ 逐页 HTML
渲染（resolved page 的 template_id + 版式编译几何 + effective_theme）→
全页 PPTX 组装（python-pptx 全幅图片）→ 回读核验 → 收据落盘。

双路线口径：image 路线未经付费授权不生成图片；本执行器以
project_design_to_prompt 证明 image 路线消费同一冻结设计（投影块
确定性），实际图像生成登记为未执行。

Usage: python3 scripts/verify_html_deck_e2e.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.render.layout import compile_geometry
from leo_ppt_generator.render.page import render_page
from leo_ppt_generator.templates import compose_design, project_design_to_prompt

BLANK_BYTES_MIN = 40_000

# 页级显式版式（html-lane 版式带 renderer_support.render:html）
PAGES = [
    {"page_no": 1, "page_role": "cover", "layout": "builtin:layout:cover-basic",
     "content_ref": "u19-cover"},
    {"page_no": 2, "page_role": "content", "layout": "builtin:layout:body-basic",
     "content_ref": "u19-content-1"},
    {"page_no": 3, "page_role": "data", "layout": "builtin:layout:p25-spec-table",
     "content_ref": "u19-data-1",
     "slots": {"rows": [["敞口对照", "行情 vs 敞口", "结构/执行归因"],
                        ["偏差还原", "事实链", "损失量化口径"],
                        ["制度修订", "权限与阈值", "委员会批准"]],
               "columns": ["议题", "口径", "产出"]}},
    {"page_no": 4, "page_role": "content", "layout": "builtin:layout:body-basic",
     "content_ref": "u19-content-2"},
    {"page_no": 5, "page_role": "data", "layout": "builtin:layout:p25-spec-table",
     "content_ref": "u19-data-2",
     "slots": {"rows": [["触发", "边界条件", "事实链起点"],
                        ["发现", "监控口径", "当日盘后"],
                        ["处置", "权限与阈值", "委员会批准"]],
               "columns": ["环节", "口径", "结论"]}},
    {"page_no": 6, "page_role": "closing", "layout": "builtin:layout:pull-quote",
     "content_ref": "u19-closing"},
]

SLIDE_DATA = {
    "u19-cover": {"kicker": "大宗商品贸易 · 风险复盘", "title": "铜贸业务风险敞口与对冲策略复盘",
                  "subtitle": "结构钱与执行钱 · 偏差事实链 · 制度修订", "footer_left": "风险管理部",
                  "footer_right": "经营班子", "page_no": 1},
    "u19-content-1": {"title": "复盘要完成三件事",
                      "bullets": ["季度行情与公司敞口的对照还原（结构钱 vs 执行钱）",
                                  "两处套保偏差的事实链（触发/发现/处置/影响量化口径）",
                                  "套保制度修订建议与剩余风险"], "page_no": 2},
    "u19-data-1": {"title": "复盘结论与产出",
                   "columns": ["议题", "口径", "产出"],
                   "column_align": ["left", "left", "left"],
                   "rows": [["敞口对照", "行情 vs 敞口", "结构/执行归因"],
                            ["偏差还原", "事实链", "损失量化口径"],
                            ["制度修订", "权限与阈值", "委员会批准"]], "page_no": 3},
    "u19-content-2": {"title": "套保偏差事实链",
                      "bullets": ["触发：边界条件触碰的事实链起点",
                                  "发现：监控口径下的当日盘后识别",
                                  "处置：按权限与阈值上报委员会批准"], "page_no": 4},
    "u19-data-2": {"title": "制度修订要点",
                   "columns": ["环节", "口径", "结论"],
                   "column_align": ["left", "left", "left"],
                   "rows": [["触发", "边界条件", "事实链起点"],
                            ["发现", "监控口径", "当日盘后"],
                            ["处置", "权限与阈值", "委员会批准"]], "page_no": 5},
    "u19-closing": {"quote": "结构钱要赚得明白，执行钱要亏得清楚。",
                    "source_name": "复盘结论", "source_meta": "委员会审批口径", "page_no": 6},
}


def main() -> int:
    resolver = AssetResolver(library=SKILL / "template-library")
    out_root = SKILL / "evals" / "fixtures" / "template-quality" / "html-deck-e2e"
    out_root.mkdir(parents=True, exist_ok=True)

    # 1) 组合冻结 + 确定性
    design = compose_design("finance-navy", pages=PAGES, resolver=resolver)
    design2 = compose_design("finance-navy", pages=PAGES, resolver=resolver)
    digest_stable = design["design_digest"] == design2["design_digest"]
    (out_root / "resolved-design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2) image 路线投影（同一冻结设计；不生成图片——未获付费授权）
    projections = []
    for page, spec in zip(design["pages"], PAGES):
        block = project_design_to_prompt(design, spec)
        block2 = project_design_to_prompt(design, spec)
        projections.append({"page_no": spec["page_no"],
                            "deterministic": json.dumps(block, sort_keys=True)
                            == json.dumps(block2, sort_keys=True),
                            "block": block})
    (out_root / "image-lane-projections.json").write_text(
        json.dumps(projections, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) HTML 逐页渲染（六闸）
    pages_out = []
    for page in design["pages"]:
        ref = next(p["content_ref"] for p in PAGES if p["page_no"] == page["page_no"])
        fixture = SLIDE_DATA[ref]
        profile = resolver.resolve(page["layout_id"])["data"]
        column_count = len(fixture["columns"]) if "columns" in fixture else None
        geometry = compile_geometry(profile, design["effective_theme"],
                                    column_count=column_count)
        weights = geometry.pop("column_weights", None)
        theme_vars = {"colors": design["effective_theme"]["colors"],
                      "fonts": design["effective_theme"]["fonts"],
                      "geometry": geometry}
        if weights is not None:
            theme_vars["column_weights"] = weights
        data_path = out_root / f"p{page['page_no']}.json"
        data_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        png = out_root / f"p{page['page_no']}.png"
        result = render_page(page["template_id"].rsplit(":", 1)[-1],
                             data_path, png, theme_variables=theme_vars)
        from PIL import Image

        bg = design["effective_theme"]["colors"]["background"]
        expected_bg = (int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16))
        corner = Image.open(png).convert("RGB").getpixel((30, 30))
        checks = {
            "dimensions": (result["width"], result["height"]) == (2560, 1440),
            "blank": png.stat().st_size >= BLANK_BYTES_MIN,
            "theme_applied": all(abs(g - w) <= 16 for g, w in zip(corner, expected_bg)),
            "ready_signal": result.get("ready_signal") == "data-leo-ready",
            "title_nonempty": bool(fixture.get("title") or fixture.get("quote")),
        }
        pages_out.append({"page_no": page["page_no"], "role": page["page_role"],
                          "template": page["template_id"], "png": str(png),
                          "sha256": result["out_sha256"], "checks": checks,
                          "hard_pass": all(checks.values())})

    # 4) PPTX 组装 + 回读
    from pptx import Presentation
    from pptx.util import Emu

    pptx_path = out_root / "u19-copper-risk-review.pptx"
    presentation = Presentation()
    presentation.slide_width = Emu(12192000)   # 16:9
    presentation.slide_height = Emu(6858000)
    blank = presentation.slide_layouts[6]
    for page in pages_out:
        slide = presentation.slides.add_slide(blank)
        slide.shapes.add_picture(page["png"], 0, 0,
                                 width=presentation.slide_width,
                                 height=presentation.slide_height)
    presentation.save(pptx_path)

    readback = Presentation(pptx_path)
    slides = list(readback.slides)
    readback_ok = (len(slides) == len(pages_out)
                   and all(len([s for s in slide.shapes if s.shape_type == 13]) == 1
                           for slide in slides))

    receipt = {
        "kind": "html-deck-e2e-receipt", "schema_version": 1,
        "input": "005 u19 铜贸复盘（6 页：cover/content×2/data×2/closing）",
        "style": design["selection"]["style"]["asset_id"],
        "theme": design["selection"]["theme"]["asset_id"],
        "mode": design["selection"]["mode"],
        "design_digest": design["design_digest"],
        "design_digest_stable_across_compositions": digest_stable,
        "image_lane": {"projection_deterministic": all(p["deterministic"]
                                                       for p in projections),
                       "generation_executed": False,
                       "note": "图像生成未获付费授权，仅登记冻结设计投影；实际 image deck 端到端未执行"},
        "html_lane": {"pages": pages_out,
                      "hard_pass": all(p["hard_pass"] for p in pages_out)},
        "pptx": {"path": str(pptx_path),
                 "sha256": hashlib.sha256(pptx_path.read_bytes()).hexdigest(),
                 "slides": len(slides), "readback_ok": readback_ok},
        "capacity_reports": design["capacity_reports"],
    }
    (out_root / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = (digest_stable and all(p["deterministic"] for p in projections)
          and all(p["hard_pass"] for p in pages_out) and readback_ok)
    print(json.dumps({"design_digest": design["design_digest"],
                      "digest_stable": digest_stable,
                      "pages_hard_pass": f"{sum(p['hard_pass'] for p in pages_out)}/{len(pages_out)}",
                      "projection_deterministic": all(p["deterministic"] for p in projections),
                      "pptx_readback_ok": readback_ok, "overall_pass": ok},
                     ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
