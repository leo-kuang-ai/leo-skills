"""bundle_root 标记定位的回归测试（托管 venv 打包缺陷修复，U10 后）。

背景：包被物理复制进托管 venv 的 site-packages 后，``parents[3]`` 布局
回不到技能包根，resolver 返回空库。修复为 runtime_manager._install 在
runtime 目录写 ``bundle_root`` 标记，``asset_resolver._marker_bundle_root``
从 ``__file__`` 向上查找标记，``builtin_library_root`` 只认标记 bundle 下的
template-library/library.json（新库声明文件）。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator import asset_resolver  # noqa: E402

LIBRARY_DECLARATION = {
    "schema_version": 1, "kind": "template-library", "library_id": "builtin",
    "zones": {"canonical": "c", "reference": "r", "governance": "g",
              "catalog": "k", "evidence": "e"},
    "reserved_directory_names": [],
}


def _make_library(bundle: Path) -> None:
    library = bundle / "template-library"
    (library / "canonical" / "styles").mkdir(parents=True, exist_ok=True)
    (library / "library.json").write_text(json.dumps(LIBRARY_DECLARATION), encoding="utf-8")


class BundleMarkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name).resolve()
        self.bundle = root / "bundle-target"
        _make_library(self.bundle)
        self.runtime_dir = root / "runtimes" / "rt1"
        fake_pkg = self.runtime_dir / "venv" / "lib" / "python3.12" / "site-packages" / "leo_ppt_generator"
        fake_pkg.mkdir(parents=True)
        self.fake_module = fake_pkg / "asset_resolver.py"
        self.runtime_dir.joinpath("bundle_root").write_text(str(self.bundle) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_marker_found_from_managed_venv_layout(self):
        with mock.patch.object(asset_resolver, "__file__", str(self.fake_module), create=True):
            self.assertEqual(asset_resolver._marker_bundle_root(), self.bundle)
            self.assertEqual(asset_resolver.builtin_library_root(),
                             self.bundle / "template-library")

    def test_env_override_still_wins(self):
        tmp_root = Path(self._tmp.name).resolve()
        override = tmp_root / "override-bundle"
        _make_library(override)
        with mock.patch.object(asset_resolver, "__file__", str(self.fake_module), create=True):
            with mock.patch.dict("os.environ", {"LEO_PPT_BUNDLE": str(override)}):
                self.assertEqual(asset_resolver.builtin_library_root(),
                                 override / "template-library")

    def test_no_marker_falls_back_to_repo_layout(self):
        self.runtime_dir.joinpath("bundle_root").unlink()
        tmp_root = Path(self._tmp.name).resolve()
        repo_like = tmp_root / "repo" / "leo-ppt-generator"
        pkg = repo_like / "runtime" / "src" / "leo_ppt_generator"
        pkg.mkdir(parents=True)
        _make_library(repo_like)
        fake = pkg / "asset_resolver.py"
        with mock.patch.object(asset_resolver, "__file__", str(fake), create=True):
            self.assertIsNone(asset_resolver._marker_bundle_root())
            self.assertEqual(asset_resolver.builtin_library_root(),
                             repo_like / "template-library")

    def test_dead_marker_path_ignored(self):
        self.runtime_dir.joinpath("bundle_root").write_text(
            str(Path(self._tmp.name).resolve() / "gone") + "\n", encoding="utf-8"
        )
        with mock.patch.object(asset_resolver, "__file__", str(self.fake_module), create=True):
            self.assertIsNone(asset_resolver._marker_bundle_root())


if __name__ == "__main__":
    unittest.main()
