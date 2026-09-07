"""聚焦回归（D-OBS-03）：strict 回溯根不依赖检查器 CWD。

run 位于 <project-root>/runs/<run-id> 时，`sources/…` 相对引用应能从项目根
回溯，无需操作者把 CWD 切到项目根，也不再强制依赖 generated_from 的解析。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "check_sources_manifest.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(project: Path, evidence: Path, *, with_generated_from: bool) -> Path:
    def canonical(payload: dict) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    payload = {
        "schema_version": 1,
        "manifest_kind": "visual-sources", "route": "generate",
        "pages": [
            {"page_id": "slide_01", "visuals": [
                {"visual_id": "v1", "kind": "figure", "source_class": "user-material",
                 "tier": "引用", "source_ref": "sources/evidence.png",
                 "source_sha256": _sha(evidence), "backend": "user",
                 "handling_mode": "preserve"},
            ]},
            {"page_id": "slide_02", "visuals": []},
        ],
    }
    if with_generated_from:
        payload["generated_from"] = "content/deck-master-v1.md"
    payload["contents_sha256"] = hashlib.sha256(
        canonical(payload).encode("utf-8")).hexdigest()
    body = json.dumps(payload, ensure_ascii=False, indent=1)
    frozen = project / "runs" / "run-001" / "input" / "sources-manifest.json"
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_text(body, encoding="utf-8")
    target = project / "content" / "sources-manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _make_run(tmp: Path) -> tuple[Path, Path, Path]:
    project = tmp / "proj"
    run = project / "runs" / "run-001"
    (project / "sources").mkdir(parents=True)
    (run / "input" / "deep").mkdir(parents=True)
    evidence = project / "sources" / "evidence.png"
    from PIL import Image
    Image.new("RGB", (32, 32), "#ffffff").save(evidence)
    # run input 内冻结副本（manifest 由检查器从 run/input 解析）
    return project, run, evidence


class TraceRootsIndependenceTest(unittest.TestCase):
    def _check(self, run: Path, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(run), "--strict"],
            capture_output=True, text=True, timeout=60, cwd=str(cwd),
        )

    def test_strict_resolves_project_relative_refs_without_cwd(self):
        with tempfile.TemporaryDirectory(prefix="leo-obs03-") as tmp_name:
            tmp = Path(tmp_name)
            project, run, evidence = _make_run(tmp)
            _manifest(project, evidence, with_generated_from=False)
            # CWD 故意放在与项目无关的目录：项目根回溯应仍然成立。
            result = self._check(run, cwd=tmp / "elsewhere"
                                 if (tmp / "elsewhere").mkdir() is None else tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"fails": 0', result.stdout)

    def test_strict_still_works_with_generated_from_present(self):
        with tempfile.TemporaryDirectory(prefix="leo-obs03b-") as tmp_name:
            tmp = Path(tmp_name)
            project, run, evidence = _make_run(tmp)
            _manifest(project, evidence, with_generated_from=True)
            result = self._check(run, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unresolvable_reference_still_fails_strict(self):
        with tempfile.TemporaryDirectory(prefix="leo-obs03c-") as tmp_name:
            tmp = Path(tmp_name)
            project, run, evidence = _make_run(tmp)
            _manifest(project, evidence, with_generated_from=False)
            evidence.unlink()  # 源文件消失：引用不可回溯必须仍然 FAIL。
            result = self._check(run, cwd=tmp)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
