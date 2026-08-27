"""Patch 0002 聚焦回归：editable 状态写入的原子化与并发锁。

直接对 vendored `deck_run_state` 单元做边界测试（工作流 Agent 才被禁止 import
`_vendor`；本文件的目的恰是证明补丁后的 vendor 行为）。唯一外部依赖 `filelock`
是 `runtime/pyproject.toml` 已声明的运行时依赖。
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

deck_run_state = None
_IMPORT_ERROR = None
try:
    from leo_ppt_generator._vendor.editable_ppt.editppt.runtime import deck_run_state
except ImportError as exc:  # pragma: no cover - 环境缺依赖时的诚实降级
    _IMPORT_ERROR = exc

THREADS = 8
UPDATES_PER_THREAD = 25


def run_concurrent_record_updates(state_path, threads, updates_per_thread):
    """threads 个 worker 并发对同一状态文件做读-改-写，返回非预期异常列表。"""
    state_path.write_text(
        json.dumps({"revision": 0, "events": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    errors = []

    def worker(tid):
        try:
            for seq in range(updates_per_thread):
                with deck_run_state.locked_json(state_path) as data:
                    # FileLock 序列化临界区 + 原子替换，并发追加不得丢事件。
                    data.setdefault("events", []).append({"thread": tid, "seq": seq})
        except Exception as exc:  # noqa: BLE001 - 测试需要收集任意异常类型
            errors.append(exc)

    workers = [threading.Thread(target=worker, args=(tid,)) for tid in range(threads)]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join()
    return errors


@unittest.skipIf(deck_run_state is None, f"filelock 未安装，无法驱动 vendor 锁：{_IMPORT_ERROR}")
class VendorLockedStateTest(unittest.TestCase):
    def test_vendor_locked_state_serializes_concurrent_record_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "run_state.json"
            errors = run_concurrent_record_updates(state_path, THREADS, UPDATES_PER_THREAD)
            self.assertEqual(errors, [], f"并发更新出现异常: {errors}")

            final = json.loads(state_path.read_text(encoding="utf-8"))
            expected = THREADS * UPDATES_PER_THREAD
            # 无事件丢失、无重复：证明写入被串行化而非交错覆盖
            seen = [(event["thread"], event["seq"]) for event in final["events"]]
            self.assertEqual(len(seen), expected)
            self.assertEqual(len(set(seen)), expected)
            # 每次成功更新恰好递增一次 revision
            self.assertEqual(final["revision"], expected)
            # 原子替换不留 .tmp 残留
            self.assertEqual(list(Path(tmp).glob(".run_state.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
