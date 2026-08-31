#!/usr/bin/env python3
# beta-m1 主题提取确定性（B4）：Trust Gate + preflight 已过的可信 PPTX 沿用
# 源风格时，agent 引用 scripts/extract_pptx_theme.py 确定性输出与
# --color 覆盖命令（deck 锚点通道），HEX 不进风格 brief palette。
# 否定感知拦截「看起来是蓝色商务风」肉眼判读充当结论。
import os, re, sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(m):
    print(m, file=sys.stderr)
    raise SystemExit(1)


def require_any(vals, label):
    if not any(v in text for v in vals):
        fail(f"缺少{label}: {' | '.join(vals)}")


QUOTE_SPAN = re.compile(
    r"(「[^」]*」|『[^』]*』|“[^”]*”|‘[^’]*’|《[^》]*》|\"[^\"]*\"|'[^']*')"
)


def plain(sentence):
    return QUOTE_SPAN.sub("", sentence)


negators = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "绝不", "而非", "不是",
    "无法", "别", "勿", "严禁", "只", "仅",
)


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        body = plain(sentence)
        for clause in re.split(r"[；;，,]", body):
            if clause and any(re.search(p, clause) for p in patterns) and not any(
                v in clause for v in negators
            ):
                return sentence
    return None


# ① 确定性脚本被引用
require_any(("extract_pptx_theme", "主题提取.{0,8}脚本"), "提取脚本引用")
# ② 输出要素（12 slot / 字体映射 / 角色色 / sha256 / 确定性）
require_any(("12 ?slot", "调色板", "clrMap", "角色色", "primary",
             "office_font", "字体映射", "sha256", "键排序", "确定性"),
            "提取输出要素")
# ③ 覆盖通道命令（--color role=HEX，deck 级）
require_any(("--color", "color_palette", "覆盖通道", "deck 级"),
            "覆盖通道命令")

# ④ 否定感知：肉眼判读当结论 / HEX 写进风格 brief。
bad = positive((
    r"看(?:起来|上去).{0,16}(?:是|像).{0,12}(?:蓝|红|黑|商务|科技)\S{0,4}风(?:格)?的?(?:结论|就是)",
    r"(?:我|肉眼|目测).{0,8}(?:看|扫).{0,12}(?:主色|配色|色值|主题).{0,8}(?:是|应该)",
    r"(?:写进|写入|存进|固化为).{0,10}(?:风格 ?brief|brief).{0,14}(?:色值|HEX|#)",
    r"HEX.{0,14}(?:写|存|固化).{0,10}(?:brief|固有)",
))
if bad:
    fail(f"肉眼判读充当结论或将 HEX 固化进风格 brief: {bad}")
