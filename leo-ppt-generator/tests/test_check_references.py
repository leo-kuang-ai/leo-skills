#!/usr/bin/env python3
"""check_references.py 单测（R-13）：DOI 格式非法 / 同 DOI 年份·题名不一致 /
同题名 DOI 不一致 / GB/T 7714 类型标识与年份提示 / 无文献页向后兼容 /
--json shape / exit 语义（0 通过 / 1 不一致 / 2 用法错误）。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_references.py"


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )


def _master(tmp, text, name="deck-master-v1.md"):
    path = Path(tmp) / name
    path.write_text(text, encoding="utf-8")
    return path


CLEAN_REFS = """# 母版
## S1 证据
- 标题：方法对比如下
- 要点：
  - Zhang 的方法收敛更快【引用|src:¶12】DOI: 10.1038/abc123
- speaker_script：先说结论。

## S2 参考文献
- [1] Zhang Y. Deep learning for X[J]. Nature, 2023, 612: 1-10. DOI: 10.1038/abc123
- [2] Li M. Graph embeddings at scale[C]. NeurIPS, 2021: 100-112. doi.org/10.1109/xyz987
"""


class NoReferenceSectionTest(unittest.TestCase):
    def test_master_without_reference_page_skips_with_info(self):
        master = """## S1 方法
- 标题：先预检后出图
- speaker_script：先说结论。
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("母版无参考文献页/段，文献元数据校验跳过", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)


class CleanReferencesTest(unittest.TestCase):
    def test_consistent_bibliography_and_citations_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, CLEAN_REFS)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)
        self.assertIn("ENTRIES: 3 条（文献页条目 2 / 正文含 DOI 行 1）", result.stdout)


class DoiFormatTest(unittest.TestCase):
    def test_malformed_doi_prefix_fails_with_exit_1(self):
        master = """## S2 参考文献
- [1] Zhang Y. Deep learning for X[J]. Nature, 2023, 612: 1-10. DOI: 10.12/abc
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("[FAIL]", result.stdout)
        self.assertIn("DOI 格式非法「10.12/abc」", result.stdout)

    def test_doi_missing_suffix_fails(self):
        master = """## S2 参考文献
- [1] Zhang Y. Deep learning for X[J]. Nature, 2023: 1-10. DOI: 10.1038/
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("DOI 格式非法", result.stdout)


class ConsistencyTest(unittest.TestCase):
    def test_same_doi_different_years_fails_and_lists_entries(self):
        master = """## S2 参考文献
- [1] Zhang Y. Deep learning for X[J]. Nature, 2023, 612: 1-10. DOI: 10.1038/abc123
- [2] Zhang Y. Deep learning for X[J]. Nature, 2022, 612: 1-10. DOI: 10.1038/abc123
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("同 DOI「10.1038/abc123」年份不一致（2022 vs 2023，", result.stdout)

    def test_same_doi_different_titles_fails(self):
        master = """## S2 参考文献
- [1] Zhang Y. Deep learning for X[J]. Nature, 2023, 612: 1-10. DOI: 10.1038/abc123
- [2] Zhang Y. Deep learning for Y[J]. Nature, 2023, 612: 1-10. DOI: 10.1038/abc123
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("同 DOI「10.1038/abc123」题名不一致", result.stdout)

    def test_same_title_different_dois_fails(self):
        master = """## S2 参考文献
- [1] Zhang Y. Deep learning for X[J]. Nature, 2023, 612: 1-10. DOI: 10.1038/abc123
- [2] Zhang Y. Deep learning for X[J]. Nature, 2023, 612: 1-10. DOI: 10.1038/xyz999
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("同题名", result.stdout)
        self.assertIn("DOI 不一致", result.stdout)


class Gbt7714FormatTest(unittest.TestCase):
    def test_missing_type_tag_and_year_warn_without_failing(self):
        master = """## S2 参考文献
- [1] Zhang Y. Deep learning for X. Nature. DOI: 10.1038/abc123
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("[WARN]", result.stdout)
        self.assertIn("缺 GB/T 7714 文献类型标识", result.stdout)
        self.assertIn("条目缺出版年份", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)

    def test_implausible_year_warns(self):
        master = """## S2 参考文献
- [1] Zhang Y. Deep learning for X[J]. Nature, 2099, 612: 1-10. DOI: 10.1038/abc123
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("在合理范围", result.stdout)


FULLWIDTH_REFS = """# 母版
## S9 参考文献
［1］ Zhang Y. Deep learning for X[J]. Nature, 2023, 612: 1-10. DOI: 10.1038/abc123
2. Li M. Graph embeddings at scale[C]. NeurIPS, 2021: 100-112. doi.org/10.1109/xyz987
"""


class NonBulletNumberingTest(unittest.TestCase):
    """Full-width ［1］ and bare "N." numbering must still parse as entries."""

    def test_fullwidth_numbered_entries_counted_as_bibliography(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, FULLWIDTH_REFS)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("文献页条目 2", result.stdout)
        self.assertNotIn("母版无参考文献页/段", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)
        self.assertNotIn("[WARN]", result.stdout)

    def test_fullwidth_numbered_entries_join_consistency_checks(self):
        # Both ［1］- and "2."-numbered entries carry the same DOI with
        # conflicting years — they must join the DOI group and FAIL.
        master = FULLWIDTH_REFS.replace(
            "2. Li M. Graph embeddings at scale[C]. NeurIPS, 2021: 100-112. "
            "doi.org/10.1109/xyz987",
            "2. Li M. Graph embeddings at scale[C]. NeurIPS, 2022: 100-112. "
            "doi.org/10.1038/abc123")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("同 DOI「10.1038/abc123」年份不一致（2022 vs 2023，", result.stdout)

    def test_section_with_unrecognized_entry_shape_is_not_misleading_skip(self):
        # No DOI anywhere: before the fix these lines dropped silently and
        # the INFO claimed the master had no reference section at all.
        master = """## S2 参考文献
［1］ Zhang Y. Deep learning for X. Nature, 2023.
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, master)])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("文献页条目 1", result.stdout)
        self.assertNotIn("母版无参考文献页/段", result.stdout)
        self.assertIn("[WARN]", result.stdout)


class CliSemanticsTest(unittest.TestCase):
    def test_no_arguments_exits_2(self):
        result = _run([])
        self.assertEqual(result.returncode, 2)

    def test_missing_file_exits_2(self):
        result = _run([Path(tempfile.gettempdir()) / "no-such-master.md"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("ERROR", result.stderr)

    def test_json_output_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run([_master(tmp, CLEAN_REFS), "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        for key in ("file", "entries", "exit", "counts", "findings"):
            self.assertIn(key, payload)
        self.assertEqual(payload["entries"],
                         {"total": 3, "bibliography": 2, "citations": 1})
        self.assertEqual(payload["exit"], 0)
        self.assertIn("offline", payload["online_crosscheck"])

    def test_deterministic_stdout_across_runs(self):
        master = """## S2 参考文献
- [1] Zhang Y. Deep learning for X[J]. Nature, 2023, 612: 1-10. DOI: 10.1038/abc123
- [2] Zhang Y. Deep learning for X[J]. Nature, 2022, 612: 1-10. DOI: 10.1038/abc123
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = _master(tmp, master)
            first = _run([path])
            second = _run([path])
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.returncode, second.returncode)
        self.assertEqual(first.returncode, 1)


if __name__ == "__main__":
    unittest.main()
