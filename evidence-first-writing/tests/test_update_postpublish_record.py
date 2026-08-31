#!/usr/bin/env python3
"""Behavioral tests for the post-publish record adjudicator script."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "update_postpublish_record.py"


def load_module():
    spec = importlib.util.spec_from_file_location("update_postpublish_record", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecordScriptTests(unittest.TestCase):
    maxDiff = None

    def run_record(self, *args: str, workdir: Path | None = None) -> subprocess.CompletedProcess[str]:
        command = ["python3", str(SCRIPT), "record", *args]
        if workdir is not None:
            return subprocess.run(
                command, check=False, capture_output=True, text=True, cwd=str(workdir)
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            return subprocess.run(
                command, check=False, capture_output=True, text=True, cwd=temp_dir
            )

    def read_ledger(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Requirement 1 & 7: legal call emits the canonical four-field block.

    def test_valid_call_emits_canonical_four_field_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_record(
                "--observation", "标题 v3 完读率 62%",
                "--hypothesis", "数字前置标题提升完读",
                "--stable-rule-update", "hypothesis",
                "--persistence", "not_run",
                workdir=Path(temp_dir),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            (
                "observation: 标题 v3 完读率 62%\n"
                "hypothesis: 数字前置标题提升完读\n"
                "stable_rule_update: hypothesis\n"
                "persistence: not_run\n"
            ),
        )

    def test_hypothesis_defaults_to_none(self) -> None:
        result = self.run_record(
            "--observation", "单篇观察",
            "--stable-rule-update", "none",
            "--persistence", "not_run",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hypothesis: none\n", result.stdout)

    def test_enum_field_rejects_unknown_values(self) -> None:
        bad_status = self.run_record(
            "--observation", "x",
            "--stable-rule-update", "promoted!", "--persistence", "not_run",
        )
        self.assertEqual(bad_status.returncode, 2)
        self.assertIn("invalid choice", bad_status.stderr)

        bad_persistence = self.run_record(
            "--observation", "x",
            "--stable-rule-update", "none", "--persistence", "maybe",
        )
        self.assertEqual(bad_persistence.returncode, 2)
        self.assertIn("invalid choice", bad_persistence.stderr)

    # Requirement 7: canonical block stays parseable for YAML-hostile text.

    def test_canonical_block_quotes_yaml_hostile_values(self) -> None:
        module = load_module()
        block = module.render_canonical_block(
            '引用 "数据" 与冒号: 结尾:', "true", "candidate", "authorized"
        )
        lines = block.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith('observation: "'))
        self.assertEqual(lines[1], 'hypothesis: "true"')
        self.assertEqual(lines[2], "stable_rule_update: candidate")
        self.assertEqual(lines[3], "persistence: authorized")

    # Requirement 2: promoted demands all three evidence conditions.

    def test_promoted_missing_replications_is_rejected_without_writing_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            result = self.run_record(
                "--observation", "o",
                "--stable-rule-update", "promoted",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                "--comparable-runs", "2",
                "--counterexamples-checked",
                workdir=Path(temp_dir),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--replications", result.stderr)
            self.assertFalse(ledger.exists())

    def test_promoted_missing_comparable_runs_is_rejected_without_writing_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            result = self.run_record(
                "--observation", "o",
                "--stable-rule-update", "promoted",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                "--replications", "2",
                "--counterexamples-checked",
                workdir=Path(temp_dir),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--comparable-runs", result.stderr)
            self.assertFalse(ledger.exists())

    def test_promoted_missing_counterexamples_declaration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            result = self.run_record(
                "--observation", "o",
                "--stable-rule-update", "promoted",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                "--replications", "2",
                "--comparable-runs", "2",
                workdir=Path(temp_dir),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--counterexamples-checked", result.stderr)
            self.assertFalse(ledger.exists())

    def test_promoted_below_threshold_is_rejected(self) -> None:
        result = self.run_record(
            "--observation", "o",
            "--stable-rule-update", "promoted",
            "--persistence", "not_run",
            "--replications", "1",
            "--comparable-runs", "3",
            "--counterexamples-checked",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--replications >= 2", result.stderr)

    def test_promoted_with_all_three_conditions_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            result = self.run_record(
                "--observation", "金句前置在 3 个可比项目复现",
                "--hypothesis", "none",
                "--stable-rule-update", "promoted",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                "--replications", "2",
                "--comparable-runs", "3",
                "--counterexamples-checked",
                "--counterexamples-note", "反例检索记录: notes.md",
                workdir=Path(temp_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            entries = self.read_ledger(ledger)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["stable_rule_update"], "promoted")
            self.assertEqual(entries[0]["replications"], 2)
            self.assertEqual(entries[0]["comparable_runs"], 3)
            self.assertTrue(entries[0]["counterexamples_checked"])
            self.assertEqual(entries[0]["counterexamples_note"], "反例检索记录: notes.md")

    # Requirement 3: explicit --ledger only; nothing written without it.

    def test_without_ledger_no_file_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            before = sorted(p.name for p in workdir.iterdir())
            result = self.run_record(
                "--observation", "o",
                "--stable-rule-update", "hypothesis",
                "--persistence", "not_run",
                workdir=workdir,
            )
            after = sorted(p.name for p in workdir.iterdir())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, after)
            self.assertEqual(result.stderr, "")

    def test_ledger_inside_skill_directory_is_rejected(self) -> None:
        ledger = SKILL_ROOT / "postpublish-ledger.jsonl"
        result = self.run_record(
            "--observation", "o",
            "--stable-rule-update", "hypothesis",
            "--persistence", "authorized",
            "--ledger", str(ledger),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("技能目录", result.stderr)
        self.assertFalse(ledger.exists())

    def test_ledger_inside_skill_mirror_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mirror_root = Path(temp_dir) / ".agents" / "skills" / "evidence-first-writing"
            (mirror_root / "scripts").mkdir(parents=True)
            (mirror_root / "scripts" / SCRIPT.name).write_text("# mirror copy\n", encoding="utf-8")
            ledger = mirror_root / "ledger.jsonl"
            result = self.run_record(
                "--observation", "o",
                "--stable-rule-update", "hypothesis",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                workdir=Path(temp_dir),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("镜像", result.stderr)
            self.assertFalse(ledger.exists())

    # Persistence/ledger consistency: no claim of authorized writes without a path.

    def test_persistence_authorized_without_ledger_is_rejected(self) -> None:
        result = self.run_record(
            "--observation", "o",
            "--stable-rule-update", "candidate",
            "--persistence", "authorized",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--ledger", result.stderr)

    def test_ledger_with_persistence_not_run_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            result = self.run_record(
                "--observation", "o",
                "--stable-rule-update", "hypothesis",
                "--persistence", "not_run",
                "--ledger", str(ledger),
                workdir=Path(temp_dir),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("persistence", result.stderr)
            self.assertFalse(ledger.exists())

    # Requirements 4 & 5: append-only semantics with pinned duplicate behavior.

    def test_ledger_append_never_overwrites_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            first = self.run_record(
                "--observation", "第一篇观察",
                "--stable-rule-update", "none",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                workdir=Path(temp_dir),
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            original = ledger.read_text(encoding="utf-8")

            second = self.run_record(
                "--observation", "第二篇观察",
                "--stable-rule-update", "hypothesis",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                workdir=Path(temp_dir),
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            updated = ledger.read_text(encoding="utf-8")
            self.assertTrue(updated.startswith(original))
            self.assertEqual(len(self.read_ledger(ledger)), 2)

    def test_identical_duplicate_entry_is_idempotently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            common = (
                "--observation", "同一观察",
                "--stable-rule-update", "hypothesis",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                "--invariant-hash", "a" * 64,
            )
            first = self.run_record(*common, workdir=Path(temp_dir))
            second = self.run_record(*common, workdir=Path(temp_dir))
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("SKIP", second.stderr)
            self.assertIn("幂等", second.stderr)
            self.assertEqual(len(self.read_ledger(ledger)), 1)
            self.assertIn("stable_rule_update: hypothesis", second.stdout)

    def test_changed_entry_for_same_observation_appends_new_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            first = self.run_record(
                "--observation", "同一观察",
                "--stable-rule-update", "none",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                workdir=Path(temp_dir),
            )
            second = self.run_record(
                "--observation", "同一观察",
                "--stable-rule-update", "hypothesis",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                workdir=Path(temp_dir),
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            entries = self.read_ledger(ledger)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["stable_rule_update"], "none")
            self.assertEqual(entries[1]["stable_rule_update"], "hypothesis")

    def test_missing_ledger_file_is_treated_as_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            result = self.run_record(
                "--observation", "首条",
                "--stable-rule-update", "none",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                workdir=Path(temp_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("新建", result.stderr)
            self.assertTrue(ledger.exists())
            self.assertEqual(len(self.read_ledger(ledger)), 1)

    def test_corrupt_ledger_lines_are_skipped_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            corrupt_line = "{not valid json"
            ledger.write_text(
                corrupt_line + "\n" + json.dumps({"observation": "旧观察"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            result = self.run_record(
                "--observation", "新观察",
                "--stable-rule-update", "none",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                workdir=Path(temp_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("WARNING", result.stderr)
            self.assertIn("第 1 行", result.stderr)
            # Append-only: the corrupt line is preserved verbatim, new line added.
            lines = ledger.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], corrupt_line)
            self.assertEqual(len(lines), 3)

    # Requirement 6: invariant hash recording and explicit staleness.

    def test_invariant_hash_is_recorded_in_ledger_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            digest = "b" * 64
            result = self.run_record(
                "--observation", "带哈希观察",
                "--stable-rule-update", "none",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                "--invariant-hash", digest,
                workdir=Path(temp_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            entries = self.read_ledger(ledger)
            self.assertEqual(entries[0]["invariant_hash"], digest)

    def test_changed_invariant_hash_explicitly_supersedes_prior_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.jsonl"
            old_hash, new_hash = "c" * 64, "d" * 64
            first = self.run_record(
                "--observation", "改稿后复盘",
                "--stable-rule-update", "hypothesis",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                "--invariant-hash", old_hash,
                workdir=Path(temp_dir),
            )
            original_first_line = ledger.read_text(encoding="utf-8").splitlines()[0]

            second = self.run_record(
                "--observation", "改稿后复盘",
                "--stable-rule-update", "hypothesis",
                "--persistence", "authorized",
                "--ledger", str(ledger),
                "--invariant-hash", new_hash,
                workdir=Path(temp_dir),
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("supersedes_invariant_hash", second.stderr)

            lines = ledger.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], original_first_line)  # history untouched
            new_entry = json.loads(lines[1])
            self.assertEqual(new_entry["invariant_hash"], new_hash)
            self.assertEqual(new_entry["supersedes_invariant_hash"], old_hash)

    # Requirement 8: clear help and non-interactive failure paths.

    def test_help_exits_zero_and_documents_contract(self) -> None:
        top_level = subprocess.run(
            ["python3", str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(top_level.returncode, 0)
        self.assertIn("record", top_level.stdout)
        self.assertIn("--ledger", top_level.stdout)

        subcommand = subprocess.run(
            ["python3", str(SCRIPT), "record", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(subcommand.returncode, 0)
        for option in (
            "--observation",
            "--hypothesis",
            "--stable-rule-update",
            "--persistence",
            "--ledger",
            "--invariant-hash",
            "--replications",
            "--comparable-runs",
            "--counterexamples-checked",
        ):
            self.assertIn(option, subcommand.stdout)

    def test_blank_observation_is_rejected(self) -> None:
        result = self.run_record(
            "--observation", "   ",
            "--stable-rule-update", "none",
            "--persistence", "not_run",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--observation", result.stderr)

    def test_negative_replications_is_rejected(self) -> None:
        result = self.run_record(
            "--observation", "o",
            "--stable-rule-update", "hypothesis",
            "--persistence", "not_run",
            "--replications", "-1",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不能为负数", result.stderr)

    def test_missing_parent_directory_is_rejected_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "no-such-dir" / "ledger.jsonl"
            result = self.run_record(
                "--observation", "o",
                "--stable-rule-update", "hypothesis",
                "--persistence", "authorized",
                "--ledger", str(missing),
                workdir=Path(temp_dir),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("父目录不存在", result.stderr)
            self.assertFalse(missing.parent.exists())

    def test_missing_subcommand_fails_clearly(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("record", result.stderr)


if __name__ == "__main__":
    unittest.main()
