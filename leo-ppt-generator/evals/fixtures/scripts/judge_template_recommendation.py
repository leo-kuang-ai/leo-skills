#!/usr/bin/env python3
"""U7/F6：24 题推荐评测判官（独立于被测推荐器）。

四类错误注入必须拒绝（恒定风格/密度交换/忽略受众/捏造理由）；正常多解
答案不误判。判官只读取冻结标签与被测输出，不读取被测推荐器代码。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[3]


def judge_one(task: dict, label: dict, output: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["输出必须为 JSON 对象"]
    candidates = output.get("candidates")
    if not isinstance(candidates, list):
        return ["candidates 必须为数组"]
    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"候选 {i + 1} 必须为对象")
            continue
        if not isinstance(candidate.get("name"), str) or not candidate["name"].strip():
            errors.append(f"候选 {i + 1} 缺少非空 name")
        reasons = candidate.get("reasons", [])
        if not isinstance(reasons, list) or any(not isinstance(r, str) for r in reasons):
            errors.append(f"候选 {i + 1}.reasons 必须为字符串数组")
        if "verified" in candidate and not isinstance(candidate["verified"], bool):
            errors.append(f"候选 {i + 1}.verified 必须为布尔值")
        if "density" in candidate and not isinstance(candidate["density"], str):
            errors.append(f"候选 {i + 1}.density 必须为字符串")
    names = [c.get("name") for c in candidates if isinstance(c, dict)
             and isinstance(c.get("name"), str)]
    hard = [n for n in names if n in label["unsuitable"]]
    if hard:
        errors.append(f"明显不适配候选进入推荐：{hard}")
    if not names:
        errors.append("零候选（无已验证候选应披露方向，不零输出）")
    if len(names) > 3:
        errors.append("候选超过 3 个（通常 2–3 个实质不同方向）")
    if len(set(names)) == 1 and len(names) > 1:
        errors.append("恒定风格：同一风格重复占位")
    # 密度交换：任务密度与首位候选密度差 ≥2 档即错误（除非无密度声明披露）。
    task_density = (task["signals"].get("content_shape") or {}).get("density")
    if task_density:
        first = candidates
        if first and first[0].get("density") and first[0]["density"] != task_density:
            tiers = ["very-low", "low", "low-medium", "balanced", "medium-high", "high"]
            if task_density in tiers and first[0]["density"] in tiers:
                gap = abs(tiers.index(task_density) - tiers.index(first[0]["density"]))
                if gap >= 2:
                    errors.append(f"密度错配占首：任务 {task_density} vs 候选 {first[0]['density']}")
    # 忽略受众：任务受众关键词与候选理由完全无关联。
    audience = str(task["signals"].get("audience") or "")
    reasons = " ".join(r for c in output.get("candidates", []) for r in c.get("reasons", []))
    if audience and len(audience) >= 3 and candidates:
        tokens = [audience[i:i+2] for i in range(len(audience) - 1)]
        audience_acknowledged = (
            any(tok in reasons or tok in " ".join(names) for tok in tokens[:6])
            or "受众" in reasons or "audience" in reasons.lower())
        if not audience_acknowledged:
            errors.append("受众信号被忽略：理由与任务受众无任何关联")
    # 捏造理由：理由引用不存在的任务条件或未验证状态。
    for cand in candidates:
        for reason in cand.get("reasons", []):
            if "已验证" in reason or "verified" in reason.lower():
                if not cand.get("verified"):
                    errors.append(f"捏造验证状态：{reason}")
            for keyword in ("用户点名", "参考图"):
                if keyword in reason and task["signals"].get("named_style") is None:
                    errors.append(f"捏造{keyword}依据：{reason}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, help="被测推荐器逐题输出 JSON")
    parser.add_argument("--out", help="判官结论落盘路径")
    args = parser.parse_args()
    tasks = {t["task_id"]: t for t in json.loads(
        (SKILL / "evals/fixtures/template-quality/recommendation-tasks.json").read_text())["tasks"]}
    labels = {l["task_id"]: l for l in json.loads(
        (SKILL / "evals/fixtures/template-quality/recommendation-labels.json").read_text())["labels"]}
    results = json.loads(Path(args.results).read_text())
    if not isinstance(results, dict):
        print(json.dumps({"kind": "recommendation-judge-verdict", "schema_version": 1,
                          "tasks_judged": 0, "total_errors": 1,
                          "errors": ["results 必须为对象"]}, ensure_ascii=False,
                         indent=2))
        return 1
    verdicts = {}
    total_errors = 0
    for task_id, output in sorted(results.items()):
        if task_id not in tasks or task_id not in labels:
            errors = ["未知 task_id 或缺少冻结标签"]
        else:
            errors = judge_one(tasks[task_id], labels[task_id], output)
        verdicts[task_id] = {"errors": errors}
        total_errors += len(errors)
    missing = sorted(set(tasks) - set(results))
    if missing:
        total_errors += len(missing)
        for task_id in missing:
            verdicts[task_id] = {"errors": ["results 缺少该 task_id"]}
    report = {"kind": "recommendation-judge-verdict", "schema_version": 1,
              "tasks_judged": len(verdicts), "total_errors": total_errors,
              "verdicts": verdicts}
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    print(payload if not args.out else json.dumps(
        {"tasks_judged": len(verdicts), "total_errors": total_errors}, ensure_ascii=False))
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
