"""layout-bank 只读查询层（B1/U10）的合同测试：加载器 fail-fast、
layout-profile 合同形状、风格路由视图悬空引用拒绝、style list 不混入
版式实体、lint 配对检查 A/B/C。

U10 切换后版式真值在 template-library/canonical/layouts/<slug>/layout.json
（P 码=别名）；旧 template-library/reference/sources/retired-styles-tree/styles 树的 reuse_friendly/max_per_deck 字段
不在新协议内（复用上限仍由 scripts/check_layout_reuse.py 按旧 sidecar 审计，
直到旧树退役）。设计对照 docs/plans/fusion-team-designs/团队β-风格版式资产层.md
§3.1/§5 与 2026-09-08-001 §5。
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator import layout_bank, styles  # noqa: E402

# layout-profile-v1 合同键（治理 schema 声明的实体面）。
PROFILE_FIELDS = {
    "schema_version", "entity", "asset_id", "name", "aliases", "canvas",
    "page_role", "layout_type", "slots", "renderer_support",
}


class LoadLayoutBankTests(unittest.TestCase):
    def test_load_layout_bank_returns_profile_contract_fields(self):
        data = layout_bank.load_layout_bank("P6")
        self.assertEqual(data["layout_id"], "P6")
        self.assertEqual(data["name"], "KPI Tower")
        self.assertEqual(data["page_role"], "data")
        # 合同字段齐备，治理外的旧语义字段（五字段封顶口径）已随 sidecar 退役。
        self.assertTrue(PROFILE_FIELDS <= set(data))
        self.assertIsInstance(data["slots"]["items"]["count_min"], int)
        self.assertRegex(data["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(data["entity"], "layout-profile")

    def test_load_layout_bank_fails_fast_on_missing_sidecar(self):
        with self.assertRaises(styles.StyleStoreError) as ctx:
            layout_bank.load_layout_bank("P99")
        self.assertIn("layout_bank_not_found", str(ctx.exception))

    def test_list_layout_bank_covers_forty_two_with_fingerprints(self):
        # 42 = 36 P 码 image-lane + 6 html-lane 版式（U9/F4 引入，登记性更新）
        items = layout_bank.list_layout_bank()
        self.assertEqual(len(items), 42)
        ids = [item["layout_id"] for item in items]
        self.assertEqual(ids, sorted(ids))  # 确定性排序
        self.assertEqual(ids[0], "P1")
        for item in items:
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            # page_role 词汇表以 layout-profile-v1 schema 枚举为准
            self.assertIn(item["page_type"], (
                "cover", "agenda", "section", "content", "data", "quote", "evidence", "closing"))


def _write_library(bundle: Path) -> None:
    library = bundle / "template-library"
    layouts = library / "canonical" / "layouts" / "p1-01-cover-layouts"
    styles_dir = library / "canonical" / "styles" / "test-style"
    layouts.mkdir(parents=True)
    styles_dir.mkdir(parents=True)
    (layouts / "layout.json").write_text(json.dumps({
        "schema_version": 1, "entity": "layout-profile",
        "asset_id": "builtin:layout:p1-01-cover-layouts", "name": "Cover",
        "aliases": ["P1"],
        "canvas": {"width": 1280, "height": 720, "units": "logical-px"},
        "page_role": "cover", "layout_type": "fixed-regions",
        "slots": {"title": {"region": "content", "desc": "t",
                            "chars_per_line": 7, "max_lines": 1, "max_chars": 8}},
        "renderer_support": {"render:html": None, "image": "test"},
    }), encoding="utf-8")
    (styles_dir / "brief.json").write_text(json.dumps({
        "schema_version": 2, "entity": "style-brief",
        "asset_id": "builtin:style:test-style", "name": "测试风",
        "lifecycle": "active", "taxonomy": {"families": ["测试族"]},
        "visual_language": {"direction": "test direction"},
        "bindings": {
            "capacity_factor": {"text": 1.0},
            "layout_routes": [{"page_type": "cover", "preferred": ["P99"],
                               "discouraged": []}],
        },
    }), encoding="utf-8")
    (library / "library.json").write_text(json.dumps({
        "schema_version": 1, "kind": "template-library", "library_id": "builtin",
        "zones": {"canonical": "c", "reference": "r", "governance": "g",
                  "catalog": "k", "evidence": "e"},
        "reserved_directory_names": [],
    }), encoding="utf-8")


class LoadStyleLayoutsTests(unittest.TestCase):
    def test_style_layouts_query_includes_sha256(self):
        data = layout_bank.load_style_layouts("手绘白板风")
        self.assertEqual(data["style_id"], "builtin:style:handdrawn-whiteboard")
        self.assertEqual(data["capacity_factor"]["text"], 0.85)
        self.assertRegex(data["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(data["routing"])

    def test_style_layouts_missing_sidecar_fails_fast(self):
        with self.assertRaises(styles.StyleStoreError) as ctx:
            layout_bank.load_style_layouts("不存在的风格")
        self.assertIn("layout_bank_not_found", str(ctx.exception))

    def test_style_layouts_dangling_reference_rejected(self):
        # 临时 template-library：路由引用 P99（不存在）→ 加载边界拒绝。
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td)
            _write_library(bundle)
            with mock.patch.dict("os.environ",
                                 {"LEO_PPT_BUNDLE": str(bundle)}):
                with self.assertRaises(styles.StyleStoreError) as ctx:
                    layout_bank.load_style_layouts("测试风")
        self.assertIn("悬空版式引用", str(ctx.exception))


class StyleListIsolationTests(unittest.TestCase):
    def test_style_list_ignores_layout_entities(self):
        # 新库枚举只含 style 实体（kind 过滤在 resolver 内）：版式实体绝不
        # 混入可加载风格清单，且数量覆盖迁移后的全量 brief。
        entries = styles.list_styles()
        self.assertGreaterEqual(len(entries), 300)
        names = {e["name"] for e in entries}
        self.assertIn("清爽专业风", names)
        self.assertFalse(any(n.endswith(".layouts") for n in names))
        self.assertNotIn("KPI Tower", names)  # 版式名不是风格名


class LintPairingTests(unittest.TestCase):
    """lint_layout_grid 检查 A/B/C 的负例（临时目录 + 常量替换）。"""

    def _run_lint(self, tmp: Path) -> list[str]:
        import importlib

        script = SKILL_DIR / "scripts" / "lint_layout_grid.py"
        spec = importlib.util.spec_from_file_location(
            f"lint_layout_grid_{id(tmp)}", script
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with mock.patch.object(mod, "LAYOUT_DIR", tmp / "12_版式库"), \
                mock.patch.object(mod, "STYLES_DIR", tmp):
            errors: list[str] = []
            mod._lint_sidecars(errors)
            return errors

    def _run_canonical_lint(self, tmp: Path) -> list[str]:
        import importlib

        script = SKILL_DIR / "scripts" / "lint_layout_grid.py"
        spec = importlib.util.spec_from_file_location(
            f"lint_layout_grid_canonical_{id(tmp)}", script
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with mock.patch.object(mod, "CANONICAL_LAYOUTS_DIR", tmp / "canonical" / "layouts"), \
                mock.patch.object(mod, "CANONICAL_TEMPLATES_DIR", tmp / "canonical" / "templates"), \
                mock.patch.object(mod, "CANONICAL_LAYOUT_MANIFEST", tmp / "canonical" / "layouts" / "manifest.json"):
            errors: list[str] = []
            mod._lint_canonical_profiles(errors)
            return errors

    def _make_canonical_profile(self, tmp: Path, *, max_chars: int = 24,
                                canvas: tuple[int, int] = (1280, 720)) -> None:
        layout_dir = tmp / "canonical" / "layouts" / "test-layout"
        template_dir = tmp / "canonical" / "templates" / "test-template"
        layout_dir.mkdir(parents=True, exist_ok=True)
        template_dir.mkdir(parents=True, exist_ok=True)
        layout_payload = {
            "schema_version": 1, "entity": "layout-profile",
            "asset_id": "builtin:layout:test-layout", "name": "Test",
            "aliases": ["P1"],
            "canvas": {"width": canvas[0], "height": canvas[1], "units": "logical-px"},
            "page_role": "content", "layout_type": "fixed-regions",
            "slots": {"title": {"region": "content", "chars_per_line": 10,
                                  "max_lines": 2, "max_chars": max_chars}},
            "renderer_support": {"render:html": "builtin:template:test-template", "image": None},
            "regions": {"content": {"x": 0, "y": 0, "width": 1280, "height": 720}},
        }
        layout_path = layout_dir / "layout.json"
        layout_path.write_text(json.dumps(layout_payload), encoding="utf-8")
        notes_path = layout_dir / "notes.md"
        notes_path.write_text("# Test layout\n", encoding="utf-8")
        (template_dir / "template.json").write_text(json.dumps({
            "schema_version": 1, "entity": "render-template",
            "asset_id": "builtin:template:test-template", "name": "Test",
        }), encoding="utf-8")
        layout_sha = hashlib.sha256(layout_path.read_bytes()).hexdigest()
        (tmp / "canonical" / "layouts" / "manifest.json").write_text(
            json.dumps({
                "schema_version": 1,
                "entity": "layout-profile-manifest",
                "owner": "template-library/canonical/layouts",
                "entries": [{
                    "profile": "test-layout/layout.json",
                    "asset_id": layout_payload["asset_id"],
                    "notes": "test-layout/notes.md",
                    "revision": layout_sha[:16],
                    "layout_sha256": layout_sha,
                    "notes_sha256": hashlib.sha256(notes_path.read_bytes()).hexdigest(),
                }],
            }), encoding="utf-8")

    def _make_layout(self, tmp: Path, stem: str, p_code: str) -> None:
        layout_dir = tmp / "12_版式库"
        layout_dir.mkdir(parents=True, exist_ok=True)
        (layout_dir / f"{stem}.md").write_text(
            f"# 版式：{p_code} · Test\n\n**用途:** t\n", encoding="utf-8",
        )
        (layout_dir / f"{stem}.layouts.json").write_text(json.dumps({
            "schema_version": 1, "entity": "layout", "layout_id": p_code,
            "name": "Test", "page_type": "content",
            "visual_signature": "t",
            "content_capacity": {"desc": {
                "desc": "t", "chars_per_line": 10, "max_lines": 2,
                "max_chars": 24,
            }},
            "best_for": ["x"], "avoid_for": ["y"], "reuse_friendly": True,
        }), encoding="utf-8")

    def test_lint_layout_grid_errors_on_missing_sidecar(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_layout(tmp, "01_Cover", "P1")
            (tmp / "12_版式库" / "01_Cover.layouts.json").unlink()
            errors = self._run_lint(tmp)
            self.assertTrue(
                any("sidecar_missing" in e for e in errors), errors,
            )

    def test_lint_layout_grid_errors_on_p_code_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_layout(tmp, "01_Cover", "P1")
            sidecar = tmp / "12_版式库" / "01_Cover.layouts.json"
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["layout_id"] = "P2"
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            errors = self._run_lint(tmp)
            self.assertTrue(
                any("sidecar_p_code_mismatch" in e for e in errors), errors,
            )

    def test_lint_layout_grid_errors_on_capacity_inconsistency(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_layout(tmp, "01_Cover", "P1")
            sidecar = tmp / "12_版式库" / "01_Cover.layouts.json"
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["content_capacity"]["desc"]["max_chars"] = 99  # 10×2×1.2=24
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            errors = self._run_lint(tmp)
            self.assertTrue(
                any("capacity_drift" in e for e in errors), errors,
            )

    def test_lint_layout_grid_checks_canonical_profile_capacity(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_canonical_profile(tmp, max_chars=99)
            errors = self._run_canonical_lint(tmp)
            self.assertTrue(any("capacity_drift" in e for e in errors), errors)

    def test_lint_layout_grid_rejects_missing_canonical_renderer(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_canonical_profile(tmp)
            profile = tmp / "canonical" / "layouts" / "test-layout" / "layout.json"
            data = json.loads(profile.read_text(encoding="utf-8"))
            data["renderer_support"]["render:html"] = "builtin:template:missing"
            profile.write_text(json.dumps(data), encoding="utf-8")
            errors = self._run_canonical_lint(tmp)
            self.assertTrue(any("canonical_renderer_missing" in e for e in errors), errors)

    def test_lint_layout_grid_rejects_notes_digest_drift(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_canonical_profile(tmp)
            profile = tmp / "canonical" / "layouts" / "test-layout" / "layout.json"
            data = json.loads(profile.read_text(encoding="utf-8"))
            data["name"] = "Tampered"
            profile.write_text(json.dumps(data), encoding="utf-8")
            errors = self._run_canonical_lint(tmp)
            self.assertTrue(any("canonical_layout_digest_mismatch" in e for e in errors), errors)

    def test_real_canonical_layout_notes_manifest_is_colocated_and_complete(self):
        root = SKILL_DIR / "template-library/canonical/layouts"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        profiles = {p.relative_to(root).as_posix() for p in root.glob("*/layout.json")}
        entries = {entry["profile"]: entry for entry in manifest["entries"]}
        self.assertEqual(manifest["entity"], "layout-profile-manifest")
        self.assertEqual(set(entries), profiles)
        for profile, entry in entries.items():
            self.assertEqual(Path(entry["notes"]).parent, Path(profile).parent)
            self.assertTrue((root / entry["notes"]).is_file())

    def test_lint_layout_grid_canonical_error_is_not_masked_by_retired_tree(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_canonical_profile(tmp, canvas=(1920, 1080))
            # A healthy retired sidecar is irrelevant: the active profile must
            # still fail its own canvas contract.
            self._make_layout(tmp, "01_Cover", "P1")
            errors = self._run_canonical_lint(tmp)
            self.assertTrue(any("画布必须为 1280" in e for e in errors), errors)

    def test_lint_layout_grid_requires_canonical_profiles(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_layout(tmp, "01_Cover", "P1")
            errors = self._run_canonical_lint(tmp)
            self.assertTrue(any("canonical_profile_missing" in e for e in errors), errors)

    def test_lint_layout_grid_errors_on_dangling_style_ref(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._make_layout(tmp, "01_Cover", "P1")
            (tmp / "测试风.md").write_text(
                "# 测试风\n```json\n{\"style_name\": \"测试风\"}\n```\n",
                encoding="utf-8",
            )
            (tmp / "测试风.layouts.json").write_text(json.dumps({
                "schema_version": 1, "entity": "style-layout-bank",
                "style_id": "测试风", "capacity_factor": {"text": 1.0},
                "routing": [{"page_type": "cover", "preferred": ["P88"],
                             "discouraged": []}],
            }), encoding="utf-8")
            errors = self._run_lint(tmp)
            self.assertTrue(
                any("dangling_layout_ref" in e for e in errors), errors,
            )

    def test_lint_style_briefs_errors_on_builtin_without_sidecar(self):
        # 直接跑真实脚本：临时移走一份内置 sidecar（测试内借还）。
        sidecar = (SKILL_DIR / Path("template-library/reference/sources/retired-styles-tree/styles")
                   / "教学课件风.layouts.json")
        backup = sidecar.read_bytes()
        sidecar.unlink()
        try:
            proc = subprocess.run(
                [sys.executable,
                 str(SKILL_DIR / "scripts" / "lint_style_briefs.py"),
                 "--legacy-fixtures"],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("style_sidecar_missing", proc.stdout)
        finally:
            sidecar.write_bytes(backup)

    def test_lint_layout_grid_baseline_exemptions_unchanged(self):
        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "lint_layout_grid.py"),
             "--legacy-sidecars"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        # 存量豁免条数不增（基线 3 条：10/12/20 号版式文件）。
        exemptions = [l for l in proc.stdout.splitlines()
                      if l.strip().startswith("~")]
        self.assertEqual(len(exemptions), 3)


if __name__ == "__main__":
    unittest.main()
