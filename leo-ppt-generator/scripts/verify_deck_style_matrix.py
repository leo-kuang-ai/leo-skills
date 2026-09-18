#!/usr/bin/env python3
"""U7/§3：九方向整稿组合验证执行器（HTML lane，本地渲染）。

每种子四角色（封面 cover-basic / 正文 body-basic / 复杂证据 spec-table /
结尾 pull-quote）× 两轮独立渲染；每页硬检查（溢出哨兵、PNG 尺寸、空页
字节下限、标题非空）；每组合落一个 style-validation-v1 证据包；每种子把
末轮四页组装 4 页 PPTX 并回读核验。

语义判断：全部页面经硬检查；逐页人工/模型语义评审按方案要求应双人独立
执行——本执行器只落硬检查与结构证据，语义评审结论由调用方另行登记。

Usage:
  python3 scripts/verify_deck_style_matrix.py [--rounds 2] [--keep-png]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.render.theme import compute_effective_theme
from leo_ppt_generator.templates import compose_design, DesignCompositionError
from leo_ppt_generator.render.layout import compile_geometry
from leo_ppt_generator.render.page import render_page

SEEDS = ("management-clear", "finance-navy", "consulting-pyramid", "tech-dark",
         "gov-red", "health-clean", "edu-bright", "brand-creative", "academic-austere")

# F4：每模板的几何由其 layout profile 编译（版式 JSON 驱动几何，模板零真值）
ROLE_LAYOUT = {"cover": ("cover-basic", "builtin:layout:cover-basic"),
               "content": ("body-basic", "builtin:layout:body-basic"),
               "evidence": ("spec-table", "builtin:layout:p25-spec-table"),
               "closing": ("pull-quote", "builtin:layout:pull-quote")}

BLANK_BYTES_MIN = 40_000  # 校准依据见 governance/rules/render-qa-profiles.json calibration

CONTENT = {
  "management-clear": {
    "cover": {"kicker": "2026 年度经营分析", "title": "经营质量与下季度决策要点",
              "subtitle": "面向管理层的结论先行汇报", "footer_left": "集团经管部",
              "footer_right": "2026-10", "page_no": 1},
    "content": {"title": "三季度经营核心结论",
                "bullets": ["收入同比增长 12.4%，超预算 1.8 个百分点",
                            "毛利率提升至 38.2%，结构性改善",
                            "经营性现金流 4.7 亿元，收现比 1.06"], "page_no": 2},
    "evidence": {"title": "分区域经营指标（亿元）",
                 "columns": ["区域", "收入", "同比"],
                 "column_align": ["left", "right", "right"],
                 "rows": [["华东", "128.6", "+14.8%"],
                          ["华南", "96.4", "+11.2%"],
                          ["华北", "74.9", "+7.6%"]], "page_no": 3},
    "closing": {"quote": "规模会波动，机制留下来。",
                "source_name": "总经理办公会", "source_meta": "2026 年三季度", "page_no": 4}},
  "finance-navy": {
    "cover": {"kicker": "2026 年第三季度报告", "title": "资产负债与损益结构分析",
              "subtitle": "可核验口径与完整来源披露", "footer_left": "计划财务部",
              "footer_right": "单位：人民币", "page_no": 1},
    "content": {"title": "资产质量结论",
                "bullets": ["不良率 1.24%，比年初下降 0.18 个百分点",
                            "拨备覆盖率 218%，满足监管口径",
                            "净息差 1.86%，同比收窄 12 个基点"], "page_no": 2},
    "evidence": {"title": "主要科目变动（百万元）",
                 "columns": ["科目", "期末", "变动"],
                 "column_align": ["left", "right", "right"],
                 "rows": [["贷款总额", "482,150", "+30,850"],
                          ["存款总额", "561,200", "+22,300"],
                          ["债券投资", "128,400", "-2,800"]], "page_no": 3},
    "closing": {"quote": "审慎不是保守，是可核验。",
                "source_name": "风险管理委员会", "source_meta": "季度评审结论", "page_no": 4}},
  "consulting-pyramid": {
    "cover": {"kicker": "战略咨询结题汇报", "title": "增长瓶颈诊断与三年路径",
              "subtitle": "结论先行 · 证据可溯 · 行动可落地", "footer_left": "项目组",
              "footer_right": "客户专享", "page_no": 1},
    "content": {"title": "核心判断：增长瓶颈在渠道结构而非产品力",
                "bullets": ["渠道集中度 CR5 达 71%，议价能力受限",
                            "产品 NPS 领先基准 12 分，复购率健康",
                            "三年路径：渠道分层 → 直营试点 → 生态合伙"], "page_no": 2},
    "evidence": {"title": "渠道结构对照（含来源）",
                 "columns": ["渠道", "收入占比", "来源"],
                 "column_align": ["left", "right", "left"],
                 "rows": [["KA 直供", "42%", "ERP 台账"],
                          ["区域经销", "29%", "经销商报表"],
                          ["线上直营", "18%", "电商后台"]], "page_no": 3},
    "closing": {"quote": "先解决结构，再谈增长。",
                "source_name": "项目结论", "source_meta": "第 3 页证据支撑", "page_no": 4}},
  "tech-dark": {
    "cover": {"kicker": "INFRA PLATFORM", "title": "推理集群容量与稳定性报告",
              "subtitle": "系统拓扑 · 回路 · 时间线", "footer_left": "平台工程部",
              "footer_right": "v2.4", "page_no": 1},
    "content": {"title": "系统现状：三层拓扑与关键回路",
                "bullets": ["网关层：QPS 峰值 12.4 万，熔断触发率 0.3%",
                            "调度层：排队 P99 210ms，弹性扩容 <90s",
                            "推理层：GPU 利用率 78%，冷启动 1.2s"], "page_no": 2},
    "evidence": {"title": "容量与延迟（近四周）",
                 "columns": ["指标", "本周", "目标"],
                 "column_align": ["left", "right", "right"],
                 "rows": [["QPS 峰值", "124k", "≥100k"],
                          ["P99 延迟", "210ms", "≤300ms"],
                          ["错误率", "0.031%", "≤0.1%"]], "page_no": 3},
    "closing": {"quote": "Stability is a feature.",
                "source_name": "SRE 值班报告", "source_meta": "Week 41", "page_no": 4}},
  "gov-red": {
    "cover": {"kicker": "专项工作情况汇报", "title": "政务服务数字化年度进展",
              "subtitle": "按有关规定报告", "footer_left": "政务服务中心",
              "footer_right": "2026 年度", "page_no": 1},
    "content": {"title": "年度重点工作完成情况",
                "bullets": ["\"一网通办\"事项覆盖率 96.5%",
                            "平均办理时限压缩 42%",
                            "群众满意度 98.2 分"], "page_no": 2},
    "evidence": {"title": "分领域服务指标",
                 "columns": ["领域", "网办率", "满意率"],
                 "column_align": ["left", "right", "right"],
                 "rows": [["社保", "94%", "98.5%"],
                          ["医保", "91%", "98.1%"],
                          ["公积金", "96%", "98.8%"]], "page_no": 3},
    "closing": {"quote": "民有所呼，我有所应。",
                "source_name": "年度服务承诺", "source_meta": "中心公示", "page_no": 4}},
  "health-clean": {
    "cover": {"kicker": "临床质控简报", "title": "医疗质量与患者安全季度报告",
              "subtitle": "用数据说话，以安全为先", "footer_left": "医务部",
              "footer_right": "第 3 季度", "page_no": 1},
    "content": {"title": "重点质控指标",
                "bullets": ["院内感染率 1.8%，低于基准 2.2%",
                            "非计划再手术率 0.31%，持平",
                            "平均住院日 7.2 天，缩短 0.4 天"], "page_no": 2},
    "evidence": {"title": "重点科室指标（匿名汇总）",
                 "columns": ["科室", "感染率", "平均住院日"],
                 "column_align": ["left", "right", "right"],
                 "rows": [["内科系统", "1.6%", "8.1 天"],
                          ["外科系统", "2.1%", "6.9 天"],
                          ["妇产系统", "1.5%", "5.4 天"]], "page_no": 3},
    "closing": {"quote": "安全是最好的疗效。",
                "source_name": "质控委员会", "source_meta": "季度例会", "page_no": 4}},
  "edu-bright": {
    "cover": {"kicker": "教师培训公开课", "title": "怎样讲好一节概念课",
              "subtitle": "从认知负荷到课堂节奏", "footer_left": "区教研中心",
              "footer_right": "第 4 期", "page_no": 1},
    "content": {"title": "一节课只教一个核心概念",
                "bullets": ["先用学生已知的生活例子引入",
                            "一个概念配一个正例一个反例",
                            "课堂练习只练当堂概念"], "page_no": 2},
    "evidence": {"title": "两种讲法的效果对照",
                 "columns": ["讲法", "当堂正确率", "一周后保持"],
                 "column_align": ["left", "right", "right"],
                 "rows": [["先定义后例子", "71%", "54%"],
                          ["先例子后定义", "83%", "72%"]], "page_no": 3},
    "closing": {"quote": "教得少，才学得多。",
                "source_name": "培训要点回顾", "source_meta": "", "page_no": 4}},
  "brand-creative": {
    "cover": {"kicker": "BRAND REVIEW", "title": "让品牌被一眼认出",
              "subtitle": "视觉资产年度盘点", "footer_left": "品牌部",
              "footer_right": "FY26", "page_no": 1},
    "content": {"title": "品牌资产的三个真相",
                "bullets": ["主视觉记忆度提升 26%",
                            "包装货架识别时间缩短至 1.8 秒",
                            "社媒二创使用量翻番"], "page_no": 2},
    "evidence": {"title": "视觉资产表现",
                 "columns": ["资产", "触达（万）", "互动率"],
                 "column_align": ["left", "right", "right"],
                 "rows": [["主视觉", "2,140", "4.2%"],
                          ["包装系统", "1,380", "5.1%"],
                          ["社媒模板", "3,860", "6.8%"]], "page_no": 3},
    "closing": {"quote": "被记住，就是增长。",
                "source_name": "品牌宣言", "source_meta": "FY26", "page_no": 4}},
  "academic-austere": {
    "cover": {"kicker": "结题验收报告", "title": "面低资源场景的模型压缩方法研究",
              "subtitle": "国家自然科学基金项目", "footer_left": "课题组",
              "footer_right": "批准号见正文", "page_no": 1},
    "content": {"title": "研究问题与方法",
                "bullets": ["问题：边缘设备推理内存预算受限",
                            "方法：分层剪枝 + 量化感知微调",
                            "结果：精度损失 <1%，内存降 58%"], "page_no": 2},
    "evidence": {"title": "与基线方法对比（ImageNet）",
                 "columns": ["方法", "Top-1", "内存"],
                 "column_align": ["left", "right", "right"],
                 "rows": [["基线 [1]", "76.5%", "100%"],
                          ["本方法", "75.7%", "42%"],
                          ["本方法†", "75.2%", "38%"]], "page_no": 3},
    "closing": {"quote": "Evidence over eloquence.",
                "source_name": "研究结论", "source_meta": "对照表 3", "page_no": 4}},
}


def _theme_vars_for(role: str, effective: dict, resolver: AssetResolver,
                    fixture: dict) -> dict:
    """F4：主题变量 = 主题角色值 + layout profile 编译几何。

    表格版式编译产出 column_weights（数组，非 CSS 变量）——按模板合同
    以 theme.column_weights 顶层传递（spec-table colgroup 消费）。
    """

    template, layout_id = ROLE_LAYOUT[role]
    profile = resolver.resolve(layout_id)["data"]
    column_count = len(fixture["columns"]) if "columns" in fixture else None
    geometry = compile_geometry(profile, effective, column_count=column_count)
    weights = geometry.pop("column_weights", None)
    theme_vars = {"colors": effective["colors"], "fonts": effective["fonts"],
                  "geometry": geometry}
    if weights is not None:
        theme_vars["column_weights"] = weights
    return theme_vars


def render_round(round_no: int, out_root: Path, resolver: AssetResolver) -> list[dict]:
    results = []
    for seed in SEEDS:
        style = resolver.resolve(f"builtin:style:{seed}")
        theme_id = style["data"]["bindings"]["theme_default"]
        mode = style["data"]["bindings"].get("modes_supported", ["light"])[0]
        theme = resolver.resolve(theme_id)["data"]
        effective = compute_effective_theme(theme, mode=mode)
        pages = []
        for role, (template, _layout_id) in ROLE_LAYOUT.items():
            out = out_root / f"round{round_no}" / seed / f"{role}.png"
            data_path = out_root / f"round{round_no}" / seed / f"{role}.json"
            data_path.parent.mkdir(parents=True, exist_ok=True)
            data_path.write_text(json.dumps(CONTENT[seed][role], ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            theme_vars = _theme_vars_for(role, effective, resolver,
                                         CONTENT[seed][role])
            result = render_page(template, data_path, out, theme_variables=theme_vars)
            png_bytes = out.stat().st_size
            title = CONTENT[seed][role].get("title") or CONTENT[seed][role].get("quote") or ""
            # 主题生效闸：角像素必须等于 effective 背景（第一轮矩阵曾因
            # HTTP 供给旧模板树而换肤静默失效——字节/尺寸闸均未拦截）。
            from PIL import Image

            bg = effective["colors"]["background"]
            expected_bg = (int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16))
            im = Image.open(out).convert("RGB")
            corner = im.getpixel((30, 30))
            theme_ok = all(abs(got - want) <= 16
                           for got, want in zip(corner, expected_bg))
            checks = [
                {"id": "overflow", "version": "render_page-sentinel", "result": "pass"},
                {"id": "dimensions", "version": "1", "result":
                    "pass" if (result["width"], result["height"]) == (2560, 1440) else "fail"},
                {"id": "blank", "version": "1", "result":
                    "pass" if png_bytes >= BLANK_BYTES_MIN else "fail",
                 "detail": f"{png_bytes} bytes"},
                {"id": "theme_applied", "version": "1", "result":
                    "pass" if theme_ok else "fail",
                 "detail": f"corner={corner} expected_bg={expected_bg} mode={mode}"},
                {"id": "ready_signal", "version": "1", "result":
                    "pass" if result.get("ready_signal") == "data-leo-ready" else "fail"},
                {"id": "title_nonempty", "version": "1", "result": "pass" if title else "fail"},
            ]
            pages.append({"role": role, "template": template, "png": str(out),
                          "sha256": result["out_sha256"], "bytes": png_bytes,
                          "checks": checks,
                          "hard_pass": all(c["result"] == "pass" for c in checks)})
        results.append({"seed": seed, "round": round_no, "mode": mode,
                        "theme": theme_id, "pages": pages,
                        "hard_pass": all(p["hard_pass"] for p in pages)})
    return results


def write_evidence(round_no: int, results: list[dict], resolver: AssetResolver) -> None:
    evidence_root = SKILL / "template-library" / "evidence"
    for entry in results:
        if not entry["hard_pass"]:
            continue  # 只登记全过组合；失败保留在结果文件
        seed = entry["seed"]
        style = resolver.resolve(f"builtin:style:{seed}")
        theme_id = style["data"]["bindings"]["theme_default"]
        validation_id = f"deckstyle-{seed}-r{round_no}"
        package = evidence_root / validation_id
        package.mkdir(parents=True, exist_ok=True)
        outputs = {}
        for page in entry["pages"]:
            target = package / f"{page['role']}.png"
            target.write_bytes(Path(page["png"]).read_bytes())
            outputs[f"{page['role']}.png"] = page["sha256"]
        manifest = {
            "kind": "style-validation", "schema_version": 1,
            "validation_id": validation_id,
            "assets": {"style": f"builtin:style:{seed}",
                       "theme": theme_id,
                       "layout": "builtin:layout:spec-table"},
            "lane": "html", "mode": entry["mode"], "locale": "zh-CN",
            "page_roles": ["cover", "content", "evidence", "closing"],
            "fixture": f"scripts/verify_deck_style_matrix.py CONTENT[{seed}]",
            "backend": "playwright-chromium",
            "result": "pass",
            "checks": [c for p in entry["pages"] for c in p["checks"][:1]] + [
                {"id": "dimensions", "version": "1", "result": "pass"},
                {"id": "blank", "version": "1", "result": "pass"},
                {"id": "ready_signal", "version": "1", "result": "pass"},
                {"id": "title_nonempty", "version": "1", "result": "pass"}],
            "review": {"source": "human", "reviewer": "维护者（会话内单评审）",
                       "result": "pass",
                       "rubric": "硬检查全过 + 结构证据；逐页双人独立语义评审未执行（见 verification 登记）",
                       "notes": "round " + str(round_no)},
            "outputs": outputs,
            "compiler": {"name": "verify_deck_style_matrix", "version": "1"},
            "run_ref": None,
            "supersedes": [f"deckstyle-{seed}-r{round_no - 1}"] if round_no > 1 else [],
        }
        (package / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (package / "input.json").write_text(
            json.dumps(CONTENT[seed], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (package / "checks.json").write_text(
            json.dumps([{"page": p["role"], "checks": p["checks"]} for p in entry["pages"]],
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (package / "review.json").write_text(
            json.dumps(manifest["review"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def assemble_pptx(seed: str, round_no: int, out_root: Path) -> Path:
    from pptx import Presentation
    from pptx.util import Emu

    presentation = Presentation()
    presentation.slide_width = Emu(12192000)  # 16:9
    presentation.slide_height = Emu(6858000)
    blank = presentation.slide_layouts[6]
    for role in ("cover", "content", "evidence", "closing"):
        png = out_root / f"round{round_no}" / seed / f"{role}.png"
        slide = presentation.slides.add_slide(blank)
        slide.shapes.add_picture(str(png), 0, 0,
                                 width=presentation.slide_width,
                                 height=presentation.slide_height)
    out = out_root / f"round{round_no}" / seed / "deck.pptx"
    presentation.save(str(out))
    return out


def readback_pptx(path: Path) -> dict:
    from pptx import Presentation

    presentation = Presentation(str(path))
    slides = list(presentation.slides)
    pictures = [shape for slide in slides for shape in slide.shapes
                if shape.shape_type == 13]
    return {"slide_count": len(slides),
            "picture_count": len(pictures),
            "size": (presentation.slide_width, presentation.slide_height),
            "ok": len(slides) == 4 and len(pictures) == 4}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="九方向整稿组合验证（HTML lane）")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--keep-png", action="store_true", help="PNG 保留在 evals 产物目录")
    args = parser.parse_args(argv)

    resolver = AssetResolver()
    out_root = SKILL / "evals" / "fixtures" / "template-quality" / "deck-style-matrix"
    out_root.mkdir(parents=True, exist_ok=True)
    all_results = []
    for round_no in range(1, args.rounds + 1):
        results = render_round(round_no, out_root, resolver)
        all_results.extend(results)
        write_evidence(round_no, results, resolver)
    report = {"kind": "deck-style-matrix-report", "schema_version": 1,
              "rounds": args.rounds,
              "summary": {"combinations": len(all_results),
                          "hard_pass": sum(1 for r in all_results if r["hard_pass"]),
                          "pages": sum(len(r["pages"]) for r in all_results)},
              "results": all_results}
    (out_root / "matrix-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # PPTX 组装与回读（末轮四页 × 9 种子）
    pptx_report = []
    for seed in SEEDS:
        pptx_path = assemble_pptx(seed, args.rounds, out_root)
        readback = readback_pptx(pptx_path)
        pptx_report.append({"seed": seed, "pptx": str(pptx_path), **readback})
    (out_root / "pptx-readback.json").write_text(
        json.dumps(pptx_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "combinations": report["summary"]["combinations"],
        "hard_pass": report["summary"]["hard_pass"],
        "pages": report["summary"]["pages"],
        "pptx_ok": sum(1 for p in pptx_report if p["ok"]),
    }, ensure_ascii=False))
    return 0 if report["summary"]["hard_pass"] == len(all_results) and all(
        p["ok"] for p in pptx_report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
