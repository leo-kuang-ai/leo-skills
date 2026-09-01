#!/usr/bin/env python3
"""check_worker_brief.py 单测（R-46 四块完备性阶梯）。

覆盖：四块齐 / 各缺一块 / 豁免路径（无术语表、无登记行）/ 多页汇总与排序 /
exit 语义（0 齐 / 1 缺块 / 2 用法）/ 单页复检模式 / 确定性（重复运行逐字节一致）。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_worker_brief.py"

TERM = "LEOM（Leo Orchestrated Model）"
LEDGER_REF = "87%（S3 口径：续约率）"

FULL_PROMPT = (
    "# Codex PPT Slide Image Prompt\n"
    "## Deck Style Lock\n"
    "shell: 纸色外层壳\n"
    "## Required Text Only\n"
    "- 标题甲\n"
    "- 要点一\n"
    "## Deck Terminology\n"
    f"- {TERM}\n"
    "## Number Ledger Rows\n"
    f"- {LEDGER_REF}\n"
)


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def base_spec() -> dict:
    """Four-block deck: every ladder condition is active."""
    return {
        "deck_context": {"canonical_terms": [TERM]},
        "style_lock": {"shell": "纸色外层壳"},
        "slides": [
            {
                "number": 1,
                "title": "标题甲",
                "required_text": ["标题甲", "要点一"],
                "terms": [TERM],
                "number_ledger_refs": [LEDGER_REF],
            }
        ],
    }


def write_deck(root: Path, spec: dict, prompts: dict) -> Path:
    deck = root / "deck"
    (deck / "prompts").mkdir(parents=True)
    (deck / "slides.json").write_text(
        json.dumps(spec, ensure_ascii=False), encoding="utf-8"
    )
    for name, prompt in prompts.items():
        (deck / "prompts" / name).write_text(
            json.dumps({"prompt": prompt}, ensure_ascii=False), encoding="utf-8"
        )
    return deck


class WorkerBriefLadderTest(unittest.TestCase):
    def test_all_four_blocks_present_exits_zero(self):
        with tempfile.TemporaryDirectory() as name:
            deck = write_deck(Path(name), base_spec(), {"slide_01.json": FULL_PROMPT})
            result = run(str(deck))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("四块齐备", result.stdout)

    def test_missing_required_text_block_reports_page_and_block(self):
        with tempfile.TemporaryDirectory() as name:
            deck = write_deck(
                Path(name), base_spec(), {"slide_01.json": FULL_PROMPT.replace("## Required Text Only\n", "")}
            )
            result = run(str(deck))
            self.assertEqual(result.returncode, 1)
            self.assertIn("slide_01", result.stdout)
            self.assertIn("## Required Text Only", result.stdout)

    def test_missing_style_lock_block_blocks_dispatch(self):
        with tempfile.TemporaryDirectory() as name:
            deck = write_deck(
                Path(name), base_spec(), {"slide_01.json": FULL_PROMPT.replace("## Deck Style Lock\n", "")}
            )
            result = run(str(deck))
            self.assertEqual(result.returncode, 1)
            self.assertIn("## Deck Style Lock", result.stdout)

    def test_missing_terminology_block_blocks_dispatch(self):
        """AE-53：简报缺术语注入块 → 阻断并给缺块清单。"""
        with tempfile.TemporaryDirectory() as name:
            deck = write_deck(
                Path(name), base_spec(), {"slide_01.json": FULL_PROMPT.replace("## Deck Terminology\n", "")}
            )
            result = run(str(deck))
            self.assertEqual(result.returncode, 1)
            self.assertIn("## Deck Terminology", result.stdout)
            self.assertIn("术语注入块静默丢失", result.stdout)

    def test_missing_number_ledger_block_blocks_dispatch(self):
        with tempfile.TemporaryDirectory() as name:
            deck = write_deck(
                Path(name), base_spec(), {"slide_01.json": FULL_PROMPT.replace("## Number Ledger Rows\n", "")}
            )
            result = run(str(deck))
            self.assertEqual(result.returncode, 1)
            self.assertIn("## Number Ledger Rows", result.stdout)

    def test_number_ledger_ref_not_verbatim_fails(self):
        with tempfile.TemporaryDirectory() as name:
            deck = write_deck(
                Path(name), base_spec(), {"slide_01.json": FULL_PROMPT.replace(LEDGER_REF, "87%")}
            )
            result = run(str(deck))
            self.assertEqual(result.returncode, 1)
            self.assertIn("数字登记行引用未逐字进入简报", result.stdout)

    def test_glossary_absent_exempts_terminology_block(self):
        """向后兼容：无术语表的 deck，术语注入块豁免。"""
        with tempfile.TemporaryDirectory() as name:
            spec = base_spec()
            del spec["deck_context"]
            prompt = FULL_PROMPT.replace("## Deck Terminology\n", "")
            deck = write_deck(Path(name), spec, {"slide_01.json": prompt})
            result = run(str(deck))
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_no_ledger_refs_exempts_number_block(self):
        """向后兼容：该页登记表无行（未声明 number_ledger_refs）→ 数字行块豁免。"""
        with tempfile.TemporaryDirectory() as name:
            spec = base_spec()
            del spec["slides"][0]["number_ledger_refs"]
            prompt = FULL_PROMPT.replace("## Number Ledger Rows\n", "").replace(LEDGER_REF, "")
            deck = write_deck(Path(name), spec, {"slide_01.json": prompt})
            result = run(str(deck))
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_multi_page_missing_blocks_aggregated_and_sorted(self):
        with tempfile.TemporaryDirectory() as name:
            spec = base_spec()
            spec["slides"].append(
                {
                    "number": 2,
                    "title": "标题乙",
                    "required_text": ["标题乙"],
                    "terms": [TERM],
                    "number_ledger_refs": [LEDGER_REF],
                }
            )
            deck = write_deck(
                Path(name),
                spec,
                {
                    # slide_01 缺术语块；slide_02 缺 style_lock 与数字行块。
                    "slide_01.json": FULL_PROMPT.replace("## Deck Terminology\n", ""),
                    "slide_02.json": FULL_PROMPT.replace("## Deck Style Lock\n", "")
                    .replace("## Number Ledger Rows\n", "")
                    .replace(LEDGER_REF, ""),
                },
            )
            result = run(str(deck))
            self.assertEqual(result.returncode, 1)
            self.assertIn("slide_01", result.stdout)
            self.assertIn("slide_02", result.stdout)
            self.assertLess(
                result.stdout.index("FAIL slide_01"), result.stdout.index("FAIL slide_02")
            )

    def test_missing_job_prompt_file_blocks_dispatch(self):
        with tempfile.TemporaryDirectory() as name:
            spec = base_spec()
            spec["slides"].append({"number": 2, "title": "标题乙"})
            deck = write_deck(Path(name), spec, {"slide_01.json": FULL_PROMPT})
            result = run(str(deck))
            self.assertEqual(result.returncode, 1)
            self.assertIn("slide_02: 缺 job prompt 文件", result.stdout)

    def test_usage_errors_exit_two(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            deck = write_deck(root, base_spec(), {"slide_01.json": FULL_PROMPT})
            # --job without --spec → usage.
            job_only = run("--job", str(deck / "prompts" / "slide_01.json"))
            self.assertEqual(job_only.returncode, 2)
            # Nonexistent path → usage.
            missing = run(str(root / "nope"))
            self.assertEqual(missing.returncode, 2)
            # Target and --job are mutually exclusive → usage.
            both = run(str(deck), "--job", str(deck / "prompts" / "slide_01.json"),
                       "--spec", str(deck / "slides.json"))
            self.assertEqual(both.returncode, 2)
            # No args at all → usage.
            self.assertEqual(run().returncode, 2)

    def test_single_job_mode_checks_only_that_page(self):
        with tempfile.TemporaryDirectory() as name:
            spec = base_spec()
            spec["slides"].append(
                {"number": 2, "title": "标题乙", "required_text": ["标题乙"]}
            )
            deck = write_deck(
                Path(name),
                spec,
                {"slide_01.json": FULL_PROMPT, "slide_02.json": "# no blocks"},
            )
            ok = run(
                "--job", str(deck / "prompts" / "slide_01.json"),
                "--spec", str(deck / "slides.json"),
            )
            self.assertEqual(ok.returncode, 0, ok.stdout)
            broken = run(
                "--job", str(deck / "prompts" / "slide_02.json"),
                "--spec", str(deck / "slides.json"),
            )
            self.assertEqual(broken.returncode, 1)
            self.assertIn("slide_02", broken.stdout)

    def test_output_is_deterministic_across_runs(self):
        with tempfile.TemporaryDirectory() as name:
            deck = write_deck(
                Path(name), base_spec(), {"slide_01.json": FULL_PROMPT.replace("## Deck Terminology\n", "")}
            )
            first = run(str(deck))
            second = run(str(deck))
            self.assertEqual(first.returncode, second.returncode)
            self.assertEqual(first.stdout, second.stdout)


if __name__ == "__main__":
    unittest.main()
