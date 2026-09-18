#!/usr/bin/env python3
"""diagram_render.py 单元测试：正常渲染 / 空节点报错 / 坏 JSON 报错 / 确定性
（同输入两次渲染逐字节一致）/ TB 方向。Pillow 缺失时 skip。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "diagram_render.py"

SPEC = {
    "direction": "LR",
    "title": "数据管线",
    "nodes": [{"id": "a", "label": "采集"}, {"id": "b", "label": "清洗"},
              {"id": "c", "label": "建模"}],
    "edges": [{"from": "a", "to": "b", "label": "raw"},
              {"from": "b", "to": "c"}],
}


_VENV = os.environ.get("LEO_PPT_TEST_VENV", "")
_PY = _VENV if _VENV and Path(_VENV).is_file() else sys.executable


def _run(argv):
    return subprocess.run([_PY, str(SCRIPT), *argv],
                          capture_output=True, text=True)


def _write(content):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                    encoding="utf-8")
    f.write(content)
    return f.name


class DiagramRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe = subprocess.run([_PY, "-c", "import PIL"], capture_output=True)
        if probe.returncode != 0:
            raise unittest.SkipTest("渲染解释器无 Pillow（LEO_PPT_TEST_VENV 可指定 venv）")

    def test_renders_png(self):
        src = _write(json.dumps(SPEC))
        out = tempfile.mktemp(suffix=".png")
        r = _run([src, out])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(Path(out).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")

    def test_deterministic_bytes(self):
        src = _write(json.dumps(SPEC))
        o1, o2 = tempfile.mktemp(suffix=".png"), tempfile.mktemp(suffix=".png")
        _run([src, o1]); _run([src, o2])
        self.assertEqual(Path(o1).read_bytes(), Path(o2).read_bytes())

    def test_empty_nodes_fails(self):
        src = _write(json.dumps({"nodes": [], "edges": []}))
        r = _run([src, tempfile.mktemp(suffix=".png")])
        self.assertEqual(r.returncode, 3)
        self.assertIn("no_nodes", r.stderr)

    def test_bad_json_fails(self):
        src = _write("{not json")
        r = _run([src, tempfile.mktemp(suffix=".png")])
        self.assertEqual(r.returncode, 2)

    def test_tb_direction(self):
        spec = dict(SPEC, direction="TB")
        src = _write(json.dumps(spec))
        r = _run([src, tempfile.mktemp(suffix=".png")])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_rejects_unknown_direction(self):
        src = _write(json.dumps(dict(SPEC, direction="DIAGONAL")))
        r = _run([src, tempfile.mktemp(suffix=".png")])
        self.assertEqual(r.returncode, 3)
        self.assertIn("direction_invalid", r.stderr)

    def test_rejects_unknown_edge_node(self):
        spec = dict(SPEC, edges=[{"from": "a", "to": "missing"}])
        src = _write(json.dumps(spec))
        r = _run([src, tempfile.mktemp(suffix=".png")])
        self.assertEqual(r.returncode, 3)
        self.assertIn("unknown_node", r.stderr)

    def test_rejects_cycle(self):
        spec = dict(SPEC, edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "a"}])
        src = _write(json.dumps(spec))
        r = _run([src, tempfile.mktemp(suffix=".png")])
        self.assertEqual(r.returncode, 3)
        self.assertIn("diagram_cycle", r.stderr)

    def test_rejects_duplicate_node_id(self):
        spec = dict(SPEC, nodes=[{"id": "a"}, {"id": "a"}], edges=[])
        src = _write(json.dumps(spec))
        r = _run([src, tempfile.mktemp(suffix=".png")])
        self.assertEqual(r.returncode, 3)
        self.assertIn("duplicate_node_id", r.stderr)


if __name__ == "__main__":
    unittest.main()
