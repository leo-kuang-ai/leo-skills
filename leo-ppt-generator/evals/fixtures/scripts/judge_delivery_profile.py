#!/usr/bin/env python3
# Judge for "delivery-profile-contract-advisory": the reply must explain that a
# saved delivery profile prefills the contract draft (each field tagged with its
# source, user confirms only deltas), that profiles hold preferences only (no
# business data), and that data-classification confirmation is NOT waived by a
# profile. Advise mode must not claim the profile was already saved this turn.
import os
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_any(values, what):
    if not any(v in text for v in values):
        fail(f"缺少{what}: {' / '.join(values)}")


# Profile storage semantics.
require_any(("profiles/", "交付档案"), "档案通道")

# Prefill semantics: draft pre-filled, user confirms deltas.
require_any(("预填", "预置", "默认带入", "只确认差异", "差异项", "逐项标注来源"), "预填语义")

# Preferences-only boundary.
require_any(("只存偏好", "偏好字段", "不存业务数据", "业务数据不入档", "不保存业务"), "只存偏好边界")

# Classification confirmation is not waived (negative-aware semantics).
if not (("分级" in text) and any(w in text for w in ("仍须", "仍会", "不豁免", "不因", "仍要", "再确认"))):
    fail("缺少分级确认不豁免的表述")

# Advise must not claim a save happened this turn.
negators = ("未", "尚未", "没有", "不", "待", "需要你", "等")
for line in text.splitlines():
    if ("已保存" in line or "已存入" in line) and not any(w in line for w in negators):
        fail(f"advise 轮声称已完成保存: {line.strip()}")
