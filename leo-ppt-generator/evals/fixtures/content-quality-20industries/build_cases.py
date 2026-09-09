#!/usr/bin/env python3
"""从 fixture 权威源确定性生成 20 个内容质量评测 case YAML。

用法（在 leo-ppt-generator/ 目录内执行）：
    python3 evals/fixtures/content-quality-20industries/build_cases.py [--check]

--check：只校验已生成 case 与当前 fixture 内容一致（无漂移），不重写。

设计契约（方案 005 §3.2/§3.5）：
- 生成侧只能获得允许输入：tasks/*.md +（直出单元）materials/*.md。
- 评审侧答案（judge-side/）绝不进入 case prompt。
- 每个 case 的 prompt = 公共委托与边界导语 + 任务简报 + 随附材料。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent
CASES_DIR = FIXTURE_DIR.parents[1] / "cases"

# (case 序号, slug, 标题行业, 材料文件名或 None)
UNITS = [
    (1, "internet-tech", "互联网科技", "u01-internet-tech.md"),
    (2, "gov-public", "政务公共", "u02-gov-public.md"),
    (3, "medical-health", "医疗健康", "u03-medical-health.md"),
    (4, "finance-audit", "金融审计", "u04-finance-audit.md"),
    (5, "education-academic", "教育学术", None),
    (6, "consulting-law", "咨询法律", "u06-consulting-law.md"),
    (7, "manufacturing-energy", "制造能源", None),
    (8, "automotive-mobility", "汽车交通", "u08-automotive-mobility.md"),
    (9, "consumer-fashion", "消费时尚", None),
    (10, "tourism-fnb", "文旅餐饮", "u10-tourism-fnb.md"),
    (11, "gaming-entertainment", "游戏娱乐", None),
    (12, "sports-fitness", "体育健身", None),
    (13, "agriculture", "农业", None),
    (14, "media-publishing", "传媒出版", None),
    (15, "aerospace", "航空航天", "u15-aerospace.md"),
    (16, "construction-eng", "建筑工程", "u16-construction-eng.md"),
    (17, "logistics", "物流供应链", "u17-logistics.md"),
    (18, "nonprofit", "公益社会组织", None),
    (19, "commodities-trading", "大宗商品贸易", "u19-commodities-trading.md"),
    (20, "hr-services", "人力资源服务", None),
]

PREAMBLE = """使用 $leo-ppt-generator，进入 execute 模式 generate 路线，完成以下委托任务。这是一次评测委托：内容与风格合同层是本次唯一交付物。

【委托与边界】
1. 委托执行：合同、大纲、母版、风格与版式决策均由你在授权范围内自主推进并记录为委托决策（decision_source: user-delegated，附依据），无需中途向用户确认；可逆决策自行完成内部审查并留痕。
2. 停止点：完成「内容合同 → 大纲 → 逐页母版 → 风格选定（style list/load/render，同一 home，记录 selection_fingerprint 与归因一句）→ 版式调度（逐页 P 码）→ 容量预检」后即停止。不要生成样张或任何图片，不要派发任何 worker，不要调用图片 Provider；本次无需核对图片 Provider/worker 可用性。
3. 落盘范围：一切产物只写入当前工作目录下的 ./project/ 子树（项目根目录用 ./project/；风格注册表 home 一律隔离在该子树内，如 ./project/leo-home/），不得写该子树之外的任何位置。
4. 材料边界：只依据下面的任务简报与随附材料；不联网检索；不读取本任务输入之外的任何文件。材料/简报未给出的关键事实不足时，按合同纪律披露并收窄断言（unknown），不要编造。
5. blocked 纪律：如遇无法可靠推断且必须用户补答的关键事实，记录 blocked 项与原因，继续完成其余部分；不得模拟用户答案或伪造人工确认。
6. 完成后回复一页摘要：产物路径清单（合同/大纲/母版/风格选择记录/版式调度记录）、确切页数、风格选择与归因一句、容量预检结论（含软超如实报告）、blocked 清单（若有）。

【任务简报】
"""

MATERIALS_HEADER = """
【随附材料】（材料引用级来源，允许输入的全部；数字与口径以此为准）
"""


def build_prompt(num: int, slug: str, material_file: str | None) -> str:
    brief = (FIXTURE_DIR / "tasks" / f"u{num:02d}-{slug}.md").read_text(encoding="utf-8")
    prompt = PREAMBLE + brief
    if material_file:
        material = (FIXTURE_DIR / "materials" / material_file).read_text(encoding="utf-8")
        prompt += MATERIALS_HEADER + material
    else:
        prompt += "\n（本单元无随附材料——只给目标形态，约束见简报「材料指引」节。）\n"
    return prompt


def build_case_yaml(num: int, slug: str, industry: str, material_file: str | None) -> str:
    case_id = f"content-quality-u{num:02d}"
    prompt = build_prompt(num, slug, material_file)
    material_note = "直出（含随附材料）" if material_file else "只给目标（无随附材料）"
    return f"""id: {case_id}
title: 跨行业内容质量 U{num:02d} {industry}（{material_note}）
description: |
  方案 005 跨行业内容质量测评单元：{industry}。真实 agent 运行 execute 模式 generate
  路线至内容与风格合同完成、样张前截断；A1–A5 判据由评测侧 L0 机检与 L1 双判官在冻结
  产物上离线评审；内联 judge 仅检查停止点执行边界，harness 通过≠内容达标。

input:
  prompt: |
{"".join("    " + line + chr(10) for line in prompt.splitlines())}
constraints:
  max_turns: 48
  timeout_seconds: 3600

judge:
  type: script
  script_path: evals/fixtures/scripts/judge_content_execution_boundary.py
  timeout_seconds: 10

collect_artifacts:
  - "project/**"
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只校验无漂移，不重写")
    args = parser.parse_args()

    drift = []
    for num, slug, industry, material_file in UNITS:
        expected = build_case_yaml(num, slug, industry, material_file)
        target = CASES_DIR / f"content-quality-u{num:02d}.yaml"
        if args.check:
            if not target.exists():
                drift.append(f"缺失 {target.name}")
            elif target.read_text(encoding="utf-8") != expected:
                drift.append(f"漂移 {target.name}（fixture 与 case 不一致）")
        else:
            target.write_text(expected, encoding="utf-8")
            print(f"生成 {target}")
    if args.check:
        if drift:
            for d in drift:
                print(f"DRIFT: {d}", file=sys.stderr)
            return 1
        print("OK: 20 个 case 与 fixture 权威源一致，无漂移")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
