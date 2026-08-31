"""F1 迁移等价性测试：legacy builder vs object builder 结构投影相等。

合同口径（团队δ设计 §5）：不做字节 diff——default 模板多余版式、endParaRPr、
属性顺序都是合法差异；等价 = 同一 manifest 在两个 builder 下产物的
``object_projection`` 投影相等（对象 kind/EMU 坐标/prst/custGeom 归一化顶点/
runs 全属性/notes hash/media 多重集）。validate_pptx（vendored，零改动）对
两个 builder 的产物都必须 passed=true——这是最强的等价证据。

覆盖矩阵：基线对象全属性 / letterbox 比例合同 / z 序稳定排序 / flip /
dash token / baseline / measured-font / 重复 media 引用 / notes 双路径
（text 与 notes_xml 字节冻结）/ 确定性（同输入同 sha256、跨 TZ）/
page.pptx 与 final deck 同构 / preset 非法值 build 期失败。
另含 F1-T5 tables 对象面、F2-T1 theme 双槽、F1-T4 builder 选择器与
run 冻结、X-6 组装门（清扫耗尽 × 缺页拒绝 × PARTIAL 不含未确认页）。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

FIXTURE_DIR = SKILL_DIR / "tests" / "fixtures" / "object-equivalence"

from leo_ppt_generator._vendor.editable_ppt.editppt.runtime import (  # noqa: E402
    build_pptx_from_manifest as vendor_builder,
)

from leo_ppt_generator.editable import (  # noqa: E402
    deterministic_zip,
    geometry,
    object_builder,
)
from leo_ppt_generator.editable.object_projection import project_pptx  # noqa: E402

EQUIVALENCE_FIXTURES = [
    "baseline-objects.json",
    "letterbox-portrait.json",
    "z-order-flip-dash.json",
]

VALIDATOR_PATH = Path(vendor_builder.__file__).with_name("validate_pptx.py")


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _fixture_manifest_with_images(name: str, workdir: Path) -> tuple[dict, Path]:
    """Copy a fixture manifest + its referenced images into ``workdir``."""
    manifest_path = workdir / name
    manifest_path.write_text(json.dumps(_load_fixture(name), ensure_ascii=False), encoding="utf-8")
    for image in _load_fixture(name).get("images", []):
        source = FIXTURE_DIR / Path(image["path"]).name
        target = workdir / image["path"]
        if not target.exists():
            target.write_bytes(source.read_bytes())
    return _load_fixture(name), manifest_path


def _run_validator(pptx_path: Path, manifest_path: Path) -> dict:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(pptx_path), "--manifest", str(manifest_path)],
        capture_output=True,
        text=True,
        env=environment,
        timeout=120,
        check=False,
    )
    return json.loads(completed.stdout)


def _assert_projection_equal(test: unittest.TestCase, legacy: dict, pptx: dict) -> None:
    if legacy == pptx:
        return
    differences = []
    for slide_index, (legacy_slide, pptx_slide) in enumerate(zip(legacy["slides"], pptx["slides"])):
        for object_index, (legacy_object, pptx_object) in enumerate(zip(legacy_slide["objects"], pptx_slide["objects"])):
            if legacy_object != pptx_object:
                differing = [key for key in set(legacy_object) | set(pptx_object) if legacy_object.get(key) != pptx_object.get(key)]
                differences.append(
                    f"slide{slide_index} object{object_index} "
                    f"({legacy_object.get('kind')}:{legacy_object.get('name')}): {differing}"
                )
        if legacy_slide != pptx_slide:
            for key in ("background", "notes_text_sha256"):
                if legacy_slide.get(key) != pptx_slide.get(key):
                    differences.append(f"slide{slide_index}.{key}")
    if legacy["media_hash_multiset"] != pptx["media_hash_multiset"]:
        differences.append("media_hash_multiset")
    if legacy["slide_size_emu"] != pptx["slide_size_emu"]:
        differences.append("slide_size_emu")
    if len(legacy["slides"]) != len(pptx["slides"]):
        differences.append(f"slide count {len(legacy['slides'])} != {len(pptx['slides'])}")
    test.fail("projection mismatch: " + "; ".join(differences))


class GeometryEquivalenceTest(unittest.TestCase):
    """F1-T1：共享几何层对 golden manifests 输出与 vendor 逐字段相等。"""

    FIXTURES = EQUIVALENCE_FIXTURES + ["tables-object-face.json", "theme-double-slot.json"]

    def test_normalize_manifest_matches_vendor_field_by_field(self):
        for name in self.FIXTURES:
            with self.subTest(fixture=name):
                manifest = _load_fixture(name)
                self.assertEqual(geometry.normalize_manifest(manifest), vendor_builder.normalize_manifest(manifest))

    def test_constants_match_vendor(self):
        self.assertEqual(geometry.TEXT_ALIGNMENTS, vendor_builder.TEXT_ALIGNMENTS)
        self.assertEqual(geometry.TEXT_VERTICAL_ALIGNMENTS, vendor_builder.TEXT_VERTICAL_ALIGNMENTS)
        self.assertEqual(geometry.EMU_PER_INCH, vendor_builder.EMU_PER_INCH)

    def test_fit_content_box_letterbox_values_match_vendor(self):
        for source in ((1080, 1920), (1920, 1080), (1600, 1200), (2560, 720)):
            with self.subTest(source=source):
                self.assertEqual(
                    geometry.fit_content_box(source[0], source[1], 13.333, 7.5),
                    vendor_builder.fit_content_box(source[0], source[1], 13.333, 7.5),
                )


class ProjectionEquivalenceTest(unittest.TestCase):
    """F1-T7 用例 1/2/3/5/6/7/8/11/12：结构投影等价 + validator 兜底 + page/deck 同构。"""

    def _build_both(self, name: str) -> tuple[Path, Path, Path]:
        workdir = Path(tempfile.mkdtemp(prefix="equiv-"))
        manifest, manifest_path = _fixture_manifest_with_images(name, workdir)
        legacy_path = workdir / "legacy.pptx"
        pptx_path = workdir / "object.pptx"
        vendor_builder.write_pptx(manifest, legacy_path, manifest_path)
        object_builder.write_pptx(manifest, pptx_path, manifest_path)
        return legacy_path, pptx_path, manifest_path

    def test_baseline_objects_project_identically(self):
        for name in EQUIVALENCE_FIXTURES:
            with self.subTest(fixture=name):
                legacy_path, pptx_path, _ = self._build_both(name)
                _assert_projection_equal(
                    self,
                    project_pptx(legacy_path),
                    project_pptx(pptx_path),
                )

    def test_custgeom_vertices_normalized_equal(self):
        legacy_path, pptx_path, _ = self._build_both("baseline-objects.json")
        legacy_objects = project_pptx(legacy_path)["slides"][0]["objects"]
        pptx_objects = project_pptx(pptx_path)["slides"][0]["objects"]
        legacy_polygons = [o["geometry"] for o in legacy_objects if o.get("geometry", {}).get("prst") == "custGeom"]
        pptx_polygons = [o["geometry"] for o in pptx_objects if o.get("geometry", {}).get("prst") == "custGeom"]
        self.assertEqual(legacy_polygons, pptx_polygons)
        self.assertTrue(legacy_polygons, "fixture must contain a polygon shape")

    def test_repeated_media_references_keep_one_part_per_reference(self):
        legacy_path, pptx_path, manifest_path = self._build_both("baseline-objects.json")
        # the fixture references photo_a.png twice and chart_b.png once
        self.assertEqual(len(project_pptx(pptx_path)["media_hash_multiset"]), 3)
        report = _run_validator(pptx_path, manifest_path)
        self.assertFalse(report["media_manifest_mismatch"], report)
        self.assertEqual(report["images"], 3)

    def test_validator_passes_both_builder_products(self):
        for name in EQUIVALENCE_FIXTURES:
            with self.subTest(fixture=name):
                legacy_path, pptx_path, manifest_path = self._build_both(name)
                for builder, path in (("legacy", legacy_path), ("pptx", pptx_path)):
                    with self.subTest(builder=builder):
                        report = _run_validator(path, manifest_path)
                        self.assertTrue(report["passed"], f"{builder}: {report}")

    def test_single_page_pptx_and_deck_page_are_isomorphic(self):
        workdir = Path(tempfile.mkdtemp(prefix="isomorph-"))
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        page_path = workdir / "page.pptx"
        deck_path = workdir / "deck.pptx"
        object_builder.write_pptx(manifest, page_path, manifest_path)
        object_builder.write_deck(
            {"slide": manifest["slide"]},
            [{"manifest": manifest, "manifest_path": manifest_path}],
            deck_path,
            [],
        )
        page_projection = project_pptx(page_path)["slides"][0]
        deck_projection = project_pptx(deck_path)["slides"][0]
        self.assertEqual(page_projection, deck_projection)

    def test_roundrect_adjustment_clamped_consistently(self):
        workdir = Path(tempfile.mkdtemp(prefix="adj-"))
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        # add the inch-path radius variant at build time only (the page contract
        # requires source_corner_radius_px for checked roundRect shapes)
        manifest["shapes"] = list(manifest["shapes"]) + [
            {"type": "roundRect", "box_px": [1250, 620, 220, 140], "radius": 0.35, "fill": "#F6D365", "stroke": "none", "z_index": 160}
        ]
        legacy_path = workdir / "legacy.pptx"
        pptx_path = workdir / "object.pptx"
        vendor_builder.write_pptx(manifest, legacy_path, manifest_path)
        object_builder.write_pptx(manifest, pptx_path, manifest_path)

        def adjustments(projection):
            return [
                o["geometry"]["adj"]
                for slide in projection["slides"]
                for o in slide["objects"]
                if o.get("geometry", {}).get("prst") == "roundRect"
            ]

        self.assertEqual(adjustments(project_pptx(legacy_path)), adjustments(project_pptx(pptx_path)))
        # px path (source_corner_radius_px) and inch path (radius) both resolve
        self.assertEqual(len(adjustments(project_pptx(pptx_path))), 2)


class NotesFreezeTest(unittest.TestCase):
    """F1-T7 用例 9 + F2-T2 语义：notes text 与 notes_xml 字节冻结。"""

    def _build_deck_pair(self, workdir: Path, notes_entries: list) -> tuple[Path, Path]:
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        second = dict(manifest)
        second["text_boxes"] = [{"box_px": [100, 80, 600, 120], "text": "第二页", "font_size": 24, "z_index": 300}]
        second_path = workdir / "page2.json"
        second_path.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
        entries = [
            {"manifest": manifest, "manifest_path": manifest_path},
            {"manifest": second, "manifest_path": second_path},
        ]
        legacy_path = workdir / "legacy-deck.pptx"
        pptx_path = workdir / "object-deck.pptx"
        vendor_builder.write_deck({"slide": manifest["slide"]}, entries, legacy_path, notes_entries)
        object_builder.write_deck({"slide": manifest["slide"]}, entries, pptx_path, notes_entries)
        return legacy_path, pptx_path

    def test_notes_text_and_frozen_bytes_hash_equal(self):
        workdir = Path(tempfile.mkdtemp(prefix="notes-"))
        frozen = workdir / "frozen_notes.xml"
        frozen.write_text(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
            ' xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            "<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>冻结字节 notes</a:t></a:r></a:p>"
            "</p:txBody></p:sp></p:spTree></p:cSld></p:notes>",
            encoding="utf-8",
        )
        notes_entries = [
            {"page_index": 1, "text": "第一页 notes line1\nline2"},
            {"page_index": 2, "text": "第二页 notes", "notes_xml": str(frozen)},
        ]
        legacy_path, pptx_path = self._build_deck_pair(workdir, notes_entries)
        _assert_projection_equal(self, project_pptx(legacy_path), project_pptx(pptx_path))
        # E26: frozen bytes are written back verbatim by the object builder
        with zipfile.ZipFile(pptx_path) as package:
            self.assertEqual(package.read("ppt/notesSlides/notesSlide2.xml"), frozen.read_bytes())
            # notes slides are numbered by page position, not creation order
            self.assertIn("ppt/notesSlides/notesSlide1.xml", package.namelist())

    def test_deck_without_notes_has_no_notes_parts(self):
        workdir = Path(tempfile.mkdtemp(prefix="nonotes-"))
        legacy_path, pptx_path = self._build_deck_pair(workdir, [])
        _assert_projection_equal(self, project_pptx(legacy_path), project_pptx(pptx_path))
        with zipfile.ZipFile(pptx_path) as package:
            self.assertEqual([n for n in package.namelist() if "notesSlide" in n], [])


class DeterminismTest(unittest.TestCase):
    """F1-T7 用例 10 / CI-2：canonical zip 重打包确定性。"""

    def _build(self, workdir: Path) -> bytes:
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        out_path = workdir / "out.pptx"
        object_builder.write_pptx(manifest, out_path, manifest_path)
        return out_path.read_bytes()

    def test_same_manifest_same_sha256_across_tz(self):
        first = self._build(Path(tempfile.mkdtemp(prefix="det1-")))
        original_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "Asia/Tokyo"
            time.tzset()
            second = self._build(Path(tempfile.mkdtemp(prefix="det2-")))
            os.environ["TZ"] = "UTC"
            time.tzset()
            third = self._build(Path(tempfile.mkdtemp(prefix="det3-")))
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
            time.tzset()
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(third).hexdigest())

    def test_repack_is_entry_ordered_and_epoch_stamped(self):
        workdir = Path(tempfile.mkdtemp(prefix="repack-"))
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        raw = workdir / "raw.pptx"
        object_builder.write_pptx(manifest, raw, manifest_path)
        canonical = deterministic_zip.canonical_bytes(raw.read_bytes())
        with zipfile.ZipFile(io.BytesIO(canonical)) as package:
            names = package.namelist()
            self.assertEqual(names[0], "[Content_Types].xml")
            self.assertEqual(names[1], "_rels/.rels")
            self.assertEqual(names[2:], sorted(names[2:]))
            for info in package.infolist():
                self.assertEqual(info.date_time, deterministic_zip.ZIP_EPOCH)
                self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)

    def test_legacy_product_still_validates_after_repack(self):
        workdir = Path(tempfile.mkdtemp(prefix="legrep-"))
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        legacy_path = workdir / "legacy.pptx"
        vendor_builder.write_pptx(manifest, legacy_path, manifest_path)
        repacked = workdir / "legacy-canonical.pptx"
        deterministic_zip.repack_zipstream(legacy_path.read_bytes(), repacked)
        report = _run_validator(repacked, manifest_path)
        self.assertTrue(report["passed"], report)


class PresetValidationTest(unittest.TestCase):
    """F1-T7 用例 7 负面：非法 preset 在 object builder build 期失败。"""

    def test_illegal_preset_raises_at_build_time(self):
        workdir = Path(tempfile.mkdtemp(prefix="preset-"))
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        manifest["shapes"] = [
            {"preset": "rounded-rectangle", "box_px": [50, 500, 300, 160], "fill": "#FFFFFF", "z_index": 100}
        ]
        with self.assertRaises(ValueError):
            object_builder.write_pptx(manifest, workdir / "bad.pptx", manifest_path)
        self.assertFalse((workdir / "bad.pptx").exists())

    def test_legacy_writes_bogus_preset_unchanged_current_behavior(self):
        workdir = Path(tempfile.mkdtemp(prefix="preset-legacy-"))
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        manifest["shapes"] = [
            {"preset": "rounded-rectangle", "box_px": [50, 500, 300, 160], "fill": "#FFFFFF", "z_index": 100}
        ]
        legacy_path = workdir / "legacy.pptx"
        vendor_builder.write_pptx(manifest, legacy_path, manifest_path)
        with zipfile.ZipFile(legacy_path) as package:
            slide = package.read("ppt/slides/slide1.xml").decode()
        self.assertIn('prst="rounded-rectangle"', slide)

    def test_unknown_dash_token_raises_at_build_time(self):
        workdir = Path(tempfile.mkdtemp(prefix="dash-"))
        manifest, manifest_path = _fixture_manifest_with_images("baseline-objects.json", workdir)
        manifest["shapes"] = [
            {"type": "line", "points_px": [80, 700, 700, 640], "stroke": "#333333", "dash": "sparkles", "z_index": 130}
        ]
        with self.assertRaises(ValueError):
            object_builder.write_pptx(manifest, workdir / "bad.pptx", manifest_path)


class TableObjectFaceTest(unittest.TestCase):
    """F1-T5：原生 tables[] 对象面（legacy builder 不消费该段，单独验证 pptx 面）。"""

    def _build_table_page(self, workdir: Path) -> tuple[Path, Path]:
        manifest = _load_fixture("tables-object-face.json")
        manifest_path = workdir / "tables-object-face.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        out_path = workdir / "tables.pptx"
        object_builder.write_pptx(manifest, out_path, manifest_path)
        return out_path, manifest_path

    def test_table_cells_columns_and_merge_project(self):
        out_path, _ = self._build_table_page(Path(tempfile.mkdtemp(prefix="tables-")))
        projection = project_pptx(out_path)
        tables = [o for o in projection["slides"][0]["objects"] if o["kind"] == "table"]
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(table["rows"][0], ["财务年度汇总", ""])
        self.assertEqual(table["rows"][1], ["季度营收", "42.8M"])
        self.assertEqual(table["grid"], [548640, 365760])  # 60/40 of 914400 EMU box width
        self.assertIsNotNone(table["off"])
        self.assertIsNotNone(table["ext"])

    def test_validator_required_text_covers_table_text(self):
        workdir = Path(tempfile.mkdtemp(prefix="tables-val-"))
        out_path, manifest_path = self._build_table_page(workdir)
        report = _run_validator(out_path, manifest_path)
        self.assertTrue(report["passed"], report)
        self.assertIn("季度营收", report["all_text"])

    def test_manifest_without_tables_unchanged_legacy_behavior(self):
        # schema is additive: dropping the tables section reproduces the shared baseline
        workdir = Path(tempfile.mkdtemp(prefix="tables-absent-"))
        manifest = _load_fixture("tables-object-face.json")
        manifest.pop("tables")
        manifest_path = workdir / "no-tables.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        legacy_path = workdir / "legacy.pptx"
        pptx_path = workdir / "object.pptx"
        vendor_builder.write_pptx(manifest, legacy_path, manifest_path)
        object_builder.write_pptx(manifest, pptx_path, manifest_path)
        _assert_projection_equal(self, project_pptx(legacy_path), project_pptx(pptx_path))


class ThemeDoubleSlotTest(unittest.TestCase):
    """F2-T1：theme1.xml 字体双槽 + role 继承 + legacy warning 不 fail。"""

    def _theme_typefaces(self, pptx_path: Path) -> dict:
        import re
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(pptx_path) as package:
            theme = package.read("ppt/theme/theme1.xml")
        root = ET.fromstring(theme)
        ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        result = {}
        for group in ("majorFont", "minorFont"):
            container = root.find(f".//{ns}fontScheme/{ns}{group}")
            result[group] = {
                tag: container.find(f"{ns}{tag}").get("typeface") for tag in ("latin", "ea", "cs")
            }
        return result

    def test_theme_double_slot_written_to_all_three_slots(self):
        workdir = Path(tempfile.mkdtemp(prefix="theme-"))
        manifest = _load_fixture("theme-double-slot.json")
        manifest_path = workdir / "theme.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        out_path = workdir / "theme.pptx"
        object_builder.write_pptx(manifest, out_path, manifest_path)
        slots = self._theme_typefaces(out_path)
        self.assertEqual(slots["majorFont"], {"latin": "Source Han Sans SC", "ea": "Source Han Sans SC", "cs": "Source Han Sans SC"})
        self.assertEqual(slots["minorFont"], {"latin": "Noto Sans SC", "ea": "Noto Sans SC", "cs": "Noto Sans SC"})

    def test_role_inheritance_and_explicit_font_override(self):
        workdir = Path(tempfile.mkdtemp(prefix="theme-role-"))
        manifest = _load_fixture("theme-double-slot.json")
        manifest_path = workdir / "theme.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        out_path = workdir / "theme.pptx"
        object_builder.write_pptx(manifest, out_path, manifest_path)
        runs = [
            run
            for slide in project_pptx(out_path)["slides"]
            for o in slide["objects"]
            if o["kind"] == "text"
            for paragraph in o["body"]["paragraphs"]
            for run in paragraph["runs"]
        ]
        by_text = {run["text"]: run for run in runs}
        self.assertEqual(by_text["主题双槽"]["font_latin"], "Source Han Sans SC")  # role=title
        self.assertEqual(by_text["正文字体"]["font_latin"], "Noto Sans SC")  # role=body
        self.assertEqual(by_text["显式字体"]["font_latin"], "Explicit Face")  # explicit font wins

    def test_manifest_without_theme_keeps_legacy_default_fonts(self):
        workdir = Path(tempfile.mkdtemp(prefix="theme-absent-"))
        manifest = _load_fixture("theme-double-slot.json")
        manifest.pop("theme")
        for box in manifest["text_boxes"]:
            box.pop("role", None)
            box.pop("font", None)
        manifest_path = workdir / "no-theme.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        legacy_path = workdir / "legacy.pptx"
        pptx_path = workdir / "object.pptx"
        vendor_builder.write_pptx(manifest, legacy_path, manifest_path)
        object_builder.write_pptx(manifest, pptx_path, manifest_path)
        _assert_projection_equal(self, project_pptx(legacy_path), project_pptx(pptx_path))
        runs = [run for o in project_pptx(pptx_path)["slides"][0]["objects"] if o["kind"] == "text" for p in o["body"]["paragraphs"] for run in p["runs"]]
        self.assertTrue(all(run["font_latin"] == "PingFang SC" for run in runs))

    def test_legacy_builder_with_theme_warns_but_builds(self):
        import contextlib

        from leo_ppt_generator.editable.adapter import _legacy_theme_warning

        workdir = Path(tempfile.mkdtemp(prefix="theme-legacy-"))
        manifest = _load_fixture("theme-double-slot.json")
        legacy_path = workdir / "legacy.pptx"
        vendor_builder.write_pptx(manifest, legacy_path, workdir / "m.json")  # builds despite theme
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            _legacy_theme_warning([{"manifest": manifest, "manifest_path": workdir / "m.json"}])
        self.assertIn("builder=legacy", stderr.getvalue())
        self.assertTrue(legacy_path.exists())


class BuilderSelectionTest(unittest.TestCase):
    """F1-T4：env 分派 + run 冻结优先 + 无效值 fail-closed 回默认。"""

    ENV = "LEO_EDITABLE_BUILDER"

    def setUp(self):
        self._original = os.environ.get(self.ENV)
        os.environ.pop(self.ENV, None)

    def tearDown(self):
        if self._original is not None:
            os.environ[self.ENV] = self._original
        else:
            os.environ.pop(self.ENV, None)

    def test_default_and_env_dispatch(self):
        from leo_ppt_generator.editable.adapter import _builder

        self.assertIs(_builder(), vendor_builder)
        os.environ[self.ENV] = "pptx"
        self.assertIs(_builder(), object_builder)
        os.environ[self.ENV] = "legacy"
        self.assertIs(_builder(), vendor_builder)

    def test_invalid_env_falls_back_to_default_legacy(self):
        from leo_ppt_generator.config import builder_selection

        for value in ("", "bogus", "PPTX "):
            with self.subTest(value=value):
                self.assertEqual(builder_selection.current(env={self.ENV: value}), "legacy")

    def test_run_frozen_field_wins_over_environment(self):
        from leo_ppt_generator.config import builder_selection

        frozen = {"id": "leo-ppt-generator/object-builder-1", "selection": "pptx"}
        self.assertEqual(builder_selection.current(env={self.ENV: "legacy"}, frozen=frozen), "pptx")
        self.assertIsNone(builder_selection.from_frozen(None))
        self.assertIsNone(builder_selection.from_frozen({"selection": "garbage"}))

    def test_finalize_rebuilds_with_frozen_builder(self):
        from PIL import Image

        from leo_ppt_generator.editable.adapter import EditableAdapter

        workdir = Path(tempfile.mkdtemp(prefix="freeze-"))
        source = workdir / "source.png"
        Image.new("RGB", (1600, 1200), (250, 250, 250)).save(source)
        os.environ[self.ENV] = "pptx"
        adapter = EditableAdapter(workdir / "run")
        adapter.prepare([source], worker_available=True)
        jobs = json.loads((workdir / "run" / "page_jobs.json").read_text())
        self.assertEqual(jobs["builder"]["selection"], "pptx")

        page = _record_single_page(adapter, workdir)
        self.assertEqual(page, "page_001")
        os.environ[self.ENV] = "legacy"  # environment flips after run creation
        result = adapter.finalize(workdir / "run" / "final" / "deck.pptx")
        with zipfile.ZipFile(result["pptx"]) as package:
            app = package.read("docProps/app.xml").decode()
        self.assertIn(object_builder.BUILDER_ID, app)


def _record_single_page(adapter, workdir: Path) -> str:
    """Build + validate + record page_001 through the real adapter gates."""
    manifest = {
        "schema_version": 1,
        "slide": {"width": 13.333, "height": 7.5},
        "source": {"width_px": 1600, "height_px": 1200},
        "text_inventory": [{"id": "t", "text": "Freeze Check"}],
        "visual_inventory": [],
        "background_strategy": {"mode": "native-or-script"},
        "quality_checks": {
            "font_size_calibrated": True,
            "visual_inventory_matched": True,
            "background_strategy_checked": True,
            "shape_corner_geometry_checked": True,
        },
        "text_boxes": [{"box_px": [100, 80, 600, 120], "text": "Freeze Check", "font_size": 32}],
        "images": [],
        "shapes": [],
        "asset_provenance": [],
    }
    page_dir = workdir / "run" / "work" / "page_001" / "agent"
    page_dir.mkdir(parents=True)
    manifest_path = page_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    builder = object_builder if os.environ.get("LEO_EDITABLE_BUILDER") == "pptx" else vendor_builder
    builder.write_pptx(manifest, page_dir / "page.pptx", manifest_path)
    report = _run_validator(page_dir / "page.pptx", manifest_path)
    (page_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    artifact = adapter.record(
        "page_001",
        page_dir / "page.pptx",
        page_dir / "validation.json",
        manifest_path,
        expected_revision=0,
        operation_id="test-op",
        notes="",
    )
    return artifact.page_id


class AssemblyGateSemanticsTest(unittest.TestCase):
    """X-6 交叉测试：清扫耗尽 × 缺页拒绝组装 × PARTIAL 不含未确认页。

    只以 manifest/状态文件（page_jobs.json / delivery 记录）断言，不依赖
    γ 的 sweep 实现细节：清扫耗尽的语义落点 = 存在未 record 的页时
    finalize 必须失败且不落任何 delivery/PARTIAL 产物。
    """

    ENV = "LEO_EDITABLE_BUILDER"

    def setUp(self):
        self._original = os.environ.get(self.ENV)
        os.environ.pop(self.ENV, None)

    def tearDown(self):
        if self._original is not None:
            os.environ[self.ENV] = self._original
        else:
            os.environ.pop(self.ENV, None)

    def test_missing_page_blocks_assembly_and_writes_no_partial_delivery(self):
        from PIL import Image

        from leo_ppt_generator.contracts import ContractError
        from leo_ppt_generator.editable.adapter import EditableAdapter

        workdir = Path(tempfile.mkdtemp(prefix="gate-"))
        sources = []
        for index in (1, 2):
            source = workdir / f"source{index}.png"
            Image.new("RGB", (1600, 1200), (240 + index, 240, 240)).save(source)
            sources.append(source)
        adapter = EditableAdapter(workdir / "run")
        adapter.prepare(sources, worker_available=True)

        # sweep exhaustion stand-in: page 1 recorded, page 2 still unrecorded
        _record_single_page(adapter, workdir)
        jobs = json.loads((workdir / "run" / "page_jobs.json").read_text())
        self.assertEqual([p["status"] for p in jobs["pages"]], ["recorded", "pending"])
        with self.assertRaises(ContractError):
            adapter.finalize(workdir / "run" / "final" / "deck.pptx")
        # no PARTIAL delivery may exist containing unconfirmed pages
        jobs = json.loads((workdir / "run" / "page_jobs.json").read_text())
        self.assertNotIn("delivery", jobs)
        self.assertFalse(list((workdir / "run" / "final").glob("*.pptx")))

    def test_confirmed_pages_only_enter_delivery(self):
        from PIL import Image

        from leo_ppt_generator.contracts import ContractError
        from leo_ppt_generator.editable.adapter import EditableAdapter

        workdir = Path(tempfile.mkdtemp(prefix="gate2-"))
        sources = []
        for index in (1, 2):
            source = workdir / f"source{index}.png"
            Image.new("RGB", (1600, 1200), (240, 240 + index, 240)).save(source)
            sources.append(source)
        adapter = EditableAdapter(workdir / "run")
        adapter.prepare(sources, worker_available=True)
        _record_single_page(adapter, workdir)
        # strict artifacts() rejects the unconfirmed page (缺页拒绝组装)
        with self.assertRaises(ContractError):
            adapter.artifacts()
        # allow_incomplete must not smuggle unconfirmed pages into assembly input
        self.assertEqual([a.page_id for a in adapter.artifacts(allow_incomplete=True)], ["page_001"])
        # after both pages are confirmed the delivery lists exactly those pages
        _record_second_page(adapter, workdir)
        result = adapter.finalize(workdir / "run" / "final" / "deck.pptx")
        self.assertEqual(result["page_count"], 2)
        self.assertEqual([p["page_id"] for p in result["pages"]], ["page_001", "page_002"])
        self.assertTrue(Path(result["pptx"]).is_file())


def _record_second_page(adapter, workdir: Path) -> None:
    """Record page_002 (same shape as page_001, distinct content)."""
    manifest = {
        "schema_version": 1,
        "slide": {"width": 13.333, "height": 7.5},
        "source": {"width_px": 1600, "height_px": 1200},
        "text_inventory": [{"id": "t", "text": "Second Page"}],
        "visual_inventory": [],
        "background_strategy": {"mode": "native-or-script"},
        "quality_checks": {
            "font_size_calibrated": True,
            "visual_inventory_matched": True,
            "background_strategy_checked": True,
            "shape_corner_geometry_checked": True,
        },
        "text_boxes": [{"box_px": [100, 80, 600, 120], "text": "Second Page", "font_size": 32}],
        "images": [],
        "shapes": [],
        "asset_provenance": [],
    }
    page_dir = workdir / "run" / "work" / "page_002" / "agent"
    page_dir.mkdir(parents=True)
    manifest_path = page_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    vendor_builder.write_pptx(manifest, page_dir / "page.pptx", manifest_path)
    report = _run_validator(page_dir / "page.pptx", manifest_path)
    (page_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    jobs = json.loads((workdir / "run" / "page_jobs.json").read_text())
    adapter.record(
        "page_002",
        page_dir / "page.pptx",
        page_dir / "validation.json",
        manifest_path,
        expected_revision=jobs["revision"],
        operation_id="test-op-2",
        notes="",
    )


if __name__ == "__main__":
    unittest.main()
