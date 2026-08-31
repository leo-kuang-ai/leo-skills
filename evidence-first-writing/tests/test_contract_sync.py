"""三方同步测试：SKILL.md 合同字段 ↔ editorial-pipeline.md Node 14 ↔ 判官接受集。

防漂移锁（仿 claude-blog ``test_blog_delivery_contract.py`` 模式，深读报告
T3 C3）：SKILL.md post-publish canonical 状态块的四字段名、Node 14
``stable_rule_update`` 的 status 枚举与 promoted 升格阈值、判官脚本的
值域常量，三方任一漂移（字段改名、枚举增删值、阈值改数、判官私造
未在档键）本文件即红。判官常量是单一事实源，由本测试钉在两份合同
文档上。2026-08-31 修复轮（scr-20260831-164237）起 JudgeAcceptanceSetTest
升级为行为级：遍历枚举实际调用 judge.judge 断言接受（补 hypothesis 首个
行为用例），并以 SKILL.md canonical 块原文经判官接受锁定文档样例腿。
"""

import importlib.util
import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
JUDGE_SCRIPT = SKILL_DIR / "evals" / "scripts" / "postpublish_judge.py"
SKILL_MD = SKILL_DIR / "SKILL.md"
PIPELINE_MD = SKILL_DIR / "references" / "editorial-pipeline.md"


def _load_judge():
    spec = importlib.util.spec_from_file_location("postpublish_judge", JUDGE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


judge = _load_judge()


def _skill_postpublish_block():
    """SKILL.md 中含全部合同字段的 canonical fenced yaml 状态块。"""
    blocks = [
        judge.parse_block(block)
        for block in judge.extract_yaml_blocks(SKILL_MD.read_text(encoding="utf-8"))
    ]
    canonical = [b for b in blocks if set(b.fields) == set(judge.CONTRACT_FIELDS)]
    return canonical


def _skill_postpublish_block_texts():
    """同上，但返回块原文（供判官行为级接受断言使用）。"""
    texts = []
    for raw in judge.extract_yaml_blocks(SKILL_MD.read_text(encoding="utf-8")):
        parsed = judge.parse_block(raw)
        if set(parsed.fields) == set(judge.CONTRACT_FIELDS):
            texts.append(raw)
    return texts


def _node14_section():
    text = PIPELINE_MD.read_text(encoding="utf-8")
    match = re.search(r"^## 14\..*?(?=^## )", text, re.DOTALL | re.MULTILINE)
    return match.group(0) if match else ""


def _node14_rule_block(section):
    blocks = [
        judge.parse_block(block) for block in judge.extract_yaml_blocks(section)
    ]
    rule_blocks = [b for b in blocks if "stable_rule_update" in b.fields]
    return rule_blocks


class SkillMdContractSyncTest(unittest.TestCase):
    def test_skill_md_canonical_block_fields_match_judge(self):
        """SKILL.md 字段名变更（如 observation→findings）即红。"""
        canonical = _skill_postpublish_block()
        self.assertTrue(canonical, "SKILL.md 应存在四字段 canonical 状态块")
        for parsed in canonical:
            self.assertEqual(
                set(parsed.fields), set(judge.CONTRACT_FIELDS),
                "SKILL.md canonical 块字段与判官合同字段漂移",
            )

    def test_skill_md_declares_node14_alignment(self):
        """SKILL.md canonical 块须显式声明与 Node 14 对齐（同步锚点）。"""
        self.assertIn("editorial-pipeline.md Node 14", SKILL_MD.read_text(encoding="utf-8"))

    def test_persistence_default_in_judge_domain(self):
        """SKILL.md 默认值 not_run 必须在判官 persistence 值域内。"""
        canonical = _skill_postpublish_block()
        self.assertTrue(canonical)
        defaults = {judge.exact_value(p.fields["persistence"]) for p in canonical}
        for value in defaults:
            self.assertIn(
                value.lower(), judge.PERSISTENCE_VALUES,
                "SKILL.md persistence 默认值不在判官值域内",
            )


class Node14ContractSyncTest(unittest.TestCase):
    def test_node14_status_enum_matches_judge(self):
        """Node 14 枚举增删值（或判官值域私改）即红。"""
        section = _node14_section()
        self.assertTrue(section, "editorial-pipeline.md 应存在 Node 14 小节")
        match = re.search(r"^\s*status:\s*(.+)$", section, re.MULTILINE)
        self.assertTrue(match, "Node 14 应枚举 stable_rule_update.status 值")
        enum_in_doc = {
            value.strip() for value in match.group(1).split("|") if value.strip()
        }
        self.assertEqual(
            enum_in_doc, set(judge.STABLE_RULE_ENUM),
            "Node 14 status 枚举与判官值域漂移",
        )

    def test_node14_block_keys_cover_documented_subfields(self):
        """判官 DOCUMENTED_SUBFIELDS 的每个额外键都须在 Node 14 在档。"""
        rule_blocks = _node14_rule_block(_node14_section())
        self.assertTrue(rule_blocks, "Node 14 应含 stable_rule_update YAML 块")
        subkeys = set(rule_blocks[0].sub.get("stable_rule_update", {}))
        for key in judge.DOCUMENTED_SUBFIELDS:
            self.assertIn(
                key, subkeys,
                "判官放行的额外键 %s 未在 Node 14 块在档" % key,
            )

    def test_node14_promoted_thresholds_match_judge(self):
        """Node 14 promoted 升格阈值与判官常量漂移即红。"""
        section = _node14_section()
        replications = re.search(r"replications\s*>=\s*([0-9]+)", section)
        comparable = re.search(r"comparable_runs\s*>=\s*([0-9]+)", section)
        self.assertTrue(replications and comparable, "Node 14 应声明 promoted 阈值")
        self.assertEqual(int(replications.group(1)), judge.PROMOTED_MIN_REPLICATIONS)
        self.assertEqual(int(comparable.group(1)), judge.PROMOTED_MIN_COMPARABLE_RUNS)
        if judge.PROMOTED_COUNTEREXAMPLES_REQUIRED:
            self.assertRegex(
                section, r"counterexamples_checked:\s*true",
                "Node 14 应要求 counterexamples_checked: true",
            )

    def test_node14_keeps_persistence_not_run_guard(self):
        self.assertIn("persistence: not_run", _node14_section())


class JudgeAcceptanceSetTest(unittest.TestCase):
    """判官接受集的行为级锁定（scr-20260831-164237）：遍历 STABLE_RULE_ENUM
    实际调用 judge.judge 断言接受——判官校验逻辑回归（常量不动）时即红，
    hypothesis 值由此获得首个判官级行为用例。"""

    def test_judge_accepts_every_documented_enum_value(self):
        for value in judge.STABLE_RULE_ENUM:
            with self.subTest(stable_rule_update=value):
                code, branch, reason = judge.judge(_canonical_message_for(value))
                self.assertEqual((code, branch), (0, "canonical"), reason)

    def test_single_post_conflict_signals_do_not_hit_promoted_acceptance_sample(self):
        """冲突门作用域抽查：单篇冲突信号不得命中判官自有的 promoted 合法
        样例消息（恒真 NotIn 的行为化替代——信号词误扩到合法样例即红）。"""
        promoted_message = _canonical_message_for("promoted")
        for phrase in judge._SINGLE_POST_PHRASES:
            self.assertNotIn(phrase, promoted_message)
        self.assertIsNone(judge._SINGLE_POST_NUMERIC_RE.search(promoted_message))

    def test_skill_md_canonical_block_text_passes_judge(self):
        """SKILL.md canonical 块原文（非仅字段名集合）经判官接受：文档样例
        被漂移键污染或判官误拒文档样例时任一方向漂移即红。"""
        blocks = _skill_postpublish_block_texts()
        self.assertTrue(blocks, "SKILL.md 应存在四字段 canonical 状态块")
        for raw in blocks:
            message = "```yaml\n" + raw + "\n```\n\n无曝光量数据，打开率状态：not_available。\n"
            self.assertEqual(judge.check_canonical_block([raw], message), "")
            code, branch, reason = judge.judge(message)
            self.assertEqual((code, branch), (0, "canonical"), reason)


def _canonical_message_for(value):
    """按枚举值构造 canonical 消息：promoted 附 Node 14 嵌套三条件形态，
    其余值顶层直写；prose 补齐两分支共享内容门。"""
    if value == "promoted":
        lines = [
            "observation: 句式效应在三篇可比文章中稳定复现",
            "hypothesis: none",
            "stable_rule_update:",
            "  status: promoted",
            "  replications: 3",
            "  comparable_runs: 2",
            "  counterexamples_checked: true",
            "persistence: not_run",
        ]
    else:
        lines = [
            "observation: 单篇阅读 12 万，约为平时 3 倍",
            "hypothesis: none",
            "stable_rule_update: " + value,
            "persistence: not_run",
        ]
    return "```yaml\n" + "\n".join(lines) + "\n```\n\n无曝光量数据，打开率状态：not_available。\n"


if __name__ == "__main__":
    unittest.main()
