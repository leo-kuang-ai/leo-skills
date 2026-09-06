#!/usr/bin/env python3
"""Markdown 结构保留：frontmatter 分隔线与 title 键名、##/### 层级各 1 处、列表项>=3、表格竖线行>=3。

适配合法输出形态：译文主体可能被包在单一外层 ```markdown 围栏中，前后带"## 译文"等包装标题
或后随"翻译说明/译注"元信息区——结构计数只针对译文主体，包装自身不计入。
"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# ① 截断翻译说明/译注/审校等元信息区（输出契约要求的元信息区不是译文结构；
#    模型对该区命名多样：翻译说明/译注/审校说明/审校报告/覆盖与保留说明/交付说明等）
m = re.search(r"^#{1,3}\s*(翻译说明|译注|审校\S{0,4}|覆盖与保留说明|交付说明|翻译报告|说明[:：])|^\*\*译注", text, re.M)
if m:
    text = text[: m.start()]

# ② 剥离单一外层 ```markdown 包装围栏：首行是围栏开且存在配对围栏时取其内部
lines = text.splitlines()
if lines and re.match(r"^```\w*\s*$", lines[0]):
    close = next((i for i in range(1, len(lines)) if re.match(r"^```\s*$", lines[i])), None)
    if close is not None:
        text = "\n".join(lines[1:close])

# ③ 剔除包装标题行（"## 译文"等，非源文结构）
text = re.sub(r"(?m)^#{1,3}\s*(译文|中文译文|简体中文译文)\s*$\n?", "", text)

# ④ frontmatter：两条 --- 分隔线 + title 键不被翻译
if len(re.findall(r"(?m)^---\s*$", text)) < 2:
    print("frontmatter 的 --- 分隔线缺失", file=sys.stderr)
    sys.exit(1)
if not re.search(r"(?m)^title\s*:", text):
    print("frontmatter 的 title 键名缺失或被翻译", file=sys.stderr)
    sys.exit(1)
if re.search(r"(?m)^(标题|题目|文档标题)\s*:", text):
    print("frontmatter 键名被翻译成“标题:”", file=sys.stderr)
    sys.exit(1)

# ⑤ 标题层级：## 与 ### 各保留 1 处（数量与源文一致）
h2 = re.findall(r"(?m)^##(?!#)[^\n]*$", text)
h3 = re.findall(r"(?m)^###(?!#)[^\n]*$", text)
if len(h2) != 1:
    print("二级标题数量错误：期望 1 个，实际 %d 个（%s）" % (len(h2), "; ".join(h.strip() for h in h2)), file=sys.stderr)
    sys.exit(1)
if len(h3) != 1:
    print("三级标题数量错误：期望 1 个，实际 %d 个（%s）" % (len(h3), "; ".join(h.strip() for h in h3)), file=sys.stderr)
    sys.exit(1)

# ⑥ 无序列表项 >= 3
list_items = re.findall(r"(?m)^-\s+\S", text)
if len(list_items) < 3:
    print("列表项数量不足：期望至少 3 项，实际 %d 项" % len(list_items), file=sys.stderr)
    sys.exit(1)

# ⑦ 表格竖线行 >= 3（表头 + 分隔行 + 数据行）
pipe_lines = [ln for ln in text.splitlines() if "|" in ln]
if len(pipe_lines) < 3:
    print("表格竖线行不足：期望至少 3 行，实际 %d 行" % len(pipe_lines), file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"^\|?\s*-{2,}\s*\|", ln) for ln in pipe_lines):
    print("表格分隔行（---）缺失", file=sys.stderr)
    sys.exit(1)

# ⑧ 表格内数据保留：max_pool 标识符仍在
if not re.search(r"max_pool", text):
    print("表格中的 max_pool 标识符丢失", file=sys.stderr)
    sys.exit(1)

print("Markdown 结构保留通过")
