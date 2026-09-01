#!/usr/bin/env python3
"""normalize_transcript.py unit tests (R-03): timestamp prefix validation,
position reporting for non-conforming lines, --fix canonicalization
(zero-padding, AI-Media2Doc bracket form, inherit/default prefix),
blank/comment tolerance, determinism, exit codes."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "normalize_transcript.py"

_spec = importlib.util.spec_from_file_location("normalize_transcript", SCRIPT)
normalize_transcript = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(normalize_transcript)

VALID = "00:00-00:05 大家好,开始今天的汇报。\n00:05-00:42 第一部分讲背景。\n"


def _run(args, expect_ok=None):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )
    if expect_ok is True and result.returncode != 0:
        raise AssertionError(
            f"expected exit 0, got {result.returncode}: {result.stderr}")
    return result


class NormalizeTranscriptTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, content, name="t.txt"):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    # 1. Fully conforming transcript: exit 0, no problem lines.
    def test_valid_transcript_passes(self):
        path = self.write(VALID)
        result = _run([path], expect_ok=True)
        self.assertIn("符合", result.stdout)
        self.assertNotIn("无时间戳前缀", result.stdout)

    # 2. Missing prefix: exit 1 and the line position is reported.
    def test_missing_prefix_reported_with_line_number(self):
        path = self.write(VALID + "这一行没有时间戳前缀。\n")
        result = _run([path], expect_ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("t.txt:3", result.stdout)
        self.assertIn("无时间戳前缀", result.stdout)

    # 3. Malformed ranges: bad seconds and end-before-start are reported.
    def test_malformed_timestamps_reported(self):
        path = self.write("00:00-00:75 秒越界\n00:42-00:10 结束早于开始\n")
        result = _run([path], expect_ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count("时间戳格式或区间非法"), 2)

    # 3b. --fix drops the malformed prefix digits instead of keeping them in
    # the body text (the fixed output must revalidate clean).
    def test_fix_drops_malformed_prefix_from_body(self):
        path = self.write("00:42-00:10 结束早于开始\n")
        result = _run([path, "--fix"], expect_ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "00:00-00:00 结束早于开始\n")
        self.assertNotIn("00:42-00:10", result.stdout)

    def test_fix_drops_out_of_range_seconds_prefix_from_body(self):
        path = self.write("00:00-00:05 甲\n00:05-00:75 秒越界\n")
        result = _run([path, "--fix"], expect_ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            result.stdout, "00:00-00:05 甲\n00:00-00:05 秒越界\n")
        round_trip = self.write(result.stdout, "round-bad.txt")
        clean = _run([round_trip], expect_ok=True)
        self.assertIn("问题行 0 个", clean.stdout)

    # 4. AI-Media2Doc lineage prefix validates as-is.
    def test_aim2d_bracket_form_is_valid(self):
        path = self.write(
            "[00:00 - 00:05 时间范围秒数:(0s-5s)] 大家好\n"
            "[00:05 - 00:42 时间范围秒数:(5s-42s)] 第一部分\n")
        result = _run([path], expect_ok=True)
        self.assertIn("问题行 0 个", result.stdout)

    # 5. --fix canonicalizes variants and adds default/inherited prefixes.
    def test_fix_canonicalizes_and_backfills_prefixes(self):
        path = self.write(
            "[00:10 - 00:20 时间范围秒数:(10s-20s)] 段落一\n"
            "没有前缀的段落二,应继承上一段区间\n"
            "0:25-0:30 一位数分钟补零\n"
            "# 注释行原样保留\n")
        result = _run([path, "--fix"], expect_ok=False)  # input has issues
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            result.stdout,
            "00:10-00:20 段落一\n"
            "00:10-00:20 没有前缀的段落二,应继承上一段区间\n"
            "00:25-00:30 一位数分钟补零\n"
            "# 注释行原样保留\n")

    # 6. Prefix-less first line falls back to 00:00-00:00.
    def test_fix_first_line_default_prefix(self):
        path = self.write("开场白没有前缀\n00:01-00:02 第二段\n")
        result = _run([path, "--fix"])
        self.assertTrue(result.stdout.startswith("00:00-00:00 开场白没有前缀\n"))

    # 7. Blank and comment lines never count as non-conforming.
    def test_blank_and_comment_lines_tolerated(self):
        path = self.write("\n\n# 备注\n" + VALID + "\n")
        result = _run([path], expect_ok=True)
        self.assertIn("问题行 0 个", result.stdout)

    # 8. JSON report shape.
    def test_json_report_shape(self):
        path = self.write("无前缀行\n")
        result = _run([path, "--json"])
        payload = json.loads(result.stdout)
        self.assertFalse(payload["conforming"])
        self.assertEqual(payload["problems"][0]["line"], 1)
        self.assertEqual(result.returncode, 1)

    # 9. Determinism: two runs over the same input are byte-identical.
    def test_deterministic_output(self):
        path = self.write(VALID + "坏行\n")
        first = _run([path])
        second = _run([path])
        self.assertEqual(first.stdout + first.stderr,
                         second.stdout + second.stderr)
        fixed1 = _run([path, "--fix"]).stdout
        fixed2 = _run([path, "--fix"]).stdout
        self.assertEqual(fixed1, fixed2)

    # 10. Usage errors: missing file exits 2.
    def test_missing_file_exit_two(self):
        result = _run([self.root / "nope.txt"], expect_ok=False)
        self.assertEqual(result.returncode, 2)

    # 11. Fixed output revalidates clean (round-trip).
    def test_fix_output_revalidates_clean(self):
        path = self.write("无前缀甲\n无前缀乙\n")
        fixed = _run([path, "--fix"]).stdout
        round_trip = self.write(fixed, "round.txt")
        result = _run([round_trip], expect_ok=True)
        self.assertIn("问题行 0 个", result.stdout)


if __name__ == "__main__":
    unittest.main()
