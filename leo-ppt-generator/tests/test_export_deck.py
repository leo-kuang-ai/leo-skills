#!/usr/bin/env python3
"""export_deck.py 单测（R-47 首批：handout-PDF + 长图）。

覆盖：两种格式产物可校验（PDF 页数/MediaBox、长图尺寸/居中/白边）、
双跑 sha256 确定性、缺页/损坏页 failed 回执与 exit 1、用法错误 exit 2、
--json 回执字段完备、自然排序与 pages.json 索引优先、dpi 进入 MediaBox。
PDF 无法被 PIL 读回，页数/尺寸按 PDF 结构标记（/Type /Page、/MediaBox）
断言；长图用 PIL 重开做像素级断言。
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_deck.py"
COLORS = [(255, 0, 0), (0, 200, 0), (0, 0, 255)]


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )


def _fixture_page(path: Path, number: int, color, width: int, height: int = 30, dpi=None):
    im = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(im)
    draw.text((2, 2), str(number), fill=(255, 255, 255))
    params = {"dpi": (dpi, dpi)} if dpi else {}
    im.save(path, **params)


def _make_run(tmp: Path, count=3, dpi=None, prefix="slide_{:02d}.png"):
    run_dir = tmp / "pages"
    run_dir.mkdir()
    for i in range(1, count + 1):
        _fixture_page(run_dir / prefix.format(i), i, COLORS[(i - 1) % len(COLORS)], 40 + i * 10, dpi=dpi)
    return run_dir


def _json_lines(stdout: str):
    return [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]


def _pdf_page_count(data: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", data))


class HandoutPdfTest(unittest.TestCase):
    def test_creates_valid_multipage_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            out = Path(tmp) / "handout.pdf"
            result = _run([run_dir, "--format", "handout-pdf", "--output", out])
            self.assertEqual(result.returncode, 0, result.stderr)
            data = out.read_bytes()
            self.assertTrue(data.startswith(b"%PDF"))
            self.assertIn(b"%%EOF", data)
            self.assertEqual(_pdf_page_count(data), 3)
            self.assertEqual(len(re.findall(rb"/MediaBox", data)), 3)

    def test_dpi_sizes_pdf_mediabox(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp), dpi=96)
            out = Path(tmp) / "handout.pdf"
            self.assertEqual(_run([run_dir, "--format", "handout-pdf", "--output", out]).returncode, 0)
            data = out.read_bytes()
            # first page 50x30 px at 96 dpi -> ~37.5 x ~22.5 pt (PNG pHYs
            # stores integer pixels-per-metre, so allow quantization drift)
            match = re.search(rb"/MediaBox \[ 0 0 ([\d.]+) ([\d.]+) \]", data)
            self.assertIsNotNone(match)
            self.assertAlmostEqual(float(match.group(1)), 37.5, delta=0.1)
            self.assertAlmostEqual(float(match.group(2)), 22.5, delta=0.1)

    def test_double_run_same_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            outs = [Path(tmp) / f"handout-{n}.pdf" for n in (1, 2)]
            for out in outs:
                self.assertEqual(_run([run_dir, "--format", "handout-pdf", "--output", out]).returncode, 0)
            self.assertEqual(outs[0].read_bytes(), outs[1].read_bytes())


class LongImageTest(unittest.TestCase):
    def test_size_centering_and_white_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            out = Path(tmp) / "long.png"
            self.assertEqual(_run([run_dir, "--format", "long-image", "--output", out]).returncode, 0)
            im = Image.open(out)
            self.assertEqual(im.mode, "RGB")
            self.assertEqual(im.size, (70, 90))  # widest page x summed heights
            self.assertEqual(im.getpixel((5, 15)), (255, 255, 255))    # left gutter
            self.assertEqual(im.getpixel((64, 15)), (255, 255, 255))   # right gutter
            for band, color in enumerate(COLORS):
                self.assertEqual(im.getpixel((35, band * 30 + 15)), color)

    def test_double_run_same_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            outs = [Path(tmp) / f"long-{n}.png" for n in (1, 2)]
            for out in outs:
                self.assertEqual(_run([run_dir, "--format", "long-image", "--output", out]).returncode, 0)
            self.assertEqual(outs[0].read_bytes(), outs[1].read_bytes())


class FailureReceiptTest(unittest.TestCase):
    def test_missing_page_fails_with_list_and_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            (run_dir / "slide_02.png").unlink()
            out = Path(tmp) / "handout.pdf"
            result = _run([run_dir, "--format", "handout-pdf", "--output", out, "--json"])
            self.assertEqual(result.returncode, 1)
            receipt = _json_lines(result.stdout)[-1]
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["failed_pages"], ["slide_02.png (missing)"])
            self.assertIsNone(receipt["artifact"])
            self.assertFalse(out.exists())

    def test_corrupt_page_fails_with_list_and_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            (run_dir / "slide_02.png").write_bytes(b"not a png at all")
            result = _run([run_dir, "--format", "long-image", "--json"])
            self.assertEqual(result.returncode, 1)
            receipt = _json_lines(result.stdout)[-1]
            self.assertEqual(receipt["status"], "failed")
            self.assertIn("slide_02.png (corrupt)", receipt["failed_pages"])

    def test_pages_json_missing_entry_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            (run_dir / "pages.json").write_text(
                json.dumps(["slide_01.png", "slide_02.png", "slide_04.png"]), encoding="utf-8")
            result = _run([run_dir, "--format", "handout-pdf", "--json"])
            self.assertEqual(result.returncode, 1)
            receipt = _json_lines(result.stdout)[-1]
            self.assertEqual(receipt["failed_pages"], ["slide_04.png (missing)"])


class UsageErrorTest(unittest.TestCase):
    def test_missing_run_dir_exits_2(self):
        result = _run([Path(tempfile.gettempdir()) / "no-such-run-dir", "--format", "handout-pdf"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("ERROR", result.stderr)

    def test_empty_dir_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([Path(tmp), "--format", "handout-pdf"])
            self.assertEqual(result.returncode, 2)

    def test_dir_without_png_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "notes.md").write_text("no images", encoding="utf-8")
            self.assertEqual(_run([Path(tmp), "--format", "long-image"]).returncode, 2)

    def test_unknown_format_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            result = _run([run_dir, "--format", "carousel"])
            self.assertEqual(result.returncode, 2)


class ReceiptTest(unittest.TestCase):
    def test_json_receipt_started_and_completed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            result = _run([run_dir, "--format", "handout-pdf", "--json"])
            self.assertEqual(result.returncode, 0)
            lines = _json_lines(result.stdout)
            self.assertEqual(lines[0]["status"], "started")
            self.assertEqual(lines[0]["pages"], 3)
            done = lines[-1]
            self.assertEqual(done["status"], "completed")
            self.assertEqual(done["pages"], 3)
            self.assertEqual(done["format"], "handout-pdf")
            self.assertTrue(Path(done["artifact"]).is_file())
            self.assertRegex(done["sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn("failed_pages", done)

    def test_human_stdout_mentions_path_sha_and_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            out = Path(tmp) / "export" / "handout.pdf"
            result = _run([run_dir, "--format", "handout-pdf", "--output", out])
            self.assertEqual(result.returncode, 0)
            self.assertIn(str(out), result.stdout)
            self.assertIn("3 页", result.stdout)
            self.assertRegex(result.stdout, r"sha256=[0-9a-f]{64}")
            self.assertIn("completed", result.stdout)


class OrderingTest(unittest.TestCase):
    def test_natural_sort_puts_page_9_before_page_10(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "pages"
            run_dir.mkdir()
            _fixture_page(run_dir / "p-9.png", 9, (255, 0, 0), 50)
            _fixture_page(run_dir / "p-10.png", 10, (0, 0, 255), 50)
            out = Path(tmp) / "long.png"
            self.assertEqual(_run([run_dir, "--format", "long-image", "--output", out]).returncode, 0)
            im = Image.open(out)
            self.assertEqual(im.size, (50, 60))
            self.assertEqual(im.getpixel((25, 15)), (255, 0, 0))   # p-9 first
            self.assertEqual(im.getpixel((25, 45)), (0, 0, 255))  # p-10 second

    def test_pages_json_order_wins_over_disk_sorting(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run(Path(tmp))
            (run_dir / "pages.json").write_text(
                json.dumps(["slide_03.png", "slide_01.png", "slide_02.png"]), encoding="utf-8")
            out = Path(tmp) / "long.png"
            self.assertEqual(_run([run_dir, "--format", "long-image", "--output", out]).returncode, 0)
            im = Image.open(out)
            self.assertEqual(im.getpixel((35, 15)), (0, 0, 255))   # slide_03 band first
            self.assertEqual(im.getpixel((35, 45)), (255, 0, 0))   # then slide_01
            self.assertEqual(im.getpixel((35, 75)), (0, 200, 0))   # then slide_02

    def test_rgba_pages_composited_onto_white(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "pages"
            run_dir.mkdir()
            for i, color in enumerate(COLORS, 1):
                im = Image.new("RGBA", (40, 30), color + (128,))
                im.save(run_dir / f"slide_{i:02d}.png")
            out = Path(tmp) / "long.png"
            self.assertEqual(_run([run_dir, "--format", "long-image", "--output", out]).returncode, 0)
            im = Image.open(out)
            self.assertEqual(im.mode, "RGB")
            # 50% alpha red over white -> (255, ~127, ~127)
            self.assertEqual(im.getpixel((20, 15)), (255, 127, 127))


if __name__ == "__main__":
    unittest.main()
