#!/usr/bin/env python3
"""dashi 集成 K4/U4 行为测试：generate 冻结绑定与关联 upgrade baseline。

覆盖：
  1. content pack / stamp-page-ids CLI 通道（编译、校验、legacy 拒绝）；
  2. image prepare --content-pack/--design：输入冻结、RunIndex 登记、
     篡改拒绝、页序不匹配拒绝、内容改版 fingerprint 冲突（须建新 run）；
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
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_root = Path(self._tmp.name) / "run"
        (self.run_root / "input").mkdir(parents=True)
        (self.run_root / "run.json").write_text(json.dumps({
            "schema_version": 1, "run_id": "r1", "route": "generate",
            "revision": 0, "supplemental_inputs": {},
        }), encoding="utf-8")
        self.master = self._tmp_path("deck-master-v1.md")
        self.master.write_text(MASTER, encoding="utf-8")
        self.pack_path = self._tmp_path("page-content-pack.json")
        _dispatch(["content", "pack", "--master", str(self.master),
                   "--out", str(self.pack_path)])
        self.design_path = self._tmp_path("resolved-design.json")
        self.design_path.write_text(json.dumps({
            "entity": "resolved-design",
            "pages": [{"page_no": 1}, {"page_no": 2}],
            "design_digest": "a" * 64,
            "design_context_digest": "b" * 64,
        }), encoding="utf-8")
        self.slides_path = self._tmp_path("slides.json")
        self.slides_path.write_text(json.dumps(SLIDES), encoding="utf-8")

    def _tmp_path(self, name: str) -> Path:
        return Path(self._tmp.name) / name

    def _prepare(self, *extra: str):
        return _dispatch([
            "image", "prepare", str(self.run_root),
            "--slides", str(self.slides_path), *extra])

    def test_prepare_freezes_binding_and_records_supplemental(self):
        result = self._prepare("--content-pack", str(self.pack_path),
                               "--design", str(self.design_path))
        self.assertEqual(result["status"], "ready")
        binding = result["content_binding"]
        self.assertEqual(len(binding["page_ids"]), 2)
        self.assertTrue((self.run_root / "input/page-content-pack.json").is_file())
        self.assertTrue((self.run_root / "input/resolved-design.json").is_file())
        index = json.loads((self.run_root / "run.json").read_text(encoding="utf-8"))
        self.assertIn("content_pack", index["supplemental_inputs"])
        self.assertIn("resolved_design", index["supplemental_inputs"])

    def test_prepare_replay_with_same_binding_is_idempotent(self):
        first = self._prepare("--content-pack", str(self.pack_path))
        second = self._prepare("--content-pack", str(self.pack_path))
        self.assertEqual(first["content_binding"], second["content_binding"])
        self.assertEqual(second["idempotency_status"], "replayed")

    def test_tampered_pack_rejected(self):
        pack = json.loads(self.pack_path.read_text(encoding="utf-8"))
        pack["pages"][0]["claim"] = "手改标题"
        self.pack_path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            self._prepare("--content-pack", str(self.pack_path))
        self.assertEqual(str(caught.exception), "content_pack_invalid")

    def test_page_mismatch_rejected(self):
        slides2 = [dict(SLIDES[0], number=9), SLIDES[1]]
        self.slides_path.write_text(json.dumps(slides2), encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            self._prepare("--content-pack", str(self.pack_path))
        self.assertEqual(str(caught.exception), "content_pack_page_mismatch")

    def test_content_revision_after_prepare_requires_new_run(self):
        self._prepare("--content-pack", str(self.pack_path))
        revised = MASTER.replace("- 标题：增长质量", "- 标题：增长质量（修订）")
        master2 = self._tmp_path("deck-master-v2.md")
        master2.write_text(revised, encoding="utf-8")
        pack2 = self._tmp_path("page-content-pack-v2.json")
        _dispatch(["content", "pack", "--master", str(master2), "--out", str(pack2)])
        with self.assertRaises(ContractError) as caught:
            self._prepare("--content-pack", str(pack2))
        self.assertEqual(str(caught.exception), "page-content-pack_fingerprint_conflict")

    def test_design_page_mismatch_rejected(self):
        design = json.loads(self.design_path.read_text(encoding="utf-8"))
        design["pages"] = [{"page_no": 1}, {"page_no": 3}]
        self.design_path.write_text(json.dumps(design), encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            self._prepare("--content-pack", str(self.pack_path),
                          "--design", str(self.design_path))
        self.assertEqual(str(caught.exception), "design_page_mismatch")


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

    def test_design_revision_after_prepare_conflicts(self):
        _root, run_root, pack_path, design_path, slides = self._setup()
        _dispatch(["image", "prepare", str(run_root), "--slides", str(slides),
                   "--content-pack", str(pack_path), "--design", str(design_path)])
        drifted = json.loads(design_path.read_text(encoding="utf-8"))
        drifted["design_digest"] = "c" * 64
        design_path.write_text(json.dumps(drifted), encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            _dispatch(["image", "prepare", str(run_root), "--slides", str(slides),
                       "--content-pack", str(pack_path), "--design", str(design_path)])
        self.assertEqual(str(caught.exception), "resolved-design_fingerprint_conflict")

    def test_selection_without_pack_currently_freezes_without_cross_check(self):
        # 表征测试（现状语义）：无内容包时选择独立冻结、跳过摘要/覆盖核对。
        # 该缺口由独立审查 finding（selection-without-pack skips checks，
        # adversarial P2/75）作为 residual 跟踪；修复后此测试应改为断言拒绝。
        _root, run_root, pack_path, design_path, slides = self._setup()
        selection = _root / "layout-selection.json"
        selection.write_text(json.dumps({
            "schema_version": 1, "kind": "deck-layout-selection",
            "policy_version": "1", "status": "complete",
            "content_digest": "0" * 64, "selection": {}}), encoding="utf-8")
        result = _dispatch(["image", "prepare", str(run_root), "--slides", str(slides),
                            "--layout-selection", str(selection)])
        self.assertEqual(result["status"], "ready")
        self.assertTrue((run_root / "input/layout-selection.json").is_file())

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
