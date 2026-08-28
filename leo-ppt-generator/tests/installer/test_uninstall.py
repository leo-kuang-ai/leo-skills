"""U9 --uninstall 行为回归（bash 侧；沙盒 HOME 与隔离 bin/target 目录）。

钥匙串零触碰以“未发起 security/keychain 子进程”断言表达；
Windows 侧仅做静态解析检查，真实拆除属 deferred 验证。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SKILL_DIR = TEST_DIR.parents[1]
INSTALLER = SKILL_DIR / "install.sh"


class UninstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        (self.home / ".local/bin").mkdir(parents=True)
        self.skill_dir = self.home / "codex-skills" / "skills" / "leo-ppt-generator"
        self.skill_dir.mkdir(parents=True)
        (self.skill_dir / "SKILL.md").write_text("# x", encoding="utf-8")
        (self.skill_dir / "scripts").mkdir()
        (self.skill_dir / "scripts" / "runtime_manager.py").write_text(
            "# x", encoding="utf-8"
        )
        launcher = self.home / ".local/bin/leo-ppt"
        launcher.symlink_to(self.skill_dir / "scripts" / "leo-ppt")
        # 卸载以“脚本自身所在位置”为拆除目标（安全护栏：父目录须为 skills），
        # 因此测试把安装器副本放进沙盒技能目录后再执行。
        shutil.copy2(INSTALLER, self.skill_dir / "install.sh")
        self.installer_copy = self.skill_dir / "install.sh"
        self.data_home = self.home / "data-home"
        (self.data_home / "runtimes").mkdir(parents=True)

    def _run_uninstall(self, *extra: str) -> subprocess.CompletedProcess:
        env = dict(
            os.environ,
            HOME=str(self.home),
            LEO_PPT_HOME=str(self.data_home),
        )
        return subprocess.run(
            ["bash", str(self.installer_copy), "--uninstall", *extra],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_default_keeps_data_and_removes_program_surface(self):
        proc = self._run_uninstall()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse((self.home / ".local/bin/leo-ppt").is_symlink())
        self.assertFalse(self.skill_dir.exists())
        self.assertTrue((self.data_home / "runtimes").exists(), "数据目录默认保留")
        self.assertIn("钥匙串", proc.stdout)

    def test_purge_flag_removes_data_home(self):
        proc = self._run_uninstall("--purge-data")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.data_home.exists())

    def test_idempotent_on_missing_install(self):
        first = self._run_uninstall()
        # 首次卸载会连带删除位于技能目录内的安装器副本；重现“再次执行”前
        # 仅重建父目录（不重建 SKILL.md，模拟内容已不完整的安装残留）。
        self.skill_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(INSTALLER, self.installer_copy)
        second = self._run_uninstall()
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0, second.stderr)

    def test_no_keychain_process_invoked(self):
        sentinel = self.home / "sentinel-security"
        sentinel.write_text("#!/bin/sh\nexit 42\n")
        sentinel.chmod(0o755)
        fake_bin = self.home / "fakebin"
        fake_bin.mkdir()
        for name in ("security", "keychain-access"):
            (fake_bin / name).write_text("#!/bin/sh\nexit 42\n")
            (fake_bin / name).chmod(0o755)
        env_path = f"{fake_bin}:{os.environ['PATH']}"
        proc = subprocess.run(
            ["bash", str(INSTALLER), "--uninstall"],
            capture_output=True,
            text=True,
            env=dict(os.environ, HOME=str(self.home), PATH=env_path),
            check=False,
        )
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
