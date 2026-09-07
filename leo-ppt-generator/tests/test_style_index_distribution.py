"""完整包复制和目录链接读取随包快照，无首次生成或安装目录写入。"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from lint_style_governance import check_document_links


class StyleIndexDistributionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.copy = cls.root / "copied-skill"
        shutil.copytree(SKILL, cls.copy, ignore=shutil.ignore_patterns("__pycache__", ".venv", "*-workspace"))
        cls.link = cls.root / "linked-skill"
        cls.link.symlink_to(cls.copy, target_is_directory=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_checkout_copy_and_link_have_identical_readable_snapshots(self):
        for root in (SKILL, self.copy, self.link):
            with self.subTest(root=root.name):
                generated = root / "references/styles/generated"
                manifest = json.loads((generated / "manifest.json").read_text())
                for relative, expected in manifest["files"].items():
                    self.assertEqual(hashlib.sha256((generated / relative).read_bytes()).hexdigest(), expected)
                docs = {p.relative_to(root).as_posix(): p.read_text() for p in generated.rglob("*.md")}
                self.assertEqual(check_document_links(docs, root), [])

    def test_copy_and_link_cli_summary_work_without_snapshot_or_writes(self):
        snapshot = self.copy / "references/styles/generated"
        unavailable = self.root / "snapshot-backup"
        snapshot.rename(unavailable)
        try:
            before = {p.relative_to(self.copy): p.stat().st_mtime_ns for p in self.copy.rglob("*") if p.is_file()}
            for root in (self.copy, self.link):
                env = dict(os.environ, PYTHONPATH=str(root / "runtime/src"), LEO_PPT_BUNDLE=str(root), PYTHONDONTWRITEBYTECODE="1")
                result = subprocess.run([sys.executable, "-B", "-m", "leo_ppt_generator.cli", "style", "list",
                                         "--summary", "--filter", "terminal", "--home", str(self.root / "user-home")],
                                        cwd=self.root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                data = json.loads(result.stdout)
                self.assertEqual({entry["name"] for entry in data["items"]}, {"Gruvbox暗风", "终端命令行风"})
            after = {p.relative_to(self.copy): p.stat().st_mtime_ns for p in self.copy.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
        finally:
            unavailable.rename(snapshot)


if __name__ == "__main__":
    unittest.main()
