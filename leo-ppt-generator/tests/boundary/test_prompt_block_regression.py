#!/usr/bin/env python3
"""vendor patch 0007 聚焦回归：`prepare_slide_prompts.py` 渲染
"## Required Text Only" 与 "## Deck Style Lock" 独立块，且白名单逐字来自
slides.json。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VENDOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "runtime"
    / "src"
    / "leo_ppt_generator"
    / "_vendor"
    / "codex_ppt"
)
SCRIPT = VENDOR_DIR / "prepare_slide_prompts.py"


def prepare(spec) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as name:
        out_dir = Path(name) / "deck"
        out_dir.mkdir()
        spec_path = Path(name) / "spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--spec", str(spec_path), "--out-dir", str(out_dir)],
            capture_output=True,
            text=True,
            cwd=str(VENDOR_DIR),  # vendor 模块平铺导入 slide_run_state
        )
        jobs = {}
        for path in sorted((out_dir / "prompts").glob("slide_*.json")):
            jobs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        return result.returncode, {"stdout": result.stdout, "stderr": result.stderr, "jobs": jobs}


SPEC = {
    "deck_name": "alpha-m1-regression",
    "language": "Chinese",
    "goal": "verify prompt blocks",
    "style_lock": {
        "shell": "纸色外层壳 + 页码右下角",
        "constants": ["标题光学字号档 96px", "网格密度 低"],
    },
    "slides": [
        {
            "number": 1,
            "title": "标题甲",
            "key_points": ["要点一"],
            "required_text": ["标题甲", "要点一", "图注：样本 N=412"],
        },
        {"number": 2, "title": "无白名单页", "key_points": ["b"]},
    ],
}


class PromptBlockRegressionTest(unittest.TestCase):
    def test_prepare_emits_required_text_and_style_lock_blocks(self):
        code, context = prepare(SPEC)
        self.assertEqual(code, 0, context["stderr"])
        job = context["jobs"]["slide_01"]
        prompt = job["prompt"]
        self.assertIn("## Required Text Only", prompt)
        for item in SPEC["slides"][0]["required_text"]:
            self.assertIn(item, prompt, f"白名单条目未逐字进入 prompt：{item}")
        self.assertIn("No other content-bearing text", prompt)
        self.assertIn("## Deck Style Lock", prompt)
        self.assertIn("纸色外层壳 + 页码右下角", prompt)
        self.assertIn("标题光学字号档 96px", prompt)

    def test_slide_without_required_text_has_no_block(self):
        code, context = prepare(SPEC)
        self.assertEqual(code, 0, context["stderr"])
        prompt = context["jobs"]["slide_02"]["prompt"]
        self.assertNotIn("## Required Text Only", prompt)
        # deck 级 style_lock 仍然进入每一页。
        self.assertIn("## Deck Style Lock", prompt)

    def test_missing_required_text_block_is_detectable(self):
        """静默丢失可检出：job prompt 缺块时 --check-job-prompts 判 FAIL。"""
        check = (
            Path(__file__).resolve().parents[2] / "scripts" / "check_sources_manifest.py"
        )
        with tempfile.TemporaryDirectory() as name:
            deck = Path(name) / "deck"
            (deck / "prompts").mkdir(parents=True)
            (deck / "slides.json").write_text(
                json.dumps(
                    {
                        "slides": [
                            {"number": 1, "title": "t", "required_text": ["标题甲"]}
                        ],
                        "style_lock": {"shell": "x"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (deck / "prompts" / "slide_01.json").write_text(
                json.dumps({"slide": 1, "prompt": "## Text\n无白名单块\n"}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(check), "--check-job-prompts", str(deck)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("静默丢失", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
