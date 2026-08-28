#!/usr/bin/env python3
"""slide-worker.md prompt 合同锚点断言（P2-7 要点-容器落位声明）。

验证 worker prompt 的自查清单包含落位声明锚点，且 qa_note 规则含重做场景的
目标判据 + 波及面双结论要求。文本锚点被删除或改写时此测试先于行为评测失败。
"""
import unittest
from pathlib import Path

PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "slide-worker.md"


class WorkerPromptContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PROMPT.read_text(encoding="utf-8")

    def test_container_mapping_self_check_anchor(self):
        """自查清单必须包含要点-容器落位声明句。"""
        self.assertIn(
            "maps into a distinct on-canvas container", self.text,
            "slide-worker.md 缺少要点-容器落位自查锚点（P2-7）",
        )

    def test_qa_note_retry_contract_anchor(self):
        """qa_note 规则必须包含重做场景双结论要求。"""
        self.assertIn(
            "target-check verdict AND spillover-check verdict", self.text,
            "slide-worker.md 缺少 qa_note 双结论锚点（P0-2 worker 侧）",
        )


if __name__ == "__main__":
    unittest.main()
