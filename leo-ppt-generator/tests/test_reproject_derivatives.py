#!/usr/bin/env python3
"""reproject_derivatives.py 单元测试（R-38 派生物重投影）：confirmed 基线
定位（含 post-confirm 链与链断；pending 退回版本不当真值）/ 新建投影与自指纹 /
篡改派生物后恢复一致 / 母版删图行投影同步删除 / slides.json 页集合漂移检测 /
流程字段继承 / 确定性 / 无 confirmed 基线 exit 2。"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reproject_derivatives.py"

MASTER_V1 = """# 母版 v1
confirmation: confirmed（测试基线）

## S1 封面
- 标题：增长质量
视觉行：图[F1] 模式:preserve 状态:vision-reviewed 焦点:核心指标 | 承载:全幅图

## S2 财务
- 标题：营收 1.24 亿元
视觉行：图[F2] 模式:overview+detail 状态:metadata-reviewed 焦点:趋势 | 承载:对比小表

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿元 | S2 | Q3 财报 | 合并 | 2026Q3 | 人民币元 | 引用 | yes | 2026-10-28 |

## 术语表
| 术语 | 缩写 | 首现页 |
| --- | --- | --- |
| 智能客服 | — | S2 |
"""


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ReprojectDerivativesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "finance"
        (self.root / "content").mkdir(parents=True)
        (self.root / "content" / "deck-master-v1.md").write_text(MASTER_V1, encoding="utf-8")
        self.manifest = self.root / "content" / "sources-manifest.json"
        self.glossary = self.root / "content" / "glossary-projection.json"

    def tearDown(self):
        self._tmp.cleanup()

    def reproject(self, *extra):
        return run("--project-root", str(self.root), "--json", *extra)

    def test_creates_both_projections_with_selfconsistent_fingerprint(self):
        proc = self.reproject()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["confirmed_master"], "deck-master-v1.md")
        self.assertEqual(payload["pages"], 2)
        self.assertEqual(payload["figure_lines"], 2)
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["generated_from"], "content/deck-master-v1.md")
        self.assertEqual([p["page_id"] for p in manifest["pages"]], ["slide_01", "slide_02"])
        v1 = manifest["pages"][0]["visuals"][0]
        self.assertEqual(v1["figure_id"], "F1")
        self.assertEqual(v1["handling_mode"], "preserve")
        self.assertEqual(v1["review_status"], "vision-reviewed")
        # contents_sha256 matches checker convention (sha256 of canonical minus field).
        body = {k: v for k, v in manifest.items() if k != "contents_sha256"}
        self.assertEqual(manifest["contents_sha256"],
                         hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest())
        glossary = json.loads(self.glossary.read_text(encoding="utf-8"))
        self.assertEqual(glossary["terms"][0]["cells"][0], "智能客服")
        self.assertEqual(glossary["number_ledger"][0]["value"], "1.24 亿元")
        self.assertEqual(glossary["master_sha256"],
                         hashlib.sha256((self.root / "content" / "deck-master-v1.md")
                                        .read_bytes()).hexdigest())

    def test_tampered_manifest_restored_and_drift_reported(self):
        self.reproject()
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["pages"][0]["visuals"][0]["handling_mode"] = "bogus-mode"
        self.manifest.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        dry = self.reproject("--dry-run")
        payload = json.loads(dry.stdout)
        self.assertTrue(any("漂移" in d or "不一致" in d for d in payload["drift"]))
        self.assertTrue(self.glossary.exists())
        proc = self.reproject()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rebuilt = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(rebuilt["pages"][0]["visuals"][0]["handling_mode"], "preserve")
        # Second run after repair reports a clean state.
        payload = json.loads(self.reproject("--dry-run").stdout)
        self.assertEqual([d for d in payload["drift"] if "slides" not in d], [])

    def test_master_figure_removed_syncs_projection(self):
        self.reproject()
        master = self.root / "content" / "deck-master-v1.md"
        text = master.read_text(encoding="utf-8").replace(
            "视觉行：图[F2] 模式:overview+detail 状态:metadata-reviewed 焦点:趋势 | 承载:对比小表",
            "视觉行：纯文字结论条")
        master.write_text(text, encoding="utf-8")
        proc = self.reproject()
        payload = json.loads(proc.stdout)
        self.assertTrue(any("母版已无图行 ['F2']" in d for d in payload["drift"]))
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["pages"][1]["visuals"], [])

    def test_post_confirm_chain_selects_highest_inheriting_version(self):
        (self.root / "content" / "deck-master-v2.md").write_text(
            "# 母版 v2\nrevision_kind: post-confirm（写回）\n\n## S1 封面\n视觉行：图[F1] 模式:preserve 状态:vision-reviewed\n", encoding="utf-8")
        proc = self.reproject()
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["confirmed_master"], "deck-master-v2.md")
        self.assertIn("deck-master-v1.md", payload["post_confirm_chain"])

    def test_pending_without_post_confirm_breaks_chain(self):
        (self.root / "content" / "deck-master-v2.md").write_text(
            "# 母版 v2\nconfirmation: pending\n\n## S1 封面\n视觉行：\n", encoding="utf-8")
        payload = json.loads(self.reproject().stdout)
        self.assertEqual(payload["confirmed_master"], "deck-master-v1.md")
        self.assertEqual(payload["post_confirm_chain"], [])

    def test_pending_post_confirm_rollback_not_projection_truth(self):
        # 页数/结构变化退回待确认：v2 带 pending + post-confirm 时是链断，
        # 投影真值回落 v1，未确认内容不得成为母版真值。
        (self.root / "content" / "deck-master-v2.md").write_text(
            "# 母版 v2\nconfirmation: pending\nrevision_kind: post-confirm\n\n"
            "## S1 封面\n## S2 结构变化页\n视觉行：图[F9] 模式:preserve 状态:vision-reviewed\n",
            encoding="utf-8")
        payload = json.loads(self.reproject().stdout)
        self.assertEqual(payload["confirmed_master"], "deck-master-v1.md")
        self.assertEqual(payload["post_confirm_chain"], [])
        # v2 的图行不得进投影（manifest 仍是 v1 口径：2 页 2 图行）。
        self.assertEqual(payload["pages"], 2)
        self.assertEqual(payload["figure_lines"], 2)

    def test_pending_rollback_breaks_chain_above_it(self):
        # v3（post-confirm 继承）叠在退回的 v2 之上：v2 链断使 v3 一并作废，
        # 基线回落 v1。
        (self.root / "content" / "deck-master-v2.md").write_text(
            "# 母版 v2\nconfirmation: pending\nrevision_kind: post-confirm\n\n## S1\n",
            encoding="utf-8")
        (self.root / "content" / "deck-master-v3.md").write_text(
            "# 母版 v3\nrevision_kind: post-confirm\n\n## S1\n", encoding="utf-8")
        payload = json.loads(self.reproject().stdout)
        self.assertEqual(payload["confirmed_master"], "deck-master-v1.md")
        self.assertEqual(payload["post_confirm_chain"], [])

    def test_flow_fields_carried_over_by_figure_id(self):
        self.reproject()
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["pages"][0]["visuals"][0].update({
            "tier": "引用", "source_class": "user-material",
            "source_ref": "sources/paper/fig1.png", "source_sha256": "ab" * 32,
        })
        self.manifest.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        self.reproject()
        rebuilt = json.loads(self.manifest.read_text(encoding="utf-8"))
        visual = rebuilt["pages"][0]["visuals"][0]
        self.assertEqual(visual["source_ref"], "sources/paper/fig1.png")
        self.assertEqual(visual["tier"], "引用")

    def test_slides_json_page_set_drift_detected(self):
        slides = {"slides": [{"number": 1, "title": "仅一页"}]}
        (self.root / "content" / "slides.json").write_text(
            json.dumps(slides, ensure_ascii=False), encoding="utf-8")
        payload = json.loads(self.reproject().stdout)
        self.assertTrue(any("S2" in d and "缺失" in d for d in payload["drift"]))

    def test_deterministic_output_between_runs(self):
        first = self.reproject("--dry-run").stdout
        second = self.reproject("--dry-run").stdout
        self.assertEqual(first, second)

    def test_no_confirmed_baseline_exits_two(self):
        (self.root / "content" / "deck-master-v1.md").write_text(
            "# 母版 v1\nconfirmation: pending\n\n## S1\n", encoding="utf-8")
        proc = self.reproject()
        self.assertEqual(proc.returncode, 2)

    def test_dry_run_writes_nothing(self):
        proc = self.reproject("--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.manifest.exists())
        self.assertFalse(self.glossary.exists())


if __name__ == "__main__":
    unittest.main()
