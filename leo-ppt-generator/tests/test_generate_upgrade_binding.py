#!/usr/bin/env python3
"""dashi 集成 K4/U4 行为测试：generate 冻结绑定与关联 upgrade baseline。

覆盖：
  1. content pack / stamp-page-ids CLI 通道（编译、校验、legacy 拒绝）；
  2. image prepare 消费 committed generation：旧参数、缺 pointer、篡改与错页拒绝；
  3. upgrade import-baseline：source_binding 关联（源 run/交付 SHA/内容与
     设计快照复制）、幂等重放、源目录移走后 load_baseline 仍可恢复、
     复制失败不暴露半份基线。
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.cli import build_parser, dispatch  # noqa: E402
from leo_ppt_generator.contracts import ContractError  # noqa: E402
from leo_ppt_generator.storage import sha256_bytes  # noqa: E402
from leo_ppt_generator.upgrade.baseline import (  # noqa: E402
    BaselineError,
    import_baseline,
    inspect_image_delivery,
    load_baseline,
)

MASTER = """# 母版 v1
confirmation: confirmed（测试基线）

## S1 封面
page_id: pg-11111111
角色：封面
argument_role: 开场
- 标题：增长质量
- 要点 1：三大指标向好
视觉行：要点1→巨字卡
- 备注：口播 30 秒

## S2 财务
page_id: pg-22222222
角色：流程·路径
argument_role: 论据
- 标题：营收 1.24 亿元
- 要点 1：环比 +18%
- 要点 2：净利率 12%
视觉行：要点1→KPI 塔 要点2→指标卡
- 备注：引用财报

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |
"""

SLIDES = [
    {"number": 1, "title": "增长质量", "notes": "口播 30 秒"},
    {"number": 2, "title": "营收 1.24 亿元", "notes": "引用财报"},
]


def _dispatch(argv: list[str]):
    return dispatch(build_parser().parse_args(argv))


class ContentPackCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.master = self.root / "deck-master-v1.md"
        self.master.write_text(MASTER, encoding="utf-8")

    def test_compile_pack_via_cli(self):
        out = self.root / "page-content-pack.json"
        result = _dispatch([
            "content", "pack", "--master", str(self.master), "--out", str(out)])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["content_pack"]["pages"], 2)
        self.assertEqual(result["content_pack"]["master_revision"], "v1")
        pack = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(
            pack["content_digest"], result["content_pack"]["content_digest"])

    def test_stamp_page_ids_then_compile(self):
        legacy = self.root / "deck-master-2.md"
        legacy.write_text("\n".join(
            ln for ln in MASTER.splitlines() if not ln.startswith("page_id:")
        ), encoding="utf-8")
        stamped = self.root / "deck-master-v2.md"
        result = _dispatch([
            "content", "stamp-page-ids", "--master", str(legacy), "--out", str(stamped)])
        self.assertEqual(result["status"], "ready")
        out = self.root / "pack2.json"
        compiled = _dispatch([
            "content", "pack", "--master", str(stamped), "--out", str(out)])
        self.assertEqual(compiled["content_pack"]["pages"], 2)

    def test_legacy_master_without_identity_rejected(self):
        legacy = self.root / "deck-master-v3.md"
        legacy.write_text("\n".join(
            ln for ln in MASTER.splitlines() if not ln.startswith("page_id:")
        ), encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            _dispatch(["content", "pack", "--master", str(legacy),
                       "--out", str(self.root / "p.json")])
        self.assertIn("content_pack_invalid", str(caught.exception))


class PrepareContentBindingTests(unittest.TestCase):
    def setUp(self):
        from tests.expression_test_support import copy_real_html_run
        from leo_ppt_generator.application.expression_pipeline import load_committed_input
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.run_root = self.root / "run"
        copy_real_html_run(self.run_root)
        committed = load_committed_input(self.run_root)
        self.inputs = committed["root"]
        self.pack = committed["payload"]["pack"]
        self.slides_path = self.root / "slides.json"
        self.slides = [{"page_id": page["page_id"], "number": page["number"], "notes": ""}
                       for page in self.pack["pages"]]
        self.slides_path.write_text(json.dumps(self.slides))

    def _prepare(self):
        return _dispatch(["image", "prepare", str(self.run_root), "--slides", str(self.slides_path)])

    def test_prepare_consumes_committed_binding_and_only_freezes_supplemental_slides(self):
        before = (self.run_root / "input/current.json").read_bytes()
        result = self._prepare()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["content_binding"]["page_ids"], [page["page_id"] for page in self.pack["pages"]])
        self.assertEqual((self.run_root / "input/current.json").read_bytes(), before)
        self.assertFalse((self.run_root / "input/page-content-pack.json").exists())
        self.assertTrue((self.run_root / "input/slides.json").is_file())

    def test_prepare_replay_is_idempotent(self):
        first, second = self._prepare(), self._prepare()
        self.assertEqual(first["content_binding"], second["content_binding"])
        self.assertEqual(second["idempotency_status"], "replayed")

    def test_tampered_pack_rejected_before_supplemental_freeze(self):
        (self.inputs / "page-content-pack.json").write_text('{"pages":[]}')
        with self.assertRaisesRegex(ContractError, "input_generation_invalid"):
            self._prepare()
        self.assertFalse((self.run_root / "input/slides.json").exists())

    def test_stable_page_id_is_required_even_if_page_numbers_match(self):
        self.slides[0]["page_id"] = "pg-99999999"
        self.slides_path.write_text(json.dumps(self.slides))
        with self.assertRaisesRegex(ContractError, "content_pack_page_mismatch"):
            self._prepare()
        self.assertFalse((self.run_root / "input/slides.json").exists())

    def test_missing_pointer_and_partial_selection_fail_closed(self):
        (self.inputs / "layout-selection.json").write_text('{"selection":{}}')
        with self.assertRaisesRegex(ContractError, "input_generation_invalid"):
            self._prepare()
        (self.run_root / "input/current.json").unlink()
        with self.assertRaisesRegex(ContractError, "input_pointer_missing"):
            self._prepare()

    def test_old_three_file_freeze_flags_are_not_a_second_production_entry(self):
        from contextlib import redirect_stderr
        import io
        for flag in ("--content-pack", "--design", "--layout-selection"):
            with self.subTest(flag=flag), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                _dispatch(["image", "prepare", str(self.run_root), "--slides", str(self.slides_path), flag, "legacy.json"])
            self.assertEqual(caught.exception.code, 2)
        self.assertFalse((self.run_root / "input/slides.json").exists())


def _make_source_run(root: Path, *, pack: dict | None, design: dict | None) -> Path:
    """构造一个已交付的 generate run（页产物 + PPTX + 关联输入快照）。"""
    run = root / "runs" / "source"
    (run / "image-deck" / "origin_image").mkdir(parents=True)
    (run / "final").mkdir(parents=True)
    (run / "input").mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({
        "schema_version": 1, "run_id": "src-1", "route": "generate",
        "revision": 0, "supplemental_inputs": {},
    }), encoding="utf-8")
    pages = []
    for number in (1, 2):
        artifact = run / "image-deck" / "origin_image" / f"slide_{number:02d}.png"
        artifact.write_bytes(f"PAGE{number}".encode())
        pages.append({
            "number": number,
            "status": "recorded",
            "artifact": f"origin_image/slide_{number:02d}.png",
            "sha256": sha256_bytes(f"PAGE{number}".encode()),
            "notes": f"notes-{number}",
        })
    pptx = run / "final" / "deck.pptx"
    pptx.write_bytes(b"FAKE-PPTX")
    jobs = {
        "slides": pages,
        "delivery": {"pptx": str(pptx), "sha256": sha256_bytes(b"FAKE-PPTX"),
                     "artifact_fingerprint": "fp"},
    }
    (run / "image-deck" / "slide_jobs.json").write_text(
        json.dumps(jobs), encoding="utf-8")
    if pack is not None:
        (run / "input" / "page-content-pack.json").write_text(
            json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    if design is not None:
        (run / "input" / "resolved-design.json").write_text(
            json.dumps(design, ensure_ascii=False), encoding="utf-8")
    return run


class UpgradeLinkedBaselineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        master = self.root / "deck-master-v1.md"
        master.write_text(MASTER, encoding="utf-8")
        pack_out = self.root / "page-content-pack.json"
        _dispatch(["content", "pack", "--master", str(master), "--out", str(pack_out)])
        self.pack = json.loads(pack_out.read_text(encoding="utf-8"))
        self.design = {
            "entity": "resolved-design",
            "pages": [{"page_no": 1}, {"page_no": 2}],
            "design_digest": "a" * 64,
            "design_context_digest": "b" * 64,
        }
        self.source = _make_source_run(self.root, pack=self.pack, design=self.design)

    def _target(self) -> Path:
        target = self.root / "runs" / "target"
        (target / "input").mkdir(parents=True, exist_ok=True)
        (target / "run.json").write_text(json.dumps({
            "schema_version": 1, "run_id": "tgt-1", "route": "upgrade-full",
            "revision": 0, "supplemental_inputs": {},
        }), encoding="utf-8")
        return target

    def test_inspect_carries_linked_input_digests(self):
        inspected = inspect_image_delivery(self.source)
        inputs = inspected["source_inputs"]
        self.assertIn("content_pack", inputs)
        self.assertEqual(inputs["content_pack"]["content_digest"],
                         self.pack["content_digest"])
        self.assertEqual(inputs["resolved_design"]["design_digest"],
                         self.design["design_digest"])

    def test_import_copies_snapshots_and_recovers_without_source(self):
        target = self._target()
        result = import_baseline(self.source, target)
        self.assertEqual(result["idempotency_status"], "created")
        binding = result["source_binding"]
        self.assertEqual(binding["source_run_id"], "src-1")
        self.assertEqual(binding["target_route"], "upgrade-full")
        self.assertIn("content_pack", binding["linked_inputs"])
        baseline_dir = target / "image-baseline"
        self.assertTrue((baseline_dir / "content_pack.json").is_file())
        self.assertTrue((baseline_dir / "resolved_design.json").is_file())
        # 源目录整体移走后，目标仍可从本地快照恢复基线。
        shutil.rmtree(self.source)
        loaded = load_baseline(target)
        self.assertEqual(loaded["source_binding"]["linked_inputs"]
                         ["content_pack"]["content_digest"],
                         self.pack["content_digest"])

    def test_same_source_replay_and_conflict(self):
        target = self._target()
        first = import_baseline(self.source, target)
        self.assertEqual(first["idempotency_status"], "created")
        replay = import_baseline(self.source, target)
        self.assertEqual(replay["idempotency_status"], "replayed")
        # 源内容改版（新内容包）→ 同一目标输入冲突，明确拒绝。
        revised = json.loads(json.dumps(self.pack))
        revised["pages"][0]["claim"] = "改版标题"
        from leo_ppt_generator.content_pack import content_digest
        revised["content_digest"] = content_digest(revised)
        (self.source / "input" / "page-content-pack.json").write_text(
            json.dumps(revised, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(BaselineError) as caught:
            import_baseline(self.source, target)
        self.assertEqual(str(caught.exception), "upgrade_baseline_conflict")

    def test_failed_copy_leaves_no_executable_half_baseline(self):
        target = self._target()
        # 篡改页产物哈希 → 复制校验失败 → baseline 目录整体清理。
        artifact = self.source / "image-deck" / "origin_image" / "slide_02.png"
        artifact.write_bytes(b"TAMPERED")
        with self.assertRaises(BaselineError):
            import_baseline(self.source, target)
        self.assertFalse((target / "image-baseline" / "baseline.json").is_file())

    def test_non_generate_route_rejected(self):
        target = self._target()
        run = json.loads((self.source / "run.json").read_text(encoding="utf-8"))
        run["route"] = "direct-editable"
        (self.source / "run.json").write_text(json.dumps(run), encoding="utf-8")
        with self.assertRaises(BaselineError):
            import_baseline(self.source, target)


if __name__ == "__main__":
    unittest.main()


class ReviewCoverageTests(unittest.TestCase):
    """独立审查覆盖补充（lfg-dashi-1788979338）：冲突分支与快照篡改。"""

    def _setup(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        run_root = root / "run"
        (run_root / "input").mkdir(parents=True)
        (run_root / "run.json").write_text(json.dumps({
            "schema_version": 1, "run_id": "r1", "route": "generate",
            "revision": 0, "supplemental_inputs": {}}), encoding="utf-8")
        master = root / "deck-master-v1.md"
        master.write_text(MASTER, encoding="utf-8")
        pack_path = root / "page-content-pack.json"
        _dispatch(["content", "pack", "--master", str(master), "--out", str(pack_path)])
        design_path = root / "resolved-design.json"
        design_path.write_text(json.dumps({
            "entity": "resolved-design", "pages": [{"page_no": 1}, {"page_no": 2}],
            "design_digest": "a" * 64, "design_context_digest": "b" * 64,
        }), encoding="utf-8")
        slides = root / "slides.json"
        slides.write_text(json.dumps(SLIDES), encoding="utf-8")
        return root, run_root, pack_path, design_path, slides

    def test_loose_design_and_selection_cannot_be_frozen_by_prepare(self):
        from contextlib import redirect_stderr
        import io
        _root, run_root, pack_path, design_path, slides = self._setup()
        for flag, path in (("--design", design_path), ("--layout-selection", pack_path)):
            with self.subTest(flag=flag), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                _dispatch(["image", "prepare", str(run_root), "--slides", str(slides), flag, str(path)])
            self.assertEqual(caught.exception.code, 2)
        self.assertFalse((run_root / "input/layout-selection.json").exists())
        self.assertFalse((run_root / "input/resolved-design.json").exists())

    def test_linked_snapshot_tamper_fail_closed(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, True))
        master = root / "deck-master-v1.md"
        master.write_text(MASTER, encoding="utf-8")
        pack_out = root / "p.json"
        _dispatch(["content", "pack", "--master", str(master), "--out", str(pack_out)])
        pack = json.loads(pack_out.read_text(encoding="utf-8"))
        source = _make_source_run(root, pack=pack, design={
            "entity": "resolved-design", "pages": [{"page_no": 1}, {"page_no": 2}],
            "design_digest": "a" * 64})
        target = root / "runs" / "target"
        (target / "input").mkdir(parents=True)
        (target / "run.json").write_text(json.dumps({
            "schema_version": 1, "run_id": "t", "route": "upgrade-full",
            "revision": 0, "supplemental_inputs": {}}), encoding="utf-8")
        from leo_ppt_generator.upgrade.baseline import load_baseline
        result = import_baseline(source, target)
        snapshot = Path(result["source_binding"]["linked_inputs"]["content_pack"]["path"])
        snapshot.write_text("{} tampered", encoding="utf-8")
        with self.assertRaises(BaselineError):
            load_baseline(target)
