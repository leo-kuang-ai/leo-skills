"""独立输出判断的真实浏览器验证；不作为 Provider、视觉或发布证据。"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.qualification import ORACLE_PATH
from leo_ppt_generator.relation_oracle import OracleError, evaluate_output, validate_expectation
from leo_ppt_generator.render.page import RenderSession, render_page

ROOT = Path(__file__).resolve().parents[1]


class RelationOracleTests(unittest.TestCase):
    def test_cover_title_glyphs_fit_their_block_without_relaxing_overflow_oracle(self):
        resolver = AssetResolver(library=ROOT / "template-library")
        with tempfile.TemporaryDirectory() as temporary, RenderSession() as session:
            root = Path(temporary)
            for title in ("封面结论", "用表达优先重构解决页面关系"):
                with self.subTest(title=title):
                    source = root / "data.json"
                    source.write_text(json.dumps({"title": title, "subtitle": "工作独立推进"}, ensure_ascii=False))
                    render_page("cover-basic", source, root / "page.png", resolver=resolver,
                                session=session, observation_path=root / "measurement.json")
                    measured = json.loads((root / "measurement.json").read_text())
                    self.assertFalse(any(b["overflow"] for b in measured["blocks"]), measured["blocks"])
                    title_text = next(t for t in measured["texts"] if t["text"] == title)
                    block = measured["blocks"][0]["box"]
                    x, y, width, height = title_text["box"]
                    self.assertGreaterEqual(y, block[1] - 1)
                    self.assertLessEqual(y + height, block[1] + block[3] + 1)

    def test_unknown_fields_and_incomplete_grid_are_rejected(self):
        cases = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())["cases"]
        expected = deepcopy(cases[1]["expected"])
        expected["structure"]["cells"].pop()
        with self.assertRaisesRegex(OracleError, "oracle_expectation_invalid"):
            validate_expectation(expected, "comparison")
        expected = deepcopy(cases[0]["expected"])
        expected["checks"] = {"all_passed": True}
        with self.assertRaises(OracleError):
            validate_expectation(expected, "independent")

    def test_real_reverse_arrows_cannot_add_an_undeclared_dependency(self):
        cases = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())["cases"]
        oracle = json.loads((ROOT / "template-library" / ORACLE_PATH).read_text())
        resolver = AssetResolver(library=ROOT / "template-library")
        with tempfile.TemporaryDirectory() as temporary, RenderSession() as session:
            root = Path(temporary)
            for case in (c for c in cases if c["relation"] in {"process", "causal"}):
                with self.subTest(relation=case["relation"]):
                    data = deepcopy(case["positive"])
                    data["chart_svg"] = data["chart_svg"].replace('marker-end="url(#arrow)"',
                        'marker-start="url(#arrow)" marker-end="url(#arrow)"')
                    (root / "data.json").write_text(json.dumps(data, ensure_ascii=False))
                    render_page("body-basic", root / "data.json", root / "page.png", resolver=resolver,
                                session=session, observation_path=root / "measurement.json")
                    measured = json.loads((root / "measurement.json").read_text())
                    self.assertTrue(any(edge["reverse"] for edge in measured["edges"]))
                    checks = evaluate_output(case["expected"], measured, relation=case["relation"], oracle=oracle)
                    key = "dependency_edges" if case["relation"] == "process" else "directed_edges"
                    self.assertFalse(checks[key], checks)

    def test_real_rendered_positive_and_semantically_wrong_negative_for_every_relation(self):
        # 本测试有意不 skip：浏览器不可运行时，必要的真实输出验证不能算通过。
        cases = json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())["cases"]
        oracle = json.loads((ROOT / "template-library" / ORACLE_PATH).read_text())
        resolver = AssetResolver(library=ROOT / "template-library")
        with tempfile.TemporaryDirectory() as temporary, RenderSession() as session:
            root = Path(temporary)
            for case in cases:
                template = resolver.resolve(case["layout_id"])["data"]["renderer_support"]["render:html"]
                for name in ("positive", "negative"):
                    with self.subTest(relation=case["relation"], probe=name):
                        source, out, observation = root / "data.json", root / "page.png", root / "measurement.json"
                        source.write_text(json.dumps(case[name], ensure_ascii=False))
                        result = render_page(template, source, out, resolver=resolver, session=session, observation_path=observation)
                        measured = json.loads(observation.read_text())
                        self.assertEqual(result["out_sha256"], measured["artifact_sha256"])
                        self.assertEqual((result["width"], result["height"]), (2560, 1440))
                        checks = evaluate_output(case["expected"], measured, relation=case["relation"], oracle=oracle)
                        if name == "positive":
                            self.assertTrue(all(checks.values()), checks)
                            if case["relation"] == "trend":
                                # 删除数字单元格，标题/日期中的 2026 不能冒充 value=6。
                                altered = deepcopy(measured)
                                altered["texts"] = [t for t in altered["texts"] if t["text"] != "6"]
                                self.assertFalse(evaluate_output(case["expected"], altered, relation="trend", oracle=oracle)["numeric_values"])
                        else:
                            self.assertFalse(checks[oracle["relations"][case["relation"]]["negative_check"]], checks)


if __name__ == "__main__":
    unittest.main()
