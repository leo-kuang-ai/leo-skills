"""内容意图 → 页型 regime → 版式候选的正负回归。

unittest.TestCase 形态（仓库运行器为 ``python -m unittest discover -s tests``
——裸 ``def test_`` 不会被收集；本文件的回归此前因此从未入账）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "src"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from leo_ppt_generator.page_intent import analyze_page_intent, load_page_type_regime  # noqa: E402
from leo_ppt_generator.asset_resolver import AssetResolver  # noqa: E402

# suggest_layout 链路经 template_inputs 依赖 jsonschema（runtime/pyproject.toml 声明）。
# 裸解释器缺该依赖时显式跳过——沿 test_content_pack.py 的同款处置。
try:  # noqa: SIM105
    import jsonschema  # noqa: F401
except ImportError:
    jsonschema = None

NEEDS_JSONSCHEMA = unittest.skipIf(jsonschema is None, "jsonschema 未安装")


def _suggest(page: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "suggest_layout.py")],
        input=json.dumps({"backend": "render:html", "pages": [page]}, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["pages"][0]


class PageIntentRoutingTest(unittest.TestCase):
    def test_regime_has_versioned_semantic_contract(self) -> None:
        regime = load_page_type_regime()
        self.assertEqual(regime["regime_id"], "page-type-regime-v2")
        self.assertLessEqual(
            {"comparison", "trend", "process", "kpi", "evidence"}, set(regime["page_types"])
        )
        for page_type, spec in regime["page_types"].items():
            with self.subTest(page_type=page_type):
                self.assertTrue(spec["preferred_layouts"])
                self.assertTrue(spec["allowed_lanes"])
                self.assertTrue(spec["required_slots"])

    def test_regime_layout_references_are_real_catalog_assets(self) -> None:
        aliases = set()
        for entity in AssetResolver().entities:
            if entity.get("kind") != "layout":
                continue
            aliases.add(entity["asset_id"])
            aliases.update(entity.get("aliases") or [])
        for page_type, spec in load_page_type_regime()["page_types"].items():
            for layout in [*spec["preferred_layouts"], *spec["fallback_layouts"]]:
                with self.subTest(page_type=page_type, layout=layout):
                    self.assertIn(layout, aliases)

    def test_regime_lint_reports_no_errors(self) -> None:
        """The regime truth source must pass its own lint (governance clause 2)."""
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "lint_page_type_regime.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("0 ERROR", proc.stdout)

    def test_regime_lint_rejects_injected_defects(self) -> None:
        """Red cases: a dangling layout reference and an unknown lane must fail lint."""
        import copy
        import pathlib
        import tempfile

        base = load_page_type_regime()
        cases = {
            "dangling_layout": lambda regime: regime["page_types"]["cover"].__setitem__(
                "preferred_layouts", ["P999-not-real"]
            ),
            "unknown_lane": lambda regime: regime["page_types"]["cover"].__setitem__(
                "allowed_lanes", ["render:svg"]
            ),
            "preferred_fallback_overlap": lambda regime: regime["page_types"][
                "cover"
            ].__setitem__("fallback_layouts", ["P1"]),
        }
        for name, mutate in cases.items():
            regime = copy.deepcopy(base)
            mutate(regime)
            handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
            try:
                with handle:
                    json.dump(regime, handle, ensure_ascii=False)
                    handle.flush()  # 子进程按路径读取，须先落盘
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "lint_page_type_regime.py"),
                        "--regime",
                        handle.name,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                pathlib.Path(handle.name).unlink(missing_ok=True)
            self.assertEqual(proc.returncode, 1, f"{name}: lint did not fail")
            self.assertIn("ERROR", proc.stdout)

    def test_explicit_structure_wins_over_ambiguous_title(self) -> None:
        result = analyze_page_intent({
            "page_role": "陈述·金句",
            "title": "为什么现在必须改变",
            "structures": {"sides": [{"label": "A"}, {"label": "B"}]},
            "points": 2,
        })
        self.assertEqual(result["page_type"], "comparison")
        self.assertEqual(result["inference"]["source"], "structure")
        self.assertEqual(result["decision"], "auto")

    def test_plain_bullets_do_not_become_kpi(self) -> None:
        result = analyze_page_intent({
            "page_role": "目标·学习目标",
            "title": "本章学习目标",
            "points": 4,
            "est_chars": 180,
        })
        self.assertEqual(result["page_type"], "text_list")
        self.assertEqual(result["evidence_type"], "none")
        self.assertNotEqual(result["page_type"], "kpi")

    @NEEDS_JSONSCHEMA
    def test_semantic_candidates_prefer_comparison_layout(self) -> None:
        result = _suggest({
            "page": 2,
            "page_role": "对比·多维",
            "title": "两种方案的交付差异",
            "points": 2,
            "est_chars": 80,
            "structures": {"sides": [{"label": "甲"}, {"label": "乙"}]},
        })
        self.assertEqual(result["intent"]["page_type"], "comparison")
        self.assertIn(result["candidates"][0]["layout"], {"P8", "compare"})
        self.assertTrue(
            any("内容意图首选" in reason for reason in result["candidates"][0]["reasons"])
        )

    @NEEDS_JSONSCHEMA
    def test_unknown_semantics_keep_human_decision(self) -> None:
        result = _suggest({
            "page": 4,
            "page_role": "未知章节角色",
            "title": "一些信息",
            "points": 2,
            "est_chars": 50,
        })
        self.assertEqual(result["intent"]["decision"], "undecided")
        self.assertEqual(result["decision"], "undecided")

    @NEEDS_JSONSCHEMA
    def test_table_is_not_routed_to_image_only_lane(self) -> None:
        result = _suggest({
            "page": 5,
            "page_role": "参考·文献",
            "title": "字段明细表",
            "points": 2,
            "est_chars": 120,
            "structures": {"table": {"columns": ["字段", "口径"], "rows": [["A", "B"]]}},
        })
        self.assertEqual(result["intent"]["page_type"], "table")
        self.assertIn(result["candidates"][0]["layout"], {"P25", "P21"})
        for candidate in result["candidates"]:
            self.assertIn("render:html", candidate["renderer_support"])

    @NEEDS_JSONSCHEMA
    def test_style_layout_routes_are_scoped_to_page_role(self) -> None:
        # 同一风格的 cover/section 路由不能泄漏到 data 页；这是 style 与页面意图
        # 断层最容易产生的静默错配。
        import suggest_layout

        _, cover = suggest_layout.load_style_routing("电子墨水杂志风", page_types={"cover"})
        _, data = suggest_layout.load_style_routing("电子墨水杂志风", page_types={"data"})
        self.assertNotEqual(cover, data)
        self.assertEqual(cover.get("P1"), 0.1)
        self.assertNotIn("P1", data)


if __name__ == "__main__":
    unittest.main()

class PageIntentRegimeV2ContractTest(unittest.TestCase):
    def test_relation_minimum_encoding_is_declared(self) -> None:
        regime = load_page_type_regime()
        for page_type in ("comparison", "trend", "process", "system", "statement"):
            spec = regime["page_types"][page_type]
            self.assertIsInstance(spec.get("relation_kind"), str)
            self.assertTrue(spec.get("minimum_encoding"))
