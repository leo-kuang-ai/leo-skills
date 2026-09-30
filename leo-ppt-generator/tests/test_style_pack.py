"""风格包导出导入测试（R-33 → U8 style_pack v2：新库数据/代码分离）。

v2 合同（scripts/style_pack.py）：
  - export 从新库导出 brief.json + manifest（确定性 sha256）；
  - import 校验 manifest v2 与文件 hash；包内自报 trusted / builtin 身份
    冒充一律拒收（F2）；可执行内容（html/js/css/svg）默认进用户库
    reference/candidates 隔离区，数据实体导入 canonical 并改写为
    user:style: 身份 + user-imported 来源；
  - adopt 在用户库 governance/trust 落 executable-adoption-v1 记录
    （绑定代码 digest + 实际审阅来源）。

v1 旧树 pack（--root/brief.md/lint 拒收/同名冲突/同板指纹）已随旧树退役：
元数据拒收面的新等价物是 F2 身份冒充/信任声明拒收。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SCRIPT_PATH = SCRIPTS_DIR / "style_pack.py"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True, text=True,
    )


def make_pack(base: Path, *, name: str = "测试导入风",
              include_html: bool = True) -> Path:
    pack = base / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    brief = {
        "schema_version": 2, "entity": "style-brief",
        "asset_id": "user:style:test-import", "name": name,
        "lifecycle": "draft", "taxonomy": {"families": ["测试族"]},
        "visual_language": {"direction": "test direction for import"},
        "bindings": {},
    }
    (pack / "brief.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = {"brief.json": _sha256(pack / "brief.json")}
    if include_html:
        (pack / "page.html").write_text("<p>executable</p>\n", encoding="utf-8")
        files["page.html"] = _sha256(pack / "page.html")
    (pack / "manifest.json").write_text(json.dumps({
        "kind": "leo-style-pack", "schema_version": 2,
        "asset_id": "user:style:test-import", "name": name,
        "lifecycle": "draft", "files": files,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pack


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExportBehavior(unittest.TestCase):
    def test_export_writes_brief_and_manifest_with_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            result = run_cli("export", "清爽专业风", "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "leo-style-pack")
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["asset_id"], "builtin:style:clean-professional")
            self.assertEqual(
                manifest["files"]["brief.json"], _sha256(out / "brief.json"))
            # 无时间戳：重复导出逐字节一致（确定性）。
            out2 = Path(tmp) / "pack2"
            run_cli("export", "清爽专业风", "--out", str(out2))
            self.assertEqual((out / "manifest.json").read_bytes(),
                             (out2 / "manifest.json").read_bytes())

    def test_export_unknown_style_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("export", "不存在的风格",
                             "--out", str(Path(tmp) / "p"))
            self.assertNotEqual(result.returncode, 0)


class ImportBehavior(unittest.TestCase):
    def test_import_rejects_maintenance_before_writing_any_pack_bytes(self):
        from leo_ppt_generator.library_migration import locked_publication
        from leo_ppt_generator.library_migration import MigrationError
        from leo_ppt_generator.styles import save_style
        with tempfile.TemporaryDirectory() as tmp:
            delivery = Path(tmp).resolve()
            home = delivery / "leo-ppt-generator"
            pack = make_pack(delivery)
            library = home / "template-library"
            with locked_publication(delivery, plan_digest="a" * 64):
                before = {p.relative_to(library).as_posix(): p.read_bytes() for p in library.rglob("*") if p.is_file()}
                result = run_cli("import", str(pack), "--home", str(home))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("library_in_maintenance", result.stderr)
                with self.assertRaisesRegex(MigrationError, "library_in_maintenance"):
                    save_style("测试", '{"visual_direction": "test"}', home=home)
                self.assertEqual({p.relative_to(library).as_posix(): p.read_bytes() for p in library.rglob("*") if p.is_file()}, before)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.pack = make_pack(self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def _import(self, *extra: str):
        return run_cli("import", str(self.pack), "--home", str(self.home), *extra)

    def test_import_data_entity_into_user_canonical_with_user_identity(self):
        result = self._import()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        brief = json.loads((self.home / "template-library" / "canonical"
                            / "visual/styles" / "test-import" / "brief.json").read_text())
        self.assertEqual(brief["asset_id"], "user:style:test-import")
        self.assertEqual(brief["source"]["origin"], "user-imported")

    def test_import_rejects_wrong_kind_theme_and_layout_binding_before_writes(self):
        brief_path = self.pack / "brief.json"
        brief = json.loads(brief_path.read_text())
        second = {**brief, "asset_id": "user:style:second", "name": "第二个风格"}
        (self.pack / "second.json").write_text(json.dumps(second))
        for binding in ({"theme_default": second["asset_id"]},
                        {"layout_routes": [{"page_type": "content", "preferred": [second["asset_id"]]}]}):
            with self.subTest(binding=binding):
                brief["bindings"] = binding
                brief_path.write_text(json.dumps(brief))
                manifest_path = self.pack / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                manifest["files"].update({"brief.json": _sha256(brief_path), "second.json": _sha256(self.pack / "second.json")})
                manifest_path.write_text(json.dumps(manifest))
                result = self._import()
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse((self.home / "template-library" / "canonical").exists())

    def test_import_quarantines_executable_content(self):
        result = self._import()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        candidate = (self.home / "template-library" / "reference"
                     / "candidates" / "测试导入风" / "page.html")
        self.assertTrue(candidate.is_file())
        self.assertIn("quarantined", result.stdout)
        # 可执行内容绝不进 canonical。
        self.assertFalse(
            any((self.home / "template-library" / "canonical").rglob("page.html")))

    def test_import_rejects_path_escape_before_writing_anything(self):
        manifest = json.loads((self.pack / "manifest.json").read_text())
        manifest["files"]["../escape.json"] = manifest["files"].pop("brief.json")
        (self.pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = self._import()
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.home / "template-library").exists())

    def test_import_preflights_all_files_and_leaves_no_partial_entity(self):
        bad = self.pack / "bad.json"
        bad.write_text("{broken", encoding="utf-8")
        manifest = json.loads((self.pack / "manifest.json").read_text())
        manifest["files"]["bad.json"] = _sha256(bad)
        (self.pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = self._import()
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.home / "template-library" / "canonical").exists())

    def test_import_rejects_absolute_name_duplicate_identity_and_missing_dependency(self):
        original = (self.pack / "manifest.json").read_text()
        for change in ("absolute", "slug", "duplicate", "dependency"):
            with self.subTest(change=change):
                manifest = json.loads(original)
                brief = json.loads((self.pack / "brief.json").read_text())
                if change == "absolute":
                    manifest["files"][str(self.pack / "brief.json")] = manifest["files"].pop("brief.json")
                elif change == "slug":
                    manifest["asset_id"] = "user:style:../../escape"
                elif change == "duplicate":
                    (self.pack / "duplicate.json").write_text(json.dumps(brief))
                    manifest["files"]["duplicate.json"] = _sha256(self.pack / "duplicate.json")
                else:
                    brief["bindings"] = {"theme": "user:theme:missing"}
                    (self.pack / "brief.json").write_text(json.dumps(brief))
                    manifest["files"]["brief.json"] = _sha256(self.pack / "brief.json")
                (self.pack / "manifest.json").write_text(json.dumps(manifest))
                result = self._import()
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse((self.home / "template-library").exists())

    def test_import_rejects_source_and_target_symlinks_without_outside_writes(self):
        outside = self.base / "outside"
        outside.mkdir()
        source = self.pack / "page.html"
        original = source.read_bytes()
        (outside / "page.html").write_bytes(original)
        source.unlink()
        source.symlink_to(outside / "page.html")
        self.assertEqual(self._import().returncode, 2)
        source.unlink()
        source.write_bytes(original)
        library = self.home / "template-library"
        library.mkdir(parents=True)
        (library / "canonical").symlink_to(outside, target_is_directory=True)
        self.assertEqual(self._import().returncode, 2)
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ["page.html"])

    def test_import_rolls_back_if_cas_replaces_then_reports_postwrite_failure(self):
        import style_pack
        from unittest.mock import patch
        from leo_ppt_generator.library_migration import compare_and_swap_file
        calls = []
        def replace_then_fail(root, relative, **kwargs):
            calls.append(relative)
            result = compare_and_swap_file(root, relative, **kwargs)
            if len(calls) == 2:
                raise OSError("postwrite verification failed")
            return result
        with patch("leo_ppt_generator.library_migration.compare_and_swap_file", side_effect=replace_then_fail):
            self.assertEqual(style_pack.cmd_import(self.pack, self.home), 2)
        library = self.home / "template-library"
        self.assertFalse(any(p.is_file() for p in (library / "canonical").rglob("*")))
        self.assertFalse(any(p.is_file() for p in (library / "reference").rglob("*")))

    def test_import_is_discoverable_through_actual_v2_user_resolver(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        from leo_ppt_generator.template_catalog import LibraryContext, read_catalog
        result = self._import()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        library = (self.home / "template-library").resolve()
        registry = read_catalog(LibraryContext(library))
        self.assertEqual(registry["entities"][0]["asset_id"], "user:style:test-import")
        resolved = AssetResolver(home=self.home.resolve()).resolve("user:style:test-import")
        self.assertEqual(resolved["data"]["name"], "测试导入风")
        self.assertEqual(resolved["relative_path"], "canonical/visual/styles/test-import/brief.json")

    def test_fresh_library_contains_only_required_governance(self):
        self.assertEqual(self._import().returncode, 0)
        governance = self.home / "template-library/governance"
        self.assertEqual({p.relative_to(governance).as_posix() for p in governance.rglob("*") if p.is_file()}, {
            "rules/asset-locations-v2.json", "schemas/style-brief-v2.schema.json",
            "schemas/asset-common.schema.json", "schemas/executable-adoption-v1.schema.json"})

    def test_second_pack_preserves_existing_v2_assets_and_catalog(self):
        from leo_ppt_generator.asset_resolver import AssetResolver
        self.assertEqual(self._import().returncode, 0)
        library = (self.home / "template-library").resolve()
        first = library / "canonical/visual/styles/test-import/brief.json"
        before = first.read_bytes()
        brief = json.loads((self.pack / "brief.json").read_text())
        brief.update(asset_id="user:style:second", name="第二个风格")
        (self.pack / "brief.json").write_text(json.dumps(brief))
        manifest = json.loads((self.pack / "manifest.json").read_text())
        manifest.update(asset_id=brief["asset_id"], name=brief["name"])
        manifest["files"]["brief.json"] = _sha256(self.pack / "brief.json")
        (self.pack / "manifest.json").write_text(json.dumps(manifest))
        result = self._import()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(first.read_bytes(), before)
        resolver = AssetResolver(home=self.home.resolve())
        self.assertIsNotNone(resolver.resolve("user:style:test-import"))
        self.assertIsNotNone(resolver.resolve("user:style:second"))

    def test_v1_library_requires_migration_without_writing(self):
        library = self.home / "template-library"
        library.mkdir(parents=True)
        (library / "library.json").write_text(json.dumps({"schema_version": 1, "kind": "template-library", "library_id": "user", "protocol": {"resolver": "asset_resolver/v1"}}))
        before = (library / "library.json").read_bytes()
        result = self._import()
        self.assertEqual(result.returncode, 2)
        self.assertIn("pack_library_migration_required", result.stderr)
        self.assertEqual((library / "library.json").read_bytes(), before)
        self.assertFalse((library / "canonical").exists())

    def test_pointer_postreplace_failure_restores_entire_existing_library(self):
        import style_pack
        from unittest.mock import patch
        from leo_ppt_generator.library_migration import compare_and_swap_file
        self.assertEqual(self._import().returncode, 0)
        library = (self.home / "template-library").resolve()
        before = {p.relative_to(library).as_posix(): p.read_bytes() for p in library.rglob("*") if p.is_file()}
        # 第二个真实包产生新 catalog；故障发生在 current 的实际替换之后。
        brief = json.loads((self.pack / "brief.json").read_text())
        brief.update(asset_id="user:style:second", name="第二个风格")
        (self.pack / "brief.json").write_text(json.dumps(brief))
        manifest = json.loads((self.pack / "manifest.json").read_text())
        manifest.update(asset_id=brief["asset_id"], name=brief["name"])
        manifest["files"]["brief.json"] = _sha256(self.pack / "brief.json")
        (self.pack / "manifest.json").write_text(json.dumps(manifest))
        failed = False
        def postreplace(root, relative, **kwargs):
            nonlocal failed
            result = compare_and_swap_file(root, relative, **kwargs)
            if relative == "catalog/current.json" and not failed:
                failed = True
                raise OSError("pointer postreplace failure")
            return result
        with patch("leo_ppt_generator.library_migration.compare_and_swap_file", side_effect=postreplace):
            self.assertEqual(style_pack.cmd_import(self.pack, self.home), 2)
        self.assertTrue(failed)
        after = {p.relative_to(library).as_posix(): p.read_bytes() for p in library.rglob("*") if p.is_file()}
        self.assertEqual(after, before)
        self.assertEqual(self._import().returncode, 0)

    def test_catalog_failure_preserves_external_file_and_can_retry_after_rollback(self):
        import style_pack
        from unittest.mock import patch
        from leo_ppt_generator.template_catalog import build_catalog
        library = (self.home / "template-library").resolve()
        def external_then_fail(root):
            (root / "catalog").mkdir(exist_ok=True)
            (root / "catalog/external.txt").write_text("external owner")
            raise OSError("catalog build failed")
        with patch("leo_ppt_generator.template_catalog.build_catalog", side_effect=external_then_fail):
            self.assertEqual(style_pack.cmd_import(self.pack, self.home), 2)
        self.assertEqual((library / "catalog/external.txt").read_text(), "external owner")
        self.assertFalse((library / "library.json").exists())
        self.assertFalse(list((library / "canonical").rglob("brief.json")))
        # 外部文件仍存在时不可将未知树纳入新库。
        self.assertEqual(self._import().returncode, 2)

    def test_catalog_pointer_failure_on_new_library_rolls_back_and_retry_succeeds(self):
        import style_pack
        from unittest.mock import patch
        from leo_ppt_generator.library_migration import compare_and_swap_file
        def pointer_fail(root, relative, **kwargs):
            if relative == "catalog/current.json":
                raise OSError("pointer failed")
            return compare_and_swap_file(root, relative, **kwargs)
        with patch("leo_ppt_generator.library_migration.compare_and_swap_file", side_effect=pointer_fail):
            self.assertEqual(style_pack.cmd_import(self.pack, self.home), 2)
        library = self.home / "template-library"
        self.assertFalse((library / "library.json").exists())
        self.assertFalse(list((library / "catalog").rglob("*.json")))
        self.assertEqual(self._import().returncode, 0)

    def test_rollback_never_removes_external_drift_of_a_written_asset(self):
        import style_pack
        from unittest.mock import patch
        from leo_ppt_generator.template_catalog import build_catalog
        library = (self.home / "template-library").resolve()
        relative = "canonical/visual/styles/test-import/brief.json"
        def drift_then_fail(root):
            (root / relative).write_text("external edit")
            raise OSError("failure after external edit")
        with patch("leo_ppt_generator.template_catalog.build_catalog", side_effect=drift_then_fail):
            self.assertEqual(style_pack.cmd_import(self.pack, self.home), 2)
        self.assertEqual((library / relative).read_text(), "external edit")

    def test_manifest_name_and_lifecycle_must_match_primary_brief(self):
        manifest = json.loads((self.pack / "manifest.json").read_text())
        for key, value in (("name", "另一个风格"), ("lifecycle", "reference")):
            changed = {**manifest, key: value}
            (self.pack / "manifest.json").write_text(json.dumps(changed))
            result = self._import()
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("pack_manifest_entity_mismatch", result.stderr)

    def test_import_rolls_back_earlier_writes_on_real_late_io_failure(self):
        import style_pack
        from unittest.mock import patch
        from leo_ppt_generator.library_migration import compare_and_swap_file
        library = (self.home / "template-library").resolve()
        calls = []
        def write_then_fail(root, relative, **kwargs):
            calls.append(relative)
            if len(calls) == 2:
                raise OSError("disk write failed")
            return compare_and_swap_file(root, relative, **kwargs)
        with patch("leo_ppt_generator.library_migration.compare_and_swap_file", side_effect=write_then_fail):
            self.assertEqual(style_pack.cmd_import(self.pack, self.home), 2)
        self.assertEqual(len(calls), 2)
        self.assertFalse((library / "canonical/styles/test-import/brief.json").exists())
        self.assertFalse((library / "reference/candidates/测试导入风/page.html").exists())

    def test_import_rejects_existing_identity_without_overwrite(self):
        first = self._import()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        target = (self.home / "template-library" / "canonical" / "visual/styles"
                  / "test-import" / "brief.json")
        original = target.read_bytes()
        second = self._import()
        self.assertEqual(second.returncode, 2)
        self.assertEqual(target.read_bytes(), original)

    def test_import_rejects_builtin_identity_impersonation(self):
        # F2：包内自报 builtin 身份不可由导入包冒充（v1 元数据拒收面的
        # 新等价负例）。
        manifest = json.loads((self.pack / "manifest.json").read_text())
        manifest["asset_id"] = "builtin:style:clean-professional"
        (self.pack / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        result = self._import()
        self.assertEqual(result.returncode, 2)
        self.assertIn("冒充", result.stderr)
        self.assertFalse((self.home / "template-library").exists())

    def test_import_rejects_self_declared_trust(self):
        manifest = json.loads((self.pack / "manifest.json").read_text())
        manifest["trusted"] = True
        (self.pack / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        result = self._import()
        self.assertEqual(result.returncode, 2)
        self.assertIn("信任声明无效", result.stderr)

    def test_import_missing_manifest_rejected(self):
        (self.pack / "manifest.json").unlink()
        result = self._import()
        self.assertEqual(result.returncode, 2)

    def test_import_non_v2_pack_rejected(self):
        manifest = json.loads((self.pack / "manifest.json").read_text())
        manifest["schema_version"] = 1
        (self.pack / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        result = self._import()
        self.assertEqual(result.returncode, 2)

    def test_import_declared_file_missing_or_corrupt_rejected(self):
        (self.pack / "page.html").write_text("<p>tampered</p>\n", encoding="utf-8")
        result = self._import()
        self.assertEqual(result.returncode, 2)
        self.assertIn("hash", result.stderr)
        # 被篡改的可执行内容绝不落入隔离区。
        self.assertFalse(
            any((self.home / "template-library" / "reference").rglob("page.html"))
            if (self.home / "template-library" / "reference").is_dir() else False)


class AdoptBehavior(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.pack = make_pack(self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def test_adopt_records_code_digests_and_review_provenance(self):
        run_cli("import", str(self.pack), "--home", str(self.home))
        result = run_cli("adopt", str(self.pack), "--reviewed-by", "维护者甲",
                         "--basis", "人工审阅 page.html", "--home", str(self.home))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        trust_dir = self.home / "template-library" / "governance" / "trust"
        records = list(trust_dir.glob("adopt-*.json"))
        self.assertEqual(len(records), 1)
        record = json.loads(records[0].read_text(encoding="utf-8"))
        self.assertEqual(record["kind"], "executable-adoption")
        self.assertEqual(record["review"],
                         {"reviewed_by": "维护者甲", "basis": "人工审阅 page.html"})
        self.assertEqual(sorted(record["code_digests"]),
                         ["测试导入风/page.html"])
        self.assertEqual(record["code_digests"]["测试导入风/page.html"],
                         _sha256(self.pack / "page.html"))

    def test_adoption_republishes_readable_catalog_and_is_idempotent(self):
        from leo_ppt_generator.template_catalog import LibraryContext, read_catalog
        self.assertEqual(run_cli("import", str(self.pack), "--home", str(self.home)).returncode, 0)
        library = (self.home / "template-library").resolve()
        before = read_catalog(LibraryContext(library))["asset_generation"]
        args = ("adopt", str(self.pack), "--reviewed-by", "维护者甲", "--basis", "人工审阅 page.html", "--home", str(self.home))
        first = run_cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        after = read_catalog(LibraryContext(library))
        self.assertEqual(after["asset_generation"], before)
        pointer = (library / "catalog/current.json").read_bytes()
        second = run_cli(*args)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('"idempotent": true', second.stdout)
        self.assertEqual((library / "catalog/current.json").read_bytes(), pointer)

    def test_adopt_without_candidates_rejected(self):
        result = run_cli("adopt", str(self.pack), "--reviewed-by", "x",
                         "--basis", "y", "--home", str(self.home))
        self.assertEqual(result.returncode, 2)

    def test_adopt_only_binds_requested_pack_and_refuses_changed_quarantine(self):
        self.assertEqual(run_cli("import", str(self.pack), "--home", str(self.home)).returncode, 0)
        candidates = self.home / "template-library/reference/candidates"
        other = candidates / "other/page.html"
        other.parent.mkdir()
        other.write_text("other code")
        result = run_cli("adopt", str(self.pack), "--reviewed-by", "维护者甲",
                         "--basis", "人工审阅 page.html", "--home", str(self.home))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        trust = self.home / "template-library/governance/trust"
        record = json.loads(next(trust.glob("*.json")).read_text())
        self.assertEqual(sorted(record["code_digests"]), ["测试导入风/page.html"])
        before = {p.name: p.read_bytes() for p in trust.iterdir()}
        (candidates / "测试导入风/page.html").write_text("changed code")
        result = run_cli("adopt", str(self.pack), "--reviewed-by", "维护者甲",
                         "--basis", "人工审阅 page.html", "--home", str(self.home))
        self.assertEqual(result.returncode, 2)
        self.assertEqual({p.name: p.read_bytes() for p in trust.iterdir()}, before)

    def test_adopt_rejects_symlink_and_invalid_review(self):
        self.assertEqual(run_cli("import", str(self.pack), "--home", str(self.home)).returncode, 0)
        target = self.home / "template-library/reference/candidates/测试导入风/page.html"
        target.unlink()
        target.symlink_to(self.pack / "page.html")
        result = run_cli("adopt", str(self.pack), "--reviewed-by", "维护者甲",
                         "--basis", "人工审阅 page.html", "--home", str(self.home))
        self.assertEqual(result.returncode, 2)
        target.unlink()
        target.write_bytes((self.pack / "page.html").read_bytes())
        result = run_cli("adopt", str(self.pack), "--reviewed-by", "x",
                         "--basis", "y", "--home", str(self.home))
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.home / "template-library/governance/trust").exists())


if __name__ == "__main__":
    unittest.main()
