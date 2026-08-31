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

用法：python3 check_number_ledger.py <deck-master.md>
      [--schema {v1,v2}] [--industry-fields p,CI,n]
退出码：0 通过；1 失败（明细写 stderr）；2 仅 WARN（如 --schema v1 迁移提示）。
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master", help="deck 母版 markdown 路径")
    ap.add_argument("--schema", choices=["v1", "v2"], default="v2",
                    help="列契约版本（默认 v2 九列；v1 迁移期兼容，通过即 WARN）")
    ap.add_argument("--industry-fields", default="",
                    help="行业必填扩展列（逗号分隔，如 p,CI,n）")
    args = ap.parse_args()

    text = open(args.master, encoding="utf-8").read()
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
    data_rows = [r for r in rows[1:] if not re.match(r"^\|[\s:-]+\|", r.replace("-", "-"))]
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
