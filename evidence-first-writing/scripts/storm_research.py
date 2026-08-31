#!/usr/bin/env python3
# 来源: https://github.com/stanford-oval/storm (MIT)，桥接实现 2026-08-30，授权已确认
"""STORM 多视角研究可选执行器（deep 档 research 的增强，非默认依赖）。

定位（evidence-first-writing 技能）：
- 仅当宿主/用户显式调用时运行，绝不作为技能的默认依赖；未安装上游包时输出
  固定降级指引并以退出码 3 结束，不打印 traceback，不阻塞技能其余工作流。
- 桥接上游 STORM 管线：LitellmModel（LLM 经 litellm 兼容任意 provider）+
  DuckDuckGoSearchRM（免 API key 检索）+ STORMWikiRunner。默认执行
  do_research（persona 多视角对话、信息表）与 do_generate_outline（双大纲
  消融）；``--full`` 再开 do_generate_article（带引用草稿）与
  do_polish_article（润色）。落盘文件名与上游 runner 完全一致。

用法：
    python3 storm_research.py <topic> --out-dir <dir> [--full]

环境变量：
    STORM_LLM_MODEL    必填，litellm 格式模型名（如 openai/gpt-4o）
    STORM_LLM_API_KEY  必填，对应 provider 的 API key
    STORM_LLM_BASE_URL 可选，OpenAI 兼容网关地址（自建/中转时使用）

退出码：0=成功；1=已安装但运行失败；3=输入/参数/环境错误（含依赖缺失降级、
环境变量缺失）。参数错误统一走 3，与 ``check_prose.py`` 的 CLI 契约对齐。

纪律：输出仅供 research 阶段参考，persona 对话与草稿里的引用、数字与事实
必须回到证据账本逐条核验后才能进入写作，不得直接搬运。

上游 import 全部收在函数内，保证未安装 knowledge-storm 的环境仍可导入本
模块做单元测试。脚本自身不依赖机器特定绝对路径。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Mapping

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_INPUT_ERROR = 3

ENV_MODEL = "STORM_LLM_MODEL"
ENV_API_KEY = "STORM_LLM_API_KEY"
ENV_BASE_URL = "STORM_LLM_BASE_URL"

# 与上游 STORMWikiRunnerArguments 默认值保持一致（search_top_k=3）。
DEFAULT_SEARCH_TOP_K = 3

# 五个 LM 槽位的 max_tokens，对齐上游 examples/storm_examples 的推荐配置。
LM_MAX_TOKENS = {
    "conv_simulator": 500,
    "question_asker": 500,
    "outline_gen": 400,
    "article_gen": 700,
    "article_polish": 4000,
}

# 上游 STORMWikiRunner 在 out_dir/<topic 下划线化>/ 下的落盘文件名（engine.py 约定）。
STORM_OUTPUT_FILES = (
    "conversation_log.json",  # persona 多视角对话日志（do_research）
    "raw_search_results.json",  # 信息表：URL 到检索所得的映射（do_research）
    "direct_gen_outline.txt",  # 凭既有知识直写的大纲（消融对照）
    "storm_gen_outline.txt",  # 访谈所得改写后的大纲
    "url_to_info.json",  # 草稿实际引用的来源（do_generate_article）
    "storm_gen_article.txt",  # 带引用草稿（do_generate_article）
    "storm_gen_article_polished.txt",  # 润色稿（do_polish_article）
    "run_config.json",  # 运行配置（post_run）
    "llm_call_history.jsonl",  # LLM 调用历史（post_run）
)

DISCIPLINE_REMINDER = (
    "STORM 结果仅供 research 阶段参考：persona 对话、大纲与草稿中的引用、"
    "数字与事实，必须回到证据账本逐条核验后才能进入写作，不得直接搬运。"
)


class StormConfigError(ValueError):
    """环境变量缺失或非法（模型名 / API key / base URL）。"""


def degradation_message() -> str:
    """依赖缺失时的固定降级指引（stdout 输出，退出码 3，不打印 traceback）。"""
    return "\n".join(
        [
            "# 未检测到 knowledge-storm（import knowledge_storm 失败），已降级退出，不影响技能其余工作流。",
            "# 本执行器是 deep 档 research 的可选增强，不作为默认依赖；如需启用：",
            "# 1. 建议在隔离环境安装，避免污染宿主：python3 -m venv .venv-storm && source .venv-storm/bin/activate",
            "# 2. pip install knowledge-storm（上游 stanford-oval/storm，MIT）",
            "# 3. 设置环境变量 STORM_LLM_MODEL / STORM_LLM_API_KEY（必填）、STORM_LLM_BASE_URL（可选，OpenAI 兼容网关）；",
            "#    LLM 经 litellm 兼容任意 provider，模型名需带 provider 前缀（如 openai/gpt-4o、deepseek/deepseek-chat）。",
            "# 4. 检索默认使用 DuckDuckGoSearchRM，免 API key；随后重跑本命令。",
            "# 未安装也不阻塞研究：references/source-analysis.md「多视角研究方法」一节的方法论可人工执行。",
            "# 退出码：0=成功；1=已安装但运行失败；3=输入/参数/环境错误（含依赖缺失降级）。",
        ]
    )


def build_lm_config_from_env(env: Mapping[str, str]) -> dict[str, str | None]:
    """从环境变量映射构造 LitellmModel 配置。

    model 与 api_key 缺失时抛 :class:`StormConfigError`（消息点名缺失项并给出
    三个变量的完整指引）；base_url 可缺省（返回 None，走 provider 官方端点）。
    入参显式传入 mapping 而非直接读 os.environ，便于单测。
    """
    model = (env.get(ENV_MODEL) or "").strip()
    api_key = (env.get(ENV_API_KEY) or "").strip()
    api_base = (env.get(ENV_BASE_URL) or "").strip() or None
    missing = [
        name
        for name, value in ((ENV_MODEL, model), (ENV_API_KEY, api_key))
        if not value
    ]
    if missing:
        raise StormConfigError(
            f"缺少 {'、'.join(missing)}；"
            f"需要设置 {ENV_MODEL}=litellm 格式模型名（如 openai/gpt-4o）、"
            f"{ENV_API_KEY}=对应密钥，可选 {ENV_BASE_URL}=OpenAI 兼容网关地址。"
        )
    return {"model": model, "api_key": api_key, "api_base": api_base}


def plan_run(full: bool) -> dict[str, bool]:
    """映射为 STORMWikiRunner.run 的四个阶段开关。

    默认只跑 research（persona 对话 + 信息表）与 outline（双大纲消融）；
    ``full=True`` 追加带引用草稿生成与润色。
    """
    return {
        "do_research": True,
        "do_generate_outline": True,
        "do_generate_article": full,
        "do_polish_article": full,
    }


def probe_storm_import() -> ImportError | None:
    """探测上游依赖是否可导入；返回 ImportError（含包损坏场景），可用则返回 None。"""
    try:
        import knowledge_storm  # noqa: F401
        import knowledge_storm.lm  # noqa: F401
        import knowledge_storm.rm  # noqa: F401
    except ImportError as error:
        return error
    return None


def run_research(
    topic: str,
    out_dir: Path,
    env: Mapping[str, str],
    full: bool = False,
) -> int:
    """已安装路径：组装 LitellmModel + DuckDuckGoSearchRM + STORMWikiRunner 并执行。

    上游 import 全部收在本函数内，保证未安装时本模块仍可被导入做单测。
    组装方式对齐上游 examples/storm_examples/run_storm_wiki_gpt.py：五个 LM
    槽位、DuckDuckGoSearchRM(k=search_top_k) 与
    STORMWikiRunnerArguments(output_dir=...)。运行结束后调用 post_run 落盘
    run_config.json 与 llm_call_history.jsonl。
    """
    from knowledge_storm import (
        STORMWikiRunner,
        STORMWikiRunnerArguments,
        STORMWikiLMConfigs,
    )
    from knowledge_storm.lm import LitellmModel
    from knowledge_storm.rm import DuckDuckGoSearchRM

    config = build_lm_config_from_env(env)
    lm_kwargs: dict[str, object] = {
        "model": config["model"],
        "api_key": config["api_key"],
        "temperature": 1.0,
        "top_p": 0.9,
    }
    if config["api_base"]:
        lm_kwargs["api_base"] = config["api_base"]

    def make_lm(slot: str):
        return LitellmModel(max_tokens=LM_MAX_TOKENS[slot], **lm_kwargs)

    lm_configs = STORMWikiLMConfigs()
    lm_configs.set_conv_simulator_lm(make_lm("conv_simulator"))
    lm_configs.set_question_asker_lm(make_lm("question_asker"))
    lm_configs.set_outline_gen_lm(make_lm("outline_gen"))
    lm_configs.set_article_gen_lm(make_lm("article_gen"))
    lm_configs.set_article_polish_lm(make_lm("article_polish"))

    engine_args = STORMWikiRunnerArguments(
        output_dir=str(out_dir), search_top_k=DEFAULT_SEARCH_TOP_K
    )
    retriever = DuckDuckGoSearchRM(k=DEFAULT_SEARCH_TOP_K, safe_search="On", region="us-en")
    runner = STORMWikiRunner(engine_args, lm_configs, retriever)

    runner.run(topic=topic, **plan_run(full))
    if hasattr(runner, "post_run"):
        runner.post_run()
    return EXIT_OK


class StormArgumentParser(argparse.ArgumentParser):
    # 参数错误统一退出码 3，与 check_prose.py 的 CLI 契约一致（argparse 默认是 2）。
    def error(self, message: str):
        self.print_usage(sys.stderr)
        print(f"参数错误：{message}", file=sys.stderr)
        raise SystemExit(EXIT_INPUT_ERROR)


def main(argv: list[str] | None = None) -> int:
    parser = StormArgumentParser(
        description="STORM 多视角研究可选执行器（deep 档 research 增强；依赖缺失时降级退出）"
    )
    parser.add_argument("topic", help="研究主题，例如「多视角研究方法」")
    parser.add_argument(
        "--out-dir",
        required=True,
        help="结果输出目录（上游会在其中按主题名建子目录）",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="额外开启带引用草稿生成与润色（默认只跑 research + outline）",
    )
    args = parser.parse_args(argv)

    if not args.topic.strip():
        print("参数错误：topic 不能为空。", file=sys.stderr)
        return EXIT_INPUT_ERROR

    import_error = probe_storm_import()
    if import_error is not None:
        print(degradation_message())
        return EXIT_INPUT_ERROR

    try:
        run_research(args.topic, Path(args.out_dir), os.environ, full=args.full)
    except StormConfigError as error:
        print(f"环境变量缺失或非法：{error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except Exception as error:  # noqa: BLE001 — CLI 边界统一清晰失败，不刷 traceback
        print(f"STORM 运行失败：{type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_RUN_FAILED

    print(f"# 输出目录：{args.out_dir}")
    print(f"# 产物（上游命名）：{', '.join(STORM_OUTPUT_FILES)}")
    print(f"# {DISCIPLINE_REMINDER}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
