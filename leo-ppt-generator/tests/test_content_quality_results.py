#!/usr/bin/env python3
"""L1 判官引擎与结果汇总器的行为单测（方案 005 D3 验证口径）。

无证据 pass / 缺子项 / 仲裁缺失不能通过；否决与失败保留在固定分母；
布尔校准失效禁止达标结论；重试账完整留存可重建。全部 mock 模型调用，
不产生真实费用。
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "evals" / "fixtures" / "scripts"

sys.path.insert(0, str(SCRIPTS))
import judge_content_common as jcc  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "scq", SCRIPTS / "summarize_content_quality.py")
scq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scq)


def fake_call(text: str):
    def _call(family, prompt, timeout=600):
        return {"ok": True, "text": text, "usage": 1234,
                "command": "mock", "returncode": 0, "stderr": ""}
    return _call


def valid_verdict(dim: str) -> dict:
    return {
        "dimension": dim, "model_self_report": "mock",
        "subcriteria": [
            {"criterion_id": f"{dim}.{i}", "status": "pass",
             "evidence": f"S{i} 原文短引", "reason": "核对通过",
             "failure_forms_excluded": ["a", "b"]}
            for i in range(1, len(jcc.DIMENSIONS[dim]["subcriteria"]) + 1)
        ],
        "dimension_conclusion": "ok", "triage_score_0_4": 3,
    }


def make_pkg(td: Path) -> Path:
    pkg = td / "PKG-test"
    pkg.mkdir()
    (pkg / "DOC-master.md").write_text("## S1 封面\n- 标题：X\n", encoding="utf-8")
    (pkg / "REF-machine-report.json").write_text("{}", encoding="utf-8")
    return pkg


class ExtractJsonTest(unittest.TestCase):
    def test_fenced_and_noise(self):
        text = '前言```json\n{"a": 1}\n```后记'
        self.assertEqual(jcc.extract_json(text), {"a": 1})

    def test_invalid(self):
        self.assertIsNone(jcc.extract_json("毫无 JSON"))
        self.assertIsNone(jcc.extract_json('{"broken": '))


class ValidateVerdictTest(unittest.TestCase):
    def test_valid_passes(self):
        self.assertEqual(jcc.validate_verdict(valid_verdict("A1"), "A1"), [])

    def test_no_evidence_pass_is_invalid(self):
        v = valid_verdict("A1")
        v["subcriteria"][0]["evidence"] = ""
        problems = jcc.validate_verdict(v, "A1")
        self.assertTrue(any("无证据" in p for p in problems))

    def test_pass_without_excluded_forms_invalid(self):
        v = valid_verdict("A1")
        v["subcriteria"][0]["failure_forms_excluded"] = []
        self.assertTrue(any("未列已排除" in p
                            for p in jcc.validate_verdict(v, "A1")))

    def test_missing_subcriterion_invalid(self):
        v = valid_verdict("A1")
        v["subcriteria"] = v["subcriteria"][:-1]
        self.assertTrue(any("缺子判据" in p
                            for p in jcc.validate_verdict(v, "A1")))

    def test_na_without_reason_invalid(self):
        v = valid_verdict("A1")
        v["subcriteria"][0] = {"criterion_id": "A1.1",
                               "status": "not_applicable"}
        self.assertTrue(any("not_applicable 缺理由" in p
                            for p in jcc.validate_verdict(v, "A1")))

    def test_illegal_status_invalid(self):
        v = valid_verdict("A1")
        v["subcriteria"][0]["status"] = "great"
        self.assertTrue(any("非法状态" in p
                            for p in jcc.validate_verdict(v, "A1")))

    def test_dimension_schema_rejects_wrong_dimension_and_duplicate(self):
        v = valid_verdict("A1")
        v["dimension"] = "A2"
        v["subcriteria"].append(dict(v["subcriteria"][0]))
        problems = jcc.validate_verdict(v, "A1")
        self.assertTrue(any("dimension" in p for p in problems))
        self.assertTrue(any("重复" in p for p in problems))

    def test_dimension_schema_rejects_bad_triage_type(self):
        v = valid_verdict("A1")
        v["triage_score_0_4"] = "3"
        self.assertTrue(any("triage_score_0_4" in p
                            for p in jcc.validate_verdict(v, "A1")))

    def test_single_arbitration_schema_requires_evidence_and_choice(self):
        problems = jcc.validate_arbitration_verdict(
            {"criterion_id": "A1.1", "status": "pass", "evidence": "x"},
            "A1.1")
        self.assertTrue(any("失败形态" in p for p in problems))
        self.assertTrue(any("chosen_side" in p for p in problems))


class RunJudgeRetryTest(unittest.TestCase):
    def test_invalid_then_valid_retries_and_keeps_both_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            pkg = make_pkg(Path(td))
            out = Path(td) / "judge-out"
            calls = {"n": 0}

            def call(family, prompt, timeout=600):
                calls["n"] += 1
                return fake_call("垃圾输出" if calls["n"] == 1
                                 else json.dumps(valid_verdict("A1"),
                                                 ensure_ascii=False))(family, prompt)
            result = jcc.run_judge("A1", pkg, "glml", out, call_fn=call)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(len(result["attempts"]), 2)
            self.assertEqual(result["attempts"][0]["parse"], "invalid_json")
            # 重试账留痕：两次原始输出都在盘上
            self.assertTrue((out / "A1-glml.attempt1.txt").exists())
            self.assertTrue((out / "A1-glml.attempt2.txt").exists())
            self.assertIn("垃圾输出",
                          (out / "A1-glml.attempt1.txt").read_text(encoding="utf-8"))

    def test_persistent_invalid_is_error_not_default_pass(self):
        with tempfile.TemporaryDirectory() as td:
            pkg = make_pkg(Path(td))
            result = jcc.run_judge("A2", pkg, "gpt", Path(td) / "o2",
                                   call_fn=fake_call("不是 JSON"))
            self.assertEqual(result["status"], "error")
            self.assertEqual(len(result["attempts"]), 2)

    def test_model_service_failure_is_error_with_attempt_logged(self):
        def boom(family, prompt, timeout=600):
            raise RuntimeError("service unavailable")

        with tempfile.TemporaryDirectory() as td:
            pkg = make_pkg(Path(td))
            result = jcc.run_judge("A3", pkg, "glml", Path(td) / "o3",
                                   call_fn=boom)
            self.assertEqual(result["status"], "error")
            self.assertTrue(all("error" in a for a in result["attempts"]))

    def test_no_evidence_pass_verdict_rejected(self):
        v = valid_verdict("A4")
        v["subcriteria"][0]["evidence"] = "  "
        with tempfile.TemporaryDirectory() as td:
            pkg = make_pkg(Path(td))
            result = jcc.run_judge("A4", pkg, "glml", Path(td) / "o4",
                                   call_fn=fake_call(json.dumps(v, ensure_ascii=False)))
            # 重试后仍是无效判定 → error（无证据 pass 不能通过）
            self.assertEqual(result["status"], "error")


class MergeLogicTest(unittest.TestCase):
    def test_machine_and_judge_both_pass(self):
        self.assertEqual(scq.merge_machine_judge("pass", "pass"), "pass")

    def test_machine_fail_overrides_judge_pass(self):
        self.assertEqual(scq.merge_machine_judge("fail", "pass"), "fail")

    def test_judge_fail_overrides_machine_pass(self):
        self.assertEqual(scq.merge_machine_judge("pass", "fail"), "fail")

    def test_missing_judge_is_error_not_pass(self):
        self.assertEqual(scq.merge_machine_judge("pass", None), "error")

    def test_candidates_resolved_by_judge_pass(self):
        # 机检候选（事实差异/术语字面命中）是透明中间态：判官语义裁决 pass 即
        # pass——判官是否真的核对了候选由 L2 植入缺陷校准把关
        self.assertEqual(
            scq.merge_machine_judge("candidates_for_judge", "pass"), "pass")

    def test_candidates_without_judge_is_error(self):
        self.assertEqual(
            scq.merge_machine_judge("candidates_for_judge", None), "error")

    def test_machine_error_not_excused_by_judge_pass(self):
        # 机器 error（如 style 记录缺失）不因判官 pass 变 pass
        self.assertEqual(scq.merge_machine_judge("error", "pass"), "error")

    def test_warning_transparent_when_judge_passes(self):
        self.assertEqual(scq.merge_machine_judge("warning", "pass"), "pass")

    def test_machine_na_judge_pass_is_pass(self):
        self.assertEqual(
            scq.merge_machine_judge("not_applicable", "pass"), "pass")

    def test_machine_side_transparent_statuses_not_folded_to_error(self):
        # U01 真实回归：机器侧仅 candidates_for_judge 时不得折叠为 error
        self.assertEqual(scq._merge_machine(["candidates_for_judge"]),
                         "candidates_for_judge")
        self.assertEqual(scq._merge_machine(["warning"]), "candidates_for_judge")
        self.assertEqual(scq._merge_machine(["pass", "warning"]), "pass")

    def test_all_na_is_na(self):
        self.assertEqual(
            scq.merge_machine_judge("not_applicable", "not_applicable"),
            "not_applicable")

    def test_blocked_propagates(self):
        self.assertEqual(scq.merge_machine_judge("pass", "blocked"), "blocked")


class DimensionAndTaskTest(unittest.TestCase):
    def test_dimension_pass(self):
        self.assertEqual(
            scq.dimension_status({"A1.1": "pass", "A1.2": "not_applicable"}),
            "pass")

    def test_dimension_fail_wins(self):
        self.assertEqual(
            scq.dimension_status({"A1.1": "pass", "A1.2": "fail"}), "fail")

    def test_dimension_incomplete_on_error(self):
        self.assertEqual(
            scq.dimension_status({"A1.1": "pass", "A1.2": "error"}),
            "incomplete")

    def test_all_na_dimension_is_config_error(self):
        self.assertEqual(
            scq.dimension_status({"A1.1": "not_applicable"}), "error")

    def test_task_veto_fails(self):
        dims = {d: "pass" for d in "A1 A2 A3 A4 A5".split()}
        self.assertEqual(scq.task_status(dims, "fail", True), "fail")

    def test_task_missing_artifacts_is_error(self):
        dims = {d: "pass" for d in "A1 A2 A3 A4 A5".split()}
        self.assertEqual(scq.task_status(dims, "pass", False), "error")

    def test_task_incomplete_dimension_blocks_pass(self):
        dims = {d: "pass" for d in "A1 A2 A3 A4 A5".split()}
        dims["A3"] = "incomplete"
        self.assertEqual(scq.task_status(dims, "pass", True), "incomplete")


def make_machine_report(items: dict) -> dict:
    return {"unit": "u01",
            "items": [{"criterion_id": k, "status": v, "detail": ""}
                      for k, v in items.items()],
            "summary": {}}


def write_judge_file(td: Path, name: str, verdict: dict, status="ok") -> Path:
    p = td / name
    p.write_text(json.dumps({"dimension": verdict["dimension"],
                             "family": "mock", "verdict": verdict,
                             "status": status, "attempts": []},
                            ensure_ascii=False), encoding="utf-8")
    return p


GOOD_MACHINE = {
    "VETO-docs-on-disk": "pass",
    "A1.2-pages": "pass", "A1.2-promises+contract": "pass",
    "A2.2-ledger-structure": "pass", "A2.2-coverage": "pass",
    "A2.2-diff-retention": "not_applicable", "A2.3-fact-candidates": "pass",
    "A3.2-density": "pass", "A3.3-prose": "pass", "A3.4-notes": "pass",
    "A4.1-term-literal": "pass", "A5.1-style-attribution": "pass",
    "A5.2-pcode": "pass", "A5.3-capacity": "pass",
    "A5.5-render-structure": "pass",
}


def judge_all_pass(dim: str) -> dict:
    return valid_verdict(dim)


class SummarizeUnitTest(unittest.TestCase):
    def _tmp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        return Path(self.td.name)

    @staticmethod
    def _family_dir(td: Path, name: str, mutate=None) -> Path:
        d = td / name
        d.mkdir()
        for dim in "A1 A2 A3 A4 A5".split():
            v = judge_all_pass(dim)
            if mutate and dim == mutate[0]:
                mutate[1](v)
            write_judge_file(d, f"{dim}-mock.json", v)
        return d

    def test_healthy_unit_passes(self):
        td = self._tmp()
        ja = self._family_dir(td, "A")
        jb = self._family_dir(td, "B")
        result = scq.summarize_unit(
            "u01", make_machine_report(GOOD_MACHINE), str(ja), str(jb), {})
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["dimensions"]["A1"], "pass")

    def test_machine_fail_makes_task_fail_even_if_judges_pass(self):
        td = self._tmp()
        items = dict(GOOD_MACHINE, **{"A3.3-prose": "fail"})
        result = scq.summarize_unit(
            "u01", make_machine_report(items),
            str(self._family_dir(td, "A")), str(self._family_dir(td, "B")), {})
        self.assertEqual(result["status"], "fail")

    def test_missing_family_b_is_error(self):
        td = self._tmp()
        result = scq.summarize_unit(
            "u01", make_machine_report(GOOD_MACHINE),
            str(self._family_dir(td, "A")), None, {})
        self.assertEqual(result["status"], "error")
        self.assertIn("判官 B", result["reason"])

    def test_family_disagreement_without_arbitration_is_error(self):
        td = self._tmp()

        def flip_fail(v):
            v["subcriteria"][0]["status"] = "fail"
            v["subcriteria"][0]["evidence"] = "S1 证据"

        result = scq.summarize_unit(
            "u01", make_machine_report(GOOD_MACHINE),
            str(self._family_dir(td, "A")),
            str(self._family_dir(td, "B", mutate=("A1", flip_fail))), {})
        self.assertEqual(result["subcriteria"]["A1"]["A1.1"], "error")

    def test_arbitration_resolves_disagreement(self):
        td = self._tmp()

        def flip_fail(v):
            v["subcriteria"][0]["status"] = "fail"
            v["subcriteria"][0]["evidence"] = "S1 证据"

        result = scq.summarize_unit(
            "u01", make_machine_report(GOOD_MACHINE),
            str(self._family_dir(td, "A")),
            str(self._family_dir(td, "B", mutate=("A1", flip_fail))),
            {"A1.1": "pass"})
        self.assertEqual(result["subcriteria"]["A1"]["A1.1"], "pass")

    def test_invalid_judge_file_is_error(self):
        td = self._tmp()
        broken = td / "broken"
        broken.mkdir()
        for dim in "A1 A2 A3 A4 A5".split():
            write_judge_file(broken, f"{dim}-mock.json",
                             judge_all_pass(dim), status="error")
        result = scq.summarize_unit(
            "u01", make_machine_report(GOOD_MACHINE),
            str(broken), str(self._family_dir(td, "B")), {})
        self.assertEqual(result["status"], "error")


class CalibrationGateTest(unittest.TestCase):
    def test_missing_calibration_blocks(self):
        ok, problems = scq.calibration_valid({})
        self.assertFalse(ok)
        self.assertTrue(any("记录缺失" in p for p in problems))

    def test_low_detection_blocks(self):
        calib = {"records": [{"judge": "glml", "defects_detected": 4,
                              "healthy_false_positives": 0,
                              "human_agreement": 0.9}]}
        ok, problems = scq.calibration_valid(calib)
        self.assertFalse(ok)

    def test_healthy_false_positive_blocks(self):
        calib = {"records": [{"judge": "glml", "defects_detected": 6,
                              "healthy_false_positives": 1,
                              "human_agreement": 0.9}]}
        self.assertFalse(scq.calibration_valid(calib)[0])

    def test_human_pending_blocks(self):
        # 人工未完成（agreement 负值）→ pending，不得由模型代签
        calib = {"records": [{"judge": "glml", "defects_detected": 6,
                              "healthy_false_positives": 0,
                              "human_agreement": -1}]}
        ok, problems = scq.calibration_valid(calib)
        self.assertFalse(ok)
        self.assertTrue(any("pending" in p for p in problems))

    def test_all_conditions_met_valid(self):
        calib = {"records": [
            {"judge": "glml", "defects_detected": 6,
             "healthy_false_positives": 0, "human_agreement": 0.85},
            {"judge": "gpt", "defects_detected": 5,
             "healthy_false_positives": 0, "human_agreement": 0.8}]}
        self.assertTrue(scq.calibration_valid(calib)[0])


class SuiteDenominatorTest(unittest.TestCase):
    def _unit(self, uid, status):
        return {"unit": uid, "status": status,
                "dimensions": {d: ("pass" if status == "pass" else "fail")
                               for d in "A1 A2 A3 A4 A5".split()}}

    def test_fail_stays_in_fixed_denominator(self):
        units = ([self._unit(f"u{i:02d}", "pass") for i in range(1, 11)]
                 + [self._unit(f"u{i:02d}", "fail") for i in range(11, 21)])
        report = scq.summarize_suite(units, [f"u{i:02d}" for i in range(13, 21)],
                                     {"records": []})
        self.assertEqual(report["evidence_boundary"]["render_visual_quality"], "not_run")
        self.assertIn("不得据此声称视觉质量", report["evidence_boundary"]["claim_ceiling"])
        run = report["runs"][0]
        self.assertEqual(len(run["passed"]) + len(run["failed"])
                         + len(run["incomplete"]), 20)
        self.assertEqual(report["denominators"]["tasks"], 20)
        self.assertEqual(report["denominators"]["g2"], 8)
        self.assertFalse(report["claim"]["allowed"])  # 校准缺失 → 不达标

    def test_incomplete_blocks_claim(self):
        units = ([self._unit(f"u{i:02d}", "pass") for i in range(1, 20)]
                 + [self._unit("u20", "incomplete")])
        units[-1]["dimensions"] = {d: "incomplete"
                                   for d in "A1 A2 A3 A4 A5".split()}
        good_calib = {"records": [
            {"judge": "glml", "defects_detected": 6,
             "healthy_false_positives": 0, "human_agreement": 0.9},
            {"judge": "gpt", "defects_detected": 6,
             "healthy_false_positives": 0, "human_agreement": 0.9}]}
        report = scq.summarize_suite(units, ["u13"], good_calib)
        self.assertFalse(report["claim"]["allowed"])
        self.assertTrue(any("未完成" in b for b in report["claim"]["blocks"]))

    def test_two_runs_x_counts_both_pass_only(self):
        run1 = [self._unit(f"u{i:02d}", "pass") for i in range(1, 21)]
        run2 = [self._unit(f"u{i:02d}", "pass") for i in range(1, 20)]
        run2.append(self._unit("u20", "fail"))
        good_calib = {"records": [
            {"judge": "glml", "defects_detected": 5,
             "healthy_false_positives": 0, "human_agreement": 0.8}]}
        report = scq.summarize_suite(run1, [], good_calib, runs=[run1, run2])
        self.assertEqual(report["m3"]["x_count"], 19)
        self.assertIn("u20", report["m3"]["unstable_or_single_fail"])

    def test_calibration_invalid_blocks_claim_even_all_pass(self):
        units = [self._unit(f"u{i:02d}", "pass") for i in range(1, 21)]
        report = scq.summarize_suite(units, [], {"records": []})
        self.assertFalse(report["claim"]["allowed"])

    @staticmethod
    def _good_calibration():
        return {"records": [
            {"judge": "glml", "defects_detected": 6,
             "healthy_false_positives": 0, "human_agreement": 0.9},
            {"judge": "gpt", "defects_detected": 6,
             "healthy_false_positives": 0, "human_agreement": 0.9},
        ]}

    def test_claim_requires_two_runs_and_dimension_thresholds(self):
        units = [self._unit(f"u{i:02d}", "pass") for i in range(1, 21)]
        g2 = [f"u{i:02d}" for i in range(13, 21)]

        single = scq.summarize_suite(units, g2, self._good_calibration())
        self.assertFalse(single["claim"]["allowed"])
        self.assertTrue(any("M3" in b for b in single["claim"]["blocks"]))

        complete = scq.summarize_suite(
            units, g2, self._good_calibration(), runs=[units, units])
        self.assertTrue(complete["claim"]["allowed"])

        failing = [self._unit(f"u{i:02d}", "fail") for i in range(1, 21)]
        failed_report = scq.summarize_suite(
            failing, g2, self._good_calibration(), runs=[failing, failing])
        self.assertFalse(failed_report["claim"]["allowed"])
        self.assertTrue(any("L0" in b for b in failed_report["claim"]["blocks"]))

    def test_claim_rejects_dimension_below_18_or_g2_below_7(self):
        g2 = [f"u{i:02d}" for i in range(13, 21)]
        units = [self._unit(f"u{i:02d}", "pass") for i in range(1, 21)]
        # Keep L0 status green while one dimension misses the L1 threshold.
        for run in (units,):
            for unit in run[:3]:
                unit["dimensions"]["A3"] = "incomplete"
        report = scq.summarize_suite(
            units, g2, self._good_calibration(), runs=[units, units])
        self.assertFalse(report["claim"]["allowed"])
        self.assertTrue(any("L1" in b for b in report["claim"]["blocks"]))

    def test_cli_returns_nonzero_when_claim_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            machine = root / "machine.json"
            machine.write_text("{}", encoding="utf-8")
            units = root / "units.json"
            units.write_text(json.dumps([{
                "unit": "u01", "machine": str(machine),
            }]), encoding="utf-8")
            blocked = {"unit": "u01", "status": "fail",
                       "dimensions": {d: "fail" for d in "A1 A2 A3 A4 A5".split()}}
            with mock.patch.object(scq, "summarize_unit", return_value=blocked), \
                    mock.patch.object(sys, "argv", ["summarize_content_quality",
                                                       "--units-file", str(units)]):
                self.assertEqual(scq.main(), 1)


class AnonymizeTest(unittest.TestCase):
    def test_anonymize_maps_and_keeps_content(self):
        import check_content_quality as ccq
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "project" / "content"
            proj.mkdir(parents=True)
            (proj / "outline-v1.md").write_text("## S1 大纲", encoding="utf-8")
            (proj / "deck-master-v1.md").write_text("## S1 母版", encoding="utf-8")
            anon_root = Path(td) / "anon"
            unit = {"id": "u01", "slug": "internet-tech",
                    "conflict": False, "material_file": "u01-internet-tech.md",
                    "gradient": "G1-styles", "audience": "投资人",
                    "task_type": "路演", "material_form": "直出",
                    "industry": "互联网科技"}
            pkg = jcc.anonymize_package(unit, Path(td), anon_root, None)
            self.assertTrue((pkg / "DOC-outline.md").exists())
            self.assertTrue((pkg / "DOC-materials.md").exists())
            self.assertTrue((pkg / "REF-terminology.md").exists())
            self.assertFalse((pkg / "REF-adjudication.md").exists())
            # 匿名映射由评测侧保管
            mapping = (anon_root / "anon-map.jsonl").read_text(encoding="utf-8")
            self.assertIn("u01", mapping)
            self.assertIn("PKG-", mapping)
            text = jcc.render_package_text(pkg)
            self.assertIn("DOC-master.md", text)

    def test_anonymize_id_is_stable_and_does_not_expose_unit_key(self):
        import check_content_quality as ccq
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proj = root / "project" / "content"
            proj.mkdir(parents=True)
            (proj / "outline-v1.md").write_text("outline", encoding="utf-8")
            (proj / "deck-master-v1.md").write_text("master", encoding="utf-8")
            unit = {"id": "u99", "slug": "internet-tech", "conflict": False,
                    "material_file": None, "gradient": "G1-styles", "audience": "x",
                    "task_type": "x", "material_form": "x", "industry": "x"}
            a = jcc.anonymize_package(unit, root / "project" / "content", root / "a", None)
            b = jcc.anonymize_package(unit, root / "project" / "content", root / "b", None)
            self.assertEqual(a.name, b.name)
            self.assertTrue(a.name.startswith("PKG-"))
            self.assertNotIn("u99", a.name)


if __name__ == "__main__":
    unittest.main()
