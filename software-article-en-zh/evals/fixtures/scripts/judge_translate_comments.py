#!/usr/bin/env python3
"""只译注释：python 围栏在场、代码行逐字保留且不含中文、注释行含中文、S3 保留。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# ① 围栏与代码本体
if not re.search(r"```python", text):
    print("缺少 ```python 开栏标注", file=sys.stderr)
    sys.exit(1)
if text.count("```") < 2:
    print("代码围栏不完整（少于 2 个 ```）", file=sys.stderr)
    sys.exit(1)
for code in ("def upload(path):", "return queue.push(path)"):
    if code not in text:
        print("代码本体被改动: %s" % code, file=sys.stderr)
        sys.exit(1)
if "S3" not in text:
    print("S3 标识丢失", file=sys.stderr)
    sys.exit(1)

# ② 代码行不得中文化（def/return/queue.push 行内不得出现中文）
for line in text.splitlines():
    if re.match(r"^\s*(def |return |queue\.push)", line) and re.search(r"[\u4e00-\u9fff]", line):
        print("代码行被混入中文: %s" % line.strip(), file=sys.stderr)
        sys.exit(1)

# ③ 注释已译：# 注释行含中文且语义在场
comment_lines = [l for l in text.splitlines() if re.match(r"^\s*#", l) and re.search(r"[\u4e00-\u9fff]", l)]
if not comment_lines:
    print("注释未翻译为中文（未发现含中文的 # 注释行）", file=sys.stderr)
    sys.exit(1)
comment_text = "\n".join(comment_lines)
if not re.search(r"重试|退避|上传", comment_text):
    print("首条注释语义缺失（重试/退避/上传）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"队列|回退|不可达|无法访问|本地", comment_text):
    print("次条注释语义缺失（队列/回退/不可达）", file=sys.stderr)
    sys.exit(1)

print("只译注释策略通过")
