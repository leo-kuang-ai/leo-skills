#!/usr/bin/env python3
"""overlay_text.py 行为测试：白名单逐字 / 2560×1440 / 非 16:9 拒绝 /
非白名单拒绝渲染 / 位级确定性；X-4：TF-2 fallback 页底图+终图双指纹与
sources manifest deterministic-overlay 标记联动（供 γ 收据消费）。"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "overlay_text.py"
CHECK_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_sources_manifest.py"


def make_base(path: Path, width=2560, height=1440, color=(240, 240, 236)):
    from PIL import Image

    Image.new("RGB", (width, height), color).save(path, format="PNG")
    return path


def run(args):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )
    return result.returncode, result.stdout + result.stderr


def summary_of(stdout: str) -> dict:
    return json.loads(stdout.strip().splitlines()[-1])


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class OverlayTextTest(unittest.TestCase):
    def test_overlay_renders_whitelist_verbatim(self):
        """逐字保证：白名单文字逐项出现在渲染计划里，改字即改产物（可 diff）。"""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = make_base(root / "base.png")
            whitelist_a = root / "wl.json"
            whitelist_a.write_text(json.dumps(["标题甲", "要点一"], ensure_ascii=False), encoding="utf-8")
            out_a = root / "out_a.png"
            code, out = run([str(base), str(whitelist_a), str(out_a)])
            self.assertEqual(code, 0, out)
            summary = summary_of(out)
            self.assertEqual(summary["rendered"], ["标题甲", "要点一"])
            self.assertTrue(summary["deterministic-overlay"])

            whitelist_b = root / "wl_b.json"
            whitelist_b.write_text(json.dumps(["标题乙", "要点一"], ensure_ascii=False), encoding="utf-8")
            out_b = root / "out_b.png"
            code, out = run([str(base), str(whitelist_b), str(out_b)])
            self.assertEqual(code, 0, out)
            self.assertNotEqual(summary_of(out)["output_sha256"], summary["output_sha256"])

    def test_overlay_output_keeps_2560x1440(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = make_base(root / "base.png", width=1280, height=720)  # 同比例不同尺寸
            whitelist = root / "wl.json"
            whitelist.write_text(json.dumps(["标题"], ensure_ascii=False), encoding="utf-8")
            out = root / "out.png"
            code, output = run([str(base), str(whitelist), str(out)])
            self.assertEqual(code, 0, output)
            with Image.open(out) as image:
                self.assertEqual(image.size, (2560, 1440))
            self.assertEqual(summary_of(output)["width"], 2560)

    def test_overlay_rejects_non_16_9_base(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = make_base(root / "base.png", width=1536, height=1024)  # 3:2
            whitelist = root / "wl.json"
            whitelist.write_text(json.dumps(["标题"], ensure_ascii=False), encoding="utf-8")
            out = root / "out.png"
            code, output = run([str(base), str(whitelist), str(out)])
            self.assertEqual(code, 1)
            self.assertIn("16:9", output)
            self.assertFalse(out.exists())

    def test_overlay_rejects_non_whitelist_anchor_text(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = make_base(root / "base.png")
            whitelist = root / "wl.json"
            whitelist.write_text(
                json.dumps(
                    {
                        "required_text": ["标题甲"],
                        "anchors": [
                            {"text": "白名单外的文字", "x": 100, "y": 200},
                            {"text": "标题甲", "x": 100, "y": 400},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out = root / "out.png"
            code, output = run([str(base), str(whitelist), str(out)])
            self.assertEqual(code, 1)
            self.assertIn("白名单外", output)
            self.assertFalse(out.exists())

    def test_overlay_rejects_incomplete_whitelist_coverage(self):
        """白名单条目缺锚点 → 拒绝不完整渲染（漏字正是 TF 要修的问题）。"""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = make_base(root / "base.png")
            whitelist = root / "wl.json"
            whitelist.write_text(
                json.dumps(
                    {
                        "required_text": ["标题甲", "要点一"],
                        "anchors": [{"text": "标题甲", "x": 100, "y": 200}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out = root / "out.png"
            code, output = run([str(base), str(whitelist), str(out)])
            self.assertEqual(code, 1)
            self.assertIn("缺少锚点", output)

    def test_overlay_deterministic_byte_identical(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = make_base(root / "base.png")
            whitelist = root / "wl.json"
            whitelist.write_text(
                json.dumps(["标题甲", "要点一", "标签 1"], ensure_ascii=False),
                encoding="utf-8",
            )
            first = root / "first.png"
            second = root / "second.png"
            code, out1 = run([str(base), str(whitelist), str(first)])
            self.assertEqual(code, 0, out1)
            code, out2 = run([str(base), str(whitelist), str(second)])
            self.assertEqual(code, 0, out2)
            self.assertEqual(first.read_bytes(), second.read_bytes(), "同输入必须位级一致")

    def test_overlay_anchored_mode_places_text(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = make_base(root / "base.png", color=(250, 250, 250))
            whitelist = root / "wl.json"
            whitelist.write_text(
                json.dumps(
                    {
                        "required_text": ["标题甲", "要点一"],
                        "anchors": [
                            {"text": "标题甲", "x": 200, "y": 300, "size": 120},
                            {"text": "要点一", "x": 200, "y": 600, "size": 72},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out = root / "out.png"
            code, output = run([str(base), str(whitelist), str(out)])
            self.assertEqual(code, 0, output)
            # 锚点位置确实写入了像素（该行不再是纯底色）。
            with Image.open(out) as image:
                pixels = image.convert("RGB").load()
            row = {pixels[x, 330] for x in range(200, 800, 8)}
            self.assertTrue(any(pixel != (250, 250, 250) for pixel in row))


class TF2FallbackRecordTest(unittest.TestCase):
    """X-4 交叉测试：overlay 后 sources manifest 的 deterministic-overlay 标记
    与产物"底图 + 终图"双记字段（γ 五指纹收据联动契约）。"""

    def test_dual_fingerprint_and_deterministic_overlay_marker(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = make_base(root / "base.png")
            whitelist = root / "wl.json"
            whitelist.write_text(
                json.dumps(
                    {
                        "required_text": ["标题甲", "要点一"],
                        "anchors": [
                            {"text": "标题甲", "x": 200, "y": 300},
                            {"text": "要点一", "x": 200, "y": 620},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            final = root / "final.png"
            code, out = run([str(base), str(whitelist), str(final)])
            self.assertEqual(code, 0, out)
            summary = summary_of(out)

            # 双指纹：底图与终图分别可指认，且贴字层确实改变了产物。
            self.assertNotEqual(summary["base_sha256"], summary["output_sha256"])
            self.assertEqual(summary["base_sha256"], hashlib.sha256(base.read_bytes()).hexdigest())
            self.assertEqual(summary["output_sha256"], hashlib.sha256(final.read_bytes()).hexdigest())

            # sources manifest 该页登记 deterministic-overlay（source_class 封闭枚举内）。
            manifest = {
                "schema_version": 1,
                "manifest_kind": "visual-sources",
                "route": "generate",
                "run_ref": "runs/r1",
                "generated_from": "content/deck-master-v1.md",
                "pages": [
                    {
                        "page_id": "slide_01",
                        "visuals": [
                            {
                                "visual_id": "text-overlay",
                                "figure_id": None,
                                "kind": "text-overlay",
                                "source_class": "deterministic-overlay",
                                "tier": "示意",
                                "handling_mode": None,
                                "review_status": None,
                                "source_ref": "origin_image/slide_01.png",
                                "source_sha256": summary["base_sha256"],
                                "backend": "overlay_text.py",
                            }
                        ],
                    }
                ],
            }
            payload = {k: v for k, v in manifest.items() if k != "contents_sha256"}
            manifest["contents_sha256"] = hashlib.sha256(
                canonical_json(payload).encode()
            ).hexdigest()
            run_dir = root / "run"
            (run_dir / "input").mkdir(parents=True)
            (run_dir / "input" / "sources-manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), str(run_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            # γ 收据联动字段：TF-2 页按"底图 + 终图"双记（模拟收据行）。
            receipt = {
                "page_id": "slide_01",
                "source_class": summary["source_class"],
                "text_fallback": True,
                "base_image_sha256": summary["base_sha256"],
                "final_image_sha256": summary["output_sha256"],
            }
            self.assertEqual(receipt["source_class"], "deterministic-overlay")
            self.assertTrue(receipt["text_fallback"])
            self.assertNotEqual(receipt["base_image_sha256"], receipt["final_image_sha256"])


if __name__ == "__main__":
    unittest.main()
