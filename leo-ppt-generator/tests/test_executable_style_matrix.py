"""首批准入的盘点前置：坏资产不从分母消失，旧 active 不冒充 executable。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import capability_manifest as cm


class InventoryAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "library.json").write_text('{"kind":"template-library"}')

    def style(self, slug, identity="builtin:style:sample", **fields):
        path = self.root / "canonical/styles" / slug / "brief.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"asset_id": identity, "name": "共同别名",
                                    "lifecycle": "active", **fields}))
        return path

    def test_active_without_combination_evidence_is_not_executable(self):
        self.style("a")
        report = cm.inventory_template_library(self.root)
        self.assertEqual(report["states"]["legacy"], 1)
        self.assertEqual(report["states"]["executable"], 0)
        self.assertFalse(report["migration_complete"])

    def test_invalid_manifest_and_duplicate_identity_remain_in_denominator(self):
        self.style("a")
        self.style("b")
        self.style("broken").write_text("{broken")
        report = cm.inventory_template_library(self.root)
        self.assertEqual(report["denominator"], {"raw_manifests": 3, "unique_identities": 1})
        self.assertEqual(report["states"]["unknown"], 1)
        self.assertEqual(len(report["duplicate_identities"]["builtin:style:sample"]), 2)

    def test_alias_conflicts_are_explicit_and_deterministic(self):
        self.style("a")
        self.style("b", "builtin:style:second")
        first = cm.inventory_template_library(self.root)
        self.assertEqual(len(first["alias_conflicts"]), 1)
        self.assertEqual(first, cm.inventory_template_library(self.root))

    def test_actual_html_bytes_change_inventory_digest(self):
        self.style("a")
        html = self.root / "canonical/page.html"
        html.write_text("before")
        before = cm.inventory_template_library(self.root)
        html.write_text("after")
        after = cm.inventory_template_library(self.root)
        self.assertNotEqual(before["source_digest"], after["source_digest"])

    def test_malformed_aliases_are_reported_not_crashed(self):
        self.style("a", aliases=42)
        self.assertEqual(cm.inventory_template_library(self.root)["gap_counts"]["invalid_aliases"], 1)

    def test_cli_inventory_writes_machine_readable_report(self):
        self.style("a")
        output = self.root / "inventory.json"
        import subprocess
        result = subprocess.run([sys.executable, str(Path(cm.__file__)),
                                 "--library-inventory", "--library-root", str(self.root),
                                 "--out", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text())["kind"], "template-library-inventory")
