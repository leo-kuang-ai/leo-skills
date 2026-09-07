"""风格索引改动前的加载、组合和最终 prompt 基线。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "tests" / "fixtures" / "style-index"
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator import styles, templates


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def prompt_runner():
    path = SKILL / "tests" / "boundary" / "test_prompt_block_regression.py"
    spec = importlib.util.spec_from_file_location("baseline_prompt_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.prepare


def render_baseline():
    prepare = prompt_runner()
    inputs = [
        ("default", "清爽专业风", {}),
        ("anchor", "清爽专业风", {"anchor": True}),
        ("guardrail", "清爽专业风", {"guardrail": True}),
        ("layout-lock", "布局回归风", {"layout_lock": True}),
        ("brand", "清爽专业风", {"brand": "回归品牌", "anchor": True}),
        ("dark", "Dracula紫风", {}),
    ]
    outputs = {}
    with tempfile.TemporaryDirectory() as directory:
        with mock.patch.dict(os.environ, {"LEO_PPT_HOME": directory, "LEO_PPT_BUNDLE": str(SKILL)}):
            base = styles.load_style("清爽专业风")["content"]
            brief = json.loads(re.search(r"```json\n(.*?)\n```", base, re.S).group(1))
            brief["style_name"] = "布局回归风"
            brief["layout"] = {
                "grid": "12 columns", "safe_margin": "5%", "page_no": "bottom-right",
                "corner_radius": "0", "line_weight": "1px",
            }
            styles.save_style("布局回归风", "# 布局回归风\n\n```json\n" + json.dumps(brief, ensure_ascii=False) + "\n```\n")
            with mock.patch.object(templates, "load_brand", return_value={
                "name": "回归品牌", "primary": "#111111", "accent": "#333333",
                "tone": "清晰", "typography": "Noto Sans SC", "verified_at": "2026-09-05",
            }):
                for key, name, kwargs in inputs:
                    composition = templates.compose_style(name, **kwargs)
                    spec = {
                        "deck_name": "style-index-baseline", "language": "Chinese",
                        "goal": "核验治理元数据不改变视觉投影", "style": composition,
                        "style_lock": {"shell": "固定样式", "constants": ["左对齐"]},
                        "slides": [{"number": 1, "title": "固定基线", "key_points": ["结果可复核"],
                                    "required_text": ["固定基线", "结果可复核"]}],
                    }
                    code, result = prepare(spec)
                    if code:
                        raise AssertionError(result["stderr"])
                    outputs[key] = {"style": composition, "prompt": result["jobs"]["slide_01"]["prompt"]}
                outputs["layout-materialize"] = templates.compose_layout("P4", materialize=True)
    return outputs


def capture(directory):
    directory.mkdir(parents=True, exist_ok=True)
    target = FIXTURES / "prompt-baseline.json"
    if target.exists():
        raise SystemExit("已存在冻结基线，拒绝覆盖；变更基线须单独审阅")
    entries = []
    for path in sorted((SKILL / "references" / "styles").rglob("*")):
        if not path.is_file() or "generated" in path.parts:
            continue
        payload = path.read_bytes()
        text = payload.decode("utf-8", errors="replace") if path.suffix == ".md" else ""
        blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
        parsed = []
        errors = []
        for block in blocks:
            try:
                parsed.append(json.loads(block))
            except ValueError:
                errors.append("invalid-json")
        briefs = [b for b in parsed if isinstance(b, dict) and "style_name" in b]
        entries.append({"path": path.relative_to(SKILL).as_posix(), "sha256": hashlib.sha256(payload).hexdigest(),
                        "legacy_parseable_json": bool(parsed), "briefs": briefs, "errors": errors})
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=SKILL, capture_output=True, text=True, check=True).stdout.strip()
    (directory / "asset-ledger.json").write_bytes(json_bytes({"revision": revision, "entries": entries}))
    target.write_bytes(json_bytes({"schema_version": 1, "source_revision": revision,
                                 "note": "品牌读取固定；layout-lock 使用固定合成风格；其余风格、组合器和最终逐页 prompt 使用真实源码。",
                                 "outputs": render_baseline()}))
    print(json.dumps({"asset_files": len(entries), "baseline": str(target), "ledger": str(directory / "asset-ledger.json")}, ensure_ascii=False))


class StyleIndexBaselineTest(unittest.TestCase):
    def test_query_sets_have_eight_categories_and_holdout(self):
        cases = json.loads((FIXTURES / "queries.json").read_text())["cases"]
        self.assertEqual(len({case["id"] for case in cases}), 32)
        self.assertEqual(set(Counter(c["category"] for c in cases).values()), {4})
        self.assertEqual(sum(c["split"] == "holdout" for c in cases), 8)

    def test_curated_lookup_names_exist_in_current_sources(self):
        names = set()
        aliases = {}
        for path in (SKILL / "references" / "styles").rglob("*.md"):
            if "generated" in path.parts:
                continue
            for block in re.findall(r"```json\n(.*?)\n```", path.read_text(), re.S):
                try:
                    brief = json.loads(block)
                except ValueError:
                    continue
                if not isinstance(brief, dict) or "style_name" not in brief:
                    continue
                name = brief["style_name"]
                names.add(name)
                for alias in brief.get("aliases", []):
                    aliases.setdefault(alias.strip().casefold(), set()).add(name)
        for case in json.loads((FIXTURES / "queries.json").read_text())["cases"]:
            category = case["category"]
            if category in {"exact", "variant", "long-tail"}:
                self.assertTrue(set(case["expected_names"]) <= names, case)
            if category in {"alias", "ambiguous"}:
                self.assertEqual(aliases.get(case["query"].strip().casefold()), set(case["expected_names"]), case)

    def test_final_prompts_match_frozen_baseline(self):
        baseline = json.loads((FIXTURES / "prompt-baseline.json").read_text())
        self.assertEqual(render_baseline(), baseline["outputs"])

    def test_same_name_user_style_remains_preferred(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "styles").mkdir()
            user = home / "styles" / "清爽专业风.md"
            user.write_text("# 用户覆盖\n\n```json\n{\"style_name\":\"清爽专业风\"}\n```\n")
            result = styles.load_style("清爽专业风", home=home)
            self.assertEqual(result["source"], "user")
            self.assertEqual(Path(result["path"]), user)
            self.assertIn("用户覆盖", result["content"])


if __name__ == "__main__":
    if "--capture" in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument("--capture", type=Path, required=True)
        capture(parser.parse_args().capture)
    else:
        unittest.main()
