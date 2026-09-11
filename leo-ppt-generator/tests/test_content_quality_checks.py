#!/usr/bin/env python3
"""check_content_quality.py（评测侧 L0 机检编排器）的检测边界单测。

方案 005 D2 验证口径：检出正文漏登、错页登记、投影丢失、未知版式、
同数异义的机检边界；覆盖健康样例、输入缺失、空内容与解析错误。
同数异义（同数异主体/期间/单位）按方案属 L1 语义判定——机检只允许产出
candidates_for_judge，不得自动判 fail。
"""
import importlib.util
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "evals" / "fixtures" / "scripts" / "check_content_quality.py"

spec = importlib.util.spec_from_file_location("ccq", SCRIPT)
ccq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccq)


def page(header: str, title: str, bullets: list[str], extra: str = "") -> str:
    body = (f"## {header}（页面角色：证据；argument_role：论据）\n"
            f"- 标题：{title}\n")
    for b in bullets:
        body += f"- {b}\n"
    body += "- 视觉行：P5｜要点 1→card，2→card\n"
    body += "- 备注：speaker_script：讲稿…… engineering：工程备注……\n"
    body += extra
    return body


HEALTHY_BULLETS = [
    "营收 1.24 亿元，环比增长 18%【引用|src:Q3 财报】",
    "大客户续约率 91%【引用|src:CRM】",
]
HEALTHY_LEDGER_S2 = """## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.24 亿 | S2 | Q3 财报 | 财务口径 | 2026-Q3 | 元 | 引用 | yes | 2026-09-30 |
| 18% | S2 | Q3 财报 | 环比 | 2026-Q3 | % | 引用 | yes | 2026-09-30 |
| 91% | S2 | CRM | logo 口径 | 2026-09 | % | 引用 | yes | 2026-09-30 |
"""

HEALTHY_MASTER = (
    page("S1 封面", "季度经营总结",
         ["- 主线：增长质量优先"])
    .replace("- 视觉行：P5｜要点 1→card，2→card", "- 视觉行：P1｜封面")
    .replace("（页面角色：证据；argument_role：论据）", "（页面角色：开场）")
    + page("S2 增长证据", "1.24 亿营收支撑增长质量", HEALTHY_BULLETS)
    + page("S3 收束", "行动项", ["- 下季度发布 v2.0"])
    .replace("（页面角色：证据；argument_role：论据）", "（页面角色：收束）")
    + HEALTHY_LEDGER_S2
)


class LedgerCoverageTest(unittest.TestCase):
    def test_healthy_sample_passes_coverage(self):
        result = ccq.check_ledger_coverage(HEALTHY_MASTER)
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_detects_bullet_number_missing_from_ledger(self):
        # 正文漏登：要点出现 37 家但登记表无该行
        bad = HEALTHY_MASTER.replace("大客户续约率 91%【引用|src:CRM】",
                                     "大客户续约率 91%【引用|src:CRM】，新签 37 家")
        result = ccq.check_ledger_coverage(bad)
        self.assertEqual(result["status"], "fail")
        self.assertIn("37", result["detail"])

    def test_detects_wrong_page_registration(self):
        # 错页登记：91% 登记到 S3 而正文在 S2
        wrong = HEALTHY_LEDGER_S2.replace("| 91% | S2 |", "| 91% | S3 |")
        result = ccq.check_ledger_coverage(HEALTHY_MASTER.replace(
            HEALTHY_LEDGER_S2, wrong))
        self.assertEqual(result["status"], "fail")
        self.assertIn("91%", result["detail"])

    def test_year_numbers_are_exempt(self):
        with_year = HEALTHY_MASTER.replace(
            "- 视觉行：P5｜要点 1→card，2→card\n",
            "- 视觉行：P5｜要点 1→card，2→card\n- 2026 年 Q3 全景回顾\n", 1)
        # 2026 为裸年份，不应要求登记
        result = ccq.check_ledger_coverage(with_year)
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_estimated_numbers_still_require_ledger_row(self):
        # 估算级数字同样须登记（登记表以证据等级区分，覆盖不因 tier 豁免）
        bad = HEALTHY_MASTER.replace(
            "- 视觉行：P5｜要点 1→card，2→card\n",
            "- 视觉行：P5｜要点 1→card，2→card\n- 明年营收约 2 亿（估算）\n", 1)
        result = ccq.check_ledger_coverage(bad)
        self.assertEqual(result["status"], "fail")
        self.assertIn("2亿", result["detail"])


class DensityAndNotesTest(unittest.TestCase):
    def test_density_healthy(self):
        result = ccq.check_density(HEALTHY_MASTER)
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_density_flags_over_limit_bullets(self):
        bloated = page("S2 证据", "超限页", [f"- 要点{i}：内容{i}" for i in range(5)])
        result = ccq.check_density(bloated)
        self.assertEqual(result["status"], "fail")
        self.assertIn("5 条超", result["detail"])

    def test_density_char_budget_is_reported_warning_not_fail(self):
        # M0 校准：80 字合计降为如实报告（产品合同为行数制），计数/分行仍硬
        long_text = "很长的论点内容" * 15
        bulky = page("S2 证据", "超字页", [f"- {long_text}【引用|src:X】"])
        result = ccq.check_density(bulky)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["char_over_80"])

    def test_visual_row_subbullets_not_counted(self):
        # 视觉行下的缩进注释行不是要点（真实 U01 母版格式回归）
        body = page("S2 证据", "标题", ["- 要点甲【引用|src:X】"])
        body = body.replace(
            "- 备注：",
            "  - 固定件：页码右下\n  - 约束摘抄：可信克制 conf 0.58\n- 备注：")
        result = ccq.check_density(body)
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_dates_and_pcodes_not_metric_numbers(self):
        line = "ARR 1.86 亿元(同比 +62%,2025-08→2026-08) 走查 P1 title 槽 ≤8 字"
        stripped = ccq.strip_non_metric(line)
        keys = [d for d, _ in __import__("check_content_facts").extract_number_keys(stripped)]
        self.assertIn("1.86亿", keys)
        self.assertIn("62%", keys)
        self.assertNotIn("08", keys)
        self.assertNotIn("8", keys)

    def test_outline_table_row_counting(self):
        outline = "# 大纲\n## 叙事骨架\n| 页 | 角色 |\n| --- | --- |\n" + \
                  "".join(f"| {i} | 证据 |\n" for i in range(1, 13))
        self.assertEqual(ccq.outline_page_count(outline), 12)
        self.assertEqual(ccq.outline_page_count("## S1 x\n## S2 y"), 2)

    def test_outline_three_real_formats(self):
        # U15 实测：`- S1 封面(开场,cover):…` 列表式；U13 实测：`### 第 N 页`
        s_list = "# 大纲\n" + "".join(f"- S{i} 页面{i}\n" for i in range(1, 13))
        self.assertEqual(ccq.outline_page_count(s_list), 12)
        numbered = "# 大纲\n## 页面序列\n" + \
            "".join(f"### 第 {i} 页 · 内容{i}\n" for i in range(1, 12))
        self.assertEqual(ccq.outline_page_count(numbered), 11)

    def test_numbered_bullets_recognized(self):
        # U15 实测：母版要点用「1. 文字」编号式（非「- 要点 1:」）
        body = ("## S2 结论（页面角色：证据）\n- 标题：论断\n"
                "1. 本次飞行回收结果为成功，参数在包线内【引用|src：材料二】\n"
                "2. 两项待补数据不进入变更依据【引用|src：材料六】\n"
                "- 视觉行：要点1→卡组\n"
                "- 备注：speaker_script：x engineering：y\n")
        self.assertEqual(len(ccq.page_bullets(body)), 2)
        density = ccq.check_density(body)
        self.assertEqual(density["status"], "pass", density["detail"])

    def test_sensor_ids_and_canvas_not_metrics(self):
        stripped = ccq.strip_non_metric("TP-07 临近阈值；画布 2560×1440")
        import check_content_facts as f
        keys = [d for d, _ in f.extract_number_keys(stripped)]
        self.assertEqual(keys, [])

    def test_ledger_multi_page_column_registers_all_pages(self):
        # 真实 U01 登记表回归：页列为多页清单（S1,S2,S3,S4）
        master = (
            page("S1 封面", "标题", ["- NRR 114% 支撑结论【引用|src:X】"])
            + page("S2 证据", "标题", ["- NRR 114% 再证【引用|src:X】"])
            + page("S3 收束", "标题", ["- 行动"])
            + "## 数字登记表\n"
            + "| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |\n"
            + "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            + "| 114% | S1,S2 | X | NRR | 2026-08 | % | 引用 | yes | 2026-08 |\n"
        )
        result = ccq.check_ledger_coverage(master)
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_ledger_slash_list_unit_expansion(self):
        # 「28/15/9 亿」+单位亿元：逐数拼装后 28 亿/15 亿/9 亿 均可对账
        master = (
            page("S1 证据", "标题", ["- JQ 年营收 28 亿【引用|src:X】",
                                    "- FH 年营收 15 亿【引用|src:X】"])
            + "## 数字登记表\n"
            + "| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |\n"
            + "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            + "| 28/15/9 亿 | S1 | X | 营收 | 2026 | 亿元 | 引用 | yes | 2026 |\n"
        )
        result = ccq.check_ledger_coverage(master)
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_projection_prefers_master_over_draft_json(self):
        # 草案 JSON（含已否决映射）不得覆盖母版视觉行定稿 P 码
        master = HEALTHY_MASTER.replace("视觉行：P5｜", "视觉行：P2｜")
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "capacity-spec-draft.json"
            draft.write_text(json.dumps({"slides": [
                {"page": 1, "layout": "P1"}, {"page": 2, "layout": "P99"},
                {"page": 3, "layout": "P12"}]}), encoding="utf-8")
            bank = {lid for lid, _ in ccq._load_layout_bank()}
            pcode, proj, missing = ccq.check_pcode_and_project(
                master, [draft], bank)
            self.assertEqual(pcode["status"], "pass", pcode["detail"])
            self.assertEqual(
                [s["layout"] for s in proj["slides"] if s["page"] == 2], ["P2"])

    def test_density_ledger_page_allows_six(self):
        bullets = [f"- 台账行{i}：数值{i}" for i in range(6)]
        tbl = page("S2 证据", "台账页", bullets,
                   extra="- 视觉行（台账表格）：P8\n")
        result = ccq.check_density(tbl + "## 数字登记表\n| 数值 | 页 |\n| --- | --- |\n")
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_notes_missing_column_fails(self):
        broken = HEALTHY_MASTER.replace("engineering：工程备注……", "")
        result = ccq.check_notes_columns(broken)
        self.assertEqual(result["status"], "fail")
        self.assertIn("engineering", result["detail"])

    def test_notes_placeholder_residue_fails(self):
        dirty = HEALTHY_MASTER.replace("讲稿……", "讲稿……TODO 补齐")
        result = ccq.check_notes_columns(dirty)
        self.assertEqual(result["status"], "fail")
        self.assertIn("占位残留", result["detail"])


class PcodeProjectionTest(unittest.TestCase):
    def test_unknown_pcode_fails(self):
        master = HEALTHY_MASTER.replace("视觉行：P5｜", "视觉行：P99｜")
        bank = {lid for lid, _ in ccq._load_layout_bank()}
        pcode, _, missing = ccq.check_pcode_and_project(master, [], bank)
        self.assertEqual(pcode["status"], "fail")
        self.assertIn("P99", pcode["detail"])
        self.assertEqual(missing, [])

    def test_projection_missing_page_is_error(self):
        # 投影丢失：S3 无调度记录且视觉行无 P 码
        master = HEALTHY_MASTER.replace(
            "- 视觉行：P1｜封面", "- 视觉行：封面")
        bank = {lid for lid, _ in ccq._load_layout_bank()}
        pcode, _, missing = ccq.check_pcode_and_project(master, [], bank)
        self.assertEqual(pcode["status"], "error")
        self.assertIn("1", str(missing))

    def test_dispatch_record_takes_precedence(self):
        with tempfile.TemporaryDirectory() as td:
            dispatch = Path(td) / "slides.json"
            dispatch.write_text(json.dumps({"slides": [
                {"page": 1, "layout": "P1"}, {"page": 2, "layout": "P5"},
                {"page": 3, "layout": "P12"}]}), encoding="utf-8")
            bank = {lid for lid, _ in ccq._load_layout_bank()}
            pcode, projection, missing = ccq.check_pcode_and_project(
                HEALTHY_MASTER, [dispatch], bank)
            self.assertEqual(pcode["status"], "pass", pcode["detail"])
            self.assertEqual(missing, [])
            self.assertEqual(len(projection["slides"]), 3)

    def test_capacity_missing_pages_not_fake_projected(self):
        result = ccq._run_capacity({"slides": []}, [3], None)
        self.assertEqual(result["status"], "error")
        self.assertIn("不做假投影", result["detail"])


class ClassificationTest(unittest.TestCase):
    def test_same_number_different_context_is_candidate_not_fail(self):
        # 同数异义边界：check_content_facts exit 1 只能是候选，语义归 L1
        run = {"exit_code": 1, "stdout_tail": "18% 不在材料数字集合",
               "stderr_tail": "", "command": "check_content_facts …"}
        item = ccq.classify_checker("A2.3-fact-candidates", run)
        self.assertEqual(item["status"], "candidates_for_judge")

    def test_ledger_tier_mismatch_is_tool_contract_error(self):
        # 已知兼容性边界：「用户确认」四级 vs VALID_TIERS 三级 → error 而非 fail
        run = {"exit_code": 1,
               "stdout_tail": "证据等级『用户确认』不在 {引用,估算,示意}",
               "stderr_tail": "", "command": "check_number_ledger …"}
        item = ccq.classify_checker("A2.2-ledger-structure", run)
        self.assertEqual(item["status"], "error")
        self.assertEqual(item["error_kind"], "tool_contract_mismatch")

    def test_prose_exit1_is_quality_fail(self):
        run = {"exit_code": 1, "stdout_tail": "翻案腔 2 处", "stderr_tail": "",
               "command": "check_deck_prose …"}
        item = ccq.classify_checker("A3.3-prose", run)
        self.assertEqual(item["status"], "fail")

    def test_tool_exit2_is_error(self):
        run = {"exit_code": 2, "stdout_tail": "", "stderr_tail": "用法错误",
               "command": "check_master_contract …"}
        item = ccq.classify_checker("A1.2-promises+contract", run)
        self.assertEqual(item["status"], "error")
        self.assertEqual(item["error_kind"], "tool")

    def test_capacity_soft_over_is_warning_not_fail(self):
        run = {"exit_code": 0,
               "stdout_tail": "over:count:cells 条数 7 超上限 6（软带内）",
               "stderr_tail": "", "command": "check_deck_geometry --capacity …"}
        item = ccq.classify_checker("A5.3-capacity", run)
        self.assertEqual(item["status"], "warning")


class TermLiteralScanTest(unittest.TestCase):
    def test_literal_hit_is_advisory_candidate(self):
        unit = {"id": "u01", "slug": "internet-tech"}
        # HEALTHY_MASTER 不含 u01 表内的「」误用字面量 → 0 命中仍为 candidates
        result = ccq.check_term_literals(unit, HEALTHY_MASTER, HEALTHY_MASTER)
        self.assertEqual(result["status"], "candidates_for_judge")

    def test_missing_terminology_table_is_error(self):
        unit = {"id": "uXX", "slug": "no-such"}
        result = ccq.check_term_literals(unit, "", "")
        self.assertEqual(result["status"], "error")


class RenderProvenanceTest(unittest.TestCase):
    @staticmethod
    def _png_bytes(width: int = 1, height: int = 1) -> bytes:
        def chunk(kind: bytes, payload: bytes) -> bytes:
            return (struct.pack(">I", len(payload)) + kind + payload
                    + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

        row = b"\x00\xff\xff\xff" * width
        raw = row * height
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw))
                + chunk(b"IEND", b""))

    def _write_receipt(self, root: Path, *, artifact: Path | None = None,
                       out_sha256: str | None = None) -> Path:
        project = root / "project" / "render"
        project.mkdir(parents=True, exist_ok=True)
        artifact = artifact or (project / "slide.png")
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(self._png_bytes())
        digest = out_sha256 or hashlib.sha256(artifact.read_bytes()).hexdigest()
        receipt = project / "slide.png.render.json"
        receipt.write_text(json.dumps({
            "schema_version": 1,
            "kind": "render_provenance",
            "backend": "render:html",
            "renderer": "playwright",
            "out": str(artifact),
            "out_sha256": digest,
            "width": 1,
            "height": 1,
        }), encoding="utf-8")
        return receipt

    def test_receipt_requires_real_artifact_and_matching_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt = self._write_receipt(root)
            result = ccq.check_render_structure([receipt], root / "project")
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_fake_receipt_without_out_cannot_pass(self):
        with tempfile.TemporaryDirectory() as td:
            receipt = Path(td) / "fake.render.json"
            receipt.write_text(json.dumps({
                "schema_version": 1,
                "kind": "render_provenance",
                "backend": "render:html",
                "renderer": "fake",
                "out_sha256": "0" * 64,
                "width": 1,
                "height": 1,
            }), encoding="utf-8")
            result = ccq.check_render_structure([receipt], Path(td))
        self.assertEqual(result["status"], "error")
        self.assertIn("out 缺失", result["detail"])

    def test_receipt_hash_mismatch_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt = self._write_receipt(root, out_sha256="0" * 64)
            result = ccq.check_render_structure([receipt], root / "project")
        self.assertEqual(result["status"], "error")
        self.assertIn("out_sha256", result["detail"])

    def test_png_bytes_and_dimensions_must_match_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt = self._write_receipt(root)
            data = json.loads(receipt.read_text(encoding="utf-8"))
            artifact = Path(data["out"])
            artifact.write_bytes(b"signed-but-not-a-png")
            data["out_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
            receipt.write_text(json.dumps(data), encoding="utf-8")
            result = ccq.check_render_structure([receipt], root / "project")
        self.assertEqual(result["status"], "error")
        self.assertIn("产物格式无效", result["detail"])

    def test_png_dimensions_must_match_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt = self._write_receipt(root)
            data = json.loads(receipt.read_text(encoding="utf-8"))
            data["width"] = 2560
            receipt.write_text(json.dumps(data), encoding="utf-8")
            result = ccq.check_render_structure([receipt], root / "project")
        self.assertEqual(result["status"], "error")
        self.assertIn("收据尺寸", result["detail"])

    def test_receipt_cannot_escape_project_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outside = root / "outside.png"
            receipt = self._write_receipt(root, artifact=outside)
            result = ccq.check_render_structure([receipt], root / "project")
        self.assertEqual(result["status"], "error")
        self.assertIn("越出 project/", result["detail"])


class ScopeContainmentTest(unittest.TestCase):
    def test_neutral_named_file_outside_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "project").mkdir()
            (root / "notes.txt").write_text("artifact", encoding="utf-8")
            violations = ccq.find_scope_violations(root)
        self.assertEqual(violations, ["notes.txt"])

    def test_external_file_and_project_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "project"
            project.mkdir()
            outside = root / "outside.bin"
            outside.write_bytes(b"x")
            (project / "alias.bin").symlink_to(outside)
            violations = ccq.find_scope_violations(root)
        self.assertEqual(violations, ["outside.bin", "project/alias.bin"])


class CliBoundaryTest(unittest.TestCase):
    """CLI 端到端边界：输入缺失 / 空内容 / 健康样例的退出码与报告结构。"""

    def _run(self, unit: str, unit_dir: Path):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--unit", unit,
             "--unit-dir", str(unit_dir)],
            capture_output=True, text=True)
        return proc

    def test_missing_unit_dir_exits_2(self):
        proc = self._run("u01", Path("/nonexistent-dir-xyz"))
        self.assertEqual(proc.returncode, 2)

    def test_unknown_unit_exits_2(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("u99", Path(td))
            self.assertEqual(proc.returncode, 2)

    def test_empty_project_dir_blocks_with_veto_error(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "project").mkdir()
            proc = self._run("u01", Path(td))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("VETO-docs-on-disk", proc.stdout)
            self.assertIn("error", proc.stdout)

    def test_master_without_pages_reports_page_fail_not_crash(self):
        # 空内容/解析错误边界：空母版不崩溃，逐项产出可读结论
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "project" / "content"
            proj.mkdir(parents=True)
            (proj / "outline-v1.md").write_text("（空大纲）", encoding="utf-8")
            (proj / "deck-master-v1.md").write_text("（空母版）", encoding="utf-8")
            proc = self._run("u01", Path(td))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("A1.2-pages", proc.stdout)

    def test_healthy_minimal_run_reports_expected_items(self):
        # 健康样例：核心补测项 pass；wrapped 检查器对该迷你母版的结论逐项在场
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "project" / "content"
            proj.mkdir(parents=True)
            (proj / "outline-v1.md").write_text(HEALTHY_MASTER, encoding="utf-8")
            (proj / "deck-master-v1.md").write_text(HEALTHY_MASTER, encoding="utf-8")
            out = Path(td) / "machine-report.json"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--unit", "u01",
                 "--unit-dir", str(Path(td)), "--out", str(out)],
                capture_output=True, text=True)
            report = json.loads(out.read_text(encoding="utf-8"))
            by_id = {i["criterion_id"]: i for i in report["items"]}
            self.assertEqual(by_id["A2.2-coverage"]["status"], "pass",
                             by_id["A2.2-coverage"]["detail"])
            self.assertEqual(by_id["A3.4-notes"]["status"], "pass")
            self.assertEqual(by_id["VETO-docs-on-disk"]["status"], "pass")
            self.assertIn("A2.3-fact-candidates", by_id)
            self.assertIn("A5.2-pcode", by_id)
            self.assertIn("inventory", report)
            # 整体 exit 1：迷你母版不满足简报页数（12）等，属预期硬失败
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
