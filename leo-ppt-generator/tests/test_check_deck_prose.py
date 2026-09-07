#!/usr/bin/env python3
"""check_deck_prose.py 单测：R-15 六族检测正反例 + 豁免路径（行业词豁免 /
孤立放行 / 论证骨架豁免）+ 确定性双跑 + exit 语义（0 干净 / 1 翻案腔超限 /
2 用法或解析错误）+ R-16 讲稿纪律（套话 / 长句 / 「大家」人称）。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_deck_prose.py"


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )


def _master(tmp, text, name="deck-master-v1.md"):
    path = Path(tmp) / name
    path.write_text(text, encoding="utf-8")
    return path


CLEAN_DECK = """# 逐页母版 v1 — 测试

## S1 封面
- 角色：开场
- 标题：测试方案概览
- speaker_script：各位好，今天讲测试方案。

## S2 方法
- 标题：先做容量预检再批量出图
- 要点：
  - 容量预检把超页挡在母版层
  - 版式库给出每个版式的上限
- speaker_script：方法一句话：先预检，后出图。
"""


class CleanDeckTest(unittest.TestCase):
    def test_clean_deck_exits_0_without_warn_or_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, CLEAN_DECK)])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DECK-PROSE:", result.stdout)
        self.assertIn("PAGES: 2 页（内容页 1 / 功能页 1）", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)


class ReversalTest(unittest.TestCase):
    def test_two_counted_hits_fail_with_exit_1(self):
        master = """## S1 对比
- 标题：不是工具问题，而是流程问题
- 要点：
  - 不是成本高，而是预算没锁
  - 复核登记表后重建
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("[FAIL]", result.stdout)
        self.assertIn("翻案腔计 2 处，超过 deck 级上限 1", result.stdout)

    def test_isolated_hit_on_short_page_is_not_counted(self):
        master = """## S1 疑问
- 标题：看似简单，其实复杂
- 要点：
  - 预检失败时降档
  - 降档不缩字号
- speaker_script：先预检，后出图。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("孤立翻案腔命中不计（要点 ≤3 的页）", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_single_counted_hit_warns_for_skeleton_note(self):
        master = """## S1 台账
- 标题：真正的杠杆是复利
- 要点：
  - 行一
  - 行二
  - 行三
  - 行四
- speaker_script：结论先说。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("[WARN]", result.stdout)
        self.assertIn("须为真实论证骨架", result.stdout)
        self.assertIn("（豁免：论证骨架）", result.stdout)

    def test_exemption_marker_on_hit_line_clears_finding(self):
        master = """## S1 台账
- 标题：真正的杠杆是复利（豁免：论证骨架）
- 要点：
  - 行一
  - 行二
  - 行三
  - 行四
- speaker_script：结论先说。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("已豁免注明", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)


class JargonTest(unittest.TestCase):
    def test_jargon_word_flags_warn(self):
        master = """## S1 方案
- 标题：为新功能赋能
- 要点：
  - 复核登记表后重建
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("[WARN]", result.stdout)
        self.assertIn("黑话「赋能」出现 1 次", result.stdout)

    def test_same_page_three_occurrences_exempt_as_industry_term(self):
        master = """## S1 交付
- 标题：交付闭环
- 要点：
  - 复核闭环自动运行
  - 闭环之外不阻断
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("按行业既定词豁免", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_allow_flag_exempts_word(self):
        master = """## S1 方案
- 标题：为新功能赋能
- 要点：
  - 复核登记表后重建
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master), "--allow", "赋能"])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("黑话「赋能」", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)


class AiFlavorTest(unittest.TestCase):
    def test_banned_phrase_in_title_flags_warn(self):
        master = """## S1 方案
- 标题：Dive into the new pipeline
- 要点：
  - 复核登记表后重建
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("AI 腔英文套话「dive into」", result.stdout)

    def test_journey_in_point_flags_warn_but_quoted_span_exempt(self):
        master = """## S1 方案
- 标题：客户路径总览
- 要点：
  - 按「Customer Journey Map」四阶段拆解
  - 这一 journey 覆盖购后环节
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("AI 腔英文套话「journey」", result.stdout)

    def test_allow_flag_exempts_phrase(self):
        master = """## S1 方案
- 标题：Explore the trade-offs
- 要点：
  - 复核登记表后重建
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master), "--allow", "explore"])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("AI 腔英文套话", result.stdout)

    def test_ordinary_english_does_not_flag(self):
        master = """## S1 方案
- 标题：容量预检与批量出图
- 要点：
  - exploration logs 归档在交付目录
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("AI 腔英文套话", result.stdout)


class NominalizationTest(unittest.TestCase):
    def test_light_verb_plus_deverbal_noun_warns(self):
        master = """## S1 动作
- 标题：母版层修复最便宜
- 要点：
  - 对流程进行了优化
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("名词化「进行了优化」", result.stdout)


class IsomorphicTest(unittest.TestCase):
    def test_three_consecutive_same_opening_prefix_warns(self):
        master = """## S1 步骤
- 标题：容量预检先行
- 要点：
  - 通过预检挡住超页
- speaker_script：先说结论。

## S2 步骤
- 标题：版式库定上限
- 要点：
  - 通过版式库查上限
- speaker_script：先说结论。

## S3 步骤
- 标题：降档保字号
- 要点：
  - 通过降档保住字号
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("连续 3 页第一条要点同构开头「通过…」", result.stdout)

    def test_two_pages_only_never_flags_isomorphic(self):
        master = """## S1 步骤
- 标题：容量预检先行
- 要点：
  - 通过预检挡住超页
- speaker_script：先说结论。

## S2 步骤
- 标题：版式库定上限
- 要点：
  - 通过版式库查上限
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("同构开头", result.stdout)


class ConnectiveTest(unittest.TestCase):
    def test_dense_connectives_on_short_page_warn(self):
        master = """## S1 对账
- 标题：然而成本超了
- 要点：
  - 因此要降档
  - 同时保住字号
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("连词 3 处", result.stdout)
        self.assertIn("处/千字", result.stdout)

    def test_isolated_single_connective_not_flagged(self):
        master = """## S1 对账
- 标题：成本超了，然而可降档
- 要点：
  - 降档不缩字号
  - 复核登记表
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("连词", result.stdout)

    def test_single_long_connective_not_double_counted(self):
        # 「与此同时」 contains 「同时」: one occurrence must count once, so a
        # lone long connective stays below CONNECTIVE_MIN_HITS and never flags.
        master = """## S1 对账
- 标题：与此同时口径不变
- 要点：
  - 降档不缩字号
  - 复核登记表
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("连词", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_long_connective_plus_distinct_one_counts_two_not_three(self):
        # 与此同时 + 因此 = 2 real hits (not 3 via the 同时 overlap).
        master = """## S1 对账
- 标题：与此同时成本上升
- 要点：
  - 因此要降档
  - 复核登记表
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("连词 2 处", result.stdout)
        self.assertNotIn("连词 3 处", result.stdout)


class FormatTest(unittest.TestCase):
    def test_cjk_latin_missing_space_warns(self):
        master = """## S1 收益
- 标题：收益测算
- 要点：
  - 提升ROI空间
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("格式[中英空格]", result.stdout)

    def test_halfwidth_punct_in_cjk_context_warns(self):
        master = """## S1 流程
- 标题：两步走
- 要点：
  - 先复核,再开工
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("格式[全角标点]", result.stdout)

    def test_bare_number_intensifier_and_unit_spacing_warn(self):
        master = """## S1 数据
- 标题：命中统计
- 要点：
  - 多达30处命中
  - 100ms内出首帧
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("格式[数字裸用]", result.stdout)
        self.assertIn("格式[数字单位]", result.stdout)


class EvidenceSpanMaskTest(unittest.TestCase):
    """合同规定的四级标注跨度不是版面文案——格式族须先掩蔽再扫描。"""

    def test_source_ref_tag_not_flagged_as_halfwidth_punct(self):
        master = """## S1 证据
- 标题：成本对账
- 要点：
  - 存储成本环比上行【引用|src:财务部】
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("格式[", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_user_confirm_round_tag_not_flagged(self):
        master = """## S1 决策
- 标题：口径确认
- 要点：
  - 分配比例按预算基数【用户确认|round:3】
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("格式[", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_unknown_and_estimate_tags_masked_too(self):
        master = """## S1 缺口
- 标题：缺口登记
- 要点：
  - 归因待回访【unknown】
  - 节省区间为经验值【估算】
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("格式[", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_halfwidth_punct_outside_annotation_still_warns(self):
        master = """## S1 流程
- 标题：口径复核
- 要点：
  - 口径见【引用|src:附录A】,已核对
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("格式[全角标点]", result.stdout)


class MetadataBulletTest(unittest.TestCase):
    """页面级元信息写成 bullet 时不得被当作要点（防同构/金句族误报）。"""

    def test_bulleted_page_metadata_not_read_as_points(self):
        # 若元信息被解析为第一条要点，三页的「页面…」开头会触发同构 WARN。
        master = """## S1 证据
- 页面角色：证据
- argument_role：论据
- beat：张力
- audience_takeaway：信任
- rst_relation：elaboration
- 标题：证据一
- 要点：
  - 通过登记表核对数字
- speaker_script：先说结论。

## S2 证据
- 页面角色：证据
- argument_role：论据
- 标题：证据二
- 要点：
  - 台账复核 37 项口径
- speaker_script：先说结论。

## S3 证据
- 页面角色：证据
- argument_role：论据
- 标题：证据三
- 要点：
  - 对账闭合后断链为零
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("同构开头", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)


class SpeakerDisciplineTest(unittest.TestCase):
    def test_opening_and_closing_cliches_warn(self):
        master = """## S1 方法
- 标题：方法两步走
- 要点：
  - 先预检后出图
- speaker_script：接下来我将介绍方法。综上所述，先看结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("讲稿套话「接下来我将」", result.stdout)
        self.assertIn("讲稿套话「综上所述」", result.stdout)

    def test_overlong_sentence_warns(self):
        long_line = "这条讲稿句子故意写得很长很长并且明显超过四十个字的上限以便触发长句警告测试用例现在足够长了"
        master = f"""## S1 方法
- 标题：方法两步走
- 要点：
  - 先预检后出图
- speaker_script：{long_line}。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("长句", result.stdout)
        self.assertIn("拆成短句口语", result.stdout)

    def test_dajia_notice_persona_warns_but_greeting_exempt(self):
        master = """## S1 方法
- 标题：方法两步走
- 要点：
  - 先预检后出图
- speaker_script：大家好。大家可以看这页。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("「大家」×1——通知腔", result.stdout)
        self.assertIn("「大家好」问候不计", result.stdout)


class CliSemanticsTest(unittest.TestCase):
    def test_no_arguments_exits_2(self):
        result = _run([])
        self.assertEqual(result.returncode, 2)

    def test_missing_file_exits_2(self):
        result = _run([Path(tempfile.gettempdir()) / "no-such-master.md"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("ERROR", result.stderr)

    def test_master_without_page_headings_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, "没有分页的母版\n")])
        self.assertEqual(result.returncode, 2)
        self.assertIn("母版解析失败", result.stderr)

    def test_deterministic_stdout_across_runs(self):
        master = CLEAN_DECK.replace(
            "- 标题：先做容量预检再批量出图",
            "- 标题：不是工具问题，而是流程问题")
        with tempfile.TemporaryDirectory() as tmp:
            path = _master(tmp, master)
            first = _run([path])
            second = _run([path])
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.returncode, second.returncode)

    def test_json_output_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, CLEAN_DECK), "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        for key in ("file", "pages", "exit", "counts", "findings"):
            self.assertIn(key, payload)
        self.assertEqual(payload["pages"], {"total": 2, "content": 1,
                                            "functional": 1})
        self.assertEqual(payload["exit"], 0)

    def test_p_heading_convention_is_accepted(self):
        master = """## P1 方法
- 标题：方法两步走
- 要点：
  - 先预检后出图
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master), "--json"])
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["pages"]["total"], 1)
        # Jargon hit makes the page label visible in the human report too.
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master.replace("方法两步走", "为新功能赋能"))])
        self.assertIn("P1 方法", result.stdout)


class DictionDisciplineTest(unittest.TestCase):
    """R-17 family h: narrator openers / notice persona / intensifier stacking."""

    def test_narrator_opener_at_point_start_warns(self):
        master = """## S1 结论
- 标题：留存率是硬指标
- 要点：
  - 这说明改写没有丢事实
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("要点以「这说明」开头", result.stdout)
        self.assertIn("要点是断言不是讲解", result.stdout)

    def test_narrator_connective_mid_point_is_not_flagged(self):
        master = """## S1 结论
- 标题：留存率达标
- 要点：
  - 改写后原文数字仍可找回，留存有据
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("要点以「", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_dajia_in_point_warns_notice_tone(self):
        master = """## S1 数据
- 标题：口径先讲清
- 要点：
  - 大家一起看这组数字
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("要点含「大家」——通知腔人称", result.stdout)
        self.assertNotIn("金句/氛围页加重", result.stdout)

    def test_dajia_in_quote_page_message_aggravated(self):
        master = """## S1 金句
- 标题：质量是护城河
- 要点：
  - 大家记住这一条
- speaker_script：收束一句。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("要点含「大家」——通知腔人称", result.stdout)
        self.assertIn("金句/氛围页加重", result.stdout)

    def test_intensifier_stacking_two_same_page_warns(self):
        master = """## S1 发现
- 标题：两个强断言
- 要点：
  - 非常关键的发现
  - 十分严格的口径
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("强度副词+形容词 ×2", result.stdout)
        self.assertIn("形容词堆砌", result.stdout)

    def test_single_intensifier_not_flagged(self):
        master = """## S1 发现
- 标题：单一修饰不计
- 要点：
  - 非常关键的发现
  - 口径写进登记表
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("强度副词", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)


LEDGER_DECK = """# 母版
## S1 证据
- 标题：营收增长 55%
- speaker_script：先说结论。

## S2 年度
- 标题：2026 年度新签 37 家
- speaker_script：一句话。

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 55% | S1 | Q3 财报 | 合并报告期 | 2026Q3 | % | 引用 | yes | 2026-10-28 |
| 37 家 | S2 | CRM 导出 | 新签口径 | 2026Q3 | 家 | 引用 | yes | 2026-10-28 |
"""


class TitleLedgerTest(unittest.TestCase):
    """R-18 family i: title numbers vs per-page ledger value sets."""

    def test_title_number_covered_by_ledger_no_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, LEDGER_DECK)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("标题数字", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_title_number_missing_from_ledger_warns(self):
        master = LEDGER_DECK.replace("营收增长 55%", "营收增长 61%")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("[WARN] S1 证据 标题：标题数字「61%」不在本页（S1）"
                      "登记表数值中", result.stdout)
        self.assertIn("回母版对账，或补登记行", result.stdout)

    def test_number_registered_on_other_page_still_warns(self):
        # 37 家 exists in the ledger but on S5; title of S2 is not covered.
        master = LEDGER_DECK.replace("| 37 家 | S2 |", "| 37 家 | S5 |")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertIn("标题数字「37」不在本页（S2）登记表数值中", result.stdout)

    def test_master_without_ledger_skips_family_with_info(self):
        master = """## S1 证据
- 标题：覆盖 37 家门店
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("母版无数字登记表，标题兑现对账跳过", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_year_like_title_number_is_exempt(self):
        master = LEDGER_DECK.replace("2026 年度新签 37 家", "2026 年度盘点收尾")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("标题数字", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_percent_title_reconciles_with_decimal_ledger_row(self):
        # 标题写「11%」、登记行写「11.0」——按数值归一比较，不再误报。
        master = LEDGER_DECK.replace("营收增长 55%", "营收增长 55%").replace(
            "| 55% | S1 |", "| 55.0 | S1 |")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("标题数字", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_decimal_title_reconciles_with_percent_ledger_row(self):
        master = LEDGER_DECK.replace("营收增长 55%", "营收增长 55").replace(
            "| 55% | S1 |", "| 55% | S1 |")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("标题数字「55」", result.stdout)

    def test_numeric_value_mismatch_still_warns_across_forms(self):
        # 归一化只解决形态（%/小数），不掩盖数值差异：61% 对 55 仍须报。
        master = LEDGER_DECK.replace("营收增长 55%", "营收增长 61%").replace(
            "| 55% | S1 |", "| 55 | S1 |")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("标题数字「61%」不在本页（S1）登记表数值中", result.stdout)

    def test_cross_page_ledger_cell_covers_both_pages(self):
        # 页列「S1/S2」的登记行须同时覆盖两页（既有行为回归保护）。
        master = LEDGER_DECK.replace(
            "## S2 年度\n- 标题：2026 年度新签 37 家",
            "## S2 年度\n- 标题：年度营收增长 55%").replace(
            "| 55% | S1 |", "| 55% | S1/S2 |").replace(
            "| 37 家 | S2 |", "| 37 家 | 附 |")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("标题数字", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)


DATA_PAGE = """## S{N} 数据
- 标题：容量数据{N}
- 要点：
  - 命中率 92%
  - 延迟 12 毫秒
  - 月成本 3.1 万元
- speaker_script：先说结论。
"""

QUAL_PAGE = """## S{N} 结论
- 标题：架构结论{N}
- 要点：
  - 分层架构降低耦合
  - 边界清晰利于长期维护
- speaker_script：先说结论。
"""


class ArgumentMediumTest(unittest.TestCase):
    """R-21 family j: three consecutive pure-data or pure-qualitative pages."""

    def _deck(self, kinds):
        return "\n".join(
            (DATA_PAGE if k == "data" else QUAL_PAGE).format(N=i + 1)
            for i, k in enumerate(kinds))

    def test_three_pure_data_pages_warn_medium_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, self._deck(["data"] * 3))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("连续 3 个内容页同为纯数据论证", result.stdout)
        self.assertIn("类比 / 案例 / 反例", result.stdout)

    def test_three_pure_qualitative_pages_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, self._deck(["qual"] * 3))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("连续 3 个内容页同为纯定性论证", result.stdout)

    def test_alternating_mediums_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, self._deck(["data", "qual", "data"]))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("论证媒介", result.stdout)
        self.assertNotIn("纯数据论证", result.stdout)
        self.assertNotIn("纯定性论证", result.stdout)

    def test_argument_role_data_declared_counts_even_without_digits(self):
        master = """## S1 论据
- argument_role：数据
- 标题：证据一
- 要点：
  - 图表支持该结论
- speaker_script：先说结论。

## S2 论据
- argument_role：数据
- 标题：证据二
- 要点：
  - 台账支持该结论
- speaker_script：先说结论。

## S3 论据
- argument_role：证据
- 标题：证据三
- 要点：
  - 引文支持该结论
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("同为纯数据论证", result.stdout)


class QuoteQualityTest(unittest.TestCase):
    """R-22 family k: slogan pattern + opposite-pair quote deck cap."""

    def test_slogan_point_on_quote_page_warns(self):
        master = """## S5 金句
- 标题：一句收束
- 要点：
  - 拥抱变化，共赢未来
- speaker_script：收束一句。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("金句要点为口号模式「拥抱变化，共赢未来」", result.stdout)
        self.assertIn("重写为具体洞见", result.stdout)

    def test_concrete_insight_with_number_not_flagged(self):
        master = """## S5 金句
- 标题：一句收束
- 要点：
  - 复利来自 20 年的年化 8%
- speaker_script：收束一句。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("口号模式", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_two_opposite_pair_quotes_exceed_deck_cap(self):
        master = """## S5 金句
- 标题：一句收束
- 要点：
  - 少即是多
  - 慢就是快
- speaker_script：收束一句。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("反向克制型金句", result.stdout)
        self.assertIn("deck 级 2 处，超过上限 1", result.stdout)

    def test_single_opposite_quote_within_cap_not_flagged(self):
        master = """## S5 金句
- 标题：一句收束
- 要点：
  - 少即是多
- speaker_script：收束一句。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("反向克制型", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_slogan_on_non_quote_page_not_flagged_by_family_k(self):
        master = """## S5 方案
- 标题：转型方案
- 要点：
  - 拥抱变化，共赢未来
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("口号模式", result.stdout)


ACADEMIC_HEADER = """# 母版
deck-contract:
  math_load: medium
  figure_orientation: figure-first

"""


def _academic(point):
    return ACADEMIC_HEADER + f"""## S1 方法
- 标题：方法概览
- 要点：
  - {point}
- speaker_script：先说结论。
"""


class VagueWordTest(unittest.TestCase):
    """R-23 family l: vague intensifiers without same-line quantifiers."""

    def test_vague_word_without_quantifier_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, _academic("本方法显著提升检索精度"))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("要点模糊强度词「显著」", result.stdout)
        self.assertIn("替换为测量条件", result.stdout)

    def test_vague_word_with_comparison_baseline_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(
                tmp, _academic("相比 BM25 基线显著提升排序质量"))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("模糊强度词", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_vague_word_with_digit_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, _academic("召回率显著提升 12%"))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("模糊强度词", result.stdout)

    def test_quoted_span_is_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(
                tmp, _academic("审稿人反对把「有效」当作默认结论"))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("模糊强度词", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_illustrative_tag_is_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, _academic("吞吐有效提升【示意】"))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("模糊强度词", result.stdout)

    def test_non_academic_master_skips_family_with_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, CLEAN_DECK)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("要点模糊词检查跳过", result.stdout)
        self.assertNotIn("模糊强度词", result.stdout)

    def test_robust_word_variants_all_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(
                tmp, _academic("新模型鲁棒，旧系统先进，流程有效，误差可控"))])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("「鲁棒」", result.stdout)
        self.assertIn("「先进」", result.stdout)
        self.assertIn("「有效」", result.stdout)


class StyleSampleTest(unittest.TestCase):
    """R-20: high-frequency sample words exempt word-list families."""

    def _sample(self, tmp, text, name="voice-sample.md"):
        path = Path(tmp) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_sample_exempts_jargon_word(self):
        master = """## S1 方案
- 标题：为新功能赋能
- 要点：
  - 复核登记表后重建
- speaker_script：先说结论。
"""
        sample = "赋能团队，赋能业务，赋能客户，赋能伙伴，持续赋能。语言直接具体。"
        with tempfile.TemporaryDirectory() as tmp:
            without = _run([_master(tmp, master)])
            with_sample = _run([_master(tmp, master, "again.md"),
                                "--style-sample", self._sample(tmp, sample)])
        self.assertIn("黑话「赋能」出现 1 次", without.stdout)
        self.assertEqual(with_sample.returncode, 0, with_sample.stdout)
        self.assertNotIn("黑话", with_sample.stdout)
        self.assertNotIn("[WARN]", with_sample.stdout)

    def test_sample_exempts_intensifier_stacking(self):
        master = """## S1 发现
- 标题：两个强断言
- 要点：
  - 非常关键的发现
  - 十分严格的口径
- speaker_script：先说结论。
"""
        sample = "非常聚焦，非常具体，非常直接，非常克制，写得非常短。"
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master),
                           "--style-sample", self._sample(tmp, sample)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("强度副词", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_sample_exempts_vague_word_in_academic_deck(self):
        master = _academic("本方法显著提升检索精度")
        sample = "显著改善，显著推进，显著收缩，显著提速，效果显著，信号显著。"
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master),
                           "--style-sample", self._sample(tmp, sample)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("模糊强度词", result.stdout)

    def test_missing_sample_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, CLEAN_DECK),
                           "--style-sample", Path(tmp) / "no-sample.md"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("无法读取文风样本", result.stderr)

    def test_empty_sample_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, CLEAN_DECK),
                           "--style-sample", self._sample(tmp, "")])
        self.assertEqual(result.returncode, 2)
        self.assertIn("文风样本为空文件", result.stderr)

    def test_json_payload_carries_style_sample_words(self):
        sample = "赋能团队，赋能业务，赋能客户，赋能伙伴，持续赋能。"
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, CLEAN_DECK, "deck.md"), "--json",
                           "--style-sample", self._sample(tmp, sample)])
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("赋能", payload["style_sample_words"])


if __name__ == "__main__":
    unittest.main()
