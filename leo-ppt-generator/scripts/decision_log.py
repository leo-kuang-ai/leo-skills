#!/usr/bin/env python3
r"""Decision log for deck projects (R-44): record / list / cite decisions.

"Why did we settle it this way back then?" — style picks, layout trade-offs
and structural decisions are recorded at the moment they happen, in the
project content directory, as a plain markdown table (neuro-book ADR
discipline: risk is mandatory, supersession leaves a trace; zero mechanism
cost beyond one file).

Storage: <project>/content/decision-log.md (override with --file). One
markdown row per decision:

    | ID | 决策 | 理由 | 风险 | 替代 | 状态 |
    | --- | --- | --- | --- | --- | --- |
    | D-001 | 风格选定清爽专业风 | 用户偏好轻量数据叙事 | 密集数据页信息密度不足，需台账版式兜底 | 深色科技风（样张落选） | superseded |

IDs are zero-padded counters (D-001, D-002, ...) derived from the existing
table; `add` appends, `supersede` flips the old row's status instead of
rewriting history. Statuses: active (default) / superseded / reversed.

Commands:
  add "决策" --reason R [--risk K] [--alt A] [--status active] [--date YYYY-MM-DD]
      Append one decision. --risk is REQUIRED by the ADR discipline: a
      decision without a stated risk is a decision nobody can revisit
      safely, so the command refuses to run without it.
  list [--status active|superseded|reversed] [--topic KEYWORD]
      Print rows (file order, deterministic). --topic filters by substring
      across decision/reason/alt.
  cite D-001
      Print a one-line citation for pasting into later revision rounds —
      reference the logged decision instead of re-arguing it.
  supersede D-001 [--by D-002]
      Mark an existing row superseded (append " <- D-00N" to its status
      cell). The replacement must already exist in the log.

Determinism: no clock, no randomness; IDs derive from file content; row
order is append-only. Dates are operator-supplied, never invented.

Exit codes: 0 ok; 1 = referenced ID not found (cite/supersede); 2 = usage
error (missing --risk, bad status, unreadable table).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_USAGE = 2

STATUSES = ("active", "superseded", "reversed")
COLUMNS = ("ID", "决策", "理由", "风险", "替代", "状态")
HEADER = "| " + " | ".join(COLUMNS) + " |"
SEPARATOR = "| " + " | ".join(["---"] * len(COLUMNS)) + " |"
ID_RE = re.compile(r"^D-(\d{3,})$")
DEFAULT_REL = Path("content") / "decision-log.md"


def split_row(line: str) -> list[str] | None:
    """Parse one markdown table row into cells; None if not a data row."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if len(cells) != len(COLUMNS):
        return None
    if cells[0] in COLUMNS or set("".join(cells)) <= {"-", ":", " "}:
        return None  # header or separator row
    return cells


def load_entries(path: Path) -> list[list[str]]:
    """All decision rows in file order."""
    if not path.is_file():
        return []
    entries: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = split_row(line)
        if cells:
            entries.append(cells)
    return entries


def render_file(entries: list[list[str]], title: str) -> str:
    lines = [f"# {title}", "", HEADER, SEPARATOR]
    lines += ["| " + " | ".join(row) + " |" for row in entries]
    return "\n".join(lines) + "\n"


def next_id(entries: list[list[str]]) -> str:
    numbers = [int(m.group(1)) for row in entries
               if (m := ID_RE.match(row[0]))]
    return f"D-{max(numbers, default=0) + 1:03d}"


def find_entry(entries: list[list[str]], entry_id: str) -> tuple[int, list[str]] | None:
    for index, row in enumerate(entries):
        if row[0] == entry_id:
            return index, row
    return None


def cmd_add(args, path: Path) -> int:
    if not args.risk or not args.risk.strip():
        print("决策必须显式声明风险（--risk）：无风险的决策无法被安全推翻", file=sys.stderr)
        return EXIT_USAGE
    entries = load_entries(path)
    entry_id = next_id(entries)
    date = f"（{args.date}）" if args.date else ""
    row = [
        entry_id,
        args.decision.strip(),
        args.reason.strip() if args.reason else "",
        args.risk.strip(),
        args.alt.strip() if args.alt else "—",
        f"{args.status}{date}",
    ]
    entries.append(row)
    if path.is_file():
        # Append-only on an existing log: preserve everything above the table.
        text = path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"
        if not any(split_row(line) for line in text.splitlines()):
            text += HEADER + "\n" + SEPARATOR + "\n"
        path.write_text(text + "| " + " | ".join(row) + " |" + "\n", encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_file(entries, "Deck 决策账本（decision log）"),
                        encoding="utf-8")
    print(f"recorded {entry_id}: {row[1]}")
    return EXIT_OK


def cmd_list(args, path: Path) -> int:
    entries = load_entries(path)
    if not entries:
        print(f"(决策账本为空: {path})", file=sys.stderr)
        return EXIT_OK
    keyword = (args.topic or "").strip()
    shown = 0
    for row in entries:
        if args.status and args.status not in row[5]:
            continue
        if keyword and not any(keyword in cell for cell in (row[1], row[2], row[4])):
            continue
        print("| " + " | ".join(row) + " |")
        shown += 1
    if not shown:
        print("(无匹配条目)", file=sys.stderr)
    return EXIT_OK


def cmd_cite(args, path: Path) -> int:
    entries = load_entries(path)
    hit = find_entry(entries, args.id)
    if hit is None:
        print(f"未找到决策 {args.id}（账本 {path}）", file=sys.stderr)
        return EXIT_NOT_FOUND
    _, row = hit
    entry_id, decision, reason, risk, alt, status = row
    cite = (f"[{entry_id}] {decision} —— 理由：{reason or '（未记录）'}；"
            f"风险：{risk or '（未记录）'}；替代：{alt or '—'}；状态：{status}"
            f"（见 {path.name}，引用而非重新论证）")
    print(cite)
    return EXIT_OK


def cmd_supersede(args, path: Path) -> int:
    if not path.is_file():
        print(f"决策账本不存在: {path}", file=sys.stderr)
        return EXIT_NOT_FOUND
    entries = load_entries(path)
    hit = find_entry(entries, args.id)
    if hit is None:
        print(f"未找到决策 {args.id}", file=sys.stderr)
        return EXIT_NOT_FOUND
    if args.by and find_entry(entries, args.by) is None:
        print(f"替代决策 {args.by} 不在账本中（须先 add）", file=sys.stderr)
        return EXIT_NOT_FOUND
    index, row = hit
    if "superseded" in row[5]:
        print(f"{args.id} 已是 superseded，幂等跳过", file=sys.stderr)
        return EXIT_OK
    row[5] = f"superseded <- {args.by}" if args.by else "superseded"
    entries[index] = row
    # Rewrite the file preserving non-table lines untouched.
    lines = path.read_text(encoding="utf-8").splitlines()
    table_rows = iter(["| " + " | ".join(e) + " |" for e in entries])
    out = [next(table_rows) if split_row(line) else line for line in lines]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{args.id} -> superseded" + (f" (by {args.by})" if args.by else ""))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="决策账本（R-44）：风格/版式/结构决策的记档与引用")
    parser.add_argument("--file", default=None,
                        help="账本路径（默认 ./content/decision-log.md）")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="追加一条决策（风险必填）")
    add.add_argument("decision", help="决策一句话")
    add.add_argument("--reason", default="", help="决策理由")
    add.add_argument("--risk", default="", help="已知风险（必填）")
    add.add_argument("--alt", default="", help="被否掉的替代方案")
    add.add_argument("--status", choices=STATUSES, default="active")
    add.add_argument("--date", default=None, help="决策日期 YYYY-MM-DD（可选，不自动生成）")

    list_cmd = sub.add_parser("list", help="列出决策（可按状态/主题过滤）")
    list_cmd.add_argument("--status", choices=STATUSES, default=None)
    list_cmd.add_argument("--topic", default=None, help="关键词过滤（决策/理由/替代）")

    cite = sub.add_parser("cite", help="输出引用句（改稿回复中粘贴）")
    cite.add_argument("id", help="决策 ID，如 D-001")

    supersede = sub.add_parser("supersede", help="标记决策被替代（留痕不删行）")
    supersede.add_argument("id", help="被替代的决策 ID")
    supersede.add_argument("--by", default=None, help="替代它的新决策 ID")

    args = parser.parse_args(argv)
    path = (Path(args.file).expanduser().resolve() if args.file
            else Path.cwd() / DEFAULT_REL)

    if args.command == "add":
        return cmd_add(args, path)
    if args.command == "list":
        return cmd_list(args, path)
    if args.command == "cite":
        return cmd_cite(args, path)
    return cmd_supersede(args, path)


if __name__ == "__main__":
    raise SystemExit(main())
