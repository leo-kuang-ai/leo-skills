#!/usr/bin/env python3
"""image-text-composition.md 文档合同测试（R-24）：四步小节、蒙版参数、
主体映射/安全区声明语法示例、终检归属表述、反模式清单防漂移。"""
import unittest
from pathlib import Path

DOC = (
    Path(__file__).resolve().parents[1]
    / "references" / "image-text-composition.md"
)
LINE_BUDGET = 48


class ImageTextCompositionDocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = DOC.read_text(encoding="utf-8")

    def test_doc_exists_and_within_line_budget(self):
        self.assertTrue(DOC.exists())
        lines = self.content.splitlines()
        self.assertLessEqual(len(lines), LINE_BUDGET)

    def test_four_step_section_headers_present(self):
        for header in (
            "## 第一步 安全区约束注入",
            "## 第二步 无蒙版优先",
            "## 第三步 局部图像色调蒙版",
            "## 第四步 缩略图终检",
        ):
            self.assertIn(header, self.content)

    def test_mask_hard_constraints_present(self):
        # Degradation-only tint must carry all three upstream constraints:
        # localized radial, image-sampled tone, peak alpha band 0.15-0.30.
        for fragment in (
            "radial",
            "0.15-0.30",
            "取图内色调",
            "仅当无蒙版方案",
        ):
            self.assertIn(fragment, self.content)

    def test_subject_map_and_safe_zone_syntax_example_present(self):
        # Master visual line must declare text zone + subject map with a
        # concrete syntax example, and keep text out of face/subject zones.
        for fragment in (
            "文字落位区",
            "主体映射",
            "文字落位=底部 30% 横带",
            "主体映射=人脸 70%x 30%y",
            "文字只进安全区",
        ):
            self.assertIn(fragment, self.content)

    def test_thumbnail_check_delegates_to_visual_qa_round(self):
        # Final thumbnail check belongs to the multimodal QA round, not a
        # deterministic script (BR-004 semantic-layer exemption).
        for fragment in (
            "360px",
            "归既有视觉 QA 轮",
            "非确定性脚本",
        ):
            self.assertIn(fragment, self.content)

    def test_antipattern_list_present(self):
        for fragment in (
            "## 反模式",
            "全画布均匀",
            "纯黑",
            "横穿人脸",
        ):
            self.assertIn(fragment, self.content)

    def test_scope_and_visual_qa_relation_present(self):
        # Scope line must limit the protocol to image-backed pages and defer
        # light solid-background pages to the existing visual-qa contrast row.
        for fragment in (
            "全出血封面",
            "大图井",
            "visual-qa.md",
            "浅底纯色页",
        ):
            self.assertIn(fragment, self.content)


if __name__ == "__main__":
    unittest.main()
