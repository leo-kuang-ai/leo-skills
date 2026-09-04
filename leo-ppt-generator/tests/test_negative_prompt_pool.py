"""负面语料参考池合同测试（UB1，方案 2026-09-02-002）。

覆盖：池文档存在性与结构契约、_load_pool/_pool_candidates 解析与匹配、
缺省行为（不传 --pool）不读池。
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / "scripts" / "draft_negative_prompts.py"
POOL_DOC = SKILL_DIR / "references" / "styles" / "00_索引" / "负面语料参考池.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("draft_negative_prompts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class NegativePromptPoolDocContract(unittest.TestCase):
    def test_pool_doc_exists_with_source_and_license_line(self):
        """池文档存在，且含来源登记（思想级改写口径）与快照日期。"""
        text = POOL_DOC.read_text(encoding="utf-8")
        self.assertIn("huashu-design", text)
        self.assertIn("思想级改写", text)
        self.assertIn("2026-09-02", text)

    def test_pool_doc_first_stage_groups_present(self):
        """首期覆盖组在场：通用 + 三派辐射家族组；每组 ≥3 条。"""
        mod = _load_module()
        groups = mod._load_pool(POOL_DOC)
        for name in ("通用", "东方意蕴", "中式载体", "质感专业"):
            self.assertIn(name, groups, f"缺首期组：{name}")
            self.assertGreaterEqual(
                len(groups[name]), 3, f"组 {name} 词条不足 3 条"
            )

    def test_pool_doc_group_names_match_library_family_dirs(self):
        """非通用组名须与 01_通用母版/ 家族目录名一致，保证路径匹配可靠。"""
        mod = _load_module()
        groups = mod._load_pool(POOL_DOC)
        root = SKILL_DIR / "references" / "styles" / "01_通用母版"
        family_dirs = {p.name for p in root.iterdir() if p.is_dir()}
        for name in groups:
            if name == "通用":
                continue
            self.assertIn(name, family_dirs, f"池组 {name} 无对应家族目录")


class PoolParsingAndMatching(unittest.TestCase):
    def test_load_pool_skips_usage_guide_section(self):
        """## 选用指引 段不参与解析。"""
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pool.md"
            p.write_text(
                "# 池\n\n## 组A\n- 不要使用高饱和撞色破坏基调\n\n"
                "## 选用指引\n- 这是一条说明不是词条\n",
                encoding="utf-8",
            )
            groups = mod._load_pool(p)
        self.assertEqual(groups, {"组A": ["不要使用高饱和撞色破坏基调"]})

    def test_pool_candidates_universal_group_always_applies(self):
        """通用组对所有 brief 适用；家族组仅路径命中时适用。"""
        mod = _load_module()
        groups = {
            "通用": ["通用负面词条一"],
            "东方意蕴": ["水墨负面词条一"],
        }
        hit = mod._pool_candidates(groups, {"01_通用母版", "东方意蕴", "x.md"})
        miss = mod._pool_candidates(groups, {"01_通用母版", "科技数字", "y.md"})
        self.assertIn("通用负面词条一", hit)
        self.assertIn("水墨负面词条一", hit)
        self.assertIn("通用负面词条一", miss)
        self.assertNotIn("水墨负面词条一", miss)

    def test_cli_without_pool_flag_leaves_default_untouched(self):
        """不传 --pool 时运行 dry-run 正常退出（缺省行为不变）。"""
        mod = _load_module()
        rc = mod.main(["--limit", "1"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
