"""聚焦回归（加固方案 WS5 / D-OBS-01）：render-lane deck 合同。

0 图像模型页的 deck 以 ``render-lane`` 合同满足 generate 路线——不再借
图像 Provider 合同的壳；样张 binding 接受页级渲染 backend（render:html）。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "runtime" / "src"))

from leo_ppt_generator.application.run_index import RunIndex  # noqa: E402
from leo_ppt_generator.application.sample_decisions import (  # noqa: E402
    ContractError,
    record_sample_decision,
)
from leo_ppt_generator.config.backend_contract import BackendRegistry  # noqa: E402


def _write_material(project: Path) -> None:
    (project / "sources").mkdir(parents=True, exist_ok=True)
    (project / "sources" / "material.md").write_text("# 材料\n", encoding="utf-8")


class RenderLaneContractTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-ws5-")
        self.project = Path(self._tmp.name) / "proj"
        self.contract_path = self.project / "contracts" / "backend.json"
        self.contract_path.parent.mkdir(parents=True, exist_ok=True)
        _write_material(self.project)

    def tearDown(self):
        self._tmp.cleanup()

    def _create(self) -> dict:
        contract = BackendRegistry.default().create_contract("render-lane", mode="generate")
        self.contract_path.write_text(json.dumps(contract), encoding="utf-8")
        return contract

    def test_contract_shape_is_honest_local_render(self):
        contract = self._create()
        self.assertEqual(contract["provider"], "render-lane")
        self.assertEqual(contract["credential_source"], "host-managed")
        self.assertIsNone(contract.get("credential_ref"))
        self.assertTrue(contract["capabilities"]["generate"])
        self.assertFalse(contract["capabilities"]["edit"])
        self.assertEqual(contract["model"], "render:html")

    def test_generate_route_run_create_satisfied_without_image_provider(self):
        self._create()
        run = RunIndex.create_from_request(
            self.project / "runs" / "run-001",
            route="generate",
            input_path=self.project / "sources" / "material.md",
            backend_contract_path=self.contract_path,
            runtime_identity="test",
            idempotency_key="ws5-render-lane",
            project_root=self.project,
        )
        self.assertTrue((self.project / "runs" / "run-001" / "run.json").is_file())

    def test_sample_binding_accepts_render_html_backend(self):
        self._create()
        run_root = self.project / "runs" / "run-001"
        RunIndex.create_from_request(
            run_root, route="generate",
            input_path=self.project / "sources" / "material.md",
            backend_contract_path=self.contract_path,
            runtime_identity="test", idempotency_key="ws5-binding",
            project_root=self.project,
        )
        samples = self.project / "samples"
        samples.mkdir(exist_ok=True)
        sample = samples / "sample.png"
        from PIL import Image

        Image.new("RGB", (2560, 1440), "#ffffff").save(sample)
        slides = self.project / "contracts" / "slides.json"
        slides.write_text(json.dumps([
            {"number": 1, "notes": ""}, {"number": 2, "notes": ""},
        ]), encoding="utf-8")
        binding = self.project / "contracts" / "binding.json"
        binding.write_text(json.dumps({
            "backend": "render:html", "width": 2560, "height": 1440,
            "generation_method": "leo-ppt render page（确定性渲染 lane）",
            "style_visual_path": str(samples / "style.json"),
            "layout_binding_path": None,
        }), encoding="utf-8")
        (samples / "style.json").write_text("{}", encoding="utf-8")
        auth = self.project / "content" / "authorization.md"
        auth.parent.mkdir(parents=True, exist_ok=True)
        auth.write_text("quote: 测试授权\n", encoding="utf-8")
        result = record_sample_decision(
            run_root, sample=sample, slides=slides, binding=binding,
            decision_source="user-delegated", authorization_ref=auth,
            authorization_quote="测试授权",
        )
        self.assertEqual(result["status"], "verified")

    def test_image_provider_contract_still_rejects_render_binding(self):
        contract = BackendRegistry.default().create_contract("zhipu", mode="generate")
        self.contract_path.write_text(json.dumps(contract), encoding="utf-8")
        run_root = self.project / "runs" / "run-002"
        RunIndex.create_from_request(
            run_root, route="generate",
            input_path=self.project / "sources" / "material.md",
            backend_contract_path=self.contract_path,
            runtime_identity="test", idempotency_key="ws5-negative",
            project_root=self.project,
        )
        samples = self.project / "samples2"
        samples.mkdir(exist_ok=True)
        sample = samples / "sample.png"
        from PIL import Image

        Image.new("RGB", (2560, 1440), "#ffffff").save(sample)
        slides = self.project / "contracts" / "slides2.json"
        slides.write_text(json.dumps([{"number": 1, "notes": ""}]), encoding="utf-8")
        binding = self.project / "contracts" / "binding2.json"
        binding.write_text(json.dumps({
            "backend": "render:html", "width": 2560, "height": 1440,
            "generation_method": "x", "style_visual_path": str(samples / "style.json"),
            "layout_binding_path": None,
        }), encoding="utf-8")
        (samples / "style.json").write_text("{}", encoding="utf-8")
        auth = self.project / "content" / "authorization.md"
        auth.parent.mkdir(parents=True, exist_ok=True)
        auth.write_text("quote: 测试授权\n", encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            record_sample_decision(
                run_root, sample=sample, slides=slides, binding=binding,
                decision_source="user-delegated", authorization_ref=auth,
                authorization_quote="测试授权",
            )
        self.assertEqual(str(caught.exception), "sample_backend_mismatch")


if __name__ == "__main__":
    unittest.main()
