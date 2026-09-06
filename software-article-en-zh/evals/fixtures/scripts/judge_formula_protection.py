#!/usr/bin/env python3
r"""公式保护：行内 LaTeX $hit\_rate = \frac{hits}{hits+misses}$ 与公式块
$$ T_{miss} = T_{lookup} + P \cdot T_{fetch} $$ 原样在场——\frac、hit\_rate（接受 hit_rate
等价转义形态）、hits/misses、T_{miss}/T_{lookup}/T_{fetch}（接受下划线等价形态）、\cdot（或 ·）、
$$ 定界符与行内 $ 定界不被翻译或改写；对照断言普通数字单位 240 ms 同样保真。

否定感知设计：先截断"翻译说明/译注"等元信息区——说明区"公式已保留"的声明不算正文保真，
防止无公式符号但声称完整翻译的输出蒙混通过；中文叙述（命中率/延迟等）与公式并存是健康
形态，不做裸 must_not_contain，公式被中文叙述整体替代经由公式符号缺席的正向断言失败暴露。
"""
import os
import re
import sys

raw = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 截断元信息说明区（命名变体与 judge_markdown_structure 对齐）
m = re.search(
    r"^#{1,3}\s*(翻译说明|译注|审校\S{0,4}|覆盖与保留说明|交付说明|翻译报告|说明[:：])|^\*\*译注",
    raw,
    re.M,
)
body = raw[: m.start()] if m else raw


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def has_any(*needles):
    return any(n in body for n in needles)


# ① 行内公式：\frac 与标识符在场（接受 hit\_rate 与 hit_rate 两种转义形态）
if r"\frac" not in body:
    fail(r"行内公式 \frac 缺失（公式可能被中文叙述整体替代）")
if not has_any(r"hit\_rate", "hit_rate"):
    fail("公式标识符 hit_rate 缺失或被中文化（接受 hit\\_rate 与 hit_rate 两种转义形态）")
for ident in ["hits", "misses"]:
    if not re.search(r"\b%s\b" % ident, body):
        fail("公式标识符 %s 缺失或被中文化" % ident)

# ② 公式块：T_{miss} 等符号与 \cdot 在场（接受下划线等价形态与 · 乘号）
if not has_any("T_{miss}", "T_miss"):
    fail("公式符号 T_{miss} 缺失或被中文化（接受 T_{miss} 与 T_miss 两种形态）")
if not has_any("T_{lookup}", "T_lookup"):
    fail("公式符号 T_{lookup} 缺失或被中文化")
if not has_any("T_{fetch}", "T_fetch"):
    fail("公式符号 T_{fetch} 缺失或被中文化")
if not has_any(r"\cdot", "·"):
    fail(r"公式符号 \cdot（或 ·）缺失或被中文化")

# ③ 对照断言：普通数字与单位同样保真
if not re.search(r"240\s*ms", body):
    fail("普通数字单位 240 ms 未保真（被译为毫秒、换算或改写）")

# ④ 公式块结构：$$ 定界符至少一对（整体叙述化或改写为其他定界即失败）
if body.count("$$") < 2:
    fail("公式块 $$ 定界符缺失（公式块被中文叙述替代或改写为其他定界形式）")

# ⑤ 行内公式定界：$ 紧邻公式标识符（防裸公式文本）
if not re.search(r"\$hit\\?_?rate", body):
    fail("行内公式 $ 定界符缺失或与公式分离")

print("公式保护通过")
