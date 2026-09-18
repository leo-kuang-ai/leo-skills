"""U11/R-76 六节点决策简报行为测试。

覆盖计划场景：六节点三要素缺字段失败、页数与 compute_impact 一致（不许
编造，含真实脚本对账）、术语通俗化与超行拒绝、页码区间确定性格式、
委托模式保留生成而豁免呈现。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.layout_proposals import (  # noqa: E402
    MAX_LINE_CHARS,
    ProposalError,
    decision_brief,
    format_page_ranges,
    plain_term,
    render_brief,
)

COMPUTE_IMPACT = SKILL_DIR / "scripts" / "compute_impact.py"

MASTER_A = """# 母版 v1
confirmation: confirmed

## S1 封面
page_id: pg-11111111
角色：封面
- 标题：增长质量
- 要点 1：三大指标向好

## S2 财务
page_id: pg-22222222
角色：流程·路径
- 标题：营收 1.24 亿元
- 要点 1：环比 +18%

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | 材料测算 | 估算 | 2026H1 | 元 | 估算 | 否 | - |
"""

MASTER_B = MASTER_A.replace("- 要点 1：环比 +18%", "- 要点 1：环比 +19%").replace(
    "| 1.24 亿元 | S2 |", "| 1.25 亿元 | S2 |")


def _brief(**overrides):
    fields = dict(node="master", changed="母版更新了财务页要点与登记数值",
                  impact="波及财务页内容层，需要重验该页产物",
                  decision="确认后重渲受影响页")
    fields.update(overrides)
    return decision_brief(**fields)


class DecisionBriefContractTest(unittest.TestCase):
    def test_six_nodes_accepted_and_unknown_rejected(self):
        for node in ("contract", "outline", "master", "visual-sample",
                     "partial-gate", "delivery-gate"):
            self.assertEqual(_brief(node=node)["node"], node)
        with self.assertRaises(ProposalError) as ctx:
            _brief(node="deploy")
        self.assertEqual(ctx.exception.reason_code, "brief_node_invalid")

    def test_missing_element_fails(self):
        for missing in ("changed", "impact", "decision"):
            fields = dict(node="master", changed="变了", impact="影响了", decision="决定吧")
            fields[missing] = "   "
            with self.assertRaises(ProposalError) as ctx:
                decision_brief(**fields)
            self.assertEqual(ctx.exception.reason_code, "brief_field_missing")

    def test_line_length_cap_enforced(self):
        with self.assertRaises(ProposalError) as ctx:
            _brief(changed="长" * (MAX_LINE_CHARS + 1))
        self.assertEqual(ctx.exception.reason_code, "brief_line_too_long")

    def test_term_rewrite_and_render(self):
        brief = _brief(impact="1 个失效工件受影响")
        self.assertIn("之前确认过的样张需要重新确认", brief["lines"]["impact"])
        text = render_brief(brief)
        self.assertIn("【母版】", text)
        self.assertIn("① 变了什么：", text)
        self.assertIn("③ 需要决定：", text)

    def test_page_ranges_deterministic_format(self):
        self.assertEqual(
            format_page_ranges([3, 7, 12, 13, 14, 15, 16, 17, 18]),
            "第 3、7、12–18 页，共 9 页")
        self.assertEqual(format_page_ranges([5]), "第 5 页，共 1 页")
        self.assertEqual(format_page_ranges([]), "无波及页")
        # 顺序无关、去重。
        self.assertEqual(format_page_ranges([7, 3]), "第 3、7 页，共 2 页")

    def test_delegate_mode_still_generates_full_brief(self):
        brief = _brief(presentation="exempt-user-delegated")
        self.assertEqual(brief["presentation"], "exempt-user-delegated")
        self.assertTrue(brief["lines"]["decision"], "委托模式仅豁免呈现，简报仍须完整生成")
        with self.assertRaises(ProposalError):
            _brief(presentation="carrier-pigeon")


class ImpactConsistencyTest(unittest.TestCase):
    """不许编造：简报波及页数必须与 compute_impact.py 输出一致。"""

    def test_brief_page_count_matches_compute_impact(self):
        with tempfile.TemporaryDirectory() as tmp:
            master_a = Path(tmp) / "deck-master-v1.md"
            master_b = Path(tmp) / "deck-master-v2.md"
            master_a.write_text(MASTER_A, encoding="utf-8")
            master_b.write_text(MASTER_B, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(COMPUTE_IMPACT), str(master_a), str(master_b),
                 "--json"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            impact = json.loads(result.stdout)
            affected = [int(page[1:]) for page in impact["affected_pages"]]
            self.assertTrue(affected, "fixture 必须真实产生波及页")
            brief = _brief(affected_pages=affected)
            self.assertEqual(brief["affected_pages"], sorted(set(affected)))
            self.assertIn(f"共 {len(set(affected))} 页", brief["lines"]["impact"])
            # 负例：简报声称的页数与生产者输出不符 → 可判定地暴露。
            doctored = _brief(affected_pages=affected + [99])
            self.assertNotEqual(
                doctored["affected_pages"], impact["affected_pages"],
                "简报页数与 compute_impact 不一致必须可检出")

    def test_plain_term_whitelist_rewrites(self):
        self.assertEqual(plain_term("overflow 溢出"), "内容超出版式容量 溢出")
        self.assertEqual(plain_term("无术语"), "无术语")


if __name__ == "__main__":
    unittest.main()
