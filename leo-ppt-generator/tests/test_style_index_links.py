"""发布索引中的真实 Markdown 链接和锚点校验。"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lint_style_governance import check_document_links


class StyleIndexLinksTest(unittest.TestCase):
    def test_virtual_pages_encoded_chinese_and_space(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = {"generated/start.md": "[下一页](../来源/中文%20空格.md#标题)", "来源/中文 空格.md": "# 标题\n"}
            self.assertEqual(check_document_links(docs, root), [])

    def test_real_files_and_duplicate_heading_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.md").write_text("# 标题\n# 标题\n")
            self.assertEqual(check_document_links({"index.md": "[项](target.md#标题-1)"}, root), [])

    def test_missing_path_and_anchor_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = check_document_links({"a.md": "[路径](missing.md) [锚点](#不存在)"}, Path(directory))
            self.assertEqual(len(errors), 2)
            self.assertIn("link_target_missing", errors[0])
            self.assertIn("link_anchor_missing", errors[1])

    def test_code_examples_and_external_links_are_not_files(self):
        with tempfile.TemporaryDirectory() as directory:
            docs = {"a.md": "```md\n[示例](missing.md)\n```\n[外部](https://example.org/missing.md)"}
            self.assertEqual(check_document_links(docs, Path(directory)), [])


if __name__ == "__main__":
    unittest.main()
