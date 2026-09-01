#!/usr/bin/env python3
"""expire_candidates.py 单元测试（R-45 候选过期标记）：新基线后旧候选入清单 /
无候选 exit 0 干净 / 重复运行幂等 / post-confirm 链成员不标 / pending 退回
版本不当过期基线 / outline 按自身序列判过期（跨系列不误伤）/ baseline 头部
标记的非版本化候选（style-candidates、sample-b 方向）判定 / 无 confirmed 基线
exit 2 / --list 只读不写。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "expire_candidates.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8")


class ExpireCandidatesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.content = self.root / "content"
        self.content.mkdir()
        self.manifest = self.content / "expired-candidates.json"

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text, parent=None):
        target = (parent or self.content) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def confirmed_master(self, version):
        return self.write(
            f"deck-master-v{version}.md",
            f"# 母版 v{version}\nconfirmation: confirmed\n\n## S1\n- 要点\n")

    def test_baseline_advance_expires_old_candidates(self):
        self.confirmed_master(3)
        # outline 系列按自身序列判：v2 为最高 confirmed 大纲，v1 过期、v2 不标。
        self.write("outline-v2.md", "confirmation: confirmed\n# 大纲 v2\n")
        self.write("outline-v1.md", "confirmation: confirmed\n# 大纲 v1\n")
        self.write("deck-master-v1.md", "confirmation: confirmed\n# 母版 v1\n")
        proc = run("--project-root", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["baseline_master"], "deck-master-v3.md")
        files = [item["file"] for item in payload["expired"]]
        self.assertIn("outline-v1.md", files)
        self.assertNotIn("outline-v2.md", files)
        self.assertIn("deck-master-v1.md", files)
        self.assertNotIn("deck-master-v3.md", files)
        # 原文件不被改动（最小侵入：只写清单）。
        self.assertEqual(
            (self.content / "outline-v1.md").read_text(encoding="utf-8"),
            "confirmation: confirmed\n# 大纲 v1\n")

    def test_no_candidates_exit_zero_clean(self):
        self.confirmed_master(2)
        proc = run("--project-root", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["expired"], [])
        self.assertEqual(payload["baseline_version"], 2)

    def test_rerun_idempotent_manifest_byte_stable(self):
        self.confirmed_master(3)
        self.write("outline-v2.md", "confirmation: pending\n# 大纲 v2\n")
        first = run("--project-root", str(self.root))
        self.assertEqual(first.returncode, 0, first.stderr)
        raw_first = self.manifest.read_bytes()
        second = run("--project-root", str(self.root))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.manifest.read_bytes(), raw_first)

    def test_post_confirm_chain_members_not_expired(self):
        # v4 继承 v3 的 confirmed（post-confirm 链，无显式 pending），链成员属
        # 当前基线不标；链外的 v2 旧母版与旧大纲过期。
        self.write("deck-master-v3.md",
                   "confirmation: confirmed\n# 母版 v3\n")
        self.write("deck-master-v4.md",
                   "revision_kind: post-confirm\n# v4 写回\n")
        self.write("deck-master-v2.md",
                   "confirmation: confirmed\n# 母版 v2\n")
        self.write("outline-v2.md", "confirmation: confirmed\n# 大纲 v2\n")
        self.write("outline-v1.md", "confirmation: confirmed\n# 大纲 v1\n")
        proc = run("--project-root", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["baseline_master"], "deck-master-v4.md")
        files = [item["file"] for item in payload["expired"]]
        self.assertIn("deck-master-v2.md", files)
        self.assertIn("outline-v1.md", files)
        self.assertNotIn("deck-master-v3.md", files)
        self.assertNotIn("deck-master-v4.md", files)
        self.assertNotIn("outline-v2.md", files)

    def test_pending_rollback_not_baseline_truth(self):
        # 页数/结构变化退回待确认：v1 confirmed、v2 pending+post-confirm
        # → 过期基线回落 v1；v2 高于基线版本不标，但也绝不作基线。
        self.write("deck-master-v1.md",
                   "confirmation: confirmed\n# 母版 v1\n")
        self.write("deck-master-v2.md",
                   "confirmation: pending\nrevision_kind: post-confirm\n# v2 退回\n")
        proc = run("--project-root", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["baseline_master"], "deck-master-v1.md")
        self.assertEqual(payload["baseline_version"], 1)
        files = [item["file"] for item in payload["expired"]]
        self.assertNotIn("deck-master-v1.md", files)
        self.assertNotIn("deck-master-v2.md", files)

    def test_outline_series_not_judged_by_master_version(self):
        # 跨系列不误伤：母版基线 v5，大纲自身序列最高 confirmed 为 v3，
        # outline-v3 是最新确认大纲，不得按母版版本 5 判过期。
        self.confirmed_master(5)
        self.write("outline-v3.md", "confirmation: confirmed\n# 大纲 v3\n")
        self.write("outline-v1.md", "confirmation: confirmed\n# 大纲 v1\n")
        proc = run("--project-root", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        files = [item["file"] for item in payload["expired"]]
        self.assertNotIn("outline-v3.md", files)
        self.assertIn("outline-v1.md", files)
        outline = [i for i in payload["expired"] if i["file"] == "outline-v1.md"][0]
        self.assertEqual(outline["reason"], "低于大纲基线 v3")

    def test_outline_without_confirmed_series_not_guessed(self):
        # 无 confirmed 大纲（唯一大纲 pending）时对 outline 不猜测、不进清单。
        self.confirmed_master(3)
        self.write("outline-v2.md", "confirmation: pending\n# 大纲 v2 草稿\n")
        proc = run("--project-root", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        files = [item["file"] for item in payload["expired"]]
        self.assertNotIn("outline-v2.md", files)

    def test_baseline_marked_candidate_below_baseline_expires(self):
        # 非版本化候选（双样张落选方向 / 风格候选）以头部 baseline: vM 标记判定。
        self.confirmed_master(3)
        self.write("sample-b-方向.md", "baseline: v1\n# 落选方向\n")
        sc = self.content / "style-candidates"
        self.write("科技风-候选.md", "baseline: v2\n# 候选\n", parent=sc)
        self.write("无标记候选.md", "# 无版本信息，不猜测\n", parent=sc)
        proc = run("--project-root", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        files = [item["file"] for item in payload["expired"]]
        self.assertIn("sample-b-方向.md", files)
        self.assertIn("style-candidates/科技风-候选.md", files)
        self.assertNotIn("style-candidates/无标记候选.md", files)

    def test_no_confirmed_baseline_is_usage_error(self):
        self.write("deck-master-v1.md", "confirmation: pending\n# 草稿\n")
        proc = run("--project-root", str(self.root))
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.manifest.is_file())

    def test_list_mode_writes_nothing(self):
        self.confirmed_master(3)
        self.write("outline-v2.md", "confirmation: confirmed\n# 大纲 v2\n")
        self.write("outline-v1.md", "confirmation: confirmed\n# 大纲 v1\n")
        proc = run("--project-root", str(self.root), "--list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.manifest.is_file())
        self.assertIn("outline-v1.md", proc.stdout)
        self.assertNotIn("outline-v2.md", proc.stdout)
        self.assertIn("--list", proc.stdout)


if __name__ == "__main__":
    unittest.main()
