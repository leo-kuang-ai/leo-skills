"""派生索引的源/输出摘要、分页、失败与旧清单兼容测试。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import capability_manifest as cm

BASE = {"type": "image", "style_name": "样式", "best_for": "汇报", "visual_direction": "网格",
        "canvas": {"density": "medium"}, "color_palette": {}, "typography": {}, "layout_patterns": ["对比"],
        "aliases": ["共享别名"]}


class StyleIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "skill"
        self.styles = self.root / "references/styles"
        self.styles.mkdir(parents=True)
        self.write("样式.md")
        self.out = self.styles / "generated"

    def write(self, name, brief=None):
        p = self.styles / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# 样式\n\n```json\n" + json.dumps(brief or BASE, ensure_ascii=False) + "\n```\n")
        return p

    def build(self):
        index = cm.build_style_index(self.root)
        return index, cm.render_style_index(index)

    def test_publish_then_check_is_read_only_and_deterministic(self):
        index, files = self.build()
        cm.publish_style_index(files, self.out)
        stamp = {p: p.stat().st_mtime_ns for p in self.out.rglob("*")}
        rebuilt, rebuilt_files = self.build()
        self.assertEqual(files, rebuilt_files)
        self.assertEqual(cm.check_style_index(rebuilt, rebuilt_files, self.out)[1], 0)
        self.assertEqual(stamp, {p: p.stat().st_mtime_ns for p in self.out.rglob("*")})

    def test_missing_and_corrupt_outputs_are_distinct_from_stale_source(self):
        index, files = self.build()
        self.assertEqual(cm.check_style_index(index, files, self.out)[0]["reason_code"], "style_index_missing")
        cm.publish_style_index(files, self.out)
        (self.out / "counts.md").write_text("坏快照")
        self.assertEqual(cm.check_style_index(index, files, self.out)[0]["reason_code"], "style_index_corrupt")
        self.write("样式.md", {**BASE, "best_for": "新汇报"})
        current, outputs = self.build()
        self.assertEqual(cm.check_style_index(current, outputs, self.out)[0]["reason_code"], "style_index_stale")

    def test_generated_content_and_unrelated_files_do_not_change_source_digest(self):
        original, _ = self.build()
        self.out.mkdir()
        (self.out / "foo.md").write_text("生成物")
        (self.root / "unrelated.txt").write_text("业务文件")
        self.assertEqual(original["source_digest"], self.build()[0]["source_digest"])

    def test_root_index_generated_region_is_not_a_recursive_input(self):
        root_index = self.styles / "00_索引/_INDEX.md"
        root_index.parent.mkdir()
        root_index.write_text("# 导航\n<!-- style-index:start -->\n旧生成段\n<!-- style-index:end -->\n")
        before, files = self.build()
        cm.publish_style_index(files, self.out)
        root_index.write_text("# 导航\n<!-- style-index:start -->\n新生成段\n<!-- style-index:end -->\n")
        after, after_files = self.build()
        self.assertEqual(before["source_digest"], after["source_digest"])
        self.assertNotEqual(before["navigation_sha256"], after["navigation_sha256"])
        self.assertEqual(cm.check_style_index(after, after_files, self.out)[0]["reason_code"], "style_index_corrupt")

    def test_alias_index_retains_all_matches(self):
        self.write("第二.md", {**BASE, "style_name": "第二"})
        index, _ = self.build()
        self.assertEqual(len(index["name_alias_index"]["共享别名"]), 2)

    def test_pagination_respects_bytes_and_has_continuation(self):
        rows = ["- " + str(i) + "中" * 300 for i in range(80)]
        files = cm._paged_markdown("facets/demo", "家族", rows, "0" * 64)
        self.assertGreater(len(files), 2)
        self.assertTrue(all(len(body) <= cm.PAGE_BYTES for body in files.values()))
        self.assertIn("下一页", files["facets/demo-001.md"].decode())
        self.assertEqual(sum(body.decode().count("\n- ") for body in files.values()), 80)

    def test_oversized_identity_is_rejected_not_truncated(self):
        with self.assertRaisesRegex(ValueError, "entry_too_large"):
            cm._paged_markdown("names", "名称", ["- " + "名" * 10000], "0" * 64)

    def test_schema_failure_stops_output_before_publish(self):
        index, _ = self.build()
        index["entries"][0]["scope"] = "unknown-scope"
        with self.assertRaisesRegex(ValueError, "schema_invalid"):
            cm.render_style_index(index)

    def test_duplicate_names_prevent_publication(self):
        self.write("other/same.md")
        with self.assertRaisesRegex(ValueError, "duplicate_style_name"):
            self.build()
        self.assertFalse(self.out.exists())

    def test_declared_role_conflict_cannot_publish_as_unknown(self):
        self.write("样式.md", {**BASE, "asset_role": ["style"]})
        with self.assertRaisesRegex(ValueError, "asset_role_invalid"):
            self.build()

    def test_failed_generation_rename_restores_previous_snapshot(self):
        _, files = self.build()
        cm.publish_style_index(files, self.out)
        original_rename = Path.rename

        def interrupted(path, target):
            if path.name == "generation":
                raise OSError("模拟发布中断")
            return original_rename(path, target)

        with mock.patch.object(Path, "rename", interrupted), self.assertRaises(OSError):
            cm.publish_style_index({**files, "counts.md": b"new"}, self.out)
        self.assertEqual((self.out / "counts.md").read_bytes(), files["counts.md"])
        self.assertFalse(self.out.with_name("generated.previous").exists())

    def test_source_add_move_delete_keep_exact_asset_set(self):
        added = self.write("nested/第二.md", {**BASE, "style_name": "第二"})
        index, _ = self.build()
        self.assertEqual(index["counts"]["assets"], 2)
        added.rename(self.styles / "moved.md")
        moved, _ = self.build()
        self.assertNotEqual(index["source_digest"], moved["source_digest"])
        self.assertEqual({e["path"] for e in moved["entries"]}, {"references/styles/样式.md", "references/styles/moved.md"})
        (self.styles / "moved.md").unlink()
        self.assertEqual(self.build()[0]["counts"]["assets"], 1)

    def test_publishing_to_symlink_is_rejected(self):
        target = Path(self.tmp.name) / "outside"
        target.mkdir()
        self.out.symlink_to(target)
        _, files = self.build()
        with self.assertRaisesRegex(ValueError, "symlink"):
            cm.publish_style_index(files, self.out)


if __name__ == "__main__":
    unittest.main()
