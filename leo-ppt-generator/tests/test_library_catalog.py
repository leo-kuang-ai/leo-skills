#!/usr/bin/env python3
"""library_catalog.py tests (R-04): add/list/remove/export-manifest behaviors,
idempotency, determinism, data-boundary exits, and derivation compatibility
with check_sources_manifest.py (default and strict).
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "library_catalog.py"
CHECKER = SKILL_DIR / "scripts" / "check_sources_manifest.py"


def _run(args, expect_ok=True):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )
    if expect_ok and result.returncode != 0:
        raise AssertionError(
            f"expected exit 0, got {result.returncode}: {result.stderr}"
        )
    return result


class _Library:
    """Temp library root + helpers to add material files."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "library"
        self.counter = 0

    def material(self, content: bytes, name="asset.png") -> Path:
        # Isolate each material in its own dir so original_name stays verbatim.
        self.counter += 1
        path = self.tmp / "materials" / f"m{self.counter}" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def run(self, *args, expect_ok=True):
        return _run(["--root", self.root, *args], expect_ok=expect_ok)

    def catalog(self) -> dict:
        return json.loads(
            (self.root / "catalog.json").read_text(encoding="utf-8")
        )


class AddBehavior(unittest.TestCase):
    def test_add_registers_catalog_and_asset_with_matching_sha(self):
        lib = _Library()
        payload = b"png-bytes-1"
        sha = hashlib.sha256(payload).hexdigest()
        lib.run("add", lib.material(payload), "--tags", "logo", "--source",
                "https://example.com/a.png", "--note", "first logo")

        entry = lib.catalog()["entries"][0]
        self.assertEqual(entry["sha256"], sha)
        self.assertEqual(entry["original_name"], "asset.png")
        self.assertEqual(entry["tags"], ["logo"])
        self.assertEqual(entry["source"], "https://example.com/a.png")
        self.assertEqual(entry["note"], "first logo")
        self.assertTrue(entry["added_at"].endswith("Z"))

        asset = lib.root / entry["asset_path"]
        self.assertTrue(asset.is_file())
        self.assertEqual(asset.name, f"{sha[:12]}-asset.png")
        self.assertEqual(
            hashlib.sha256(asset.read_bytes()).hexdigest(), sha
        )

    def test_duplicate_add_is_idempotent_with_warn(self):
        lib = _Library()
        payload = b"same-content"
        lib.run("add", lib.material(payload))
        second = lib.run("add", lib.material(payload, name="copy.png"))
        self.assertEqual(second.returncode, 0)
        self.assertIn("WARN", second.stderr)
        self.assertIn("幂等", second.stderr)
        entries = lib.catalog()["entries"]
        self.assertEqual(len(entries), 1)
        # Content-addressed: only one asset copy exists even after two adds.
        assets = list((lib.root / "assets").iterdir())
        self.assertEqual(len(assets), 1)

    def test_add_missing_file_exits_2(self):
        lib = _Library()
        result = lib.run("add", lib.tmp / "nope.png", expect_ok=False)
        self.assertEqual(result.returncode, 2)

    def test_sensitive_source_is_rejected(self):
        lib = _Library()
        result = lib.run(
            "add", lib.material(b"x"), "--source", "https://u:my-api-key@h/",
            expect_ok=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse((lib.root / "catalog.json").exists())


class ListBehavior(unittest.TestCase):
    def test_list_tag_filter(self):
        lib = _Library()
        lib.run("add", lib.material(b"a"), "--tags", "logo,brand")
        lib.run("add", lib.material(b"b"), "--tags", "chart")
        hit = lib.run("list", "--tag", "logo", "--json")
        data = json.loads(hit.stdout)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["entries"][0]["tags"], ["brand", "logo"])

    def test_list_json_output_sorted_by_sha(self):
        lib = _Library()
        lib.run("add", lib.material(b"zz"))
        lib.run("add", lib.material(b"aa"))
        lib.run("add", lib.material(b"mm"))
        shas = [
            e["sha256"]
            for e in json.loads(lib.run("list", "--json").stdout)["entries"]
        ]
        self.assertEqual(shas, sorted(shas))

    def test_tags_with_spaces_are_kept_verbatim(self):
        lib = _Library()
        lib.run("add", lib.material(b"s"), "--tags", "brand logo, chart")
        entry = lib.catalog()["entries"][0]
        self.assertEqual(entry["tags"], ["brand logo", "chart"])
        hit = lib.run("list", "--tag", "brand logo", "--json")
        self.assertEqual(json.loads(hit.stdout)["count"], 1)


class RemoveBehavior(unittest.TestCase):
    def test_remove_single_entry_and_asset(self):
        lib = _Library()
        payload = b"to-remove"
        sha = hashlib.sha256(payload).hexdigest()
        lib.run("add", lib.material(payload))
        lib.run("add", lib.material(b"keep-me"))

        lib.run("remove", sha[:12])
        entries = lib.catalog()["entries"]
        self.assertEqual(len(entries), 1)
        self.assertNotEqual(entries[0]["sha256"], sha)
        self.assertFalse((lib.root / "assets" / f"{sha[:12]}-asset.png").exists())

    def test_remove_all_clears_library(self):
        lib = _Library()
        lib.run("add", lib.material(b"one"))
        lib.run("add", lib.material(b"two"))
        lib.run("remove", "--all")
        self.assertEqual(lib.catalog()["entries"], [])
        self.assertEqual(list((lib.root / "assets").iterdir()), [])

    def test_remove_unknown_sha_exits_2(self):
        lib = _Library()
        lib.run("add", lib.material(b"x"))
        result = lib.run("remove", "ffffffffffff", expect_ok=False)
        self.assertEqual(result.returncode, 2)

    def test_remove_short_prefix_exits_2(self):
        lib = _Library()
        lib.run("add", lib.material(b"x"))
        self.assertEqual(lib.run("remove", "abc", expect_ok=False).returncode, 2)

    def _retarget_asset_path(self, lib, new_path):
        catalog = lib.catalog()
        catalog["entries"][0]["asset_path"] = new_path
        (lib.root / "catalog.json").write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_remove_refuses_asset_path_escaping_library(self):
        # Hand-edited catalog: "../" must not turn remove into an arbitrary
        # unlink of files outside the library root.
        lib = _Library()
        payload = b"guard-me"
        sha = hashlib.sha256(payload).hexdigest()
        lib.run("add", lib.material(payload))
        outside = lib.tmp / "outside-secret.txt"
        outside.write_bytes(payload)
        self._retarget_asset_path(lib, "../outside-secret.txt")
        result = lib.run("remove", sha[:12], expect_ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("越界", result.stderr)
        self.assertTrue(outside.is_file())
        # The entry itself is not dropped either: refuse means no mutation.
        self.assertEqual(len(lib.catalog()["entries"]), 1)

    def test_remove_refuses_absolute_asset_path(self):
        lib = _Library()
        payload = b"abs-guard"
        sha = hashlib.sha256(payload).hexdigest()
        lib.run("add", lib.material(payload))
        outside = lib.tmp / "absolute-secret.txt"
        outside.write_bytes(payload)
        self._retarget_asset_path(lib, str(outside))
        result = lib.run("remove", sha[:12], expect_ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("越界", result.stderr)
        self.assertTrue(outside.is_file())


class ExportManifestBehavior(unittest.TestCase):
    def _seed(self, lib):
        lib.run("add", lib.material(b"zz"), "--tags", "a")
        lib.run("add", lib.material(b"aa"), "--tags", "b")

    def test_export_fields_and_order(self):
        lib = _Library()
        self._seed(lib)
        result = lib.run("export-manifest")
        manifest = json.loads(result.stdout)

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["manifest_kind"], "visual-sources")
        visuals = manifest["pages"][0]["visuals"]
        self.assertEqual(len(visuals), 2)
        shas = [v["source_sha256"] for v in visuals]
        self.assertEqual(shas, sorted(shas))
        for v in visuals:
            self.assertEqual(v["source_class"], "user-material")
            self.assertEqual(v["tier"], "引用")
            self.assertEqual(v["backend"], "user")
            self.assertTrue(Path(v["source_ref"]).is_absolute())
        self.assertIn("WARN", result.stderr)
        self.assertIn("slide_01", result.stderr)

    def test_export_contents_sha256_is_self_consistent(self):
        lib = _Library()
        self._seed(lib)
        manifest = json.loads(lib.run("export-manifest").stdout)
        payload = {
            k: v for k, v in manifest.items() if k != "contents_sha256"
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        self.assertEqual(
            manifest["contents_sha256"],
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def test_export_is_deterministic(self):
        lib = _Library()
        self._seed(lib)
        first = lib.run("export-manifest").stdout
        second = lib.run("export-manifest").stdout
        self.assertEqual(first, second)

    def test_export_empty_library_exits_2(self):
        lib = _Library()
        result = lib.run("export-manifest", expect_ok=False)
        self.assertEqual(result.returncode, 2)

    def test_exported_manifest_passes_check_sources_manifest(self):
        lib = _Library()
        self._seed(lib)
        out = lib.tmp / "exported-manifest.json"
        out.write_text(lib.run("export-manifest").stdout, encoding="utf-8")
        for extra in ([], ["--strict"]):
            with self.subTest(strict=bool(extra)):
                check = subprocess.run(
                    [sys.executable, str(CHECKER), str(out), *extra],
                    capture_output=True, text=True,
                )
                self.assertEqual(
                    check.returncode, 0,
                    f"checker output: {check.stdout}{check.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
