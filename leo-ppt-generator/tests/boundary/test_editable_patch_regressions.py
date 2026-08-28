"""Patch 0004 / 0006 聚焦回归：vendored editable 运行时的补丁行为。

- 0004：`quality_contract_violations` 必须把 confirmed 的
  `expected_formula_inventory` 缺席视为质量合同违规，且拒绝非 list 清单与
  未确认的候选。
- 0006：legacy `.ppt` 规范化必须把请求的 dpi 透传给 `render_pdf_pages`
  （补丁前代码误引用不存在的 `args.dpi`）。

直接对 vendored 模块做边界测试（工作流 Agent 才被禁止 import `_vendor`；
本文件的目的恰是证明补丁后的 vendor 行为）。外部转换器
（LibreOffice/soffice）通过 monkeypatch 替换，测试不依赖真实 Office 栈。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[2]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

_input_normalization = None
validate_pptx = None
_IMPORT_ERROR = None
try:
    from leo_ppt_generator._vendor.editable_ppt.editppt.runtime import (
        _input_normalization,
    )

    # validate_pptx.py 沿用上游扁平布局（`from build_pptx_from_manifest import
    # ...`），顶层 adapter 以子进程脚本方式运行它；这里按同一布局做文件路径
    # 加载，临时把 vendor runtime 目录挂上 sys.path 以解析裸 import。
    _VENDOR_RUNTIME_DIR = Path(_input_normalization.__file__).parent
    _spec = importlib.util.spec_from_file_location(
        "validate_pptx_under_test", _VENDOR_RUNTIME_DIR / "validate_pptx.py"
    )
    validate_pptx = importlib.util.module_from_spec(_spec)
    _had_vendor_dir = str(_VENDOR_RUNTIME_DIR) in sys.path
    if not _had_vendor_dir:
        sys.path.insert(0, str(_VENDOR_RUNTIME_DIR))
    try:
        _spec.loader.exec_module(validate_pptx)
    finally:
        if not _had_vendor_dir:
            sys.path.remove(str(_VENDOR_RUNTIME_DIR))
except ImportError as exc:  # pragma: no cover - 环境缺依赖时的诚实降级
    _IMPORT_ERROR = exc


@unittest.skipIf(_IMPORT_ERROR is not None, f"vendored runtime 不可导入: {_IMPORT_ERROR}")
class ExpectedFormulaInventoryTest(unittest.TestCase):
    """Patch 0004：confirmed 公式清单不可缺席。"""

    def test_confirmed_source_formula_inventory_cannot_be_omitted(self):
        manifest = {
            "expected_formula_inventory": [{"id": "f1", "status": "confirmed"}],
            "formula_inventory": [],
        }
        violations = validate_pptx.quality_contract_violations(manifest)
        missing = [
            v
            for v in violations
            if v.get("field") == "formula_inventory" and v.get("formula_id") == "f1"
        ]
        self.assertTrue(
            missing,
            "confirmed 公式缺席 formula_inventory 时必须产生违规",
        )
        self.assertIn("missing", missing[0].get("reason", ""))

        present = dict(
            manifest, formula_inventory=[{"id": "f1", "latex": "E=mc^2"}]
        )
        violations = validate_pptx.quality_contract_violations(present)
        self.assertFalse(
            [v for v in violations if v.get("formula_id") == "f1"],
            "公式在場时不得再报缺席违规",
        )

    def test_inventory_must_be_a_list(self):
        violations = validate_pptx.quality_contract_violations(
            {"expected_formula_inventory": "f1,f2", "formula_inventory": []}
        )
        self.assertTrue(
            any(
                v.get("field") == "expected_formula_inventory"
                and "list" in v.get("reason", "")
                for v in violations
            )
        )

    def test_unconfirmed_candidate_requires_explicit_confirmation(self):
        violations = validate_pptx.quality_contract_violations(
            {
                "expected_formula_inventory": [{"id": "f2", "status": "low"}],
                "formula_inventory": [{"id": "f2"}],
            }
        )
        self.assertTrue(
            any(
                "confirmation" in v.get("reason", "")
                for v in violations
                if v.get("field", "").startswith("expected_formula_inventory")
            )
        )


@unittest.skipIf(_IMPORT_ERROR is not None, f"vendored runtime 不可导入: {_IMPORT_ERROR}")
class LegacyPptDpiForwardingTest(unittest.TestCase):
    """Patch 0006：legacy .ppt 规范化透传请求的 dpi。"""

    def test_legacy_ppt_normalization_forwards_requested_dpi(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            source_ppt = tmp_dir / "legacy.ppt"
            source_ppt.write_bytes(b"fake legacy ppt payload")

            converted = tmp_dir / "converted.pptx"
            converted.write_bytes(b"fake converted pptx")
            rendered_pdf = tmp_dir / "legacy.pdf"
            rendered_pdf.write_bytes(b"fake pdf")

            captured = {}

            def fake_render_pdf_pages(pdf_path, pages_dir, dpi):
                captured["dpi"] = dpi
                page = Path(pages_dir) / "page_001.png"
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_bytes(b"fake page")
                return [page]

            with mock.patch.object(
                _input_normalization, "convert_ppt_to_pptx", return_value=converted
            ), mock.patch.object(
                _input_normalization, "collect_notes_from_pptx", return_value=[]
            ), mock.patch.object(
                _input_normalization, "convert_office_to_pdf", return_value=rendered_pdf
            ), mock.patch.object(
                _input_normalization, "render_pdf_pages", fake_render_pdf_pages
            ):
                manifest = _input_normalization.normalize_inputs(
                    [source_ppt], out_root=tmp_dir / "output", dpi=220
                )

            self.assertEqual(captured.get("dpi"), 220)
            deck_manifest = json.loads(
                Path(manifest).read_text(encoding="utf-8")
            )
            self.assertEqual(deck_manifest.get("input_type"), "ppt")


if __name__ == "__main__":
    unittest.main()
