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
                            / "styles" / "test-import" / "brief.json").read_text())
        self.assertEqual(brief["asset_id"], "user:style:test-import")
        self.assertEqual(brief["source"]["origin"], "user-imported")

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

    def test_adopt_without_candidates_rejected(self):
        result = run_cli("adopt", str(self.pack), "--reviewed-by", "x",
                         "--basis", "y", "--home", str(self.home))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
