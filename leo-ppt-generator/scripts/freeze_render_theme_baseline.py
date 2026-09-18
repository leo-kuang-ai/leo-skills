#!/usr/bin/env python3
r"""U1 行业合并交付：冻结七模板 21 页改前渲染基线（template-rebuild v4）。

七模板（cover-basic/body-basic/compare/timeline/spec-table/pull-quote/frame-shot）
× 三档输入（minimal/typical/near-capacity）= 21 页。本地 Playwright 渲染，
不涉及付费生成。产物：

  tests/fixtures/render-theme-baseline/
    manifest.json          输入/输出 hash、命令、版本、源码 dirty hash、字体
    inputs/<t>-<level>.json
    outputs/<t>-<level>.png

用途：解释重构差异（改前基线）。不沿用旧方案 diff ≤0.001 作为新设计等价门。

Usage:
  python3 scripts/freeze_render_theme_baseline.py [--check]

--check 只读校验 manifest 与磁盘一致（漂移非零退出）。
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
VENV_PYTHON = SKILL_DIR / "runtime" / ".venv" / "bin" / "python"
OUT_DIR = SKILL_DIR / "tests" / "fixtures" / "render-theme-baseline"

TEMPLATES = ("cover-basic", "body-basic", "compare", "timeline",
             "spec-table", "pull-quote", "frame-shot")
LEVELS = ("minimal", "typical", "near-capacity")
SIZE = "2560x1440"

# 输入合同来自各模板 applyData 的字段（改前真实消费面）。
INPUTS: dict[str, dict[str, dict]] = {
    "cover-basic": {
        "minimal": {"kicker": "2026 年度汇报", "title": "季度经营回顾",
                    "subtitle": "综合经营分析", "footer_left": "综合部", "footer_right": "2026-09",
                    "page_no": 1},
        "typical": {"kicker": "2026 年第三季度经营分析会",
                    "title": "稳健增长中的结构优化与下季度重点",
                    "subtitle": "收入、利润与现金流的联动解读及四季度行动建议",
                    "footer_left": "集团经营管理部", "footer_right": "2026-10-08 · 内部资料",
                    "page_no": 1},
        "near-capacity": {"kicker": "2026 年第三季度暨滚动经营分析专题材料",
                          "title": "稳健增长态势下结构优化与动能转换的系统性回顾",
                          "subtitle": "覆盖收入、利润、现金流与组织能力四维联动解读及下季度行动建议",
                          "footer_left": "集团经营管理部 · 运营分析中心",
                          "footer_right": "2026-10-08 · 内部资料", "page_no": 1},
    },
    "body-basic": {
        "minimal": {"title": "核心结论", "bullets": ["增长稳健", "结构改善"], "page_no": 2},
        "typical": {"title": "三季度经营核心结论",
                    "bullets": ["收入同比增长 12.4%，超出预算目标 1.8 个百分点",
                                "毛利率提升至 38.2%，主因产品结构升级与采购降本",
                                "经营性现金流净额 4.7 亿元，同比改善明显",
                                "应收账款周转天数下降 6 天，回款纪律加强"],
                    "page_no": 4},
        "near-capacity": {"title": "三季度经营核心结论与支撑证据分解",
                          "bullets": [
                              "收入同比增长 12.4%，超预算目标 1.8 个百分点",
                              "毛利率提升至 38.2%，产品结构与采购降本叠加",
                              "经营性现金流净额 4.7 亿元，收现比 1.06",
                              "应收账款周转天数从 58 天降至 52 天",
                              "三项费用率下降 0.9 个百分点，销售贡献最大",
                              "华东华南贡献主要增量，西部减亏符合预期",
                          ], "page_no": 6},
    },
    "compare": {
        "minimal": {"sides": [
            {"label": "方案 A", "title": "自建", "points": ["周期长"]},
            {"label": "方案 B", "title": "外购", "points": ["周期短"]}], "page_no": 7},
        "typical": {"sides": [
            {"label": "现状", "title": "分散部署",
             "points": ["三套独立环境，资源利用率不足 40%", "版本碎片化，安全补丁滞后两个季度", "跨系统数据同步依赖人工脚本"]},
            {"label": "目标", "title": "统一平台",
             "points": ["资源池化后利用率提升至 75% 以上", "统一版本列车，补丁周期缩短至两周", "标准数据接口，同步自动化率超过 90%"]}],
            "page_no": 7},
        "near-capacity": {"sides": [
            {"label": "方案 A · 自建私有云平台", "title": "自主可控但投入周期长",
             "points": ["初始投入约 2400 万元，建设周期 14 个月，核心团队需 12 人",
                        "数据完全驻留内网，满足等保三级与行业监管要求",
                        "后续扩容灵活，但运维复杂度持续高于托管方案约 35%",
                        "三年总持有成本低于托管方案，但对组织能力要求最高"]},
            {"label": "方案 B · 行业云托管", "title": "交付快但长期依赖外部",
             "points": ["初始投入约 900 万元，上线周期 5 个月，仅需 4 人对接",
                        "数据驻留共享集群，敏感工作负载需单独申请专属资源池",
                        "弹性伸缩能力最强，峰值扩容可在分钟级完成",
                        "三年总持有成本高于自建，且迁移成本随时间累积上升"]}],
            "page_no": 7},
    },
    "timeline": {
        "minimal": {"title": "推进节奏", "steps": [{"name": "立项"}, {"name": "试点"}, {"name": "推广"}], "page_no": 8},
        "typical": {"title": "数字化转型五阶段路线",
                    "steps": [{"no": "01", "name": "现状盘点"}, {"no": "02", "name": "平台选型"},
                              {"no": "03", "name": "试点验证"}, {"no": "04", "name": "分批迁移"},
                              {"no": "05", "name": "全面运营"}], "page_no": 8},
        "near-capacity": {"title": "数字化转型分阶段路线与关键里程碑交付物",
                          "steps": [{"no": "01", "name": "现状盘点与差距评估"}, {"no": "02", "name": "平台选型与商务谈判"},
                                    {"no": "03", "name": "试点验证（华东大区）"}, {"no": "04", "name": "核心系统分批迁移"},
                                    {"no": "05", "name": "历史数据治理归档"}, {"no": "06", "name": "全员培训与变更管理"},
                                    {"no": "07", "name": "全面运营与持续优化"}, {"no": "08", "name": "二期规划（AI 场景）"},
                                    {"no": "09", "name": "复盘与制度化固化"}], "page_no": 8},
    },
    "spec-table": {
        "minimal": {"title": "参数对照", "columns": ["项目", "取值"],
                    "column_align": ["left", "right"],
                    "rows": [["吞吐", "1200/s"], ["延迟", "45ms"]], "page_no": 9},
        "typical": {"title": "主要产品线三季度交付表现",
                    "columns": ["产品线", "交付量（万件）", "同比", "准时交付率"],
                    "column_align": ["left", "right", "right", "right"],
                    "rows": [["智能终端", "412.6", "+9.8%", "97.2%"],
                             ["家用储能", "86.3", "+41.5%", "94.8%"],
                             ["工业模块", "58.9", "+3.2%", "98.6%"],
                             ["软件服务", "24.1", "+18.7%", "99.3%"],
                             ["配件及其他", "15.4", "-2.1%", "96.5%"]],
                    "page_no": 9},
        "near-capacity": {"title": "重点区域市场三季度经营指标与预算执行对照",
                          "columns": ["区域", "收入", "完成率", "同比", "毛利率", "风险"],
                          "column_align": ["left", "right", "right", "right", "right", "center"],
                          "rows": [["华东大区", "128.6", "103.2%", "+14.8%", "39.2%", "低"],
                                   ["华南大区", "96.4", "98.7%", "+11.2%", "37.8%", "低"],
                                   ["华北大区", "74.9", "95.4%", "+7.6%", "36.4%", "中"],
                                   ["西部区域", "38.2", "88.9%", "+4.1%", "31.6%", "中"],
                                   ["海外亚太", "52.3", "101.6%", "+22.4%", "40.8%", "中"],
                                   ["线上渠道", "31.5", "106.8%", "+28.9%", "42.6%", "低"]],
                          "page_no": 9},
    },
    "pull-quote": {
        "minimal": {"quote": "质量是唯一不可妥协的底线。", "source_name": "质量委员会", "page_no": 10},
        "typical": {"quote": "把不确定性变成可管理的风险。",
                    "source_name": "陈明远", "source_meta": "风险管理委员会主席 · 2026 年三季度经营会", "page_no": 10},
        "near-capacity": {"quote": "规模会波动，机制会留下来。",
                          "source_name": "林澜", "source_meta": "集团首席执行官 · 2026 年三季度经营分析会开场发言 · 关于组织决策机制的说明", "page_no": 10},
    },
    "frame-shot": {},  # image_src 由下方 data URI 确定性生成。
}

FRAME_SHOT_FRAME = {
    "minimal": {"kicker": "系统界面", "title": "控制台首页", "caption": "概览视图",
                "ratio": "16x10", "corners": "sq", "shadow": "none", "bg": "paper",
                "inset": "sub", "fit": "contain", "device": "none", "page_no": 11},
    "typical": {"kicker": "运行证据", "title": "生成任务控制台 · 运行列表视图",
                "caption": "2026-09 季度评审留档截图，含 lane 标识与状态列",
                "ratio": "16x10", "corners": "sq", "shadow": "flat", "bg": "paper",
                "inset": "sub", "fit": "contain", "device": "none", "page_no": 11},
    "near-capacity": {"kicker": "运行证据 · 完整工作台", "title": "生成任务控制台 · 运行详情与质量走查双视图",
                      "caption": "2026-09 季度评审留档截图：左侧为任务登记与执行合同状态，右侧为逐页质量走查结论与收据入口",
                      "ratio": "16x10", "corners": "sq", "shadow": "flat", "bg": "paper",
                      "inset": "wide", "fit": "contain", "device": "none", "page_no": 11},
}


def _png_data_uri(width: int, height: int, seed: int) -> str:
    """确定性占位截图（Pillow 画几何块），data: URI 供 frame-shot 离线消费。"""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), (247, 245, 240))
    draw = ImageDraw.Draw(image)
    colors = [(20, 33, 61), (138, 127, 106), (74, 74, 74), (216, 207, 189)]
    for i in range(12):
        x = (i * 97 + seed * 31) % (width - 160)
        y = (i * 53 + seed * 17) % (height - 120)
        w = 120 + (i * 37 + seed) % 180
        h = 24 + (i * 13) % 40
        draw.rectangle([x, y, x + w, y + h], fill=colors[(i + seed) % len(colors)])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    import base64
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_ready_facts() -> dict:
    out = subprocess.run([str(VENV_PYTHON), "-m", "leo_ppt_generator", "render", "ready", "--json"],
                         capture_output=True, text=True, check=True)
    report = json.loads(out.stdout)
    render = report.get("render", {})
    return {"playwright_version": render.get("playwright_version"),
            "chromium_version": render.get("chromium_version"),
            "status": render.get("status")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="冻结七模板 21 页改前渲染基线")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    inputs_dir = OUT_DIR / "inputs"
    outputs_dir = OUT_DIR / "outputs"
    manifest_path = OUT_DIR / "manifest.json"

    if args.check:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        problems = []
        for page in manifest["pages"]:
            inp = SKILL_DIR / page["input_path"]
            out = SKILL_DIR / page["output_path"]
            if not inp.is_file() or _sha(inp) != page["input_sha256"]:
                problems.append(f"input drift: {page['page_id']}")
            if not out.is_file() or _sha(out) != page["output_sha256"]:
                problems.append(f"output drift: {page['page_id']}")
        for rel, sha in manifest["source_hashes"].items():
            path = SKILL_DIR / rel
            if not path.is_file() or _sha(path) != sha:
                problems.append(f"source drift: {rel}")
        if problems:
            print(json.dumps({"problems": problems}, ensure_ascii=False))
            return 1
        print(f"baseline check ok: {len(manifest['pages'])} pages")
        return 0

    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    frame_uris = {level: _png_data_uri(1600, 1000, idx)
                  for idx, level in enumerate(LEVELS)}
    for level, frame in FRAME_SHOT_FRAME.items():
        INPUTS["frame-shot"][level] = {**frame, "image_src": frame_uris[level],
                                       "image_alt": "控制台截图占位"}

    head = subprocess.run(["git", "-C", str(SKILL_DIR), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(SKILL_DIR), "status", "--porcelain"],
                           capture_output=True, text=True, check=True).stdout.splitlines()

    pages = []
    for template in TEMPLATES:
        for level in LEVELS:
            stem = f"{template}-{level}"
            input_path = inputs_dir / f"{stem}.json"
            output_path = outputs_dir / f"{stem}.png"
            input_path.write_text(
                json.dumps(INPUTS[template][level], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            command = [str(VENV_PYTHON), "-m", "leo_ppt_generator", "render", "page",
                       "--template", template, "--data", str(input_path.relative_to(SKILL_DIR)),
                       "--out", str(output_path.relative_to(SKILL_DIR)), "--size", SIZE]
            result = subprocess.run(command, cwd=SKILL_DIR, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"render failed: {stem}\n{result.stdout}\n{result.stderr}", file=sys.stderr)
                return 1
            from PIL import Image
            with Image.open(output_path) as image:
                width, height = image.size
            pages.append({
                "page_id": stem, "template": template, "level": level,
                "input_path": str(input_path.relative_to(SKILL_DIR)),
                "input_sha256": _sha(input_path),
                "output_path": str(output_path.relative_to(SKILL_DIR)),
                "output_sha256": _sha(output_path),
                "output_size": [width, height],
                "command": command,
            })
            print(f"rendered {stem}: {width}x{height}")

    source_files = [
        *(f"template-library/canonical/templates/{name}/page.html" for name in TEMPLATES),
        "runtime/src/leo_ppt_generator/render/page.py",
        "runtime/src/leo_ppt_generator/render/fonts.py",
        "runtime/src/leo_ppt_generator/render/assets.py",
        "runtime/src/leo_ppt_generator/render/chart.py",
        "assets/render-fonts/NotoSansSC-Regular.otf",
        "assets/render-fonts/NotoSansSC-Bold.otf",
    ]
    manifest = {
        "kind": "render-theme-baseline",
        "schema_version": 1,
        "plan": "docs/plans/2026-09-08-001-feat-leo-ppt-template-quality-plan.md",
        "purpose": "改前基线：解释重构差异；不作为新设计等价门（不沿用 diff ≤0.001）",
        "freeze": {"head": head, "dirty_files": sorted(dirty)},
        "render_facts": _render_ready_facts(),
        "size": SIZE,
        "source_hashes": {rel: _sha(SKILL_DIR / rel) for rel in source_files},
        "pages": pages,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    print(f"manifest written: {manifest_path} ({len(pages)} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
