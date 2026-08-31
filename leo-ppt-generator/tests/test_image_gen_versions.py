"""image_gen 参考图归一化与输出图像版本历史（--keep-versions）的单元测试。

放置说明：与 test_image_gen_backoff.py / test_image_gen_resume.py 同类——
放在 tests/ 根目录，import runtime vendored 脚本做行为单测，无需网络。

覆盖：
  1. prepare_reference_inputs：本地 png→data URL（前缀正确、base64 可解码）；
     http(s) URL 与已有 data URL 原样透传；不存在文件清晰报错；未知扩展名
     清晰报错；
  2. 版本轮转：预置输出→带 --keep-versions 再生成→旧内容进 .v1、新内容在
     激活路径、history 行字段完整（且无需 --force）；
  3. 多次轮转版本号递增、旧版本不被覆盖；
  4. 不带 flag：既有文件被直接覆盖、无 history 文件、无 .vN 文件（回归保护）；
  5. set_active：切回 v1 后激活路径内容=旧内容、追加 active:true 行、
     版本文件仍在；版本/记录缺失时清晰报错；
  6. 与退避共存：一次 429 后成功的 generate + --keep-versions 轮转正常；
  7. resume 正交性：版本文件存在不影响 resume 跳过判定（以激活文件为准）。
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

# Minimal valid 1x1 PNG (same fixture as test_image_gen_backoff).
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd4"
    "0000000049454e44ae426082"
)
PNG_B64 = base64.b64encode(PNG_BYTES).decode("ascii")
SECOND_BYTES = PNG_BYTES + b"#-second-generation"
SECOND_B64 = base64.b64encode(SECOND_BYTES).decode("ascii")
THIRD_BYTES = PNG_BYTES + b"#-third-generation"
THIRD_B64 = base64.b64encode(THIRD_BYTES).decode("ascii")


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
    """Mimics openai.RateLimitError surface: status_code == 429."""

    status_code = 429

    def __init__(self, message: str = "429 Too Many Requests") -> None:
        super().__init__(message)


class FakeSyncProvider:
    def __init__(self, result: list) -> None:
        self.result = result
        self.calls = 0

    def generate(self, payload):
        self.calls += 1
        return self.result


class FlakySyncProvider:
    """First generate() raises 429; later calls succeed."""

    def __init__(self, result: list) -> None:
        self.result = result
        self.calls = 0

    def generate(self, payload):
        self.calls += 1
        if self.calls == 1:
            raise RateLimitedError()
        return self.result


class FakeAsyncBatchProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_batch(self, payload, *, attempts, job_label):
        self.calls += 1
        return [PNG_B64]


class PrepareReferenceInputsTests(unittest.TestCase):
    def test_local_png_becomes_decodable_data_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.png"
            ref.write_bytes(PNG_BYTES)
            prepared = image_gen.prepare_reference_inputs([str(ref)])
        self.assertEqual(len(prepared), 1)
        self.assertTrue(prepared[0].startswith("data:image/png;base64,"))
        payload = prepared[0].split(",", 1)[1]
        self.assertEqual(base64.b64decode(payload), PNG_BYTES)

    def test_urls_and_data_urls_pass_through_in_order(self):
        data_url = "data:image/png;base64," + PNG_B64
        items = ["https://example.com/a.png", "http://example.com/b.jpg", data_url]
        self.assertEqual(image_gen.prepare_reference_inputs(items), items)

    def test_missing_file_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "nope.png")
        with self.assertRaises(ValueError) as ctx:
            image_gen.prepare_reference_inputs([missing])
        self.assertIn("not found", str(ctx.exception))
        self.assertIn("nope.png", str(ctx.exception))

    def test_unknown_extension_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.bmp"
            ref.write_bytes(b"BMfake")
            with self.assertRaises(ValueError) as ctx:
                image_gen.prepare_reference_inputs([str(ref)])
        self.assertIn("unsupported reference image extension", str(ctx.exception))
        self.assertIn(".bmp", str(ctx.exception))


class VersionHistoryTestCase(unittest.TestCase):
    """Shared harness: stub QPS limiter and image validation."""

    def setUp(self) -> None:
        self._old_limiter = image_gen._RATE_LIMITER
        self.limiter = RecordingLimiter()
        image_gen._RATE_LIMITER = self.limiter
        self.addCleanup(self._restore_limiter)
        patcher = mock.patch.object(
            image_gen, "_validate_generated_image_bytes", lambda *a, **k: None
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_limiter(self) -> None:
        image_gen._RATE_LIMITER = self._old_limiter

    def make_generate_args(
        self, out_path: Path, *, force: bool = False, keep_versions: bool = False
    ) -> SimpleNamespace:
        return SimpleNamespace(
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
            force=force,
            keep_versions=keep_versions,
            dry_run=False,
            downscale_max_dim=None,
            downscale_suffix="-web",
        )

    def run_generate(self, args: SimpleNamespace, provider) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            image_gen, "create_image_provider", return_value=provider
        ):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                image_gen._generate(args)

    def history_file(self, out_path: Path) -> Path:
        return out_path.parent / image_gen.IMAGE_HISTORY_NAME

    def history_records(self, out_path: Path) -> list:
        path = self.history_file(out_path)
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


class VersionRotationTests(VersionHistoryTestCase):
    def test_keep_versions_rotates_old_content_and_logs_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "slide.png"
            # First generation creates the active file (keep-versions on).
            self.run_generate(
                self.make_generate_args(out_path, keep_versions=True),
                FakeSyncProvider([PNG_B64]),
            )
            # Second generation without --force rotates instead of dying.
            self.run_generate(
                self.make_generate_args(out_path, keep_versions=True),
                FakeSyncProvider([SECOND_B64]),
            )

            self.assertEqual((out_path.parent / "slide.v1.png").read_bytes(), PNG_BYTES)
            self.assertEqual(out_path.read_bytes(), SECOND_BYTES)

            records = self.history_records(out_path)
            self.assertEqual(len(records), 3)
            for rec in records:
                self.assertEqual(rec["output"], "slide.png")
                self.assertIn(rec["version"], ("v1", "v2"))
                self.assertTrue(rec["file"])
                self.assertIsInstance(rec["bytes"], int)
                self.assertTrue(rec["timestamp"])
                self.assertIsInstance(rec["active"], bool)
            # Chronological rows: first-run active row stays untouched
            # (append-only), then the rotation archive row, then the new
            # active row.
            self.assertEqual(records[0]["version"], "v1")
            self.assertEqual(records[0]["file"], "slide.png")
            self.assertTrue(records[0]["active"])
            self.assertEqual(records[1]["version"], "v1")
            self.assertEqual(records[1]["file"], "slide.v1.png")
            self.assertFalse(records[1]["active"])
            self.assertEqual(records[1]["bytes"], len(PNG_BYTES))
            self.assertEqual(records[2]["version"], "v2")
            self.assertEqual(records[2]["file"], "slide.png")
            self.assertTrue(records[2]["active"])
            self.assertEqual(records[2]["bytes"], len(SECOND_BYTES))

    def test_multiple_rotations_increment_slots_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "slide.png"
            for b64 in (PNG_B64, SECOND_B64, THIRD_B64):
                self.run_generate(
                    self.make_generate_args(out_path, keep_versions=True),
                    FakeSyncProvider([b64]),
                )
            parent = out_path.parent
            self.assertEqual((parent / "slide.v1.png").read_bytes(), PNG_BYTES)
            self.assertEqual((parent / "slide.v2.png").read_bytes(), SECOND_BYTES)
            self.assertEqual(out_path.read_bytes(), THIRD_BYTES)
            self.assertFalse((parent / "slide.v3.png").exists())


class NoKeepVersionsRegressionTests(VersionHistoryTestCase):
    def test_without_flag_existing_file_is_overwritten_and_no_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "slide.png"
            out_path.write_bytes(b"stale-previous-content")
            self.run_generate(
                self.make_generate_args(out_path, force=True),
                FakeSyncProvider([PNG_B64]),
            )
            self.assertEqual(out_path.read_bytes(), PNG_BYTES)
            self.assertFalse(self.history_file(out_path).exists())
            self.assertEqual(list(out_path.parent.glob("*.v*.png")), [])


class SetActiveTests(VersionHistoryTestCase):
    def _run_two_generations(self, out_path: Path) -> None:
        self.run_generate(
            self.make_generate_args(out_path, keep_versions=True),
            FakeSyncProvider([PNG_B64]),
        )
        self.run_generate(
            self.make_generate_args(out_path, keep_versions=True),
            FakeSyncProvider([SECOND_B64]),
        )

    def test_set_active_restores_v1_content_and_appends_active_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "slide.png"
            self._run_two_generations(out_path)
            history = self.history_file(out_path)
            records_before = self.history_records(out_path)

            active = image_gen.set_active(history, "slide.png", "v1")

            self.assertEqual(active, out_path)
            self.assertEqual(out_path.read_bytes(), PNG_BYTES)
            # The version file itself survives (copy, not move).
            self.assertEqual((out_path.parent / "slide.v1.png").read_bytes(), PNG_BYTES)
            records_after = self.history_records(out_path)
            self.assertEqual(len(records_after), len(records_before) + 1)
            new_row = records_after[-1]
            self.assertEqual(new_row["output"], "slide.png")
            self.assertEqual(new_row["version"], "v1")
            self.assertEqual(new_row["file"], "slide.png")
            self.assertTrue(new_row["active"])
            self.assertEqual(new_row["bytes"], len(PNG_BYTES))
            self.assertTrue(new_row["timestamp"])

    def test_set_active_clear_errors_for_missing_history_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "slide.png"
            out_path.write_bytes(PNG_BYTES)
            history = self.history_file(out_path)
            with self.assertRaises(ValueError) as ctx:
                image_gen.set_active(history, "slide.png", "v1")
            self.assertIn("not found", str(ctx.exception))

            self._run_two_generations(out_path)
            with self.assertRaises(ValueError) as ctx:
                image_gen.set_active(history, "slide.png", "v9")
            self.assertIn("v9", str(ctx.exception))


class BackoffCoexistenceTests(VersionHistoryTestCase):
    def test_429_retry_success_with_keep_versions_rotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "slide.png"
            self.run_generate(
                self.make_generate_args(out_path, keep_versions=True),
                FakeSyncProvider([PNG_B64]),
            )
            provider = FlakySyncProvider([SECOND_B64])
            # Shrink the backoff ladder to 0s (read from the module global at
            # call time) so the retry is real but the test stays fast.
            with mock.patch.object(image_gen, "RATE_LIMIT_BACKOFF_SECONDS", (0.0,)):
                stderr = io.StringIO()
                stdout = io.StringIO()
                with mock.patch.object(
                    image_gen, "create_image_provider", return_value=provider
                ):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                        stderr
                    ):
                        image_gen._generate(
                            self.make_generate_args(out_path, keep_versions=True)
                        )
            # One 429 consumed one backoff step, then the retry landed.
            self.assertEqual(provider.calls, 2)
            self.assertIn("429 rate limited; backing off 0s", stderr.getvalue())
            self.assertEqual((out_path.parent / "slide.v1.png").read_bytes(), PNG_BYTES)
            self.assertEqual(out_path.read_bytes(), SECOND_BYTES)
            self.assertEqual(len(self.history_records(out_path)), 3)


class ResumeOrthogonalityTests(VersionHistoryTestCase):
    def test_version_files_do_not_affect_resume_skip_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jobs_path = tmp_path / "jobs.jsonl"
            jobs_path.write_text(
                json.dumps({"prompt": "slide 1", "out": "slide-1.png"}) + "\n",
                encoding="utf-8",
            )
            out_dir = tmp_path / "out"
            out_dir.mkdir()
            # Completed job: manifest ok row plus a non-empty active file, and
            # a stray version file that must not influence the skip decision.
            (out_dir / "slide-1.png").write_bytes(PNG_BYTES)
            (out_dir / "slide-1.v1.png").write_bytes(b"older-version")
            manifest = out_dir / image_gen.BATCH_MANIFEST_NAME
            manifest.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "job": 1,
                        "output": "slide-1.png",
                        "bytes": len(PNG_BYTES),
                        "timestamp": "2026-01-01T00:00:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                input=str(jobs_path),
                out_dir=str(out_dir),
                concurrency=1,
                max_attempts=3,
                fail_fast=False,
                resume=True,
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
                force=False,
                dry_run=False,
                downscale_max_dim=None,
                downscale_suffix="-web",
            )
            provider = FakeAsyncBatchProvider()
            stderr = io.StringIO()
            with mock.patch.object(
                image_gen, "create_image_provider", return_value=provider
            ):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                    stderr
                ):
                    exit_code = asyncio.run(image_gen._run_generate_batch(args))
            self.assertEqual(exit_code, 0)
            # Active file present + manifest ok → skipped, provider untouched.
            self.assertEqual(provider.calls, 0)
            self.assertIn("resumed=1", stderr.getvalue())
            # Version files are never rewritten or deleted by resume.
            self.assertEqual((out_dir / "slide-1.v1.png").read_bytes(), b"older-version")
            self.assertEqual((out_dir / "slide-1.png").read_bytes(), PNG_BYTES)


if __name__ == "__main__":
    unittest.main()
