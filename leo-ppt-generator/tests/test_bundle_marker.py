"""bundle_root 标记定位的回归测试（托管 venv 打包缺陷修复）。

背景：包被物理复制进托管 venv 的 site-packages 后，
``parents[3]`` 布局回不到技能包根，``style list`` 返回空。修复为
runtime_manager._install 在 runtime 目录写 ``bundle_root`` 标记，
``styles._marker_bundle_root`` 从 ``__file__`` 向上查找标记。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator import styles  # noqa: E402


class BundleMarkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name).resolve()
        self.bundle = root / "bundle-target"
        (self.bundle / "references" / "styles").mkdir(parents=True)
        (self.bundle / "assets").mkdir(parents=True)
        self.runtime_dir = root / "runtimes" / "rt1"
        fake_pkg = self.runtime_dir / "venv" / "lib" / "python3.12" / "site-packages" / "leo_ppt_generator"
        fake_pkg.mkdir(parents=True)
        self.fake_styles_py = fake_pkg / "styles.py"
        self.runtime_dir.joinpath("bundle_root").write_text(str(self.bundle) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_marker_found_from_managed_venv_layout(self) -> None:
        with mock.patch.object(styles, "__file__", str(self.fake_styles_py), create=True):
            self.assertEqual(styles._marker_bundle_root(), self.bundle)
            self.assertEqual(
                styles._builtin_styles_dir(), self.bundle / "references" / "styles"
            )

    def test_env_override_still_wins(self) -> None:
        tmp_root = Path(self._tmp.name).resolve()
        override = tmp_root / "override-bundle"
        (override / "references" / "styles").mkdir(parents=True)
        with mock.patch.object(styles, "__file__", str(self.fake_styles_py), create=True):
            with mock.patch.dict("os.environ", {"LEO_PPT_BUNDLE": str(override)}):
                self.assertEqual(
                    styles._builtin_styles_dir(), override / "references" / "styles"
                )

    def test_no_marker_falls_back_to_repo_layout(self) -> None:
        self.runtime_dir.joinpath("bundle_root").unlink()
        tmp_root = Path(self._tmp.name).resolve()
        repo_like = tmp_root / "repo" / "leo-ppt-generator"
        pkg = repo_like / "runtime" / "src" / "leo_ppt_generator"
        pkg.mkdir(parents=True)
        (repo_like / "references" / "styles").mkdir(parents=True)
        fake = pkg / "styles.py"
        with mock.patch.object(styles, "__file__", str(fake), create=True):
            self.assertIsNone(styles._marker_bundle_root())
            self.assertEqual(
                styles._builtin_styles_dir(), repo_like / "references" / "styles"
            )

    def test_dead_marker_path_ignored(self) -> None:
        self.runtime_dir.joinpath("bundle_root").write_text(
            str(Path(self._tmp.name).resolve() / "gone") + "\n", encoding="utf-8"
        )
        with mock.patch.object(styles, "__file__", str(self.fake_styles_py), create=True):
            self.assertIsNone(styles._marker_bundle_root())


if __name__ == "__main__":
    unittest.main()
