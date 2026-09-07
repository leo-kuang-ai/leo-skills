"""聚焦回归（加固方案 WS4 最小实）：母版 delivery_tier 字段。"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "check_master_contract.py"

MINIMAL_MASTER = """# deck-master-v1（tier 用例）
confirmation: confirmed

## S1 封面（页面角色：开场）
argument_role：背景
- 标题：开场页
- 要点1：唯一要点
- 视觉行：容器=标题区；要点1→标题区
- 备注 speaker_script：开场。
- 备注 engineering：无。

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
"""


def _check(text: str) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    return subprocess.run([sys.executable, str(SCRIPT), path],
                          capture_output=True, text=True, timeout=60)


class DeliveryTierTest(unittest.TestCase):
    # 退出码合同：0 通过 / 1 FAIL / 2 仅 WARN（本夹具会触发反方承载 WARN，
    # 故非失败用例接受 {0, 2}）。

    def test_legal_tier_reported(self):
        result = _check("delivery_tier: minimal\n" + MINIMAL_MASTER)
        self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
        self.assertIn("DELIVERY-TIER: minimal", result.stdout)

    def test_illegal_tier_fails(self):
        result = _check("delivery_tier: turbo\n" + MINIMAL_MASTER)
        self.assertEqual(result.returncode, 1)
        self.assertIn("delivery_tier 非法", result.stderr)

    def test_absent_tier_defaults_standard_without_new_warning(self):
        result = _check(MINIMAL_MASTER)
        # 缺省档不得新增 WARN（不改变存量退出码语义）。
        self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
        self.assertIn("DELIVERY-TIER: standard (default)", result.stdout)
        self.assertNotIn("未声明 delivery_tier", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
