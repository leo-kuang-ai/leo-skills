#!/usr/bin/env python3
"""check_sensitive_text.py unit tests (R-53): phone/ID detection with
checksum gating, masking discipline (full values never echoed), custom
glossary, profile/strict tiers, directory recursion, determinism, exit codes.

The hardcoded valid ID 11010519491231002X checksum was verified against
GB 11643-1999 independently of the script under test.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_sensitive_text.py"

_spec = importlib.util.spec_from_file_location("check_sensitive_text", SCRIPT)
check_sensitive_text = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_sensitive_text)

VALID_ID = "11010519491231002X"
VALID_ID_MASKED = "11**************2X"
# Same body with a wrong check digit.
INVALID_ID = "110105194912310021"
PHONE = "13812345678"
PHONE_MASKED = "138****5678"


def _run(args, expect_ok=True):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )
    if expect_ok and result.returncode != 0:
        raise AssertionError(
            f"expected exit 0, got {result.returncode}: {result.stderr}")
    return result


class CheckSensitiveTextTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def json_run(self, *args):
        result = _run(list(args) + ["--json"])
        return json.loads(result.stdout)

    # 1. Phone hit: file/line/column position and exact masked format.
    def test_phone_hit_position_and_mask(self):
        path = self.write("a.md", "前文\n请联系 13812345678 或邮件\n后文\n")
        payload = self.json_run(path)
        self.assertEqual(payload["candidate_count"], 1)
        hit = payload["results"][0]["hits"][0]
        self.assertEqual(hit["kind"], "phone")
        self.assertEqual(hit["masked"], PHONE_MASKED)
        self.assertEqual(hit["line"], 2)
        # Column counts characters before the match ("请联系 " = 4 chars).
        self.assertEqual(hit["column"], 5)

    # 2. Phones inside longer digit runs must not match.
    def test_phone_embedded_in_longer_digits_not_matched(self):
        path = self.write("b.md", f"订单号 {PHONE}9 与卡号 62{PHONE} 均非手机号\n")
        payload = self.json_run(path)
        self.assertEqual(payload["candidate_count"], 0)

    # 3. Valid-checksum ID detected and masked head-2/tail-2, same length.
    def test_valid_idcard_detected_and_masked(self):
        path = self.write("c.md", f"证件 {VALID_ID} 登记\n")
        payload = self.json_run(path)
        hits = payload["results"][0]["hits"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["kind"], "idcard")
        self.assertEqual(hits[0]["checksum"], "valid")
        self.assertEqual(hits[0]["masked"], VALID_ID_MASKED)
        self.assertEqual(len(hits[0]["masked"]), 18)

    # 4. Checksum-failing ID is suppressed under the internal profile.
    def test_invalid_checksum_id_suppressed_by_default(self):
        path = self.write("d.md", f"证件 {INVALID_ID} 登记\n")
        payload = self.json_run(path)
        self.assertEqual(payload["candidate_count"], 0)

    # 5. confidential --strict keeps checksum-failing IDs as low confidence.
    def test_strict_confidential_reports_invalid_id(self):
        path = self.write("e.md", f"证件 {INVALID_ID} 登记\n")
        payload = self.json_run(path, "--profile", "confidential", "--strict")
        hits = payload["results"][0]["hits"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["confidence"], "low")
        self.assertEqual(hits[0]["checksum"], "invalid")

    # 6. --strict under internal profile is a usage error (exit 2).
    def test_strict_rejected_under_internal_profile(self):
        path = self.write("f.md", "x\n")
        result = _run([path, "--strict"], expect_ok=False)
        self.assertEqual(result.returncode, 2)

    # 7. Custom glossary hit with reason, case-insensitive.
    def test_custom_terms_hit_with_reason(self):
        path = self.write("g.md", "本项目代号 ProjectAtlas 已立项\n")
        terms = self.write("terms.txt", "# 内部代号\nprojectatlas|内部项目代号\n")
        payload = self.json_run(path, "--custom-terms", terms)
        hits = payload["results"][0]["hits"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["kind"], "term")
        self.assertEqual(hits[0]["reason"], "内部项目代号")
        self.assertTrue(hits[0]["masked"].startswith("Pr"))
        self.assertNotIn("ProjectAtlas", json.dumps(payload, ensure_ascii=False))

    # 8. No hits: zero candidates, exit 0, two-layer note still present.
    def test_no_hits_zero_candidates_exit_zero(self):
        path = self.write("h.md", "普通内容,无敏感词。\n")
        result = _run([path])
        self.assertEqual(result.returncode, 0)
        self.assertIn("候选 0 处", result.stdout)
        payload = self.json_run(path)
        self.assertEqual(payload["candidate_count"], 0)
        self.assertIn("候选", payload["note"])

    # 9. Directory recursion: nested .md/.txt scanned, other extensions skipped.
    def test_directory_recursion_and_extension_filter(self):
        self.write("sub/inner.txt", f"电话 {PHONE}\n")
        self.write("sub/deep/note.md", f"证件 {VALID_ID}\n")
        self.write("sub/blob.bin", f"phone {PHONE}\n")
        payload = self.json_run(self.root)
        self.assertEqual(payload["files_scanned"], 2)
        self.assertEqual(payload["candidate_count"], 2)
        files = {r["file"] for r in payload["results"]}
        self.assertFalse(any(f.endswith(".bin") for f in files))

    # 10. Masking discipline: full sensitive values never appear in output.
    def test_full_values_never_leaked(self):
        path = self.write("i.md", f"手机 {PHONE},证件 {VALID_ID}\n")
        result = _run([path])
        combined = result.stdout + result.stderr
        self.assertNotIn(PHONE, combined)
        self.assertNotIn(VALID_ID, combined)
        payload = self.json_run(path)
        self.assertNotIn(PHONE, json.dumps(payload, ensure_ascii=False))
        self.assertNotIn(VALID_ID, json.dumps(payload, ensure_ascii=False))

    # 11. Determinism: identical runs produce byte-identical JSON.
    def test_deterministic_json_output(self):
        path = self.write("j.md", f"a {PHONE} b {VALID_ID} c\n")
        first = _run([path, "--json"]).stdout
        second = _run([path, "--json"]).stdout
        self.assertEqual(first, second)

    # 12. Usage errors: missing path and missing glossary exit 2.
    def test_usage_errors_exit_two(self):
        result = _run([self.root / "nope.md"], expect_ok=False)
        self.assertEqual(result.returncode, 2)
        path = self.write("k.md", "x\n")
        result = _run([path, "--custom-terms", self.root / "no-terms.txt"],
                      expect_ok=False)
        self.assertEqual(result.returncode, 2)

    # 13. Checksum function matches the GB 11643-1999 reference pair.
    def test_idcard_checksum_reference_values(self):
        self.assertTrue(check_sensitive_text.idcard_checksum_ok(VALID_ID))
        self.assertFalse(check_sensitive_text.idcard_checksum_ok(INVALID_ID))
        self.assertFalse(check_sensitive_text.idcard_checksum_ok("1101051949123100"))
        self.assertTrue(check_sensitive_text.idcard_checksum_ok(
            "11010519491231002x"))  # lowercase x accepted

    # 14. Mask keeps length and hides the middle for short values.
    def test_mask_shapes(self):
        self.assertEqual(check_sensitive_text.mask(PHONE), PHONE_MASKED)
        self.assertEqual(check_sensitive_text.mask(VALID_ID), VALID_ID_MASKED)
        self.assertEqual(check_sensitive_text.mask("代号"), "代*")
        self.assertEqual(check_sensitive_text.mask("abcd"), "a***")


if __name__ == "__main__":
    unittest.main()
