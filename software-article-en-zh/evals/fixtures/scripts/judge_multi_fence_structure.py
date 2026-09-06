#!/usr/bin/env python3
"""三个 fenced code block 完整保留：``` 恰好 6 个（3 对），yaml/js/bash 语言标注不丢。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 先剥离"翻译说明/审校说明"等元信息区——说明区引用代码片段属健康行为，不计入译文围栏
m = re.search(r"^#{1,3}\s*(翻译说明|译注|审校\S{0,4}|覆盖与保留说明|交付说明|翻译报告|说明|翻译信息|状态信息|备注)|^\*\*译注|^说明[:：]", text, re.M)
if m:
    text = text[: m.start()]

# 再剥离整篇译文外层可能出现的包装围栏（如把全文包进 ```markdown）：只统计正文围栏
stripped = text.strip()
wrapper = re.match(r"^(```|~~~)[a-zA-Z]*\s*\n", stripped)
if wrapper and re.search(r"\n\s*" + wrapper.group(1) + r"\s*$", stripped):
    stripped = stripped[wrapper.end():]
    stripped = re.sub(r"\n\s*" + wrapper.group(1) + r"\s*$", "", stripped)
    text = stripped

fence_count = text.count("```")
if fence_count != 6:
    print("代码围栏数量错误：期望 6 个 ```（3 对），实际 %d 个" % fence_count, file=sys.stderr)
    sys.exit(1)

for lang_pattern, lang in [(r"```(?:js|javascript)", "js"), (r"```yaml", "yaml"), (r"```bash", "bash")]:
    if not re.search(lang_pattern, text):
        print("缺少语言标注 %s（围栏开标记被改写或翻译）" % lang, file=sys.stderr)
        sys.exit(1)

# 代码内容仍为原文数据：关键标识符未被翻译
if not re.search(r"process\.on\(\"SIGTERM\"", text) and not re.search(r"process\.on\('SIGTERM'", text):
    print("js 代码内容被改写（process.on(SIGTERM...) 缺失）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"kubectl rollout restart worker", text):
    print("bash 代码内容被改写（kubectl rollout restart worker 缺失）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"registry\.example\.com/app:2\.4\.1", text):
    print("yaml 代码内容被改写（镜像地址缺失）", file=sys.stderr)
    sys.exit(1)

print("多围栏结构保留通过")
