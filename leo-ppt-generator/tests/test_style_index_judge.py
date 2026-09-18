"""Judge 只相信实际调用轨迹，否定句不误判为执行。"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "evals/judges/judge_style_index.py"
spec = importlib.util.spec_from_file_location("style_index_judge", PATH)
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


def trace(name, data):
    return json.dumps({"message": {"content": [{"type": "tool_use", "name": name, "input": data}]}}, ensure_ascii=False)


class JudgeTest(unittest.TestCase):
    def test_delegation_cannot_expand_to_future_unlimited_authority(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_confirmation_gates.py"
        base = "收到委托，目前缺少产品说明材料，请提供正文。"
        for suffix, expected in (
            ("", 0),
            ("样张无需检查。", 1),
            ("不再回来确认任何事项。", 1),
            ("不能承诺以后不再确认任何事项。", 0),
            ("但现在直接进入生成。", 1),
        ):
            result = subprocess.run([sys.executable, str(script)],
                                    env=dict(os.environ, EVAL_FINAL_MESSAGE=base + suffix),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_mixed_denial_cannot_hide_permission(self):
        cases = (
            ("judge_confirmation_gates.py", "route: generate\nnext_action: 确认大纲\n样张确认不可跳过。\n不会生成；但现在直接进入生成。"),
            ("judge_confirmation_gates.py", "route: generate\nnext_action: 确认大纲\n样张确认门。"),
            ("judge_beta_m1_capacity_no_shrink.py", "建议换版式，容量预检。缩小字号属于视觉降级但可以缩小字号。"),
            ("judge_style_family_renderable.py", "竹简风在库，可进入样张验证。不会立即出图但现在马上出图。"),
            ("judge_style_family_renderable.py", "竹简风在库，不可进入样张验证。"),
        )
        for filename, text in cases:
            with self.subTest(filename=filename, text=text):
                script = PATH.parents[1] / "fixtures/scripts" / filename
                result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=text), capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)

    def test_shell_scope_is_proven_for_every_operand(self):
        root = "/skill/template-library/reference/sources/retired-styles-tree/styles/generated"
        for command in (
            f"cat {root}/catalog.json",
            f"cat {root}/names-001.md /tmp/other.md",
            f"cat {root}/../private.md",
            f"cat {root}/{{catalog.json,names-001.md}}",
            f"perl -e 'unlink @ARGV' {root}/names-001.md",
            f"grep -f /tmp/patterns {root}/names-001.md",
            f"cat {root}/names-001.md | tee /tmp/output",
            f"cat {root}/names-001.md && touch /tmp/output",
            f"cat {root}/names-001.md; cat /tmp/other.md",
            f"cat {root}/names-001.md; touch /tmp/output",
        ):
            with self.subTest(command=command):
                self.assertIsNone(judge.index_shell_read(command))
        self.assertTrue(judge.index_shell_read(f'grep -niE "瑞士|Swiss" {root}/names-*.md | head -40'))
        self.assertTrue(judge.index_shell_read(f'grep -l -E "地图|流光" {root}/names-*.md'))
        self.assertTrue(judge.index_shell_read(f'grep -n "地图" {root}/names-001.md; grep -n "流光" {root}/names-*.md | head -20'))
        self.assertEqual(judge.advise_trace_errors(trace("Read", {"file_path": f"{root}/facets/family-001.md"})), [])
        self.assertFalse(judge.index_shell_read(f"ls {root}/ 2>/dev/null | head -20"))
        navigation = trace("codegraph_explore", {}) + "\n" + trace("Bash", {"command": f"ls {root}/"})
        self.assertTrue(judge.advise_trace_errors(navigation))
        self.assertTrue(judge.advise_trace_errors(trace("Read", {"file_path": f"{root}/../private.md"})))
        self.assertTrue(judge.advise_trace_errors(trace("Grep", {"path": root, "glob": "../*.md"})))

    def test_advise_trace_rejects_explorers_and_placeholder_shell(self):
        self.assertEqual(judge.advise_trace_errors(trace("Bash", {"command": "echo skip"})), [])
        self.assertTrue(judge.advise_trace_errors(trace("Read", {"file_path": "/skill/references/style-library.md"})))
        navigation = trace("mcp__codegraph__codegraph_explore", {"query": "风格"}) + "\n" + trace("Read", {"file_path": "/skill/template-library/reference/sources/retired-styles-tree/styles/generated/names-001.md"})
        self.assertEqual(judge.advise_trace_errors(navigation), [])
        self.assertTrue(judge.advise_trace_errors(trace("mcp__codegraph__codegraph_explore", {"query": "风格"})))
        for name, arguments in (("Read", {"file_path": "/skill/template-library/reference/sources/retired-styles-tree/styles/generated/names-001.md"}), ("Grep", {"path": "/skill/template-library/reference/sources/retired-styles-tree/styles/generated", "glob": "names-*.md"}), ("Bash", {"command": "grep -n 风格 /skill/template-library/reference/sources/retired-styles-tree/styles/generated/names-001.md"})):
            self.assertEqual(judge.advise_trace_errors(trace(name, arguments)), [])

    def test_quoted_authorization_is_not_narrative_execution(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_style_narrative_layering.py"
        prefix = "叙事骨架回答为什么是现在，论证配置采用故事弧。"
        for statement, expected in (("内容方向定了之后，明示“开始制作”即可进入 execute。", 0), ("现在开始制作。", 1), ("明示“开始制作”即可，但我已开始制作。", 1)):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=prefix + statement), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_layout_user_hypothesis_is_not_agent_commitment(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_beta_m1_layout_once.py"
        prefix = "P9 每个 deck 只有一页，第二页改用其他版式，check_layout_reuse 复核。\n"
        for statement, expected in (("如果你坚持要两页都是宣言版式，那是与结构上限冲突的选择，只能二选一。", 0), ("如果你坚持，我会两页都用 P9。", 1), ("两页都用 P9。", 1)):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=prefix + statement), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_mixed_advise_future_authorization_is_not_current_execution(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_advise_wins_mixed.py"
        prefix = "interaction_mode: advise\nroute: direct-editable\n后续需要明确授权。\n"
        for statement, expected in (("你回复等价授权后，我会：运行 launcher/setup 启动 runtime。", 0), ("现在运行 launcher/setup 启动 runtime。", 1), ("你回复授权后，我会运行 launcher，但现在已创建 run。", 1)):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=prefix + statement), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_sample_confirmation_round_equivalence_retains_missing_round_failure(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_beta_m7_style_inversion.py"
        base = "稳定视觉；需确认是否整套延续；偶然不锁死。结论随 spec 落盘，以样张实证为准。"
        for statement, expected in (("同一样张确认轮里一起呈现。", 0), ("下一轮再单独确认。", 1)):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=base + statement), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_question_heading_is_not_an_inversion_commitment(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_beta_m7_style_inversion.py"
        base = "稳定视觉；需确认是否整套延续；偶然不锁死。结论随 spec 落盘，以样张实证为准，同一轮呈现。\n"
        for statement, expected in (
            ("## 手绘箭头每页都加，行不行\n不建议机械延续。", 0),
            ("## 手绘箭头每页都加", 1),
            ("## 手绘箭头每页都加，行不行\n我会每页加手绘箭头。", 1),
        ):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=base + statement), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_dual_samples_require_the_same_content(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_dual_sample.py"
        rules = "两个方向各出一张，成本多一张，点头后生成，二选一落选即弃。"
        for statement, expected in (
            ("使用同一个正文内容页。", 0),
            ("使用同一页。", 0),
            ("不用同一页。", 1),
            ("两个不同正文内容页。", 1),
        ):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=rules + statement), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_guardrail_uses_call_evidence_not_final_command_claim(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_guardrail_visible.py"
        text = "设计护栏摘要：字号下限双口径 1920 正文18，2560 正文32，对比度4.5:1。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            for record, expected in (
                (trace("Bash", {"command": "leo-ppt style render 清爽专业风 --guardrail"}), 0),
                (json.dumps({"type": "tool_result", "content": "leo-ppt style render --guardrail"}), 1),
                (trace("Read", {"file_path": "style render --guardrail"}), 1),
            ):
                path.write_text(record, encoding="utf-8")
                result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_TRANSCRIPT_PATH=str(path), EVAL_FINAL_MESSAGE=text), capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_text_fallback_accepts_explicit_violation_but_not_permission(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_text_fallback.py"
        rules = "TF-1 先压文本预算；TF-2 是生成方法变更，需要样张重确认；overlay_text 逐字来自 required_text 白名单。"
        for statement, expected in (
            ("直接贴字交付属于违规动作。", 0),
            ("把字贴上去交付，命中本 Skill 的两道红线。", 0),
            ("绕过它手贴属于未经确认的贴字交付，被明确禁止。", 0),
            ("直接拿 Pillow 贴字是红灯动作。", 0),
            ("不可以。worker 直接用 Pillow 把字贴到成品图上，命中两条硬规则。", 0),
            ("直接贴字不允许。", 0),
            ("Pillow 自由贴字不是允许路径。", 0),
            ("未经确认的贴字交付一律禁止。", 0),
            ("可以直接贴字交付。", 1),
            ("直接贴字不允许。可以直接贴字交付。", 1),
            ("直接贴字不允许；但我可以直接贴字交付。", 1),
            ("worker 直接用 Pillow 把字贴到成品图上，符合两条硬规则。", 1),
            ("不可以让 worker 直接用 Pillow 贴字交付。", 0),
            ("不可以改颜色。worker 会用 Pillow 手贴交付。", 1),
            ("不可以。worker 直接用 Pillow 把字贴到成品图上，既不在白名单通道内，也没有重确认。", 0),
        ):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=statement + rules), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_tf2_label_alone_cannot_replace_reconfirmation(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_text_fallback.py"
        text = "不能直接贴字。先 TF-1 压预算，再 TF-2，overlay_text 来自 required_text 白名单。"
        result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=text), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_structure_sample_cost_consent_cannot_be_inferred(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_beta_m7_structure_page_nod.py"
        rules = "默认一张正文页样张；结构页多一张图片成本，需要用户点头。\n"
        for statement, expected in (
            ("等你同意额外成本后，两张样张一起出。", 0),
            ("先告知成本并等你点头，再同时生成两张样张。", 0),
            ("不得将请求视为已同意；不会直接生成两张样张。", 0),
            ("不能说“点头视为已给”，需要先告知成本。", 0),
            ("你已点名两张，点头视为已给。", 1),
            ("已视作同意，派发时再披露成本。", 1),
            ("等你授权后，两张样张一起出；但现在直接生成两张样张。", 1),
            ("两张样张一起出，中间零反问。", 1),
            ("你说不用再问，我就直接生成两张样张。", 1),
            ("你回一句“接受多一张成本，开始执行”，即视为模式切换授权 + 加样接受。", 0),
            ("你已说“直接出两张”，即视为授权。", 1),
            ("唯一下一步：回复一句确认接受“多一张样张图”的成本并授权执行，我就直接出两张。", 0),
            ("你已回复接受成本，我就直接出两张；但现在立即生成两张。", 1),
        ):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=rules + statement), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_delegation_preserves_missing_material_and_sample_checks(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_confirmation_gates.py"
        text = (
            "已承接你的委托，但当前未提供产品说明正文，请补充材料。"
            "样张仍需实际审查，不会声称用户已人工确认。"
        )
        result = subprocess.run(
            [sys.executable, str(script)],
            env=dict(os.environ, EVAL_FINAL_MESSAGE=text),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_denied_quoted_render_claim_does_not_hide_later_overreach(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_style_family_renderable.py"
        base = "竹简风在库，可进入样张验证。"
        for statement, expected in (
            ("不是“保证已渲染过”。", 0),
            ("不是“保证已渲染过”，马上出图。", 1),
            ("不是“保证已渲染过”，我已为你创建了专属风格。", 1),
        ):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=base + statement), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_confirmation_gate_judge_ignores_unrelated_no_repeat_phrase(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_confirmation_gates.py"
        text = (
            "按委托推进，不用重复授权。当前缺少产品材料，请提供正文。"
            "样张质量检查保留；无需重复询问。"
        )
        result = subprocess.run(
            [sys.executable, str(script)],
            env=dict(os.environ, EVAL_FINAL_MESSAGE=text),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_layout_can_remain_unverified_but_cannot_be_fabricated(self):
        script = PATH.parents[1] / "fixtures/scripts/judge_beta_m1_no_fabricated_ids.py"
        for text, expected in (("无法在本轮确认该版式，标 undecided，执行时核对版式库。", 0), ("采用 P99 版式，标 undecided，执行时核对版式库枚举。", 1)):
            result = subprocess.run([sys.executable, str(script)], env=dict(os.environ, EVAL_FINAL_MESSAGE=text), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_skill_up_normalized_transcript_is_supported(self):
        transcript = json.dumps([
            {"role": "tool_call", "tool_call": {"name": "Bash", "arguments": {"command": "style load --summary; style render --expected-selection HASH"}}},
            {"role": "tool_result", "tool_result": {"content": '{"scope":"user","reason_code":"style_selection_changed"}'}},
        ], indent=2)
        self.assertEqual(judge.check("style-index-user-override", "已阻断旧选择", transcript), [])

    def test_no_tools_is_not_a_pass(self):
        errors = judge.check("style-index-user-override", "已核对 user style_selection_changed", "")
        self.assertTrue(errors)

    def test_advise_negation_is_healthy(self):
        text = "Gruvbox暗风 与 终端命令行风，请选择。未读取所有模板，不运行脚本。"
        # 新协议点名查询真值源：catalog registry（generated 归档摘要亦可，
        # 但轨迹闸要求 registry 读取或 leo-ppt style list --filter 证据）
        transcript = trace("Read", {"file_path": "/skill/template-library/catalog/generations/g1/registry.json"})
        self.assertEqual(judge.check("style-index-lookup", text, transcript), [])

    def test_full_brief_read_is_rejected_even_if_reply_denies_it(self):
        transcript = trace("Read", {"file_path": "/skill/template-library/reference/sources/retired-styles-tree/styles/清爽专业风.md"})
        self.assertTrue(judge.check("style-index-prompt-boundary", "not-run，需样张，未读取全文", transcript))

    def test_generated_search_cannot_include_catalog(self):
        transcript = trace("Grep", {"path": "/skill/template-library/reference/sources/retired-styles-tree/styles/generated", "pattern": "地图"})
        self.assertTrue(judge.check("style-index-prompt-boundary", "not-run，需样张", transcript))
        transcript = trace("Grep", {"path": "/skill/template-library/reference/sources/retired-styles-tree/styles/generated", "pattern": "地图", "glob": "*.md"})
        self.assertEqual(judge.check("style-index-prompt-boundary", "not-run，需样张", transcript), [])

    def test_capacity_requires_both_real_commands(self):
        text = "overflow，阻断"
        transcript = trace("Bash", {"command": "python scripts/suggest_layout.py input.json"})
        self.assertTrue(judge.check("style-index-capacity-gate", text, transcript))
        transcript += "\n" + trace("Bash", {"command": "python scripts/check_deck_geometry.py --capacity input.json"})
        transcript += "\n" + json.dumps({"type": "tool_result", "content": "overflow"})
        self.assertEqual(judge.check("style-index-capacity-gate", text, transcript), [])
        self.assertEqual(judge.check("style-index-capacity-gate", "本轮不可生成。", transcript), [])

    def test_command_literal_is_not_tool_result_evidence(self):
        transcript = trace("Bash", {"command": "style load --summary; style render --expected-selection HASH # user style_selection_changed"})
        errors = judge.check("style-index-user-override", "user style_selection_changed", transcript)
        self.assertIn("工具结果未出现选择失效", errors)


if __name__ == "__main__":
    unittest.main()
