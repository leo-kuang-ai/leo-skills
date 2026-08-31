"""layout-bank sidecar 层（B1）的合同测试：加载器 fail-fast、五字段封顶、
风格路由视图悬空引用拒绝、style list 不混入 sidecar、lint 配对检查 A/B/C。

设计对照 docs/plans/fusion-team-designs/团队β-风格版式资产层.md §3.1/§5。
"""

from __future__ import annotations

import json
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

SEMANTIC_FIELDS = {
    "visual_signature", "content_capacity", "best_for", "avoid_for",
    "reuse_friendly",
}


class LoadLayoutBankTests(unittest.TestCase):
    def test_load_layout_bank_returns_five_capped_fields(self):
        data = layout_bank.load_layout_bank("P6")
        # 治理字段（标识类）+ 恰好五个语义字段封顶，无第六语义字段。
        self.assertEqual(data["layout_id"], "P6")
        self.assertEqual(data["name"], "KPI Tower")
        self.assertIn(data["page_type"], (
            "cover", "agenda", "section", "content", "data", "closing",
        ))
        self.assertEqual(
            set(data) & {"visual_signature", "content_capacity", "best_for",
                         "avoid_for", "reuse_friendly", "variation_tags",
                         "json_schema", "external_image_slots", "reuse_reason",
                         "summary"},
            SEMANTIC_FIELDS,
        )
        self.assertIsInstance(data["content_capacity"]["items"]["count_min"], int)

    def test_load_layout_bank_fails_fast_on_missing_sidecar(self):
        with self.assertRaises(styles.StyleStoreError) as ctx:
            layout_bank.load_layout_bank("P99")
        self.assertIn("layout_bank_not_found", str(ctx.exception))

    def test_list_layout_bank_covers_thirty_six_with_fingerprints(self):
        items = layout_bank.list_layout_bank()
        self.assertEqual(len(items), 36)
        ids = [item["layout_id"] for item in items]
        self.assertEqual(ids, sorted(ids))  # 确定性排序
        self.assertEqual(
            {item["layout_id"] for item in items
             if item["reuse_friendly"] is False},
            {"P1", "P9", "P23", "P24", "P34", "P36"},
        )
        for item in items:
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
        # P36 每 deck ≤2，其余强视觉版式上限 1。
        by_id = {item["layout_id"]: item for item in items}
        self.assertEqual(by_id["P36"]["max_per_deck"], 2)
        self.assertEqual(by_id["P9"]["max_per_deck"], 1)


class LoadStyleLayoutsTests(unittest.TestCase):
    def test_style_layouts_query_includes_sha256(self):
        data = layout_bank.load_style_layouts("手绘白板风")
        self.assertEqual(data["style_id"], "手绘白板风")
        self.assertEqual(data["capacity_factor"]["text"], 0.85)
        self.assertRegex(data["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(data["routing"])

    def test_style_layouts_missing_sidecar_fails_fast(self):
        with self.assertRaises(styles.StyleStoreError) as ctx:
            layout_bank.load_style_layouts("不存在的风格")
        self.assertIn("layout_bank_not_found", str(ctx.exception))

    def test_style_layouts_dangling_reference_rejected(self):
        # LEO_PPT_BUNDLE 指向临时 bundle：路由引用 P99（不存在）→ 加载边界拒绝。
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td)
            styles_dir = bundle / "references" / "styles"
            layout_dir = styles_dir / "12_版式库"
            layout_dir.mkdir(parents=True)
            (layout_dir / "01_Cover.layouts.json").write_text(json.dumps({
                "schema_version": 1, "entity": "layout", "layout_id": "P1",
                "name": "Cover", "page_type": "cover",
                "visual_signature": "test",
                "content_capacity": {"title": {
                    "desc": "t", "chars_per_line": 7, "max_lines": 1,
                    "max_chars": 8,
                }},
                "best_for": ["x"], "avoid_for": ["y"], "reuse_friendly": False,
            }), encoding="utf-8")
            (styles_dir / "测试风.layouts.json").write_text(json.dumps({
                "schema_version": 1, "entity": "style-layout-bank",
                "style_id": "测试风",
                "capacity_factor": {"text": 1.0},
                "routing": [{"page_type": "cover", "preferred": ["P99"],
                             "discouraged": []}],
            }), encoding="utf-8")
            with mock.patch.dict("os.environ",
                                 {"LEO_PPT_BUNDLE": str(bundle)}):
                with self.assertRaises(styles.StyleStoreError) as ctx:
                    layout_bank.load_style_layouts("测试风")
        self.assertIn("悬空版式引用", str(ctx.exception))


class StyleListIsolationTests(unittest.TestCase):
    def test_style_list_ignores_layout_sidecars(self):
        # 47 份 .layouts.json 不得混入 style list（守护 _is_style_md 只认 .md
        # 的语义）：可加载数量仍为 137，且无任何名字来自 sidecar 文件。
        entries = styles.list_styles()
        self.assertEqual(len(entries), 137)
        names = {e["name"] for e in entries}
        sidecar_stems = {
            p.name[: -len(".layouts.json")] for p in
            (SKILL_DIR / "references" / "styles").glob("*.layouts.json")
        }
        # sidecar 与内置风格同名是刻意设计（薄路由视图，成对存在）：
        self.assertTrue({"清爽专业风", "科研答辩风"} <= sidecar_stems <= names)
        # 关键守卫：.layouts.json 后缀本身永不出现，sidecar 不新增可加载项。
        self.assertFalse(any(n.endswith(".layouts") for n in names))
        self.assertEqual(len(sidecar_stems), 11)


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
        sidecar = (SKILL_DIR / "references" / "styles"
                   / "教学课件风.layouts.json")
        backup = sidecar.read_bytes()
        sidecar.unlink()
        try:
            proc = subprocess.run(
                [sys.executable,
                 str(SKILL_DIR / "scripts" / "lint_style_briefs.py")],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("style_sidecar_missing", proc.stdout)
        finally:
            sidecar.write_bytes(backup)

    def test_lint_layout_grid_baseline_exemptions_unchanged(self):
        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "lint_layout_grid.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        # 存量豁免条数不增（基线 3 条：10/12/20 号版式文件）。
        exemptions = [l for l in proc.stdout.splitlines()
                      if l.strip().startswith("~")]
        self.assertEqual(len(exemptions), 3)


if __name__ == "__main__":
    unittest.main()
