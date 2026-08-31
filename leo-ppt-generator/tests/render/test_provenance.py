"""D1-T5 render provenance sidecar 的校验与 slide entry 并入（离线）。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from leo_ppt_generator.render.provenance import (
    attach_provenance_to_slide,
    load_render_receipt,
)
from leo_ppt_generator.render.errors import RenderError
from leo_ppt_generator.storage import sha256_file


def _make_receipt(artifact: Path, **overrides):
    receipt = {
        "schema_version": 1,
        "kind": "render_provenance",
        "backend": "render:html",
        "template_id": "body-basic",
        "template_sha256": "a" * 64,
        "data_sha256": "b" * 64,
        "dialect": None,
        "renderer": "playwright-chromium@test",
        "out": str(artifact),
        "out_sha256": sha256_file(artifact),
        "width": 2560,
        "height": 1440,
    }
    receipt.update(overrides)
    return receipt


def _make_deck(root: Path) -> Path:
    deck = root / "image-deck"
    (deck / "origin_image").mkdir(parents=True)
    artifact = deck / "origin_image" / "slide_01.png"
    artifact.write_bytes(b"fake-png-bytes-for-receipt-test")
    jobs = {
        "schema_version": 1,
        "revision": 1,
        "slides": [
            {
                "number": 1,
                "slide_id": "slide_01",
                "status": "recorded",
                "artifact": "origin_image/slide_01.png",
                "sha256": sha256_file(artifact),
                "backend": "render:html",
            }
        ],
    }
    (deck / "slide_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    return deck


class LoadRenderReceipt(unittest.TestCase):
    def test_valid_receipt_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "slide.png"
            artifact.write_bytes(b"png")
            path = Path(tmp) / "slide.png.render.json"
            path.write_text(json.dumps(_make_receipt(artifact)), encoding="utf-8")
            receipt = load_render_receipt(path)
            self.assertEqual(receipt["backend"], "render:html")

    def test_wrong_kind_and_backend_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "slide.png"
            artifact.write_bytes(b"png")
            for overrides in (
                {"kind": "something_else"},
                {"backend": "openai"},
                {"schema_version": 2},
            ):
                path = Path(tmp) / "r.json"
                path.write_text(json.dumps(_make_receipt(artifact, **overrides)), encoding="utf-8")
                with self.assertRaises(RenderError) as ctx:
                    load_render_receipt(path)
                self.assertEqual(ctx.exception.reason_code, "render_receipt_invalid")

    def test_unreadable_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RenderError) as ctx:
                load_render_receipt(Path(tmp) / "missing.json")
            self.assertEqual(ctx.exception.reason_code, "render_receipt_invalid")


class AttachProvenanceToSlide(unittest.TestCase):
    def test_attaches_sidecar_into_slide_entry_and_bumps_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = _make_deck(Path(tmp))
            artifact = deck / "origin_image" / "slide_01.png"
            summary = attach_provenance_to_slide(deck, 1, _make_receipt(artifact))
            self.assertEqual(summary["template_id"], "body-basic")
            jobs = json.loads((deck / "slide_jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(jobs["revision"], 2)
            provenance = jobs["slides"][0]["provenance"]
            self.assertEqual(provenance["backend"], "render:html")
            self.assertEqual(provenance["template_id"], "body-basic")
            self.assertEqual(provenance["data_sha256"], "b" * 64)

    def test_tampered_out_sha_rejected(self):
        # sidecar 不可手改：out_sha256 与落盘产物不一致 → 拒绝并入。
        with tempfile.TemporaryDirectory() as tmp:
            deck = _make_deck(Path(tmp))
            artifact = deck / "origin_image" / "slide_01.png"
            receipt = _make_receipt(artifact, out_sha256="0" * 64)
            with self.assertRaises(RenderError) as ctx:
                attach_provenance_to_slide(deck, 1, receipt)
            self.assertEqual(ctx.exception.reason_code, "render_receipt_invalid")
            jobs = json.loads((deck / "slide_jobs.json").read_text(encoding="utf-8"))
            self.assertNotIn("provenance", jobs["slides"][0])

    def test_backend_mismatch_between_receipt_and_record_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = _make_deck(Path(tmp))
            artifact = deck / "origin_image" / "slide_01.png"
            with self.assertRaises(RenderError) as ctx:
                attach_provenance_to_slide(deck, 1, _make_receipt(artifact), backend="fixture")
            self.assertEqual(ctx.exception.reason_code, "render_receipt_invalid")


if __name__ == "__main__":
    unittest.main()
