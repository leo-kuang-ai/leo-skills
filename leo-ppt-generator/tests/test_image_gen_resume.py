"""image_gen generate-batch 断点续跑（--resume）与每页落库 manifest 的单元测试。

放置说明：与 test_image_gen_backoff.py 同类——放在 tests/ 根目录而非
tests/boundary/，import runtime vendored 脚本做行为单测。

覆盖（对应任务 1-6）：
  1. 全新跑：无 manifest、无输出 → 全部生成，manifest 行数=job 数、字段完整；
  2. resume 跳过：预置部分输出+manifest → provider 调用次数仅等于缺失 job 数，
     汇总含 resumed/skipped 统计；
  3. 损毁输出（0 字节文件 / manifest 无记录）：resume 时该页重新生成；
  4. 不带 --resume：即使输出存在也全部重新生成（回归保护）；
  5. manifest 崩溃模拟：完整行后截断的尾行 → resume 只采纳完整行、坏行告警
     不崩溃，且新记录不被粘到坏行上（后续 resume 仍可全量跳过）；
  6. 与退避/限流共存：一次 429 后成功的 job 在 resume 二次运行中被跳过。
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import json
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
from image_providers.openai_compatible import (  # noqa: E402
    OpenAICompatibleImageProvider,
)

# Minimal valid 1x1 PNG (same fixture as test_image_gen_backoff).
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd4"
    "0000000049454e44ae426082"
)
PNG_B64 = base64.b64encode(PNG_BYTES).decode("ascii")


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


class RateLimitedError(Exception):
    """Mimics openai.RateLimitError: status_code 429 and a zero Retry-After."""

    status_code = 429
    retry_after = 0.0

    def __init__(self, message: str = "429 Too Many Requests") -> None:
        super().__init__(message)


class FakeAsyncBatchProvider:
    """Counts generate_batch calls; always succeeds with one image."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate_batch(self, payload, *, attempts, job_label):
        self.calls += 1
        return [PNG_B64]


class _FlakyAsyncImages:
    """First images.generate call raises 429; later calls succeed."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **payload):
        self.calls += 1
        if self.calls == 1:
            raise RateLimitedError()
        return SimpleNamespace(data=[SimpleNamespace(b64_json=PNG_B64)])


class _FakeAsyncClient:
    def __init__(self) -> None:
        self.images = _FlakyAsyncImages()


def _write_jobs_file(path: Path, count: int, *, with_page_type: bool = False) -> None:
    lines = []
    for i in range(1, count + 1):
        job = {"prompt": f"slide {i} prompt", "out": f"slide-{i}.png"}
        if with_page_type:
            job["page_type"] = "cover" if i == 1 else "content"
        lines.append(json.dumps(job))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_batch_args(
    tmp: Path,
    count: int = 3,
    *,
    resume: bool = False,
    force: bool = False,
    with_page_type: bool = False,
) -> SimpleNamespace:
    jobs_path = tmp / "jobs.jsonl"
    _write_jobs_file(jobs_path, count, with_page_type=with_page_type)
    return SimpleNamespace(
        input=str(jobs_path),
        out_dir=str(tmp / "out"),
        concurrency=2,
        max_attempts=3,
        fail_fast=False,
        resume=resume,
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
        force=force,
        dry_run=False,
        downscale_max_dim=None,
        downscale_suffix="-web",
    )


class BatchResumeTestCase(unittest.TestCase):
    """Shared harness: stub QPS limiter and image validation, capture stderr."""

    def setUp(self) -> None:
        self._old_limiter = image_gen._RATE_LIMITER
        self.limiter = RecordingLimiter()
        image_gen._RATE_LIMITER = self.limiter
        self.addCleanup(self._restore_limiter)
        # Pillow size validation is orthogonal to resume semantics; the
        # decoded-bytes contract is what these tests protect.
        patcher = mock.patch.object(
            image_gen, "_validate_generated_image_bytes", lambda *a, **k: None
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_limiter(self) -> None:
        image_gen._RATE_LIMITER = self._old_limiter

    def run_batch(self, args: SimpleNamespace, provider) -> tuple:
        stderr = io.StringIO()
        stdout = io.StringIO()
        with mock.patch.object(
            image_gen, "create_image_provider", return_value=provider
        ):
            # Swallow the per-file "Wrote ..." stdout chatter; assertions
            # only need the summary on stderr.
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = asyncio.run(image_gen._run_generate_batch(args))
        return exit_code, stderr.getvalue()

    def manifest_file(self, args: SimpleNamespace) -> Path:
        return Path(args.out_dir) / image_gen.BATCH_MANIFEST_NAME

    def read_manifest_lines(self, args: SimpleNamespace) -> list:
        path = self.manifest_file(args)
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def parse_manifest_records(self, args: SimpleNamespace) -> list:
        return [json.loads(line) for line in self.read_manifest_lines(args)]

    def seed_output(
        self, args: SimpleNamespace, job_index: int, data: bytes = PNG_BYTES
    ) -> Path:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"slide-{job_index}.png"
        out.write_bytes(data)
        return out

    def append_manifest_line(self, args: SimpleNamespace, line: str) -> None:
        path = self.manifest_file(args)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def seed_completed(self, args: SimpleNamespace, job_indexes) -> None:
        for i in job_indexes:
            out = self.seed_output(args, i)
            record = {
                "status": "ok",
                "job": i,
                "output": out.name,
                "bytes": out.stat().st_size,
                "timestamp": "2026-01-01T00:00:00Z",
            }
            self.append_manifest_line(args, json.dumps(record))


class FreshRunManifestTests(BatchResumeTestCase):
    def test_fresh_run_generates_all_jobs_and_writes_complete_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=3, with_page_type=True)
            provider = FakeAsyncBatchProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            self.assertEqual(provider.calls, 3)
            out_dir = Path(args.out_dir)
            for i in (1, 2, 3):
                self.assertEqual((out_dir / f"slide-{i}.png").read_bytes(), PNG_BYTES)

            lines = self.read_manifest_lines(args)
            self.assertEqual(len(lines), 3)
            records = self.parse_manifest_records(args)
            by_job = {rec["job"]: rec for rec in records}
            self.assertEqual(set(by_job), {1, 2, 3})
            for i in (1, 2, 3):
                rec = by_job[i]
                self.assertEqual(rec["status"], "ok")
                self.assertEqual(rec["output"], f"slide-{i}.png")
                self.assertEqual(rec["bytes"], len(PNG_BYTES))
                self.assertTrue(rec["timestamp"])
            # Optional page-type passthrough from the job object.
            self.assertEqual(by_job[1].get("page_type"), "cover")
            self.assertEqual(by_job[2].get("page_type"), "content")

            self.assertIn("resumed=0", stderr)
            self.assertIn("skipped=0", stderr)
            self.assertIn("generated=3", stderr)
            self.assertIn("failed=0", stderr)

    def test_failed_job_records_error_line_and_failing_summary(self):
        class FailingProvider:
            def __init__(self) -> None:
                self.calls = 0

            async def generate_batch(self, payload, *, attempts, job_label):
                self.calls += 1
                raise RuntimeError("provider exploded\nwith details")

        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=1)
            provider = FailingProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 1)
            self.assertEqual(provider.calls, 1)
            records = self.parse_manifest_records(args)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "error")
            self.assertEqual(records[0]["job"], 1)
            # Multi-line error text collapses onto one parseable line.
            self.assertEqual(records[0]["error"], "provider exploded with details")
            self.assertIn("failed=1", stderr)
            self.assertIn("generated=0", stderr)


class ResumeSkipTests(BatchResumeTestCase):
    def test_resume_regenerates_only_missing_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=3, resume=True)
            self.seed_completed(args, [1, 2])
            provider = FakeAsyncBatchProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            # Only the missing job reaches the provider.
            self.assertEqual(provider.calls, 1)
            out_dir = Path(args.out_dir)
            self.assertEqual((out_dir / "slide-3.png").read_bytes(), PNG_BYTES)
            # Seeded outputs keep their bytes (not rewritten).
            self.assertEqual((out_dir / "slide-1.png").read_bytes(), PNG_BYTES)

            records = self.parse_manifest_records(args)
            ok_jobs = {rec["job"] for rec in records if rec["status"] == "ok"}
            self.assertEqual(ok_jobs, {1, 2, 3})
            self.assertEqual(len(records), 3)

            self.assertIn("resumed=2", stderr)
            self.assertIn("skipped=2", stderr)
            self.assertIn("generated=1", stderr)
            self.assertIn("failed=0", stderr)

    def test_resume_with_everything_complete_generates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=2, resume=True)
            self.seed_completed(args, [1, 2])
            provider = FakeAsyncBatchProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            self.assertEqual(provider.calls, 0)
            # Skipped jobs never touch the QPS limiter.
            self.assertEqual(self.limiter.reserve_count, 0)
            self.assertIn("resumed=2", stderr)
            self.assertIn("generated=0", stderr)
            # No new manifest lines for already-recorded jobs.
            self.assertEqual(len(self.read_manifest_lines(args)), 2)


class CorruptOutputResumeTests(BatchResumeTestCase):
    def test_resume_regenerates_zero_byte_output_despite_manifest_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=1, resume=True)
            zero = self.seed_output(args, 1, data=b"")
            record = {
                "status": "ok",
                "job": 1,
                "output": zero.name,
                "bytes": 0,
                "timestamp": "2026-01-01T00:00:00Z",
            }
            self.append_manifest_line(args, json.dumps(record))
            provider = FakeAsyncBatchProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            self.assertEqual(provider.calls, 1)
            self.assertEqual(zero.read_bytes(), PNG_BYTES)
            records = self.parse_manifest_records(args)
            self.assertEqual([rec["status"] for rec in records], ["ok", "ok"])
            self.assertIn("resumed=0", stderr)
            self.assertIn("generated=1", stderr)

    def test_resume_regenerates_present_output_without_manifest_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=1, resume=True)
            orphan = self.seed_output(args, 1)
            self.assertFalse(self.manifest_file(args).exists())
            provider = FakeAsyncBatchProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            # Manifest is the resume truth: an output without a success
            # record is regenerated (and overwritten).
            self.assertEqual(provider.calls, 1)
            self.assertEqual(orphan.read_bytes(), PNG_BYTES)
            records = self.parse_manifest_records(args)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["job"], 1)
            self.assertEqual(records[0]["status"], "ok")
            self.assertIn("resumed=0", stderr)
            self.assertIn("generated=1", stderr)


class NoResumeRegressionTests(BatchResumeTestCase):
    def test_without_resume_regenerates_all_even_when_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=2, force=True)
            self.seed_completed(args, [1, 2])
            provider = FakeAsyncBatchProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            self.assertEqual(provider.calls, 2)
            self.assertIn("resumed=0", stderr)
            self.assertIn("skipped=0", stderr)
            self.assertIn("generated=2", stderr)

    def test_missing_resume_attribute_defaults_to_off(self):
        # Other callers build Namespace objects without the new flag; the
        # batch path must not require it.
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=3)
            del args.resume
            provider = FakeAsyncBatchProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            self.assertEqual(provider.calls, 3)
            self.assertIn("resumed=0", stderr)
            self.assertIn("generated=3", stderr)

    def test_dry_run_neither_skips_nor_touches_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=2, resume=True)
            args.dry_run = True
            self.seed_completed(args, [1])
            provider = FakeAsyncBatchProvider()

            stdout = io.StringIO()
            with mock.patch.object(
                image_gen, "create_image_provider", return_value=provider
            ):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                    io.StringIO()
                ):
                    exit_code = asyncio.run(image_gen._run_generate_batch(args))

            self.assertEqual(exit_code, 0)
            self.assertEqual(provider.calls, 0)
            # Dry-run previews every job; the seeded manifest keeps exactly
            # its original single record.
            self.assertEqual(stdout.getvalue().count('"job": 2'), 1)
            self.assertEqual(len(self.read_manifest_lines(args)), 1)


class ManifestCrashTests(BatchResumeTestCase):
    def test_truncated_trailing_line_is_ignored_with_warning_and_stays_resumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=2, resume=True)
            self.seed_completed(args, [1])
            # Simulate a crash mid-write: a partial record without newline.
            with self.manifest_file(args).open("a", encoding="utf-8") as fh:
                fh.write('{"status": "ok", "job": 2, "output": "slide-2')
            provider = FakeAsyncBatchProvider()

            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            # Job 1 (complete line) skipped; job 2 (truncated line) redone.
            self.assertEqual(provider.calls, 1)
            self.assertIn("Batch manifest line 2", stderr)
            self.assertIn("resumed=1", stderr)
            self.assertIn("generated=1", stderr)

            # The new record must not be glued onto the truncated line.
            lines = self.read_manifest_lines(args)
            self.assertEqual(len(lines), 3)
            with self.assertRaises(json.JSONDecodeError):
                json.loads(lines[1])
            first = json.loads(lines[0])
            last = json.loads(lines[2])
            self.assertEqual((first["status"], first["job"]), ("ok", 1))
            self.assertEqual((last["status"], last["job"]), ("ok", 2))

            # A follow-up resume run can now skip everything.
            provider2 = FakeAsyncBatchProvider()
            exit_code2, stderr2 = self.run_batch(args, provider2)
            self.assertEqual(exit_code2, 0)
            self.assertEqual(provider2.calls, 0)
            self.assertIn("resumed=2", stderr2)
            self.assertIn("generated=0", stderr2)


class ResumeWithBackoffTests(BatchResumeTestCase):
    def test_job_surviving_429_is_skipped_on_resume_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = _make_batch_args(Path(tmp), count=1)
            client = _FakeAsyncClient()
            provider = OpenAICompatibleImageProvider(
                api_key="test-key",
                base_url=None,
                async_client_factory=lambda: client,
            )

            # First run: the provider's internal backoff absorbs one 429 and
            # the job still lands (retry_after=0 keeps the test fast).
            exit_code, stderr = self.run_batch(args, provider)

            self.assertEqual(exit_code, 0)
            self.assertEqual(client.images.calls, 2)
            self.assertIn("retrying in", stderr)
            self.assertIn("generated=1", stderr)
            records = self.parse_manifest_records(args)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "ok")
            reserves_after_first = self.limiter.reserve_count
            self.assertEqual(reserves_after_first, 1)

            # Second run with --resume: no provider call, no QPS slot.
            args.resume = True
            exit_code2, stderr2 = self.run_batch(args, provider)

            self.assertEqual(exit_code2, 0)
            self.assertEqual(client.images.calls, 2)
            self.assertEqual(self.limiter.reserve_count, reserves_after_first)
            self.assertIn("resumed=1", stderr2)
            self.assertIn("skipped=1", stderr2)
            self.assertIn("generated=0", stderr2)
            self.assertIn("failed=0", stderr2)


if __name__ == "__main__":
    unittest.main()
