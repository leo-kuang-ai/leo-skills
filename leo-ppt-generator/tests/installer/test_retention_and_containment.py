"""U1 保留策略核心回归：prune-backups / prune-runtimes 的行为与 containment 纪律。

直接以文件路径加载 vendored-adjacent 的 scripts/runtime_manager.py（非包内模块），
在临时目录中构造备份/runtime 形态，验证 R1/R2：
- 保留计数与体积报告；
- 符号链接等异常候选触发整批放弃并告警（无一删除）；
- current 引用的 runtime 恒被排除，rollback 可用性下限恒成立；
- 零边界：不超上限时零删除。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SKILL_DIR = TEST_DIR.parents[1]
MANAGER_PATH = SKILL_DIR / "scripts" / "runtime_manager.py"

_spec = importlib.util.spec_from_file_location("runtime_manager_under_test", MANAGER_PATH)
assert _spec is not None and _spec.loader is not None
rtm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rtm)

HEX_CHARS = set("0123456789abcdef")


def make_dir_with_payload(root: Path, name: str, payload_bytes: int) -> Path:
    target = root / name
    target.mkdir(parents=True)
    (target / "payload.bin").write_bytes(b"x" * payload_bytes)
    return target


def stagger_mtime(path: Path, age_rank: int) -> None:
    """age_rank 越大越旧，保证 mtime 顺序稳定可断言。"""
    stamp = time.time() - age_rank * 3600
    os.utime(path, (stamp, stamp))


class PruneBackupsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / ".leo-ppt-generator-backups"
        self.root.mkdir()

    def test_keeps_newest_three_and_reports_freed_bytes(self):
        names = {}
        expected_removed = 0
        for rank, stamp in enumerate(["a-old", "b-mid", "c-new", "d-new", "e-new"]):
            size = 100 + rank
            path = make_dir_with_payload(self.root, f"20260801T000000Z-{stamp}", size)
            stagger_mtime(path, 100 - rank)  # 列表顺序 = 从最老到最新
            if rank < 2:
                expected_removed += size
            names[stamp] = path
        result = rtm.prune_backups(self.root, keep_newest=3)
        remaining = sorted(p.name for p in self.root.iterdir())
        self.assertEqual(len(remaining), 3)
        self.assertEqual(result["removed_count"], 2)
        self.assertEqual(result["total_bytes_freed"], expected_removed)
        self.assertIsNone(result["aborted_reason"])
        # 被删的恰是最老两份
        for stale in ("a-old", "b-mid"):
            prefix = f"20260801T000000Z-{stale}"
            self.assertFalse((self.root / prefix).exists())

    def test_symlink_anomaly_aborts_entire_batch_without_deletion(self):
        real = make_dir_with_payload(self.root, "20260801T000000Z-real", 50)
        stagger_mtime(real, 9)  # 最老，若无熔断必被删
        outside_target = make_dir_with_payload(
            Path(self._tmp.name), "outside-target", 10_000
        )
        link = self.root / "20260802T000000Z-link"
        os.symlink(outside_target, link)
        for extra in range(5):
            p = make_dir_with_payload(self.root, f"20260803T00000{extra}Z-x{extra}", 10)
            stagger_mtime(p, extra)
        result = rtm.prune_backups(self.root, keep_newest=3)
        self.assertEqual(result["aborted_reason"], "symlink_or_non_dir")
        self.assertEqual(result["removed_count"], 0)
        self.assertTrue(real.exists(), "整批放弃后原候选必须全部完好")
        self.assertTrue(link.is_symlink())
        self.assertTrue(outside_target.exists(), "外部目标绝不能被波及")

    def test_zero_boundary_when_under_cap(self):
        for rank in range(2):
            p = make_dir_with_payload(self.root, f"2026080{rank+1}T000000Z-k{rank}", 7)
            stagger_mtime(p, rank)
        result = rtm.prune_backups(self.root, keep_newest=3)
        self.assertEqual(result["removed_count"], 0)
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_missing_root_is_noop(self):
        result = rtm.prune_backups(self.root / "absent", keep_newest=3)
        self.assertEqual(result["removed_count"], 0)


class PruneRuntimesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.runtimes = self.home / "runtimes"
        self.runtimes.mkdir()
        self.current_path = self.home / "current"
        self.manager = self._make_manager()
        self.identity_seq = iter("0123456789abcdef")

    def _make_manager(self) -> Any:
        bundle = self.home / "bundle"
        (bundle / "runtime").mkdir(parents=True, exist_ok=True)
        return rtm.RuntimeManager(bundle_root=bundle, home=self.home)

    def _new_identity_name(self) -> str:
        return next(self.identity_seq) * 32

    def _set_current(self, identity: str | None) -> None:
        if identity is None:
            self.current_path.write_text("", encoding="utf-8")
        else:
            self.current_path.write_text(
                json.dumps({"runtime_identity": identity}), encoding="utf-8"
            )

    def test_prunes_oldest_beyond_two_and_never_touches_current(self):
        names = []
        for rank in range(4):
            identity = self._new_identity_name()
            path = make_dir_with_payload(self.runtimes, identity, 40 + rank)
            stagger_mtime(path, 100 - rank)  # names[0] 最老，names[-1] 最新
            names.append(identity)
        self._set_current(names[-1])  # newest 为 current
        result = self.manager.prune_runtimes(keep_newest=2)
        remaining = {p.name for p in self.runtimes.iterdir()}
        # 候选 = 非 current 的 3 个；保留其中最新 2 个，删除唯 1 个最老
        self.assertEqual(remaining, set(names) - {names[0]})
        self.assertIn(names[-1], remaining, "current 所指 runtime 必须保留")
        self.assertEqual(result["removed_count"], 1)

    def test_current_is_excluded_even_when_it_is_the_oldest(self):
        identities = [self._new_identity_name() for _ in range(3)]
        for rank, identity in enumerate(identities):
            path = make_dir_with_payload(self.runtimes, identity, 10)
            stagger_mtime(path, 100 + rank)  # identities[0] 最老
        self._set_current(identities[0])  # current 同时最老
        result = self.manager.prune_runtimes(keep_newest=2)
        remaining = {p.name for p in self.runtimes.iterdir()}
        self.assertIn(identities[0], remaining, "最老的 current 也被排除在候选之外")
        self.assertEqual(remaining - {identities[0]}, set(identities[1:]))

    def test_unreadable_current_aborts_fail_closed(self):
        identity = self._new_identity_name()
        make_dir_with_payload(self.runtimes, identity, 10)
        self.current_path.write_text("{not-json", encoding="utf-8")
        result = self.manager.prune_runtimes(keep_newest=2)
        self.assertIsNotNone(result["aborted_reason"])
        self.assertTrue(self.runtimes.joinpath(identity).exists())

    def test_quarantine_and_staging_entries_are_not_candidates(self):
        leftover = self.runtimes / f".{self._new_identity_name()}.20260101.install"
        make_dir_with_payload(leftover.parent, leftover.name, 5)
        good = make_dir_with_payload(self.runtimes, self._new_identity_name(), 10)
        self._set_current(good.name)
        result = self.manager.prune_runtimes(keep_newest=2)
        self.assertTrue(leftover.exists(), "非 hex 命名的杂项不属于剪裁候选")
        self.assertEqual(result["removed_count"], 0)


class MainProtocolTest(unittest.TestCase):
    def test_main_prune_backups_emits_json_and_zero_exit_on_abort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "backups"
            root.mkdir()
            link_target = Path(tmp) / "outside"
            make_dir_with_payload(Path(tmp), "outside", 10)
            os.symlink(link_target, root / "link-entry")
            exit_code = rtm.main(["prune-backups", "--root", str(root), "--keep-newest", "3"])
            self.assertEqual(exit_code, 0)
            # aborted 时 stderr 有告警；stdout JSON 留给调用方解析

    def test_main_unknown_kind_rejected(self):
        with self.assertRaises(SystemExit):
            rtm.main(["prune"])


if __name__ == "__main__":
    unittest.main()
