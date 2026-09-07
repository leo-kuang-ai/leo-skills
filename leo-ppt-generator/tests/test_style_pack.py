"""风格包导入导出测试（R-33）。

覆盖：export 完整打包（brief/sidecar/缩略图/manifest sha256）、export 参考风格
无 sidecar、export 未知风格名 exit 2、import 干净包入位、import 缺 manifest
拒收、manifest 缺必备键拒收、manifest 声明文件缺失拒收（AE-43）、brief 过不了
lint 拒收、同名冲突拒收、同板 family_duplicate 预检拒收、import 顶层位置要求
--target（exit 2）、round-trip 内容一致。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import style_pack  # noqa: E402

SCRIPT_PATH = SCRIPTS_DIR / "style_pack.py"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True, text=True,
    )


PALETTE_A = {
    "primary": "deep navy #1A2B4C",
    "secondary": "cool gray #8A93A6",
    "accent": "signal amber #D97A1F",
    "neutral": "ink #14161B, hairline #E3E6EC",
    "rule": "one accent per slide",
}
# Distinct HEX set: the builtin and the reference style must not share a
# palette fingerprint, or the family_duplicate pre-check fires on import.
PALETTE_B = {
    "primary": "warm ivory #F5F1E8",
    "secondary": "clay #B96A4B",
    "accent": "deep teal #0F6B66",
    "neutral": "graphite #2E2A26, hairline #DED5C4",
    "rule": "warm neutrals, teal only for emphasis",
}


def brief_md(style_name: str, palette: dict | None = None,
             extra: str = "") -> str:
    brief = {
        "type": "16:9 full-slide PowerPoint image",
        "style_name": style_name,
        "best_for": "unit-test fixture deck",
        "visual_direction": "calm gridded report look",
        "canvas": {"aspect_ratio": "16:9", "background": "paper white",
                   "composition": "title block top-left", "density": "medium"},
        "color_palette": palette or PALETTE_A,
        "typography": {"title": "思源黑体 Bold", "body": "Noto Sans SC",
                       "labels": "Inter small caps"},
        "layout_patterns": ["cover with quiet title block"],
    }
    return (
        f"# {style_name}\n\nGPT-Image-2 风格 Brief：\n\n```json\n"
        + json.dumps(brief, ensure_ascii=False, indent=2)
        + f"\n```\n{extra}\n"
    )


class FixtureLibrary:
    """Minimal skill root: one builtin (top level) + one reference style."""

    def __init__(self, base: Path):
        self.root = base / "root"
        styles = self.root / "references" / "styles"
        (styles / "01_通用母版" / "商务专业").mkdir(parents=True)
        builtin = styles / "测试内置风.md"
        builtin.write_text(brief_md("测试内置风", palette=PALETTE_B), encoding="utf-8")
        (styles / "测试内置风.layouts.json").write_text(
            json.dumps({"layout_id": "routing", "routing": []}), encoding="utf-8")
        ref = styles / "01_通用母版" / "商务专业" / "测试参考风.md"
        ref.write_text(brief_md("测试参考风"), encoding="utf-8")
        self.ref_path = ref


class ExportBehavior(unittest.TestCase):
    def test_export_builtin_packs_brief_sidecar_thumbs_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            result = run_cli("export", "清爽专业风", "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["style_name"], "清爽专业风")
            self.assertEqual(manifest["pack_version"], 1)
            roles = {e["role"]: e for e in manifest["files"]}
            self.assertIn("brief", roles)
            self.assertIn("token_sidecar", roles)
            self.assertGreaterEqual(len([e for e in manifest["files"]
                                         if e["role"] == "thumbnail"]), 1)
            # No timestamps: byte-identical on repeat export (determinism).
            out2 = Path(tmp) / "pack2"
            run_cli("export", "清爽专业风", "--out", str(out2))
            self.assertEqual((out / "manifest.json").read_bytes(),
                             (out2 / "manifest.json").read_bytes())

    def test_export_unknown_style_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("export", "不存在的风格", "--out", str(Path(tmp) / "p"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("style_not_found", result.stderr)


class ImportBehavior(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.lib = FixtureLibrary(base)
        self.pack = base / "pack"
        result = run_cli("export", "测试参考风", "--out", str(self.pack),
                         "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def tearDown(self):
        self._tmp.cleanup()

    def _resync_brief_sha(self, style_name: str | None = None) -> None:
        """Rewrite manifest brief sha256 (and name) after editing brief.md."""
        import hashlib
        manifest = json.loads((self.pack / "manifest.json").read_text(encoding="utf-8"))
        if style_name:
            manifest["style_name"] = style_name
        for entry in manifest["files"]:
            if entry.get("role") == "brief":
                entry["sha256"] = hashlib.sha256(
                    (self.pack / "brief.md").read_bytes()).hexdigest()
        (self.pack / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    def test_import_clean_pack_places_brief_in_target(self):
        # Cross-machine shape: export, remove the source, import elsewhere.
        exported_bytes = self.lib.ref_path.read_bytes()
        self.lib.ref_path.unlink()
        result = run_cli("import", str(self.pack),
                         "--target", "01_通用母版/极简排版",
                         "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        dest = (self.lib.root / "references" / "styles" / "01_通用母版"
                / "极简排版" / "测试参考风.md")
        self.assertTrue(dest.is_file())
        # Round-trip: imported bytes equal the exported source brief.
        self.assertEqual(dest.read_bytes(), exported_bytes)

    def test_import_preserves_optional_governance_metadata(self):
        path = self.pack / "brief.md"
        brief = style_pack._parse_brief(path)
        brief.update(source={"license": "unknown"}, taxonomy={"families": ["family:business-professional"]})
        path.write_text("```json\n" + json.dumps(brief, ensure_ascii=False) + "\n```\n")
        self._resync_brief_sha()
        self.lib.ref_path.unlink()
        result = run_cli("import", str(self.pack), "--target", "01_通用母版/极简排版", "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        dest = self.lib.root / "references/styles/01_通用母版/极简排版/测试参考风.md"
        self.assertEqual(dest.read_bytes(), path.read_bytes())

    def test_import_rejects_invalid_governance_metadata(self):
        path = self.pack / "brief.md"
        brief = style_pack._parse_brief(path)
        brief["source"] = {"license": "made-up"}
        path.write_text("```json\n" + json.dumps(brief, ensure_ascii=False) + "\n```\n")
        self._resync_brief_sha()
        self.lib.ref_path.unlink()
        result = run_cli("import", str(self.pack), "--target", "01_通用母版/极简排版", "--root", str(self.lib.root))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("metadata_invalid", result.stdout + result.stderr)
        self.assertFalse((self.lib.root / "references/styles/01_通用母版/极简排版/测试参考风.md").exists())

    def test_import_missing_manifest_rejected_with_list(self):
        (self.pack / "manifest.json").unlink()
        result = run_cli("import", str(self.pack), "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("manifest_missing", result.stdout)
        self.assertIn("REJECTED", result.stdout)

    def test_import_manifest_missing_required_keys_rejected(self):
        manifest = json.loads((self.pack / "manifest.json").read_text(encoding="utf-8"))
        del manifest["style_name"]
        # Demote the brief entry to a non-brief role so `files` stays non-empty
        # and both the style_name and brief-role checks are exercised.
        for entry in manifest["files"]:
            if entry.get("role") == "brief":
                entry["role"] = "other"
        (self.pack / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        result = run_cli("import", str(self.pack), "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("manifest_style_name", result.stdout)
        self.assertIn("manifest_brief_role", result.stdout)

    def test_import_declared_file_missing_rejected_with_list(self):
        # AE-43: manifest declares a file the pack does not carry -> reject.
        (self.pack / "brief.md").unlink()
        result = run_cli("import", str(self.pack), "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("file_missing: brief.md", result.stdout)

    def test_import_brief_failing_lint_rejected(self):
        broken = brief_md("测试坏风")
        broken = broken.replace('"best_for": "unit-test fixture deck",\n', "")
        (self.pack / "brief.md").write_text(broken, encoding="utf-8")
        self._resync_brief_sha()
        result = run_cli("import", str(self.pack), "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("required_missing", result.stdout)

    def test_import_name_conflict_rejected(self):
        result = run_cli("import", str(self.pack),
                         "--target", "01_通用母版/商务专业",
                         "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("name_conflict: 测试参考风", result.stdout)

    def test_import_same_palette_family_duplicate_rejected(self):
        # New name but identical palette -> family_duplicate pre-check (R-66).
        variant = brief_md("测试同板风")
        (self.pack / "brief.md").write_text(variant, encoding="utf-8")
        self._resync_brief_sha("测试同板风")
        result = run_cli("import", str(self.pack),
                         "--target", "01_通用母版/极简排版",
                         "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("family_duplicate", result.stdout)

    def test_import_variant_of_same_palette_allowed(self):
        # Same palette but declared as a family variant passes the pre-check.
        variant = brief_md("测试变体风", extra="")
        variant = variant.replace(
            '"layout_patterns"',
            '"variant_of": "测试内置风",\n  "layout_patterns"')
        (self.pack / "brief.md").write_text(variant, encoding="utf-8")
        self._resync_brief_sha("测试变体风")
        result = run_cli("import", str(self.pack),
                         "--target", "01_通用母版/极简排版",
                         "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_import_top_level_source_requires_target(self):
        # A pack exported from the top level cannot return there without a
        # target; remove the source first so only the usage path is exercised.
        builtin_pack = Path(self._tmp.name) / "builtin-pack"
        run_cli("export", "测试内置风", "--out", str(builtin_pack),
                "--root", str(self.lib.root))
        (self.lib.root / "references" / "styles" / "测试内置风.md").unlink()
        result = run_cli("import", str(builtin_pack), "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 2)
        self.assertIn("--target", result.stderr)

    def test_import_manifest_path_escape_to_sibling_dir_rejected(self):
        # "../pack-evil/brief.md" resolves to a sibling of pack/ sharing its
        # path prefix — a str.startswith boundary would wave it through and
        # let out-of-pack files join validation/copying.
        evil = Path(self._tmp.name) / "pack-evil"
        evil.mkdir()
        (evil / "brief.md").write_bytes((self.pack / "brief.md").read_bytes())
        manifest = json.loads(
            (self.pack / "manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            if entry.get("role") == "brief":
                entry["path"] = "../pack-evil/brief.md"
        (self.pack / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        result = run_cli("import", str(self.pack), "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("path_escape: ../pack-evil/brief.md", result.stdout)
        self.assertIn("REJECTED", result.stdout)

    def test_import_target_traversal_into_styles_sibling_rejected(self):
        # "01_通用母版/../../styles-evil" passes the IMPORTABLE_PREFIXES gate
        # and resolves to a styles-prefixed sibling of the styles root.
        self.lib.ref_path.unlink()
        result = run_cli("import", str(self.pack),
                         "--target", "01_通用母版/../../styles-evil",
                         "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 2)
        self.assertIn("逃逸风格库根", result.stderr)
        self.assertFalse(
            (self.lib.root / "references" / "styles-evil").exists())

    def test_import_missing_pack_dir_is_usage_error(self):
        result = run_cli("import", str(Path(self._tmp.name) / "nope"),
                         "--root", str(self.lib.root))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
