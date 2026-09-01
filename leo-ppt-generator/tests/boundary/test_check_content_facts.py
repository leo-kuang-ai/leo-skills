#!/usr/bin/env python3
"""check_content_facts.py 单元测试（R-06 内容核查官）：数字命中含格式容忍
（千分位/百分号空格/万·亿换算/千分号/百分之）、未命中差异清单与
re-run-after-fix 说明、无数字母版、材料/母版缺失 exit 2、估算/示意/用户确认
标注豁免、标题断言抽取、交叉引用与机器标记不计数字、多材料并集、--json
机读、确定性。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_content_facts.py"

MASTER = """# 母版
## S1 封面
argument_role: 开场
- 标题：营收 1.24 亿元创单季新高
- 要点 1：环比 +18%（见第 2 页）
视觉行：要点1→巨字卡
- 备注：口播 30 秒

## S2 财务
argument_role: 支柱1
- 标题：利润率回到健康区间
- 要点 1：环比增速 18 %
视觉行：要点1→KPI 塔
- 备注：引用财报

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 |
"""

MATERIAL = """2026Q3 财报摘要
营收 12,400 万元，去年同期 1.05 亿元；环比增速 18%。
"""


def write_tmp(content, suffix=".md"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False,
                                    encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


def run(master_content, material_contents, extra=()):
    master = write_tmp(master_content)
    materials = [write_tmp(c) for c in material_contents]
    r = subprocess.run([sys.executable, str(SCRIPT), master, *materials, *extra],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


class ContentFactsTest(unittest.TestCase):
    def test_number_hit_with_format_tolerances_passes(self):
        # 1.24亿 ↔ 12,400万（万·亿换算）、18% ↔ 18 %（空格）双容忍
        code, out, err = run(MASTER, [MATERIAL])
        self.assertEqual(code, 0, err)
        self.assertIn("PASS: 全部数字断言均可在材料中回读", out)
        self.assertIn("numbers=3", out)

    def test_thousand_separator_tolerance_passes(self):
        master = MASTER.replace("1.24 亿元", "12,400 万元")
        code, out, _ = run(master, [MATERIAL])
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_cn_percent_word_tolerance_passes(self):
        master = MASTER.replace("环比 +18%", "市占 25%")
        material = "百分之25 的用户选择本产品；营收 12,400 万元；环比增速 18%。\n"
        code, out, _ = run(master, [material])
        self.assertEqual(code, 0, out)

    def test_permille_tolerance_passes(self):
        master = MASTER.replace("环比 +18%", "坏账率 0.5%")
        material = "营收 12,400 万元；环比增速 18%；坏账率 5‰。\n"
        code, out, _ = run(master, [material])
        self.assertEqual(code, 0, out)

    def test_untraceable_number_fails_with_diff_list(self):
        master = MASTER.replace("1.24 亿元", "1.35 亿元")
        code, out, _ = run(master, [MATERIAL])
        self.assertEqual(code, 1)
        self.assertIn("DIFF: 1 个数字未在材料中回读到", out)
        self.assertIn("1.35亿", out)
        self.assertIn("RE-RUN-AFTER-FIX", out)
        self.assertIn("有界 2 轮", out)

    def test_title_assertion_number_is_checked(self):
        # 标题行数字同样是断言：材料缺失即差异
        material = MATERIAL.replace("环比增速 18%。", "")
        code, out, _ = run(MASTER.replace("利润率回到健康区间",
                                          "利润率 22% 回到健康区间"),
                           [material])
        self.assertEqual(code, 1)
        self.assertIn("22%", out)

    def test_master_without_numbers_passes(self):
        master = MASTER.replace("1.24 亿元", "创新高").replace("+18%", "高增")
        master = master.replace("18 %", "高增")
        code, out, _ = run(master, [MATERIAL])
        self.assertEqual(code, 0, out)
        self.assertIn("numbers=0", out)

    def test_missing_material_file_exits_2(self):
        master = write_tmp(MASTER)
        r = subprocess.run([sys.executable, str(SCRIPT), master,
                            "/nonexistent/material.md"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("材料文件不存在", r.stderr)

    def test_missing_master_file_exits_2(self):
        material = write_tmp(MATERIAL)
        r = subprocess.run([sys.executable, str(SCRIPT),
                            "/nonexistent/master.md", material],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("母版文件不存在", r.stderr)

    def test_master_without_page_blocks_exits_2(self):
        # A page-less master is an unusable input, not a clean zero-number PASS.
        material = write_tmp(MATERIAL)
        r = subprocess.run(
            [sys.executable, str(SCRIPT), write_tmp("没有分页的母版\n"),
             material], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("母版解析失败", r.stderr)
        self.assertIn("未发现任何页", r.stderr)

    def test_year_like_title_number_is_exempt(self):
        # "2026 年市场回顾": bare 19xx/20xx without unit/percent suffix reads
        # as a year — no material traceability required (family-i parity).
        master = MASTER.replace("营收 1.24 亿元创单季新高", "2026 年市场回顾")
        code, out, _ = run(master, [MATERIAL])
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_year_like_number_with_unit_still_checked(self):
        # A unit suffix defeats the year exemption: 2026 万 is a metric.
        master = MASTER.replace("营收 1.24 亿元创单季新高", "盘子 2026 万元起")
        code, out, _ = run(master, [MATERIAL])
        self.assertEqual(code, 1)
        self.assertIn("DIFF: 1 个数字", out)
        self.assertIn("2026万", out)

    def test_year_like_percent_number_still_checked(self):
        master = MASTER.replace("营收 1.24 亿元创单季新高", "增长 1926% 之说")
        code, out, _ = run(master, [MATERIAL])
        self.assertEqual(code, 1)
        self.assertIn("DIFF: 1 个数字", out)
        self.assertIn("1926%", out)

    def test_tier_marked_bullets_are_exempt(self):
        master = MASTER.replace(
            "环比 +18%（见第 2 页）",
            "明年目标 2 亿元（用户确认）round:3")
        master = master.replace(
            "环比增速 18 %",
            "利润 3,500 万元（估算）")
        master = master.replace(
            "营收 1.24 亿元创单季新高",
            "行业空间十倍（示意）")
        code, out, _ = run(master, [MATERIAL])
        self.assertEqual(code, 0, out)
        self.assertIn("tier_exempt=3", out)

    def test_crossref_and_metadata_digits_are_not_counted(self):
        master = """# 母版
## S1 封面
argument_role: 开场
- 标题：全量口径已核对
- 要点 1：口径细节见第 9 页 [src:附录B]
- 要点 2：母版版本 v2.5 已冻结【引用|src:S3脚注】
视觉行：要点1→巨字卡；要点2→对照表
- 备注：口播 30 秒

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 无 | S1 | — | — | — | — | 示意 |
"""
        code, out, _ = run(master, ["（空材料）\n"])
        self.assertEqual(code, 0, out)
        self.assertIn("numbers=0", out)

    def test_multiple_materials_union_passes(self):
        material_a = "营收规模见另一份文件。\n"
        material_b = "本季营收 12400 万元；环比增速 18%。\n"
        code, out, _ = run(MASTER, [material_a, material_b])
        self.assertEqual(code, 0, out)

    def test_json_output_is_structured(self):
        master = MASTER.replace("1.24 亿元", "1.35 亿元")
        code, out, _ = run(master, [MATERIAL], extra=["--json"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(payload["bounded_rounds"], 2)
        self.assertEqual(len(payload["diffs"]), 1)
        self.assertEqual(payload["diffs"][0]["value"], "1.35亿")
        self.assertIn("page", payload["diffs"][0])
        self.assertIn("re_run_after_fix", payload)

    def test_json_clean_run_has_empty_diffs(self):
        code, out, _ = run(MASTER, [MATERIAL], extra=["--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["diffs"], [])
        self.assertEqual(payload["numbers"], 3)

    def test_output_is_deterministic(self):
        master = write_tmp(MASTER.replace("+18%", "+19%"))
        material = write_tmp(MATERIAL)
        runs = [subprocess.run([sys.executable, str(SCRIPT), master, material],
                               capture_output=True, text=True)
                for _ in range(2)]
        self.assertEqual(
            (runs[0].returncode, runs[0].stdout, runs[0].stderr),
            (runs[1].returncode, runs[1].stdout, runs[1].stderr))


if __name__ == "__main__":
    unittest.main()
