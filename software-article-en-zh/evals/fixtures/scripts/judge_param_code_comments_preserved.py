#!/usr/bin/env python3
"""代码注释默认保留：python 围栏完整（2 条围栏线），注释行与代码行逐字保留
（默认 code_policy: preserve，注释不翻译），正文内容词与超时行为保真。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

fences = len(re.findall(r"(?m)^\s*```", text))
if fences != 2:
    print("围栏标记行数为 %d，应为 2（1 个代码块）" % fences, file=sys.stderr)
    sys.exit(1)

# 代码与英文注释逐字保留（默认 preserve：注释不翻译）
for token in (
    "def drain(timeout_ms):",
    "# Drain in-flight tasks before reloading config.",
    "while queue.size() > 0:",
    "queue.pop(timeout_ms)",
):
    if token not in text:
        print("代码块内容被改动或注释被翻译: %s" % token, file=sys.stderr)
        sys.exit(1)

# 正文保真：超时退出行为
if not re.search(r"超时|timeout", text):
    print("缺少超时语义", file=sys.stderr)
    sys.exit(1)
if not re.search(r"退出(代码|码)?\s*1|退出码为 1|以代码 1 退出|exit code 1|返回码 1", text):
    print("缺少退出码 1 的语义锚点", file=sys.stderr)
    sys.exit(1)
if not re.search(r"队列", text):
    print("缺少内容词 队列", file=sys.stderr)
    sys.exit(1)
if not re.search(r"重载|重新加载", text):
    print("缺少内容词 重载/重新加载", file=sys.stderr)
    sys.exit(1)

print("代码注释保留通过")
