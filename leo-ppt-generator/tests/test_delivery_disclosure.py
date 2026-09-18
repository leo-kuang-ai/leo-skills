"""U14/R-78+R-79+R-82 交付披露面行为测试。

覆盖计划场景：拼图页集合严格相等且图注存在、缺图/多图失败、旧 receipt
仍有效（加性 disclosure 块不进指纹类）、alt 缺失披露、讲稿超时不阻断、
不同预算来源与章节页时长保留。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.delivery_disclosure import (  # noqa: E402
    build_alt_manifest,
    build_diff_puzzles,
    disclosure_summary,
    speaker_duration_report,
)
from leo_ppt_generator.render.receipt import (  # noqa: E402
    create_delivery_receipt,
    verify_delivery_receipt,
)
from leo_ppt_generator.storage import sha256_file  # noqa: E402
from tests.expression_test_support import copy_real_html_run

EXPORT_SCRIPT = SKILL_DIR / "scripts" / "export_speaker_notes.py"
FINGERPRINT_CLASSES = {
    "page_artifacts", "local_assets", "qa_reports", "render_previews",
    "template_style_sources",
}


def _png(path: Path, color=(200, 200, 200), size=(320, 180)) -> Path:
    from PIL import Image

    Image.new("RGB", size, color).save(path, format="PNG")
    return path


class DiffPuzzleTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run = Path(self._tmp.name) / "run"
        self.run.mkdir(parents=True)
        self.old = _png(self.run / "old.png", (220, 220, 220))
        self.new = _png(self.run / "new.png", (60, 60, 90))

    def test_puzzle_page_set_equals_affected_and_captions_exist(self):
        index = build_diff_puzzles(
            run_root=self.run,
            pairs=[{"page_id": "S7", "number": 7, "old": self.old, "new": self.new}],
            affected_pages=["S7"],
            regime_version="page-type-regime-v2")
        self.assertEqual(sorted(p["page_id"] for p in index["pages"]), ["S7"])
        self.assertIn("regime=page-type-regime-v2", index["pages"][0]["caption"])
        self.assertIn("左=旧  右=新", index["pages"][0]["caption"])
        puzzle = self.run / "diffs" / "S7.png"
        self.assertTrue(puzzle.is_file())
        self.assertTrue((self.run / "diffs" / "index.json").is_file())

    def test_missing_image_rejected(self):
        with self.assertRaises(Exception) as ctx:
            build_diff_puzzles(
                run_root=self.run,
                pairs=[{"page_id": "S7", "number": 7, "old": self.old,
                        "new": self.run / "nope.png"}],
                affected_pages=["S7"])
        self.assertIn("diff_puzzle_image_missing", str(ctx.exception))

    def test_extra_page_beyond_affected_rejected(self):
        extra = _png(self.run / "extra-new.png")
        with self.assertRaises(Exception) as ctx:
            build_diff_puzzles(
                run_root=self.run,
                pairs=[{"page_id": "S7", "number": 7, "old": self.old, "new": self.new},
                       {"page_id": "S8", "number": 8, "old": self.old, "new": extra}],
                affected_pages=["S7"])
        self.assertIn("diff_puzzle_page_set_mismatch", str(ctx.exception))


class AltManifestTest(unittest.TestCase):
    def test_missing_alt_disclosed_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = _png(Path(tmp) / "page.png")
            manifest = build_alt_manifest(
                run_root=tmp,
                pages=[
                    {"page_id": "S1", "number": 1, "artifact": str(artifact),
                     "title": "封面", "claim": "增长质量", "alt": "增长质量封面页"},
                    {"page_id": "S2", "number": 2, "artifact": str(artifact),
                     "title": "财务", "claim": "营收 1.24 亿元", "alt": None},
                ])
            self.assertEqual(manifest["pages_total"], 2)
            self.assertEqual(manifest["pages_missing_alt"], 1)
            by_id = {page["page_id"]: page for page in manifest["pages"]}
            self.assertEqual(by_id["S1"]["status"], "ok")
            self.assertEqual(by_id["S2"]["status"], "missing")
            self.assertTrue((Path(tmp) / "disclosure/alt-manifest.json").is_file())

    def test_additive_artifacts_never_enter_fingerprint_classes(self):
        """R-79 负例：披露工件若落入既有指纹类即失败。"""

        with tempfile.TemporaryDirectory() as tmp:
            from leo_ppt_generator.render.receipt import collect_fingerprints

            build_alt_manifest(run_root=tmp, pages=[])
            (Path(tmp) / "diffs").mkdir()
            copy_real_html_run(Path(tmp))
            fingerprints = collect_fingerprints(Path(tmp))
            self.assertEqual(set(fingerprints), FINGERPRINT_CLASSES)
            for class_name, items in fingerprints.items():
                for relative in items:
                    self.assertFalse(
                        relative.startswith("diffs/") or "alt-manifest" in relative,
                        f"{class_name} 指纹不得覆盖披露工件：{relative}")


class ReceiptDisclosureTest(unittest.TestCase):
    """R-79/R-78：可选 disclosure 不参与表达收据的输入与产物摘要。"""

    def test_expression_receipt_without_optional_disclosure_still_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "final").mkdir(parents=True)
            _png(root / "final" / "deck.png")
            copy_real_html_run(root)
            result = create_delivery_receipt(root)
            receipt_path = Path(result["path"])
            # 剥离可选披露块，保留正式双层绑定与真实产物。
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt.pop("disclosure", None)
            receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
            outcome = verify_delivery_receipt(root)
            self.assertEqual(outcome["status"], "fresh")

    def test_new_receipt_carries_non_fingerprint_disclosure_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "final").mkdir(parents=True)
            _png(root / "final" / "deck.png")
            copy_real_html_run(root)
            result = create_delivery_receipt(root)
            self.assertIsNotNone(result["receipt"]["disclosure"])
            # disclosure 为 null/摘要块均不影响 verify。
            outcome = verify_delivery_receipt(root)
            self.assertEqual(outcome["status"], "fresh")

    def test_disclosure_summary_reports_counts_when_artifacts_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_alt_manifest(run_root=tmp, pages=[
                {"page_id": "S1", "number": 1, "title": "t", "claim": "c", "alt": "替代文本"}])
            summary = disclosure_summary(tmp)
            self.assertEqual(summary["alt_manifest"]["pages_total"], 1)
            self.assertIsNone(summary["diff_puzzles"], "缺 diff 工件如实 null")


class SpeakerDurationTest(unittest.TestCase):
    def test_over_budget_reported_advisory(self):
        report = speaker_duration_report(
            pages=[{"page_id": "S1", "chars": 600, "budget_seconds": 60},
                   {"page_id": "S2", "chars": 100, "budget_seconds": 60}])
        by_id = {row["page_id"]: row for row in report["pages"]}
        self.assertEqual(by_id["S1"]["status"], "over")   # 600 字 @240字/分 = 150s
        self.assertEqual(by_id["S2"]["status"], "ok")
        self.assertTrue(report["advisory"])

    def test_page_budget_preferred_then_deck_share_then_unknown(self):
        report = speaker_duration_report(
            pages=[{"page_id": "S1", "chars": 100, "budget_seconds": 30},
                   {"page_id": "S2", "chars": 100},
                   {"page_id": "S3", "chars": 100}],
            deck_duration_seconds=90)
        by_id = {row["page_id"]: row for row in report["pages"]}
        self.assertEqual(by_id["S1"]["budget_source"], "page-budget")
        self.assertEqual(by_id["S1"]["budget_seconds"], 30)
        self.assertEqual(by_id["S2"]["budget_source"], "deck-share")
        self.assertAlmostEqual(by_id["S2"]["budget_seconds"], 30.0)
        self.assertEqual(by_id["S3"]["budget_source"], "deck-share")

    def test_double_missing_budget_is_unknown(self):
        report = speaker_duration_report(pages=[{"page_id": "S1", "chars": 100}])
        self.assertEqual(report["pages"][0]["status"], "unknown")
        self.assertEqual(report["pages_unknown_budget"], 1)

    def test_section_page_budgets_preserved_individually(self):
        """不同预算的章节页各自保留，不被整册均分抹平。"""

        report = speaker_duration_report(pages=[
            {"page_id": "S1", "chars": 100, "budget_seconds": 15},
            {"page_id": "S2", "chars": 100, "budget_seconds": 120},
            {"page_id": "S3", "chars": 100, "budget_seconds": 45},
        ])
        budgets = [row["budget_seconds"] for row in report["pages"]]
        self.assertEqual(budgets, [15, 120, 45])


class ExportDurationCliTest(unittest.TestCase):
    def test_duration_check_warns_but_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            master = Path(tmp) / "deck-master-v1.md"
            master.write_text(
                "# 母版 v1\nconfirmation: confirmed\n\n"
                "## P1 封面\npage_id: pg-aaaaaaaa\n- speaker_script：短讲稿\n\n"
                "## P2 财务\npage_id: pg-bbbbbbbb\n- speaker_script："
                + "很长的一页讲稿" * 60 + "\n",
                encoding="utf-8")
            pack = Path(tmp) / "page-content-pack.json"
            pack.write_text(json.dumps({
                "deck": {"duration_seconds": 30},
                "pages": [
                    {"page_id": "pg-aaaaaaaa", "number": 1, "budget_seconds": 5},
                    {"page_id": "pg-bbbbbbbb", "number": 2, "budget_seconds": 5},
                ],
            }, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(EXPORT_SCRIPT), "--master", str(master),
                 "--duration-check", str(pack)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("DURATION-WARN", result.stderr)
            self.assertIn("pg-bbbbbbbb", result.stderr)
            self.assertIn("讲稿", result.stdout)


if __name__ == "__main__":
    unittest.main()


class ConsoleDiffServingTest(unittest.TestCase):
    """R-78 验收 2：控制台按 §7 路径规则 serve `<run>/diffs/`。"""

    RUN_ID = "d1ff0001aaaa4bbb8ccc0ddd00000000"

    def _scanner_with_run(self, home: Path):
        sys.path.insert(0, str(SKILL_DIR / "tests"))
        from runs_fixture import make_run

        from leo_ppt_generator.runs_console import RunScanner

        run = make_run(home, project="p", run_id=self.RUN_ID)
        (run / "diffs").mkdir(parents=True, exist_ok=True)
        return RunScanner(home), run

    def test_serves_puzzle_inside_diffs_namespace(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            scanner, run = self._scanner_with_run(Path(name))
            _png(run / "diffs" / "S7.png", (90, 90, 140))
            payload, content_type = scanner.diff_puzzle(self.RUN_ID, "S7")
            self.assertEqual(content_type, "image/png")
            self.assertTrue(payload)

    def test_path_traversal_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            scanner, run = self._scanner_with_run(Path(name))
            _png(run.parent / "escape.png")
            from leo_ppt_generator.runs_console import PreviewLookupError

            with self.assertRaises(PreviewLookupError):
                scanner.diff_puzzle(self.RUN_ID, "../escape.png")
