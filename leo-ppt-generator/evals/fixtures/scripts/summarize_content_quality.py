#!/usr/bin/env python3
"""跨行业内容质量测评 · 结果汇总器（方案 005 §3.7 唯一汇总口径）。

输入：每单元 machine-report.json、两家族判官结果（含仲裁）、校准记录、
重试账；输出：任务级/维度级/套件级结论矩阵 + 达标门禁判定。

铁律：
- 分母固定（任务 20 / G2 8），fail 与未完成一律保留在分母内；
- 无证据 pass / 缺子项 / 非法状态在判官侧已是 error，此处不修复；
- 布尔校准失效（L2 无效或记录缺失）→ 禁止发布达标结论，只出诊断矩阵；
- 存在未完成评审 → 只报告『已确认通过 X/20，另有 Y 个未完成』；
- 全部结论可由冻结原件 + 本脚本确定性重建。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VALID = ("pass", "fail", "not_applicable", "error", "blocked")


# --------------------------------------------------------------------------- #
# 原子合并
# --------------------------------------------------------------------------- #

def _merge_machine(statuses: list[str | None]) -> str | None:
    """机器侧多检查项预合并：fail 赢；有 pass 则 pass；全 na 才 na；
    candidates/warning 为透明中间态（语义裁决在 L1，不得折叠为 error）。"""
    hard = [s for s in statuses if s is not None]
    if not hard:
        return None
    if any(s == "fail" for s in hard):
        return "fail"
    if any(s == "pass" for s in hard):
        return "pass"
    if all(s == "not_applicable" for s in hard):
        return "not_applicable"
    if any(s == "blocked" for s in hard):
        return "blocked"
    if all(s in ("candidates_for_judge", "warning") for s in hard):
        return "candidates_for_judge"  # 保持透明，交 L1 裁决
    return "error"


def merge_machine_judge(machine_status: str | None, judge_status: str | None) -> str:
    """机器态 + 语义态合并（方案 §3.7：同一子项两者都通过才 pass）。

    - 任一 fail → fail（机器 fail 不因判官 pass 豁免，反之亦然）；
    - 判官缺子项/非法（None）→ error：语义裁决缺失不得静默通过；
    - 机器 candidates_for_judge / warning 是透明中间态（语义裁决在 L1），
      判官 pass 即 pass——判官是否真的核对了候选由 L2 校准把关；
    - 机器 error（如产物/记录缺失）不因判官 pass 变 pass。
    """
    if judge_status is None:
        return "error"
    if judge_status == "fail" or machine_status == "fail":
        return "fail"
    if judge_status == "error":
        return "error"
    if judge_status == "blocked":
        return "blocked"
    if judge_status == "not_applicable":
        return "not_applicable"
    if machine_status in (None, "pass", "not_applicable",
                          "candidates_for_judge", "warning"):
        return "pass"
    return "error"


def dimension_status(subs: dict[str, str]) -> str:
    """维度：全部适用子项 pass 才 pass；任一 fail 则 fail；否则未完成。
    整维度不能全部 not_applicable。"""
    if not subs:
        return "error"
    if all(s == "not_applicable" for s in subs.values()):
        return "error"  # 整维度全不适用 = 配置错误
    if any(s == "fail" for s in subs.values()):
        return "fail"
    if all(s in ("pass", "not_applicable") for s in subs.values()):
        return "pass"
    return "incomplete"  # error/blocked 混合 → 未完成，不算通过也不算失败


def task_status(dimensions: dict[str, str], veto: str,
                required_artifacts_ok: bool) -> str:
    """任务通过 = 必需产物齐全 + 无否决 + A1–A5 全 pass。"""
    if not required_artifacts_ok:
        return "error"  # 产物缺失阻断，按未完成
    if veto == "fail":
        return "fail"
    if any(d == "fail" for d in dimensions.values()):
        return "fail"
    if all(d == "pass" for d in dimensions.values()):
        return "pass"
    return "incomplete"


# --------------------------------------------------------------------------- #
# 判官结果装载与双家族合并
# --------------------------------------------------------------------------- #

def load_judge_result(path: Path) -> dict:
    """装载一个家族的判官结果：path 可以是单文件，也可以是包含
    A{1..5}-<family>.json 的目录。返回 {criterion_id: status}；
    无效/缺失返回 {'__meta__': 'error'}。"""
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    files = [f for f in files
             if not f.name.startswith(("ARB-",)) and ".attempt" not in f.name]
    if not files:
        return {"__meta__": "error", "error": "no judge files"}
    out: dict = {}
    saw_error = False
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saw_error = True
            continue
        if data.get("status") != "ok" or not data.get("verdict"):
            saw_error = True
            continue
        for s in data["verdict"]["subcriteria"]:
            out[s["criterion_id"]] = s["status"]
    if saw_error or not out:
        return {"__meta__": "error", "error": "invalid judge files"}
    return out


def merge_two_families(a: dict, b: dict, arbitrations: dict) -> dict:
    """同子判据双家族合并：一致 → 该状态；分歧 → 仲裁结果；无仲裁 → error。"""
    merged = {}
    keys = sorted(set(a) | set(b))
    for k in keys:
        sa, sb = a.get(k), b.get(k)
        if sa is None or sb is None:
            merged[k] = "error"  # 某家族缺子项
        elif sa == sb:
            merged[k] = sa
        elif k in arbitrations:
            merged[k] = arbitrations[k]
        else:
            merged[k] = "error"  # 分歧未仲裁 → 未完成，不默认多数
    return merged


# --------------------------------------------------------------------------- #
# 校准有效性（布尔门禁）
# --------------------------------------------------------------------------- #

def calibration_valid(calib: dict) -> tuple[bool, list[str]]:
    """L2 有效 = 每位 judge 植入检出 ≥5/6；健康对照零误报；人工一致率 ≥75%。"""
    problems = []
    if not calib or not calib.get("records"):
        return False, ["校准记录缺失"]
    for rec in calib["records"]:
        judge = rec.get("judge", "?")
        detected = rec.get("defects_detected", -1)
        if detected < 5:
            problems.append(f"{judge}: 植入检出 {detected}/6 < 5")
        if rec.get("healthy_false_positives", 0) > 0:
            problems.append(f"{judge}: 健康对照误报 {rec['healthy_false_positives']} > 0")
        agreement = rec.get("human_agreement", -1.0)
        if agreement < 0.75:
            problems.append(
                f"{judge}: 人工一致率 {agreement:.0%} < 75%"
                + ("（人工未完成 → pending，不得代签）" if agreement < 0 else ""))
    return (not problems), problems


# --------------------------------------------------------------------------- #
# 单元汇总
# --------------------------------------------------------------------------- #

def summarize_unit(unit_id: str, machine: dict, judge_a: dict, judge_b: dict,
                   arbitrations: dict) -> dict:
    machine_items = {i["criterion_id"]: i["status"] for i in machine["items"]}

    def machine_of(cid: str) -> str | None:
        return machine_items.get(cid)

    ja = load_judge_result(Path(judge_a)) if judge_a else {}
    jb = load_judge_result(Path(judge_b)) if judge_b else {}
    if not ja or "__meta__" in ja:
        return {"unit": unit_id, "status": "error",
                "reason": "判官 A 结果缺失/无效", "dimensions": {}}
    if not jb or "__meta__" in jb:
        return {"unit": unit_id, "status": "error",
                "reason": "判官 B 结果缺失/无效（双家族缺一）", "dimensions": {}}

    l1 = merge_two_families(ja, jb, arbitrations)
    subs: dict[str, dict[str, str]] = {"A1": {}, "A2": {}, "A3": {}, "A4": {}, "A5": {}}
    # 机器判据 ↔ 子判据映射（protocol criteria_machine_mapping 的代码面）
    machine_pair = {
        "A1.2": ("A1.2-pages", "A1.2-promises+contract"),
        "A2.1": ("A2.2-ledger-structure",),  # ⑩ 四级标注由 contract 检查器承载
        "A2.2": ("A2.2-coverage", "A2.2-diff-retention"),
        "A2.3": ("A2.3-fact-candidates",),
        "A3.2": ("A3.2-density",),
        "A3.3": ("A3.3-prose",),
        "A3.4": ("A3.4-notes",),
        "A4.1": ("A4.1-term-literal",),
        "A5.1": ("A5.1-style-attribution",),
        "A5.2": ("A5.2-pcode",),
        "A5.3": ("A5.3-capacity",),
        "A5.5": ("A5.5-render-structure",),
    }
    for dim in subs:
        for cid_key in [k for k in l1 if k.startswith(dim + ".")]:
            m_keys = machine_pair.get(cid_key, ())
            merged = merge_machine_judge(
                _merge_machine([machine_of(mk) for mk in m_keys]),
                l1.get(cid_key))
            subs[dim][cid_key] = merged

    dimensions = {d: dimension_status(v) for d, v in subs.items()}
    veto = "fail" if machine_items.get("VETO-docs-on-disk") == "error" else "pass"
    # 一票否决细化：VETO-docs-on-disk error = 产物缺失（阻断），不是质量否决
    required_ok = machine_items.get("VETO-docs-on-disk") == "pass"
    status = task_status(
        dimensions,
        veto="fail" if machine_items.get("A5.2-pcode") == "fail" else veto,
        required_artifacts_ok=required_ok)
    return {"unit": unit_id, "status": status, "dimensions": dimensions,
            "subcriteria": subs,
            "machine_summary": machine.get("summary", {}),
            "judge_a": Path(judge_a).name if judge_a else None,
            "judge_b": Path(judge_b).name if judge_b else None}


# --------------------------------------------------------------------------- #
# 套件汇总（分母固定；两轮口径；校准门禁）
# --------------------------------------------------------------------------- #

def summarize_suite(units: list[dict], g2_units: list[str], calib: dict,
                    runs: list[list[dict]] | None = None) -> dict:
    """runs: M3 双轮时的两份 units 列表；None = 单轮（挖掘口径）。"""
    total, g2_total = len(units), len(g2_units)
    denominator_note = f"分母恒定：任务 {total}、G2 {g2_total}（fail/未完成不剔除）"

    def one_pass(run: list[dict]) -> dict:
        passed = [u["unit"] for u in run if u["status"] == "pass"]
        failed = [u["unit"] for u in run if u["status"] == "fail"]
        incomplete = [u["unit"] for u in run
                      if u["status"] in ("error", "incomplete", "blocked")]
        return {"passed": passed, "failed": failed, "incomplete": incomplete,
                "g2_passed": [u for u in passed if u in g2_units]}

    calib_ok, calib_problems = calibration_valid(calib)
    out: dict = {
        "denominators": {"tasks": total, "g2": g2_total},
        "denominator_note": denominator_note,
        "calibration": {"valid": calib_ok, "problems": calib_problems},
        "runs": [],
        "evidence_boundary": {
            "contract_quality": "L0/L1 内容与执行合同证据",
            "render_visual_quality": "not_run",
            "human_visual_review": "not_run",
            "claim_ceiling": "不得据此声称视觉质量或最终 PPT 观感已验证",
        },
    }
    if runs:
        per_run = [one_pass(r) for r in runs]
        out["runs"] = per_run
        if len(runs) == 2:
            both = set(per_run[0]["passed"]) & set(per_run[1]["passed"])
            unstable = [u for u in
                        set(per_run[0]["passed"]) ^ set(per_run[1]["passed"])]
            out["m3"] = {
                "x_both_pass": sorted(both),
                "x_count": len(both),
                "unstable_or_single_fail": sorted(unstable),
                "suite_gate": {
                    "l0_all_pass_both_runs": all(
                        r["incomplete"] == [] and r["failed"] == [] for r in per_run),
                    "note": "L1 维度门槛按维度统计另附（见 dimension_gates）",
                },
            }
    else:
        out["runs"].append(one_pass(units))

    # 维度门槛（L1）：M3 每维度双次通过 ≥18/20、G2 ≥7/8
    dim_counts = {}
    for d in ("A1", "A2", "A3", "A4", "A5"):
        dim_counts[d] = {}
        if runs:
            for ri, run in enumerate(runs, 1):
                passed = sum(1 for u in run
                             if u.get("dimensions", {}).get(d) == "pass")
                g2p = sum(1 for u in run if u["unit"] in g2_units
                          and u.get("dimensions", {}).get(d) == "pass")
                dim_counts[d][f"run{ri}"] = {"pass": passed, "g2_pass": g2p}
        else:
            passed = sum(1 for u in units
                         if u.get("dimensions", {}).get(d) == "pass")
            g2p = sum(1 for u in units if u["unit"] in g2_units
                      and u.get("dimensions", {}).get(d) == "pass")
            dim_counts[d] = {"pass": passed, "g2_pass": g2p}
    out["dimension_gates"] = dim_counts

    # 最终声称控制：必须完成 M3 双轮、L0 全通过，并满足每维度阈值。
    # 仅有校准记录或单轮全绿不能支撑协议中的双次达标结论。
    any_incomplete = any(r.get("incomplete") for r in out["runs"])
    any_failed = any(r.get("failed") for r in out["runs"])
    m3_ready = bool(runs and len(runs) == 2)
    l0_ready = bool(out.get("m3", {}).get("suite_gate", {}).get(
        "l0_all_pass_both_runs"))
    dimension_ready = False
    if m3_ready:
        dimension_ready = all(
            out["dimension_gates"][d].get("run1", {}).get("pass", 0) >= 18
            and out["dimension_gates"][d].get("run2", {}).get("pass", 0) >= 18
            and out["dimension_gates"][d].get("run1", {}).get("g2_pass", 0) >= 7
            and out["dimension_gates"][d].get("run2", {}).get("g2_pass", 0) >= 7
            for d in ("A1", "A2", "A3", "A4", "A5"))
    claim_allowed = (calib_ok and m3_ready and l0_ready and dimension_ready
                     and not any_incomplete and not any_failed)
    claim_blocks = [f"校准无效：{p}" for p in calib_problems]
    if not m3_ready:
        claim_blocks.append("缺少 M3 两轮独立复跑，不能声称双次达标")
    if not l0_ready or any_failed:
        claim_blocks.append("L0 未达到两轮 20/20 全通过")
    if not dimension_ready:
        claim_blocks.append("L1 维度门槛未达到：每维度两轮 ≥18/20 且 G2 ≥7/8")
    if any_incomplete:
        claim_blocks.append("存在未完成评审，只能报告已确认通过数与未完成数")
    out["claim"] = {
        "allowed": claim_allowed,
        "template": ("本版本在 20 个固定行业任务中，X 个任务的内容层双次达标；"
                     "未验证未见任务迁移或视觉质量"),
        "blocks": claim_blocks,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--units-file", required=True,
                        help="JSON：[{unit, machine, judge_a, judge_b, arbitrations}]")
    parser.add_argument("--calibration", default=None, help="校准记录 JSON")
    parser.add_argument("--g2", default="u13,u14,u15,u16,u17,u18,u19,u20")
    parser.add_argument("--second-run", default=None,
                        help="第二轮 units-file（M3 双次复跑口径）")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    def load_units(path: str) -> list[dict]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        out = []
        for rec in raw:
            machine = json.loads(Path(rec["machine"]).read_text(encoding="utf-8"))
            out.append(summarize_unit(rec["unit"], machine,
                                      rec.get("judge_a"), rec.get("judge_b"),
                                      rec.get("arbitrations") or {}))
        return out

    units = load_units(args.units_file)
    g2 = [x.strip() for x in args.g2.split(",") if x.strip()]
    calib = (json.loads(Path(args.calibration).read_text(encoding="utf-8"))
             if args.calibration else {})
    runs = [units]
    if args.second_run:
        runs.append(load_units(args.second_run))
    report = summarize_suite(units, g2, calib, runs=runs if args.second_run else None)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"汇总 → {args.out}")
    print(json.dumps({"claim_allowed": report["claim"]["allowed"],
                      "blocks": report["claim"]["blocks"][:3]},
                     ensure_ascii=False))
    return 0 if report["claim"]["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
