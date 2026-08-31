#!/usr/bin/env python3
"""STORM 多视角研究可选执行器桥的单元测试。

本仓库测试环境不安装 knowledge-storm：降级路径用 subprocess 直测 CLI；
已安装路径通过向 sys.modules 注入最小假包（记录调用参数）验证组装逻辑，
无需真实安装。
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "storm_research.py"
SOURCE_ANALYSIS = SKILL_ROOT / "references" / "source-analysis.md"

# 纯逻辑部分按可测函数导入：未安装 knowledge-storm 时模块必须仍可导入。
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import storm_research  # noqa: E402


class DegradationTests(unittest.TestCase):
    """依赖缺失：CLI 输出固定降级块，退出码 3，不打印 traceback。"""

    def run_cli_with_missing_dependency(self, *cli_args: str) -> subprocess.CompletedProcess[str]:
        # 在 PYTHONPATH 前置一个 import 即抛 ImportError 的假包，无论宿主是否
        # 安装过真实 knowledge-storm，子进程都会进入"未安装"分支，测试可确定性复现。
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_pkg = Path(temp_dir) / "knowledge_storm"
            stub_pkg.mkdir()
            (stub_pkg / "__init__.py").write_text(
                'raise ImportError("stub: simulate missing knowledge-storm")\n',
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = str(temp_dir) + os.pathsep + env.get("PYTHONPATH", "")
            return subprocess.run(
                ["python3", str(SCRIPT), *cli_args],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

    def test_missing_dependency_degrades_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_cli_with_missing_dependency("sample topic", "--out-dir", temp_dir)
        self.assertEqual(result.returncode, 3)
        self.assertIn("pip install knowledge-storm", result.stdout)
        self.assertIn("DuckDuckGoSearchRM", result.stdout)
        self.assertIn("litellm", result.stdout)
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_dependency_does_not_create_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "storm-out"
            result = self.run_cli_with_missing_dependency("sample topic", "--out-dir", str(out_dir))
            self.assertEqual(result.returncode, 3)
            self.assertFalse(out_dir.exists())


class ArgumentValidationTests(unittest.TestCase):
    """参数校验：缺 topic / 缺 --out-dir / 空 topic 都给明确错误退出（3）。"""

    def run_cli(self, *cli_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *cli_args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_missing_topic_exits_with_usage_error(self) -> None:
        result = self.run_cli()
        self.assertEqual(result.returncode, 3)
        self.assertIn("参数错误", result.stderr)

    def test_missing_out_dir_exits_with_usage_error(self) -> None:
        result = self.run_cli("some topic")
        self.assertEqual(result.returncode, 3)
        self.assertIn("--out-dir", result.stderr)

    def test_blank_topic_is_rejected(self) -> None:
        # 空 topic 属输入校验，先于依赖探测，已安装环境同样返回 3。
        with tempfile.TemporaryDirectory() as temp_dir:
            code = storm_research.main(["   ", "--out-dir", temp_dir])
        self.assertEqual(code, 3)


class PureFunctionTests(unittest.TestCase):
    """纯函数：环境变量两态、plan_run 默认与 --full 差异、降级消息锚点。"""

    def test_build_lm_config_requires_model_and_api_key(self) -> None:
        with self.assertRaises(storm_research.StormConfigError) as ctx:
            storm_research.build_lm_config_from_env({})
        message = str(ctx.exception)
        self.assertIn("缺少 STORM_LLM_MODEL、STORM_LLM_API_KEY", message)
        self.assertIn("STORM_LLM_BASE_URL", message)

    def test_build_lm_config_names_only_the_missing_vars(self) -> None:
        with self.assertRaises(storm_research.StormConfigError) as ctx:
            storm_research.build_lm_config_from_env(
                {storm_research.ENV_API_KEY: "sk-test"}
            )
        message = str(ctx.exception)
        self.assertIn("缺少 STORM_LLM_MODEL", message)
        self.assertNotIn("缺少 STORM_LLM_MODEL、STORM_LLM_API_KEY", message)

    def test_build_lm_config_complete_env(self) -> None:
        config = storm_research.build_lm_config_from_env(
            {
                storm_research.ENV_MODEL: "deepseek/deepseek-chat",
                storm_research.ENV_API_KEY: "sk-test",
                storm_research.ENV_BASE_URL: "https://api.example.com/v1",
            }
        )
        self.assertEqual(
            config,
            {
                "model": "deepseek/deepseek-chat",
                "api_key": "sk-test",
                "api_base": "https://api.example.com/v1",
            },
        )

    def test_build_lm_config_base_url_is_optional(self) -> None:
        config = storm_research.build_lm_config_from_env(
            {
                storm_research.ENV_MODEL: "openai/gpt-4o",
                storm_research.ENV_API_KEY: "sk-test",
            }
        )
        self.assertIsNone(config["api_base"])

    def test_plan_run_default_is_research_and_outline_only(self) -> None:
        self.assertEqual(
            storm_research.plan_run(False),
            {
                "do_research": True,
                "do_generate_outline": True,
                "do_generate_article": False,
                "do_polish_article": False,
            },
        )

    def test_plan_run_full_enables_article_and_polish(self) -> None:
        default = storm_research.plan_run(False)
        plan = storm_research.plan_run(True)
        self.assertTrue(plan["do_generate_article"])
        self.assertTrue(plan["do_polish_article"])
        # --full 只追加草稿与润文，research 与 outline 保持默认开启。
        self.assertEqual(plan["do_research"], default["do_research"])
        self.assertEqual(plan["do_generate_outline"], default["do_generate_outline"])

    def test_degradation_message_anchors(self) -> None:
        message = storm_research.degradation_message()
        for anchor in (
            "pip install knowledge-storm",
            "venv",
            "DuckDuckGoSearchRM",
            "litellm",
            "多视角研究方法",
        ):
            self.assertIn(anchor, message)


# ---- 注入 sys.modules 的最小假包：记录调用参数，模拟已安装路径。 ----


class _FakeLitellmModel:
    instances: list["_FakeLitellmModel"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        type(self).instances.append(self)


class _FakeDuckDuckGoSearchRM:
    instances: list["_FakeDuckDuckGoSearchRM"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        type(self).instances.append(self)


class _FakeLMConfigs:
    def __init__(self):
        self.slots = {}

    def set_conv_simulator_lm(self, lm):
        self.slots["conv_simulator_lm"] = lm

    def set_question_asker_lm(self, lm):
        self.slots["question_asker_lm"] = lm

    def set_outline_gen_lm(self, lm):
        self.slots["outline_gen_lm"] = lm

    def set_article_gen_lm(self, lm):
        self.slots["article_gen_lm"] = lm

    def set_article_polish_lm(self, lm):
        self.slots["article_polish_lm"] = lm


class _FakeRunnerArguments:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeRunner:
    last: "_FakeRunner | None" = None

    def __init__(self, engine_args, lm_configs, rm):
        self.engine_args = engine_args
        self.lm_configs = lm_configs
        self.rm = rm
        self.run_calls: list[tuple[str, dict[str, bool]]] = []
        self.post_run_called = False
        type(self).last = self

    def run(self, topic, **flags):
        self.run_calls.append((topic, flags))
        # 模拟上游 engine.py 行为：在 output_dir/<topic 下划线化>/ 创建产物目录。
        os.makedirs(
            os.path.join(self.engine_args.output_dir, topic.replace(" ", "_")),
            exist_ok=True,
        )

    def post_run(self):
        self.post_run_called = True


class InstalledPathTests(unittest.TestCase):
    """已安装路径：注入假 knowledge_storm，验证组装与 runner 调用确实发生。"""

    env = {
        storm_research.ENV_MODEL: "openai/gpt-4o",
        storm_research.ENV_API_KEY: "sk-test",
        storm_research.ENV_BASE_URL: "https://api.example.com/v1",
    }

    def setUp(self) -> None:
        _FakeLitellmModel.instances = []
        _FakeDuckDuckGoSearchRM.instances = []
        _FakeRunner.last = None

    def install_fake_storm(self):
        package = types.ModuleType("knowledge_storm")
        package.STORMWikiRunner = _FakeRunner
        package.STORMWikiRunnerArguments = _FakeRunnerArguments
        package.STORMWikiLMConfigs = _FakeLMConfigs
        lm_module = types.ModuleType("knowledge_storm.lm")
        lm_module.LitellmModel = _FakeLitellmModel
        rm_module = types.ModuleType("knowledge_storm.rm")
        rm_module.DuckDuckGoSearchRM = _FakeDuckDuckGoSearchRM
        package.lm = lm_module
        package.rm = rm_module
        return mock.patch.dict(
            sys.modules,
            {
                "knowledge_storm": package,
                "knowledge_storm.lm": lm_module,
                "knowledge_storm.rm": rm_module,
            },
        )

    def test_run_research_wires_topic_flags_and_output_dir(self) -> None:
        with self.install_fake_storm(), tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "storm-out"
            code = storm_research.run_research(
                "multi perspective research", out_dir, self.env
            )
            self.assertEqual(code, 0)
            runner = _FakeRunner.last
            self.assertIsNotNone(runner)
            topic, flags = runner.run_calls[-1]
            self.assertEqual(topic, "multi perspective research")
            self.assertEqual(flags, storm_research.plan_run(False))
            self.assertTrue(runner.post_run_called)
            self.assertEqual(runner.engine_args.output_dir, str(out_dir))
            # 上游在 output_dir 下按主题名建目录，验证 out-dir 透传成功。
            self.assertTrue((out_dir / "multi_perspective_research").is_dir())

    def test_run_research_builds_five_lms_from_env(self) -> None:
        with self.install_fake_storm(), tempfile.TemporaryDirectory() as temp_dir:
            storm_research.run_research("some topic", Path(temp_dir), self.env)
            models = _FakeLitellmModel.instances
            self.assertEqual(len(models), 5)
            for model in models:
                self.assertEqual(model.kwargs["model"], "openai/gpt-4o")
                self.assertEqual(model.kwargs["api_key"], "sk-test")
                self.assertEqual(model.kwargs["api_base"], "https://api.example.com/v1")
            self.assertEqual(
                sorted(model.kwargs["max_tokens"] for model in models),
                sorted(storm_research.LM_MAX_TOKENS.values()),
            )
            runner = _FakeRunner.last
            self.assertEqual(len(runner.lm_configs.slots), 5)
            self.assertTrue(all(runner.lm_configs.slots.values()))
            self.assertEqual(
                runner.rm.kwargs["k"], storm_research.DEFAULT_SEARCH_TOP_K
            )

    def test_full_flag_reaches_runner(self) -> None:
        with self.install_fake_storm(), tempfile.TemporaryDirectory() as temp_dir:
            storm_research.run_research(
                "some topic", Path(temp_dir), self.env, full=True
            )
            _, flags = _FakeRunner.last.run_calls[-1]
            self.assertEqual(flags, storm_research.plan_run(True))
            self.assertTrue(all(flags.values()))

    def test_main_success_prints_discipline_reminder(self) -> None:
        captured = io.StringIO()
        with (
            self.install_fake_storm(),
            tempfile.TemporaryDirectory() as temp_dir,
            mock.patch.dict(os.environ, self.env),
            redirect_stdout(captured),
        ):
            code = storm_research.main(
                ["bridge topic", "--out-dir", str(Path(temp_dir) / "out")]
            )
        self.assertEqual(code, 0)
        output = captured.getvalue()
        self.assertIn("证据账本", output)
        self.assertIn("storm_gen_outline.txt", output)


class ReferencePointerTests(unittest.TestCase):
    """source-analysis.md「多视角研究方法」节末尾指向可选执行器。"""

    def test_source_analysis_mentions_optional_executor(self) -> None:
        text = SOURCE_ANALYSIS.read_text(encoding="utf-8")
        section_start = text.index("## 多视角研究方法")
        section_end = text.index("## 视频证据获取")
        pointer = text.index("storm_research.py")
        self.assertGreater(pointer, section_start)
        self.assertLess(pointer, section_end)
        # 指针同时声明降级态与核验纪律。
        self.assertIn("证据账本", text[section_start:section_end])


if __name__ == "__main__":
    unittest.main()
