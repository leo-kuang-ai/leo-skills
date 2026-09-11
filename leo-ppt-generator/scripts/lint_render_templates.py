#!/usr/bin/env python3
"""lint_render_templates.py — E5 渲染模板合同 lint（gamma M1）。

对 ``template-library/canonical/templates/*/page.html`` 执行 render:html 专属规则
（规则-渲染器映射见 ``assets/render-lint-rules.json`` 的 ``template.*`` 键；
skip 集/映射改动走 style-lint-baseline.txt 式白名单登记纪律）：

- ``template.ready_signal``        模板置 ``data-leo-ready`` 显式信号（ERROR）
- ``template.deterministic_mode``  ``?leo_render=1`` 禁动画兜底（ERROR）
- ``template.no_file_fonts``       禁 ``file://`` 与远程字体 URL（ERROR）
- ``template.canvas_contract``     根容器 1280x720 + overflow:hidden +
  ``data-leo-block`` 锚点（ERROR）
- ``template.data_injection_only`` 不得 fetch 外部资源（ERROR）

规则-渲染器适配接口：``--renderer <name>`` 只检查 applies 命中的规则
（如 ``--renderer image-model`` 时全部 template.* 规则 skip 并披露——
供 E5 消费方按页级 backend 来源交叉调用）。

退出码（CI-4）：0 全过；1 存在 ERROR；2 仅 WARN。本 lint 的合同条款
无 WARN 级（条款不满足即 ERROR；顺带的披露性发现按 WARN 输出）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RULES_FILE = Path(__file__).resolve().parents[1] / "assets/render-lint-rules.json"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "template-library/canonical/templates"

TEMPLATE_RULES = (
    "template.ready_signal",
    "template.deterministic_mode",
    "template.no_file_fonts",
    "template.canvas_contract",
    "template.data_injection_only",
)


def load_rules() -> dict:
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def rule_applies(rule: dict, renderer: str) -> bool:
    for pattern in rule.get("applies", []):
        if pattern == renderer or (
            pattern.endswith(":*") and renderer.startswith(pattern[:-1])
        ):
            if renderer in rule.get("skip", []):
                return False
            return True
    return False


def _check_ready_signal(text: str) -> list[str]:
    problems = []
    if "leoReady" not in text:
        problems.append("缺 data-leo-ready 就绪信号脚本（document.documentElement.dataset.leoReady）")
    if "fonts.ready" not in text:
        problems.append("ready 信号未挂 document.fonts.ready（字体未就绪即置位 = 时序漏气）")
    return problems


def _check_deterministic_mode(text: str) -> list[str]:
    problems = []
    if "leo_render" not in text:
        problems.append("未识别 ?leo_render=1 deterministic 模式查询参数")
    if "animation: none" not in text.replace(" !important", ""):
        problems.append("缺 html[data-leo-render] 禁动画兜底 CSS")
    return problems


def _check_no_file_fonts(text: str) -> list[str]:
    problems = []
    if re.search(r"url\(\s*file://", text, re.IGNORECASE):
        problems.append("出现 file:// 字体直引（headless 下静默失败，必须走 /leo-fonts/ HTTP）")
    if re.search(r"url\(\s*https?://", text, re.IGNORECASE):
        problems.append("出现远程 URL 资源引用（离线确定合同禁止）")
    if "@font-face" in text and "/leo-fonts/" not in text:
        problems.append("@font-face 未指向 /leo-fonts/ 供给路径")
    return problems


def _check_canvas_contract(text: str) -> list[str]:
    problems = []
    if not re.search(r"width:\s*1280px", text) or not re.search(r"height:\s*720px", text):
        problems.append("根容器未声明 1280x720 逻辑画幅")
    if "overflow: hidden" not in text and "overflow:hidden" not in text:
        problems.append("未声明 overflow:hidden（禁止滚动条入图）")
    if "data-leo-block" not in text:
        problems.append("缺 data-leo-block 结构锚点（E2 对账/E5 lint 依赖）")
    return problems


def _check_data_injection_only(text: str) -> list[str]:
    problems = []
    if re.search(r"\bfetch\s*\(", text):
        problems.append("模板内出现 fetch()（数据只允许来自 window.__LEO_SLIDE_DATA__ 注入）")
    if re.search(r"XMLHttpRequest|import\s*\(\s*['\"]https?://", text):
        problems.append("模板内出现外部网络请求原语")
    if "__LEO_SLIDE_DATA__" not in text:
        problems.append("模板未消费 window.__LEO_SLIDE_DATA__")
    return problems


CHECKERS = {
    "template.ready_signal": _check_ready_signal,
    "template.deterministic_mode": _check_deterministic_mode,
    "template.no_file_fonts": _check_no_file_fonts,
    "template.canvas_contract": _check_canvas_contract,
    "template.data_injection_only": _check_data_injection_only,
}


def lint_template(path: Path, renderer: str, rules: dict) -> dict:
    text = path.read_text(encoding="utf-8")
    errors: list[dict] = []
    skipped: list[str] = []
    for rule_id in TEMPLATE_RULES:
        rule = rules["rules"].get(rule_id)
        if rule is None or not rule_applies(rule, renderer):
            skipped.append(rule_id)
            continue
        for problem in CHECKERS[rule_id](text):
            errors.append({"rule": rule_id, "file": f"{path.parent.name}/{path.name}", "problem": problem})
    return {"file": f"{path.parent.name}/{path.name}", "errors": errors, "skipped_rules": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--renderer", default="render:html",
                        help="按页级 backend 来源过滤规则（缺省 render:html；"
                             "如 image-model 则全部 template.* 规则 skip 并披露）")
    parser.add_argument("--templates-dir", default=str(TEMPLATES_DIR))
    args = parser.parse_args(argv)

    rules = load_rules()
    templates_dir = Path(args.templates_dir)
    html_files = sorted(templates_dir.glob("*/page.html"))
    if not html_files:
        print(f"ERROR: 未找到模板于 {templates_dir}", file=sys.stderr)
        return 1

    results = [lint_template(path, args.renderer, rules) for path in html_files]
    error_count = sum(len(r["errors"]) for r in results)
    for result in results:
        status = "OK" if not result["errors"] else "ERROR"
        print(f"{result['file']}: {status}"
              + (f"（skip: {', '.join(result['skipped_rules'])}）" if result["skipped_rules"] else ""))
        for error in result["errors"]:
            print(f"  [XX] {error['rule']}: {error['problem']}")
    print(
        f"TOTAL: {len(results)} templates, ERROR={error_count}"
        + (f" → EXIT 1（render_template_contract_violation）" if error_count else " → EXIT 0")
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
