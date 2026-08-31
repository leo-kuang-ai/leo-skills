"""image_gen 429 退避与全局 QPS 限流的单元测试。

放置说明：放在 tests/ 根目录而非 tests/boundary/——boundary/ 收文档合同
锚点断言，本文件 import runtime vendored 脚本做行为单测，与
test_templates.py 的 runtime 行为测试同类。

覆盖：
  1. 仅 HTTP 429 触发指数退避（2/4/8s 三档），重试成功路径等待序列正确；
  2. 连续 429 超过三档后最终失败，且异常原样抛出（不被吞）；
  3. 非 429 错误立即失败，无重试、无等待；
  4. QPS 限流放行间隔不小于 1/qps，LEO_PPT_IMAGE_QPS 环境变量覆盖生效；
  5. 回归：正常成功路径（单次 generate 与 generate-batch）输出与改动前一致。
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
CODEX_PPT_DIR = (
    SKILL_DIR / "runtime" / "src" / "leo_ppt_generator" / "_vendor" / "codex_ppt"
)
if str(CODEX_PPT_DIR) not in sys.path:
    sys.path.insert(0, str(CODEX_PPT_DIR))

import image_gen  # noqa: E402

# Minimal valid 1x1 PNG.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd4"
    "0000000049454e44ae426082"
)
PNG_B64 = base64.b64encode(PNG_BYTES).decode("ascii")


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSleep:
    """Records wait durations; advances a paired FakeClock."""

    def __init__(self, clock: FakeClock) -> None:
        self.waits: list[float] = []
        self.clock = clock

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.clock.advance(seconds)


class RateLimitedError(Exception):
    """Mimics openai.RateLimitError surface: status_code == 429."""

    status_code = 429

    def __init__(self, message: str = "429 Too Many Requests") -> None:
        super().__init__(message)


class ServerError(Exception):
    """Mimics a non-429 HTTP failure."""

    status_code = 500

    def __init__(self) -> None:
        super().__init__("500 Internal Server Error")


class ScriptedCall:
    """Callable that replays scripted outcomes: exceptions or a return value."""

    def __init__(self, outcomes: list) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingLimiter:
    """Stand-in for the module-level limiter; never sleeps."""

    def __init__(self, wait: float = 0.0) -> None:
        self.wait = wait
        self.acquire_count = 0
        self.reserve_count = 0

    def acquire(self) -> None:
        self.acquire_count += 1

    def reserve(self) -> float:
        self.reserve_count += 1
        return self.wait


class IsRateLimitErrorTests(unittest.TestCase):
    def test_detects_429_by_status_code_class_name_and_message(self):
        self.assertTrue(image_gen._is_rate_limit_error(RateLimitedError()))
        self.assertTrue(
            image_gen._is_rate_limit_error(RuntimeError("HTTP 429: too many requests"))
        )
        self.assertTrue(image_gen._is_rate_limit_error(RuntimeError("rate limit hit")))

    def test_rejects_non_429_errors(self):
        self.assertFalse(image_gen._is_rate_limit_error(ServerError()))
        self.assertFalse(image_gen._is_rate_limit_error(ValueError("boom")))
        self.assertFalse(image_gen._is_rate_limit_error(TimeoutError("timed out")))


class RateLimitBackoffTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.sleep = FakeSleep(self.clock)
        self.limiter = RecordingLimiter()
        self._old_limiter = image_gen._RATE_LIMITER
        image_gen._RATE_LIMITER = self.limiter

    def tearDown(self):
        image_gen._RATE_LIMITER = self._old_limiter

    def test_two_429s_then_success_backs_off_and_retries(self):
        outcomes = [RateLimitedError(), RateLimitedError(), "ok"]
        script = ScriptedCall(outcomes)
        result = image_gen._call_rate_limited(script, sleep=self.sleep)
        self.assertEqual(result, "ok")
        self.assertEqual(script.calls, 3)
        # Only the backoff table prefix is consumed before success.
        self.assertEqual(self.sleep.waits, [2.0, 4.0])
        # Every attempt passes through the QPS limiter.
        self.assertEqual(self.limiter.acquire_count, 3)

    def test_backoff_ladder_is_2_4_8_seconds(self):
        self.assertEqual(tuple(image_gen.RATE_LIMIT_BACKOFF_SECONDS), (2.0, 4.0, 8.0))

    def test_persistent_429_exhausts_ladder_and_raises_original_error(self):
        final = RateLimitedError("429 still rate limited")
        outcomes = [RateLimitedError(), RateLimitedError(), RateLimitedError(), final]
        script = ScriptedCall(outcomes)
        with self.assertRaises(RateLimitedError) as ctx:
            image_gen._call_rate_limited(script, sleep=self.sleep)
        self.assertIs(ctx.exception, final)
        self.assertEqual(script.calls, 4)
        self.assertEqual(self.sleep.waits, [2.0, 4.0, 8.0])

    def test_non_429_error_fails_immediately_without_retry(self):
        script = ScriptedCall([ValueError("provider exploded")])
        with self.assertRaises(ValueError):
            image_gen._call_rate_limited(script, sleep=self.sleep)
        self.assertEqual(script.calls, 1)
        self.assertEqual(self.sleep.waits, [])
        self.assertEqual(self.limiter.acquire_count, 1)


class QpsLimiterTests(unittest.TestCase):
    def test_admission_spacing_never_exceeds_configured_qps(self):
        clock = FakeClock()
        limiter = image_gen._QpsLimiter(4, clock=clock)  # interval = 0.25s
        admitted_at = []
        for _ in range(10):
            wait = limiter.reserve()
            clock.advance(wait)  # simulate actually sleeping the reservation
            admitted_at.append(clock())
        for earlier, later in zip(admitted_at, admitted_at[1:]):
            self.assertGreaterEqual(later - earlier, 0.25 - 1e-9)

    def test_threaded_acquisition_respects_spacing(self):
        import threading

        clock = FakeClock()
        lock = threading.Lock()
        admitted: list[float] = []

        def worker() -> None:
            wait = limiter.reserve()
            with lock:
                # Simulate sleeping outside the limiter lock.
                admitted.append(clock() + wait)
                clock.advance(wait)

        limiter = image_gen._QpsLimiter(4, clock=clock)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        admitted.sort()
        for earlier, later in zip(admitted, admitted[1:]):
            self.assertGreaterEqual(later - earlier, 0.25 - 1e-9)

    def test_env_override_changes_configured_qps(self):
        old_env = os.environ.get(image_gen.IMAGE_QPS_ENV)
        old_limiter = image_gen._RATE_LIMITER
        try:
            os.environ[image_gen.IMAGE_QPS_ENV] = "10"
            image_gen._RATE_LIMITER = None
            limiter = image_gen._rate_limiter()
            self.assertAlmostEqual(limiter._interval, 0.1)

            os.environ[image_gen.IMAGE_QPS_ENV] = "not-a-number"
            image_gen._RATE_LIMITER = None
            limiter = image_gen._rate_limiter()
            self.assertAlmostEqual(limiter._interval, 1.0 / image_gen.DEFAULT_IMAGE_QPS)
        finally:
            if old_env is None:
                os.environ.pop(image_gen.IMAGE_QPS_ENV, None)
            else:
                os.environ[image_gen.IMAGE_QPS_ENV] = old_env
            image_gen._RATE_LIMITER = old_limiter


class _FakeSyncProvider:
    def __init__(self, result: list) -> None:
        self.result = result
        self.calls: list[dict] = []

    def generate(self, payload):
        self.calls.append(payload)
        return self.result


class _FakeAsyncBatchProvider:
    def __init__(self, result: list) -> None:
        self.result = result
        self.calls: list[tuple[dict, int, str]] = []

    async def generate_batch(self, payload, *, attempts, job_label):
        self.calls.append((payload, attempts, job_label))
        return self.result


class SuccessPathRegressionTests(unittest.TestCase):
    """Normal success paths must behave exactly as before the rate-limit work."""

    def setUp(self):
        self._old_limiter = image_gen._RATE_LIMITER
        self.limiter = RecordingLimiter()
        image_gen._RATE_LIMITER = self.limiter
        # Pillow is not a test dependency; the decoded-bytes contract is what
        # this regression protects, so bypass image-content validation.
        patcher = mock.patch.object(
            image_gen, "_validate_generated_image_bytes", lambda *a, **k: None
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        image_gen._RATE_LIMITER = self._old_limiter

    def test_generate_cli_path_writes_output_unchanged(self):
        provider = _FakeSyncProvider([PNG_B64])
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "slide.png"
            args = SimpleNamespace(
                prompt="a test slide",
                prompt_file=None,
                augment=False,
                model="gpt-image-2",
                n=1,
                size="auto",
                quality="medium",
                background=None,
                output_format=None,
                output_compression=None,
                moderation=None,
                out=str(out_path),
                out_dir=None,
                force=True,
                dry_run=False,
                downscale_max_dim=None,
                downscale_suffix="-web",
            )
            with mock.patch.object(
                image_gen, "create_image_provider", return_value=provider
            ):
                image_gen._generate(args)
            self.assertTrue(out_path.exists())
            self.assertEqual(out_path.read_bytes(), PNG_BYTES)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(self.limiter.acquire_count, 1)

    def test_generate_batch_cli_path_writes_output_and_throttles(self):
        provider = _FakeAsyncBatchProvider([PNG_B64])
        with tempfile.TemporaryDirectory() as tmp:
            jobs_path = Path(tmp) / "jobs.jsonl"
            jobs_path.write_text('{"prompt": "batch test"}\n', encoding="utf-8")
            out_dir = Path(tmp) / "out"
            args = SimpleNamespace(
                input=str(jobs_path),
                out_dir=str(out_dir),
                concurrency=1,
                max_attempts=3,
                fail_fast=False,
                augment=False,
                model="gpt-image-2",
                n=1,
                size="2560x1440",
                quality="medium",
                background=None,
                output_format=None,
                output_compression=None,
                moderation=None,
                out=None,
                force=True,
                dry_run=False,
                downscale_max_dim=None,
                downscale_suffix="-web",
            )
            with mock.patch.object(
                image_gen, "create_image_provider", return_value=provider
            ):
                exit_code = asyncio.run(image_gen._run_generate_batch(args))
            self.assertEqual(exit_code, 0)
            written = list(out_dir.glob("*.png"))
            self.assertEqual(len(written), 1)
            self.assertEqual(written[0].read_bytes(), PNG_BYTES)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(self.limiter.reserve_count, 1)


if __name__ == "__main__":
    unittest.main()
