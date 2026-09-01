#!/usr/bin/env python3
"""expire_candidates.py — 候选工件过期标记（R-45）。

基线（最高 confirmed 母版，含 post-confirm 修订链）confirmed 后，把 content/ 下
低于该版本的候选工件登记进 content/expired-candidates.json 清单，防止残留候选被
后续会话误读为当前方案。不改动任何原文件（最小侵入：json 清单，不插注释行）。
上游依据：inkos forecast 过期标记——正史（基线）变化后旧推演失效（专家4 报告 #12）。

确定性判定规则：
  1. 母版候选 deck-master-v<K>.md：低于母版基线版本即过期；母版 post-confirm
     链成员属于当前基线，不标；显式 pending 的 post-confirm 退回版本视为链断，
     不作过期基线（未确认内容不当真值，回落更低 confirmed 根）。
  2. 大纲候选 outline-v<M>.md：只对照大纲自身序列的最高 confirmed 版本判过期
     （母版序列只判母版，防跨系列误伤最新确认大纲）；无 confirmed 大纲不猜测。
  3. content/ 下（含 style-candidates/ 等子目录）头部带 `baseline: v<M>` 标记的
     文本工件：标记版本低于母版基线版本即过期（覆盖双样张落选方向等非版本化候选）。
  4. 无版本号、无 baseline 标记的文件不猜测、不进清单。

用法：
  expire_candidates.py --project-root DIR [--list] [--json]

退出码：0 成功（清单已写，可为空）；2 用法错误（content/ 缺失 / 无 confirmed 基线）。
重复运行幂等：清单不含时间戳，内容由当前基线与文件状态唯一决定。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Sibling-script reuse: single confirmed-baseline walk shared with
# reproject_derivatives (pending rollback = chain break, never truth).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_confirmed_baseline import find_confirmed_baseline  # noqa: E402

SCHEMA_VERSION = 1
EXPIRED_LIST = "expired-candidates.json"
MASTER_RE = re.compile(r"^deck-master-v(\d+)\.md$")
OUTLINE_RE = re.compile(r"^outline-v(\d+)\.md$")
BASELINE_MARK_RE = re.compile(r"^baseline:\s*v(\d+)", re.M)

EXIT_OK = 0
EXIT_USAGE = 2


def find_baseline(content_dir: Path) -> tuple[int, str, set[str]] | None:
    """Highest confirmed master baseline incl. post-confirm chain (shared walk).

    Delegates to find_confirmed_baseline: an explicitly pending rollback
    (confirmation: pending, incl. a post-confirm revision sent back for
    re-confirmation) is a chain break — never the expiry baseline; the
    baseline falls back to the lower confirmed root.
    Returns (baseline_version, baseline_file_name, chain_member_names).
    """
    found = find_confirmed_baseline(content_dir)
    if found is None:
        return None
    top, chain = found
    return int(MASTER_RE.match(top.name).group(1)), top.name, set(chain)


def find_outline_baseline_version(content_dir: Path) -> int | None:
    """Highest confirmed outline version of the outline's own series.

    Outlines are never expired against the master baseline version: the two
    series number independently, so a master at v5 with a latest confirmed
    outline at v3 must not flag outline-v3 (cross-series mismatch). The
    master series only judges masters; None means no confirmed outline
    exists and outline expiry is not guessed.
    """
    found = find_confirmed_baseline(content_dir, OUTLINE_RE)
    if found is None:
        return None
    top, _ = found
    return int(OUTLINE_RE.match(top.name).group(1))


def read_head(path: Path, limit: int = 2048) -> str:
    """Best-effort head bytes as text; binary/undecodable files yield ''."""
    try:
        with path.open("rb") as stream:
            return stream.read(limit).decode("utf-8", errors="ignore")
    except OSError:
        return ""


def collect_expired(content_dir: Path, baseline_version: int,
                    chain: set[str], outline_baseline: int | None) -> list[dict]:
    expired: list[dict] = []
    for path in sorted(content_dir.iterdir()):
        m_out = OUTLINE_RE.match(path.name)
        m_mas = MASTER_RE.match(path.name)
        if m_out:
            # Outline series is judged by its own confirmed baseline only;
            # with no confirmed outline, expiry is not guessed.
            if outline_baseline is not None \
                    and int(m_out.group(1)) < outline_baseline:
                expired.append({
                    "file": path.name, "kind": "outline",
                    "version": int(m_out.group(1)),
                    "reason": f"低于大纲基线 v{outline_baseline}"})
        elif m_mas and int(m_mas.group(1)) < baseline_version \
                and path.name not in chain:
            expired.append({
                "file": path.name, "kind": "master",
                "version": int(m_mas.group(1)),
                "reason": f"低于基线 v{baseline_version}"})
    # Non-versioned candidates (style-candidates/, sample-B direction, ...):
    # decided by an explicit `baseline: vM` head mark only, never guessed.
    for path in sorted(content_dir.rglob("*")):
        if not path.is_file() or path.name == EXPIRED_LIST \
                or path.name.endswith(".base-lock.json") \
                or MASTER_RE.match(path.name) or OUTLINE_RE.match(path.name):
            continue
        m = BASELINE_MARK_RE.search(read_head(path))
        if m and int(m.group(1)) < baseline_version:
            expired.append({
                "file": path.relative_to(content_dir).as_posix(),
                "kind": "baseline-marked",
                "baseline_marked": int(m.group(1)),
                "reason": f"baseline v{m.group(1)} 低于基线 v{baseline_version}"})
    return sorted(expired, key=lambda item: item["file"])


def build_manifest(content_dir: Path, baseline_version: int,
                   baseline_file: str, expired: list[dict]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_master": baseline_file,
        "baseline_version": baseline_version,
        "expired": expired,
    }


def render(result: dict, list_mode: bool) -> str:
    lines = [f"基线: {result['baseline_master']}（v{result['baseline_version']}）"]
    expired = result["expired"]
    noun = "过期候选" if not list_mode else "过期候选（--list 只读，未写清单）"
    lines.append(f"{noun}: {len(expired)} 件"
                 + ("" if list_mode else f" → content/{EXPIRED_LIST}"))
    for item in expired:
        lines.append(f"  - {item['file']}（{item['kind']}，{item['reason']}）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="基线 confirmed 后标记过期候选（json 清单，不改原文件）")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--list", action="store_true", help="只查看，不写清单文件")
    parser.add_argument("--json", action="store_true", help="结构化 JSON 输出")
    args = parser.parse_args(argv)

    root = Path(args.project_root).expanduser().resolve()
    content = root / "content"
    if not content.is_dir():
        print(f"content/ 不存在: {content}", file=sys.stderr)
        return EXIT_USAGE

    found = find_baseline(content)
    if found is None:
        print("无 confirmed 基线（含 post-confirm 链）母版：无可对照基线，退出。",
              file=sys.stderr)
        return EXIT_USAGE
    baseline_version, baseline_file, chain = found

    outline_baseline = find_outline_baseline_version(content)
    expired = collect_expired(content, baseline_version, chain, outline_baseline)
    result = build_manifest(content, baseline_version, baseline_file, expired)
    result["actions"] = ["list 模式：未写任何文件"] if args.list \
        else [f"写 {EXPIRED_LIST}"]

    if not args.list:
        (content / EXPIRED_LIST).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    if args.json:
        result["list_mode"] = bool(args.list)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result, args.list))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
