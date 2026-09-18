#!/usr/bin/env python3
"""结合最终回复与实际工具轨迹校验索引行为，不接受自述代替工具证据。"""
import json
import os
import re
import shlex
import sys
from pathlib import Path


def transcript_records(transcript):
    try:
        return [json.loads(transcript)]
    except ValueError:
        records = []
        for line in transcript.splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                pass
        return records


def tool_calls(transcript):
    calls = []

    def walk(value):
        if isinstance(value, dict):
            if value.get("role") == "tool_call" and isinstance(value.get("tool_call"), dict):
                call = value["tool_call"]
                calls.append((call.get("name", ""), call.get("arguments", {})))
            elif value.get("type") == "tool_use":
                calls.append((value.get("name", ""), value.get("input", {})))
            elif value.get("type") == "function_call":
                calls.append((value.get("name", ""), value.get("arguments", {})))
            for key, child in value.items():
                if key not in {"thinking", "signature"}:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for record in transcript_records(transcript):
        walk(record)
    return calls


def tool_results(transcript):
    results = []

    def walk(value):
        if isinstance(value, dict):
            if value.get("role") == "tool_result" and isinstance(value.get("tool_result"), dict):
                results.append(json.dumps(value["tool_result"].get("content", ""), ensure_ascii=False))
            elif value.get("type") in {"tool_result", "function_call_output"}:
                results.append(json.dumps(value.get("content", value.get("output", "")), ensure_ascii=False))
            for key, child in value.items():
                if key not in {"thinking", "signature"}:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for record in transcript_records(transcript):
        walk(record)
    return "\n".join(results)


def index_path(path, directory=False):
    """点名查询真值源白名单（U10 后新协议，与 SKILL.md 一致）。

    允许：catalog/generations/<gen>/registry.json（点名查询唯一索引真值，
    SKILL.md「风格库点名查询」条目）与 catalog/current.json（指针）；
    归档树的 generated 摘要仍可读（历史证据）。旧 references/styles/
    00_索引/_INDEX.md 已随旧树退役，不再是合法入口。
    """
    path = str(path)
    if any(part in {"..", "."} for part in path.split("/")) or any(c in path for c in "{}\\"):
        return False
    retired = "/template-library/reference/sources/retired-styles-tree/styles/generated"
    if directory:
        return path.rstrip("/").endswith(retired)
    if path.endswith("/template-library/catalog/current.json"):
        return True
    if "/template-library/catalog/generations/" in path and path.endswith("/registry.json"):
        return True
    return (retired + "/" in path
            and path.endswith(".md"))


def index_shell_read(command):
    """只接受能静态证明读取范围的简单命令及截取输出管道。"""
    command = command.replace("2>/dev/null", "")
    if re.search(r"[$\x60<>\n]", command):
        return None
    # SKILL.md 认可的终端适配：leo-ppt style list（resolver 只读点名查询）
    if re.fullmatch(r"leo-ppt style list( +-{2}[\w-]+| +[^\s\"']+)*", command.strip()):
        return True
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    if ";" in tokens:
        groups = [[]]
        for token in tokens:
            if token == ";":
                groups.append([])
            else:
                groups[-1].append(token)
        if not groups[-1]:
            groups.pop()
        reads = [index_shell_read(shlex.join(group)) if group else None for group in groups]
        return None if any(value is None for value in reads) else any(reads)
    if tokens in (["true"], ["echo", "skip"]):
        return False
    if not tokens or any(token in {"&", "&&", "||"} for token in tokens):
        return None
    if "|" in tokens:
        split = tokens.index("|")
        tail = tokens[split + 1:]
        if not (len(tail) == 2 and tail[0] in {"head", "tail"} and re.fullmatch(r"-\d+", tail[1])
                or len(tail) == 3 and tail[0] in {"head", "tail"} and tail[1] == "-n" and tail[2].isdigit()):
            return None
        tokens = tokens[:split]
    if not tokens:
        return None
    command_name, *args = tokens
    if command_name not in {"cat", "grep", "rg", "head", "tail", "ls"}:
        return None
    operands = []
    pattern_seen = command_name not in {"grep", "rg"}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            remaining = args[i + 1:]
            if not pattern_seen:
                remaining = remaining[1:]
            operands.extend(remaining)
            break
        if arg.startswith("-"):
            if command_name in {"grep", "rg"} and arg in {"-e", "--regexp"}:
                i += 1
                pattern_seen = True
            elif command_name in {"head", "tail"} and arg == "-n":
                i += 1
                if i >= len(args) or not args[i].isdigit():
                    return None
            elif not ((command_name in {"grep", "rg"} and re.fullmatch(r"-[niErhFHsolL]+", arg))
                      or (command_name in {"head", "tail"} and re.fullmatch(r"-\d+", arg))
                      or (command_name == "cat" and arg in {"-n", "-b"})
                      or (command_name == "ls" and re.fullmatch(r"-[la1]+", arg))):
                return None
        elif not pattern_seen:
            pattern_seen = True
        else:
            operands.append(arg)
        i += 1
    if not operands or not all(index_path(path, directory=command_name == "ls") for path in operands):
        return None
    return command_name != "ls"


def advise_trace_errors(transcript):
    """按能力/副作用检查 advise 轨迹，允许宿主等价只读适配器。"""
    errors = []
    calls = tool_calls(transcript)
    has_index_source_read = False
    has_navigation = False
    for name, args in calls:
        lower = name.lower()
        if lower == "skill":
            continue
        if lower in {"read", "read_file"}:
            path = str(args.get("file_path", args.get("path", "")))
            allowed = index_path(path)
            if allowed:
                has_index_source_read = True
            else:
                errors.append("advise 读取了点名查询真值源白名单外文件")
        elif lower in {"grep", "search", "search_files"}:
            path = str(args.get("path", ""))
            glob = str(args.get("glob", ""))
            if index_path(path) or "/template-library/catalog/" in path or (
                    index_path(path, directory=True) and ".." not in glob.split("/") and glob.endswith(".md") and not any(c in glob for c in "{}\\")):
                has_index_source_read = True
            else:
                errors.append("advise 搜索未限定索引范围（catalog/归档摘要）")
        elif lower in {"mcp__codegraph__codegraph_explore", "codegraph_explore"}:
            has_navigation = True
        elif lower in {"bash", "exec_command", "shell", "run_shell_command"}:
            command = str(args.get("command", args.get("cmd", "")))
            source_read = index_shell_read(command)
            if source_read is None:
                errors.append("advise shell 未证明为索引范围只读访问")
            elif source_read:
                has_index_source_read = True
        else:
            errors.append(f"advise 使用了无法证明只读范围的工具: {name}")
    if has_navigation and not has_index_source_read:
        errors.append("CodeGraph 导航未回到索引 Markdown 事实")
    return errors


def check(case, text, transcript):
    errors = []
    calls = tool_calls(transcript)
    results = tool_results(transcript)
    reads = [json.dumps(args, ensure_ascii=False) for name, args in calls if name.lower() in {"read", "read_file"}]
    searches = [args for name, args in calls if name.lower() in {"grep", "search", "search_files"}]
    commands = [json.dumps(args, ensure_ascii=False) for name, args in calls if name.lower() in {"bash", "exec_command", "shell", "run_shell_command"}]
    if case in {"style-index-lookup", "style-index-long-tail", "style-index-fallback", "style-index-prompt-boundary"}:
        errors.extend(advise_trace_errors(transcript))
        if any("/canonical/styles/" in value for value in reads):
            errors.append("advise 点名查询读取了 canonical 完整 brief（应走 registry 索引）")
        for args in searches:
            path = str(args.get("path", ""))
            if "/canonical/styles/" in path:
                errors.append("advise 搜索未限定索引范围（canonical 全量扫描）")
    if case == "style-index-lookup":
        if not all(name in text for name in ("Gruvbox暗风", "终端命令行风")):
            errors.append("共享别名未报告两个真实命中")
        if not re.search(r"选择|选哪|二选一|消歧|确认|指定", text):
            errors.append("缺少消歧出口")
        if not any("registry.json" in value for value in reads) \
                and not any("--filter" in value for value in commands):
            errors.append("缺少实际索引读取轨迹（registry 或 style list --filter）")
    if case == "style-index-long-tail":
        if "地图战略风" not in text or "流光液态风" not in text:
            errors.append("长尾名称未命中")
        if not any("registry.json" in value for value in reads) \
                and not any("--filter" in value for value in commands):
            errors.append("缺少真实索引读取（registry 或 style list --filter）")
    if case == "style-index-fallback":
        if not re.search(r"恢复.*索引|索引.*恢复", text):
            errors.append("索引缺失未给恢复动作")
        if not re.search(r"无法确认|不能确认|不可确认|无法核实", text):
            errors.append("缺失索引被当成有效目录")
    if case == "style-index-prompt-boundary":
        if not re.search(r"not-run|未验证|未做.*验证|未.*视觉验证", text):
            errors.append("coverage 被冒充为视觉通过")
        if not re.search(r"样张", text):
            errors.append("未保留样张门")
    if case == "style-index-user-override":
        if not any("--summary" in value for value in commands):
            errors.append("缺少真实摘要命令")
        if not any("--expected-selection" in value for value in commands):
            errors.append("缺少真实选择守卫命令")
        if "style_selection_changed" not in results:
            errors.append("工具结果未出现选择失效")
        if "user" not in results:
            errors.append("未获得用户作用域证据")
    if case == "style-index-capacity-gate":
        if not any("suggest_layout.py" in value for value in commands):
            errors.append("未运行真实版式调度")
        if not any("check_deck_geometry.py" in value and "--capacity" in value for value in commands):
            errors.append("未运行独立容量检查")
        if "overflow" not in results:
            errors.append("没有硬超工具结果")
        if not re.search(r"阻断|不能.*生成|不得.*生成|不可生成|暂停|不通过|execution_eligibility:\s*blocked", text):
            errors.append("容量硬超未阻断")
    if not calls:
        errors.append("没有可核验工具轨迹")
    return errors


def main():
    case = json.loads(Path("review-case.json").read_text())["case_id"]
    path = os.environ.get("EVAL_TRANSCRIPT_PATH", "")
    transcript = Path(path).read_text() if path and Path(path).is_file() else ""
    errors = check(case, os.environ.get("EVAL_FINAL_MESSAGE", ""), transcript)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
