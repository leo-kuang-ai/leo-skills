"""风格推荐硬规则层测试（R-61 / R-62 接线件 / R-63 bypass 语义）。

覆盖：正反样本（学术答辩×复古潮流系等对抗样本）、党政锁定、投资人路演
偏好不锁定、儿童受众排除高攻击系、点名 bypass_all、未触发零输出、
确定性、阈值边界、lock/exclude 冲突消解、CLI 用法错误 exit 2、
--self-test、规则词表完整性（防家族名漂移）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import style_hard_rules as shr  # noqa: E402

SCRIPT_PATH = SCRIPTS_DIR / "style_hard_rules.py"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True, text=True,
    )


class EvaluateBehavior(unittest.TestCase):
    """evaluate() 纯函数层：正反样本与消解语义。"""

    def test_academic_defense_excludes_retro_and_locks_academic(self):
        out = shr.evaluate({"genre": "博士论文答辩", "domain": ["高校"]})
        self.assertIn("academic-defense", out["triggered_rules"])
        for family in ("复古潮流", "波普孟菲斯", "高攻击"):
            self.assertIn(family, out["exclude_families"])
        self.assertIn("学术答辩", out["lock_families"])

    def test_party_gov_context_locks_party_red_family(self):
        out = shr.evaluate({"culture": "支部主题党日"})
        self.assertEqual(out["lock_families"], ["党政红"])
        self.assertIn("party-gov-lock", out["triggered_rules"])

    def test_named_style_bypasses_all_rules(self):
        out = shr.evaluate({"genre": "论文答辩", "named_style": "蒸汽波风"})
        self.assertTrue(out["bypassed"])
        self.assertIn("蒸汽波风", out["bypass_reason"])
        self.assertEqual(out["triggered_rules"], [])
        self.assertEqual(out["exclude_families"], [])
        self.assertEqual(out["lock_families"], [])
        self.assertEqual(out["prefer_families"], {})

    def test_untriggered_signals_produce_zero_output(self):
        out = shr.evaluate({"genre": "团队周会", "preferences": ["清爽一点"]})
        self.assertFalse(out["bypassed"])
        self.assertEqual(out["triggered_rules"], [])
        self.assertEqual(out["exclude_families"], [])
        self.assertEqual(out["lock_families"], [])
        self.assertEqual(out["prefer_families"], {})

    def test_investor_pitch_tech_boosts_tech_dark_without_locking(self):
        out = shr.evaluate({"genre": "融资路演", "domain": ["AI 大模型"]})
        self.assertIn("investor-pitch-tech", out["triggered_rules"])
        self.assertEqual(out["prefer_families"].get("科技暗色"), 1)
        self.assertEqual(out["lock_families"], [])

    def test_kids_audience_excludes_aggressive_families(self):
        out = shr.evaluate({"audience": "小学二年级学生"})
        self.assertIn("kids-education", out["triggered_rules"])
        self.assertIn("高攻击", out["exclude_families"])
        self.assertIn("卡通儿童", out["prefer_families"])

    def test_medical_domain_prefers_health_and_excludes_pop(self):
        out = shr.evaluate({"domain": ["临床试验"]})
        self.assertIn("医疗健康", out["prefer_families"])
        self.assertIn("波普孟菲斯", out["exclude_families"])

    def test_formality_threshold_respected(self):
        high = shr.evaluate({"genre": "年度述职汇报", "formality": 0.9})
        low = shr.evaluate({"genre": "年度述职汇报", "formality": 0.5})
        self.assertIn("board-formal-report", high["triggered_rules"])
        self.assertNotIn("board-formal-report", low["triggered_rules"])

    def test_data_pages_threshold_triggers_chart_family(self):
        out = shr.evaluate({"content_shape": {"data_pages": 0.7}})
        self.assertIn("数据图表", out["prefer_families"])
        zero = shr.evaluate({"content_shape": {"data_pages": 0.2}})
        self.assertNotIn("数据图表", zero["prefer_families"])

    def test_deterministic_output_for_same_input(self):
        brief = {"genre": "结题验收", "culture": "国风水墨", "formality": 0.85}
        self.assertEqual(shr.evaluate(brief), shr.evaluate(brief))

    def test_lock_beats_exclude_on_conflict(self):
        out = shr.evaluate({"genre": "课题中期检查", "culture": "国潮"})
        self.assertFalse(set(out["lock_families"]) & set(out["exclude_families"]))

    def test_list_and_scalar_domain_signals_both_match(self):
        scalar = shr.evaluate({"domain": "银行"})
        listing = shr.evaluate({"domain": ["银行", "零售"]})
        self.assertIn("金融审计", scalar["prefer_families"])
        self.assertIn("金融审计", listing["prefer_families"])

    def test_missing_or_invalid_formality_does_not_crash(self):
        out = shr.evaluate({"genre": "年度述职汇报"})
        self.assertNotIn("board-formal-report", out["triggered_rules"])
        out = shr.evaluate({"genre": "年度述职汇报", "formality": "很高"})
        self.assertNotIn("board-formal-report", out["triggered_rules"])


class VocabularyIntegrity(unittest.TestCase):
    """规则词表防漂移：家族引用有效、id 唯一、条数在设计区间。"""

    def test_rule_ids_unique(self):
        ids = [r["id"] for r in shr.RULES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_rule_count_within_design_band(self):
        self.assertGreaterEqual(len(shr.RULES), 15)
        self.assertLessEqual(len(shr.RULES), 25)

    def test_all_rule_effects_reference_declared_families(self):
        for rule in shr.RULES:
            for key in ("exclude", "lock", "prefer"):
                for family in rule.get(key, []):
                    self.assertIn(family, shr.FAMILIES,
                                  f"rule {rule['id']} 引用未声明家族 {family}")

    def test_builtin_brief_styles_covered_by_some_family(self):
        # 顶层 11 内置风格必须至少归属一个家族，否则规则层对其"失明"。
        builtin = {"党政红风格", "创意杂志风", "复古扁平插画风", "手绘技术解释风",
                   "手绘白板风", "教学课件风", "数据仪表盘风", "清爽专业风",
                   "温暖手工风", "电子墨水杂志风", "科研答辩风"}
        covered = {s for members in shr.FAMILIES.values() for s in members}
        self.assertEqual(builtin - covered, set(),
                         f"内置风格未被任何家族收录: {builtin - covered}")

    def test_k12_family_covers_online_education_master_style(self):
        # R-66：在线教育风并入互联网产品风簇后，主风格必须留在教学课件
        # prefer 池内，否则 k12-courseware 语境对合并后主风格失明。
        self.assertIn("互联网产品风", shr.FAMILIES["教学课件"])
        out = shr.evaluate({"genre": "课件"})
        self.assertIn("教学课件", out["prefer_families"])
        self.assertIn("k12-courseware", out["triggered_rules"])

    def test_finance_family_covers_report_variant_master_style(self):
        # R-66：财报季报风并入商业计划书风簇后，主风格必须留在金融审计
        # prefer 池内，否则 finance-audit 语境对合并后主风格失明。
        self.assertIn("商业计划书风", shr.FAMILIES["金融审计"])
        out = shr.evaluate({"domain": ["银行"]})
        self.assertIn("金融审计", out["prefer_families"])
        self.assertIn("finance-audit", out["triggered_rules"])


class CliContract(unittest.TestCase):
    """CLI 契约：exit 0/2、stdout 可解析 JSON、--self-test。"""

    def test_check_brief_outputs_parseable_json(self):
        proc = run_cli("--check-brief", json.dumps({"genre": "论文答辩"}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertIn("学术答辩", out["lock_families"])
        self.assertIn("复古潮流", out["exclude_families"])

    def test_self_test_passes_via_cli(self):
        proc = run_cli("--self-test")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("self-test OK", proc.stdout)

    def test_invalid_json_exits_two(self):
        proc = run_cli("--check-brief", "not-json")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("brief_json_invalid", proc.stderr)

    def test_non_object_json_exits_two(self):
        proc = run_cli("--check-brief", "[1,2]")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("brief_json_not_object", proc.stderr)

    def test_missing_mode_argument_exits_two(self):
        proc = run_cli()
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
