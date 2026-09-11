"""A2 image prepare --sources 冻结与 prepare_fingerprint 聚合的行为测试。

覆盖：
  1. 带 --sources 的 prepare：manifest 冻结进 <run>/input/sources-manifest.json，
     contents_sha256 并入 fingerprint，jobs 记 sources 元数据；
  2. 不带 --sources：fingerprint 与旧算法 sha256(canonical_json(slides)) 逐字节
     一致（旧 run 恢复兼容回归保护）；
  3. 旧 run（无 sources 键）无 sources 重放幂等；带 sources 再 prepare →
     image_prepare_fingerprint_conflict；
  4. 非法 manifest（schema / 自指纹 / 敏感字段）→ sources_manifest_invalid；
  5. CLI 通道（dispatch image prepare --sources）：冻结、幂等重放与漂移冲突。
"""

from __future__ import annotations

import copy
import hashlib
import json
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
from leo_ppt_generator.image_deck.adapter import (  # noqa: E402
    ImageDeckAdapter,
    validate_sources_manifest,
)
from leo_ppt_generator.storage import canonical_json, sha256_bytes  # noqa: E402


def _fingerprint(manifest: dict) -> str:
    payload = {key: value for key, value in manifest.items() if key != "contents_sha256"}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def make_manifest() -> dict:
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
                        "visual_id": "v1",
                        "figure_id": "F1",
                        "kind": "figure",
                        "source_class": "user-material",
                        "tier": "引用",
                        "handling_mode": "preserve",
                        "review_status": "vision-reviewed",
                        "source_ref": "sources/fig1.png",
                        "source_sha256": None,
                        "backend": "user",
                    }
                ],
            },
            {"page_id": "slide_02", "visuals": []},
        ],
    }
    manifest["contents_sha256"] = _fingerprint(manifest)
    return manifest


SLIDES = [
    {"number": 1, "title": "a", "notes": ""},
    {"number": 2, "title": "b", "notes": ""},
]

LEGACY_FINGERPRINT = sha256_bytes(canonical_json(SLIDES).encode())


class AdapterPrepareSourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name) / "image-deck"

    def test_prepare_without_sources_keeps_legacy_fingerprint(self):
        jobs = ImageDeckAdapter(self.run_dir).prepare(copy.deepcopy(SLIDES))
        self.assertEqual(jobs["prepare_fingerprint"], LEGACY_FINGERPRINT)
        self.assertIsNone(jobs["sources"])

    def test_prepare_with_sources_changes_fingerprint_and_records(self):
        manifest = make_manifest()
        jobs = ImageDeckAdapter(self.run_dir).prepare(
            copy.deepcopy(SLIDES), sources_manifest=copy.deepcopy(manifest)
        )
        expected = sha256_bytes(
            canonical_json(
                {"slides": SLIDES, "sources_manifest": manifest}
            ).encode()
        )
        self.assertEqual(jobs["prepare_fingerprint"], expected)
        self.assertNotEqual(jobs["prepare_fingerprint"], LEGACY_FINGERPRINT)
        self.assertEqual(
            jobs["sources"],
            {"path": "input/sources-manifest.json", "contents_sha256": manifest["contents_sha256"]},
        )

    def test_legacy_run_resumes_without_sources(self):
        adapter = ImageDeckAdapter(self.run_dir)
        # 模拟旧 run 产物：无 sources 键 + 旧算法 fingerprint。
        adapter.images_dir.mkdir(parents=True, exist_ok=True)
        legacy_jobs = {
            "schema_version": 1,
            "revision": 0,
            "prepare_fingerprint": LEGACY_FINGERPRINT,
            "run_status": "prepared",
            "operations": {},
            "slides": [
                {"number": 1, "slide_id": "slide_01", "status": "pending", "notes": ""},
                {"number": 2, "slide_id": "slide_02", "status": "pending", "notes": ""},
            ],
        }
        (self.run_dir / "slide_jobs.json").write_text(
            json.dumps(legacy_jobs), encoding="utf-8"
        )
        replayed = adapter.prepare(copy.deepcopy(SLIDES))
        self.assertEqual(replayed["prepare_fingerprint"], LEGACY_FINGERPRINT)
        self.assertNotIn("sources", replayed)

    def test_legacy_run_conflicts_when_sources_added(self):
        adapter = ImageDeckAdapter(self.run_dir)
        adapter.images_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "slide_jobs.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "revision": 0,
                    "prepare_fingerprint": LEGACY_FINGERPRINT,
                    "run_status": "prepared",
                    "operations": {},
                    "slides": [],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ContractError) as caught:
            adapter.prepare(copy.deepcopy(SLIDES), sources_manifest=make_manifest())
        self.assertEqual(str(caught.exception), "image_prepare_fingerprint_conflict")

    def test_idempotent_replay_with_same_sources(self):
        adapter = ImageDeckAdapter(self.run_dir)
        manifest = make_manifest()
        first = adapter.prepare(copy.deepcopy(SLIDES), sources_manifest=copy.deepcopy(manifest))
        replay = adapter.prepare(copy.deepcopy(SLIDES), sources_manifest=copy.deepcopy(manifest))
        self.assertEqual(first, replay)

    def test_invalid_manifest_rejected(self):
        adapter = ImageDeckAdapter(self.run_dir)
        tampered = make_manifest()
        tampered["contents_sha256"] = "0" * 64
        with self.assertRaises(ContractError) as caught:
            adapter.prepare(copy.deepcopy(SLIDES), sources_manifest=tampered)
        self.assertEqual(str(caught.exception), "sources_manifest_invalid")

        bad_enum = make_manifest()
        bad_enum["pages"][0]["visuals"][0]["source_class"] = "ai-generated-or-worse"
        bad_enum["contents_sha256"] = _fingerprint(bad_enum)
        with self.assertRaises(ContractError):
            adapter.prepare(copy.deepcopy(SLIDES), sources_manifest=bad_enum)

        sensitive = make_manifest()
        sensitive["pages"][0]["visuals"][0]["source_ref"] = "sources/api_key.png"
        sensitive["contents_sha256"] = _fingerprint(sensitive)
        with self.assertRaises(ContractError):
            validate_sources_manifest(sensitive)


class CliPrepareSourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_root = Path(self._tmp.name) / "run"
        (self.run_root / "input").mkdir(parents=True)
        (self.run_root / "run.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "run_id": "r1",
                    "route": "generate",
                    "revision": 0,
                    "supplemental_inputs": {},
                }
            ),
            encoding="utf-8",
        )
        self.slides_path = Path(self._tmp.name) / "slides.json"
        self.slides_path.write_text(json.dumps(SLIDES), encoding="utf-8")
        self.manifest_path = Path(self._tmp.name) / "sources-manifest.json"
        self.manifest_path.write_text(
            json.dumps(make_manifest(), ensure_ascii=False), encoding="utf-8"
        )

    def _dispatch(self, *extra: str):
        parser = build_parser()
        args = parser.parse_args(
            [
                "image",
                "prepare",
                str(self.run_root),
                "--slides",
                str(self.slides_path),
                *extra,
            ]
        )
        return dispatch(args)

    def test_cli_freezes_sources_into_run_input(self):
        result = self._dispatch("--sources", str(self.manifest_path))
        prepared = result["result"]
        frozen = self.run_root / "input" / "sources-manifest.json"
        self.assertTrue(frozen.is_file())
        self.assertEqual(
            prepared["sources"]["path"], "input/sources-manifest.json"
        )
        # 幂等重放：同 sources 再跑返回同一 state。
        replay = self._dispatch("--sources", str(self.manifest_path))
        self.assertEqual(replay["result"], prepared)

    def test_cli_conflicting_sources_rejected(self):
        self._dispatch("--sources", str(self.manifest_path))
        drifted = make_manifest()
        drifted["pages"][0]["visuals"][0]["source_ref"] = "sources/other.png"
        drifted["contents_sha256"] = _fingerprint(drifted)
        self.manifest_path.write_text(
            json.dumps(drifted, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaises(ContractError) as caught:
            self._dispatch("--sources", str(self.manifest_path))
        self.assertEqual(str(caught.exception), "sources_manifest_invalid")

    def test_cli_invalid_manifest_rejected(self):
        broken = make_manifest()
        broken["schema_version"] = 2
        self.manifest_path.write_text(json.dumps(broken), encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            self._dispatch("--sources", str(self.manifest_path))
        self.assertEqual(str(caught.exception), "sources_manifest_invalid")


class RecordedPageTerminalStateTest(unittest.TestCase):
    """D-DEF-04 回归：已 recorded 页只允许幂等重放或显式 rework 再写。"""

    def setUp(self):
        from PIL import Image

        self._tmp = tempfile.TemporaryDirectory(prefix="leo-ppt-recorded-")
        self.run_dir = Path(self._tmp.name) / "image-deck"
        adapter = ImageDeckAdapter(self.run_dir)
        adapter.prepare(copy.deepcopy(SLIDES))
        self.png = Path(self._tmp.name) / "page.png"
        Image.new("RGB", (1600, 900), "#ffffff").save(self.png)
        self.adapter = ImageDeckAdapter(self.run_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def _record_once(self):
        jobs = self.adapter._jobs()
        return self.adapter.record(
            1,
            self.png,
            backend="render:html",
            expected_revision=jobs["revision"],
            operation_id="op-first",
        )

    def test_late_record_on_recorded_page_rejected(self):
        self._record_once()
        jobs = self.adapter._jobs()
        with self.assertRaises(ContractError) as caught:
            self.adapter.record(
                1,
                self.png,
                backend="render:html",
                expected_revision=jobs["revision"],
                operation_id="op-late",
            )
        self.assertEqual(str(caught.exception), "page_already_recorded")

    def test_idempotent_replay_of_same_operation_still_allowed(self):
        first = self._record_once()
        jobs = self.adapter._jobs()
        replay = self.adapter.record(
            1,
            self.png,
            backend="render:html",
            expected_revision=jobs["revision"],
            operation_id="op-first",
        )
        self.assertEqual(first.artifact_sha256, replay.artifact_sha256)

    def test_explicit_rework_can_replace_recorded_page(self):
        self._record_once()
        jobs = self.adapter._jobs()
        artifact = self.adapter.record(
            1,
            self.png,
            backend="render:html",
            expected_revision=jobs["revision"],
            operation_id="op-rework",
            rework=True,
        )
        self.assertTrue(Path(artifact.artifact_path).is_file())


class DispatchDisciplineWarningTest(unittest.TestCase):
    """加固 WS6 第一步：同 agent-id 累计 record ≥3 页 → run 账本警告事件。"""

    def setUp(self):
        from PIL import Image

        self._tmp = tempfile.TemporaryDirectory(prefix="leo-ws6-")
        run_root = Path(self._tmp.name) / "run-001"
        self.run_dir = run_root / "image-deck"
        adapter = ImageDeckAdapter(self.run_dir)
        three = copy.deepcopy(SLIDES) + [{"number": 3, "notes": ""}]
        adapter.prepare(three)
        self.png = Path(self._tmp.name) / "page.png"
        Image.new("RGB", (1600, 900), "#ffffff").save(self.png)
        self.ledger = run_root / "reports" / "run-ledger.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def _record(self, number: int, agent: str) -> None:
        adapter = ImageDeckAdapter(self.run_dir)
        jobs = adapter._jobs()
        adapter.record(
            number, self.png, backend="render:html",
            expected_revision=jobs["revision"],
            operation_id=f"op-{number}-{agent}", agent_id=agent,
        )

    def test_third_consecutive_record_by_same_agent_warns(self):
        for n in (1, 2, 3):
            self._record(n, agent="serial-agent")
        self.assertTrue(self.ledger.is_file())
        lines = [json.loads(l) for l in self.ledger.read_text(encoding="utf-8").splitlines()]
        warnings = [l for l in lines if l.get("step") == "dispatch_discipline_warning"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["agent_id"], "serial-agent")
        self.assertEqual(warnings[0]["recorded_by_agent"], 3)
        self.assertEqual(warnings[0]["schema_version"], 1)
        self.assertEqual(warnings[0]["page"], "3")

    def test_distinct_agents_do_not_warn(self):
        for n, agent in ((1, "w1"), (2, "w2"), (3, "w3")):
            self._record(n, agent=agent)
        if self.ledger.is_file():
            lines = [json.loads(l) for l in self.ledger.read_text(encoding="utf-8").splitlines()]
            self.assertFalse([l for l in lines if l.get("step") == "dispatch_discipline_warning"])


if __name__ == "__main__":
    unittest.main()
