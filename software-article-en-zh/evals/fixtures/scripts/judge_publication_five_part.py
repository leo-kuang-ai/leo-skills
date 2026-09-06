#!/usr/bin/env python3
"""五件套在场检查：publication 交付必须含 译文正文 + 翻译说明 + 术语表 + 歧义与原文问题 +
未解决事项/需作者确认 五个组件；无已知项允许“无已知/无”，但节不得缺失。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 20:
    print("缺少中文译文主体", file=sys.stderr)
    sys.exit(1)

parts = [
    (r"翻译说明|译文说明|术语与处理说明|处理说明|翻译注记|译注", "翻译说明"),
    (r"术语表|术语对照|术语清单|术语说明|术语与\S{0,6}说明", "技术术语表"),
    (r"歧义与原文问题|歧义|原文问题|源文问题", "歧义与原文问题清单"),
    (r"未解决(事项|项|问题)|需作者确认|待确认", "未解决事项/需作者确认"),
]
for pat, label in parts:
    if not re.search(pat, text):
        print("五件套缺少组件：%s" % label, file=sys.stderr)
        sys.exit(1)

# 译文主体内容词（工具说明段）
for a in ("配置", "非零", "修改"):
    if a not in text:
        print("译文主体缺少内容词 %s（疑未翻译）" % a, file=sys.stderr)
        sys.exit(1)

print("五件套交付通过")
