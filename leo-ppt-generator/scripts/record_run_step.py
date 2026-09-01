#!/usr/bin/env python3
"""record_run_step.py — run 阶段账本（R-37）。

向 <run>/reports/run-ledger.jsonl 追加阶段事件，并给出"从哪继续"的恢复建议。
上游依据：webnovel-writer data_modules/run_ledger.py 的 WRITE_STEPS 六步记账与
build_write_resume_plan 建议式恢复（只给建议不自动覆盖）。本脚本把同一礼仪平移到
leo 的页内阶段链：prompt → backend → qa → record，加 deck 级 receipt（收据门）。

阶段集合（对齐 execution-contract 逐页三层容错 + 指纹收据）：
  RUN_STEPS = ("prompt", "backend", "qa", "record", "receipt")
  prompt/backend/qa 为页内三阶段；record 为该页 image record 落账；receipt 为
  deck 级收据 create/verify（page 为 null）。step 不在集合内时 exit 4。

用法：
  record_run_step.py --run DIR --step prompt --page 3 --attempt 1 --status completed \
      [--problems-json '["..."]'] [--artifact FILE] [--note "..."]
  record_run_step.py --run DIR --tail N
  record_run_step.py --run DIR --resume-suggestion

退出码：0 记录/查看/建议成功；2 双义——需人工裁决（账本为空不含此义；闭合
       状态矛盾、阶段重试预算耗尽须改变输入后再试），或 argparse 用法错误
       （参数非法：命令打错重试即可，状态矛盾才需人工裁决）；
       4 run 目录无效 / 页内阶段缺 --page。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
LEDGER_NAME = "run-ledger.jsonl"
RUN_STEPS = ("prompt", "backend", "qa", "record", "receipt")
PAGE_STEPS = ("prompt", "backend", "qa", "record")
# Statuses that close a step; "started" leaves it open.
CLOSED_STATUSES = ("completed", "failed", "skipped")
MAX_PAGE_ATTEMPTS = 3  # execution-contract: 每页阶段重试 ≤3

EXIT_OK = 0
EXIT_NEEDS_HUMAN = 2
EXIT_USAGE = 4


def ledger_path(run_dir: Path) -> Path:
    return run_dir / "reports" / LEDGER_NAME


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _artifact_signature(run_dir: Path, artifact: str | None) -> dict:
    if not artifact:
        return {"artifact": None, "artifact_sha256": None}
    path = (run_dir / artifact).resolve() if not Path(artifact).is_absolute() else Path(artifact)
    if not path.is_file():
        return {"artifact": artifact, "artifact_sha256": None,
                "artifact_problem": "artifact file missing"}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    rel = path.resolve()
    try:
        rel = path.relative_to(run_dir.resolve())
    except ValueError:
        pass
    return {"artifact": str(rel), "artifact_sha256": digest}


def append_step(
    run_dir: Path,
    *,
    step: str,
    page: str | None,
    attempt: int,
    status: str,
    problems: list[str],
    artifact: str | None,
    note: str,
) -> dict:
    entry = {
        "schema_version": SCHEMA_VERSION,
        "ts": now_iso(),
        "step": step,
        "page": page,
        "attempt": int(attempt),
        "status": status,
        "problems": [str(p) for p in problems],
        **_artifact_signature(run_dir, artifact),
    }
    if note:
        entry["note"] = note
    path = ledger_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def read_entries(run_dir: Path) -> list[dict]:
    path = ledger_path(run_dir)
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def _page_sort_key(page: str) -> tuple:
    m = re.search(r"(\d+)", page)
    return (int(m.group(1)) if m else 1 << 30, page)


def _last_status(entries: list[dict], step: str, page: str | None) -> dict | None:
    latest = None
    for entry in entries:
        if entry.get("step") == step and entry.get("page") == page:
            latest = entry
    return latest


def build_resume_suggestion(entries: list[dict]) -> tuple[str, bool]:
    """Return (suggestion_text, needs_human).

    needs_human=True 当：账本为空；或存在 failed 且尝试已达上限（重复失败纪律）；
    或同一页同一阶段出现相互矛盾的闭合状态（并发会话双写账本）。
    """
    if not entries:
        return "账本为空：无已记录阶段，从首个页的 prompt 阶段开始。", False

    pages = sorted({e["page"] for e in entries if e.get("page")}, key=_page_sort_key)
    conflicts: list[str] = []
    overrun: list[str] = []

    def step_state(page: str | None, step: str) -> tuple[str, dict | None]:
        """(state, last_entry): open / closed-status / missing."""
        hits = [e for e in entries if e.get("step") == step and e.get("page") == page]
        if not hits:
            return "missing", None
        closed = [e for e in hits if e.get("status") in CLOSED_STATUSES]
        if closed:
            states = {e.get("status") for e in closed}
            if len(states) > 1:
                conflicts.append(
                    f"{'deck 级' if page is None else page}/{step}: 闭合状态矛盾 {sorted(states)}")
            return str(closed[-1].get("status")), closed[-1]
        return "open", hits[-1]

    # Detect retry-budget overrun (execution-contract 第 0 条纪律).
    for page in pages:
        for step in PAGE_STEPS:
            fails = [e for e in entries
                     if e.get("step") == step and e.get("page") == page
                     and e.get("status") == "failed"]
            if fails and max(int(e.get("attempt") or 0) for e in fails) >= MAX_PAGE_ATTEMPTS:
                overrun.append(f"{page}/{step} 已失败 {len(fails)} 次（attempt≥{MAX_PAGE_ATTEMPTS}）")

    lines = []
    resume_target = None
    for page in pages:
        states = {step: step_state(page, step)[0] for step in PAGE_STEPS}
        pending = [step for step in PAGE_STEPS if states[step] in ("missing", "open", "failed")]
        if pending:
            if resume_target is None:
                resume_target = (page, pending[0])
        lines.append(f"- {page}: prompt={states['prompt']} backend={states['backend']} "
                     f"qa={states['qa']} record={states['record']}")

    receipt_state, _ = step_state(None, "receipt")
    if resume_target is None:
        if receipt_state == "completed":
            head = "全部已记录页均 record completed 且收据 completed：无待续阶段。"
        else:
            head = "全部已记录页均 record completed；下一步为 deck 级 receipt（收据 create/verify）。"
            resume_target = ("deck", "receipt")
    else:
        page, step = resume_target
        head = f"从 {page} 的 {step} 阶段继续（其后阶段未记录，不重做已 completed 阶段）。"

    out = [head, "resume_from: " + (f"{resume_target[0]}/{resume_target[1]}" if resume_target else "none")]
    out.extend(lines)
    out.append(f"- deck/receipt: {receipt_state}")
    if overrun:
        out.append("重复失败纪律（第 0 条）：以下阶段已达重试预算，重复失败前必须改变输入、"
                   "配置、backend 或实现；同输入原样重试不计入任何层预算——")
        out.extend(f"  - {item}" for item in overrun)
    if conflicts:
        out.append("账本冲突（疑似并发会话双写）：以下阶段存在矛盾闭合状态，停止推进并人工裁决——")
        out.extend(f"  - {item}" for item in conflicts)

    return "\n".join(out), bool(conflicts or overrun)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="run 阶段账本：追加 / 查看 / 续点建议")
    parser.add_argument("--run", required=True, help="run 目录（含 reports/）")
    parser.add_argument("--step", choices=RUN_STEPS, help="要记录的阶段")
    parser.add_argument("--page", default=None,
                        help="页标识（如 3 / page_003）；receipt 等 deck 级步骤省略")
    parser.add_argument("--attempt", type=int, default=1, help="该页该阶段第几次尝试")
    parser.add_argument("--status", default=None, help="completed / failed / skipped / started")
    parser.add_argument("--problems-json", default="[]", help="问题清单 JSON 数组")
    parser.add_argument("--artifact", default=None, help="产物路径（相对 run 或绝对），自动计算 sha256")
    parser.add_argument("--note", default="", help="自由备注")
    parser.add_argument("--tail", type=int, default=None, metavar="N", help="查看最后 N 行")
    parser.add_argument("--resume-suggestion", action="store_true", help="输出从哪继续的建议文本")
    args = parser.parse_args(argv)

    run_dir = Path(args.run).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"run 目录不存在: {run_dir}", file=sys.stderr)
        return EXIT_USAGE

    if args.resume_suggestion or args.tail is not None:
        if args.step or args.status:
            parser.error("--tail / --resume-suggestion 与记录参数互斥")
        if args.tail is not None:
            entries = read_entries(run_dir)[-args.tail:]
            for entry in entries:
                print(json.dumps(entry, ensure_ascii=False, sort_keys=True))
            return EXIT_OK
        text, needs_human = build_resume_suggestion(read_entries(run_dir))
        print(text)
        return EXIT_NEEDS_HUMAN if needs_human else EXIT_OK

    if not args.step or not args.status:
        parser.error("记录模式需要 --step 与 --status")
    try:
        problems = json.loads(args.problems_json)
        if not isinstance(problems, list):
            raise ValueError("problems-json 必须是 JSON 数组")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"--problems-json 不合法: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.step != "receipt" and not args.page:
        print("页内阶段必须给 --page（receipt 为 deck 级，省略 page）", file=sys.stderr)
        return EXIT_USAGE
    if args.step == "receipt" and args.page:
        print("receipt 为 deck 级阶段，不接受 --page", file=sys.stderr)
        return EXIT_USAGE

    entry = append_step(
        run_dir,
        step=args.step,
        page=args.page,
        attempt=args.attempt,
        status=args.status,
        problems=problems,
        artifact=args.artifact,
        note=args.note,
    )
    print(json.dumps(entry, ensure_ascii=False, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
