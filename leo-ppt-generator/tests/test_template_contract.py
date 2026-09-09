"""canonical 模板目录级合同回归。"""
from __future__ import annotations
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import lint_template_contract as contract  # noqa: E402


class TemplateContractTest(unittest.TestCase):
    def setUp(self):
        self.layouts = {}
        for p in (SKILL / "template-library/canonical/layouts").glob("*/layout.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            self.layouts[data["asset_id"]] = data

    def test_canonical_templates_pass(self):
        root = SKILL / "template-library/canonical/templates"
        errors = []
        for path in sorted(root.iterdir()):
            if path.is_dir():
                errors.extend(contract.lint_one(path, self.layouts))
        self.assertEqual(errors, [])

    def test_missing_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "new-template"
            path.mkdir()
            shutil.copy(SKILL / "template-library/canonical/templates/body-basic/page.html", path / "page.html")
            self.assertTrue(any("missing template.json" in e for e in contract.lint_one(path, self.layouts)))

    def test_selector_drift_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "body-basic"
            shutil.copytree(SKILL / "template-library/canonical/templates/body-basic", path)
            manifest = json.loads((path / "template.json").read_text())
            manifest["slot_bindings"][0]["selector"] = "[data-leo-block='missing']"
            (path / "template.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertTrue(any("missing DOM anchor" in e for e in contract.lint_one(path, self.layouts)))


if __name__ == "__main__":
    unittest.main()
