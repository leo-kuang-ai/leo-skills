#!/usr/bin/env python3
# Judge for "academic-vertical-entry": with an explicit "学术模式" request and
# paper material, the first execute turn must treat it as the academic vertical:
# contract must raise the three academic fields (math_load / figure_orientation /
# section_priority) and ask the delivery tier (minimal vs dense-defense) instead
# of defaulting, and must not start generating or claim any confirmation.
import os
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_any(values, what):
    if not any(v in text for v in values):
        fail(f"缺少{what}: {' / '.join(values)}")


require_any(("math_load", "数学量级"), "数学量级字段")
require_any(("figure_orientation", "图表取向"), "图表取向字段")
require_any(("section_priority", "分节优先级", "分节"), "分节优先级字段")
require_any(
    ("组会", "minimal", "答辩证据密集", "dense-defense", "答辩档位", "交付档位"),
    "答辩档位询问",
)
# The tier must not be silently defaulted to dense. The bare word 确认 is
# acceptable here: premature "已确认/已冻结" claims are rejected by the scan
# below, so it cannot fake the ask.
require_any(
    ("不得默认", "未问明不默认", "请选择", "请明确", "需要你定", "等你确认", "二选一",
     "待确认", "需确认", "等你回复", "请回复", "待你", "确认后", "确认"),
    "档位交给用户选择",
)

negators = ("未", "尚未", "没有", "不", "待", "等")
for line in text.splitlines():
    if ("已确认" in line or "已冻结" in line or "已生成" in line) and not any(w in line for w in negators):
        fail(f"首轮即声称已确认/已生成: {line.strip()}")
