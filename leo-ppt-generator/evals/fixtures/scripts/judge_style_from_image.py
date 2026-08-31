#!/usr/bin/env python3
# 照图做：跳过推荐直行提取视觉系统；复用样张并排比对；不提取业务内容。
import os, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
require_any(("提取","参考图"), "参考图提取")
require_any(("配色", "视觉系统", "字重", "纹理", "留白"), "只提取视觉系统")
require_any(("样张",), "样张验证")
require_any(("并排","比对","对比","像不像"), "并排比对")
require_any(("业务", "正文", "人脸", "标识", "水印"), "不提取边界提及")
