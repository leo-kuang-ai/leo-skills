#!/usr/bin/env python3
"""update_postpublish_record.py - 裁决 post-publish 复盘状态块并按显式授权追加 JSONL ledger。

设计合同（对齐 evidence-first-writing/SKILL.md post-publish 节与
references/editorial-pipeline.md Node 14）：

- canonical 四字段块（observation / hypothesis / stable_rule_update / persistence）
  由本脚本产出，模型不得手写；stdout 只包含该块，供判官比对。
- stable_rule_update 取值 none|hypothesis|candidate|promoted；persistence 取值
  not_run|authorized。`promoted` 强制三条件：replications >= 2、comparable_runs >= 2、
  显式声明反例已查（--counterexamples-checked）；缺任一即非零退出且不写 ledger。
- ledger 是 append-only JSONL，仅通过显式 --ledger <path> 写入；无 --ledger 时
  不写任何文件（只 stdout）。--ledger 指向本技能目录或其镜像内部时拒绝。
- persistence: authorized 与 --ledger 互为必要：声明已授权持久写入却未提供授权
  路径、或提供了 ledger 却声明 not_run，均拒绝（防止「声称已写入 / 静默落盘」）。
- 重复写入同 observation 的语义（钉死）：语义完全相同的条目幂等跳过；任一字段
  （含 invariant_hash）不同则追加显式新条目，历史行永不改写。
- 可选 --invariant-hash 记录 check_factual_invariants.py 输出的内容哈希；同
  observation 后续条目携带不同哈希时，新条目以 supersedes_invariant_hash 显式
  标记旧哈希失效（append-only 约束下的 auto-stale 形态）。
- ledger 文件不存在按新建；损坏 JSON 行跳过并向 stderr 警告，不崩溃、不改写。
- 仅标准库；无交互提示。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
SKILL_DIR = SCRIPT_PATH.parents[1]

STABLE_RULE_UPDATE_VALUES = ("none", "hypothesis", "candidate", "promoted")
PERSISTENCE_VALUES = ("not_run", "authorized")
LEDGER_SCHEMA = "efw-postpublish-ledger/1"
PROMOTED_MIN_REPLICATIONS = 2
PROMOTED_MIN_COMPARABLE_RUNS = 2

EXIT_OK = 0
EXIT_VALIDATION = 1

# Hypothesis absent -> canonical literal "none" (must stay unquoted for judges).
HYPOTHESIS_NONE = "none"

_PLAIN_NUMBER = re.compile(r"-?\d+(?:\.\d+)?\Z")
_YAML_LIKE_BOOL = {"true", "false", "null", "yes", "no", "on", "off", "~", ""}


class RecordError(Exception):
    """Validation or IO failure with a user-facing message."""


def yaml_scalar(value: str) -> str:
    """Render a single-line YAML scalar, quoting only when necessary.

    Enum-ish tokens stay plain so textual judges can match the canonical block;
    anything YAML-ambiguous is emitted as a JSON-compatible double-quoted scalar.
    """
    text = str(value)
    if text == HYPOTHESIS_NONE:
        return text
    needs_quote = (
        not text
        or text != text.strip()
        or any(ch in text for ch in ('"', "\\", "\n", "\r", "\t", "#"))
        or ": " in text
        or text.endswith(":")
        or text[0] in "-?:,[]{}&*!|>'%@`"
        or text.lower() in _YAML_LIKE_BOOL
        or _PLAIN_NUMBER.fullmatch(text) is not None
    )
    if needs_quote:
        return json.dumps(text, ensure_ascii=False)
    return text


def render_canonical_block(
    observation: str,
    hypothesis: str | None,
    stable_rule_update: str,
    persistence: str,
) -> str:
    return "\n".join(
        (
            f"observation: {yaml_scalar(observation)}",
            f"hypothesis: {yaml_scalar(hypothesis or HYPOTHESIS_NONE)}",
            f"stable_rule_update: {stable_rule_update}",
            f"persistence: {persistence}",
        )
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def guard_ledger_path(raw: str) -> Path:
    """Resolve the explicitly authorized ledger path, rejecting skill-dir targets."""
    resolved = Path(raw).expanduser().resolve()
    if _is_within(resolved, SKILL_DIR):
        raise RecordError(
            f"ledger 路径禁止落在技能目录内部: {resolved}（技能目录: {SKILL_DIR}）"
        )
    # Reject copies of this skill (host mirrors such as .agents/.claude/...):
    # any ancestor named evidence-first-writing that ships this very script.
    for ancestor in resolved.parents:
        if (
            ancestor.name.casefold() == "evidence-first-writing"
            and (ancestor / "scripts" / SCRIPT_PATH.name).is_file()
        ):
            raise RecordError(
                f"ledger 路径禁止落在技能目录或其镜像内部: {resolved}（命中: {ancestor}）"
            )
    if resolved.is_dir():
        raise RecordError(f"ledger 路径是目录而非文件: {resolved}")
    if not resolved.parent.is_dir():
        raise RecordError(f"ledger 父目录不存在（不会自动创建）: {resolved.parent}")
    return resolved


def validate(args: argparse.Namespace) -> Path | None:
    """Return the guarded ledger path (or None); raise RecordError on any problem."""
    if not args.observation.strip():
        raise RecordError("--observation 不能为空")

    for field in ("replications", "comparable_runs"):
        value = getattr(args, field)
        if value is not None and value < 0:
            raise RecordError(f"--{field.replace('_', '-')} 不能为负数: {value}")

    if args.stable_rule_update == "promoted":
        if args.replications is None:
            raise RecordError(
                "promoted 需要 --replications >= "
                f"{PROMOTED_MIN_REPLICATIONS}（可比项目独立复现次数）"
            )
        if args.replications < PROMOTED_MIN_REPLICATIONS:
            raise RecordError(
                f"promoted 需要 --replications >= {PROMOTED_MIN_REPLICATIONS}，"
                f"实际 {args.replications}；证据不足时只能 none 或 hypothesis"
            )
        if args.comparable_runs is None:
            raise RecordError(
                "promoted 需要 --comparable-runs >= "
                f"{PROMOTED_MIN_COMPARABLE_RUNS}（满足可比控制的项目数）"
            )
        if args.comparable_runs < PROMOTED_MIN_COMPARABLE_RUNS:
            raise RecordError(
                f"promoted 需要 --comparable-runs >= {PROMOTED_MIN_COMPARABLE_RUNS}，"
                f"实际 {args.comparable_runs}；证据不足时只能 none 或 hypothesis"
            )
        if not args.counterexamples_checked:
            raise RecordError(
                "promoted 需要 --counterexamples-checked 声明反例已检查；"
                "未检查反例时只能 none 或 hypothesis"
            )

    if args.invariant_hash is not None and not args.invariant_hash.strip():
        raise RecordError("--invariant-hash 不能为空")

    if args.persistence == "authorized" and not args.ledger:
        raise RecordError(
            "persistence: authorized 需要显式 --ledger <用户授权的目标路径>；"
            "未获授权路径时必须停在 persistence: not_run"
        )
    if args.ledger and args.persistence != "authorized":
        raise RecordError(
            "提供了 --ledger（持久写入）但 persistence 声明为 "
            f"{args.persistence}；写入任何文件都需要用户显式授权，"
            "请改用 --persistence authorized 或去掉 --ledger"
        )

    return guard_ledger_path(args.ledger) if args.ledger else None


def load_ledger_entries(path: Path) -> tuple[list[dict], list[str]]:
    """Read a JSONL ledger; skip corrupt lines with warnings instead of crashing."""
    if not path.exists():
        return [], [f"NOTE: ledger 不存在，按新建处理: {path}"]
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise RecordError(f"ledger 不是 UTF-8 文本: {path}: {exc}") from exc

    entries: list[dict] = []
    warnings: list[str] = []
    for line_number, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            warnings.append(f"WARNING: ledger 第 {line_number} 行不是有效 JSON，已跳过: {path}")
            continue
        if not isinstance(parsed, dict):
            warnings.append(f"WARNING: ledger 第 {line_number} 行不是 JSON 对象，已跳过: {path}")
            continue
        entries.append(parsed)
    return entries, warnings


def build_entry(args: argparse.Namespace, recorded_at: str) -> dict:
    entry: dict = {
        "schema": LEDGER_SCHEMA,
        "recorded_at": recorded_at,
        "observation": args.observation,
        "hypothesis": args.hypothesis or HYPOTHESIS_NONE,
        "stable_rule_update": args.stable_rule_update,
        "persistence": args.persistence,
        "replications": args.replications if args.replications is not None else 0,
        "comparable_runs": args.comparable_runs if args.comparable_runs is not None else 0,
        "counterexamples_checked": bool(args.counterexamples_checked),
    }
    if args.invariant_hash:
        entry["invariant_hash"] = args.invariant_hash.strip()
    if args.counterexamples_note:
        entry["counterexamples_note"] = args.counterexamples_note
    return entry


def dedup_key(entry: dict) -> tuple:
    """Semantic identity of an entry: every field except bookkeeping columns."""
    return (
        entry.get("observation"),
        entry.get("hypothesis"),
        entry.get("stable_rule_update"),
        entry.get("persistence"),
        entry.get("replications"),
        entry.get("comparable_runs"),
        entry.get("counterexamples_checked"),
        entry.get("invariant_hash"),
        entry.get("counterexamples_note"),
    )


def stale_prior_hash(entries: list[dict], observation: str, new_hash: str | None) -> str | None:
    """Latest prior invariant_hash for this observation that differs from new_hash."""
    if not new_hash:
        return None
    for entry in reversed(entries):
        if entry.get("observation") != observation:
            continue
        prior = entry.get("invariant_hash")
        if isinstance(prior, str) and prior != new_hash:
            return prior
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="update_postpublish_record.py",
        description=(
            "裁决 post-publish 复盘状态块（canonical YAML 四字段）并按显式授权"
            "追加 append-only JSONL ledger；无 --ledger 时不写任何文件"
        ),
        epilog=(
            "示例: update_postpublish_record.py record --observation '完读率 62%' "
            "--stable-rule-update hypothesis --persistence not_run"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="{record}")
    record = subparsers.add_parser(
        "record",
        help="记录一次 post-publish 复盘并产出 canonical 状态块",
    )
    record.add_argument("--observation", required=True, help="本次单篇的版本绑定观察（必填）")
    record.add_argument("--hypothesis", help="待验证假设；缺省记为 none")
    record.add_argument(
        "--stable-rule-update",
        required=True,
        choices=STABLE_RULE_UPDATE_VALUES,
        help="稳定规则写入决策（对齐 editorial-pipeline Node 14 四值）",
    )
    record.add_argument(
        "--persistence",
        required=True,
        choices=PERSISTENCE_VALUES,
        help="持久写入授权状态；未获明确授权时只能 not_run",
    )
    record.add_argument(
        "--ledger",
        help="用户显式授权的 JSONL ledger 路径（append-only）；禁止指向技能目录内部",
    )
    record.add_argument(
        "--invariant-hash",
        help="check_factual_invariants.py 输出的内容哈希，写入 ledger 条目",
    )
    record.add_argument(
        "--replications",
        type=int,
        help=f"可比项目独立复现次数（promoted 需要 >= {PROMOTED_MIN_REPLICATIONS}）",
    )
    record.add_argument(
        "--comparable-runs",
        type=int,
        help=f"满足可比控制的项目数（promoted 需要 >= {PROMOTED_MIN_COMPARABLE_RUNS}）",
    )
    record.add_argument(
        "--counterexamples-checked",
        action="store_true",
        help="声明反例已检查（promoted 必需）",
    )
    record.add_argument(
        "--counterexamples-note",
        help="反例检查的声明/路径备注，写入 ledger 条目",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        ledger_path = validate(args)
    except RecordError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    recorded_at = datetime.now().astimezone().isoformat(timespec="seconds")
    entry = build_entry(args, recorded_at)
    block = render_canonical_block(
        entry["observation"],
        entry["hypothesis"],
        entry["stable_rule_update"],
        entry["persistence"],
    )

    if ledger_path is not None:
        try:
            entries, warnings = load_ledger_entries(ledger_path)
        except RecordError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return EXIT_VALIDATION
        for warning in warnings:
            print(warning, file=sys.stderr)

        key = dedup_key(entry)
        if any(dedup_key(existing) == key for existing in entries):
            print(
                f"SKIP: ledger 已存在语义相同的条目，幂等跳过（observation 相同且字段一致）",
                file=sys.stderr,
            )
        else:
            superseded = stale_prior_hash(entries, entry["observation"], entry.get("invariant_hash"))
            if superseded:
                entry["supersedes_invariant_hash"] = superseded
            try:
                with ledger_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError as exc:
                print(f"ERROR: 无法追加 ledger {ledger_path}: {exc}", file=sys.stderr)
                return EXIT_VALIDATION
            print(f"APPEND: {ledger_path}", file=sys.stderr)
            if superseded:
                print(
                    f"NOTE: 旧 invariant_hash 已被本条目显式失效（supersedes_invariant_hash）: {superseded}",
                    file=sys.stderr,
                )

    print(block)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
