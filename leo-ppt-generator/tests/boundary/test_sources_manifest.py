#!/usr/bin/env python3
"""check_sources_manifest.py 行为测试：默认/--strict/--compile/--check-job-prompts
四模式与退出码三态（0/1/2）。"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_sources_manifest.py"


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(manifest):
    payload = {k: v for k, v in manifest.items() if k != "contents_sha256"}
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def visual(**overrides):
    base = {
        "visual_id": "v1",
        "figure_id": "F1",
        "kind": "figure",
        "source_class": "user-material",
        "tier": "引用",
        "handling_mode": "preserve",
        "review_status": "vision-reviewed",
        "source_ref": "sources/paper/fig1.png",
        "source_sha256": None,
        "backend": "user",
    }
    base.update(overrides)
    return base


def make_manifest(pages):
    manifest = {
        "schema_version": 1,
        "manifest_kind": "visual-sources",
        "route": "generate",
        "run_ref": "runs/r1",
        "generated_from": "content/deck-master-v1.md",
        "pages": pages,
    }
    manifest["contents_sha256"] = fingerprint(manifest)
    return manifest


def write_run(manifest, *, slides=(1, 2), extra_files=()):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    run_dir = root / "run"
    (run_dir / "input").mkdir(parents=True)
    (run_dir / "input" / "sources-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "slide_jobs.json").write_text(
        json.dumps(
            {
                "slides": [
                    {"number": n, "slide_id": f"slide_{n:02d}", "status": "pending"}
                    for n in slides
                ]
            }
        ),
        encoding="utf-8",
    )
    for rel, content in extra_files:
        target = run_dir / "input" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
    return tmp, run_dir


def run(args, cwd=None):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    return result.returncode, result.stdout + result.stderr


VALID_PAGES = [
    {"page_id": "slide_01", "visuals": []},
    {
        "page_id": "slide_02",
        "visuals": [
            visual(source_sha256=None),
            visual(
                visual_id="v2",
                figure_id=None,
                kind="background",
                source_class="ai-generated",
                tier="示意",
                handling_mode=None,
                review_status=None,
                source_ref=None,
                backend="builtin-imagegen",
            ),
        ],
    },
]


class SourcesManifestTest(unittest.TestCase):
    def test_valid_generate_manifest_passes(self):
        manifest = make_manifest(json.loads(json.dumps(VALID_PAGES)))
        # 引用级图带源文件（含 sha256）。
        png = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 16
        manifest["pages"][1]["visuals"][0]["source_sha256"] = hashlib.sha256(png).hexdigest()
        manifest["contents_sha256"] = fingerprint(manifest)
        tmp, run_dir = write_run(
            manifest, extra_files=[("sources/paper/fig1.png", png)]
        )
        with tmp:
            code, out = run([str(run_dir), "--strict"])
            self.assertEqual(code, 0, out)

    def test_citation_tier_with_missing_source_file_fails_strict(self):
        manifest = make_manifest(json.loads(json.dumps(VALID_PAGES)))
        tmp, run_dir = write_run(manifest)  # 不创建 sources/paper/fig1.png
        with tmp:
            code, out = run([str(run_dir), "--strict"])
            self.assertEqual(code, 1, out)
            self.assertIn("source_unverifiable", out)

    def test_citation_tier_missing_source_passes_default_mode(self):
        """默认档不追源（strict 才追），避免把校验器变成第二套 prepare。"""
        manifest = make_manifest(json.loads(json.dumps(VALID_PAGES)))
        tmp, run_dir = write_run(manifest)
        with tmp:
            code, out = run([str(run_dir)])
            self.assertEqual(code, 0, out)

    def test_ai_generated_marked_as_citation_fails_strict(self):
        pages = [
            {
                "page_id": "slide_01",
                "visuals": [
                    visual(source_class="ai-generated", source_ref=None, backend="builtin-imagegen"),
                    visual(
                        visual_id="v2",
                        figure_id=None,
                        kind="figure",
                        source_class="ai-generated",
                        tier="引用",
                        source_ref="https://example.com/fig.png",
                        backend="builtin-imagegen",
                    ),
                ],
            },
            {"page_id": "slide_02", "visuals": []},
        ]
        manifest = make_manifest(pages)
        tmp, run_dir = write_run(manifest)
        with tmp:
            code, out = run([str(run_dir), "--strict"])
            self.assertEqual(code, 1, out)
            self.assertIn("冒充引用", out)

    def test_contents_sha256_tamper_fails(self):
        manifest = make_manifest(json.loads(json.dumps(VALID_PAGES)))
        manifest["contents_sha256"] = "0" * 64
        tmp, run_dir = write_run(manifest)
        with tmp:
            code, out = run([str(run_dir)])
            self.assertEqual(code, 1, out)
            self.assertIn("contents_sha256", out)

    def test_sensitive_field_rejected(self):
        pages = json.loads(json.dumps(VALID_PAGES))
        pages[1]["visuals"][0]["source_ref"] = "sources/paper/api_key.png"
        manifest = make_manifest(pages)
        tmp, run_dir = write_run(manifest)
        with tmp:
            code, out = run([str(run_dir)])
            self.assertEqual(code, 1, out)
            self.assertIn("敏感", out)

    def test_enum_violation_fails(self):
        pages = json.loads(json.dumps(VALID_PAGES))
        pages[1]["visuals"][0]["tier"] = "unknown"
        manifest = make_manifest(pages)
        tmp, run_dir = write_run(manifest)
        with tmp:
            code, out = run([str(run_dir)])
            self.assertEqual(code, 1, out)
            self.assertIn("tier", out)

    def test_null_source_ref_on_citation_fails(self):
        pages = json.loads(json.dumps(VALID_PAGES))
        pages[1]["visuals"][0]["source_ref"] = None
        manifest = make_manifest(pages)
        tmp, run_dir = write_run(manifest)
        with tmp:
            code, out = run([str(run_dir)])
            self.assertEqual(code, 1, out)

    def test_page_coverage_mismatch_fails(self):
        manifest = make_manifest([{"page_id": "slide_01", "visuals": []}])
        tmp, run_dir = write_run(manifest, slides=(1, 2))
        with tmp:
            code, out = run([str(run_dir)])
            self.assertEqual(code, 1, out)
            self.assertIn("slide_02", out)

    def test_warn_only_review_status_exits_2(self):
        pages = json.loads(json.dumps(VALID_PAGES))
        pages[1]["visuals"][0]["review_status"] = "caption-inferred"
        manifest = make_manifest(pages)
        tmp, run_dir = write_run(manifest)
        with tmp:
            code, out = run([str(run_dir)])
            self.assertEqual(code, 2, out)
            self.assertIn("caption-inferred", out)

    def test_figure_id_duplicate_fails(self):
        pages = [
            {"page_id": "slide_01", "visuals": [visual()]},
            {"page_id": "slide_02", "visuals": [visual(visual_id="v9")]},
        ]
        manifest = make_manifest(pages)
        tmp, run_dir = write_run(manifest)
        with tmp:
            code, out = run([str(run_dir)])
            self.assertEqual(code, 1, out)
            self.assertIn("重复", out)

    def test_strict_master_cross_check(self):
        manifest = make_manifest(json.loads(json.dumps(VALID_PAGES)))
        tmp, run_dir = write_run(manifest)
        master = Path(tmp.name) / "master.md"
        master.write_text(
            "# 母版\n图[F1] 模式:preserve 状态:vision-reviewed 焦点:主结果\n"
            "承载:误差线 | 服务:方法对比 | 避免误读:误差线≠显著性\n",
            encoding="utf-8",
        )
        with tmp:
            code, out = run([str(run_dir), "--strict", "--master", str(master)])
            self.assertEqual(code, 1, out)  # strict 下引用级仍无源文件 → FAIL
            # 换成母版含 F2（manifest 无）也应 FAIL。
            master.write_text(
                "# 母版\n图[F2] 模式:preserve 状态:vision-reviewed 焦点:主结果\n",
                encoding="utf-8",
            )
            code, out = run([str(run_dir), "--master", str(master)])
            self.assertEqual(code, 1, out)
            self.assertIn("figure_id", out)

    def test_strict_low_review_with_positional_annotation_fails(self):
        pages = json.loads(json.dumps(VALID_PAGES))
        pages[1]["visuals"][0]["review_status"] = "caption-inferred"
        manifest = make_manifest(pages)
        tmp, run_dir = write_run(manifest)
        master = Path(tmp.name) / "master.md"
        master.write_text(
            "# 母版\n图[F1] 模式:preserve 状态:caption-inferred 焦点:高亮右上子图\n",
            encoding="utf-8",
        )
        with tmp:
            code, out = run([str(run_dir), "--strict", "--master", str(master)])
            self.assertEqual(code, 1, out)
            self.assertIn("位置性标注", out)


class CompileModeTest(unittest.TestCase):
    def test_compile_mode_aggregates_page_provenance(self):
        with tempfile.TemporaryDirectory() as name:
            run_dir = Path(name) / "run"
            page = run_dir / "pages" / "page_002"
            page.mkdir(parents=True)
            (page / "manifest.json").write_text(
                json.dumps(
                    {
                        "asset_provenance": [
                            {
                                "path": "assets/logo.png",
                                "source": "source.png",
                                "source_type": "asset-sheet-separated",
                                "provenance_note": "asset-sheet separated from source",
                            },
                            {
                                "path": "assets/hero.png",
                                "source": "source.png",
                                "source_type": "user-provided",
                                "provenance_note": "user photo",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (page / "imagegen-jobs.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "jobs": [
                            {
                                "job_id": "icon-sheet",
                                "role": "asset_sheet",
                                "status": "recorded",
                                "source_image": "/tmp/tool-output.png",
                                "output": "assets/logo.png",
                                "output_sha256": "a" * 64,
                                "backend": "builtin-imagegen",
                                "fallback_reason": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = Path(name) / "compiled.json"
            code, output = run(["--compile", str(run_dir), "--out", str(out)])
            self.assertEqual(code, 0, output)
            compiled = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(compiled["manifest_kind"], "visual-sources")
            self.assertEqual(compiled["pages"][0]["page_id"], "slide_02")
            classes = {v["source_class"] for v in compiled["pages"][0]["visuals"]}
            self.assertEqual(classes, {"derived-crop", "user-material"})
            job_backed = [
                v
                for v in compiled["pages"][0]["visuals"]
                if v["source_ref"] == "assets/logo.png"
            ]
            self.assertEqual(job_backed[0]["backend"], "builtin-imagegen")
            self.assertEqual(job_backed[0]["source_sha256"], "a" * 64)
            # 自指纹可复算。
            self.assertEqual(compiled["contents_sha256"], fingerprint(compiled))


class JobPromptBlockTest(unittest.TestCase):
    def _spec(self, with_required=True, with_lock=True):
        slide = {"number": 1, "title": "T", "key_points": ["a"]}
        if with_required:
            slide["required_text"] = ["标题甲", "要点一"]
        spec = {"deck_name": "d", "slides": [slide]}
        if with_lock:
            spec["style_lock"] = {"shell": "纸色外层壳", "constants": ["页码右下"]}
        return spec

    def _prepare(self, spec):
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        deck = Path(tmp.name) / "deck"
        deck.mkdir()
        (deck / "slides.json").write_text(
            json.dumps(spec, ensure_ascii=False), encoding="utf-8"
        )
        prompts = deck / "prompts" / "slide_01.json"
        prompts.parent.mkdir()
        return tmp, deck, prompts

    def test_missing_required_text_block_fails(self):
        tmp, deck, prompts = self._prepare(self._spec())
        with tmp:
            prompts.write_text(
                json.dumps({"slide": 1, "prompt": "## Text\n没有白名单块\n"}),
                encoding="utf-8",
            )
            code, out = run(["--check-job-prompts", str(deck)])
            self.assertEqual(code, 1, out)
            self.assertIn("Required Text Only", out)
            self.assertIn("静默丢失", out)

    def test_non_verbatim_item_fails(self):
        tmp, deck, prompts = self._prepare(self._spec())
        with tmp:
            prompts.write_text(
                json.dumps(
                    {
                        "slide": 1,
                        "prompt": "## Required Text Only\n- 标题甲\n- 要点二\n## Deck Style Lock\n纸色外层壳\n",
                    }
                ),
                encoding="utf-8",
            )
            code, out = run(["--check-job-prompts", str(deck)])
            self.assertEqual(code, 1, out)
            self.assertIn("逐字", out)

    def test_missing_style_lock_block_fails(self):
        tmp, deck, prompts = self._prepare(self._spec())
        with tmp:
            prompts.write_text(
                json.dumps(
                    {
                        "slide": 1,
                        "prompt": "## Required Text Only\n- 标题甲\n- 要点一\n",
                    }
                ),
                encoding="utf-8",
            )
            code, out = run(["--check-job-prompts", str(deck)])
            self.assertEqual(code, 1, out)
            self.assertIn("Deck Style Lock", out)

    def test_complete_blocks_pass(self):
        tmp, deck, prompts = self._prepare(self._spec())
        with tmp:
            prompts.write_text(
                json.dumps(
                    {
                        "slide": 1,
                        "prompt": (
                            "## Deck Style Lock\n纸色外层壳\n## Required Text Only\n"
                            "- 标题甲\n- 要点一\n"
                        ),
                    }
                ),
                encoding="utf-8",
            )
            code, out = run(["--check-job-prompts", str(deck)])
            self.assertEqual(code, 0, out)

    def test_no_declaration_no_requirement(self):
        tmp, deck, prompts = self._prepare(
            self._spec(with_required=False, with_lock=False)
        )
        with tmp:
            prompts.write_text(
                json.dumps({"slide": 1, "prompt": "普通 prompt\n"}), encoding="utf-8"
            )
            code, out = run(["--check-job-prompts", str(deck)])
            self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
