#!/usr/bin/env python3
"""lint_style_briefs.py 单测：R-25 negative_prompt / R-68 paired_illustration
字段校验（内置必填、参考风格豁免、形状/枚举错误、真实库存全绿）+
R-66 家族合并防回潮校验（同板顶层去重 / variant_of 归属 / variants 双向一致）。"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "lint_style_briefs.py"
SAMPLE = SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles") / "清爽专业风.md"

BRIEF = """# {name}

**适用场景:**
- 测试

**GPT-Image-2 风格 Brief:**
```json
{{
  "type": "16:9 full-slide PowerPoint image",
  "style_name": "{name}",
  "best_for": "测试",
  "visual_direction": "clean test style",
  "canvas": {{"aspect_ratio": "16:9", "background": "#FFFFFF",
             "composition": "test", "density": "medium"}},
  "color_palette": {{"primary": "{primary}", "secondary": "#0F766E",
                     "accent": "#F59E0B", "neutral": "#F8FAFC",
                     "rule": "restrained"}},
  "typography": {{"title": "思源黑体", "body": "Noto Sans SC", "labels": "Inter"}},
  "layout_patterns": ["a"]
{extra}}}
```
"""

NEGATIVE_AND_PAIRED = """,
  "negative_prompt": ["neon colors", "dense tables"],
  "paired_illustration": {"family": "flat", "density": "supportive"}"""


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args, capture_output=True, text=True
    )


def _fixture(tmp: Path, builtin_extra: str, reference_extra: str = "") -> Path:
    root = tmp / "skill"
    styles = root / Path("template-library/reference/sources/retired-styles-tree/styles")
    styles.mkdir(parents=True)
    (styles / "测试内置风.md").write_text(
        BRIEF.format(name="测试内置风", primary="#2563EB", extra=builtin_extra),
        encoding="utf-8")
    (styles / "测试内置风.layouts.json").write_text("{}", encoding="utf-8")
    ref_dir = styles / "01_通用母版" / "测试组"
    ref_dir.mkdir(parents=True)
    # distinct palette so the family-duplicate check stays silent in these
    # negative_prompt / paired_illustration fixtures
    (ref_dir / "测试参考风.md").write_text(
        BRIEF.format(name="测试参考风", primary="#7C2D12", extra=reference_extra),
        encoding="utf-8")
    return root


class FieldValidationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-lint-test-")
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_builtin_with_fields_passes_and_reference_exempt(self):
        root = _fixture(self.tmp, NEGATIVE_AND_PAIRED)
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("briefs=2", result.stdout)

    def test_builtin_missing_negative_prompt_is_error(self):
        root = _fixture(
            self.tmp,
            ',\n  "paired_illustration": {"family": "flat", "density": "core"}')
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("negative_prompt_missing", result.stdout)

    def test_builtin_missing_paired_illustration_is_error(self):
        root = _fixture(self.tmp, ',\n  "negative_prompt": ["neon"]')
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("paired_illustration_missing", result.stdout)

    def test_reference_without_fields_is_exempt(self):
        root = _fixture(self.tmp, NEGATIVE_AND_PAIRED, reference_extra="")
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_density_is_error(self):
        root = _fixture(
            self.tmp,
            ',\n  "negative_prompt": ["neon"],\n'
            '  "paired_illustration": {"family": "flat", "density": "heavy"}')
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("paired_illustration_invalid", result.stdout)
        self.assertIn("density", result.stdout)

    def test_unknown_family_is_error(self):
        root = _fixture(
            self.tmp,
            ',\n  "negative_prompt": ["neon"],\n'
            '  "paired_illustration": {"family": "pixel-noise", "density": "core"}')
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("family", result.stdout)

    def test_empty_negative_list_is_error(self):
        root = _fixture(
            self.tmp,
            ',\n  "negative_prompt": [],\n'
            '  "paired_illustration": {"family": "flat", "density": "core"}')
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("negative_prompt_invalid", result.stdout)

    def test_reference_with_malformed_field_still_validated(self):
        root = _fixture(
            self.tmp, NEGATIVE_AND_PAIRED,
            reference_extra=',\n  "negative_prompt": "not-a-list"')
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("negative_prompt_invalid", result.stdout)


class FamilyMergeLintTest(unittest.TestCase):
    """R-66 家族合并防回潮：同板顶层去重、variant_of 归属、variants 双向一致。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-lint-fam-")
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _root(self) -> Path:
        root = self.tmp / "skill"
        (root / Path("template-library/reference/sources/retired-styles-tree/styles")).mkdir(parents=True, exist_ok=True)
        return root

    def _write(self, root: Path, rel: str, name: str, primary: str = "#2563EB",
               extra: str = "") -> None:
        p = root / Path("template-library/reference/sources/retired-styles-tree/styles") / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(BRIEF.format(name=name, primary=primary, extra=extra),
                     encoding="utf-8")

    PRIMARY = ',\n  "variants": ["测试变体风: 同板场景变体，差异说明"]'
    VARIANT = ',\n  "variant_of": "测试主风格风"'

    def test_same_palette_without_attribution_is_family_duplicate(self):
        root = self._root()
        self._write(root, "01_通用母版/甲/测试主风格风.md", "测试主风格风")
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风")
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("family_duplicate", result.stdout)

    def test_same_palette_with_variant_attribution_passes(self):
        root = self._root()
        self._write(root, "01_通用母版/甲/测试主风格风.md", "测试主风格风",
                    extra=self.PRIMARY)
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风",
                    extra=self.VARIANT)
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_distinct_palettes_stay_independent(self):
        root = self._root()
        self._write(root, "01_通用母版/甲/测试主风格风.md", "测试主风格风")
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风",
                    primary="#7C2D12")
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_variant_of_unknown_target_is_error(self):
        root = self._root()
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风",
                    extra=self.VARIANT)
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("variant_target_missing", result.stdout)

    def test_variant_chain_is_error(self):
        root = self._root()
        self._write(root, "01_通用母版/甲/测试中间风.md", "测试中间风",
                    extra=',\n  "variant_of": "测试主风格风"')
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风",
                    extra=',\n  "variant_of": "测试中间风"')
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("variant_chain", result.stdout)

    def test_variants_list_mismatch_is_error(self):
        root = self._root()
        # declares 变体 A but the actual variant file points elsewhere via name
        self._write(root, "01_通用母版/甲/测试主风格风.md", "测试主风格风",
                    extra=',\n  "variants": ["别的变体风: 同板场景变体"]')
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风",
                    extra=self.VARIANT)
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("variants_list_mismatch", result.stdout)

    def test_variant_pointing_at_primary_without_list_is_error(self):
        root = self._root()
        self._write(root, "01_通用母版/甲/测试主风格风.md", "测试主风格风")
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风",
                    primary="#7C2D12", extra=self.VARIANT)
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("variants_list_missing", result.stdout)

    def test_variant_carrying_variants_list_is_conflict(self):
        root = self._root()
        self._write(root, "01_通用母版/甲/测试主风格风.md", "测试主风格风",
                    extra=self.PRIMARY)
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风",
                    extra=self.PRIMARY + self.VARIANT)
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("variant_fields_conflict", result.stdout)

    def test_empty_variant_of_string_is_shape_error(self):
        root = self._root()
        self._write(root, "01_通用母版/乙/测试变体风.md", "测试变体风",
                    extra=',\n  "variant_of": "  "')
        result = _run(["--root", str(root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("variant_of_invalid", result.stdout)


class RealLibraryTest(unittest.TestCase):
    def test_real_library_lints_green(self):
        result = _run([])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Parallel intake batches grow the library concurrently; pin a
        # monotonic floor (S3 snapshot 223) instead of a hard total so
        # sibling batches do not break this gate.
        m = re.search(r"briefs=(\d+)", result.stdout)
        self.assertIsNotNone(m, result.stdout)
        self.assertGreaterEqual(int(m.group(1)), 223)

    def test_real_briefs_carry_both_fields(self):
        text = SAMPLE.read_text(encoding="utf-8")
        self.assertIn('"negative_prompt"', text)
        self.assertIn('"paired_illustration"', text)


if __name__ == "__main__":
    unittest.main()
