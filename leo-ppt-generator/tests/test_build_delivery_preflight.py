#!/usr/bin/env python3
"""build_delivery_preflight.py 单元测试（R-59 交付预检聚合）：单文件聚合
形态 / geometry 门 passed+failed / sources 门 passed+failed / sensitive 门
候选→warn 与零命中→passed / receipt 门 fresh→passed 与篡改→failed /
缺输入门如实 not_run 并入 WARN 清单 / blocked 语义 exit 1 / 用法错误 exit 2。"""
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_delivery_preflight.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8")


def make_png(w: int, h: int) -> bytes:
    """Minimal valid PNG (solid white), stdlib only."""
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def make_pptx(path: Path, canvas: tuple[int, int], disp: tuple[int, int],
              png_size: tuple[int, int]) -> None:
    """Minimal deck: one slide, one full-bleed picture (16:9 by default)."""
    cx, cy = canvas
    dw, dh = disp
    pic = (
        '<p:pic xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<p:nvPicPr><p:cNvPr id=\"1\" name=\"img\"/>"
        "<p:cNvPicPr/><p:nvPr/></p:nvPicPr>"
        "<p:blipFill><a:blip r:embed=\"rId1\"/></p:blipFill>"
        f"<p:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/>"
        f"<a:ext cx=\"{dw}\" cy=\"{dh}\"/></a:xfrm>"
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
    slide = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
             'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
             'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
             f"<p:cSld><p:spTree><p:nvGrpSpPr/>{pic}</p:spTree></p:cSld></p:sld>")
    presentation = ('<?xml version="1.0" encoding="UTF-8"?>'
                    '<p:presentation xmlns:p="http://schemas.openxmlformats.org/'
                    'presentationml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    f'<p:sldSz cx="{cx}" cy="{cy}"/>'
                    '<p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>'
                    "</p:presentation>")
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>'
            "</Relationships>")
    slide_rels = ('<?xml version="1.0" encoding="UTF-8"?>'
                  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                  '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                  'officeDocument/2006/relationships/image" Target="../media/image1.png"/>'
                  "</Relationships>")
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ppt/presentation.xml", presentation)
        z.writestr("ppt/_rels/presentation.xml.rels", rels)
        z.writestr("ppt/slides/slide1.xml", slide)
        z.writestr("ppt/slides/_rels/slide1.xml.rels", slide_rels)
        z.writestr("ppt/media/image1.png", make_png(*png_size))


def manifest(pages: list[dict]) -> str:
    payload = {
        "schema_version": 1,
        "manifest_kind": "visual-sources",
        "pages": pages,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    import hashlib
    payload["contents_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")).hexdigest()
    return json.dumps(payload, ensure_ascii=False)


GOOD_MASTER = """## S1 标题页
- 标题：智能客服年报
- 要点：无
- 视觉行：全幅图
"""


class DeliveryPreflightTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self._tmp.name) / "runs" / "imgdeck-v1"
        (self.run_dir / "input").mkdir(parents=True)
        (self.run_dir / "reports").mkdir(parents=True)
        (self.run_dir / "content").mkdir(parents=True)
        self.out = self.run_dir / "reports" / "delivery-preflight.json"

    def tearDown(self):
        self._tmp.cleanup()

    def seed(self, *, pptx_ok=True, master=GOOD_MASTER, pages=None):
        if pptx_ok is not None:
            make_pptx(self.run_dir / "deck.pptx",
                      canvas=(12192000, 6858000),
                      disp=(12192000, 6858000),
                      png_size=(2560, 1440))
        (self.run_dir / "input" / "sources-manifest.json").write_text(
            manifest(pages if pages is not None
                     else [{"page_id": "slide_1", "visuals": []}]),
            encoding="utf-8")
        (self.run_dir / "content" / "deck-master-v1.md").write_text(
            master, encoding="utf-8")

    def seed_receipt(self):
        sys.path.insert(0, str(Path(SCRIPT).parents[0].parent / "runtime" / "src"))
        try:
            from leo_ppt_generator.render.receipt import create_delivery_receipt
        except Exception:
            self.skipTest("runtime receipt module not importable")
        create_delivery_receipt(self.run_dir)

    def gates(self):
        return {g["gate"]: g for g in json.loads(
            self.out.read_text(encoding="utf-8"))["gates"]}

    def test_all_gates_pass_single_report(self):
        self.seed()
        self.seed_receipt()
        proc = run(str(self.run_dir))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(report["kind"], "delivery-preflight")
        self.assertEqual([g["gate"] for g in report["gates"]],
                         ["deck_geometry", "sources_manifest",
                          "sensitive_text", "delivery_receipt"])
        self.assertTrue(all(g["status"] == "passed" for g in report["gates"]))
        self.assertFalse(report["blocked"])
        self.assertEqual(report["not_run"], [])

    def test_geometry_failure_blocks_and_is_reported(self):
        self.seed(pptx_ok=None)
        make_pptx(self.run_dir / "deck.pptx",
                  canvas=(12192000, 6858000),  # 16:9 canvas
                  disp=(9144000, 6858000),     # 4:3 display: stretched
                  png_size=(2560, 1440))
        self.seed_receipt()
        proc = run(str(self.run_dir))
        self.assertEqual(proc.returncode, 1, "有门失败必须 exit 1")
        report = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(report["gates"][0]["status"], "failed")
        self.assertTrue(report["blocked"])

    def test_sources_failure_reported_as_failed(self):
        self.seed(pages=[{"page_id": "slide_1"}])  # visuals 缺失 → FAIL
        self.seed_receipt()
        proc = run(str(self.run_dir))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.gates()["sources_manifest"]["status"], "failed")

    def test_sensitive_candidates_warn_but_do_not_block(self):
        master = GOOD_MASTER + "\n联系我 13812345678 获取内部数据。\n"
        self.seed(master=master)
        self.seed_receipt()
        proc = run(str(self.run_dir))
        self.assertEqual(proc.returncode, 0, "候选是线索不是结论，不阻断")
        gate = self.gates()["sensitive_text"]
        self.assertEqual(gate["status"], "warn")
        self.assertGreaterEqual(gate["candidate_count"], 1)
        report = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertTrue(any("sensitive_text" in w for w in report["warnings"]))

    def test_receipt_tampering_fails_the_gate(self):
        self.seed()
        self.seed_receipt()
        # Tamper with a fingerprinted input after receipt creation.
        (self.run_dir / "input" / "sources-manifest.json").write_text(
            manifest([{"page_id": "slide_2", "visuals": []}]), encoding="utf-8")
        proc = run(str(self.run_dir))
        self.assertEqual(proc.returncode, 1)
        gate = self.gates()["delivery_receipt"]
        self.assertEqual(gate["status"], "failed")
        self.assertFalse(gate["fresh"])

    def test_missing_inputs_are_not_run_and_listed(self):
        proc = run(str(self.run_dir))  # nothing seeded at all
        self.assertEqual(proc.returncode, 0, "not_run 是披露不是失败")
        report = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(report["not_run"], ["deck_geometry", "sources_manifest",
                                             "sensitive_text", "delivery_receipt"])
        self.assertEqual(len(report["warnings"]), 4)
        self.assertFalse(report["blocked"])

    def test_explicit_master_and_pptx_args_override_probes(self):
        self.seed(pptx_ok=None)
        alt_master = self.run_dir / "m.md"
        alt_master.write_text(GOOD_MASTER, encoding="utf-8")
        alt_pptx = self.run_dir / "explicit.pptx"
        make_pptx(alt_pptx, canvas=(12192000, 6858000),
                  disp=(12192000, 6858000), png_size=(2560, 1440))
        self.seed_receipt()
        proc = run(str(self.run_dir), "--master", str(alt_master),
                   "--pptx", str(alt_pptx))
        self.assertEqual(proc.returncode, 0)
        # macOS tempdirs resolve through /private; compare resolved paths.
        self.assertEqual(Path(self.gates()["deck_geometry"]["target"]).resolve(),
                         alt_pptx.resolve())
        self.assertEqual(Path(self.gates()["sensitive_text"]["target"]).resolve(),
                         alt_master.resolve())

    def test_usage_error_exit_two(self):
        proc = run(str(self.run_dir.parent / "nope"))
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
