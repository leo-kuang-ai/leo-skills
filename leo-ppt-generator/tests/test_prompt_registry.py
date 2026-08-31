"""E6 提示词进化记账（prompts/registry.yaml）的治理检查测试（gamma M0）。

覆盖可观察行为：

- 仓库现状 registry schema 合法且覆盖全部 prompts/*.md（无 FAIL）；
- prompts/ 下 .md 缺 registry 条目 → lint FAIL；
- 条目指向不存在的文件 → 仅 WARN 不 FAIL；
- schema 非法（缺字段 / 非法 change / file 非 prompts/ 路径）→ FAIL。
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]


def _load_lint_module():
    spec = importlib.util.spec_from_file_location(
        "lint_style_governance", SKILL_DIR / "scripts" / "lint_style_governance.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LINT = _load_lint_module()

_VALID_REGISTRY = """\
schema_version: 1
entries:
  - id: prompt-0001
    date: "2026-08-30"
    name: covered-change
    file: prompts/slide-worker.md
    improvement: 覆盖性登记
    dimension: registry-coverage
    change: updated
    lesson: 文件级引用满足检查
    related_eval: null
"""


def _run_check(prompts_dir: Path, registry_body: str | None):
    errors: list[str] = []
    warnings: list[str] = []
    registry_path = prompts_dir / "registry.yaml"
    if registry_body is not None:
        registry_path.write_text(registry_body, encoding="utf-8")
    LINT._check_prompt_registry(errors, warnings, prompts_dir=prompts_dir, registry_path=registry_path)
    return errors, warnings


class RepoRegistryStateTest(unittest.TestCase):
    def test_repo_registry_is_valid_and_covers_every_prompt(self):
        errors, warnings = _run_check(LINT.PROMPTS_DIR, None)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class MissingEntryFailsTest(unittest.TestCase):
    def test_prompt_file_without_registry_entry_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompts_dir = Path(tmp) / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "slide-worker.md").write_text("prompt", encoding="utf-8")
            (prompts_dir / "page-worker.md").write_text("prompt", encoding="utf-8")
            registry = _VALID_REGISTRY  # 只覆盖 slide-worker.md
            errors, _ = _run_check(prompts_dir, registry)
            self.assertTrue(
                any("page-worker.md" in item and "无任何 registry 条目" in item for item in errors)
            )

    def test_absent_registry_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompts_dir = Path(tmp) / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "slide-worker.md").write_text("prompt", encoding="utf-8")
            errors, _ = _run_check(prompts_dir, None)
            self.assertTrue(any("registry.yaml 不存在" in item for item in errors))


class ExtraEntryWarnsOnlyTest(unittest.TestCase):
    def test_stale_entry_warns_but_does_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompts_dir = Path(tmp) / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "slide-worker.md").write_text("prompt", encoding="utf-8")
            stale = _VALID_REGISTRY + """\
  - id: prompt-0002
    date: "2026-08-30"
    name: stale-entry
    file: prompts/ghost-worker.md
    improvement: 指向已删除文件
    dimension: registry-coverage
    change: removed
    lesson: removed 条目允许字段缺省，仅提示
    related_eval: null
"""
            errors, warnings = _run_check(prompts_dir, stale)
            # ghost 条目只 WARN；slide-worker.md 仍在册不产生新 FAIL。
            self.assertTrue(
                any("ghost-worker.md" in item for item in warnings)
            )
            self.assertEqual(errors, [])


class InvalidSchemaFailsTest(unittest.TestCase):
    def test_entry_missing_required_fields_fails(self):
        broken = """\
schema_version: 1
entries:
  - id: prompt-0001
    file: prompts/slide-worker.md
"""
        with tempfile.TemporaryDirectory() as tmp:
            prompts_dir = Path(tmp) / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "slide-worker.md").write_text("prompt", encoding="utf-8")
            errors, _ = _run_check(prompts_dir, broken)
            self.assertTrue(any("缺字段" in item for item in errors))

    def test_invalid_change_value_fails(self):
        broken = _VALID_REGISTRY.replace("change: updated", "change: hotfix")
        with tempfile.TemporaryDirectory() as tmp:
            prompts_dir = Path(tmp) / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "slide-worker.md").write_text("prompt", encoding="utf-8")
            errors, _ = _run_check(prompts_dir, broken)
            self.assertTrue(any("change 须 ∈" in item for item in errors))

    def test_file_outside_prompts_prefix_fails(self):
        broken = _VALID_REGISTRY.replace(
            "file: prompts/slide-worker.md", "file: references/deck-master.md"
        )
        with tempfile.TemporaryDirectory() as tmp:
            prompts_dir = Path(tmp) / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "slide-worker.md").write_text("prompt", encoding="utf-8")
            errors, _ = _run_check(prompts_dir, broken)
            self.assertTrue(any("file 须为 prompts/ 相对路径" in item for item in errors))

    def test_non_map_or_wrong_schema_version_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompts_dir = Path(tmp) / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "slide-worker.md").write_text("prompt", encoding="utf-8")
            errors, _ = _run_check(prompts_dir, "schema_version: 2\nentries: []\n")
            self.assertTrue(any("schema_version" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
