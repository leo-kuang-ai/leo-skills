#!/usr/bin/env python3
"""check_cross_page_consistency.py 单元测试（R-40 长 deck 术语漂移硬门禁）：
>30 页同实体异写 FAIL / ≤30 页降风险（向后兼容）/ 编号跳号 / 固定件冲突 /
四分类输出 / 无术语表兼容 / exit 语义 / 确定性 / --threshold 覆盖 /
拉丁缩写边界防误报 / 附录页不参与编号核对 / 术语表内同实体异写 /
承诺状态复用 deck-promises。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
          / "check_cross_page_consistency.py")


def page(n, point="常规要点内容", fixed=None):
    lines = [
        f"## S{n} 第{n}页",
        "argument_role: 支柱",
        f"- 标题：第{n}页的结论句完整断言",
        f"- 要点 1：{point}",
        "视觉行：要点1→结论条"
        + (f"；固定件：{fixed}" if fixed else ""),
        "- 备注：口播 30 秒",
    ]
    return "\n".join(lines)


GLOSSARY = """
## 术语表
| 术语 | 缩写 | 首现页 |
| --- | --- | --- |
| 净收入留存率 | NRR | S1 |
"""

PROMISES = """deck-promises:
  | 承诺 | 锚页 | 兑现页 | 状态 |
  | --- | --- | --- | --- |
  | 方法章将给出消融实验 | S1 | S2 | open |
  | 附录给出数据字典 | S1 | — | closed |
"""


def build_master(nums, glossary="", promises="", points=None, fixed=None):
    """Assemble a master from page numbers with optional extras."""
    parts = ["# 母版"]
    for n in nums:
        point = (points or {}).get(n, "常规要点内容")
        fx = (fixed or {}).get(n)
        parts.append(page(n, point=point, fixed=fx))
    if glossary:
        parts.append(glossary.rstrip())
    text = "\n\n".join(parts) + "\n"
    if promises:
        text = promises + "\n" + text
    return text


def run(text, extra=()):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        path = f.name
    r = subprocess.run([sys.executable, str(SCRIPT), path, *extra],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


class CrossPageConsistencyTest(unittest.TestCase):
    def test_variant_over_30_pages_blocks_with_exit_1(self):
        nums = list(range(1, 32))  # 31 pages: over the default threshold
        points = {5: "净收入 留存率环比 +18%"}
        code, out, _ = run(build_master(nums, glossary=GLOSSARY,
                                        points=points))
        self.assertEqual(code, 1)
        self.assertIn("mode=block", out)
        self.assertIn("[阻断] S5：「净收入 留存率」是表内术语"
                      "「净收入留存率」的变体", out)
        self.assertIn("exit=1", out)

    def test_variant_at_or_below_30_pages_downgrades_to_risk(self):
        nums = list(range(1, 31))  # 30 pages: at threshold, report mode
        points = {5: "净收入 留存率环比 +18%"}
        code, out, _ = run(build_master(nums, glossary=GLOSSARY,
                                        points=points))
        self.assertEqual(code, 0)
        self.assertIn("mode=report", out)
        self.assertIn("[风险] （阻断降级：页数 ≤ 阈值）S5", out)
        self.assertIn("[阻断] （无）", out)

    def test_fullwidth_abbr_variant_is_detected(self):
        nums = list(range(1, 32))
        points = {7: "ＮＲＲ 连续三季改善"}
        code, out, _ = run(build_master(nums, glossary=GLOSSARY,
                                        points=points))
        self.assertEqual(code, 1)
        self.assertIn("「ＮＲＲ」是表内术语「NRR」的变体", out)

    def test_numbering_skip_blocks_when_over_threshold(self):
        nums = list(range(1, 7)) + list(range(8, 33))  # S7 missing, 31 pages
        code, out, _ = run(build_master(nums))
        self.assertEqual(code, 1)
        self.assertIn("页码跳号：S7 缺失（现有最大页号 S32）", out)

    def test_duplicate_page_number_is_reported(self):
        nums = list(range(1, 31)) + [30]  # 31 pages with S30 twice
        code, out, _ = run(build_master(nums))
        self.assertEqual(code, 1)
        self.assertIn("页码重复：S30 出现 2 次", out)

    def test_fixed_element_conflict_blocks(self):
        nums = list(range(1, 32))
        fixed = {2: "页码：右下 12pt", 9: "页码：左下 12pt；页脚：公司名"}
        code, out, _ = run(build_master(nums, fixed=fixed))
        self.assertEqual(code, 1)
        self.assertIn("[阻断] 固定件声明冲突（页码）：「右下12pt」@S2；"
                      "「左下12pt」@S9", out)

    def test_four_category_lines_always_present(self):
        nums = list(range(1, 11))
        fixed = {3: "版面常量见合同"}  # unparseable fixed line -> risk
        code, out, _ = run(build_master(nums, glossary=GLOSSARY,
                                        promises=PROMISES, fixed=fixed))
        self.assertEqual(code, 0)
        for marker in ("[阻断]", "[风险]", "[承诺状态]", "[通过]"):
            self.assertIn(marker, out)
        self.assertIn("固定件声明无法解析", out)
        self.assertIn("「方法章将给出消融实验」：open（锚页 S1，兑现页 S2）", out)
        self.assertIn("术语一致性：通过（术语表 1 条，正文无同实体异写变体）", out)

    def test_master_without_glossary_is_compatible(self):
        code, out, _ = run(build_master(list(range(1, 31))))
        self.assertEqual(code, 0)
        self.assertIn("术语一致性：跳过（母版无 ## 术语表 节，向后兼容）", out)

    def test_exit_semantics_usage_and_parse_errors(self):
        r = subprocess.run([sys.executable, str(SCRIPT),
                            "/nonexistent-master.md"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        code, _, err = run("# 只有标题没有页块\n")
        self.assertEqual(code, 2)
        self.assertIn("页块", err)

    def test_output_is_deterministic(self):
        nums = list(range(1, 32))
        points = {5: "净收入 留存率环比 +18%"}
        fixed = {2: "页码：右下 12pt", 9: "页码：左下 12pt"}
        text = build_master(nums, glossary=GLOSSARY, points=points,
                            fixed=fixed)
        runs = [run(text)[1] for _ in range(2)]
        self.assertEqual(runs[0], runs[1])

    def test_threshold_flag_overrides_block_mode(self):
        nums = list(range(1, 32))
        points = {5: "净收入 留存率环比 +18%"}
        text = build_master(nums, glossary=GLOSSARY, points=points)
        code, out, _ = run(text, ["--threshold", "40"])
        self.assertEqual(code, 0)
        self.assertIn("threshold=40 mode=report", out)
        self.assertIn("[风险] （阻断降级：页数 ≤ 阈值）", out)

    def test_latin_abbr_glued_into_longer_word_not_flagged(self):
        glossary = """
## 术语表
| 术语 | 缩写 | 首现页 |
| --- | --- | --- |
| 人工智能 | AI | S1 |
"""
        nums = list(range(1, 31))  # "ai" inside "said": glued, not a variant
        points = {4: "团队 said 改善了口径"}
        code, out, _ = run(build_master(nums, glossary=glossary,
                                        points=points))
        self.assertEqual(code, 0)
        self.assertIn("术语一致性：通过", out)

    def test_appendix_page_counts_but_skips_numbering_check(self):
        text = (build_master([1, 2, 3])
                + "\n## 附 数据字典\nargument_role: 附录\n"
                  "- 标题：口径备查\n- 要点 1：备查条目\n"
                  "视觉行：要点1→备忘条\n- 备注：备查\n")
        code, out, _ = run(text)
        self.assertEqual(code, 0)
        self.assertIn("pages=4", out)
        self.assertIn("页码连续性：通过（4 页编号连续，无跳号/重复）", out)

    def test_glossary_internal_duplicate_term_is_blocked(self):
        glossary = """
## 术语表
| 术语 | 缩写 | 首现页 |
| --- | --- | --- |
| 净收入留存率 | NRR | S1 |
| 净收入 留存率 | NRR | S9 |
"""
        code, out, _ = run(build_master(list(range(1, 32)),
                                        glossary=glossary))
        self.assertEqual(code, 1)
        self.assertIn("[阻断] 术语表内同实体异写：净收入 留存率 / 净收入留存率",
                      out)

    def test_invalid_promise_status_is_risk_not_exit(self):
        promises = """deck-promises:
  | 承诺 | 锚页 | 兑现页 | 状态 |
  | --- | --- | --- | --- |
  | 方法章将给出消融实验 | S1 | S2 | pending |
"""
        code, out, _ = run(build_master(list(range(1, 31)),
                                        promises=promises))
        self.assertEqual(code, 0)
        self.assertIn("[风险] deck-promises「方法章将给出消融实验」：状态"
                      "「pending」不在封闭枚举", out)


if __name__ == "__main__":
    unittest.main()
