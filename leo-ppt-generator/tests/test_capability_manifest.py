#!/usr/bin/env python3
"""capability_manifest.py 单元测试（R-60 能力清单版本表）：四层计数与
sha256 / brief 口径与 lint_style_index 一致(exclude _content_rules)/
digest 汇总 / --compare diff(计数变化/文件增删/hash 变化)/ identical /
确定性 / 用法错误 exit 2。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "capability_manifest.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8")


def make_skill(tmp: Path) -> Path:
    """A minimal but realistic skill tree: styles axes + briefs + scripts."""
    root = tmp / "skill"
    styles = root / "references" / "styles"
    styles.mkdir(parents=True)
    (styles / "清爽专业风.md").write_text("brief A\n", encoding="utf-8")
    (styles / "01_通用母版").mkdir()
    (styles / "01_通用母版" / "商务蓝.md").write_text("brief B\n", encoding="utf-8")
    (styles / "02_行业内容域").mkdir()
    (styles / "02_行业内容域" / "金融风.md").write_text("brief C\n", encoding="utf-8")
    (styles / "02_行业内容域" / "_content_rules.md").write_text("rules\n", encoding="utf-8")
    (styles / "06_论证模式").mkdir()
    (styles / "06_论证模式" / "三段论.md").write_text("axis doc\n", encoding="utf-8")
    (styles / "00_索引").mkdir()
    (styles / "00_索引" / "_INDEX.md").write_text("index\n", encoding="utf-8")
    (root / "references" / "style-library.md").write_text("lib\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / "visual_qa.py").write_text("# qa\n", encoding="utf-8")
    (root / "scripts" / "leo-bootstrap.sh").write_text("# boot\n", encoding="utf-8")
    return root


class CapabilityManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = make_skill(self.tmp)
        self.out = self.tmp / "capability-manifest.json"

    def tearDown(self):
        self._tmp.cleanup()

    def manifest(self):
        proc = run("--root", str(self.root), "--out", str(self.out))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(self.out.read_text(encoding="utf-8"))

    def test_layer_counts_and_sha256_files(self):
        data = self.manifest()
        layers = data["layers"]
        # briefs: 3 (top + 01 + 02) — _content_rules excluded, axis doc not brief.
        self.assertEqual(layers["briefs"]["count"], 3)
        self.assertEqual(
            sorted(layers["briefs"]["files"]),
            ["references/styles/01_通用母版/商务蓝.md",
             "references/styles/02_行业内容域/金融风.md",
             "references/styles/清爽专业风.md"])
        self.assertEqual(layers["styles"]["count"], 6)  # every .md incl rules
        self.assertEqual(layers["references"]["count"], 7)
        self.assertEqual(layers["scripts"]["count"], 2)
        for path, digest in layers["scripts"]["files"].items():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertTrue((self.root / path).is_file())
        self.assertEqual(data["styles_axis_counts"]["02_行业内容域"], 1)

    def test_digest_is_content_sensitive(self):
        first = self.manifest()
        before = first["digest"]
        (self.root / "scripts" / "visual_qa.py").write_text("# qa v2\n",
                                                            encoding="utf-8")
        second = self.manifest()
        self.assertNotEqual(before, second["digest"])
        self.assertNotEqual(first["layers"]["scripts"]["digest"],
                            second["layers"]["scripts"]["digest"])
        self.assertEqual(first["layers"]["briefs"]["digest"],
                         second["layers"]["briefs"]["digest"])

    def test_compare_reports_counts_add_remove_and_hash_change(self):
        old_path = self.tmp / "old.json"
        run("--root", str(self.root), "--out", str(old_path))
        # mutate: add a brief, remove a script, change a reference
        (self.root / "references" / "styles" / "新风格.md").write_text(
            "brief N\n", encoding="utf-8")
        (self.root / "scripts" / "leo-bootstrap.sh").unlink()
        (self.root / "references" / "style-library.md").write_text(
            "lib v2\n", encoding="utf-8")
        proc = run("--root", str(self.root), "--out", str(self.out),
                   "--compare", str(old_path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("CHANGED", proc.stdout)
        data = json.loads(self.out.read_text(encoding="utf-8"))
        diff = data["compare"]
        self.assertFalse(diff["identical"])
        briefs = diff["layers"]["briefs"]
        self.assertEqual(briefs["count_delta"], 1)
        self.assertEqual(briefs["added"],
                         ["references/styles/新风格.md"])
        scripts = diff["layers"]["scripts"]
        self.assertEqual(scripts["removed"], ["scripts/leo-bootstrap.sh"])
        self.assertEqual(scripts["count_delta"], -1)
        refs = diff["layers"]["references"]
        self.assertEqual(refs["hash_changed"],
                         ["references/style-library.md"])

    def test_compare_identical_trees_clean(self):
        old_path = self.tmp / "old.json"
        run("--root", str(self.root), "--out", str(old_path))
        proc = run("--root", str(self.root), "--out", str(self.out),
                   "--compare", str(old_path))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("identical", proc.stdout)
        data = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertTrue(data["compare"]["identical"])
        for layer in data["compare"]["layers"].values():
            self.assertEqual(layer["added"], [])
            self.assertEqual(layer["removed"], [])
            self.assertEqual(layer["hash_changed"], [])
            self.assertEqual(layer["count_delta"], 0)

    def test_deterministic_output(self):
        first = self.manifest()
        payload_first = self.out.read_bytes()
        second = self.manifest()
        self.assertEqual(payload_first, self.out.read_bytes())
        self.assertEqual(first["digest"], second["digest"])

    def test_usage_errors_exit_two(self):
        proc = run("--root", str(self.tmp / "nope"))
        self.assertEqual(proc.returncode, 2)
        proc = run("--root", str(self.root), "--compare",
                   str(self.tmp / "missing.json"))
        self.assertEqual(proc.returncode, 2)

    def test_real_skill_tree_manifest_is_consistent(self):
        """旧清单仍可用；不能再拿人读目录的风格总数代替兼容计数。"""
        real = Path(__file__).resolve().parents[1]
        proc = run("--root", str(real))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["kind"], "capability-manifest")
        briefs = data["layers"]["briefs"]
        self.assertEqual(briefs["count"], len(briefs["files"]))
        self.assertTrue(all((real / path).is_file() for path in briefs["files"]))
        self.assertNotIn("references/styles/00_索引/_INDEX.md", briefs["files"])


if __name__ == "__main__":
    unittest.main()
