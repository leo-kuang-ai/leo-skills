"""聚焦回归（patches/0010）：组装进度输出不得污染 stdout。

`image assemble` 在 leo 进程内调用 vendored create_presentation；其进度
print 必须全部走 stderr，`leo-ppt-machine/v1` envelope 的 stdout 保持
单 JSON 约定（基线证据：R02-R04 首装回执不可直接 json.loads）。
"""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from leo_ppt_generator._vendor.codex_ppt import assemble_ppt


class AssembleStdoutPurityTest(unittest.TestCase):
    def test_create_presentation_keeps_stdout_empty(self):
        with tempfile.TemporaryDirectory(prefix="leo-0010-") as tmp:
            root = Path(tmp)
            pages = []
            for i in range(2):
                png = root / f"slide_{i + 1:02d}.png"
                Image.new("RGB", (1600, 900), "#ffffff").save(png)
                pages.append(str(png))
            out = root / "deck.pptx"
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                ok = assemble_ppt.create_presentation(pages, str(out))
            self.assertTrue(ok)
            self.assertTrue(out.is_file())
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("已添加", stderr.getvalue())

    def test_create_presentation_with_notes_still_pure(self):
        with tempfile.TemporaryDirectory(prefix="leo-0010b-") as tmp:
            root = Path(tmp)
            png = root / "slide_01.png"
            Image.new("RGB", (1600, 900), "#ffffff").save(png)
            out = root / "deck-notes.pptx"
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                ok = assemble_ppt.create_presentation([str(png)], str(out),
                                                      speaker_notes={1: "讲稿"})
            self.assertTrue(ok)
            self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
