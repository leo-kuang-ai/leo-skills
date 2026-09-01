#!/usr/bin/env python3
"""lint_skill_structure.py 单元测试（R-57 技能结构 lint）：健康树全绿 /
断链定位（SKILL.md 与 references 内、markdown 链接与反引号两形态）/
行数超限 ERROR 与预警 WARN / frontmatter 缺 name/description / URL 与占位符
豁免 / vendored 来源目录豁免 / 上游叙述行豁免 / 前缀匹配（patches/0007）/
用法错误 exit 2。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lint_skill_structure.py"

GOOD_FRONTMATTER = "---\nname: demo-skill\ndescription: 当用户要求演示时使用。\n---\n\n# Demo\n"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8")


def make_tree(tmp: Path, skill_md: str, refs: dict[str, str] | None = None,
              refs_files: list[str] | None = None) -> Path:
    root = tmp / f"skill-{len(list(tmp.iterdir()))}"
    (root / "references").mkdir(parents=True)
    root.joinpath("SKILL.md").write_text(skill_md, encoding="utf-8")
    for rel, content in (refs or {}).items():
        path = root / "references" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for rel in refs_files or []:
        path = root / "references" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")
    return root


class LintSkillStructureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_healthy_tree_passes_exit_zero(self):
        root = make_tree(
            self.tmp,
            GOOD_FRONTMATTER + "见 [风格库](references/style-library.md) 与 "
            "`scripts/visual_qa.py`。\n",
            refs={"style-library.md": "见 `references/style-library.md` 自身。"},
            refs_files=["nested/guide.md"],
        )
        (root / "references" / "style-library.md").write_text(
            "深页见 [nested](nested/guide.md)。\n", encoding="utf-8")
        (root / "scripts").mkdir()
        (root / "scripts" / "visual_qa.py").write_text("# ok\n", encoding="utf-8")
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("0 error(s)", proc.stdout)

    def test_broken_markdown_link_in_skill_md_is_located(self):
        root = make_tree(self.tmp, GOOD_FRONTMATTER +
                         "读 [执行合同](references/no-such.md)。\n")
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("断链", proc.stderr)
        self.assertIn("references/no-such.md", proc.stderr)
        self.assertIn("SKILL.md:7", proc.stderr)

    def test_broken_backtick_path_in_references_is_located(self):
        root = make_tree(self.tmp, GOOD_FRONTMATTER + "\n",
                         refs={"guide.md": "先跑 `scripts/ghost.py` 再继续。\n"})
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("guide.md:1", proc.stderr)
        self.assertIn("scripts/ghost.py", proc.stderr)

    def test_over_limit_is_error_and_warn_threshold_only_warns(self):
        body = GOOD_FRONTMATTER + "\n" + "filler line\n" * 460
        root = make_tree(self.tmp, body)
        proc = run("--root", str(root), "--max-lines", "455", "--warn-lines", "450")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("超过上限 455", proc.stderr)
        proc = run("--root", str(root))  # defaults: 450 < lines <= 500
        self.assertEqual(proc.returncode, 0)
        self.assertRegex(proc.stdout, r"WARN: SKILL\.md 共 \d+ 行，超过预警线 450")

    def test_missing_frontmatter_name_or_description_fails(self):
        root = make_tree(self.tmp, "---\nname: x\n---\n# 无描述\n")
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("description", proc.stderr)
        root = make_tree(self.tmp, "# 没有 frontmatter\n")
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("frontmatter", proc.stderr)

    def test_urls_anchors_and_placeholders_are_exempt(self):
        root = make_tree(self.tmp, GOOD_FRONTMATTER + (
            "外链 [spec](https://example.com/a.md) 与锚点 [x](#section)、"
            "占位符 `<run>/reports/x.json` 与 `${HOME}/y` 均不算断链。\n"))
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_vendored_source_dirs_and_upstream_lines_are_exempt(self):
        root = make_tree(self.tmp, GOOD_FRONTMATTER + (
            "上游改编自 frontend-slides `scripts/export-pdf.sh`，未转写。\n"),
            refs={"04_来源_demo/upstream.md": "见 `assets/upstream-only.html`\n"})
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_upstream_context_on_previous_line_is_exempt(self):
        # "> 上游出处：\n> xhs-visual-director-skill `templates/x.md`" — the
        # narrative word sits on the line ABOVE the reference.
        root = make_tree(self.tmp, GOOD_FRONTMATTER + "\n",
                         refs={"style-extension-template.md":
                               "> 上游出处：\n"
                               "> xhs-visual-director-skill "
                               "`templates/style_extension_template.md`。\n"})
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # Same reference WITHOUT upstream narrative must still be a broken link.
        root2 = make_tree(self.tmp, GOOD_FRONTMATTER + "\n",
                          refs={"plain.md": "见 `templates/style_extension_template.md`。\n"})
        proc2 = run("--root", str(root2))
        self.assertEqual(proc2.returncode, 1)

    def test_prefix_reference_matches_patched_sibling(self):
        root = make_tree(self.tmp, GOOD_FRONTMATTER +
                         "vendor patch（`patches/0007`）见上文。\n")
        (root / "patches").mkdir()
        (root / "patches" / "0007-codex-required-text.patch").write_text(
            "diff\n", encoding="utf-8")
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_usage_errors_exit_two(self):
        proc = run("--root", str(self.tmp / "nope"))
        self.assertEqual(proc.returncode, 2)
        proc = run("--root", str(self.tmp), "--warn-lines", "600",
                   "--max-lines", "500")
        self.assertEqual(proc.returncode, 2)

    def test_current_skill_tree_stays_green(self):
        """验收锚点：lint 对本技能当前树必须全绿（防入口可见性缺口复发）。"""
        root = Path(__file__).resolve().parents[1]
        proc = run("--root", str(root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("0 error(s)", proc.stdout)


if __name__ == "__main__":
    unittest.main()
