#!/usr/bin/env python3
"""compute_impact.py 单元测试（R-35 影响面自动计算）：
改登记表数字 → 恰含引用页与闭包页 / 可见内容变化 / 双向对称 / 解析失败
exit 2 / 确定性 / JSON 结构 / 数字挪页 / 术语词形变化 / cross-ref 链式
传递闭包 / 登记表行删除 / 无术语表节兼容。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compute_impact.py"

BASE = """# 母版
## S1 封面
argument_role: 开场
- 标题：增长质量是本季主叙事
- 要点 1：三大指标全面向好
视觉行：要点1→巨字卡
- 备注：口播 30 秒

## S2 财务
argument_role: 支柱1
- 标题：营收 1.24 亿元创单季新高
- 要点 1：环比 +18%
视觉行：要点1→KPI 塔
- 备注：引用财报

## S3 展望
argument_role: 支柱2
- 标题：下季度继续提速
- 要点 1：口径详见财务页（见 S2）
视觉行：要点1→结论条
- 备注：衔接

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
"""

GLOSSARY = """
## 术语表
| 术语 | 缩写 | 首现页 |
| --- | --- | --- |
| 净收入留存率 | NRR | S2 |
"""


def run(old, new, extra=()):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as f:
        f.write(old)
        old_path = f.name
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as f:
        f.write(new)
        new_path = f.name
    try:
        r = subprocess.run([sys.executable, str(SCRIPT), old_path, new_path, *extra],
                           capture_output=True, text=True)
    finally:
        Path(old_path).unlink()
        Path(new_path).unlink()
    return r.returncode, r.stdout, r.stderr


def affected(out):
    for ln in out.splitlines():
        if ln.startswith("AFFECTED: "):
            payload = ln[len("AFFECTED: "):].strip()
            return [] if payload == "(none)" else [p.strip() for p in payload.split(",")]
    return None


class ComputeImpactTest(unittest.TestCase):
    def test_number_change_hits_ledger_page_and_crossref_closure(self):
        new = BASE.replace("1.24 亿元", "1.31 亿元")
        code, out, _ = run(BASE, new)
        self.assertEqual(code, 0)
        # S2 直接命中（登记表数字变化），S3 因 cross-ref 引用 S2 纳入闭包
        self.assertEqual(affected(out), ["S2", "S3"])
        self.assertIn("数字登记表:1.31 亿元", out)
        self.assertIn("交叉引用→S2", out)

    def test_pure_copywriting_change_hits_its_page(self):
        new = BASE.replace("下季度继续提速", "下季度增速再上台阶")
        code, out, _ = run(BASE, new)
        self.assertEqual(code, 0)
        self.assertEqual(affected(out), ["S3"])

    def test_impact_is_symmetric_across_direction(self):
        new = BASE.replace("1.24 亿元", "1.31 亿元")
        _, out_fwd, _ = run(BASE, new)
        _, out_bwd, _ = run(new, BASE)
        self.assertEqual(affected(out_fwd), affected(out_bwd))

    def test_identical_files_yield_zero_pages(self):
        code, out, _ = run(BASE, BASE)
        self.assertEqual(code, 0)
        self.assertEqual(affected(out), [])

    def test_missing_file_exits_2(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "/nonexistent-old.md",
             "/nonexistent-new.md"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_pageless_master_exits_2(self):
        code, _, err = run("# 只有标题没有页块\n", BASE)
        self.assertEqual(code, 2)
        self.assertIn("页块", err)

    def test_output_is_deterministic(self):
        new = BASE.replace("1.24 亿元", "1.31 亿元")
        runs = [run(BASE, new)[1] for _ in range(2)]
        self.assertEqual(runs[0], runs[1])

    def test_json_output_has_required_fields(self):
        new = BASE.replace("1.24 亿元", "1.31 亿元")
        code, out, _ = run(BASE, new, ["--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["affected_pages"], ["S2", "S3"])
        self.assertEqual(sorted(data["reasons"]), ["S2", "S3"])
        self.assertIn("1.31 亿元@S2", data["numbers_added"])
        self.assertIn("1.24 亿元@S2", data["numbers_removed"])

    def test_number_moving_pages_hits_both_old_and_new_pages(self):
        new = BASE.replace("| 1.24 亿元 | S2 |", "| 1.24 亿元 | S1 |")
        code, out, _ = run(BASE, new)
        self.assertEqual(code, 0)
        # 旧页（数字被移走）与新页（数字落点）都须重建；S3 闭包仍引用 S2
        self.assertEqual(affected(out), ["S1", "S2", "S3"])

    def test_ledger_row_removal_hits_its_page(self):
        new = BASE.replace(
            "| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |\n",
            "")
        code, out, _ = run(BASE, new)
        self.assertEqual(code, 0)
        self.assertEqual(affected(out), ["S2", "S3"])

    def test_term_wording_change_hits_pages_containing_term(self):
        old = BASE + GLOSSARY
        new = old.replace("净收入留存率", "净收入保持率")
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        # 术语表词形变化：旧词形/新词形出现的页命中（此处母版正文均未提
        # 及该术语，仅登记表节自身命中不算页——期望零页产出证明正文匹配
        # 不误伤登记表节）
        self.assertEqual(affected(out), [])

    def test_term_wording_change_hits_body_pages_when_mentioned(self):
        old = BASE + GLOSSARY
        old = old.replace("- 要点 1：环比 +18%", "- 要点 1：净收入留存率环比 +18%")
        new = old.replace("净收入留存率", "净收入保持率")
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        self.assertIn("S2", affected(out))

    def test_crossref_chain_propagates_transitively(self):
        old = BASE.replace(
            "## 数字登记表",
            "## S4 备忘\nargument_role: 附录\n- 标题：口径备查\n"
            "- 要点 1：同见展望（见 S3）\n视觉行：要点1→备忘条\n- 备注：备查\n\n"
            "## 数字登记表")
        new = old.replace("1.24 亿元", "1.31 亿元")
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        # S2 直接命中 → S3（引用 S2）→ S4（引用 S3）链式闭包
        self.assertEqual(affected(out), ["S2", "S3", "S4"])

    def test_master_without_glossary_section_is_compatible(self):
        # 无 ## 术语表 节的存量母版：解析为空集，不报错
        code, out, _ = run(BASE, BASE.replace("提速", "扩张"))
        self.assertEqual(code, 0)
        self.assertEqual(affected(out), ["S3"])

    def test_assertion_reversal_propagates_without_numbers(self):
        old = BASE.replace("营收 1.24 亿元创单季新高", "继续投资")
        code, out, _ = run(old, old.replace("继续投资", "停止投资"))
        self.assertEqual(code, 0)
        self.assertEqual(affected(out), ["S2", "S3"])

    def test_visible_and_unknown_page_fields_are_conservative(self):
        for old, new in (("环比 +18%", "环比 -18%"),
                         ("要点1→KPI 塔", "要点1→趋势图"),
                         ("argument_role: 支柱1", "argument_role: 证据"),
                         ("## S2 财务", "## S2 投资"),
                         ("备注：引用财报", "备注：speaker_script: 新讲稿"),
                         ("备注：引用财报", "备注：engineering: 新参数")):
            with self.subTest(new=new):
                code, out, _ = run(BASE, BASE.replace(old, new))
                self.assertEqual(code, 0)
                self.assertEqual(affected(out), ["S2", "S3"])

    def test_added_and_removed_pages_are_explicit(self):
        new = BASE + "\n## S4 新页\n- 标题：新行动\n"
        _, out, _ = run(BASE, new, ["--json"])
        data = json.loads(out)
        self.assertEqual(data["affected_pages"], ["S4"])
        self.assertEqual(data["added_pages"], ["S4"])
        _, out, _ = run(new, BASE, ["--json"])
        data = json.loads(out)
        self.assertEqual(data["affected_pages"], ["S4"])
        self.assertEqual(data["removed_pages"], ["S4"])

    def test_deleted_target_propagates_to_surviving_reference(self):
        start = BASE.index("## S2")
        end = BASE.index("## S3")
        new = BASE[:start] + BASE[end:]
        _, out, _ = run(BASE, new, ["--json"])
        data = json.loads(out)
        self.assertEqual(data["affected_pages"], ["S2", "S3"])
        self.assertIn("交叉引用→S2", data["reasons"]["S3"])

    def test_page_order_changes_rebuild_moved_pages(self):
        s2, s3, ledger = (BASE.index(marker) for marker in
                          ("## S2", "## S3", "## 数字登记表"))
        new = BASE[:s2] + BASE[s3:ledger] + BASE[s2:s3] + BASE[ledger:]
        _, out, _ = run(BASE, new)
        self.assertEqual(affected(out), ["S2", "S3"])
        self.assertIn("页序变化", out)

    def test_global_unknown_change_affects_all_pages(self):
        _, out, _ = run(BASE, BASE.replace("# 母版", "# 母版\n受众：董事会"))
        self.assertEqual(affected(out), ["S1", "S2", "S3"])

    def test_ledger_scope_change_without_number_change_is_affected(self):
        _, out, _ = run(BASE, BASE.replace("| 合并 |", "| 母公司 |"))
        self.assertEqual(affected(out), ["S2", "S3"])

    def test_duplicate_page_ids_fail_instead_of_overwriting(self):
        code, _, err = run(BASE, BASE + "\n## S2 重复\n")
        self.assertEqual(code, 2)
        self.assertIn("重复页标识", err)


if __name__ == "__main__":
    unittest.main()
