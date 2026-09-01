#!/usr/bin/env python3
"""build_material_digest.py 单测（R-02）：按主题词频抽段 / 原文锚点保留 /
大纲分节归属 / 低分过滤 / 输出目录创建 / 确定性双跑 / 英文关键词 /
零命中语义 / CLI 错误 exit 2。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_material_digest.py"


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )


def _write(tmp, name, text):
    path = Path(tmp) / name
    path.write_text(text, encoding="utf-8")
    return path


MATERIAL = """第一章 背景

本节介绍分布式存储系统的整体背景与行业现状，未涉及缓存设计。

第二章 缓存设计

缓存命中率是分布式存储系统的核心指标。本章提出三级缓存架构，
热点数据驻留内存层，冷数据下沉到 SSD 层，命中率提升到 92%。

第三章 一致性协议

副本一致性协议负责多副本数据的同步顺序，写放大问题影响整体吞吐。

第四章 成本模型

存储成本由硬件折旧与运维人力共同决定，本章给出单位 TB 成本公式。
"""

IRRELEVANT = """ 第一章 风土

本节介绍葡萄种植的风土条件与酿造工艺细节，与缓存设计无关。

第二章 酒窖

橡木桶陈酿时间影响单宁结构。
"""


class TopicOnlyTest(unittest.TestCase):
    def test_relevant_paragraphs_selected_with_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            material = _write(tmp, "material.md", MATERIAL)
            result = _run([material, "--topic", "分布式存储系统的缓存命中率设计",
                           "--top", "1",
                           "--output", str(Path(tmp) / "out" / "material-digest.md")])
            self.assertEqual(result.returncode, 0, result.stdout)
            digest = (Path(tmp) / "out" / "material-digest.md").read_text(encoding="utf-8")
        self.assertIn("缓存命中率是分布式存储系统的核心指标", digest)
        self.assertIn("¶", digest)
        # Top-1 keeps only the highest-scoring paragraph; meta-narration
        # background text is discounted below it.
        self.assertNotIn("行业现状", digest)

    def test_anchor_header_marks_original_paragraph_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            material = _write(tmp, "material.md", MATERIAL)
            result = _run([material, "--topic", "缓存命中率",
                           "--output", str(Path(tmp) / "d.md")])
            self.assertEqual(result.returncode, 0, result.stdout)
            digest = (Path(tmp) / "d.md").read_text(encoding="utf-8")
        # Blank-line blocks: 1 背景标题 / 2 背景正文 / 3 缓存标题 / 4 缓存正文.
        self.assertIn("### ¶4（得分", digest)
        self.assertIn("未收录段落", digest)

    def test_output_parent_directory_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            material = _write(tmp, "material.md", MATERIAL)
            out = Path(tmp) / "deep" / "nested" / "content" / "material-digest.md"
            result = _run([material, "--topic", "缓存命中率", "--output", str(out)])
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(out.exists())


class OutlineSectionedTest(unittest.TestCase):
    def test_sections_collect_their_own_paragraphs(self):
        outline = """# 大纲
## 缓存设计
## 一致性协议
"""
        with tempfile.TemporaryDirectory() as tmp:
            material = _write(tmp, "material.md", MATERIAL)
            outline_path = _write(tmp, "outline-v1.md", outline)
            result = _run([material, "--topic", "分布式存储系统",
                           "--outline", outline_path,
                           "--output", str(Path(tmp) / "d.md")])
            self.assertEqual(result.returncode, 0, result.stdout)
            digest = (Path(tmp) / "d.md").read_text(encoding="utf-8")
        self.assertIn("## 缓存设计", digest)
        self.assertIn("## 一致性协议", digest)
        self.assertIn("三级缓存架构", digest)
        self.assertIn("写放大问题", digest)

    def test_low_score_paragraphs_never_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            material = _write(tmp, "material.md", MATERIAL + "\n" + IRRELEVANT)
            result = _run([material, "--topic", "缓存命中率与三级缓存架构",
                           "--output", str(Path(tmp) / "d.md")])
            self.assertEqual(result.returncode, 0, result.stdout)
            digest = (Path(tmp) / "d.md").read_text(encoding="utf-8")
        self.assertNotIn("葡萄种植", digest)
        self.assertNotIn("橡木桶", digest)


class DeterminismAndJsonTest(unittest.TestCase):
    def test_same_input_same_output_across_runs(self):
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                material = _write(tmp, "material.md", MATERIAL)
                result = _run([material, "--topic", "缓存命中率",
                               "--output", str(Path(tmp) / "d.md")])
                self.assertEqual(result.returncode, 0, result.stdout)
                outputs.append((result.stdout,
                                (Path(tmp) / "d.md").read_text(encoding="utf-8")))
        self.assertEqual(outputs[0], outputs[1])

    def test_json_payload_reports_selected_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            material = _write(tmp, "material.md", MATERIAL)
            result = _run([material, "--topic", "缓存命中率",
                           "--output", str(Path(tmp) / "d.md"), "--json"])
            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout)
        for key in ("material", "topic", "paragraphs", "selected", "mode", "exit"):
            self.assertIn(key, payload)
        self.assertEqual(payload["paragraphs"], 4)
        self.assertIn(4, [e["anchor"] for e in payload["selected"]])

    def test_english_topic_token_hits_english_paragraph(self):
        material = """Intro paragraph with general background and no signal at all here.

The Transformer architecture relies on self-attention to model token
dependencies across the full sequence without recurrence.
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, "paper.md", material)
            result = _run([path, "--topic", "Transformer self-attention 综述",
                           "--output", str(Path(tmp) / "d.md")])
            self.assertEqual(result.returncode, 0, result.stdout)
            digest = (Path(tmp) / "d.md").read_text(encoding="utf-8")
        self.assertIn("self-attention", digest)


class CliSemanticsTest(unittest.TestCase):
    def test_zero_hits_exits_1_with_note_in_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            material = _write(tmp, "material.md", IRRELEVANT)
            result = _run([material, "--topic", "缓存命中率架构",
                           "--output", str(Path(tmp) / "d.md")])
            self.assertEqual(result.returncode, 1, result.stdout)
            digest = (Path(tmp) / "d.md").read_text(encoding="utf-8")
        self.assertIn("零命中", digest)

    def test_missing_material_file_exits_2(self):
        result = _run([Path(tempfile.gettempdir()) / "no-such-material.md",
                       "--topic", "x"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("ERROR", result.stderr)

    def test_missing_topic_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            material = _write(tmp, "material.md", MATERIAL)
            result = _run([material])
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
