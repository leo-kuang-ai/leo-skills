"""Judge-script replay regression tests.

每个用例把一份冻结的历史真实响应或合成正/负样本回放到对应的
``evals/scripts/check-*.sh`` 判官，并断言退出码。纪律来源（known-issues.md，
2026-08-27）：收紧判定必须附带历史响应重放——本文件把该纪律机器化，后续
修改任何判官后直接跑 ``python3 -m unittest discover -s evidence-first-writing/tests``。

``expect=0`` 的真实 fixture 是历史 PASS 响应或已确认「实质合规、仅词汇漂移」
的响应（判官接受集已按同义词收口）；``expect=1`` 的负样本覆盖各判官的关键
拦截门。新增判官门禁或收紧词表时，必须先确认本文件全部通过。
"""

import os
import subprocess
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "evals" / "scripts"
FIXTURES_DIR = SKILL_DIR / "tests" / "fixtures" / "judge_replay"

# (judge script, fixture, expected exit code)
CASES = [
    # check-audit-readonly.sh
    ("check-audit-readonly.sh", "audit__it51_pass.md", 0),
    # 2026-08-27 词汇漂移锚点：标签用「证据：」，实质逐字引用原句，必须放行
    ("check-audit-readonly.sh", "audit__it55_label_drift.md", 0),
    ("check-audit-readonly.sh", "audit__syn_no_evidence_label.md", 1),
    ("check-audit-readonly.sh", "audit__syn_rewrite_trespass.md", 1),
    # check-causal-boundary.sh
    ("check-causal-boundary.sh", "causal__it51_pass.md", 0),
    # 已知假阴性教训：情态词与动词间插入宾语（无法**将这一下降**归因于）
    ("check-causal-boundary.sh", "causal__syn_modal_insertion.md", 0),
    ("check-causal-boundary.sh", "causal__syn_overclaim.md", 1),
    # check-post-publish-boundary.sh
    ("check-post-publish-boundary.sh", "postpublish__it51_pass.md", 0),
    # known-issues 记录的自发合同词汇缺口样本（四轮稳定 FAIL 的其中一轮）
    ("check-post-publish-boundary.sh", "postpublish__it54_unprompted_vocabulary_gap.md", 1),
    ("check-post-publish-boundary.sh", "postpublish__syn_overclaim.md", 1),
    # check-dev-edit-first.sh
    ("check-dev-edit-first.sh", "devedit__syn_pass.md", 0),
    ("check-dev-edit-first.sh", "devedit__syn_style_first.md", 1),
    # check-independent-review-status.sh
    ("check-independent-review-status.sh", "indepreview__syn_not_run.md", 0),
    ("check-independent-review-status.sh", "indepreview__syn_claims_passed.md", 1),
    # check-formal-report-route.sh
    ("check-formal-report-route.sh", "formalreport__syn_pass.md", 0),
    ("check-formal-report-route.sh", "formalreport__syn_route_pollution.md", 1),
]


class JudgeScriptReplayTest(unittest.TestCase):
    def test_judge_replay_matrix(self):
        for script, fixture, expected in CASES:
            with self.subTest(judge=script, fixture=fixture):
                message = (FIXTURES_DIR / fixture).read_text(encoding="utf-8")
                env = dict(os.environ, EVAL_FINAL_MESSAGE=message)
                proc = subprocess.run(
                    ["bash", str(SCRIPTS_DIR / script)],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertEqual(
                    proc.returncode,
                    expected,
                    f"{script} 对 {fixture} 期望退出码 {expected}，"
                    f"实际 {proc.returncode}；stderr: {proc.stderr.strip()}",
                )


if __name__ == "__main__":
    unittest.main()
