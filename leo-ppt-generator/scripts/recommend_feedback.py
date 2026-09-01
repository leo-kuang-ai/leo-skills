#!/usr/bin/env python3
"""风格推荐反馈闭环（R-64）：记录归类、建议家族权重、提供清理入口。

上游原型：《Style推荐引擎设计》第六节（反馈闭环）——``feedback.log`` 记
{brief, candidates, recommended, user_choice, veto_words}，三机制：否定词
回填降权标记、简易 bandit（同场景被选中/被否定的家族计数，周期回写
boost/decay）、别名扩充（经治理确认）。leo 化数据边界（PRD R-64）：

- **仅存本地**：数据落 ``${LEO_PPT_HOME}/style-feedback/records.jsonl``
  （或 ``--store`` 显式路径），随 LEO_PPT_HOME 数据目录管理；
- **只存归类标签，不存原话**：brief 信号经 ``style_hard_rules.evaluate``
  归类为家族标签后落盘，genre/domain/受众等原文措辞一律不落；候选/选中/
  被否风格只落风格名与家族映射；
- **清理入口**：``clear`` 一键清空；
- **用户措辞不落盘**：``record --note`` 直接拒收（可能含业务数据）；
  用户否定措辞若要补进某风格 ``aliases`` 候选，须先经治理确认、人工
  编辑 brief，不经本脚本落盘。

用法::

    python3 scripts/recommend_feedback.py record \
        --brief-json '{"genre":"融资路演","domain":["AI"]}' \
        --candidates '暗黑科技风,麦肯锡咨询风,极简风' \
        --chosen '暗黑科技风' --rejected-ids '麦肯锡咨询风'
    python3 scripts/recommend_feedback.py suggest-weights
    python3 scripts/recommend_feedback.py clear

``suggest-weights`` 读全部累积记录，输出家族 boost/decay 建议 JSON（简易
bandit 口径：chosen 家族计数 +1、rejected 家族计数 -1；net ≥ ``--threshold``
（默认 2）建议 boost，≤ -threshold 建议 decay，其余 hold）。输出确定性：
纯计数聚合 + 排序，无时间戳参与。

退出码：0 = 成功；1 = 拒收（如 --note 含用户原话）；2 = 用法错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import style_hard_rules as shr  # noqa: E402

SCHEMA_VERSION = 1
STORE_REL = Path("style-feedback") / "records.jsonl"


def default_home() -> Path:
    """Resolve LEO_PPT_HOME with the same convention as runtime config."""
    override = os.environ.get("LEO_PPT_HOME")
    if override and override.strip():
        return Path(os.path.expanduser(override)).resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" /
                "leo-ppt-generator")
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "leo-ppt-generator"
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "leo-ppt-generator"


def _families_of(style_name: str) -> list[str]:
    """Reverse lookup: which declared families contain this style name."""
    return sorted(fam for fam, members in shr.FAMILIES.items() if style_name in members)


def _parse_names(raw: str) -> list[str]:
    """Accept a JSON array or a comma-separated list of style names."""
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def _load_records(store: Path) -> list[dict]:
    if not store.is_file():
        return []
    records: list[dict] = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate a torn tail line, never crash on read
        if isinstance(rec, dict) and rec.get("schema_version") == SCHEMA_VERSION:
            records.append(rec)
    return records


def cmd_record(args, store: Path) -> int:
    # Data boundary: user wording must never hit the disk (R-64).
    if args.note and args.note.strip():
        print("note_refused: 用户原话不落盘——反馈日志只存归类标签（可能含业务"
              "数据）；否定措辞仅当轮会话内使用，补进 aliases 候选须先经治理确认"
              "后人工编辑 brief。", file=sys.stderr)
        return 1
    if not args.candidates:
        print("usage: record 需要 --candidates（候选风格名列表）", file=sys.stderr)
        return 2

    try:
        brief = json.loads(args.brief_json) if args.brief_json else {}
    except json.JSONDecodeError as exc:
        print(f"brief_json_invalid: {exc}", file=sys.stderr)
        return 2
    if not isinstance(brief, dict):
        print("brief_json_not_object: --brief-json 须为 JSON 对象", file=sys.stderr)
        return 2

    # Store family classification only; raw signal wording stays in-session.
    verdict = shr.evaluate(brief)
    candidates = _parse_names(args.candidates)
    chosen = (args.chosen or "").strip()
    rejected = _parse_names(args.rejected_ids or "")

    records = _load_records(store)
    record = {
        "schema_version": SCHEMA_VERSION,
        "seq": len(records) + 1,
        "signal_family": {
            "exclude": verdict["exclude_families"],
            "lock": verdict["lock_families"],
            "prefer": verdict["prefer_families"],
            "triggered_rules": verdict["triggered_rules"],
        },
        "candidates": {name: _families_of(name) for name in candidates},
        "chosen": {"style": chosen, "families": _families_of(chosen)} if chosen else None,
        "rejected": [{"style": name, "families": _families_of(name)}
                     for name in rejected],
    }
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"recorded: seq={record['seq']} -> {store}（只存归类标签，不存原话）")
    return 0


def cmd_suggest_weights(args, store: Path) -> int:
    records = _load_records(store)
    tally: dict[str, dict[str, int]] = {}
    for rec in records:
        if rec.get("chosen"):
            for fam in rec["chosen"].get("families", []):
                tally.setdefault(fam, {"chosen": 0, "rejected": 0})["chosen"] += 1
        for rej in rec.get("rejected", []):
            for fam in rej.get("families", []):
                tally.setdefault(fam, {"chosen": 0, "rejected": 0})["rejected"] += 1

    threshold = args.threshold
    boost, decay, hold = [], [], []
    families = {}
    for fam in sorted(tally):
        chosen_n = tally[fam]["chosen"]
        rejected_n = tally[fam]["rejected"]
        net = chosen_n - rejected_n
        families[fam] = {"chosen": chosen_n, "rejected": rejected_n, "net": net}
        if net >= threshold:
            boost.append(fam)
        elif net <= -threshold:
            decay.append(fam)
        else:
            hold.append(fam)
    suggestion = {
        "records": len(records),
        "families": families,
        "suggestions": {"boost": boost, "decay": decay, "hold": hold},
        "usage_note": "boost/decay 为人工回写建议（否定词回写与别名扩充均须经"
                      "治理确认）；本输出不落盘、不自动改推荐权重",
    }
    print(json.dumps(suggestion, ensure_ascii=False, indent=2))
    return 0


def cmd_clear(store: Path) -> int:
    if not store.is_file():
        print(f"clear: 无反馈记录（{store} 不存在），已是空库")
        return 0
    records = _load_records(store)
    store.unlink()
    print(f"cleared: 删除 {len(records)} 条归类记录（{store}）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # --store lives on each subparser so it is accepted after the subcommand.
    sub = parser.add_subparsers(dest="command", required=True)
    p_rec = sub.add_parser("record", help="记录一次推荐的归类标签（不存原话）")
    p_rec.add_argument("--brief-json", help="合同信号 JSON（genre/domain/audience/"
                      "formality/culture/named_style；只落家族归类不落原文）")
    p_rec.add_argument("--candidates", help="候选风格名（JSON 数组或逗号分隔）")
    p_rec.add_argument("--chosen", help="用户选中的风格名（可空）")
    p_rec.add_argument("--rejected-ids", help="被用户否定的风格名（逗号分隔）")
    p_rec.add_argument("--note", help=argparse.SUPPRESS)  # always refused (R-64)
    p_sug = sub.add_parser("suggest-weights", help="输出家族 boost/decay 建议 JSON")
    p_sug.add_argument("--threshold", type=int, default=2,
                       help="net 计数进入 boost/decay 建议的阈值（默认 2）")
    p_clr = sub.add_parser("clear", help="清空反馈记录（清理入口）")
    for p in (p_rec, p_sug, p_clr):
        p.add_argument("--store", help="显式记录文件路径"
                       "（默认 ${LEO_PPT_HOME}/style-feedback/records.jsonl）")
    args = parser.parse_args(argv)

    store = Path(args.store).resolve() if args.store else default_home() / STORE_REL

    if args.command == "record":
        return cmd_record(args, store)
    if args.command == "suggest-weights":
        return cmd_suggest_weights(args, store)
    return cmd_clear(store)


if __name__ == "__main__":
    sys.exit(main())
