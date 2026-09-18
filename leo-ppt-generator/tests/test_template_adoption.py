"""U8/F2：模板采用信任边界——数据/代码分离、包内自报无效、未审阅不执行。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "style_pack.py"
PYTHON = SKILL / "runtime" / ".venv" / "bin" / "python"


def _run(*args: str, home: Path | None = None) -> subprocess.CompletedProcess:
    command = [str(PYTHON), str(SCRIPT), *args]
    if home is not None:
        command += ["--home", str(home)]
    return subprocess.run(command, capture_output=True, text=True, cwd=SKILL)


def _make_pack(tmp: Path, *, name: str = "示例导入风", with_code: bool = True,
               trusted_claim: bool = False, builtin_claim: bool = False) -> Path:
    pack = tmp / "pack"
    pack.mkdir()
    brief = {
        "schema_version": 2, "entity": "style-brief",
        "asset_id": f"builtin:style:{name}" if builtin_claim else f"user:style:{name}",
        "name": name, "lifecycle": "draft",
        "source": {"origin": "user-imported"},
        "taxonomy": {"families": ["未分类"]},
        "visual_language": {"direction": "x" * 10},
        "bindings": {},
        "content_review": {"reviewed": False, "disposition": "draft"},
    }
    files = {"brief.json": json.dumps(brief, ensure_ascii=False).encode()}
    if with_code:
        files["page.html"] = b"<html><script>alert(1)</script></html>"
    manifest = {
        "kind": "leo-style-pack", "schema_version": 2,
        "asset_id": f"builtin:style:{name}" if builtin_claim else f"user:style:{name}",
        "name": name, "lifecycle": "draft",
        "files": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
    }
    if trusted_claim:
        manifest["trusted"] = True
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False).encode()
    for file_name, body in files.items():
        (pack / file_name).write_bytes(body)
    return pack


class TemplateAdoptionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="leo-pack-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()

    def test_data_imports_and_code_quarantines(self) -> None:
        pack = _make_pack(self.tmp)
        result = _run("import", str(pack), home=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        library = self.home / "template-library"
        self.assertTrue((library / "canonical/styles/示例导入风/brief.json").is_file())
        quarantined = library / "reference/candidates/示例导入风/page.html"
        self.assertTrue(quarantined.is_file(), "可执行内容必须默认隔离")
        # 导入的数据实体不得位于 canonical 的执行面。
        self.assertFalse(list((library / "canonical/styles/示例导入风").glob("*.html")))

    def test_package_trusted_claim_is_invalid(self) -> None:
        pack = _make_pack(self.tmp, trusted_claim=True)
        result = _run("import", str(pack), home=self.home)
        self.assertEqual(result.returncode, 2)
        self.assertIn("pack_trusted_claim_invalid", result.stderr)

    def test_builtin_identity_impersonation_rejected(self) -> None:
        pack = _make_pack(self.tmp, builtin_claim=True)
        result = _run("import", str(pack), home=self.home)
        self.assertEqual(result.returncode, 2)
        self.assertIn("builtin", result.stderr)

    def test_hash_mismatch_rejected(self) -> None:
        pack = _make_pack(self.tmp)
        (pack / "brief.json").write_text("{}", encoding="utf-8")
        result = _run("import", str(pack), home=self.home)
        self.assertEqual(result.returncode, 2)
        self.assertIn("hash", result.stderr)

    def test_adoption_requires_reviewer_and_binds_digests(self) -> None:
        pack = _make_pack(self.tmp)
        self.assertEqual(_run("import", str(pack), home=self.home).returncode, 0)
        result = _run("adopt", str(pack), "--reviewed-by", "维护者甲",
                      "--basis", "逐行审阅 page.html，无外发与脚本执行风险",
                      home=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        trust_dir = self.home / "template-library/governance/trust"
        records = list(trust_dir.glob("*.json"))
        self.assertEqual(len(records), 1)
        record = json.loads(records[0].read_text(encoding="utf-8"))
        self.assertEqual(record["kind"], "executable-adoption")
        self.assertEqual(record["review"]["reviewed_by"], "维护者甲")
        self.assertTrue(any(k.endswith("page.html") for k in record["code_digests"]))
        # 绑定 digest 与实际文件一致。
        actual = hashlib.sha256(
            (self.home / "template-library/reference/candidates/示例导入风/page.html").read_bytes()).hexdigest()
        self.assertEqual(record["code_digests"]["示例导入风/page.html"], actual)

    def test_adoption_schema_validates(self) -> None:
        from jsonschema import Draft7Validator

        schema = json.loads((SKILL / "template-library/governance/schemas/"
                             "executable-adoption-v1.schema.json").read_text())
        Draft7Validator.check_schema(schema)
        # 包内自报形态（review.reviewed_by 缺失）不得通过。
        bad = {"kind": "executable-adoption", "schema_version": 1,
               "adoption_id": "x", "template_asset_id": "user:template:x",
               "code_digests": {"a.html": "0" * 64},
               "review": {"basis": "self claimed"}}
        self.assertTrue(list(Draft7Validator(schema).iter_errors(bad)))


if __name__ == "__main__":
    unittest.main()
