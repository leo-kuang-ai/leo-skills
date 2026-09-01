#!/usr/bin/env python3
"""check_number_ledger.py — 数字登记表合同校验器（v2 九列契约）。

解析 deck 母版文档末尾的 `## 数字登记表` 表格，校验：
  ① 表头与列契约一致——v2（默认）九列
     （数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of）；
     `--schema v1` 兼容旧七列（迁移期，通过即 WARN）；
  ② 每数据行列值全部非空；
  ③ 证据等级 ∈ {引用, 估算, 示意}；
  ④ verified? ∈ {yes, no, open}；`verified?=no` 且 `证据等级=引用` → FAIL；
  ⑤ 行业扩展字段（content_rules 声明的额外列）允许存在，仅要求非空。
不做正文语义匹配（正文数字 ⊆ 登记表的对账随母版机读语法校验器）。

--diff 模式（R-19，TF-1 信息点留存断言；机制来源：shuorenhua SKILL.md §8
Pass 1「信息留存优先——原文每个信息点在输出里都要可追溯，这是硬指标」+
humanizer 复查两问，上游快照 2026-08-31）：对比两版母版登记表——
  ⑥ verified?=yes 的行（按 数值×页×口径 键）在新版消失 → FAIL（exit 1），
     提示 TF-1 减法删数字性证据须显式降级（示意）或经确认，不得静默消失；
  ⑦ 新增行 / 数值变化（同页同口径换数值）/ 行内字段变化 → INFO 如实列出；
     删除非 verified?=yes 的行 → INFO 列出（可见但不阻断）。

用法：python3 check_number_ledger.py <deck-master.md>
      [--schema {v1,v2}] [--industry-fields p,CI,n]
      python3 check_number_ledger.py --diff <old-master.md> <new-master.md>
退出码：0 通过；1 失败（明细写 stderr）；2 仅 WARN（如 --schema v1 迁移提示）
  或用法/解析错误（--diff 模式下文件不可读、旧版登记表节缺失亦为 2；
  新版登记表整体消失时按 ⑥ 判定——旧版存在 verified=yes 行即 FAIL）。
"""
import argparse
import re
import sys

REQUIRED_COLUMNS_V1 = ["数值", "页", "来源", "口径", "期间", "单位", "证据等级"]
REQUIRED_COLUMNS_V2 = REQUIRED_COLUMNS_V1 + ["verified?", "as-of"]
VALID_TIERS = {"引用", "估算", "示意"}
VALID_VERIFIED = {"yes", "no", "open"}


def extract_ledger_lines(text):
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("## 数字登记表"):
            start = i + 1
            break
    if start is None:
        return None, "缺少 '## 数字登记表' 节"
    rows = []
    for ln in lines[start:]:
        s = ln.strip()
        if s.startswith("## "):  # 下一节，登记表结束
            break
        if s.startswith("|"):
            rows.append(s)
    if not rows:
        return None, "登记表节内无表格行"
    return rows, None


def split_row(row):
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    return cells


def parse_ledger_rows(text):
    """Parse the ledger into a list of {column: cell} dicts (lenient: no
    completeness/tier validation — diff mode only needs identity fields)."""
    rows, err = extract_ledger_lines(text)
    if err:
        return None, err
    header = split_row(rows[0])
    data = []
    for row in rows[1:]:
        if re.match(r"^\|[\s:|-]+\|$", row):
            continue
        cells = split_row(row)
        data.append(dict(zip(header, cells)))
    return data, None


def run_diff(old_path, new_path):
    """R-19 --diff mode: TF-1 information-retention assertion.

    verified?=yes rows keyed by (数值, 页, 口径) must not silently disappear
    from the new version. A rewritten value on the same (页, 口径) scope is a
    value change (INFO), not a disappearance; only a fully vacated scope
    counts as lost evidence. New rows and field changes are listed as INFO.
    Exit: 0 no lost verified evidence / 1 verified row lost / 2 parse error
    (only when the OLD master carries no usable ledger to diff against; a NEW
    master whose ledger vanished is the TF-1 extreme case and FAILs when the
    old side had verified=yes rows).
    """
    parsed = []
    for path in (old_path, new_path):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            print(f"ERROR: 无法读取 {path}: {exc}", file=sys.stderr)
            return 2
        rows, err = parse_ledger_rows(text)
        parsed.append((rows, err))
    (old_rows, old_err), (new_rows, new_err) = parsed

    if old_err:
        print(f"ERROR: {old_path}: {old_err}", file=sys.stderr)
        return 2
    if new_err:
        # New master lost the whole ledger section (or emptied the table):
        # every old row is gone. verified=yes rows are lost TF-1 evidence;
        # the rest only merit INFO, matching single-row removal semantics.
        lost = [r for r in old_rows if r.get("verified?", "") == "yes"]
        for r in lost:
            print(f"FAIL: verified?=yes 登记行在新版消失：数值 "
                  f"{r.get('数值', '')} / 页 {r.get('页', '')} / "
                  f"口径 {r.get('口径', '')}——新版{new_err}：登记表整体"
                  "消失，数字性证据须显式降级（示意）或经确认，不得静默删除"
                  "（TF-1）", file=sys.stderr)
        for r in old_rows:
            if r.get("verified?", "") != "yes":
                print(f"INFO: 删除登记行（非 verified?=yes）：数值 "
                      f"{r.get('数值', '')} / 页 {r.get('页', '')} / "
                      f"口径 {r.get('口径', '')}（新版{new_err}）")
        if lost:
            return 1
        print(f"OK: --diff 对账完成（新版{new_err}，旧版无 verified?=yes 行，"
              "无证据损失）")
        return 0

    def key(row):
        return (row.get("数值", ""), row.get("页", ""), row.get("口径", ""))

    def scope(row):
        return (row.get("页", ""), row.get("口径", ""))

    old_by_key = {key(r): r for r in old_rows}
    new_by_key = {key(r): r for r in new_rows}
    old_scopes = {}
    for r in old_rows:
        old_scopes.setdefault(scope(r), []).append(r)
    new_scopes = {}
    for r in new_rows:
        new_scopes.setdefault(scope(r), []).append(r)

    lost, removed_unverified = [], []
    for r in old_rows:
        if key(r) in new_by_key:
            continue
        if r.get("verified?", "") == "yes":
            if not new_scopes.get(scope(r)):
                lost.append(r)          # scope vacated: evidence itself is gone
        else:
            removed_unverified.append(r)

    changed_fields = []
    for k, old_r in old_by_key.items():
        new_r = new_by_key.get(k)
        if not new_r:
            continue
        diffs = [(c, old_r.get(c, ""), new_r.get(c, ""))
                 for c in ("来源", "期间", "单位", "证据等级", "verified?", "as-of")
                 if old_r.get(c, "") != new_r.get(c, "")]
        if diffs:
            changed_fields.append((old_r, diffs))

    added, revalued = [], []
    for r in new_rows:
        if key(r) in old_by_key:
            continue
        (revalued if scope(r) in old_scopes else added).append(r)

    for r in lost:
        print(f"FAIL: verified?=yes 登记行在新版消失：数值 {r.get('数值', '')} / "
              f"页 {r.get('页', '')} / 口径 {r.get('口径', '')}——TF-1 减法删"
              "数字性证据须显式降级（示意）或经确认，不得静默消失",
              file=sys.stderr)
    for r in removed_unverified:
        print(f"INFO: 删除登记行（非 verified?=yes）：数值 {r.get('数值', '')} / "
              f"页 {r.get('页', '')} / 口径 {r.get('口径', '')}")
    for r in added:
        print(f"INFO: 新增登记行：数值 {r.get('数值', '')} / "
              f"页 {r.get('页', '')} / 口径 {r.get('口径', '')}")
    for r in revalued:
        print(f"INFO: 数值变化（页 {r.get('页', '')} / 口径 "
              f"{r.get('口径', '')}）：→ {r.get('数值', '')}")
    for old_r, diffs in changed_fields:
        detail = "，".join(f"{c}: {o}→{n}" for c, o, n in diffs)
        print(f"INFO: 行变化（数值 {old_r.get('数值', '')} / "
              f"页 {old_r.get('页', '')}）：{detail}")

    if lost:
        return 1
    print(f"OK: --diff 对账完成，verified?=yes 证据留存无损失"
          f"（旧 {len(old_rows)} 行 → 新 {len(new_rows)} 行）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master", nargs="?", default=None,
                    help="deck 母版 markdown 路径（--diff 模式下省略）")
    ap.add_argument("--schema", choices=["v1", "v2"], default="v2",
                    help="列契约版本（默认 v2 九列；v1 迁移期兼容，通过即 WARN）")
    ap.add_argument("--industry-fields", default="",
                    help="行业必填扩展列（逗号分隔，如 p,CI,n）")
    ap.add_argument("--diff", nargs=2, default=None, metavar=("OLD", "NEW"),
                    help="对比两版母版登记表（R-19 TF-1 信息点留存断言）："
                         "verified?=yes 行消失即 FAIL")
    args = ap.parse_args()

    if args.diff:
        return run_diff(args.diff[0], args.diff[1])
    if not args.master:
        ap.error("需提供母版路径，或使用 --diff OLD NEW")

    try:
        with open(args.master, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"ERROR: 无法读取 {args.master}: {exc}", file=sys.stderr)
        return 2
    rows, err = extract_ledger_lines(text)
    if err:
        print(f"FAIL: {err}", file=sys.stderr)
        return 1

    base_cols = REQUIRED_COLUMNS_V2 if args.schema == "v2" else REQUIRED_COLUMNS_V1
    header = split_row(rows[0])
    industry = [f.strip() for f in args.industry_fields.split(",") if f.strip()]
    expected = base_cols + industry
    missing_cols = [c for c in expected if c not in header]
    if missing_cols:
        print(f"FAIL: 表头缺列: {', '.join(missing_cols)}", file=sys.stderr)
        return 1

    failures = []
    data_rows = [r for r in rows[1:] if not re.match(r"^\|[\s:-]+\|", r)]
    for idx, row in enumerate(data_rows, start=1):
        cells = split_row(row)
        if len(cells) < len(expected):
            failures.append(f"行{idx}: 列数不足（{len(cells)} < {len(expected)}）")
            continue
        for col, val in zip(expected, cells):
            if not val:
                failures.append(f"行{idx}: 列「{col}」为空")
        tier = cells[base_cols.index("证据等级")]
        if tier and tier not in VALID_TIERS:
            failures.append(f"行{idx}: 证据等级「{tier}」不在 {sorted(VALID_TIERS)}")
        if args.schema == "v2":
            verified = cells[base_cols.index("verified?")]
            if verified and verified not in VALID_VERIFIED:
                failures.append(
                    f"行{idx}: verified?「{verified}」不在 {sorted(VALID_VERIFIED)}")
            if verified == "no" and tier == "引用":
                failures.append(
                    f"行{idx}: verified?=no 且证据等级=引用（核验未过不得上稿，"
                    f"须降级示意并确认）")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    if args.schema == "v1":
        print("WARN: v1 七列契约为迁移期兼容档，请升级 v2 九列"
              "（新增 verified? 与 as-of）后去掉 --schema v1", file=sys.stderr)
        print(f"OK: 数字登记表 {len(data_rows)} 行按 v1 通过（迁移期 WARN）")
        return 2
    print(f"OK: 数字登记表 {len(data_rows)} 行全部通过（v2 九列，含行业扩展列 "
          f"{len(industry)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
