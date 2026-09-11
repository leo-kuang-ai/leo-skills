"""U1/F6：24 题推荐评测 fixture 的结构完整性（冻结纪律）。

检查项（对应方案 F6 验收）：
  - 恰好 24 题，八方向各三题；
  - 每题标签 acceptable/preferred/unsuitable 非空，preferred ⊆ acceptable，
    preferred ∩ unsuitable = ∅；
  - 至少八组成对任务（pair_id + disjoint_preferred）首选集合不相交；
  - 不存在对全部 24 题都可接受的单一风格；
  - 标签引用的风格旧名全部能经迁移账本映射到稳定 ID；
  - 基线含两轮输出且逐字节一致；基线记录了每题的规则层结论。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = SKILL_DIR / "evals" / "fixtures" / "template-quality"
LEDGER_PATH = SKILL_DIR / "template-library" / "governance" / "migration" / "asset-ledger.json"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class TemplateRecommendationFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tasks_doc = _load("recommendation-tasks.json")
        cls.labels_doc = _load("recommendation-labels.json")
        cls.baseline = _load("recommendation-baseline.json")
        cls.ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        cls.tasks = {task["task_id"]: task for task in cls.tasks_doc["tasks"]}
        cls.labels = {label["task_id"]: label for label in cls.labels_doc["labels"]}

    def test_exactly_24_tasks_across_8_directions(self) -> None:
        self.assertEqual(len(self.tasks), 24)
        self.assertEqual(len(self.tasks_doc["directions"]), 8)
        for direction in self.tasks_doc["directions"]:
            count = sum(1 for task in self.tasks.values() if task["direction"] == direction)
            self.assertEqual(count, 3, f"direction {direction} has {count} tasks, want 3")

    def test_condition_coverage_audience_density_environment(self) -> None:
        conditions = [task["condition"] for task in self.tasks.values()]
        self.assertGreaterEqual(
            sum(c.startswith("audience-") for c in conditions), 8,
            "需要至少 8 个受众对照条件")
        self.assertTrue(any("density" in c for c in conditions), "缺密度对照条件")
        self.assertGreaterEqual(
            sum("environment" in c or "screen" in c for c in conditions), 3,
            "缺展示环境变化条件")

    def test_labels_complete_and_consistent(self) -> None:
        self.assertEqual(set(self.tasks), set(self.labels))
        for task_id, label in self.labels.items():
            for field in ("acceptable", "preferred", "unsuitable"):
                self.assertTrue(label[field], f"{task_id}.{field} 为空")
            self.assertTrue(label.get("rationale"), f"{task_id} 缺理由")
            self.assertTrue(label.get("label_source") or self.labels_doc.get("label_source"))
            extra = set(label["preferred"]) - set(label["acceptable"])
            self.assertFalse(extra, f"{task_id} preferred 越出 acceptable: {extra}")
            overlap = set(label["preferred"]) & set(label["unsuitable"])
            self.assertFalse(overlap, f"{task_id} preferred 与 unsuitable 相交: {overlap}")

    def test_at_least_8_disjoint_preferred_pairs(self) -> None:
        groups: dict[str, list[dict]] = {}
        for task in self.tasks.values():
            groups.setdefault(task["pair_id"], []).append(task)
        # pair_id 命名约定：*-a 为双题成对（受众对照），*-b 为单题环境/密度变体。
        paired = {pid: members for pid, members in groups.items() if len(members) >= 2}
        self.assertGreaterEqual(len(paired), 8, "成对任务组不足 8 组")
        disjoint_pairs = 0
        for pair_id, members in sorted(paired.items()):
            preferred = [set(self.labels[m["task_id"]]["preferred"]) for m in members]
            if all(not preferred[0] & other for other in preferred[1:]):
                disjoint_pairs += 1
        self.assertGreaterEqual(
            disjoint_pairs, 8,
            f"不相交首选集合的成对任务只有 {disjoint_pairs} 组，需 ≥8")

    def test_no_single_style_acceptable_everywhere(self) -> None:
        from collections import Counter
        counter: Counter[str] = Counter()
        for label in self.labels.values():
            counter.update(label["acceptable"])
        universal = [name for name, count in counter.items() if count == 24]
        self.assertFalse(universal, f"存在全题可接受风格: {universal}")

    def test_label_styles_map_to_stable_ids(self) -> None:
        # 稳定 ID 真值源是 template-library（账本只覆盖旧树迁移条目；行业
        # 皮肤等新作者资产没有旧名，直接以库内 brief 的 asset_id 为准）。
        styles_root = SKILL_DIR / "template-library" / "canonical" / "styles"
        name_to_id = {
            brief["name"]: brief["asset_id"]
            for brief in (json.loads(p.read_text(encoding="utf-8"))
                          for p in styles_root.glob("*/brief.json"))
        }
        ledger_names = {entry["current_name"] for entry in self.ledger["entries"]
                        if "current_name" in entry}
        self.assertLessEqual(ledger_names - set(name_to_id), set(),
                             "账本旧名存在库中缺失的映射")
        for task_id, label in self.labels.items():
            for field in ("acceptable", "preferred", "unsuitable"):
                for name in label[field]:
                    self.assertIn(
                        name, name_to_id,
                        f"{task_id}.{field} 引用的风格 {name!r} 无稳定 ID 映射")

    def test_baseline_two_identical_rounds_all_tasks(self) -> None:
        self.assertEqual(len(self.baseline["rounds"]), 2)
        self.assertEqual(self.baseline["rounds"][0], self.baseline["rounds"][1],
                         "两轮基线输出不一致")
        self.assertEqual(set(self.baseline["rounds"][0]), set(self.tasks))
        for task_id, output in self.baseline["rounds"][0].items():
            self.assertIn("evaluate", output, f"{task_id} 缺规则层结论")
            self.assertIn("triggered_rules", output["evaluate"])


if __name__ == "__main__":
    unittest.main()
