"""真实 PNG/OCR 的检测回归；测试观测不作为真实 Provider 或发布资格证据。"""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.qualification import ORACLE_PATH, digest
from leo_ppt_generator.raster_oracle import RasterOracleError, evaluate_raster_output, measure_raster
from leo_ppt_generator.render.page import RenderSession, render_page

ROOT = Path(__file__).resolve().parents[1]


class RasterOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = next(c for c in json.loads((ROOT / "evals/fixtures/expression-first-relation-probes.json").read_text())["cases"]
                        if c["relation"] == "comparison")
        cls.oracle = json.loads((ROOT / "template-library" / ORACLE_PATH).read_text())
        cls.images = {}
        resolver = AssetResolver(library=ROOT / "template-library")
        with tempfile.TemporaryDirectory() as temporary, RenderSession() as session:
            root = Path(temporary)
            for name in ("positive", "negative"):
                source = root / "data.json"
                source.write_text(json.dumps(cls.case[name], ensure_ascii=False))
                render_page("spec-table", source, root / "page.png", resolver=resolver, session=session)
                cls.images[name] = (root / "page.png").read_bytes()

    def review(self, name="positive"):
        import hashlib
        return {"schema_version": 1, "kind": "raster-geometry-observation",
                "artifact_sha256": hashlib.sha256(self.images[name]).hexdigest(),
                "expectation_digest": digest(self.case["expected"]), "oracle_digest": digest(self.oracle),
                "environment_sha256": "a" * 64, "reviewer": "controlled-test-observation",
                "method": "model", "observations": "受控模板测试的全画布观测；不是真实Provider视觉验收。",
                "complete": True, "edges": [], "blocks": [{"box": [0, 0, 1280, 720], "overflow": False}]}

    def evaluate(self, name="positive", review=None, expected=None):
        return evaluate_raster_output(expected or self.case["expected"], self.images[name], review or self.review(name),
            relation="comparison", oracle=self.oracle, environment_sha256="a" * 64)

    def test_real_ocr_reads_pixels_and_detects_the_misaligned_comparison(self):
        positive = self.evaluate()
        self.assertEqual(positive["measurement"]["source"], "apple-vision-revision-3")
        self.assertTrue(all(positive["checks"].values()), positive["checks"])
        negative = self.evaluate("negative")
        self.assertFalse(negative["checks"]["aligned_cells"], negative["checks"])

    def test_resealed_expected_text_cannot_change_ocr_output(self):
        expected = deepcopy(self.case["expected"])
        expected["required_text"].append("并未出现在图中的断言")
        review = self.review()
        review["expectation_digest"] = digest(expected)
        result = self.evaluate(review=review, expected=expected)
        self.assertFalse(result["checks"]["all_required_text"])
        self.assertEqual(result["measurement"], measure_raster(self.images["positive"]))

    def test_missing_stale_and_freeform_geometry_are_rejected(self):
        for key, value in (("artifact_sha256", "f" * 64), ("expectation_digest", "f" * 64),
                           ("environment_sha256", "f" * 64), ("complete", False),
                           ("blocks", []), ("reviewer", ""), ("css", "display:none")):
            with self.subTest(key=key):
                review = self.review()
                review[key] = value
                with self.assertRaises(RasterOracleError):
                    self.evaluate(review=review)

    def test_blank_image_is_not_qualified_and_html_measurement_cannot_replace_pixels(self):
        with self.assertRaisesRegex(RasterOracleError, "image_geometry_observation_required"):
            evaluate_raster_output(self.case["expected"], self.images["positive"], {"source": "browser-dom"},
                                  relation="comparison", oracle=self.oracle, environment_sha256="a" * 64)
        buffer = io.BytesIO()
        Image.new("RGB", (2560, 1440), "white").save(buffer, "PNG")
        self.assertEqual(measure_raster(buffer.getvalue())["texts"], [])


if __name__ == "__main__":
    unittest.main()
