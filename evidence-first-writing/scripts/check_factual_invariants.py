#!/usr/bin/env python3
"""Compare mechanically extractable factual invariants across two text files.

stdout 首行输出 ``invariant_hash: before=<sha256> after=<sha256>``（before/after
文件内容的 SHA-256，任一端字节变化即改变哈希；供 post-publish ledger 做
auto-stale 绑定），其后输出 JSON 对比报告。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


PATTERNS = {
    "urls": re.compile(r"https?://[^\s)>\]，。；;]+"),
    "markdown_targets": re.compile(r"\[[^\]]*\]\(([^)]+)\)"),
    "evidence_ids": re.compile(r"\bE\d{3,}\b"),
    "numbers": re.compile(
        r"(?<![\w])(?:\d{4}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?|"
        r"\d+(?:\.\d+)?\s*(?:%|％|万|亿|元|美元|年|月|日|小时|分钟|秒|倍|人|个)?)(?![\w])"
    ),
    "inline_code": re.compile(r"`([^`\n]+)`"),
    "chinese_quotes": re.compile(r"「([^」\n]+)」"),
    "curly_quotes": re.compile(r"“([^”\n]+)”"),
    "double_quotes": re.compile(r'(?<![\w])"([^"\n]+)"'),
}

# URLs sit inside CJK prose where trailing full-width punctuation and Chinese
# characters are not part of the address; stop at the first non-ASCII char.
_NON_ASCII = re.compile(r"[^\x00-\x7f]")


def extract(text: str) -> dict[str, Counter[str]]:
    result: dict[str, Counter[str]] = {}
    for name, pattern in PATTERNS.items():
        values = []
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            if name == "urls":
                value = _NON_ASCII.split(value, maxsplit=1)[0]
            values.append(value.strip())
        result[name] = Counter(value for value in values if value)
    return result


def counter_delta(before: Counter[str], after: Counter[str]) -> dict[str, list[dict[str, object]]]:
    removed = before - after
    added = after - before
    return {
        "removed": [{"value": value, "count": count} for value, count in sorted(removed.items())],
        "added": [{"value": value, "count": count} for value, count in sorted(added.items())],
    }


def compare(before_text: str, after_text: str) -> dict[str, object]:
    before = extract(before_text)
    after = extract(after_text)
    categories = {name: counter_delta(before[name], after[name]) for name in PATTERNS}
    changed = [name for name, delta in categories.items() if delta["removed"] or delta["added"]]
    return {
        "status": "changed" if changed else "unchanged",
        "changed_categories": changed,
        "categories": categories,
        "limitations": [
            "This check does not identify names reliably.",
            "It cannot detect changes to certainty, scope, actor, chronology, or causality.",
            "Every reported addition or removal requires editorial review; a change is not automatically an error.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--fail-on-change", action="store_true")
    args = parser.parse_args()

    before_text = args.before.read_text(encoding="utf-8")
    after_text = args.after.read_text(encoding="utf-8")
    result = compare(before_text, after_text)
    # 内容哈希按原始字节计算（比较文本仍按 utf-8 解码，行为不变），
    # 保证换行符等字节级变化也能被 auto-stale 消费方察觉。
    before_hash = hashlib.sha256(args.before.read_bytes()).hexdigest()
    after_hash = hashlib.sha256(args.after.read_bytes()).hexdigest()
    print(f"invariant_hash: before={before_hash} after={after_hash}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.fail_on_change and result["status"] == "changed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
