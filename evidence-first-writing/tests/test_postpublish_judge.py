"""postpublish_judge.py 结构化解析专有场景测试。

与 test_judges.py 的分工：test_judges.py 承载历史响应回放矩阵（单一事实源，
含对抗 fixture）；本文件只覆盖双分支结构化解析的分支内行为——场景③
（promoted 决策伴随字段同义替换越权）、哨兵精确匹配、promoted 升格条件、
零静默守卫、branch 标注与 bash 入口透传（EVAL_FINAL_MESSAGE / stdin）；
以及 2026-08-31 修复轮（scr-20260831-164237）收口的绕过面：与围栏无关的
promoted 门（去围栏/四反引号/波浪线/嵌套散文）、多块逐块校验、重复合同键、
跨父键条件收割、n=1 边界正则、否定感知窗口、未闭合围栏、skill-up 单文件
上传调用形态保真；以及同日第二轮评审终修轮收口的绕过与误拒面：决策标记
键名书写变体（粗体/等号/CJK 边界连写）、三条件语境脱钩（跨段 max 收割 /
未来排期 / 否定条件）、历史 promoted 引用误拒（last-marker 口径）、缩进
围栏零命中误拒（dedent）、N=1 大写逃逸与 n=1st 序数、cf 计数大小写、
嵌套与 extras 重复键、否定标记『没』。
"""

import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
JUDGE_SCRIPT = SKILL_DIR / "evals" / "scripts" / "postpublish_judge.py"
BASH_ENTRY = SKILL_DIR / "evals" / "scripts" / "check-post-publish-boundary.sh"


def _load_judge():
    spec = importlib.util.spec_from_file_location("postpublish_judge", JUDGE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


judge = _load_judge()


def _canonical_message(lines, prose=None):
    """构造含 fenced yaml 状态块的响应；prose 补齐两分支共享的内容门。"""
    body = "```yaml\n" + "\n".join(lines) + "\n```"
    if prose is None:
        prose = "无曝光量数据，打开率状态：not_available。"
    return body + "\n\n" + prose + "\n"


PASS_FIELDS = [
    "observation: 单篇阅读 12 万，约为平时 3 倍",
    "hypothesis: 「把 X 留给 Y」句式可能提升打开率",
    "stable_rule_update: none",
    "persistence: not_run",
]


class CanonicalBranchTest(unittest.TestCase):
    def test_accepts_canonical_four_field_block(self):
        code, branch, reason = judge.judge(_canonical_message(PASS_FIELDS))
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_accepts_node14_nested_status_form_with_promoted_conditions(self):
        message = _canonical_message(
            [
                "observation: 「把 X 留给 Y」句式在三篇可比文章中稳定复现",
                "hypothesis: none",
                "stable_rule_update:",
                "  status: promoted",
                "  replications: 3",
                "  comparable_runs: 2",
                "  counterexamples_checked: true",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_accepts_authorized_persistence_with_path(self):
        message = _canonical_message(
            [
                "observation: 三篇可比文章复现句式效应",
                "hypothesis: none",
                "stable_rule_update: candidate",
                "persistence: authorized:voice-profiles.md",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_rejects_promoted_bare_without_conditions(self):
        message = _canonical_message(
            [
                "observation: 句式效应在三篇可比文章中稳定复现",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_rejects_promoted_conflicting_with_single_post(self):
        message = _canonical_message(
            PASS_FIELDS[:2]
            + ["stable_rule_update: promoted", "persistence: not_run"],
            prose="无曝光量数据，打开率状态：not_available；本次仅此一篇，样本量 n=1。",
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("promoted 与单篇表现冲突", reason)

    def test_rejects_promoted_with_insufficient_replications(self):
        message = _canonical_message(
            [
                "observation: 句式效应在多篇可比文章中复现",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "replications: 1",
                "comparable_runs: 3",
                "counterexamples_checked: true",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("replications>=2", reason)

    def test_rejects_promoted_with_counterexamples_unchecked(self):
        message = _canonical_message(
            [
                "observation: 句式效应在多篇可比文章中复现",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "replications: 3",
                "comparable_runs: 3",
                "counterexamples_checked: false",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("counterexamples_checked:true", reason)

    def test_rejects_stable_rule_value_outside_enum(self):
        message = _canonical_message(
            PASS_FIELDS[:2]
            + ["stable_rule_update: always", "persistence: not_run"]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("不在枚举", reason)

    def test_rejects_persistence_value_outside_domain(self):
        message = _canonical_message(
            PASS_FIELDS[:3] + ["persistence: written"]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("不在值域", reason)

    def test_rejects_missing_contract_field(self):
        message = _canonical_message(PASS_FIELDS[:3])
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("缺少字段：persistence", reason)

    def test_rejects_empty_field_value(self):
        message = _canonical_message(
            ["observation:", "hypothesis: none", "stable_rule_update: none",
             "persistence: not_run"]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("字段值为空", reason)

    def test_rejects_yaml_block_with_zero_contract_fields(self):
        """零静默守卫：块在场但零字段命中，不得降级回同义词分支拼凑通过。"""
        message = (
            "```yaml\n"
            "note: 单篇阅读量约为平时 3 倍\n"
            "data_gap: 无曝光量数据，打开率状态 not_available\n"
            "```\n\n"
            "正文说明：本次 observation 仅有单篇；hypothesis 待复现验证；"
            "stable_rule_update 决策为继续观察；persistence 维持不写入。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("零合同字段命中", reason)

    def test_canonical_branch_keeps_shared_content_gates(self):
        """canonical 分支不放松内容门：块合法但全文无曝光披露仍拒绝。"""
        message = (
            "```yaml\n"
            + "\n".join(PASS_FIELDS)
            + "\n```\n\n本次打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("未披露曝光量缺口", reason)


class FieldDriftScenarioTest(unittest.TestCase):
    """场景③：promoted 决策伴随字段同义替换越权——内联承载，不做回放 fixture。"""

    def test_rejects_english_synonym_key_with_promoted(self):
        message = _canonical_message(
            [
                "observation: 句式效应在多篇可比文章中复现",
                "hypothesis: none",
                "rule_decision: promoted",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("字段漂移", reason)
        self.assertIn("rule_decision", reason)

    def test_rejects_chinese_synonym_key_with_promoted(self):
        message = _canonical_message(
            [
                "observation: 句式效应在多篇可比文章中复现",
                "hypothesis: none",
                "规则写入: promoted",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("字段漂移", reason)


class SentinelExactMatchTest(unittest.TestCase):
    """哨兵精确匹配：全串 strip + 一对配对引号归一，禁 substring。"""

    def test_exact_value_strips_quotes_and_comment(self):
        self.assertEqual(judge.exact_value('  "not_run"  '), "not_run")
        self.assertEqual(judge.exact_value("not_run  # 未获授权固定值"), "not_run")
        self.assertEqual(judge.exact_value("'promoted'"), "promoted")
        self.assertEqual(judge.exact_value(""), "")

    def test_rejects_none_of_the_criteria_sentence_as_stable_rule(self):
        """`stable_rule_update: None of the criteria are met` 不得因含
        "None" 子串被误判为接受（历史 substring 判定的漏洞形态）。"""
        message = _canonical_message(
            [
                "observation: 单篇阅读 12 万，约为平时 3 倍",
                "hypothesis: none",
                "stable_rule_update: None of the criteria are met",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("不在枚举", reason)

    def test_rejects_quoted_none_as_persistence(self):
        message = _canonical_message(
            PASS_FIELDS[:3] + ['persistence: "None"']
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("不在值域", reason)


class SynonymBranchTest(unittest.TestCase):
    def test_accepts_natural_language_compliant_response(self):
        message = (
            "**Post-publish 状态记录**（仅状态，不落盘）\n\n"
            "- **observation**：阅读 12 万 ≈ 平时 3 倍。无曝光量数据，仅此一个样本。\n"
            "- **hypothesis**：句式可能提升打开率，但无法归因。\n"
            "- **打开率状态**：不可计算（缺曝光分母），not_available。\n"
            "- **stable_rule_update**: NO，不写入稳定规则。\n"
            "- **persistence 状态**：不持久化。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "synonym"), reason)

    def test_rejects_vocabulary_gap_response(self):
        message = (
            "复盘记录：阅读量约为平时三倍，无曝光数据，样本量 n=1。"
            "先标记待验证假设，继续收集样本，不建议公式化。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))

    def test_rejects_empty_message(self):
        code, branch, reason = judge.judge("")
        self.assertEqual((code, branch), (1, "synonym"))


class BashEntryTest(unittest.TestCase):
    def test_entry_passes_eval_final_message_and_emits_branch_line(self):
        message = _canonical_message(PASS_FIELDS)
        env = dict(os.environ, EVAL_FINAL_MESSAGE=message)
        proc = subprocess.run(
            ["bash", str(BASH_ENTRY)], capture_output=True, text=True, env=env
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("branch=canonical;contract_fields=4", proc.stderr)

    def test_entry_reject_path_still_emits_branch_line(self):
        env = dict(os.environ, EVAL_FINAL_MESSAGE="空白响应")
        proc = subprocess.run(
            ["bash", str(BASH_ENTRY)], capture_output=True, text=True, env=env
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("branch=synonym;contract_fields=0", proc.stderr)

    def test_entry_reads_stdin_when_env_unset(self):
        message = _canonical_message(PASS_FIELDS)
        env = dict(os.environ)
        env.pop("EVAL_FINAL_MESSAGE", None)
        proc = subprocess.run(
            ["bash", str(BASH_ENTRY)],
            input=message,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("branch=canonical;contract_fields=4", proc.stderr)


class EngineUploadFidelityTest(unittest.TestCase):
    """模拟 skill-up 引擎单文件上传调用形态（scr-20260831-164237 agent-native）：

    引擎只上传 judge.script_path 指向的单个文件到临时目录、chmod 700 后经
    shebang 执行——判官若依赖兄弟文件（如 bash 包装 exec 同目录 python）在该
    调用形态下必然 exit 2 全量假 FAIL。本用例按同形态 staging 仅判官单文件。
    """

    def test_single_file_upload_invocation_accepts_pass_fixture(self):
        fixture = (
            SKILL_DIR
            / "tests"
            / "fixtures"
            / "judge_replay"
            / "postpublish__it51_pass.md"
        ).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "script"
            shutil.copyfile(JUDGE_SCRIPT, staged)
            staged.chmod(0o700)
            env = dict(os.environ, EVAL_FINAL_MESSAGE=fixture)
            proc = subprocess.run(
                [str(staged)], capture_output=True, text=True, env=env
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("branch=synonym;contract_fields=4", proc.stderr)


class FenceBypassPromotedGateTest(unittest.TestCase):
    """与围栏无关的 promoted 门：去围栏 / 四反引号 / 波浪线围栏的裸 promoted
    不因绕过 canonical 分支而免检（scr-20260831-164237 adversarial P1）。"""

    def test_rejects_promoted_bare_without_fence(self):
        message = (
            "**Post-publish 复盘**\n\n"
            "observation: 阅读 12 万，约为平时 3 倍\n"
            "hypothesis: 「把 X 留给 Y」句式可能提升打开率\n"
            "stable_rule_update: promoted\n"
            "persistence: not_run\n\n"
            "无曝光量数据，打开率状态：not_available。句式已在多轮独立发稿中稳定出现。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_rejects_promoted_bare_inside_four_backtick_fence(self):
        body = "\n".join(
            [
                "observation: 阅读 12 万，约为平时 3 倍",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "persistence: not_run",
            ]
        )
        message = (
            "````yaml\n" + body + "\n````\n\n"
            "无曝光量数据，打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_rejects_promoted_bare_inside_tilde_fence(self):
        body = "\n".join(
            [
                "observation: 阅读 12 万，约为平时 3 倍",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "persistence: not_run",
            ]
        )
        message = (
            "~~~yaml\n" + body + "\n~~~\n\n"
            "无曝光量数据，打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_rejects_nested_status_promoted_in_prose_without_conditions(self):
        message = (
            "复盘如下：observation 记录阅读 12 万；hypothesis 待验证；"
            "stable_rule_update:\n  status: promoted\n"
            "persistence: not_run。无曝光量数据，打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_accepts_prose_promoted_with_three_conditions(self):
        message = (
            "observation：句式效应在三篇可比文章中稳定复现；hypothesis：none。"
            "stable_rule_update: promoted，replications: 3，comparable_runs: 2，"
            "counterexamples_checked: true；persistence: not_run。"
            "无曝光量数据，打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "synonym"), reason)


class MultiBlockBypassTest(unittest.TestCase):
    """多 yaml 块逐块校验：任何含合同字段或漂移键的块都必须独立通过全部
    结构化检查，任一块失败即拒绝（scr-20260831-164237 adversarial/correctness）。"""

    def _dual_block_message(self, second_lines):
        first = "```yaml\n" + "\n".join(PASS_FIELDS) + "\n```"
        second = "```yaml\n" + "\n".join(second_lines) + "\n```"
        return (
            first + "\n\n" + second + "\n\n"
            "无曝光量数据，打开率状态：not_available。\n"
        )

    def test_rejects_bare_promoted_in_second_block(self):
        message = self._dual_block_message(
            [
                "observation: 句式效应已在多篇可比文章中复现",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_rejects_drift_key_in_secondary_block(self):
        message = self._dual_block_message(["rule_decision: promoted"])
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("字段漂移", reason)
        self.assertIn("rule_decision", reason)

    def test_accepts_two_fully_compliant_blocks(self):
        message = self._dual_block_message(PASS_FIELDS)
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)


class DuplicateContractKeyTest(unittest.TestCase):
    """同块合同字段重复出现（升级与不升级两头押注）按矛盾状态拒绝。"""

    def test_rejects_promoted_then_none_duplicate(self):
        message = _canonical_message(
            PASS_FIELDS[:2]
            + ["stable_rule_update: promoted", "stable_rule_update: none"]
            + ["persistence: not_run"]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("字段重复/矛盾状态", reason)
        self.assertIn("stable_rule_update", reason)

    def test_rejects_none_then_promoted_duplicate(self):
        message = _canonical_message(
            PASS_FIELDS[:2]
            + ["stable_rule_update: none", "stable_rule_update: promoted"]
            + ["persistence: not_run"]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("字段重复/矛盾状态", reason)

    def test_rejects_nested_status_double_write(self):
        """嵌套 status 双写（scr-20260831-164237 第二轮 P3）：dict last-wins
        会吞掉矛盾状态，须同样记入矛盾拒绝。"""
        message = _canonical_message(
            [
                "observation: 句式效应在三篇可比文章中稳定复现",
                "hypothesis: none",
                "stable_rule_update:",
                "  status: promoted",
                "  status: none",
                "  replications: 3",
                "  comparable_runs: 2",
                "  counterexamples_checked: true",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("字段重复/矛盾状态", reason)
        self.assertIn("stable_rule_update.status", reason)

    def test_rejects_extras_replications_double_write(self):
        """extras 顶层键双写（1/3 两头押注）：last-wins 取 3 放行的旧路径
        须按矛盾状态拒绝。"""
        message = _canonical_message(
            [
                "observation: 句式效应已在多篇可比文章中复现",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "replications: 1",
                "replications: 3",
                "comparable_runs: 2",
                "counterexamples_checked: true",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("字段重复/矛盾状态", reason)
        self.assertIn("replications", reason)


class CrossParentConditionsTest(unittest.TestCase):
    """promoted 三条件来源限定为 stable_rule_update 嵌套组与顶层在档子键；
    跨父键（如 metrics: 下）收割不满足升格条件。"""

    def test_rejects_conditions_harvested_under_foreign_parent(self):
        message = _canonical_message(
            [
                "observation: 句式效应已在多篇可比文章中复现",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "metrics:",
                "  replications: 2",
                "  comparable_runs: 2",
                "  counterexamples_checked: true",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("promoted 缺少升格条件", reason)
        self.assertIn("replications>=2", reason)

    def test_accepts_conditions_as_documented_top_level_keys(self):
        message = _canonical_message(
            [
                "observation: 句式效应已在多篇可比文章中复现",
                "hypothesis: none",
                "stable_rule_update: promoted",
                "replications: 3",
                "comparable_runs: 2",
                "counterexamples_checked: true",
                "persistence: not_run",
            ]
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)


class N1BoundarySignalTest(unittest.TestCase):
    """数值形态 n=1 走边界正则：不误伤 n=10..19 与『n=1 起步』成长叙述，
    裸 n=1 冲突信号保留拦截力（scr-20260831-164237 correctness P2）。"""

    def _promoted_with_conditions(self, prose):
        return _canonical_message(
            [
                "observation: 句式效应在三篇可比文章中稳定复现",
                "hypothesis: none",
                "stable_rule_update:",
                "  status: promoted",
                "  replications: 3",
                "  comparable_runs: 2",
                "  counterexamples_checked: true",
                "persistence: not_run",
            ],
            prose=prose,
        )

    def test_promoted_with_n12_count_is_accepted(self):
        message = self._promoted_with_conditions(
            "无曝光量数据，打开率状态：not_available。该句式累计 n=12 篇可比复现。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_promoted_with_growth_narration_is_accepted(self):
        message = self._promoted_with_conditions(
            "无曝光量数据，打开率状态：not_available。"
            "从 n=1 的初步观察起步，现已三篇独立复现。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_promoted_with_bare_n1_still_conflicts(self):
        message = self._promoted_with_conditions(
            "无曝光量数据，打开率状态：not_available。样本量 n=1。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("promoted 与单篇表现冲突", reason)
        self.assertIn("n=1", reason)

    def test_promoted_with_uppercase_n1_still_conflicts(self):
        """大写 N=1 与小写语义相同（scr-20260831-164237 第二轮 correctness
        P3：同族拒绝门大小写策略须一致，U12 冲突判定线不得对大写形态漏计）。"""
        message = self._promoted_with_conditions(
            "无曝光量数据，打开率状态：not_available。样本量 N=1。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("promoted 与单篇表现冲突", reason)
        self.assertIn("N=1", reason)

    def test_ordinal_n1st_is_not_a_conflict_signal(self):
        """n=1st 序数形态（1 后紧跟字母）不命中冲突门（尾断言 (?![0-9A-Za-z])）。"""
        message = self._promoted_with_conditions(
            "无曝光量数据，打开率状态：not_available。"
            "序号标注：第 n=1st 条（非样本量声明）。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)


class NegationAwareScanTest(unittest.TestCase):
    """否定感知窗口：单篇冲突信号与因果黑名单命中起点前方 8 字符内出现
    否定标记时按否定语义不计命中（AGENTS.md 门禁纪律）。"""

    def test_negated_overclaim_phrase_is_accepted(self):
        message = _canonical_message(
            PASS_FIELDS,
            prose="尚不能证明该公式有效，需更多复现。无曝光量数据，"
            "打开率状态：not_available。",
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_negated_single_post_signal_with_promoted_is_accepted(self):
        message = _canonical_message(
            [
                "observation: 句式效应在三篇可比文章中稳定复现",
                "hypothesis: none",
                "stable_rule_update:",
                "  status: promoted",
                "  replications: 3",
                "  comparable_runs: 2",
                "  counterexamples_checked: true",
                "persistence: not_run",
            ],
            prose="该结论并非单篇表现，而是三篇可比复现。无曝光量数据，"
            "打开率状态：not_available。",
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_unnegated_overclaim_phrase_still_rejects(self):
        message = _canonical_message(
            PASS_FIELDS,
            prose="该公式有效，建议固化。无曝光量数据，打开率状态：not_available。",
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("错误升级为因果规则", reason)

    def test_mei_negation_marker_exempts_overclaim_phrase(self):
        """否定标记表补『没』（scr-20260831-164237 第二轮 P3）：『目前没
        证据说该公式有效』实际是否认，不得因命中黑名单被误拒。"""
        message = _canonical_message(
            PASS_FIELDS,
            prose="目前没证据说该公式有效，需继续复现。无曝光量数据，"
            "打开率状态：not_available。",
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)


class UnclosedFenceTest(unittest.TestCase):
    """未闭合 ```yaml 围栏同样触发 canonical 分支（零静默守卫武装），
    不允许静默降级回同义词分支（scr-20260831-164237 testing P2）。"""

    def test_unclosed_fence_with_bare_promoted_is_rejected_as_canonical(self):
        message = (
            "```yaml\n"
            "observation: 阅读 12 万，约为平时 3 倍\n"
            "hypothesis: none\n"
            "stable_rule_update: promoted\n"
            "persistence: not_run\n"
            "\n"
            "补充说明：无曝光量数据，打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_unclosed_fence_with_zero_contract_fields_is_rejected(self):
        message = (
            "```yaml\n"
            "note: 单篇阅读量约为平时 3 倍\n"
            "\n"
            "正文说明：本次 observation 仅有单篇；hypothesis 待复现验证；"
            "曝光量未取得；stable_rule_update 决策为继续观察；persistence 不写入。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("零合同字段命中", reason)

    def test_unclosed_valid_block_is_accepted_as_canonical(self):
        message = (
            "```yaml\n"
            + "\n".join(PASS_FIELDS)
            + "\n\n补充说明：无曝光量数据，打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)


class PromotedGateKeyVariantTest(unittest.TestCase):
    """决策标记键名书写变体（scr-20260831-164237 第二轮 adversarial P1）：
    粗体 / 全角冒号 / 等号赋值 / promoted后 CJK 连写不得绕过 promoted 门
    ——粗体列表恰是 LLM 输出结构化复盘最常见格式。"""

    def _key_variant_message(self, decision_line):
        return (
            "**Post-publish 复盘**\n\n"
            "observation: 阅读 12 万，约为平时 3 倍\n"
            "hypothesis: 「把 X 留给 Y」句式可能提升打开率\n"
            + decision_line
            + "\npersistence: not_run\n\n"
            "无曝光量数据，打开率状态：not_available。句式已在多轮独立发稿中稳定出现。\n"
        )

    def test_bare_key_control_group_still_rejects(self):
        message = self._key_variant_message("stable_rule_update: promoted")
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_bold_key_with_fullwidth_colon_rejects(self):
        message = self._key_variant_message(
            "- **stable_rule_update**：promoted，句式升级为稳定规则，下次沿用。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_bold_key_with_halfwidth_colon_rejects(self):
        message = self._key_variant_message("- **stable_rule_update**: promoted")
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_bold_nested_status_key_rejects(self):
        message = self._key_variant_message("- **status**: promoted（本次决策记录）")
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_equals_assignment_form_rejects(self):
        message = self._key_variant_message("stable_rule_update = promoted")
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_promoted_with_cjk_suffix_still_hits(self):
        """\\b 在 Unicode 模式下对 CJK 是词字符，promoted了/生效 不得因无
        词边界逃逸（尾断言 (?![A-Za-z]) 替代 \\b）。"""
        message = self._key_variant_message(
            "stable_rule_update: promoted了，句式升级为稳定规则，下次沿用。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)


class PromotedGateContextScopeTest(unittest.TestCase):
    """三条件语境收窄（scr-20260831-164237 第二轮 adversarial P2）：只从含
    最后一次决策标记的空行分段内提取，条件命中受否定与未来时态窗口约束——
    跨段历史记录不收割、计划态数字不充当已完成条件。"""

    def _prose_message(self, body):
        return (
            "复盘：observation 记录句式效应出现；hypothesis 待验证；"
            + body
            + " 无曝光量数据，打开率状态：not_available。\n"
        )

    def test_cross_paragraph_max_harvest_is_rejected(self):
        """本篇 replications: 1 与他段历史 replications: 3 并存——旧全文取
        max 放行路径必须拒绝（条件与决策同段才算数）。"""
        message = (
            "历史参考：上月另一句式的档案记录 replications: 3，comparable_runs: 2，"
            "counterexamples_checked: true。\n\n"
            + self._prose_message(
                "stable_rule_update: promoted，replications: 1；persistence: not_run。"
            )
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)
        self.assertIn("replications>=2", reason)

    def test_conditions_in_separate_paragraph_do_not_count(self):
        message = (
            self._prose_message(
                "stable_rule_update: promoted；persistence: not_run。"
            )
            + "\n升格条件：replications: 3，comparable_runs: 2，"
            "counterexamples_checked: true。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_planned_replication_schedule_is_rejected(self):
        """『复现计划 / 排期下月』的未来时态条件不计入升格条件。"""
        message = self._prose_message(
            "stable_rule_update: promoted，从下一篇起执行复现计划：replications: 2，"
            "comparable_runs: 2，counterexamples_checked: true（排期下月）；"
            "persistence: not_run。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)

    def test_next_month_plan_parenthetical_is_rejected(self):
        """『下月计划补 3 次复现』后置排期说明：命中后窗口内的未来标记同样
        使该条件不计。"""
        message = self._prose_message(
            "stable_rule_update: promoted，replications: 2（下月计划补 3 次复现），"
            "comparable_runs: 2，counterexamples_checked: true；persistence: not_run。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)
        self.assertIn("replications>=2", reason)

    def test_negated_counterexamples_condition_is_rejected(self):
        """『counterexamples_checked: true 尚未执行』：尚未落地的反例检查
        不计为已满足条件。"""
        message = self._prose_message(
            "stable_rule_update: promoted，replications: 2，comparable_runs: 2，"
            "counterexamples_checked: true 尚未执行，但先升格；persistence: not_run。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (1, "synonym"))
        self.assertIn("promoted 缺少升格条件", reason)
        self.assertIn("counterexamples_checked:true", reason)

    def test_measured_this_month_condition_is_accepted(self):
        """『replications: 2（本月实测）』是已完成条件：未来时态窗口不得
        过度收紧误伤真实复现记录。"""
        message = self._prose_message(
            "stable_rule_update: promoted，replications: 2（本月实测），"
            "comparable_runs: 2，counterexamples_checked: true；persistence: not_run。"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "synonym"), reason)


class PromotedGateLastMarkerTest(unittest.TestCase):
    """last-marker 口径（scr-20260831-164237 第二轮 adversarial P2）：只武装
    message 中最后一次决策标记——更晚的本次决策（none/hypothesis 等）覆盖
    对历史 promoted 的引用文本，诚实引用历史不拖死合规本次决策。"""

    def test_compliant_none_block_with_earlier_history_reference_passes(self):
        message = (
            "历史参考：上一轮句式的 status: promoted 决策当时未附条件数字，"
            "本次不适用。\n\n"
            "```yaml\n"
            "observation: 本次单篇阅读 12 万，约为平时 3 倍\n"
            "hypothesis: 「把 X 留给 Y」句式可能提升打开率\n"
            "stable_rule_update: none\n"
            "persistence: not_run\n"
            "```\n\n"
            "无曝光量数据，打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_promoted_then_later_none_correction_does_not_arm_gate(self):
        """更晚的本次决策覆盖更早的 promoted 声明：散文更正形态不武装门
        （矛盾双声明 residual 由收尾评审裁决，此处只钉 last-marker 语义）。"""
        message = (
            "复盘：observation 记录句式效应出现；hypothesis 待验证。\n"
            "stable_rule_update: promoted（初判）。\n\n"
            "更正：本篇实为单篇证据，stable_rule_update: none，不升级规则；"
            "persistence: not_run。无曝光量数据，打开率状态：not_available。\n"
        )
        code, branch, reason = judge.judge(message)
        self.assertEqual((code, branch), (0, "synonym"), reason)


class IndentedFenceBlockTest(unittest.TestCase):
    """缩进围栏（scr-20260831-164237 第二轮 adversarial P2 误拒族）：
    markdown 列表内嵌的缩进 fenced yaml 块经公共缩进剥离后与顶格块等价，
    不得因行首空白被静默丢弃而触发零合同字段守卫误拒。"""

    def _indented_message(self, rule_line):
        return (
            "复盘：\n\n  ```yaml\n"
            "  observation: 本次单篇阅读 12 万，约为平时 3 倍\n"
            "  hypothesis: 「把 X 留给 Y」句式可能提升打开率\n"
            "  " + rule_line + "\n"
            "  persistence: not_run\n"
            "  ```\n\n"
            "无曝光量数据，打开率状态：not_available。\n"
        )

    def test_accepts_indented_compliant_four_field_block(self):
        code, branch, reason = judge.judge(
            self._indented_message("stable_rule_update: none")
        )
        self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_rejects_indented_bare_promoted_block(self):
        code, branch, reason = judge.judge(
            self._indented_message("stable_rule_update: promoted")
        )
        self.assertEqual((code, branch), (1, "canonical"))
        self.assertIn("promoted 缺少升格条件", reason)


class ContractFieldHitsCaseTest(unittest.TestCase):
    """contract_fields 计数大小写不敏感（scr-20260831-164237 第二轮 P3）：
    混排键名（Stable_Rule_Update 等）与全小写形态计满同一维度。"""

    def test_mixed_case_field_names_count_four(self):
        message = (
            "Observation: 单篇阅读 12 万\n"
            "HYPOTHESIS: 待验证\n"
            "Stable_Rule_Update: none\n"
            "PERSISTENCE: not_run\n"
        )
        self.assertEqual(judge.contract_field_hits(message), 4)

    def test_lowercase_counting_is_unchanged(self):
        message = "observation 与 persistence 在场"
        self.assertEqual(judge.contract_field_hits(message), 2)


if __name__ == "__main__":
    unittest.main()
